# Tasks: Codebase-Analyse – Verbleibende 10%

**Stand:** 2026-03-05
**Kontext:** Die initiale Analyse (90%) wurde abgeschlossen und in CLAUDE.md dokumentiert. Diese Tasks schließen die verbleibenden Lücken. Jeder Task endet mit einem konkreten CLAUDE.md-Commit.

**Legende:** `[ ]` offen · `[~]` in Arbeit · `[x]` abgeschlossen

---

## Phase 1: Schema & Migrations

### ANALYSIS-001 – Alembic-Migrationshistorie lesen
- **Dateien:** `alembic/versions/*.py` (alle ~20 Dateien), `alembic/env.py`
- **Leitfragen:**
  - Welche Tabellen wurden nach dem Initial-Schema strukturell geändert?
  - Gibt es `downgrade()`-Implementierungen oder nur `pass`?
  - Gibt es `merge`-Migrationen (mehrere Heads)? → `2026_03_03_merge_all_heads.py` ansehen
  - Sind alle Alembic-Heads konsistent (`alembic heads` ausführen)?
- **Akzeptanzkriterium:** CLAUDE.md enthält eine Tabelle der kritischen Migrationsschritte und bekannten Tech-Debt.

### ANALYSIS-002 – `run_migrations()` in `app/core/db.py` vollständig lesen
- **Datei:** `app/core/db.py` (vollständig, aktuell nur erste 60 Zeilen bekannt)
- **Leitfragen:**
  - Welche Inline-Migrationen laufen bei jedem App-Start?
  - Sind sie idempotent (sicher für mehrere Restarts)?
  - Gibt es Konflikte mit Alembic-Migrationen?
- **Akzeptanzkriterium:** Inline-Migrationen in CLAUDE.md `### Database` ergänzt.

---

## Phase 2: Test-Suite-Abdeckung

### ANALYSIS-003 – Test-Abdeckung kartieren
- **Dateien:** Alle `tests/test_*.py` (Dateinamen lesen, nicht unbedingt Inhalt)
- **Leitfragen:**
  - Welche App-Module haben keinen Test (Vergleich `app/` vs `tests/`)?
  - Welche Tests sind als `skip` oder `xfail` markiert?
  - Werden Stripe-Webhooks getestet? (`tests/test_billing_webhook.py`)
  - Werden Tenant-Isolation-Grenzfälle getestet? (`tests/test_multitenant_isolation.py`)
- **Akzeptanzkriterium:** CLAUDE.md neuer Abschnitt `## Testing` mit Coverage-Map.

### ANALYSIS-004 – Eval-Tests und Load-Tests verstehen
- **Dateien:** `tests/evals/test_faithfulness.py`, `tests/golden_dataset.json`, `tests/locustfile.py`, `tests/run_evals.py`
- **Leitfragen:**
  - Wie werden LLM-Antworten auf Faithfulness geprüft?
  - Was sind die Golden-Dataset-Szenarien?
  - Welche Endpoints werden mit Locust getestet, welche Lastprofile?
- **Akzeptanzkriterium:** Eval- und Load-Test-Abschnitt in CLAUDE.md.

### ANALYSIS-005 – CI-Konfiguration prüfen
- **Dateien:** `.github/workflows/ci.yml` ✅ (bekannt), `.github/workflows/frontend_quality.yml`, `.github/workflows/eval.yml`, `.github/workflows/deploy.yml`
- **Leitfragen:**
  - Was macht `eval.yml` — wann läuft es, was triggert es?
  - Gibt es parallelisierte Test-Jobs?
  - Werden Secrets korrekt gesetzt (kein Hardcode in CI)?
- **Akzeptanzkriterium:** CI-Abschnitt in CLAUDE.md mit allen 4 Workflows kurz erklärt.

---

## Phase 3: Security & Resilience

### ANALYSIS-006 – SecurityMiddleware analysieren
- **Datei:** `app/core/security.py`
- **Leitfragen:**
  - Auf welchen Pfaden greift Rate-Limiting?
  - Was sind die konkreten Limits (Requests/Minute per IP/Tenant)?
  - Gibt es Request-Size-Limits?
  - Welche Pfade sind von Rate-Limiting ausgenommen?
- **Akzeptanzkriterium:** Rate-Limit-Tabelle in CLAUDE.md `### Security Details`.

### ANALYSIS-007 – Resilience & Circuit Breaker
- **Datei:** `app/core/resilience.py`
- **Leitfragen:**
  - Welche Integrations haben einen Circuit Breaker?
  - Threshold für Open/Half-Open/Closed?
  - Wird Redis für State genutzt (erwartet: `t{id}:circuit_breaker:{integration}`)?
- **Akzeptanzkriterium:** Circuit-Breaker-Abschnitt in CLAUDE.md.

### ANALYSIS-008 – Guardrails, MFA, Crypto
- **Dateien:** `app/core/guardrails.py`, `app/core/mfa.py`, `app/core/crypto.py`
- **Leitfragen:**
  - Was wird durch Guardrails geblockt (Regex? LLM-basiert? Blockliste)?
  - Welche TOTP-Bibliothek? Backup-Codes: wie viele, wie gespeichert?
  - Was verschlüsselt `crypto.py` — API-Keys? Alle Settings?
- **Akzeptanzkriterium:** Security-Details-Abschnitt in CLAUDE.md vollständig.

---

## Phase 4: Platform API & Admin

