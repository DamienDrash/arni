# ARNI v1.4 🤖

> **Living System Agent für GetImpulse Berlin** – KI-gestützter Fitnessstudio-Assistent mit WhatsApp, Voice, Vision & Swarm Intelligence.

---

## Quick Start

```bash
# 1. Environment vorbereiten
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Redis starten
redis-server --daemonize yes

# 3. Gateway starten
uvicorn app.gateway.main:app --host 0.0.0.0 --port 8000

# 4. Health Check
curl http://185.209.228.251:8000/health
```

## Docker (Empfohlen)

```bash
docker compose up --build
```

## Projektstruktur

```
arni/
├── app/
│   ├── gateway/          # Hybrid Gateway (FastAPI + Redis + WebSocket)
│   │   ├── main.py       # Endpoints: /health, /webhook, /ws/control
│   │   ├── redis_bus.py   # Async Redis Pub/Sub Connector
│   │   └── schemas.py     # Pydantic Message Models
│   ├── swarm/             # Agent Swarm (Sprint 2)
│   ├── integrations/      # WhatsApp, Telegram, PII (Sprint 3)
│   ├── memory/            # 3-Tier Memory System (Sprint 4)
│   ├── vision/            # YOLOv8 + Privacy Engine (Sprint 5a)
│   ├── voice/             # Whisper STT + ElevenLabs TTS (Sprint 5b)
│   ├── acp/               # ACP Pipeline (Sprint 6a)
│   ├── soul/              # Soul Evolution (Sprint 6b)
│   ├── core/              # Metrics & Config (Sprint 7b)
│   ├── tools/             # MCP Tools
│   ├── voice/             # STT/TTS Pipeline (Sprint 5b)
│   ├── vision/            # RTSP + YOLOv8 (Sprint 5a)
│   └── integrations/      # Magicline, WhatsApp, Telegram
├── config/
│   └── settings.py        # Pydantic Settings
├── tests/                 # Pytest Suite (246 Tests)
├── docs/
│   ├── specs/             # Architektur, DSGVO, Coding Standards
│   ├── sprints/           # Roadmap + Sprint-Pläne
│   └── audits/            # Security Audit Reports
├── docker-compose.yml     # Gateway + Redis Services
├── Dockerfile             # Multi-stage, non-root
└── pyproject.toml         # Python 3.12, alle Dependencies
```

## Tests

```bash
# Alle Tests
pytest tests/ -v

# Mit Coverage
pytest tests/ --cov=app --cov-report=term-missing

# Aktuell: 262 passed ✅, Coverage ~87%
```

## API Endpoints

| Method | Path | Beschreibung |
|--------|------|-------------|
| `GET` | `/health` | System-Status + Redis-Verbindung |
| `GET` | `/webhook/whatsapp` | Meta Webhook Verification |
| `POST` | `/webhook/whatsapp` | WhatsApp Message Ingress |
| `POST` | `/swarm/route` | Intent Classification → Agent Response |
| `WS` | `/ws/control` | Admin Dashboard (Ghost Mode) |

## Swarm Intelligence (Sprint 2)

```
User Message → Router (GPT-4o-mini) → Intent Classification
                    ↓
    ┌───────────────┼───────────────┐
    │               │               │
  Agent Ops    Agent Sales    Agent Medic    ...
  (Booking)    (Retention)   (Health+⚕️)

Fallback: Keyword-basiert wenn LLM nicht verfügbar
Fallback: Ollama/Llama-3 wenn OpenAI offline
```

| Agent | Intent | Besonderheit |
|-------|--------|-------------|
| **Ops** | `booking` | Magicline API Stub, One-Way-Door |
| **Sales** | `sales` | Retention-First, 3 Alternativen |
| **Medic** | `health` | ⚕️ Disclaimer IMMER, Notfall → 112 |
| **Vision** | `crowd` | Stub (Sprint 5: YOLOv8) |
| **Persona** | `smalltalk` | Arni-Persönlichkeit (SOUL.md) |

## Communication Layer (Sprint 3)

```
WhatsApp (Meta Cloud API) ──→ Normalizer ──→ InboundMessage ──→ Redis Bus
Telegram (Bot API)         ──→ Normalizer ──→ InboundMessage ──→ Redis Bus
                                                                    ↓
WhatsApp ←── Dispatcher ←── OutboundMessage ←── Swarm Router
Telegram ←── Dispatcher ←── OutboundMessage ←── Swarm Router
Dashboard←── Dispatcher ←── OutboundMessage ←── Swarm Router
```

