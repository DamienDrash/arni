# High-End Premium SaaS Transformation Plan

This document outlines the roadmap to transform ARIIA v1.4 from a "professional middleware" into a true **High-End Premium SaaS Solution**. The focus is on strict multi-tenancy, security (BYOK/Encryption), and architectural decoupling.

## Phase 1: Architecture Decoupling (The Gateway Split)
**Goal:** Dismantle the "God Object" `app/gateway/main.py` to improve maintainability and enforce strict separation of concerns.

- [ ] **Task 1.1:** Create `app/gateway/routers/webhooks.py`.
    - Move `/webhook/whatsapp` (and tenant variants) logic here.
    - Move `/webhook/telegram` logic here.
    - Move `/webhook/sms` and `/webhook/email` logic here.
- [ ] **Task 1.2:** Create `app/gateway/routers/voice.py`.
    - Centralize `/voice/incoming` and `/voice/stream` logic here.
- [ ] **Task 1.3:** Create `app/gateway/routers/websocket.py`.
    - Isolate the `/ws/control` (Ghost Mode) logic into its own router.
- [ ] **Task 1.4:** Clean up `app/gateway/main.py`.
    - It should only contain `FastAPI` app initialization, middleware setup, and router inclusion.

## Phase 2: Secure Configuration (Encryption & BYOK)
**Goal:** Enable "Bring Your Own Key" (OpenAI, Twilio) safely by encrypting sensitive settings at rest.

- [ ] **Task 2.1:** Introduce Encryption.
    - Add `cryptography` dependency.
    - Create `app/core/crypto.py` with `encrypt_value(str) -> str` and `decrypt_value(str) -> str` using `AUTH_SECRET` as the key (or a specific `ENCRYPTION_KEY`).
- [ ] **Task 2.2:** Update `PersistenceService`.
    - Modify `upsert_setting`: If key is in a "sensitive list" (e.g., `openai_api_key`), encrypt before saving.
    - Modify `get_setting`: If key is in "sensitive list", decrypt after retrieval.
    - Sensitive Keys: `openai_api_key`, `elevenlabs_api_key`, `twilio_auth_token`, `magicline_api_key`, `smtp_password`.

## Phase 3: Strict Multi-Tenancy (The "No Default" Policy)
**Goal:** Eliminate data leak risks by removing "System Default" fallbacks for tenant resolution.

- [ ] **Task 3.1:** Refactor `PersistenceService`.
    - Deprecate/Remove `get_default_tenant_id`.
    - All methods (`get_setting`, `get_session`, `save_message`) MUST require a valid `tenant_id`.
- [ ] **Task 3.2:** Update Webhook Ingress.
    - Hard-fail 404 if `tenant_slug` in URL is invalid.
    - Remove legacy routes (without slug) or strictly map them to a specific "Legacy Tenant" if absolutely necessary, but preferably remove them.
- [ ] **Task 3.3:** Scoped LLM Execution.
    - Refactor `SwarmRouter` to not use a global `LLMClient`.
    - Instead, resolve the `LLMClient` dynamically per request using the tenant's specific (encrypted) API key (or system default if plan allows).

## Phase 4: Scalable Infrastructure Readiness
**Goal:** Prepare the codebase for PostgreSQL and high-scale operations.

- [ ] **Task 4.1:** Async Database Verification.
    - Ensure all new routers use `await asyncio.to_thread` for blocking DB calls (as seen in `gateway/main.py`) or move to `sqlalchemy.ext.asyncio`. *For this plan, we stick to the existing `to_thread` pattern to minimize regression risk, but verify consistency.*
- [ ] **Task 4.2:** Refactor `RedisBus` for Namespace Isolation.
    - Verify all pub/sub channels are prefixed with `t{tenant_id}:`.

## Validation Strategy
- **Manual Verification:** After each phase, `pytest` will be run.
- **Deep Analysis:** A final audit using `codebase_investigator` will ensure no "default tenant" logic remains.
