# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

ARNI (v1.4) is a multi-tenant SaaS AI agent platform for fitness studios (WhatsApp, Telegram, SMS, Email, Voice) with a full admin dashboard. Tenants are fully isolated — each gets their own subscription plan, Jinja2 prompt templates, knowledge base, and branding. Powered by swarm-based agent routing (GPT-4o-mini) with a self-improvement ("Soul") subsystem and deterministic guardrails.

## Commands

### Backend (Python/FastAPI)

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run (manual)
redis-server --daemonize yes
uvicorn app.gateway.main:app --host 0.0.0.0 --port 8000

# Run (Docker – preferred, starts all services)
docker compose up --build

# Tests
pytest tests/ -v
pytest tests/test_auth.py -v          # single test file
pytest tests/ -k "test_name" -v       # single test by name
pytest tests/ --cov=app --cov-report=term-missing  # with coverage

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
npm run lint:strict           # ESLint with zero warnings
npm run typecheck             # tsc --noEmit
npm run test:rbac             # RBAC contract tests
npm run build                 # production build
```

The CI pipeline (`.github/workflows/frontend_quality.yml`) runs `lint:strict`, `typecheck`, `test:rbac`, and `build` on every PR touching `frontend/`.

## Architecture

### Request Flow

```
Platform (WA/TG/SMS/Email/Voice) → Webhook Endpoint (FastAPI)
  → InboundMessage normalization (app/integrations/normalizer.py)
  → GuardrailsService (deterministic safety check, pre-LLM)
  → Phone-based MFA verification gate (Redis)
  → Member matching (app/gateway/member_matching.py)
  → Swarm Router (GPT-4o-mini intent classifier)
  → Agent (Ops / Sales / Medic / Vision / Persona)
  → Platform Dispatcher → reply sent