| Modul | Funktion |
|-------|----------|
| `whatsapp.py` | Meta Cloud API Client, HMAC-SHA256 Webhook Verifizierung |
| `telegram.py` | Admin Bot (/status, /ghost, /help), Emergency Alerts |
| `normalizer.py` | Multi-Platform → einheitliches InboundMessage Schema |
| `dispatcher.py` | OutboundMessage → richtigen Kanal (WA/TG/Dashboard) |
| `pii_filter.py` | PII-Erkennung + Maskierung (DSGVO-konform) |
| `wa_flows.py` | WhatsApp Interactive Buttons/Lists (Stub) |

## Memory & Knowledge (Sprint 4)

```
                    ┌─── RAM Context (20 Turns, 30 Min TTL)
                    │
User Message ──→ Consent Check (Art. 6)
                    │
                    ├─── SQLite Sessions DB (90 Tage)
                    │
                [Context > 80%?]
                    │ ja
                Silent Flush → Fact Extraction → Knowledge Files
                    │                              ↓
                Context Kompaktiert         GraphRAG (NetworkX)
```

| Modul | Funktion |
|-------|----------|
| `context.py` | RAM Short-Term Context (20 Turns, TTL, Auto-Flush Trigger) |
| `database.py` | Async SQLite (WAL, CASCADE DELETE, 90-Tage Cleanup) |
| `repository.py` | Session + Message CRUD (Repository Pattern) |
| `knowledge.py` | Per-Member Markdown Knowledge Files |
| `flush.py` | Silent Flush: Fact Extraction + Context Compaction |
| `graph.py` | NetworkX GraphRAG Stub (Full Neo4j in Sprint 6) |
| `consent.py` | GDPR Art. 6 + Art. 17 Cascade Delete |

## Physical Intelligence (Sprint 5)

### Vision (Sprint 5a)
```
RTSP Camera ──→ Connector ──→ Processor (YOLOv8) ──→ Privacy Engine
                                      ↓                    ↓
                                 {count, density}     Frame gelöscht (0s)
```

| Modul | Funktion |
|-------|----------|
| `processor.py` | YOLOv8 Person Detection (Auto-Stub wenn keine GPU) |
| `rtsp.py` | Snapshot Grabber (Auto-Reconnect) |
| `privacy.py` | 0s Retention Enforcer (RAM-only, Audit Trail) |

### Voice (Sprint 5b)
```
Audio In ──→ Ingress (FFmpeg) ──→ STT (Whisper) ──→ Swarm ──→ TTS (ElevenLabs) ──→ Audio Out
```

| Modul | Funktion |
|-------|----------|
| `stt.py` | Whisper Speech-to-Text (Auto-Stub wenn keine Lib) |
| `tts.py` | ElevenLabs Turbo v2.5 (Auto-Stub wenn kein API Key) |
| `pipeline.py` | E2E Orchestrator (<8s Latenz-Target) |

## Self-Improvement (Sprint 6)

### ACP Pipeline (6a)
- **Soft Sandbox:** Python-based Isolation (`app/acp/sandbox.py`)
- **Rollback:** Git-based Checkpoints (`app/acp/rollback.py`)
- **Refactoring:** AST Analysis (`app/acp/refactor.py`)

### Soul Evolution (6b)
- **Analyzer:** LLM Topic Extraction from logs
- **Evolver:** Auto-Update for `docs/personas/SOUL.md`
- **Flow:** Continuous Persona Improvement Loop

## Hardening & Launch (Sprint 7)

### Security (7a)
- **Audit:** Automated `pip-audit` + `bandit` checks (`scripts/audit.sh`).
- **Load Test:** Locust scenario verified 100 concurrent users with <100ms latency.

### Operations (7b)
- **Metrics:** Prometheus endpoint at `/metrics`.
- **Runbook:** Operational guides in `docs/ops/RUNBOOK.md`.
- **Launch:** Production startup via `scripts/launch.sh`.

## Architektur

```
WhatsApp/Telegram ──→ Gateway ──→ Redis Bus ──→ Swarm Router ──→ Agents
                         ↑              ↓
                    WebSocket      Events Channel
                    (Admin)        (Alerts, Logs)
```

## Regeln

- **BMAD-Zyklus:** Benchmark → Modularize → Architect → Deploy
- **One-Way-Door:** Irreversible Aktionen → Menschliche Bestätigung
- **DSGVO:** 0s Retention für Kameradaten, PII-Masking in Logs
- **Sandboxing:** Docker, non-root, nur `./data/` writable

---

> Entwickelt mit ❤️ für GetImpulse Berlin | VPS: `185.209.228.251`