### ANALYSIS-009 – Admin-Router vollständig lesen
- **Datei:** `app/gateway/admin.py`
- **Leitfragen:**
  - Vollständige Endpunkt-Liste mit HTTP-Methode und Pfad?
  - Welche Endpunkte sind `system_admin`-only, welche `tenant_admin`?
  - Gibt es Endpunkte, die noch nicht in der Frontend-RBAC-Matrix stehen?
- **Akzeptanzkriterium:** Vollständige Admin-API-Tabelle in CLAUDE.md oder `docs/api/ADMIN_API.md`.

### ANALYSIS-010 – Platform APIs (Public API, Tenant Portal, Marketplace)
- **Dateien:** `app/platform/api/public_api.py`, `app/platform/api/tenant_portal.py`, `app/platform/api/marketplace.py`, `app/platform/api/analytics.py`
- **Leitfragen:**
  - Welche Endpunkte sind öffentlich (ohne Auth)?
  - Was kann ein Tenant selbst im Portal verwalten?
  - Wie funktioniert der Marketplace (manuelle Freischaltung? Automatisch?)
- **Akzeptanzkriterium:** Platform-API-Abschnitt in CLAUDE.md ergänzt.

### ANALYSIS-011 – Ghost Mode v2
- **Datei:** `app/platform/ghost_mode_v2.py`
- **Leitfragen:**
  - Wie unterscheidet sich v2 von v1 (WebSocket `/ws/control`)?
  - Wie wird Human-Handoff ausgelöst und beendet?
  - Welcher Redis-Key tracked den manuellen Modus?
- **Akzeptanzkriterium:** Ghost-Mode-Abschnitt in CLAUDE.md aktualisiert.

### ANALYSIS-012 – Team-Personas auswerten
- **Dateien:** `.antigravity/team/FRONTEND.md`, `DEVOPS.md`, `QA.md`, `SEC.md`, `PO.md`, `UX.md`, `DOCS.md`
- **Leitfragen:**
  - Welche Konventionen definiert das Frontend-Team (Komponentenstil, State-Management)?
  - Welche Deployment-Konventionen definiert DevOps?
  - Welche Security-Standards definiert SEC?
- **Akzeptanzkriterium:** `## Team-Konventionen`-Abschnitt in CLAUDE.md oder `.antigravity/SUMMARY.md`.

---

## Phase 5: Business Logic

### ANALYSIS-013 – Contacts: Duplikat-Erkennung & Merge
- **Dateien:** `app/contacts/conflict_resolver.py`, `app/contacts/service.py`
- **Leitfragen:**
  - Welche Felder werden für Duplikat-Matching verwendet (Email? Telefon? Name-Fuzzy)?
  - Ist der Algorithmus exakt oder Fuzzy-Match?
  - Was ist die Merge-Strategie: Primary gewinnt, oder Feld-für-Feld wählbar?
- **Akzeptanzkriterium:** Duplikat-Erkennung-Abschnitt im Contacts-Teil von CLAUDE.md.

### ANALYSIS-014 – Contacts Repository & Sync-Core
- **Dateien:** `app/contacts/repository.py`, `app/contacts/sync_core.py`, `app/contacts/sync_health.py`
- **Leitfragen:**
  - Wie unterscheidet sich der Query-Layer vom Service-Layer (Trennung sauber)?
  - Wie funktioniert Sync-Health-Check (was wird gemessen)?
  - Gibt es Retry-Logik im Sync-Core?
- **Akzeptanzkriterium:** Contacts-Architektur-Abschnitt in CLAUDE.md.

### ANALYSIS-015 – Billing v1 vs. v2 Gating
- **Dateien:** `app/billing/gating_service.py`, `app/billing/metering_service.py`, `app/billing/subscription_service.py`
- **Leitfragen:**
  - Was kann `gating_service.py` (v2), was `feature_gates.py` (v1) nicht kann?
  - Koexistieren beide oder ist v2 der Nachfolger?
  - Wie wird Subscription-Downgrade gehandhabt (was passiert mit Daten über Limit)?
  - Wie funktioniert Metering genau (Batch? Live? Redis-Counter)?
- **Akzeptanzkriterium:** Billing-Abschnitt in CLAUDE.md: v1 vs. v2 klar getrennt, Downgrade-Verhalten dokumentiert.

---

## Bonus (falls Zeit): Randmodule

### ANALYSIS-016 – Memory Tier-System vollständig
- **Dateien:** `app/memory/context.py`, `app/memory/librarian_v2.py`, `app/memory/graph.py`
- **Ziel:** 3-Tier-Speicher (RAM → SQLite/PG → GraphRAG) vollständig verstehen

### ANALYSIS-017 – `app/acp/refactor.py` und `rollback.py`
- **Ziel:** ACP-Internals vollständig (aktuell nur `server.py` und `sandbox.py` bekannt)

### ANALYSIS-018 – AI Config Observability
- **Datei:** `app/ai_config/observability.py`
- **Ziel:** Was wird in Langfuse geloggt? Welche Metriken werden exposed?

---

## Fortschritt

| Phase | Tasks | Offen | In Arbeit | Abgeschlossen |
|-------|-------|-------|-----------|---------------|
| 1 – Schema | 2 | 2 | 0 | 0 |
| 2 – Tests | 3 | 3 | 0 | 0 |
| 3 – Security | 3 | 3 | 0 | 0 |
| 4 – Platform | 4 | 4 | 0 | 0 |
| 5 – Business | 3 | 3 | 0 | 0 |
| Bonus | 3 | 3 | 0 | 0 |
| **Gesamt** | **18** | **18** | **0** | **0** |