```

### Infrastructure (Docker Compose)

| Service | Image | Purpose |
|---------|-------|---------|
| `arni-core` | Custom (Dockerfile) | FastAPI backend, port 8000 |
| `arni-frontend` | node:20-slim | Next.js admin panel, port 3000 |
| `redis` | redis:alpine | Pub/sub, session cache, MFA codes |
| `qdrant` | qdrant/qdrant | Vector DB for RAG / knowledge base |
| `postgres` | postgres:16-alpine | Primary relational DB (multi-tenant prod) |

### Key Backend Services

| Component | Location | Purpose |
|-----------|----------|---------|
| Gateway | `app/gateway/main.py` | Webhook ingress, WebSocket `/ws/control` (Ghost Mode), health, `/metrics` |
| Admin API | `app/gateway/admin.py` | REST endpoints for the dashboard (members, settings, knowledge, audit, etc.) |
| Redis Bus | `app/gateway/redis_bus.py` | Async pub/sub: `arni:inbound`, `arni:outbound`, `arni:events` |
| Redis Keys | `app/core/redis_keys.py` | Tenant-scoped key factory — all Redis keys MUST use this module |
| Swarm Router | `app/swarm/router/router.py` | Intent classification → agent dispatch |
| Swarm Intents | `app/swarm/router/intents.py` | Intent definitions and routing table |
| Agents | `app/swarm/agents/` | Ops (booking), Sales (retention), Medic (health), Vision, Persona |
| Swarm Tools | `app/swarm/tools/` | `magicline.py` (member-facing API wrapper), `knowledge_base.py` (RAG search) |
| Guardrails | `app/core/guardrails.py` | Deterministic safety layer ("Iron Dome"), config-driven via `config/guardrails.yaml` |
| Persistence | `app/gateway/persistence.py` | Singleton wrapping SQLAlchemy SessionLocal; `get_setting()`, `upsert_setting()` |
| Persistence Helpers | `app/gateway/persistence_helpers.py` | Additional DB query helpers |
| Member Matching | `app/gateway/member_matching.py` | Phone → StudioMember lookup |
| Memory (Context) | `app/memory/context.py` | RAM context: 20 turns / 30 min TTL |
| Memory (DB) | `app/memory/database.py` | SQLite sessions: 90 days retention |
| Memory (Knowledge) | `app/memory/knowledge.py` | Per-tenant knowledge file access |
| Memory (Graph) | `app/memory/graph.py` | GraphRAG FactGraph via NetworkX (member facts as nodes/edges) |
| Memory (Consent) | `app/memory/consent.py` | GDPR Art. 6 + 17 ConsentManager; cascade deletion on revocation |
| Memory (Analyzer) | `app/memory/member_memory_analyzer.py` | LLM-based extraction of durable member facts from chat history |
| Memory (Flush) | `app/memory/flush.py` | Memory flush / cleanup routines |
| Memory (Repository) | `app/memory/repository.py` | SessionRepository abstraction |
| Prompt Builder | `app/core/prompt_builder.py` | Tenant-aware prompt hydration from Settings table |
| Prompt Engine | `app/prompts/engine.py` | Jinja2 template renderer |
| Integrations | `app/integrations/` | WhatsApp (HMAC-SHA256), Telegram, Email (SMTP), Magicline, PII filter, WA Flows |
| Magicline | `app/integrations/magicline/` | `client.py`, `member_enrichment.py`, `members_sync.py`, `scheduler.py` |
| WhatsApp Web | `app/integrations/whatsapp_web/` | Node.js bridge (Baileys-based); auth artifacts in `data/whatsapp/` |
| Auth | `app/core/auth.py` | HMAC-SHA256 tokens, RBAC (system_admin / tenant_admin / tenant_user) |
| Feature Gates | `app/core/feature_gates.py` | HTTP 402/429 enforcement for plan limits |
| Observability | `app/core/observability.py` | LangFuse tracing wrapper with graceful fallback |
| Instrumentation | `app/core/instrumentation.py` | Prometheus metrics (`http_requests_total`, `http_request_duration_seconds`) |
| ACP Server | `app/acp/server.py` | WebSocket endpoint for IDE integration and self-refactoring |
| ACP Sandbox | `app/acp/sandbox.py` | Isolated execution environment for code changes |
| ACP Rollback | `app/acp/rollback.py` | Git-based rollback for ACP changes |
| ACP Refactor | `app/acp/refactor.py` | Refactoring engine (runs inside sandbox) |
| Soul / Evolution | `app/soul/` | `analyzer.py` (log analysis), `evolver.py` (prompt change proposals), `flow.py` (cycle orchestrator) |
| Knowledge Ingest | `app/knowledge/ingest.py` | MD file ingest into ChromaDB |
| Knowledge Store | `app/knowledge/store.py` | ChromaDB wrapper |
| Knowledge Retriever | `app/core/knowledge/retriever.py` | HybridRetriever (vector + BM25) |
| Skills | `skills/` | MCP-compliant skill definitions (e.g., `magicline-support/SKILL.md`) |
| Config | `config/settings.py` | Pydantic Settings loaded from `.env` |

### Frontend Structure

Next.js App Router with role-gated pages. Auth uses a cookie `arni_access_token` (HMAC-SHA256, not JWT). Role matrix is contract-tested in `frontend/tests/rbac.contract.test.ts`.

**Pages (`frontend/app/`):**

| Route | Purpose |
|-------|---------|
| `login/` | Login page |
| `register/` | Tenant registration |
| `analytics/` | Conversation analytics dashboard |
| `audit/` | Admin audit log viewer |
| `escalations/` | Escalation queue (human handoff) |
| `knowledge/` | Per-tenant knowledge base management |
| `live/` | Live WebSocket / Ghost Mode control |
| `magicline/` | Magicline member sync & enrichment stats |
| `member-memory/` | Member memory file viewer/editor |
| `members/` | Studio member list (enrichment status, language, check-in stats) |
| `plans/` | Subscription plan management |
| `system-prompt/` | Ops agent system-prompt editor |
| `tenants/` | Multi-tenant management (system_admin only) |
| `users/` | Admin user management |
| `settings/` | Settings hub with sub-pages: `account/`, `automation/`, `billing/`, `branding/`, `general/`, `integrations/`, `prompts/` |

**Libraries (`frontend/lib/`):**

| File | Purpose |
|------|---------|
| `auth.ts` | Token verify/decode helpers |
| `api.ts` | Typed API client |
| `api-hooks.ts` | React Query hooks |
| `rbac.ts` | RBAC helper functions |
| `branding.ts` | White-label branding helpers |
| `chat-analytics.ts` | Analytics data transforms |
| `tokens.ts` | Token management |
| `base-path.ts` | Next.js basePath helper |
| `query-client.ts` | React Query client setup |
| `mock-data.ts` | Mock fixtures for development |
| `server/proxy.ts` | Server-side API proxy helper |

**Components (`frontend/components/`):**

- `NavShell.tsx`, `Sidebar.tsx` — Layout shell
- `TiptapEditor.tsx` — Rich text editor
- `settings/SettingsSubnav.tsx` — Settings navigation
- `pages/` — Page-level components: `AnalyticsPage`, `ConversationsPage`, `DashboardPage`, `EscalationsPage`, `MagiclinePage`
- `ui/` — Design system atoms: `Avatar`, `Badge`, `Card`, `ChannelIcon`, `ConfirmModal`, `CustomTooltip`, `Dialog`, `MiniButton`, `Modal`, `ProgressBar`, `QueryStates`, `SectionHeader`, `Stat`, `ToggleSwitch`

### Database

SQLAlchemy ORM with SQLite (dev) / PostgreSQL (prod). Schema lives in `app/core/models.py`. Migrations are handled by `run_migrations()` in `app/core/db.py` (idempotent column-level backfills) and Alembic in `alembic/`.

Key tables: `tenants`, `users`, `chat_sessions`, `chat_messages`, `studio_members` (Magicline cache), `settings`, `audit_logs`, `plans`, `subscriptions`, `usage_records`.

`StudioMember` new fields (added in recent sprints): `gender`, `preferred_language`, `member_since`, `is_paused`, `additional_info` (JSON), `checkin_stats` (JSON), `recent_bookings` (JSON dict), `enriched_at`.

`Settings` table key-value store — important keys:

| Key | Default | Description |
|-----|---------|-------------|
| `checkin_enabled` | `true` | Use check-in stats; falls back to booking stats if disabled or data absent |
| `studio_name` | `Mein Studio` | Shown in agent prompts and branding |
| `agent_display_name` | `ARNI` | Member-facing agent name |
| `medic_disclaimer_text` | (legal text) | Appended to all Medic agent replies |
| ...and others seeded by `PROMPT_SETTINGS_KEYS` in `app/core/prompt_builder.py` | | |

### Authentication

- **Admin users**: HMAC-SHA256 token, cookie `arni_access_token`, 12h TTL (`auth_token_ttl_hours`). Backend dependency `get_current_user()` returns `AuthContext`.
- **End users (members)**: Phone-based 6-digit MFA, code cached in Redis, matched to Magicline member.
- **Webhooks**: WhatsApp → HMAC-SHA256 on raw body; Telegram → secret header; Twilio → HMAC-SHA1.
- **Passwords**: PBKDF2-HMAC-SHA256 with 200k iterations.
- **Auth transition mode**: `AUTH_TRANSITION_MODE=true` enables parallel validation during secret rotation.

### SaaS Architecture (S1–S7+)

| Feature | Location | Notes |
|---------|----------|-------|
| Plans & Billing | `app/core/feature_gates.py`, `app/core/models.py` | Starter/Pro/Enterprise; metered usage; HTTP 402/429 gates; Stripe integration |
| Prompt Templates | `app/prompts/`, `app/prompts/templates/` | Per-agent Jinja2 `.j2`; per-tenant override via `data/knowledge/tenants/{slug}/prompts/` |
| Knowledge Bases | `app/knowledge/`, `app/core/knowledge/` | Per-tenant ChromaDB + Qdrant collections; HybridRetriever (vector + BM25) |
| Redis Namespacing | `app/core/redis_keys.py` | Keys: `t{tenant_id}:{domain}:{key}` — always use `redis_key()` |
| White-label Branding | Admin API + `frontend/app/settings/branding/` | `tenant_logo_url`, `tenant_primary_color`, `tenant_app_title` |
| Tenant Onboarding | `app/gateway/auth.py` | On register: auto-seed Starter subscription + prompt defaults |
| Tenant-aware Prompts | `app/core/prompt_builder.py` | Fills `{placeholders}` from Settings table at call time |
| Vision (stub mode) | `app/vision/` | Set `VISION_ENABLE_YOLO=1` for real YOLOv8 inference; default is stub |
| Voice (stub mode) | `app/voice/` | `SpeechToText` (Whisper), `TextToSpeech` (Kokoro/Piper), `VoicePipeline`; stub by default |
| Observability | `app/core/observability.py` | LangFuse traces; degrades gracefully if `LANGFUSE_*` not set |
| Prometheus Metrics | `app/core/instrumentation.py` | Exposed at `GET /metrics` |
| ACP (IDE bridge) | `app/acp/` | WebSocket at `/acp/ws`; sandboxed self-refactoring with git rollback |
| Soul / Self-Improvement | `app/soul/` | Analyze logs → propose prompt changes → (human-gated) apply |
| GDPR Consent | `app/memory/consent.py` | Art. 6 check + Art. 17 cascade erasure |
| GraphRAG | `app/memory/graph.py` | NetworkX FactGraph for member relationship facts |
| Member Memory | `app/memory/member_memory_analyzer.py` | LLM-based extraction; cron-schedulable; stored as Markdown in `data/knowledge/` |
| Magicline Enrichment | `app/integrations/magicline/member_enrichment.py` | Check-in stats, booking history (±2 week API limit), member profile |
| Magicline Sync | `app/integrations/magicline/members_sync.py` | Bulk sync of all members from Magicline API |
| Magicline Scheduler | `app/integrations/magicline/scheduler.py` | Background enrichment for all tenant members |
| WA Web Bridge | `app/integrations/whatsapp_web/` | Node.js Baileys bridge; auth dir configurable via `BRIDGE_AUTH_DIR` |
| Email (SMTP) | `app/integrations/email.py` | `SMTPMailer`; verification email support |
| WA Flows | `app/integrations/wa_flows.py` | WhatsApp interactive message builders (buttons, lists) |
| Skills | `skills/` | MCP-compliant skill rule files; `magicline-support/SKILL.md` is binding for Magicline operations |

## Engineering Rules (from `docs/specs/CODING_STANDARDS.md`)

- **BMAD cycle**: Benchmark (define success metric) → Modularize (build in isolation) → Architect (integrate into swarm/redis) → Deploy & Verify. Only commit on PASS.
- **MCP Tools**: New skills/tools go in `app/swarm/tools/` or `skills/`, must inherit `BaseTool` (or be MCP-compliant SKILL.md), accept JSON Schema inputs, return structured JSON.
- **Skills are binding**: The `skills/magicline-support/SKILL.md` ruleset governs all Magicline member support operations — no alternatives, always ask if ambiguous.
- **One-Way-Door**: Irreversible actions (deletions, cancellations) require human confirmation before execution.
- **Emergency hard-route**: Keywords like "notfall", "unfall" bypass LLM classification and go directly to the Medic agent.
- **Medic agent**: ALWAYS include the legal health disclaimer (`medic_disclaimer_text` from Settings) and fallback to 112. Never omit this.
- **Guardrails first**: `GuardrailsService.check()` runs before every LLM call to block dangerous/off-topic inputs without spending tokens.
- **External API mocking**: All tests must mock Magicline, WhatsApp, OpenAI. Never hit production APIs in CI.
- **Multi-tenant isolation**: Every DB query must be scoped to `tenant_id`. Never leak data across tenants. All Redis keys must go through `app/core/redis_keys.py`.
- **PII**: Mask in logs via `app/integrations/pii_filter.py`. Camera data: 0s retention (RAM-only).
- **Conventional Commits**: Use `feat(scope):`, `fix:`, `refactor:` etc. Scope examples: `saas/s8`, `memory`, `integrations/magicline`.
- **ACP Safety**: Self-refactoring always runs inside `app/acp/sandbox.py` (Dockerized). No root access. File access restricted to `./workspace/` and `./data/`.

## Coding Style & Naming Conventions

- **Python**: 4-space indentation, type hints required (`from __future__ import annotations`), keep functions focused.
- **Lint / type tools**: `ruff`, `mypy` (strict), `pytest`.
- **TypeScript / React**: strict typing, no implicit `any`, ESLint clean (`lint:strict`).
- **Naming**:
  - Python modules/functions: `snake_case`
  - Classes/Pydantic models: `PascalCase`
  - React components: `PascalCase`
  - Files in `frontend/app/`: route-based naming (Next.js App Router)

## Testing

| Location | Purpose |
|----------|---------|
| `tests/test_*.py` | Backend unit/integration tests |
| `tests/agents/` | Agent-specific tests (ops booking, sales, magicline tools) |
| `tests/integrations/` | Integration tests (Magicline client, Telegram webhook) |
| `tests/evals/` | LLM faithfulness evaluations (`test_faithfulness.py`, `golden_dataset.json`) |
| `tests/voice/` | Voice ingress tests |
| `tests/conftest.py` | Shared fixtures |
| `tests/locustfile.py` | Load test definitions |
| `tests/run_all_qa.py` | QA runner script |
| `tests/run_evals.py` | Eval runner script |
| `frontend/tests/rbac.contract.test.ts` | RBAC contract tests |

**Rules**: Use `pytest-asyncio` for async tests. Mock all external APIs (Magicline, WhatsApp, OpenAI) with `fakeredis` and `httpx` test clients. Add tests per behavior change, especially for RBAC and tenant isolation.

## Environment

Copy `.env.example` to `.env`. Key variables:

```bash
# Database
DATABASE_URL=sqlite:////app/data/arni.db   # or postgres://...
POSTGRES_PASSWORD=arni_dev_password

