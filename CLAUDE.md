# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

ARIIA is a multi-tenant SaaS AI agent platform for fitness studios (WhatsApp, Telegram, SMS, Email, Voice) with a full admin dashboard. Tenants are fully isolated — each gets their own subscription plan, Jinja2 prompt templates, knowledge base, and branding. Powered by swarm-based agent routing (GPT-4o-mini).

## Commands

### Backend (Python/FastAPI)

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run (manual)
redis-server --daemonize yes
uvicorn app.gateway.main:app --host 0.0.0.0 --port 8000

# Run (Docker – preferred)
docker compose up --build

# Tests
pytest tests/ -v
pytest tests/test_auth.py -v          # single test file
pytest tests/ -k "test_name" -v       # single test by name

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
npm run lint:strict           # ESLint with zero wariiangs
npm run typecheck             # tsc --noEmit
npm run test:rbac             # RBAC contract tests
npm run build                 # production build
```

The CI pipeline (`.github/workflows/frontend_quality.yml`) runs `lint:strict`, `typecheck`, `test:rbac`, and `build` on every PR touching `frontend/`.

## Architecture

### Request Flow

```
Platform (WA/TG/SMS) → Webhook Endpoint (FastAPI)
  → InboundMessage normalization
  → Phone-based MFA verification gate (Redis)
  → Swarm Router (GPT-4o-mini intent classifier)
  → Agent (Ops / Sales / Medic / Vision / Persona)
  → Platform Dispatcher → reply sent
```

### Key Services

| Component | Location | Purpose |
|-----------|----------|---------|
| Gateway | `app/gateway/main.py` | Webhook ingress, WebSocket `/ws/control` (Ghost Mode), health |
| Redis Bus | `app/gateway/redis_bus.py` | Async pub/sub: `ariia:inbound`, `ariia:outbound`, `ariia:events` |
| Swarm Router | `app/swarm/` | Intent classification → agent dispatch |
| Agents | `app/swarm/agents/` | Ops (booking), Sales (retention), Medic (health), Vision, Persona |
| Persistence | `app/gateway/persistence.py` | Singleton wrapping SQLAlchemy SessionLocal |
| Memory | `app/memory/` | 3-tier: RAM context (20 turns/30 min TTL), SQLite sessions (90 days), knowledge files |
| Integrations | `app/integrations/` | WhatsApp (HMAC-SHA256), Telegram, Magicline, PII filter |
| Auth | `app/core/auth.py` | HMAC-SHA256 tokens, RBAC (system_admin / tenant_admin / tenant_user) |
| Config | `config/settings.py` | Pydantic Settings loaded from `.env` |

### Frontend Structure

Next.js app router with role-gated pages. Auth uses a cookie `ariia_access_token` (HMAC-SHA256, not JWT). Role matrix is contract-tested in `frontend/tests/rbac.contract.test.ts`.

- `frontend/app/` – Pages (login, users, settings, integrations, etc.)
- `frontend/components/` – NavShell, Sidebar, Modal, settings sub-components
- `frontend/lib/auth.ts` – Token verify/decode helpers
- `frontend/app/api/auth/[...path]/route.ts` – Auth API proxy to backend

### Database

SQLAlchemy ORM with SQLite (dev) / PostgreSQL (prod). Schema lives in `app/core/models.py`. Migrations are handled by `run_migrations()` in `app/core/db.py` (idempotent column-level backfills) and Alembic in `alembic/`.

Key tables: `tenants`, `users`, `chat_sessions`, `chat_messages`, `studio_members` (Magicline cache), `settings`, `audit_logs`, `plans`, `subscriptions`, `usage_records`.

### Authentication

- **Admin users**: HMAC-SHA256 token, cookie `ariia_access_token`, 12h TTL. Backend dependency `get_current_user()` returns `AuthContext`.
- **End users (members)**: Phone-based 6-digit MFA, code cached in Redis, matched to Magicline member.
- **Webhooks**: WhatsApp → HMAC-SHA256 on raw body; Telegram → secret header; Twilio → HMAC-SHA1.
- **Passwords**: PBKDF2-HMAC-SHA256 with 200k iterations.

### SaaS Architecture (added S1–S7)

| Feature | Location | Notes |
|---------|----------|-------|
| Plans & Billing | `app/core/feature_gates.py`, `app/core/models.py` | Starter/Pro/Enterprise; metered usage; HTTP 402/429 gates |
| Prompt Templates | `app/prompts/`, `app/prompts/templates/` | Per-agent Jinja2 `.j2`; per-tenant override via `data/knowledge/tenants/{slug}/prompts/` |
| Knowledge Bases | `app/knowledge/` | Per-tenant ChromaDB collections (`ariia_knowledge_{slug}`); ingest MD files |
| Redis Namespacing | `app/gateway/redis_bus.py` | Keys: `t{tenant_id}:{domain}:{key}` |
| White-label Branding | Admin API + `frontend/app/settings/branding/` | `tenant_logo_url`, `tenant_primary_color`, `tenant_app_title` |
| Tenant Onboarding | `app/gateway/auth.py` | On register: auto-seed Starter subscription + prompt defaults |
| Vision (stub mode) | `app/vision/` | Set `VISION_ENABLE_YOLO=1` for real inference; default is stub |
| Voice (stub mode) | `app/voice/` | `SpeechToText`, `TextToSpeech`, `VoicePipeline` are stub-mode by default |

## Engineering Rules (from `docs/specs/CODING_STANDARDS.md`)

- **BMAD cycle**: Benchmark (define success metric) → Modularize (build in isolation) → Architect (integrate into swarm/redis) → Deploy & Verify. Only commit on PASS.
- **MCP Tools**: New skills/tools go in `app/tools/`, must inherit `BaseTool`, accept JSON Schema inputs, return structured JSON.
- **One-Way-Door**: Irreversible actions (deletions, cancellations) require human confirmation before execution.
- **Emergency hard-route**: Keywords like "notfall", "unfall" bypass LLM classification and go directly to the Medic agent.
- **Medic agent**: ALWAYS include the legal health disclaimer and fallback to 112 for emergencies. Never omit this.
- **External API mocking**: All tests must mock Magicline, WhatsApp, OpenAI. Never hit production APIs in CI.
- **Multi-tenant isolation**: Every DB query must be scoped to `tenant_id`. Never leak data across tenants.
- **PII**: Mask in logs via `app/integrations/pii_filter.py`. Camera data: 0s retention (RAM-only).

## Environment

Copy `.env.example` to `.env`. Required variables include: `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `WA_VERIFY_TOKEN`, `WA_APP_SECRET`, `TELEGRAM_BOT_TOKEN`, `MAGICLINE_API_KEY`, `AUTH_SECRET`, `ACP_SECRET`.

Optional feature flags:
- `VISION_ENABLE_YOLO=1` — enable real YOLOv8 inference (default: stub mode)
- `RTSP_ENABLE_LIVE=1` — enable live RTSP stream capture (default: stub mode)
- `SYSTEM_ADMIN_PASSWORD` — must be ≥16 chars; weak passwords block startup in production
