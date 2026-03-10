# ARIIA Legacy Code Analysis Report

**Erstellt:** 2026-03-10
**Scope:** `/opt/ariia/production/app/`
**Methode:** Statische Strukturanalyse, Import-Tracing, Alembic-Chain-Audit

---

## 1. Executive Summary

Die Codebase enthält mehrere Generations-Schichten aus iterativer Refaktorierung: v1-Module koexistieren mit v2-Ersetzungen, Monkey-Patch-Bridges überbrücken inkompatible Architekturen, und die Alembic-Migrationskette enthält eine kritische Fehlkonfiguration, die `alembic heads` zum Absturz bringt. Höchste Dringlichkeit hat der Alembic-Kettenbruch (Priorität 1), gefolgt von der Konsolidierung doppelter v1/v2-Module (Priorität 2).

---

## 2. Doppelte Module (v1 vs v2)

### 2.1 Memory Librarian

| Datei | Zeilen | Status |
|-------|--------|--------|
| `app/memory/librarian.py` | 79 | v1 – veraltet, nur noch in `app/core/maintenance.py` referenziert |
| `app/memory/librarian_v2.py` | 575 | v2 – aktiver Worker mit Redis-Stream, Retry-Logik, Fallback-Mechanismus |

**Befund:** `librarian.py` (v1) ist ein 79-Zeilen-Stub, der direkt mit SQLAlchemy arbeitet und keine Fehlertoleranz besitzt. `librarian_v2.py` ersetzt es vollständig mit einem Redis-Stream-Worker. v1 wird nur noch von `app/core/maintenance.py` importiert – kein Produktionspfad.

**Empfehlung:** `librarian.py` entfernen; `maintenance.py` auf v2 migrieren.

### 2.2 Swarm Master Orchestrator

| Datei | Zeilen | Status |
|-------|--------|--------|
| `app/swarm/master/orchestrator.py` | 122 | v1 – Regex-basiertes Tool-Parsing |
| `app/swarm/master/orchestrator_v2.py` | 631 | v2 – natives OpenAI Function Calling, aktiv genutzt |

**Befund:** v2 wird von `app/swarm/router/router.py` und `app/gateway/routers/webhooks.py` importiert. v1 verwendet ein `TOOL: worker_name("query")` Regex-Muster, das in v2 vollständig durch strukturiertes Tool-Calling ersetzt wurde. v1 ist in keinem aktiven Produktionspfad eingebunden.

**Empfehlung:** `orchestrator.py` (v1) entfernen. `orchestrator_v2.py` in `orchestrator.py` umbenennen.

---

## 3. Fragliche/Experimentelle Module

### 3.1 `app/acp/` — Autonomes Code-Patching-System

| Datei | Beschreibung |
|-------|-------------|
| `refactor.py` | AST-basierte Refaktorierungsvorschläge (Sprint 6a) |
| `rollback.py` | Git-Checkpoint-basiertes Rollback-System |
| `sandbox.py` | Sandbox-Executor für Refaktorierungen |
| `server.py` | FastAPI-Router, eingebunden in `app/gateway/main.py` |

**Befund:** Das ACP-Modul ermöglicht es dem System, eigenen Code zu analysieren und Änderungsvorschläge zu erzeugen. Der Router ist aktiv in `main.py` eingebunden (`from app.acp.server import router as acp_router`). Das Modul birgt operationelles Risiko: Fehler im Selbst-Refaktorierungsmodus können Produktionscode beschädigen. Laut BMAD-Cycle-Vorgabe sollten irreversible Aktionen manuell bestätigt werden.

**Empfehlung:** ACP-Router hinter Feature-Flag (`ACP_ENABLE=1`) stellen; in Produktionsumgebungen standardmäßig deaktiviert lassen.

### 3.2 `app/soul/` — Persona-Evolutions-System

| Datei | Beschreibung |
|-------|-------------|
| `analyzer.py` | Log-Analyse zur Trend-Erkennung (Sprint 6b) |
| `evolver.py` | Schlägt SOUL.md-Updates vor |
| `flow.py` | Orchestriert Analyze → Evolve Pipeline |

**Befund:** Wird nicht in `app/gateway/main.py` oder einem aktiven Router eingebunden. Isoliertes Experimental-Modul. Kein Produktionseinsatz nachweisbar.

**Empfehlung:** In `app/experimental/soul/` verschieben oder mit Kommentar als nicht-produktionsreif markieren.

### 3.3 `app/memory_platform/` — Monkey-Patch-Bridge

**Befund:** `app/memory_platform/integration/orchestrator_patch.py` patcht `MasterAgentV2` zur Laufzeit, um Legacy-Handler durch Memory-Platform-Calls zu ersetzen. Dies ist eine technische Schuld: die Patch-Architektur umgeht saubere Dependency-Injection und macht das Systemverhalten schwer nachvollziehbar.

**Empfehlung:** Memory-Platform-Calls direkt in `orchestrator_v2.py` integrieren; Monkey-Patch-Bridge entfernen.

### 3.4 `app/agent/` — Zweite Agenten-Laufzeit

**Befund:** `app/agent/runtime/` und `app/agent/specialists/` existieren parallel zu `app/swarm/agents/`. `orchestrator_v2.py` importiert aus `app.agent.runtime.handoff`, aber die Spezialistenprofile in `app/agent/specialists/profiles.py` stehen in unklarem Verhältnis zu den Swarm-Agents in `app/swarm/agents/`.