# Auth & Security
AUTH_SECRET=<long-random-secret>
ACP_SECRET=arni-acp-secret-changeme
AUTH_TOKEN_TTL_HOURS=12
AUTH_TRANSITION_MODE=false
AUTH_ALLOW_HEADER_FALLBACK=false

# Redis & Vector DB
REDIS_URL=redis://127.0.0.1:6379/0
QDRANT_URL=http://qdrant:6333

# LLM
OPENAI_API_KEY=<key>

# Observability
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<key>
LANGFUSE_HOST=https://cloud.langfuse.com

# WhatsApp / Meta
META_VERIFY_TOKEN=<token>
META_ACCESS_TOKEN=<token>
META_PHONE_NUMBER_ID=<id>
META_APP_SECRET=<secret>

# WhatsApp Web Bridge
BRIDGE_MODE=production          # 'self' for dev (self-chat only)
BRIDGE_AUTH_DIR=/app/data/whatsapp/auth_info_baileys

# Telegram
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_ADMIN_CHAT_ID=<id>
TELEGRAM_WEBHOOK_SECRET=<secret>

# Magicline
MAGICLINE_BASE_URL=<url>
MAGICLINE_API_KEY=<key>

# SMTP / Email
SMTP_HOST=<host>
SMTP_PORT=587
SMTP_USERNAME=<user>
SMTP_PASSWORD=<pass>
SMTP_FROM_EMAIL=<email>

# Voice
ELEVENLABS_API_KEY=<key>        # optional; Kokoro/Piper are local TTS
```

Optional feature flags:

```bash
VISION_ENABLE_YOLO=1            # Enable real YOLOv8 inference (default: stub)
RTSP_ENABLE_LIVE=1              # Enable live RTSP stream capture (default: stub)
SYSTEM_ADMIN_PASSWORD=<≥16chars>  # Blocks startup in production if weak
```

## Magicline API Constraints (Important)

- `GET /v1/appointments/booking?customerId=X` — only **±2 weeks** (hard API limit, no date filter)
- `GET /v1/classes/booking?customerId=X` — only **±2 weeks** (same constraint)
- `GET /v1/customers/{id}/activities/checkins` — up to 365 days with `fromDate`+`toDate`, max `sliceSize=50` (>50 → 400 error), paginated via `offset`
- Configure `checkin_enabled` in Settings table to switch between check-in and booking-based stats

## PR Guidelines

- Short title (≤70 chars), detail in description body
- Include: problem/solution summary, impacted areas (backend/frontend/data), test evidence (commands + output), screenshots for UI changes
- PRs touching `frontend/` trigger the CI quality gate automatically
