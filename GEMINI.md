# GEMINI.md – ARIIA Project Context & Instructions

## Project Overview
**ARIIA (v1.4)** is a multi-tenant SaaS AI agent platform designed for fitness studios (specifically GetImpulse Berlin). It integrates multiple communication channels (WhatsApp, Telegram, SMS, Email, Voice) with a swarm-based AI architecture to handle member interactions, bookings, and studio operations.

### Core Technologies
- **Backend:** Python 3.12, FastAPI, Redis (Pub/Sub & Caching), SQLAlchemy (PostgreSQL/SQLite), Pydantic.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS.
- **AI Swarm:** GPT-4o-mini (Router), specialized agents (Ops, Sales, Medic, Vision, Persona).
- **Data/Memory:** 3-tier memory (RAM context, SQLite sessions, Vector DB/Knowledge files), Qdrant/ChromaDB, GraphRAG.
- **Integrations:** Meta Cloud API (WhatsApp), Telegram Bot API, Magicline (Studio Management), ElevenLabs/Kokoro/Piper (TTS), Whisper (STT), YOLOv8 (Vision).

---

## Development Workflow

### The BMAD Cycle
Every new feature or refactoring must follow the **BMAD** implementation method:
1.  **B - Benchmark:** Define the success metric/test case first.
2.  **M - Modularize:** Build the component in isolation.
3.  **A - Architect:** Integrate the module into the Swarm Router and Redis Bus.
4.  **D - Deploy & Verify:** Run tests and verify against the benchmark.

### Coding Standards
- **Model Context Protocol (MCP):** All tool integrations must be defined as MCP Tools in `app/tools/`, accepting JSON Schema inputs and returning structured JSON.
- **Multi-Tenant Isolation:** Every database query and Redis key must be scoped to a `tenant_id`.
- **Security & Privacy:**
    - **0s Retention:** Camera data/frames must be processed in RAM and deleted immediately (0s retention).
    - **PII Masking:** Personally Identifiable Information must be masked in logs via `app/integrations/pii_filter.py`.
    - **One-Way-Door:** Irreversible actions (deletions, cancellations) require human confirmation.
- **Medic Agent:** Must always include a legal health disclaimer and fallback to emergency services (112) for critical keywords.

---

## Key Commands

### Backend (Python)
- **Setup:** `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- **Run Gateway:** `uvicorn app.gateway.main:app --reload`
- **Run Tests:** `pytest tests/ -v` (Use `-k` for specific tests, `--cov` for coverage)
- **Linting:** `ruff check .`
- **Type Checking:** `mypy .`
- **Docker:** `docker compose up --build`

### Frontend (Next.js)
- **Setup:** `cd frontend && npm install`
- **Run Dev:** `npm run dev`
- **Quality Gate:** `npm run qa:gate` (Lints, type-checks, and builds)
- **Linting:** `npm run lint:strict`

---

## Architecture & File Structure

- `app/gateway/`: Webhook ingress (WhatsApp, Telegram), WebSocket control (Ghost Mode), and Redis Bus orchestration.
- `app/swarm/`: Swarm intelligence logic, intent classification (Router), and specialized agent implementations.
- `app/core/`: Models (SQLAlchemy), Auth (RBAC), DB migrations, and instrumentation.
- `app/integrations/`: Third-party API connectors (Magicline, WhatsApp, etc.).
- `app/memory/`: 3-tier memory system and GraphRAG logic.
- `app/tools/`: MCP-compliant tools used by agents.
- `frontend/`: Next.js dashboard for studio admins.
- `scripts/`: Utility scripts for deployment, audits, and data seeding.
- `docs/`: Comprehensive specifications, sprint plans, and audit reports.

## Environment Configuration
Required variables in `.env`:
- `DATABASE_URL`, `REDIS_URL`
- `OPENAI_API_KEY`
- `WA_VERIFY_TOKEN`, `WA_APP_SECRET`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`
- `MAGICLINE_API_KEY`, `MAGICLINE_BASE_URL`
- `AUTH_SECRET`, `ACP_SECRET`
