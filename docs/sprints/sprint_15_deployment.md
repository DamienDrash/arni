# Sprint 15: Deployment & Scale (No Mocks)

**Goal:** Transition ARNI from a development prototype (with mocks) to a production-ready containerized application connected to real infrastructure.

## User Stories
| ID | Story | Acceptance Criteria |
| :--- | :--- | :--- |
| **US-15.1** | **Containerization** | Dockerfile builds successfully; `PYTHONPATH` matches production standards; No import errors. |
| **US-15.2** | **Real Infrastructure** | System converts to use `Qdrant` (Vector DB) and `Redis` (Cache) via Docker Compose. No more `MockVectorIndex`. |
| **US-15.3** | **Orchestration** | Kubernetes manifests (Deployment, Service) valid and applyable. |

## Architecture Changes
### 1. The "Path Fix" (Docker Strategy)
- We will standardize the runtime environment using a multi-stage `Dockerfile`.
- **Base Image:** `python:3.12-slim`
- **Env:** `PYTHONPATH=/app`
- **Entrypoint:** `gunicorn app.main:app`

### 2. "No Mocks" Policy (Infrastructure)
- **Vector DB:** Qdrant (Docker Image: `qdrant/qdrant`)
- **Cache:** Redis (Docker Image: `redis:alpine`)
- **Tracing:** LangFuse (Cloud or Self-Hosted)

## Implementation Steps

### 15.1 Containerization
1. Create `Dockerfile` with explicit path handling.
2. Create `.dockerignore`.
3. Verify build.

### 15.2 Real Data Integration
1. Add `qdrant-client` to `pyproject.toml`.
2. Rewrite `app/core/knowledge/retriever.py` to connect to `os.getenv("QDRANT_HOST")`.
3. Create `docker-compose.yml` spinning up the full stack.

### 15.3 Kubernetes (Optional/stretch)
1. Generate Helm chart or raw manifests.
