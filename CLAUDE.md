# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Last updated: 2026-02-28 (ground-up codebase analysis).

---

## What This Project Is

**ARNI** is a multi-tenant SaaS AI agent platform for fitness studios. Members interact via WhatsApp, Telegram, SMS, Email, and Voice. Studio admins manage everything through a Next.js dashboard. Each tenant is fully isolated: own subscription plan, Jinja2 prompt templates, knowledge base, branding, and Magicline API credentials.

Core engine: swarm-based agent routing (GPT-4o-mini intent classification → 5 specialized agents). Deterministic guardrails run before every LLM call. A "Soul" subsystem enables self-improving prompt evolution. An ACP bridge enables sandboxed self-refactoring from an IDE.

**Deployment target:** VPS at `185.209.228.251` | Gateway port 8000 | Frontend port 3000

---

## Commands

### Backend (Python/FastAPI)

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run (manual)
redis-server --daemonize yes
uvicorn app.gateway.main:app --host 0.0.0.0 --port 8000

# Run (Docker – preferred, starts all 6 services)
docker compose up --build

# Tests
pytest tests/ -v
pytest tests/test_auth.py -v             # single file
pytest tests/ -k "test_name" -v          # single test
pytest tests/ --cov=app --cov-report=term-missing  # with coverage
# Current status: 262 passed, ~87% coverage

# Lint / Type-check
ruff check .
mypy .
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev                   # dev server on :3000
npm run qa:gate               # full quality gate: lint + typecheck + build
npm run lint:strict           # ESLint, zero warnings allowed
npm run typecheck             # tsc --noEmit
npm run test:rbac             # RBAC contract tests
npm run build                 # production build
```

CI (`.github/workflows/frontend_quality.yml`) runs `lint:strict`, `typecheck`, `test:rbac`, `build` on every PR touching `frontend/`.

---

## Architecture

### Request Flow

```
Platform (WA/TG/SMS/Email/Voice)
  → Webhook Endpoint (FastAPI app/gateway/main.py)
  → InboundMessage normalization (app/integrations/normalizer.py)
  → GuardrailsService.check()  ← deterministic safety, runs BEFORE any LLM call
  → Phone-based MFA gate (Redis)
  → Member matching (app/gateway/member_matching.py)
  → SwarmRouter (GPT-4o-mini intent classification)
  → Agent (Ops / Sales / Medic / Vision / Persona)
  → Platform Dispatcher → reply sent
