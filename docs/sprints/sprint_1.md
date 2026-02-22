# Sprint 1 – Foundation: Hybrid Gateway & Redis Integration

> **Zeitraum:** Woche 1–2  |  **Phase:** 1 (Foundation)
> **Ziel:** Lauffähiges Gateway mit Redis Message Bus, bereit für Swarm-Anbindung in Sprint 2.

---

## Sprint Goal
Ein funktionsfähiger **Hybrid Gateway** (FastAPI), der über einen **Redis Pub/Sub Bus** Nachrichten empfängt und verteilt. Eingehende Webhooks (WhatsApp) und ein WebSocket-Kanal (Admin/Ghost Mode) sind operativ. Alle Komponenten sind getestet und containerisiert.

---

## Tasks

### 🏗️ Infrastruktur & Design

| # | Task | Agent | Beschreibung | Acceptance Criteria | Status |
|---|------|-------|-------------|---------------------|--------|
| 1.1 | Gateway Skeleton | **@ARCH** | FastAPI-App erstellen mit `app/gateway/main.py`, Health-Endpoint `GET /health` | `curl /health` → `{"status": "ok"}` | ✅ |
| 1.2 | Projektstruktur finalisieren | **@ARCH** | `pyproject.toml`, Dependencies (FastAPI, Redis, Pydantic, Uvicorn) | `pip install -e .` läuft fehlerfrei | ✅ |
| 1.3 | Config & Environment | **@ARCH** | Pydantic `Settings` Klasse in `config/settings.py`, `.env.example` mit allen Variablen | Settings laden ohne Fehler | ✅ |

### 💻 Gateway Implementation

| # | Task | Agent | Beschreibung | Acceptance Criteria | Status |
|---|------|-------|-------------|---------------------|--------|
| 1.4 | Redis Bus Connector | **@BACKEND** | `app/gateway/redis_bus.py` – Pub/Sub Klasse (publish, subscribe, health check) | Redis Ping → Pong, Message Roundtrip | ✅ |
| 1.5 | Webhook Ingress | **@BACKEND** | `POST /webhook/whatsapp` Endpoint – Validiert Payload, published auf Redis Channel `inbound` | Webhook → Redis Message sichtbar | ✅ |
| 1.6 | WebSocket Control | **@BACKEND** | `/ws/control` Endpoint – Bidirektionaler Kanal für Admin Dashboard & Ghost Mode | WS Connect + Echo-Test bestanden | ✅ |
| 1.7 | Message Schema | **@BACKEND** | Pydantic Models für `InboundMessage`, `OutboundMessage`, `SystemEvent` in `app/gateway/schemas.py` | Validation mit Test-Payloads | ✅ |

### 🕵️ Testing & Qualität

| # | Task | Agent | Beschreibung | Acceptance Criteria | Status |
|---|------|-------|-------------|---------------------|--------|
| 1.8 | Unit Tests Gateway | **@QA** | `tests/test_gateway.py` – Health, Webhook, WS Tests mit fakeredis Mock | `pytest` → 100% Pass | ✅ |
| 1.9 | Unit Tests Redis | **@QA** | `tests/test_redis_bus.py` – Pub/Sub Roundtrip, Error Handling | `pytest` → 100% Pass | ✅ |
| 1.10 | Integration Test | **@QA** | `tests/test_integration.py` – Webhook → Redis → WS Pipeline E2E | Full Pipeline Test Pass | ✅ |

### ⚙️ Infrastructure (@DEVOPS)

| # | Task | Agent | Beschreibung | Acceptance Criteria | Status |
|---|------|-------|-------------|---------------------|--------|
| 1.11 | Docker Compose Setup | **@DEVOPS** | `docker-compose.yml` mit Gateway + Redis Services, Health Checks | `docker compose up` startet beide Services | ✅ |
| 1.12 | Dockerfile Gateway | **@DEVOPS** | Multi-stage Dockerfile für FastAPI App (non-root User) | Image baut in <60s, läuft als non-root | ✅ |
| 1.13 | Redis Persistence | **@DEVOPS** | AOF + RDB Snapshot Konfiguration | Redis-Restart ohne Datenverlust | ✅ |

### 🛡️ Security & Privacy (@SEC)

| # | Task | Agent | Beschreibung | Acceptance Criteria | Status |
|---|------|-------|-------------|---------------------|--------|
| 1.14 | DSGVO-Baseline | **@SEC** | Consent-Schema validieren, PII-Masking Policy dokumentieren | Policy-Dokument erstellt | ✅ |
| 1.15 | Logging Audit | **@SEC** | Sicherstellen, dass Gateway-Logs keine PII enthalten | Grep auf Logs: 0 PII Findings | ✅ |

### 🎭 User Experience (@UX)

| # | Task | Agent | Beschreibung | Acceptance Criteria | Status |
|---|------|-------|-------------|---------------------|--------|
| 1.16 | Persona Audit | **@UX** | SOUL.md Review, Greeting/Error-Varianten definieren | ≥5 Greeting + ≥3 Error-Varianten | ✅ |
| 1.17 | Ghost Mode UX Flow | **@UX** | Conversation Wireframe für Admin Ghost Mode | Flow-Diagram erstellt | ✅ |

### 📝 Dokumentation

| # | Task | Agent | Beschreibung | Acceptance Criteria | Status |
|---|------|-------|-------------|---------------------|--------|
| 1.18 | README.md | **@DOCS** | Projekt-Setup (Install, Run, Test), Architektur-Überblick | Neuer Dev kann in <10min starten | ✅ |
| 1.19 | API Docs | **@DOCS** | OpenAPI/Swagger Doku für Gateway Endpoints | `/docs` zeigt alle Endpoints | ✅ |

---

## Definition of Done
- [x] Ordnerhierarchie erstellt
- [x] FastAPI Gateway startet (`uvicorn app.gateway.main:app`)
- [x] Redis Bus connected und Pub/Sub funktional
- [x] Webhook + WebSocket Endpoints aktiv
- [x] Docker Compose startet alle Services (`@DEVOPS`)
- [x] DSGVO-Baseline dokumentiert (`@SEC`)
- [x] Persona-Varianten definiert (`@UX`)
- [x] Alle Tests grün (`pytest --tb=short`)
- [x] `.env.example` dokumentiert alle Variablen
- [x] README enthält Setup-Anleitung

---

## Risiken & Mitigation
| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Redis nicht verfügbar auf VPS | Mittel | Docker Compose mit Redis-Service, Fallback auf in-memory Queue |
| Meta API Webhook-Validierung komplex | Niedrig | Mock-Server für Dev, Prod-Validierung erst in Sprint 3 |

---

## Abhängigkeiten
- **Benötigt:** Python 3.12, Redis Server (lokal oder Docker)
- **Blockiert:** Sprint 2 (Swarm) benötigt funktionalen Redis Bus aus Sprint 1