**Empfehlung:** Architekturentscheidung treffen: entweder `app/agent/` vollständig in `app/swarm/` aufgehen lassen oder als klare separate Schicht dokumentieren.

---

## 4. Alembic-Ketten-Problem (KRITISCH)

### 4.1 Symptom

`alembic heads` schlägt fehl mit:

```
UserWarning: Revision 2026_03_03_merge_all_heads referenced from
2026_03_03_merge_all_heads -> 2026_03_05_media_image (head)
is not present
```

`alembic upgrade head` ist damit **nicht ausführbar**.

### 4.2 Ursache

`2026_03_05_media_and_image_providers.py` hat:
```python
down_revision = "2026_03_03_merge_all_heads"
```

Aber die tatsächliche Revision-ID in `2026_03_03_merge_all_heads.py` lautet:
```python
revision: str = "merge_all_heads_001"
```

Der String `"2026_03_03_merge_all_heads"` entspricht dem **Dateinamen**, nicht der **Revision-ID**. Alembic verwendet ausschließlich `revision`-Strings, nicht Dateinamen.

### 4.3 Fix

In `/opt/ariia/production/alembic/versions/2026_03_05_media_and_image_providers.py` ändern:

```python
# VORHER (falsch):
down_revision = "2026_03_03_merge_all_heads"

# NACHHER (korrekt):
down_revision = "merge_all_heads_001"
```

### 4.4 Weitere Loose-End-Revisionen

Mehrere Migrationen haben `down_revision = None` und hängen damit als separate Roots in der Kette. Die folgende Tabelle zeigt Migrationen ohne Anker, die **nicht** in `merge_all_heads_001` zusammengeführt wurden:

| Datei | Revision | down_revision |
|-------|----------|---------------|
| `2026_03_02_ai_config_management.py` | `ai_config_001` | `None` |
| `2026_03_03_billing_v2_refactoring.py` | `billing_v2_001` | `None` |
| `2026_03_03_auth_refactoring.py` | `auth_refactoring_001` | `merge_all_heads_001` |

`billing_v2_001` erscheint im `down_revision`-Tuple von `merge_all_heads_001`, hat aber selbst `down_revision = None`. Das ist korrekt für einen Branch-Root. `ai_config_001` fehlt im Merge-Tuple.

**Empfehlung:** Nach dem Fix von `2026_03_05_media_and_image_providers.py` mit `alembic heads` prüfen, ob weitere offene Heads existieren, und ggf. eine neue Merge-Migration erstellen.

---

## 5. Leermodule / Stub-Module

| Modul | Datei | Status |
|-------|-------|--------|
| `app/voice/` | `stt.py`, `tts.py`, `pipeline.py` | Stubs — funktional, aber ohne echte Inferenz (kein `VOICE_ENABLE=1`-Flag) |
| `app/vision/` | `processor.py`, `rtsp.py` | Stubs — YOLO nur mit `VISION_ENABLE_YOLO=1` |
| `app/tools/` | Verzeichnis leer (nur `__init__.py`) | Keine `BaseTool`-Implementierungen; laut CODING_STANDARDS vorgesehen |

---

## 6. Priorisierter Cleanup-Plan

### Priorität 1 — Sofort (blockiert Deployments)

- [ ] **Fix Alembic-Chain**: `2026_03_05_media_and_image_providers.py` — `down_revision` von `"2026_03_03_merge_all_heads"` auf `"merge_all_heads_001"` korrigieren
- [ ] **Verifikation**: `alembic heads` auf genau einen Head prüfen

### Priorität 2 — Kurzfristig (technische Schuld, Wartbarkeit)

- [ ] `app/memory/librarian.py` entfernen; `maintenance.py` auf `librarian_v2` migrieren
- [ ] `app/swarm/master/orchestrator.py` (v1) entfernen; `orchestrator_v2.py` umbenennen
- [ ] ACP-Router (`app/acp/`) hinter `ACP_ENABLE`-Feature-Flag kapseln

### Priorität 3 — Mittelfristig (Architektur)

- [ ] Monkey-Patch in `app/memory_platform/integration/orchestrator_patch.py` auflösen — Memory-Platform direkt in Orchestrator integrieren
- [ ] `app/agent/` vs. `app/swarm/agents/` klären und konsolidieren
- [ ] `app/soul/` in `app/experimental/` verschieben oder deaktivieren

### Priorität 4 — Langfristig (Feature-Vervollständigung)

- [ ] `app/tools/` mit `BaseTool`-Implementierungen befüllen (laut CODING_STANDARDS-Anforderung)
- [ ] Voice-Pipeline (`app/voice/`) mit echtem STT/TTS-Provider aktivierbar machen

---

## 7. Metriken

| Kategorie | Anzahl |
|-----------|--------|
| Alembic-Revisionen gesamt | 27 |
| Revisionen mit `down_revision = None` (Roots) | 7 |
| Kritische Kettenbrüche | 1 (media_image → merge ID falsch) |
| Doppelte v1/v2-Module | 2 Paare |
| Experimentelle Module ohne Produktionsanbindung | 2 (`soul/`, `acp/` partially) |
| Stub-Module (Feature-Flag-abhängig) | 2 (`voice/`, `vision/`) |