```

### SwarmRouter Logic (Priority Order)

1. **Emergency hard-route** — keywords like `notfall`, `herzinfarkt`, `unfall`, `112` → Medic directly (bypasses LLM)
2. **Booking action keywords** — delete/cancel/reschedule → Ops
3. **Dialog context override** — check `pending_action` flag from Redis
4. **LLM classification** — GPT-4o-mini (Ollama/Llama-3 fallback if OpenAI offline)
5. **Confidence threshold** — if <0.6, fall back to keyword matching
6. **Final fallback** → Persona (smalltalk)

### Intent → Agent Mapping

| Intent | Agent | Purpose |
|--------|-------|---------|
| `booking` | `AgentOps` | Schedule, book, cancel, reschedule (Magicline tools) |
| `sales` | `AgentSales` | Contract, cancellation, retention |
| `health` | `AgentMedic` | Fitness advice, injuries — ALWAYS appends `medic_disclaimer_text`, fallback to 112 |
| `crowd` | `AgentVision` | Occupancy detection (YOLOv8, stub by default) |
| `smalltalk` | `AgentPersona` | Chitchat, greetings, general Q&A (knowledge base + handoff) |
| `unknown` | `AgentPersona` | Final fallback |

### Infrastructure (Docker Compose — 6 Services)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `arni-frontend` | `node:20-slim` | 3000 | Next.js admin dashboard |
| `arni-core` | Custom (Dockerfile) | 8000 | FastAPI backend |
| `arni-telegram` | Custom (Dockerfile) | — | Telegram polling worker (separate process) |
| `redis` | `redis:alpine` | 6379 | Pub/sub, session cache, MFA codes |
| `qdrant` | `qdrant/qdrant:latest` | 6333 | Vector DB (RAG / knowledge base) |
| `postgres` | `postgres:16-alpine` | 5432 | Primary relational DB (multi-tenant prod) |

Source code is hot-mounted into `arni-core` (`./app`, `./config`, `./scripts`).

---

## Backend Module Map

### app/core/ — Core Infrastructure

| Module | Purpose | Key API |
|--------|---------|---------|
| `auth.py` | HMAC-SHA256 tokens, RBAC | `create_access_token()`, `decode_access_token()`, `hash_password()`, `get_current_user()`, `require_role()`, `AuthContext` dataclass |
| `db.py` | SQLAlchemy engine, session factory, migrations | `Base`, `SessionLocal`, `engine`, `run_migrations()` |
| `models.py` | All ORM models | See **Database Models** section |
| `feature_gates.py` | Plan-based limits (HTTP 402/429) | `FeatureGate.require_channel()`, `require_feature()`, `check_message_limit()` |
| `guardrails.py` | Deterministic safety layer ("Iron Dome") | `GuardrailsService.check()` — phrase/pattern/PII blocking via `config/guardrails.yaml` |
| `instrumentation.py` | Prometheus metrics | `http_requests_total`, `http_request_duration_seconds` — exposed at `GET /metrics` |
| `observability.py` | LangFuse tracing | Graceful fallback if `LANGFUSE_*` env vars not set |
| `prompt_builder.py` | Tenant-aware Jinja2 prompt hydration | `get_prompt()` — fills `{placeholders}` from Settings table at call time |
| `redis_keys.py` | Tenant-scoped Redis key factory | `redis_key()`, `token_key()`, `user_token_key()`, `dialog_context_key()`, `human_mode_key()` |
| `knowledge/retriever.py` | Hybrid vector search | `HybridRetriever(collection_name)` — ChromaDB + BM25 |

### app/gateway/ — Webhook Ingress & REST API

| Module | Purpose |
|--------|---------|
| `main.py` | FastAPI app: all webhook routes, WebSocket Ghost Mode, health, metrics |
| `admin.py` | REST admin API (members, settings, knowledge, audit, member memory) — mounted at `/admin/*` |
| `auth.py` | Auth initialization + tenant bootstrap (`ensure_default_tenant_and_admin()`) |
| `schemas.py` | Pydantic models: `InboundMessage`, `OutboundMessage`, `Platform` enum, `WebhookPayload` |
| `redis_bus.py` | Async Redis pub/sub: channels `arni:inbound`, `arni:outbound`, `arni:events` |
| `persistence.py` | `persistence` singleton wrapping `SessionLocal`; `get_setting()`, `upsert_setting()`, `init_default_settings()` |
| `persistence_helpers.py` | Additional DB query helpers |
| `member_matching.py` | Phone number → `StudioMember` lookup |
| `routers/billing.py` | Stripe billing routes |

**All Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | System status + Redis connection |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/webhook/whatsapp` | Meta webhook verification (default tenant) |
| `GET` | `/webhook/whatsapp/{tenant_slug}` | Meta webhook verification (per-tenant) |
| `POST` | `/webhook/whatsapp` | WhatsApp message ingress (default tenant) |
| `POST` | `/webhook/whatsapp/{tenant_slug}` | WhatsApp message ingress (per-tenant) |
| `POST` | `/webhook/telegram` | Telegram ingress (default tenant) |
| `POST` | `/webhook/telegram/{tenant_slug}` | Telegram ingress (per-tenant) |
| `POST` | `/webhook/sms/{tenant_slug}` | SMS ingress (Twilio) |
| `POST` | `/webhook/email/{tenant_slug}` | Email ingress |
| `POST` | `/voice/incoming/{tenant_slug}` | Voice call ingress |
| `WS` | `/voice/stream/{tenant_slug}` | Live voice streaming |
| `WS` | `/ws/control` | Ghost Mode (admin live monitoring/injection) |
| `POST` | `/swarm/route` | Direct routing endpoint (internal) |
| `WS` | `/acp/ws` | ACP IDE bridge (self-refactoring) |
| `GET/POST` | `/admin/*` | Admin REST API (RBAC-enforced) |

### app/swarm/ — Agent Swarm

```
app/swarm/
├── base.py                     # BaseAgent ABC (shared LLM integration)
├── llm.py                      # LLMClient: OpenAI primary, Ollama fallback
├── router/
│   ├── router.py               # SwarmRouter — intent classification + dispatch
│   └── intents.py              # Intent enum (BOOKING, SALES, HEALTH, CROWD, SMALLTALK, UNKNOWN)
├── agents/
│   ├── ops.py                  # AgentOps — scheduling, bookings, Magicline tools
│   ├── sales.py                # AgentSales — contracts, retention
│   ├── medic.py                # AgentMedic — health advice, emergency routing
│   ├── persona.py              # AgentPersona — smalltalk, knowledge base
│   └── vision.py               # AgentVision — crowd/occupancy (stub by default)
└── tools/
    ├── magicline.py            # Member-facing Magicline API wrappers
    └── knowledge_base.py       # RAG search tool (HybridRetriever)
```

### app/integrations/ — Platform Connectors

```
app/integrations/
├── dispatcher.py               # OutboundMessage → platform routing
├── normalizer.py               # Platform → InboundMessage normalization
├── pii_filter.py               # PII masking for logs (email, phone, IBAN)
├── whatsapp.py                 # WhatsApp Cloud API client (HMAC-SHA256 verification)
├── telegram.py                 # Telegram Bot API client + polling worker
├── email.py                    # SMTP mailer (SMTPMailer, verification emails)
├── wa_flows.py                 # WhatsApp interactive messages (buttons, lists)
├── magicline/
│   ├── client.py               # Resource-oriented Magicline API client (1 method = 1 API call)
│   ├── member_enrichment.py    # Check-in stats, booking history enrichment
│   ├── members_sync.py         # Bulk sync all studio members
│   └── scheduler.py            # Background enrichment scheduler
└── whatsapp_web/
    └── (Node.js Baileys bridge; auth artifacts in data/whatsapp/)
```

### app/memory/ — Conversation & Knowledge Storage

| Module | Class | Purpose |
|--------|-------|---------|
| `context.py` | `ConversationContext`, `Turn` | RAM context: 20-turn limit, 30-min TTL, auto-flush trigger at >80% |
| `database.py` | `MemoryDB` | SQLite session persistence (WAL, CASCADE DELETE, 90-day retention) |
| `repository.py` | `SessionRepository` | Abstract CRUD for sessions and messages |
| `knowledge.py` | — | Per-tenant `.md` knowledge file access |
| `graph.py` | `FactGraph` | NetworkX GraphRAG: member facts as nodes/edges (HAS_INJURY, TRAINS, PREFERS, etc.) |
| `consent.py` | `ConsentManager` | GDPR Art. 6 lawful processing check + Art. 17 cascade delete on revocation |
| `flush.py` | — | Silent flush: fact extraction + context compaction routines |
| `member_memory_analyzer.py` | `MemberMemoryAnalyzer` | LLM-based extraction of durable facts from chat history; cron-schedulable; output stored as Markdown in `data/knowledge/tenants/{slug}/members/` |

**Memory Flow:**
```
ConversationContext (RAM, 20 turns)
  → [at >80% capacity] → Silent Flush
      → MemberMemoryAnalyzer (LLM fact extraction)
      → knowledge files (Markdown)
      → FactGraph (NetworkX nodes/edges)
  → SQLite (90-day persistence)
```

### app/prompts/ — Prompt Templates

```
app/prompts/
├── context.py                  # Tenant context builder
├── engine.py                   # Jinja2 template renderer
└── templates/
    ├── medic/system.j2         # Health advice (legal disclaimer, emergency routing)
    ├── ops/system.j2           # Scheduling/booking (Magicline tool definitions)
    ├── persona/system.j2       # Smalltalk (knowledge base + handoff tools)
    ├── router/system.j2        # Intent classification (5 categories)
    └── sales/system.j2         # Retention (member status + check-in tools)
```

All templates use `{{ placeholder }}` syntax filled from the `Settings` table at runtime via `PromptBuilder`. Per-tenant overrides stored in `data/knowledge/tenants/{slug}/prompts/`.

**Settings keys used in templates** (seeded by `PROMPT_SETTINGS_KEYS` in `prompt_builder.py`):

| Key | Default | Used In |
|-----|---------|---------|
| `studio_name` | `Mein Studio` | All agents |
| `studio_short_name` | — | All agents |
| `agent_display_name` | `ARNI` | All agents (member-facing name) |
| `studio_locale` | `de-DE` | All agents |
| `studio_timezone` | `Europe/Berlin` | Ops |
| `studio_emergency_number` | `112` | Medic |
| `studio_address` | — | Ops, Persona |
| `sales_prices_text` | — | Sales |
| `sales_retention_rules` | — | Sales |
| `medic_disclaimer_text` | (legal text) | Medic — ALWAYS appended, never omit |
| `persona_bio_text` | — | Persona |
| `checkin_enabled` | `true` | Ops, Sales (falls back to booking stats if false or data absent) |

### app/soul/ — Self-Improvement Subsystem

| Module | Class | Purpose |
|--------|-------|---------|
| `analyzer.py` | `LogAnalyzer` | Analyzes recent chat logs for trending topics and sentiment patterns |
| `evolver.py` | `PromptEvolver` | Proposes prompt changes based on analyzer output |
| `flow.py` | `SoulFlow` | Orchestrates: analyze → propose → (human-gated) apply cycle |

### app/acp/ — IDE Bridge & Self-Refactoring

| Module | Purpose |
|--------|---------|
| `server.py` | WebSocket endpoint `/acp/ws` for IDE handshake |
| `sandbox.py` | Dockerized execution environment; file access restricted to `./workspace/` and `./data/` |
| `refactor.py` | Refactoring engine (runs inside sandbox, no root access) |
| `rollback.py` | Git-based rollback for any ACP-applied changes |

### app/knowledge/ — Knowledge Ingestion

| Module | Purpose |
|--------|---------|
| `ingest.py` | Scans `data/knowledge/*.md`, chunks on headers, upserts into ChromaDB per-tenant |
| `store.py` | ChromaDB wrapper |

### app/vision/ & app/voice/ — Physical Intelligence

**Vision** (`app/vision/`):
- `processor.py` — YOLOv8 person detection (auto-stubs when no GPU or `VISION_ENABLE_YOLO` not set)
- `privacy.py` — 0s retention enforcer: processes in RAM only, no disk write of camera frames
- `rtsp.py` — RTSP live stream snapshot grabber (auto-reconnect; set `RTSP_ENABLE_LIVE=1` to enable)

**Voice** (`app/voice/`):
- `stt.py` — Faster-Whisper speech-to-text (auto-stubs when library absent)
- `tts.py` — Kokoro-82M ONNX (multilingual) or Piper TTS (German); ElevenLabs optional fallback
- `pipeline.py` — Full voice I/O orchestration (<8s latency target)
- `ingress.py` — Voice call ingress (Twilio/etc.)
- `text_cleaner.py` — Transcription cleanup pre-LLM

---

## Database

### Models (`app/core/models.py`)

| Model | Key Columns | Purpose |
|-------|------------|---------|
| `Tenant` | id, slug (unique), name, is_active, created_at | Multi-tenant accounts |
| `UserAccount` | id, tenant_id (FK), email (unique), full_name, role, password_hash, is_active | Admin users (RBAC) |
| `ChatSession` | id, user_id, tenant_id (FK), platform, user_name, phone_number, email, member_id | Conversation sessions |
| `ChatMessage` | id, session_id, tenant_id (FK), role (user/assistant), content, timestamp, metadata_json | Message history |
| `Setting` | (tenant_id, key) composite PK, value, description, updated_at | Per-tenant + system-wide KV store |
| `AuditLog` | id, actor_user_id, actor_email, tenant_id (FK), action, category, target_type, target_id, details_json | Governance audit trail |
| `StudioMember` | id, tenant_id (FK), customer_id, member_number, first_name, last_name, phone_number, email, **gender**, **preferred_language**, **member_since**, **is_paused**, pause_info (JSON), additional_info (JSON), **checkin_stats** (JSON), **recent_bookings** (JSON dict), enriched_at | Member profile + Magicline cache |
| `Plan` | id, name, slug (unique), stripe_price_id, price_monthly_cents, max_members, max_monthly_messages, max_channels, whatsapp_enabled, telegram_enabled, sms_enabled, email_channel_enabled, voice_enabled, memory_analyzer_enabled, custom_prompts_enabled | SaaS plans (Starter/Pro/Enterprise) |
| `Subscription` | id, tenant_id (FK, unique), plan_id (FK), status, stripe_subscription_id, stripe_customer_id, current_period_start/end, trial_ends_at | Active plan per tenant |
| `UsageRecord` | id, tenant_id (FK), period_year, period_month, messages_inbound, messages_outbound, active_members, llm_tokens_used | Monthly usage for billing |

**Migrations:** Alembic in `alembic/versions/` + idempotent column-level backfills via `run_migrations()` in `app/core/db.py`.

### DB Stack

| DB | Use Case |
|----|---------|
| SQLite | Dev (single-tenant) |
| PostgreSQL 16 | Production (multi-tenant) |
| ChromaDB | Knowledge base per tenant |
| Qdrant | RAG vector search |
| Redis | Pub/sub, session cache, MFA codes, dialog context |

---

## Frontend

### Pages (`frontend/app/` — Next.js App Router)

| Route | Purpose | Access |
|-------|---------|--------|
| `login/` | Login | Public |
| `register/` | Tenant self-registration | Public |
| `/` (root) | Dashboard home | All roles |
| `analytics/` | Conversation analytics | tenant_admin+ |
| `audit/` | Audit log viewer | tenant_admin+ |
| `escalations/` | Escalation queue (human handoff) | tenant_admin+ |
| `knowledge/` | Knowledge base manager | tenant_admin+ |
| `live/` | Ghost Mode (WebSocket control panel) | tenant_admin+ |
| `magicline/` | Member sync & enrichment stats | tenant_admin+ |
| `member-memory/` | Member memory file viewer/editor | tenant_admin+ |
| `members/` | Studio member list (enrichment, language, check-in stats) | tenant_admin+ |
| `plans/` | Subscription plan management | system_admin |
| `system-prompt/` | Ops agent system-prompt editor | tenant_admin+ |
| `tenants/` | Multi-tenant management | system_admin |
| `users/` | Admin user management | tenant_admin+ |
| `settings/` | Settings hub | tenant_admin+ |
| `settings/account/` | Account settings | tenant_admin+ |
| `settings/automation/` | Automation rules | tenant_admin+ |
| `settings/billing/` | Stripe billing | tenant_admin+ |
| `settings/branding/` | White-label branding | tenant_admin+ |
| `settings/general/` | General settings | tenant_admin+ |
| `settings/integrations/` | Platform integrations | tenant_admin+ |
| `settings/prompts/` | Agent prompt configuration | tenant_admin+ |
| `api/auth/[...path]/` | Auth proxy (cookie handling) | — |
| `api/admin/[...path]/` | Admin API proxy | — |
| `api/send/` | Outbound message proxy | — |

### Libraries (`frontend/lib/`)

| File | Purpose |
|------|---------|
| `api.ts` | Typed API client with error handling |
| `api-hooks.ts` | React Query hooks (`useQuery`, `useMutation`) |
| `auth.ts` | Token verify/decode helpers |
| `rbac.ts` | RBAC helper functions (role checks) |
| `branding.ts` | White-label branding helpers |
| `chat-analytics.ts` | Analytics data transformations |
| `tokens.ts` | Token management (set, get, clear) |
| `base-path.ts` | Next.js basePath helper |
| `query-client.ts` | React Query client setup |
| `mock-data.ts` | Mock fixtures for development |
| `server/proxy.ts` | Server-side API proxy helper |

### Components (`frontend/components/`)

**Page-level** (`components/pages/`): `AnalyticsPage`, `ConversationsPage`, `DashboardPage`, `EscalationsPage`, `MagiclinePage`

**Layout**: `NavShell.tsx`, `Sidebar.tsx`, `TiptapEditor.tsx`

**Settings**: `settings/SettingsSubnav.tsx`

**UI Design System** (`components/ui/`): `Avatar`, `Badge`, `Card`, `ChannelIcon`, `ConfirmModal`, `CustomTooltip`, `Dialog`, `MiniButton`, `Modal`, `ProgressBar`, `QueryStates`, `SectionHeader`, `Stat`, `ToggleSwitch`

### Auth

- Cookie: `arni_access_token` (HMAC-SHA256, not JWT), 12h TTL
- RBAC roles: `system_admin` > `tenant_admin` > `tenant_user`
- Contract-tested in `frontend/tests/rbac.contract.test.ts`

---

## Authentication (All Layers)

| Layer | Mechanism |
|-------|-----------|
| Admin users | HMAC-SHA256 token in `arni_access_token` cookie; `get_current_user()` → `AuthContext` |
| End users (members) | Phone-based 6-digit MFA; code cached in Redis; matched to `StudioMember` via phone |
| WhatsApp webhooks | HMAC-SHA256 on raw request body (`meta_app_secret`) |
| Telegram webhooks | Secret header (`telegram_webhook_secret`) |
| Twilio (SMS/Voice) | HMAC-SHA1 |
| Passwords | PBKDF2-HMAC-SHA256, 200k iterations |
| Secret rotation | `AUTH_TRANSITION_MODE=true` enables parallel validation during rotation |

---

## Skills (MCP)

```
skills/
└── magicline-support/
    └── SKILL.md           # BINDING ruleset for all Magicline member support
```

`skills/magicline-support/SKILL.md` is **binding**: it governs all Magicline member operations. Never deviate from it. Always ask for clarification when ambiguous. Tools defined:
- `get_member_bookings`, `book_appointment`, `cancel_member_booking` (and ~5 more)
- Multi-variant disambiguation required (e.g., "Kraft Training mit/ohne Trainer" → must ask)
- Affirmative responses ("ja", "okay") must resolve against `pending_action` from context

---

## Engineering Rules

- **BMAD cycle**: Benchmark (define success metric first) → Modularize (build in isolation) → Architect (integrate into swarm/redis) → Deploy & Verify. Only commit on PASS.
- **Guardrails first**: `GuardrailsService.check()` runs before every LLM call. Never skip.
- **Emergency hard-route**: `notfall`, `herzinfarkt`, `unfall`, `112` → Medic directly, no LLM classification.
- **Medic disclaimer**: ALWAYS include `medic_disclaimer_text` from Settings. Never omit this.
- **One-Way-Door**: Irreversible actions (cancellations, deletions) require explicit human confirmation before execution.
- **Redis keys**: ALL Redis keys MUST go through `app/core/redis_keys.py` → `redis_key()`. No hardcoded strings.
- **Multi-tenant isolation**: Every DB query must filter by `tenant_id`. Never leak data across tenants.
- **MCP Tools**: New swarm tools go in `app/swarm/tools/`, new skills go in `skills/`. Tools must accept JSON Schema inputs, return structured JSON.
- **External API mocking**: All tests mock Magicline, WhatsApp, OpenAI. Never hit production APIs in CI.
- **PII**: Mask in logs via `app/integrations/pii_filter.py`. Camera data: 0s retention, RAM-only.
- **ACP Safety**: Self-refactoring runs inside `app/acp/sandbox.py`. No root access. File access restricted to `./workspace/` and `./data/`.
- **Conventional Commits**: `feat(scope):`, `fix:`, `refactor:`, etc. Scope examples: `saas/billing`, `memory/graph`, `integrations/magicline`.

---

## Coding Style

- **Python**: 4-space indentation, `from __future__ import annotations`, type hints required everywhere.
- **Tools**: `ruff` (lint), `mypy --strict` (types), `pytest` (tests).
- **TypeScript/React**: Strict mode, no implicit `any`, zero ESLint warnings (`lint:strict`).
- **Naming**:
  - Python modules/functions: `snake_case`
  - Classes/Pydantic models: `PascalCase`
  - React components: `PascalCase`
  - Next.js pages: `frontend/app/<route>/page.tsx` (App Router convention)

---

## Testing

| Location | Purpose |
|----------|---------|
| `tests/conftest.py` | Shared fixtures (fake Redis, mock DB, test client) |
| `tests/test_gateway.py`, `test_gateway_extended.py` | Webhook routes, Ghost Mode |
| `tests/test_auth_restore.py` | Auth initialization |
| `tests/test_multitenant_isolation.py` | Tenant data isolation |
| `tests/test_swarm.py` | Swarm routing + agents |
| `tests/test_memory.py` | Memory system (context, DB, flush) |
| `tests/test_security_hardening.py` | Auth edge cases, PII |
| `tests/test_acp.py` | ACP bridge |
| `tests/test_voice.py`, `tests/voice/` | Voice pipeline |
| `tests/test_vision.py` | Vision/YOLO stub |
| `tests/test_soul.py` | Soul evolution subsystem |
| `tests/agents/` | Agent-specific tests (ops booking, sales, magicline tools) |
| `tests/integrations/` | Magicline client, Telegram webhook |
| `tests/evals/` | LLM faithfulness evals (`golden_dataset.json`) |
| `tests/locustfile.py` | Load test (100 concurrent users, <100ms p95) |
| `frontend/tests/rbac.contract.test.ts` | RBAC contract tests |

**Rules**: `pytest-asyncio` for all async tests. Mock all external APIs with `fakeredis` and `httpx` test clients. Add tests with every behavior change, especially RBAC and tenant isolation.

---

## Magicline API Constraints (Critical)

| Endpoint | Constraint |
|----------|-----------|
| `GET /v1/appointments/booking?customerId=X` | **±2 weeks only** — hard API limit, no date filter possible |
| `GET /v1/classes/booking?customerId=X` | **±2 weeks only** — same constraint |
| `GET /v1/customers/{id}/activities/checkins` | Up to 365 days with `fromDate`+`toDate`; max `sliceSize=50` (>50 → 400 error); paginated via `offset` |

Configure `checkin_enabled` in Settings table to switch between check-in stats (default) and booking-based stats (fallback when check-in data is absent or zero).

---

## Environment Variables

Copy `.env.example` to `.env`. All variables:

```bash
# Gateway
ENVIRONMENT=development          # 'production' enables stricter checks
LOG_LEVEL=info
GATEWAY_PUBLIC_URL=              # e.g. https://arni.getimpulse.de (for webhook reg)
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Database
DATABASE_URL=sqlite:////app/data/arni.db  # or postgresql+psycopg://...
POSTGRES_PASSWORD=arni_dev_password

# Redis & Vector DB
REDIS_URL=redis://127.0.0.1:6379/0
QDRANT_URL=http://qdrant:6333

# LLM
OPENAI_API_KEY=<key>

# Auth & Security
AUTH_SECRET=<long-random-secret>           # HMAC signing key
ACP_SECRET=arni-acp-secret-changeme        # ACP WebSocket auth
AUTH_TOKEN_TTL_HOURS=12
AUTH_TRANSITION_MODE=false                 # true during secret rotation
AUTH_ALLOW_HEADER_FALLBACK=false
SYSTEM_ADMIN_PASSWORD=<≥16chars>           # Blocks startup in prod if weak

# Observability
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<key>
LANGFUSE_HOST=https://cloud.langfuse.com

# WhatsApp / Meta Cloud API
META_VERIFY_TOKEN=<token>
META_ACCESS_TOKEN=<token>
META_PHONE_NUMBER_ID=<id>
META_APP_SECRET=<secret>                   # HMAC-SHA256 webhook signature

# WhatsApp Web Bridge (Node.js / Baileys)
BRIDGE_MODE=production                     # 'self' = dev/self-chat only
BRIDGE_PORT=3000
BRIDGE_WEBHOOK_URL=http://localhost:8000/webhook/whatsapp
BRIDGE_AUTH_DIR=/app/data/whatsapp/auth_info_baileys

# Telegram
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_ADMIN_CHAT_ID=<id>
TELEGRAM_WEBHOOK_SECRET=<secret>

# Magicline
MAGICLINE_BASE_URL=<url>
MAGICLINE_API_KEY=<key>
MAGICLINE_STUDIO_ID=<id>

# Email (SMTP)
SMTP_HOST=<host>
SMTP_PORT=587
SMTP_USERNAME=<user>
SMTP_PASSWORD=<pass>
SMTP_FROM_EMAIL=<email>
SMTP_FROM_NAME=Arni
SMTP_USE_STARTTLS=true

# Voice
ELEVENLABS_API_KEY=<key>                   # Optional; Kokoro/Piper are local TTS

# Feature flags
VISION_ENABLE_YOLO=1                       # Enable real YOLOv8 inference (default: stub)
RTSP_ENABLE_LIVE=1                         # Enable live RTSP stream capture (default: stub)
```

---

## Key File Locations

| What | Where |
|------|-------|
| Guardrails config | `config/guardrails.yaml` |
| Prompt templates | `app/prompts/templates/{agent}/system.j2` |
| Per-tenant prompt overrides | `data/knowledge/tenants/{slug}/prompts/` |
| Knowledge base files | `data/knowledge/tenants/{slug}/` |
| Member memory files | `data/knowledge/tenants/{slug}/members/{phone}.md` |
| WhatsApp auth artifacts | `data/whatsapp/auth_info_baileys/` |
| ORM models | `app/core/models.py` |
| DB migrations | `alembic/versions/` + `app/core/db.py:run_migrations()` |
| Persona / Soul config | `docs/personas/SOUL.md` |
| Magicline skill ruleset | `skills/magicline-support/SKILL.md` (BINDING) |
| Architecture specs | `docs/specs/` |
| Ops runbook | `docs/ops/RUNBOOK.md` |
| Security audits | `docs/audits/` |
| Sprint plans | `docs/sprints/` |

---

## PR Guidelines

- Title ≤70 chars; put detail in body
- Include: problem/solution summary, impacted areas (backend/frontend/data), test evidence (commands + output), screenshots for UI changes
- PRs touching `frontend/` trigger CI quality gate automatically
- PRs touching `app/` should include updated/new pytest coverage
