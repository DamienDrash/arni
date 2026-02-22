# Repository Guidelines

## Project Structure & Module Organization
- `app/` contains backend services (FastAPI gateway, integrations, swarm agents, memory, prompts).
- `frontend/` is the Next.js control UI.
- `tests/` holds backend test suites (unit, integration, persistence, multitenancy, security).
- `docs/` stores audits, sprint plans, and architecture notes.
- `config/settings.py` defines runtime configuration.
- Runtime data is under `data/` (DB, knowledge files, tenant artifacts).

## Build, Test, and Development Commands
- Backend setup: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Run backend locally: `uvicorn app.gateway.main:app --host 0.0.0.0 --port 8000`
- Full stack (recommended): `docker compose up --build`
- Backend tests: `pytest tests/ -v`
- Coverage run: `pytest tests/ --cov=app --cov-report=term-missing`
- Frontend dev: `cd frontend && npm install && npm run dev`
- Frontend quality gate: `cd frontend && npm run qa:gate`

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints required, keep functions focused.
- Lint/type tools: `ruff`, `mypy` (strict), `pytest`.
- TypeScript/React: strict typing, no implicit `any`, ESLint clean (`lint:strict`).
- Naming:
  - Python modules/functions: `snake_case`
  - Classes/Pydantic models: `PascalCase`
  - React components: `PascalCase`
  - Files in `frontend/app`: route-based naming.

## Testing Guidelines
- Framework: `pytest` with async support (`pytest-asyncio`).
- Add tests with each behavior change, especially for RBAC and tenant isolation.
- Test files: `tests/test_<feature>.py`.
- Frontend RBAC contract test: `cd frontend && npm run test:rbac`.

## Commit & Pull Request Guidelines
- Follow Conventional Commit style used in history, e.g.:
  - `feat(saas/s8): ...`
  - `fix: ...`
  - `refactor: ...`
- Keep commits scoped and atomic; include tests with code changes.
- PRs should include:
  - concise problem/solution summary,
  - impacted areas (backend/frontend/data),
  - test evidence (commands + result),
  - screenshots for UI changes.

## Security & Configuration Tips
- Never commit secrets (`.env`, API keys, tokens).
- Validate tenant scoping on all new endpoints/queries.
- Prefer redacted logging for credentials and PII.
