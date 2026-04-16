# Implementation Plan: Domain-Driven Modular Monolith Refactoring

This plan translates the 10-Epic product and architecture consolidation roadmap into a concrete, executable strategy.

## Goal Description
Transform the current highly-coupled 106K LOC monolithic backend into a capability-based, modular monolith. We will aggressively trim the active execution footprint down to the real product core, dormitize unused features, and establish firm boundaries using a Thin API Edge, Module Registry, and Event/Capability wiring.

## Progress Update (2026-03-27)
- Epic 3 backend runtime wiring is now in place:
  - `FeatureGate` resolves technical capabilities declaratively from plans and add-ons.
  - `ModuleRegistry` distinguishes deployment-active modules from tenant-level capability evaluation.
  - `app.edge` registry setup is idempotent and no longer accumulates duplicate module registrations.
  - Regression coverage exists for runtime-active modules, tenant capability resolution, and `/health/app` active-module reporting.
- Epic 3 frontend gating is now in place:
  - `/admin/permissions` exposes tenant capabilities plus runtime-active/dormant capability metadata.
  - The frontend resolves route states centrally as `available`, `upgrade`, `coming_soon`, or `hidden`.
  - Dormant routes are still visible in navigation where appropriate, but render as `Coming Soon` instead of loading inactive UI flows.
  - Route-access contract tests protect the dormant/hidden/available matrix.
- Epic 4 progress:
  - `app.edge.app` is the effective application assembly point.
  - Legacy `app.gateway.main` has been reduced to a compatibility shim that reuses the edge app and only keeps backward-compatible exports like `/health`, `/ws/control`, `broadcast_to_admins`, and `_whatsapp_verifier`.
  - Health endpoints are standardized under `/health`, `/health/app`, `/health/db`, `/health/redis`, `/health/workers`, and `/health/integrations`, while legacy `/health` remains backward-compatible.
- Epic 5 progress:
  - The first `admin.py` extraction slice is now separated into `app.gateway.routers.admin_settings`.
  - Frontend-critical settings/platform endpoints like `/admin/prompt-config`, `/admin/platform/email/test`, and `/admin/platform/whatsapp/*` no longer live in the 3.4K-line fallback router.
  - The settings/platform flows now also have an application-layer service in `app.gateway.services.admin_settings_service`.
  - Prompt-config persistence, SMTP probe/send logic, and WhatsApp QR/reset bridge orchestration are no longer implemented inline inside the router.
  - Core admin settings endpoints are now separated into `app.gateway.routers.admin_core_settings`.
  - `/admin/settings*` and `/admin/tenant-preferences` are no longer owned by the fallback admin router, reducing the legacy surface for frontend settings pages and tenant branding flows.
  - The core settings/preferences flows now also have an application-layer service in `app.gateway.services.admin_core_settings_service`.
  - Sensitive-setting masking, batch/single-setting persistence, and tenant-preferences fallback/default resolution are no longer implemented inline inside the router.
  - Integration configuration endpoints are now separated into `app.gateway.routers.admin_integrations`.
  - `/admin/integrations/config`, `/admin/integrations/test/*`, `/admin/integrations/health`, and deletion flows no longer live in the fallback admin router.
  - The integrations flows now also have an application-layer service in `app.gateway.services.admin_integrations_service`.
  - Secret masking/persistence, connector probes, health aggregation, and Magicline config-trigger orchestration are no longer implemented inline inside the router.
  - Knowledge and member-memory file administration endpoints are now separated into `app.gateway.routers.admin_knowledge`.
  - `/admin/knowledge*` and `/admin/member-memory*` no longer live in the fallback admin router, shrinking the legacy surface for content ingestion and memory-maintenance workflows.
  - The knowledge/member-memory flows now also have an application-layer service in `app.gateway.services.admin_knowledge_service`.
  - Filesystem path resolution, ingest/reindex orchestration, vector-store status reads, and member-memory run/status handling are no longer implemented inline inside the router.
  - Prompt and agent-template administration endpoints are now separated into `app.gateway.routers.admin_prompts`.
  - `/admin/prompts/*` and `/admin/prompts/agent/*` no longer live in the fallback admin router, shrinking the legacy surface for system prompts and tenant prompt overrides.
  - The prompt/template flows now also have an application-layer service in `app.gateway.services.admin_prompts_service`.
  - Filesystem path resolution, prompt/template concurrency checks, and audit-backed save/reset logic are no longer implemented inline inside the router.
  - Analytics and audit endpoints are now separated into `app.gateway.routers.admin_analytics`.
  - `/admin/analytics/*`, `/admin/analytics/channels`, `/admin/analytics/sessions/recent`, and `/admin/audit` no longer live in the fallback admin router, shrinking the legacy surface for KPI aggregation, dashboard tables, and compliance log access.
  - Operations endpoints are now separated into `app.gateway.routers.admin_operations`.
  - `/admin/members*`, `/admin/chats*`, `/admin/handoffs*`, `/admin/tokens`, and `/admin/stats` no longer live in the fallback admin router, shrinking the legacy surface for day-to-day support operations and tenant-scoped CRM workflows.
  - The operational admin flows now also have an application-layer service in `app.gateway.services.admin_operations_service`.
  - Token hydration, handoff resolution, chat resets, member orchestration, and Redis key compatibility are no longer implemented inline inside the router.
  - Billing and platform-governance endpoints are now separated into `app.gateway.routers.admin_billing_platform`.
  - `/admin/plans/config`, `/admin/billing/*`, and `/admin/platform/llm/*` no longer live in the fallback admin router, shrinking the legacy surface for SaaS governance, billing connectors, and platform-wide LLM administration.
  - The billing/platform governance flows now also have an application-layer service in `app.gateway.services.admin_billing_platform_service`.
  - Connector masking, plan config persistence, subscription/usage reads, and platform LLM governance are no longer implemented inline inside the router.
  - The analytics/audit flows now also have an application-layer service in `app.gateway.services.admin_analytics_service`.
  - KPI aggregation, channel rollups, recent-session formatting, and audit payload parsing are no longer implemented inline inside the router.
  - `app.gateway.admin` itself is now only a compatibility shim with an empty `/admin` router; the old monolith no longer owns runtime behavior.
  - All extracted `app.gateway.routers.admin_*` modules are now thin HTTP adapters; DB, filesystem, integration, and audit orchestration now live in dedicated application services.
  - The remaining legacy `connector_hub` surface is now mounted explicitly as a compatibility router in the edge assembly instead of being an accidental runtime leftover.
  - `GET /admin/connector-hub/catalog` was hardened into a read-only, tenant-local catalog read and no longer mutates settings during a GET request.
  - The integrations frontend now deduplicates in-flight catalog fetches, preventing duplicate browser-side requests from tripping the legacy compatibility endpoint during page bootstrap.
  - Frontend verification is now complete for the tenant-admin admin flows used in the current product core: `settings/general`, `settings/prompts`, `settings/integrations`, `knowledge`, `member-memory`, and `analytics` were browser-smoke-tested without 4xx/5xx admin API failures or console errors.
- Epic 6 progress:
  - `app.shared.db` now exists as the first shared persistence foundation with `session_scope`, `transaction_scope`, and a small sync `UnitOfWork`.
  - `app.gateway.persistence` no longer depends on `scoped_session` and no longer opens direct `SessionLocal()` sessions inline; the central legacy persistence facade now runs on `app.shared.db` session helpers.
  - `app.gateway.services.admin_analytics_service`, `app.gateway.services.admin_operations_service`, `app.gateway.services.admin_core_settings_service`, `app.gateway.services.admin_integrations_service`, `app.gateway.services.admin_billing_platform_service`, and `app.gateway.services.admin_knowledge_service` now depend on the shared session helpers instead of ad-hoc `SessionLocal()`/`close()` blocks.
  - `app.gateway.auth` now also runs on the shared session helpers across registration, login, password reset, profile, user/tenant admin, invitation, impersonation, and MFA flows; the module no longer opens direct `SessionLocal()` sessions.
  - `app.contacts.service` now runs fully on `app.shared.db`: both the read/query slice and the write/transaction slice use shared session helpers, and the module no longer opens direct `SessionLocal()` sessions.
  - The contacts edge assembly now mounts the `/v2/admin/contacts` compatibility alias explicitly again, restoring `/v2/admin/contacts/segments` during the Epic 6 verification pass.
  - A focused service regression contract now covers the refactored contact write paths (`create/update/delete`, custom fields, tags, and lifecycle transition), which also flushed out and fixed a pre-existing `metadata`/`metadata_json` bug in lifecycle activity logging.
  - The legacy Stripe compatibility router at `app.gateway.routers.billing` no longer opens direct `SessionLocal()` sessions; its DB lifecycle now enters through `app.shared.db.open_session`.
  - The edge assembly now mounts `/admin/billing/*` explicitly as a compatibility surface, so the same legacy billing contract is available through `app.edge.app` and `app.gateway.main`.
  - The Billing V2 router at `app.billing.router` also no longer opens direct `SessionLocal()` sessions; its public catalog and tenant subscription flows now enter through `app.shared.db.open_session`.
  - Test bootstrap now seeds both the canonical legacy public plan catalog and the canonical Billing-V2 catalog before each run, keeping `/admin/billing/plans` and `/billing/plans` aligned with the expected Starter/Pro/Enterprise product surface.
  - A focused Billing V2 regression contract now covers the public `/billing/plans` surface and the default subscription state for a freshly registered tenant.
  - The Billing V2 admin router at `app.billing.admin_router` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the module.
  - A focused admin billing regression contract now covers `/admin/plans/public` plus the protected `/admin/plans/subscribers` surface for both system-admin and tenant-admin roles.
  - The edge registry no longer mounts the replaced legacy duplicate `app.gateway.routers.plans_admin`; `tenant_management` now mounts `app.billing.admin_router` directly, and the obsolete staging router file has been deleted instead of being refactored in parallel.
  - `app.platform.api.marketplace` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the marketplace router.
  - A focused marketplace API contract now covers the fallback catalog surface and the `activate` failure mode when the integration registry is unavailable.
  - The marketplace router also had a hidden runtime bug in the integration test path (`asyncio.iscoroutinefunction` without importing `asyncio`); that is now fixed while touching the same code path.
  - `app.platform.api.tenant_portal` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the tenant portal router.
  - A focused tenant-portal API contract now covers the overview payload and a channels update/readback roundtrip.
  - The tenant portal overview also had a real compatibility bug in audit rendering (`details` vs `details_json`); that path now tolerates both legacy and newer audit payload fields.
  - `app.platform.api.analytics` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the analytics router.
  - A focused analytics API contract now covers the dashboard surface and the CSV export path.
  - The analytics export endpoint had a transport-level hang in the CSV branch; because the export is generated synchronously in-memory, that path now returns a normal `Response` instead of a `StreamingResponse`.
  - `app.core.feature_gates` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` openings have been removed from plan loading, addon loading, usage loading, usage mutation, seed, and overdue-trial maintenance paths.
  - The feature-gate regression surface stays green across runtime capability resolution and billing plan seeding, so the central plan/capability path is now aligned with the shared DB layer instead of remaining a legacy outlier.
  - `app.gateway.routers.swarm_admin` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the Swarm admin CRUD/config surface.
  - The Epic 6 verification pass also exposed a real assembly gap: `/admin/swarm/*` was no longer mounted in the edge build. `app.edge.registry_setup` now mounts the Swarm admin router explicitly again inside the admin control plane, and the focused Swarm admin regression suite is back to green.
  - The old tenant-level LLM router (`app.gateway.routers.tenant_llm`) turned out to be dead code: it was no longer mounted anywhere in the edge build, while the live `/settings/ai` tenant flow already runs through `app.ai_config.router`.
  - The matching frontend component `frontend/components/settings/TenantLLMManager.tsx` was also unreferenced. Both legacy files have been deleted instead of being refactored, which removes an obsolete API surface and prevents the persistence inventory from being polluted by a dead path.
  - `app.worker.campaign_tasks` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the send-batch, scheduler, analytics aggregation, A/B evaluation, and follow-up worker paths.
  - The focused campaign-adjacent regression gate (`test_tenant_isolation_idempotency_hmac`) stays green after this worker-side session cleanup, so Epic 6 is no longer leaving the main campaign worker as a legacy session outlier.
  - `app.gateway.routers.members_crud` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from member CRUD, custom-column, CSV import, and CSV export paths.
  - A focused members CRUD contract now covers create/list, duplicate detection, and CSV export. While adding that coverage, the member serialization path was centralized so the router no longer reimplements ad-hoc payload shaping across create/list/update.
  - `app.gateway.routers.llm_costs` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from model-cost CRUD plus cost/usage analytics endpoints.
  - A focused LLM-costs contract now covers the system-admin model-cost roundtrip and the usage-summary aggregation path, so this analytics/control router is no longer an untested persistence outlier.
  - `app.swarm.registry.dynamic_loader` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the agent-definition load, tenant agent-config load, tenant tool-config load, and agent-listing paths.
  - A focused dynamic-loader contract now covers DB-backed agent listing and tenant override loading, so the swarm runtime no longer keeps this central loader as a direct-session outlier.
  - `app.gateway.routers.contact_sync_api` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from integration toggle, sync-stats, and webhook tenant-resolution paths.
  - The focused Contact-Sync verification also exposed a real assembly gap: the unauthenticated `webhook_router` was no longer mounted in the edge build. `app.edge.registry_setup` now mounts that router explicitly again inside the support core, and the focused router contract is back to green.
  - `app.gateway.routers.connector_hub` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the tenant catalog read, tenant webhook-info lookup, and system usage-overview paths.
  - The focused Connector-Hub verification now covers not just the existing read-only catalog contract but also the WhatsApp webhook-info bootstrap path and the system usage-overview aggregation path, so this compatibility router is no longer a direct-session outlier.
  - `app.gateway.routers.revenue_analytics` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from revenue overview, monthly breakdown, tenant revenue, token analytics, and Stripe invoice lookup paths.
  - The focused revenue verification exposed another real assembly gap: `/admin/revenue/*` was present in code but no longer mounted in the edge build. `app.edge.registry_setup` now mounts the revenue router explicitly again inside the admin control plane, and the fallback/local-data revenue contract is back to green.
  - `app.gateway.routers.webhooks` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from tenant-slug resolution, tenant plan lookup, campaign-reply DB handoff, and WAHA tenant-integration upsert paths.
  - The existing webhook ingress/security gates stay green after this cleanup, so the most critical inbound compatibility router is no longer carrying direct-session outliers in its core runtime paths.
  - `app.swarm.qa.escalation_router` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the quality-gate handler-config lookup and the dead-letter audit-log write path.
  - A focused escalation-router contract now covers both the configured-handler lookup and the dead-letter audit-log persistence path, so the Swarm QA escalation runtime is no longer a direct-session outlier.
  - `app.core.tenant_context` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the request-scoped DB dependency helper and the slug-to-tenant resolution path.
  - A focused tenant-context contract now covers `resolve_tenant_from_slug()` for active tenants with an attached plan, so this central cross-cutting context helper is no longer a direct-session outlier.
  - `app.core.instrumentation` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the metrics export and campaign-health DB probe paths.
  - A focused instrumentation contract now covers the auth gauge update plus the campaign-health database counters, so this observability cross-cutting helper is no longer a direct-session outlier.
  - `app.integrations.adapters.member_memory_adapter` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the member-history and tenant-slug resolution paths.
  - The focused member-memory adapter contract exposed two real schema-drift bugs in the same slice: the history path was ordering by a non-existent `ChatSession.updated_at` field and formatting a non-existent `ChatMessage.created_at` field. It now uses the real `last_message_at` / `timestamp` schema instead, and the regression contract covers a seeded member-history roundtrip.
  - `app.integrations.adapters.stripe_adapter` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from subscription lookup, invoice listing, and customer creation paths.
  - The focused Stripe adapter contract also flushed out schema drift in the same runtime slice: customer creation no longer assumes a `Tenant.admin_email` attribute exists, and subscription status now falls back to the real `Plan.slug` when no legacy `tier` field exists.
  - `app.memory_platform.notion_service` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from connection lookup, OAuth exchange persistence, disconnect, synced-page reads, sync orchestration, and sync-log reads.
  - A focused Notion-service contract now covers the local DB-backed runtime slice (`get_status`, `get_synced_pages`, `get_sync_logs`, `disconnect`), so this multi-tenant knowledge integration is no longer carrying direct-session persistence in its core state-management paths.
  - `app.contacts.sync_core` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from configured-integrations listing, integration save/delete, sync execution, webhook dispatch, and sync-history paths.
  - This refactor also closed a larger model-drift seam in the same runtime slice: `sync_core` now uses the real `TenantIntegration.config_meta` / `config_encrypted` fields, persists secrets via `CredentialVault.encrypt/decrypt`, derives the UI interval from `SyncSchedule.cron_expression`, and logs history against the actual `SyncLog` schema (`tenant_integration_id`, `sync_type`, `trigger`, `finished_at`, `metadata_json`) instead of the removed legacy fields.
  - A focused Sync-Core contract now covers integration save/list/delete plus sync-history roundtrips against the current schema, so the central contact-sync orchestration path is no longer both a direct-session outlier and a stale-model compatibility risk.
  - `app.memory.member_memory_analyzer` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from memory indexing, tenant-slug resolution, chat summary, Magicline summary, and scheduler tenant discovery.
  - The focused member-memory analyzer contract also closed a compatibility seam in the same runtime slice: chat summary now reads both legacy `ChatMessage.session_id == user_id` rows and current `ChatMessage.session_id == ChatSession.id` rows, so old and new conversation history remain analyzable through one path.
  - `app.contacts.sync_scheduler` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from the advisory-lock, due-integrations, and retry-backoff paths.
  - This refactor also closed the stale-schema assumptions in the same runtime slice: scheduler cadence is now derived from `SyncSchedule.cron_expression` rather than the removed `TenantIntegration.sync_interval_minutes`, and retry backoff now reads `SyncLog` through the real `tenant_integration_id` key instead of the removed `integration_id` field.
  - A focused scheduler contract now covers due-integration selection and consecutive-error counting against the current `SyncSchedule` / `SyncLog` schema, so the automatic contact-sync runtime is no longer carrying direct-session persistence plus stale-model assumptions in its core loop.
  - `app.memory.librarian_v2` now also enters its DB lifecycle through `app.shared.db.open_session`; direct `SessionLocal()` imports and openings have been removed from stale-session scanning and the session-archive writeback path.
  - The focused Librarian contract also closed the same identifier-drift seam already seen in the analyzer: stale-session scans now read both legacy `ChatMessage.session_id == ChatSession.user_id` rows and current `ChatMessage.session_id == ChatSession.id` rows, and the archival writeback now deactivates sessions by the real `ChatSession.id` whenever it is available.
  - The final Epic-6.1 cleanup sweep moved the remaining runtime rest cluster onto `app.shared.db.open_session`, including knowledge ingestion, core auth bootstrap/context helpers, AI gateway cost/logging paths, sync-health reporting, legacy contact import/export, admin shared helpers, ingestion workers, member-memory tooling, and the last Swarm/voice/maintenance/router call sites that were still opening ad-hoc sessions.
  - The same sweep also removed the last stale-schema assumptions still sitting in the contact-sync health path: display names now resolve through `TenantIntegration.integration`, stale-sync thresholds derive from `SyncSchedule.cron_expression`, and error history reads `SyncLog` through the real `tenant_integration_id` key.
  - With that sweep complete, Epic 6.1 is now closed in practical code terms: outside of the intentional DB-layer files (`app.shared.db`, `app.core.db`) there are no remaining product-runtime `SessionLocal()` call sites in `app/`.
  - Epic 6.2 has now started with a strict architecture guardrail instead of another soft baseline: `tests/architecture/test_guardrails.py` fails if any file in `app/` outside `app.core.db` and `app.shared.db` references `SessionLocal`, locking in the Epic-6.1 end state before repository/UoW extraction begins.
  - The first Epic-6.2 inventory pass is now concrete enough to drive 6.3 by cluster instead of intuition:
    - `get_db()` is concentrated in sync FastAPI CRUD routers such as `platform/api/integrations.py` and the gateway router cluster (`automations`, `campaigns`, `media`, `public_subscribe`, `consent`, `agent_teams`, `orchestrators`).
    - `open_session()` is concentrated in compatibility-heavy router/integration surfaces, especially billing (`billing/router.py`, `billing/admin_router.py`, `gateway/routers/billing.py`), platform APIs, swarm-admin, and integration/service adapters.
    - `session_scope()` and `transaction_scope()` are already concentrated in the strongest application-layer candidates: `gateway/auth.py`, `gateway/persistence.py`, `contacts/service.py`, and the admin services.
  - That inventory has now been converted into the first real 6.3 extraction step in `contacts/service.py`: aggregate statistics, export-contact reads, and tag lookup/count reads moved into `contacts/repository.py`, so the active contacts core now has an explicit repository boundary for its first remaining read-model cluster instead of inline ORM orchestration.
  - The same contacts slice also exposed and fixed a live runtime defect while adding the new regression contract: `export_contacts_v2()` used `io`/`csv` without importing them in the active runtime path. The export path is now hardened and covered by focused service-level tests for both statistics and export output.
  - The next 6.3 slice is now in `gateway/auth.py`: repeated user/tenant/invitation lookups and scoped list queries moved into a focused `gateway/auth_repository.py`, while login/register/MFA/invitation security orchestration deliberately stayed in `auth.py`. That keeps the repository boundary narrow and behavior-preserving instead of turning the auth module into a second monolith under a new filename.
  - The next 6.3 slice is now also in `gateway/persistence.py`: settings and tenant-resolution lookups moved into `gateway/persistence_repository.py`, which makes the compatibility persistence facade explicit about what is repository access versus what is still orchestration. The critical semantic edge was preserved deliberately: system-governed settings such as `billing_default_provider` remain globally keyed rows, while legacy tenant-scoped unprefixed rows still resolve through an explicit fallback path for backward compatibility.
  - That persistence extraction also flushed out a real drift between `staging` and the effective `production` import path. The same repository contract is now mirrored in both trees, and the regression gate proves that tenant-isolated settings, system-scoped billing defaults, persistence tenant-scope helpers, and connector-hub read-only catalog/webhook-info flows still behave correctly after the extraction.
  - The next persistence slice now pushes the same repository boundary deeper into chat/session state: counts, recent-session reads, session lookups, chat-history reads, reset/link writes, and the create-or-update session primitives now live in `gateway/persistence_repository.py` instead of being rebuilt inline in `gateway/persistence.py`.
  - That step also removes a real structural smell from the compatibility layer: `save_message()` no longer opens one persistence session and then re-enters the database through separate `get_or_create_session()`/lookup calls on fresh sessions. The message write path now operates against a single session boundary for the whole persist operation, which is closer to the intended 6.3 UoW direction and reduces detached-state risk in a hot runtime path.
  - The focused persistence regression gate now covers tenant-scoped chat history, recent sessions, stats, reset behavior, system-scoped settings, and tenant-scoped settings together, so the persistence extraction is no longer relying on only indirect module tests to validate its chat/session compatibility contract.
  - The next 6.3 slice now leaves the compatibility layer and enters the active billing admin service: `gateway/services/admin_billing_platform_service.py` no longer performs its own plan-list and subscription/plan lookup queries inline. Those reads now live in `gateway/admin_billing_repository.py`, which gives the billing admin surface its first explicit repository boundary instead of mixing DB query shape with API payload shape in one service.
  - The corresponding regression gate proves both the route-level connector masking/predefined-provider behavior and the tenant-scoped billing-subscription view still hold after the extraction, so this is a real repository cut with runtime coverage rather than a purely internal reorganization.
  - The next 6.3 slice now moves into the active Stripe orchestration core: `billing/stripe_service.py` no longer inlines its recurring subscription/customer/plan/addon/invoice lookup queries. Those reads now live in `billing/stripe_repository.py`, which gives the Stripe service an explicit data-access boundary while leaving all external Stripe API orchestration in place.
  - The focused Stripe-service contract covers the three highest-value repository-backed paths in that service: persisting a newly created customer ID back into the tenant subscription, resolving checkout plan pricing through the repository-backed active-plan lookup, and upserting local invoice cache rows without regressing the `billing_invoices.status` NOT NULL contract. That last issue surfaced immediately during the extraction and is now fixed by keeping invoice creation and field population inside the same service transaction instead of flushing too early.
  - The next 6.3 slice now moves into the analytics control plane: `gateway/services/admin_analytics_service.py` no longer carries its main read-model queries inline. Assistant-message windows, member-feedback summary reads, recent-session loads, and audit-log pagination now live in `gateway/admin_analytics_repository.py`.
  - That analytics extraction also removes a real runtime smell rather than only rearranging code: `analytics/sessions/recent` no longer performs an N+1 query loop over sessions for latest assistant message, latest user message, and message counts. The service now loads the recent session set once and hydrates it from a single repository-backed message batch, while preserving the existing output contract and legacy-audit-details parsing behavior.
  - The next 6.3 slice now moves into the admin operations service: `gateway/services/admin_operations_service.py` no longer carries its member- and operations-read queries inline. Member stats, member/chat aggregation, enrichment stats, bulk-enrichment candidate IDs, and member-link search now live in `gateway/admin_operations_repository.py`.
  - That operations extraction preserves the operational orchestration in the service layer while removing a sizeable query block from it. The new contract proves that tenant-scoped member stats, member listing with chat aggregation, chat token hydration, and the tenant-admin/system-admin boundary still hold after the extraction, so this is again a real repository cut rather than a pure file split.
  - The next 6.3 slice now also covers the tenant self-service portal: `platform/api/tenant_portal.py` no longer mixes overview, usage, audit, and tenant-config query shape inline with response mapping. Those reads and writes now live in `platform/api/tenant_portal_repository.py`, which gives the self-service surface an explicit repository boundary instead of another ad-hoc compatibility-style DB access layer.
  - That tenant-portal extraction also preserves the already repaired compatibility behavior around legacy audit payloads and tenant-local config reads while making the route contracts easier to regression-test in isolation.
  - The next 6.3 slice now moves into the integration marketplace self-service surface: `platform/api/marketplace.py` no longer carries its main catalog, integration-detail, capability, tenant-plan, and tenant-integration lookups inline. Those reads now live in `platform/api/marketplace_repository.py`, which gives the marketplace the same explicit repository boundary we already introduced in the stronger admin and billing paths.
  - That marketplace extraction flushed out several real runtime drifts rather than only rearranging queries: the active registry path now uses string integration/capability IDs, resolves capabilities through the real `IntegrationCapability` link table, persists tenant-side config through `TenantIntegration.config_meta`, and writes audits through `AuditLog.details_json` instead of the stale legacy fields. The focused contract now proves both the fallback catalog path and a real DB-backed registry detail/capability flow.
  - The next 6.3 slice now also covers the integration-registry CRUD surface itself: `platform/api/integrations.py` no longer mixes repeated `select(...)` blocks for definitions, capability links, capabilities, and tenant-integrations inline with HTTP concerns. Those reads and create/look-up primitives now live in `platform/api/integrations_repository.py`, giving the registry API the same repository boundary as the adjacent marketplace routes.
  - That registry extraction keeps the FastAPI router as a thin HTTP adapter and centralizes output hydration through shared builders, so integration/capability link lookups and tenant-integration response mapping are no longer duplicated across multiple endpoints. The focused tenant-integration contract is green, and the relevant Phase-2 router endpoint assertions are still green; the remaining broad `tests/test_phase2_refactoring.py` collector error is pre-existing ballast from the file's custom `test(...)` helper, not a regression from this slice.
  - The next 6.3 slice now goes back into the active billing admin surface: `billing/admin_router.py` no longer carries several of its larger read-only plan, subscriber, public catalog, and V2 catalog queries inline. Those reads now reuse the existing `gateway/admin_billing_repository.py` boundary instead of duplicating another pocket of plan/subscription/addon ORM code inside the router.
  - That billing-admin extraction is intentionally read-focused: write-heavy Stripe sync, create/update/delete, and feature-entitlement mutation paths stay in place for now, while the route-level read contracts (`/admin/plans/public`, `/admin/plans/subscribers`, `/admin/plans/v2/plans`, `/admin/plans/v2/addons`) remain green. During the pass it also became explicit that `platform/api/public_api.py` is not a useful 6.3 target yet because it currently contains no real DB query layer to extract.
  - The next 6.3 slice now moves into the subscription lifecycle core: `billing/subscription_service.py` no longer inlines its repeated subscription, active-plan, current-plan, and pending-change lookups. Those reads now live in `billing/subscription_repository.py`, which gives the billing lifecycle service an explicit repository boundary alongside the Stripe and admin billing services.
  - That subscription extraction stays intentionally surgical: creation, upgrade/downgrade, cancellation, Stripe sync, and event emission remain in the service, while the read-side lookup and due-change query logic are centralized. The focused service contract for create/upgrade and scheduled-change application is green, so this is again a real repository cut rather than just moving helpers around.
  - The next 6.3 slice now also covers the Stripe webhook core: `billing/webhook_processor.py` no longer carries its repeated customer-to-tenant, subscription, invoice-record, and tenant-addon lookups inline. Those reads and the local invoice upsert primitive now live in `billing/webhook_repository.py`, which gives the inbound webhook processor the same explicit data-access boundary as the adjacent billing lifecycle services.
  - That webhook extraction surfaced and closed a real compatibility gap in the legacy public billing catalog: `gateway/routers/billing.py` now derives a stable fallback feature list from real plan limits/toggles when `features_json` is empty, so the public `/admin/billing/plans` contract no longer depends on every test/runtime plan row being perfectly curated. The focused webhook processor contract and the broader billing webhook regression gate are green together.
  - The next 6.3 slice now also trims the active Billing-V2 API router itself: `billing/router.py` no longer performs its pending-plan, current-plan, target-plan, tenant, and session-verification subscription lookups inline. Those reads now reuse the existing `billing/subscription_repository.py` and `billing/stripe_repository.py` boundaries, so the router is closer to a thin HTTP adapter instead of being another pocket of ORM query shape.
  - That router extraction is intentionally incremental rather than inventing a second billing service layer: write-heavy Stripe operations, billing-event emission, and account lifecycle orchestration remain where they are, while the focused subscription-status contract now proves the pending-downgrade response path against the repository-backed reads.
  - The next 6.3 slice now also covers the billing gating core: `billing/gating_service.py` no longer carries its subscription, plan, feature, entitlement, addon-definition, public-plan, and usage-record reads inline. Those queries now live in `billing/gating_repository.py`, which gives the feature-gating/service-comparison core the same explicit read-model boundary as the adjacent billing services.
  - That gating extraction keeps the merge/orchestration logic where it belongs while deleting the distributed ORM query shape from the service itself. The focused contract now proves the three important behaviors directly against the repository-backed service: public plan comparison, additive addon limit merging, and current-period metered usage limit evaluation.
  - The next 6.3 slice now also covers the billing metering core: `billing/metering_service.py` no longer performs its usage-record CRUD and feature lookup shape inline. Those operations now live in `billing/metering_repository.py`, while plan/feature/limit resolution is reused through the existing `billing/gating_repository.py`.
  - That metering extraction removes another duplicated query pocket from the billing core and fixes a real structural inefficiency at the same time: `get_all_usage()` no longer queries `Feature` once per usage row, but hydrates feature names through a single keyed load. The focused metering contract is green for hard-limit enforcement and usage-summary hydration.
  - The combined billing verification gate (`billing_v2_router`, `billing_webhook`, multitenant subscription/usage isolation) is green, so the persistence refactor now has stable coverage on both legacy and V2 billing surfaces.
  - Epic 6.4 has now started outside the billing cluster with the first knowledge hotpath: `knowledge/ingest.py` no longer performs tenant resolution and active-tenant listing inline. Those reads now live in `knowledge/ingest_repository.py`, so the ingestion entrypoint stops mixing filesystem/chunking work with ad-hoc tenant ORM access.
  - That first 6.4 step is intentionally narrow but useful: the direct contract now proves tenant-slug resolution for tenant-specific ingestion and the active-tenant filter for `ingest_all_tenants()`, which gives the Knowledge slice its first explicit repository boundary before larger campaign/support hotpaths are touched.
  - The next 6.4 step now moves into the active integrations admin surface: `gateway/routers/connector_hub.py` no longer mixes tenant lookup, tenant listing, and tenant-scoped Setting reads inline with HTTP/config/probe logic. Those DB reads now live in `gateway/connector_hub_repository.py`, giving the connector hub the same explicit repository boundary pattern already used in the stronger billing and platform surfaces.
  - That connector-hub extraction is deliberately read-focused: external SMTP/Postmark/Calendly/Stripe/PayPal/Telegram probe logic and persistence writes remain in the router for now, while the catalog/webhook-info/system-usage DB access is centralized. Compile plus the catalog and webhook-info contracts are green; the existing `system/usage-overview` test path is still unusually slow in this environment and should be re-run in the next broader verification sweep instead of being hand-waved.
  - The next 6.4 step now also trims the gateway-side phone matching helper: `gateway/member_matching.py` no longer queries `StudioMember` inline. That member listing now lives in `gateway/member_matching_repository.py`, so the matching helper keeps only normalization/candidate logic while the DB read boundary becomes explicit.
  - That phone-matching extraction is intentionally tiny but useful because it sits on a live ingress path via webhook/member lookup flows. The direct contract is green for unique match, ambiguous match, and tenant scoping, so this is another small but real step toward clearing the remaining gateway edge read pockets before the broader 6.4 verification pass.
  - The next 6.4 step now also trims the contact-sync edge router: `gateway/routers/contact_sync_api.py` no longer mixes integration toggle writes, sync-stat reads, and webhook tenant resolution inline with HTTP concerns. Those DB paths now live in `gateway/contact_sync_repository.py`, so the router keeps only transport-level behavior while the DB access boundary becomes explicit.
  - That contact-sync extraction is deliberately narrow and runtime-focused: only the compatibility DB pockets were moved, while `sync_core` and health/scheduler orchestration stay where they belong. The code compiles cleanly and the existing router suite has been extended with a tenant-scoped `/sync/stats` contract, but the full `tests/test_contact_sync_api_router.py` run is currently unusually slow/hanging in this environment and should be re-run in the next broader verification sweep instead of being overstated.
  - The next 6.4 step now also trims the voice ingress edge router: `gateway/routers/voice.py` no longer resolves tenant slugs through direct model/session access inline. That active-tenant lookup now lives in `gateway/voice_repository.py`, leaving the router with only Twilio transport behavior and per-tenant setting resolution.
  - This voice extraction is intentionally tiny but useful because it sits on a live inbound path and deletes another direct ORM read from the gateway edge. The focused contract covers tenant-specific configured stream URLs plus the forwarded-host fallback path for active vs inactive tenants; the code compiles cleanly, but the dedicated pytest file is currently showing the same unusually slow/hanging behavior in this environment as the recent contact-sync router suite and should be re-run in the next broader verification sweep.
  - The next 6.4 step now also trims the shared admin helper module: `gateway/admin_shared.py` no longer resolves target tenants or writes audit rows through direct inline DB access. Those pockets now live in `gateway/admin_shared_repository.py`, which gives the shared admin utility layer the same explicit repository boundary already introduced across the stronger router and service slices.
  - This `admin_shared` extraction is deliberately small but structurally useful because that module is imported by multiple admin routers and services. The code compiles cleanly and a focused contract now exists for system-admin tenant resolution plus impersonation-aware audit writes, but the dedicated pytest file currently hangs in this environment as well; even a `timeout 20s` run exits with `124`, so this verification remains explicitly open for the next broader sweep instead of being overstated.
  - The next 6.4 step now also trims the campaign-offers admin router: `gateway/routers/campaign_offers.py` no longer mixes tenant-scoped list, duplicate lookup, object lookup, and create/delete DB access inline with HTTP concerns. Those CRUD reads now live in `gateway/campaign_offers_repository.py`, keeping the router focused on payload mapping and validation.
  - This `campaign_offers` extraction is another intentionally small live-surface cut because the router is mounted in the edge build and sits on the active admin campaign path. The code compiles cleanly and a focused router contract now exists for create/list plus duplicate/update behavior, but that dedicated pytest file also hangs in this environment; even `timeout 20s pytest tests/test_campaign_offers_router.py -q` exits with `124`, so the verification remains explicitly open for the broader sweep.
  - The next 6.4 step now also trims the campaign-templates admin router: `gateway/routers/campaign_templates.py` no longer mixes active-template list/default reads, object lookup, and default-reset writes inline with HTTP concerns. Those tenant-scoped CRUD reads now live in `gateway/campaign_templates_repository.py`, leaving the router focused on payload mapping, validation, and lifecycle logging.
  - This `campaign_templates` extraction intentionally closes another active Campaign admin edge slice right next to the already extracted offers router. The code compiles cleanly and a focused router contract now exists for create/list plus duplicate/default-by-type behavior, but that dedicated pytest file also hangs in this environment; `timeout 20s pytest tests/test_campaign_templates_router.py -q` exits with `124`, so this verification remains explicitly open for the broader bundled sweep.
  - The next 6.4 step now also trims the active support-side agent-team router: `gateway/routers/agent_teams.py` no longer mixes system-admin list, duplicate lookup, object lookup, and state/delete DB access inline with HTTP concerns. Those CRUD reads now live in `gateway/agent_teams_repository.py`, leaving the router focused on payload mapping, validation, and role enforcement.
  - The 6.4 closeout gate is now fully green. The earlier timeout diagnosis turned out to be a mix of real regressions plus an overly tight timeout window on a heavy pytest bootstrap. The remaining schema/runtime drifts were fixed directly: `contact_sync_api` now uses `tenant_integration_id` plus a safe `display_name` fallback, `gateway.main` mounts the legacy Voice ingress compatibility path explicitly again, `agent_teams` now uses the real `AgentTeam.status` field instead of the dead `state` attribute, and `connector_hub` system usage aggregation now batches enabled-connector reads through `gateway/connector_hub_repository.py` instead of doing N×M `persistence.get_setting(...)` calls across every tenant/connector pair.
  - The resulting bundled verification now completes successfully: `pytest tests/test_knowledge_ingest_contract.py tests/test_connector_hub_catalog.py tests/test_member_matching_contract.py tests/test_contact_sync_api_router.py tests/test_voice_router_contract.py tests/test_admin_shared_contract.py tests/test_campaign_offers_router.py tests/test_campaign_templates_router.py tests/test_agent_teams_router.py -q` finishes with `21 passed` in about 41 seconds.
  - Epic 7 is now formally started with the ownership cut-off for `app/core/models.py`. The new `refactoring_ddmm/model_ownership_map.md` defines the target ownership for Tenant/Identity, Support/CRM, Billing, Campaigns, Knowledge, AI/Swarm configuration, and Platform/Settings models before any physical file split happens.
  - That mapping intentionally freezes the order of operations for `7.2`: Tenant/Identity first, then Billing, Campaigns, Support/CRM, Knowledge, AI/Swarm, and finally Platform/Settings. It also names the first real `7.3` cross-domain hotspots, so the next work no longer needs to rediscover the migration shape from scratch.
  - Epic 7.2 has now started physically with the first compatible ownership cut: `Tenant`, `UserAccount`, `AuditLog`, `PendingInvitation`, `RefreshToken`, and `UserSession` live in `app.domains.identity.models`, while `app.core.models` remains a compatibility re-export shim for the legacy import surface.
  - The first model split is intentionally behavior-neutral: table names, SQLAlchemy metadata registration, and legacy imports remain stable, and `tests/test_identity_models_shim.py` protects both the re-export contract and the unchanged table mapping.
  - The second physical ownership cut now moves the Billing/Entitlements/AI-cost cluster into `app.domains.billing.models`: `Plan`, `AddonDefinition`, `TenantAddon`, `Subscription`, `UsageRecord`, `TokenPurchase`, `ImageCredit*`, `LLMModelCost`, and `LLMUsageLog` no longer live physically in `app.core.models`.
  - `app.core.models` remains the compatibility shim for those billing models as well, and `tests/test_billing_models_shim.py` now protects the re-export identity plus the unchanged legacy table names.
  - The next physical ownership cut now moves the Campaign domain cluster into `app.domains.campaigns.models`: `Campaign`, `CampaignTemplate`, `CampaignVariant`, `CampaignRecipient`, and `CampaignOffer` no longer live physically in `app.core.models`.
  - `app.core.models` remains the compatibility shim for those campaign models as well, and `tests/test_campaign_models_shim.py` protects the re-export identity plus the unchanged legacy table names.
  - The next physical ownership cut now also moves the Support/CRM cluster into `app.domains.support.models`: `ChatSession`, `ChatMessage`, `StudioMember`, `MemberCustomColumn`, `MemberImportLog`, `MemberSegment`, `ScheduledFollowUp`, `MemberFeedback`, and `ContactConsent` no longer live physically in `app.core.models`.
  - `app.core.models` remains the compatibility shim for those support models as well, and `tests/test_support_models_shim.py` protects the re-export identity plus the unchanged legacy table names.
  - Epic 7.2 is now physically complete: `app.core.models` has been reduced to a compatibility shim, and the remaining Knowledge/AI/Platform ownership was cut into `app.domains.knowledge.models`, `app.domains.ai.models`, and `app.domains.platform.models`.
  - The shim contract is now covered end-to-end by focused tests for identity, billing, campaigns, support, knowledge, ai/swarm, and platform/settings, so the remaining Epic-7 work can move to cross-domain reads and import-boundary cleanup instead of further physical model moves.
  - Epic 7.3 has now started in the platform self-service slice: `platform/api/tenant_portal_repository.py` and `platform/api/marketplace_repository.py` no longer formulate cross-domain Identity/Billing/Support reads inline against foreign models. They now depend on explicit domain query services in `app.domains.identity.queries`, `app.domains.billing.queries`, `app.domains.support.queries`, and `app.domains.platform.queries`.
  - Epic 7.3 now also covers the active media quota path: `app.media.service` no longer reads plan limits and current monthly usage by importing Billing entities from `app.core.models`. Those reads now go through `app.domains.billing.queries`, keeping Media focused on quota orchestration while Billing owns the foreign read model.
  - Epic 7.3 now also trims the media credit path: `app.media.credit_service` resolves image-credit balance and monthly plan grants through `app.domains.billing.queries` instead of reading Billing entities through the `app.core.models` shim. The remaining balance/transaction mutations now at least target `app.domains.billing.models` directly, reducing shim dependence on the active media billing path even further.
  - Epic 7.3 now also reaches the active HTTP media surface: `gateway/routers/media.py` no longer resolves tenants and credit-plan reads through `app.core.models`. Tenant lookup now goes through `app.domains.identity.queries`, monthly grant resolution through `app.domains.billing.queries`, and the active-campaign asset protection through `app.domains.campaigns.queries`. The remaining `ImageCreditPack` read is now at least a direct Billing-domain import instead of a shim import.
  - Epic 7.3 now also reaches the public opt-in surface: `gateway/routers/public_subscribe.py` no longer resolves active tenants and campaign/offer context by importing foreign entities from `app.core.models`. Those reads now go through `app.domains.identity.queries` and `app.domains.campaigns.queries`, while the write side keeps direct domain-model references for consent and recipient creation.
  - Epic 7.3 now also removes shim usage from the smaller active support/campaign gateway paths. `gateway/routers/feedback.py`, `gateway/routers/campaign_webhooks.py`, and `gateway/routers/analytics_api.py` now import their own domain models directly instead of depending on `app.core.models` for support/campaign-owned entities.
  - Epic 7.3 now also clears a broad gateway repository/service batch: auth, persistence, connector hub, contact sync, admin analytics, admin operations, admin billing, admin shared, member matching, agent teams, and campaign template slices now import their already-owned domain models directly instead of routing through `app.core.models`.
  - The architectural guardrail was tightened accordingly: `tests/architecture/test_guardrails.py` now uses the reduced `app.core.models` import baseline of `117` instead of `158`, so the cleanup is enforced instead of merely described.
  - The next active API batch is now also off the shim: `platform/api/tenant_portal.py`, `platform/api/analytics.py`, `platform/api/marketplace.py`, and `billing/router.py` now use direct Identity/Support domain imports, and `tenant_portal`'s audit writes/reads were aligned with the real `AuditLog` field names during the move.
  - The next active Campaign/Worker batch is now also off the shim: `worker/campaign_tasks.py`, `campaign_engine/ab_testing.py`, `campaign_engine/analytics_processor.py`, `campaign_engine/reply_handler.py`, `campaign_engine/renderer.py`, and `campaign_engine/node_executors.py` now import their Campaign/Support/Identity domain models directly instead of routing through `app.core.models`.
  - That batch keeps the active campaign runtime aligned with the ownership split: send-batch, scheduler, analytics aggregation, A/B evaluation, opt-in reply handling, rendering, and automation-triggered campaign creation no longer depend on the compatibility shim for their owned entities.
  - The next Core/Gateway/Swarm/Billing hotpath batch is now also off the shim: `core/feature_gates.py`, `gateway/auth.py`, `swarm/registry/dynamic_loader.py`, `integrations/adapters/stripe_adapter.py`, and `ai_config/observability.py` now import Billing/Identity/AI domain models directly instead of routing through `app.core.models`.
  - That batch removes shim-dependence from plan/capability evaluation, registration/login/invitations, tenant agent/tool loading, Stripe subscription/customer status reads, and AI usage/budget observability, which are all active runtime-critical cross-cutting paths rather than edge leftovers.
  - The next active Gateway/Core/Swarm edge batch is now also off the shim: `gateway/routers/billing.py`, `gateway/routers/webhooks.py`, `gateway/routers/campaigns.py`, `ai_config/gateway.py`, `core/instrumentation.py`, `core/tenant_context.py`, and `swarm/agents/campaign/orchestrator.py` now use direct domain imports for their owned Billing/Identity/Campaign/Support entities.
  - That second batch keeps inbound webhooks, public billing compatibility, campaign admin flows, AI gateway cost logging, metrics/health probes, tenant resolution, and the campaign swarm orchestrator aligned with the ownership split instead of continuing to lean on the compatibility shim.
  - The architectural guardrail was tightened again accordingly: `tests/architecture/test_guardrails.py` now uses the reduced `app.core.models` import baseline of `57`, down from `101`, after the combined core/gateway/swarm cleanup.
  - The next Seed/Memory/Orchestration rest cluster is now also off the shim: `platform/seed.py`, `orchestration/team_seed.py`, `billing/credit_seed.py`, `memory/librarian_v2.py`, `worker/ingestion_tasks.py`, `swarm/tools/member_memory.py`, `integrations/adapters/member_memory_adapter.py`, `orchestration/service.py`, and `orchestration/runtime.py` now import their owned domain models directly instead of routing through `app.core.models`.
  - That batch also hardened a real runtime edge case in `memory/librarian_v2.py`: stale-session scanning is now deterministically ordered for batch selection, which keeps the legacy/current session-identifier archival contract stable even in a test database with many pre-existing stale sessions.
  - The architectural guardrail was tightened again accordingly: `tests/architecture/test_guardrails.py` now uses the reduced `app.core.models` import baseline of `41`, down from `57`, after the seed/memory/orchestration cleanup.
  - The next Gateway/Core/Billing rest cluster is now also off the shim: `gateway/persistence.py`, `core/auth.py`, `ai_config/service.py`, `billing/admin_router.py`, `billing/stripe_repository.py`, `core/billing_sync.py`, `gateway/services/admin_core_settings_service.py`, `billing/webhook_processor.py`, `gateway/routers/ab_testing_api.py`, `gateway/routers/member_memory_admin.py`, `gateway/routers/chats.py`, `gateway/routers/llm_costs.py`, `gateway/routers/permissions.py`, `gateway/routers/members_crud.py`, `gateway/routers/revenue_analytics.py`, `gateway/routers/swarm_admin.py`, `knowledge/ingest_repository.py`, `gateway/member_matching.py`, `gateway/voice_repository.py`, `gateway/campaign_offers_repository.py`, and `core/contact_models.py` now import their owned domain models directly instead of routing through `app.core.models`.
  - That batch was verified against the active contracts for auth, persistence, matching, voice, campaign offers, billing admin/webhooks, member feedback, llm costs, core settings, members CRUD, revenue analytics, and swarm admin, which all stayed green through the import-boundary move.
  - The architectural guardrail was tightened again accordingly: `tests/architecture/test_guardrails.py` now uses the reduced `app.core.models` import baseline of `20`, down from `41`, after the gateway/core/billing cleanup.
  - The final Memory/Gateway/Swarm/Integrations rest cluster is now also off the shim: `memory/librarian.py`, `memory/member_memory_analyzer.py`, `core/maintenance.py`, `swarm/agents/ops.py`, `swarm/tools/dynamic_tool.py`, `swarm/lead/lead_agent.py`, `swarm/registry/seed.py`, `swarm/qa/escalation_router.py`, `swarm/agents/media/prompt_agent.py`, `integrations/shopify/members_sync.py`, `integrations/magicline/member_enrichment.py`, `integrations/magicline/members_sync.py`, `integrations/magicline/scheduler.py`, `integrations/adapters/email_adapter.py`, `integrations/adapters/knowledge_adapter.py`, `gateway/routers/analytics_tracking.py`, `gateway/routers/consent.py`, `gateway/routers/campaign_offers.py`, `gateway/routers/agent_teams.py`, and `gateway/routers/campaign_templates.py` now import their owned domain models directly instead of routing through `app.core.models`.
  - That final batch stayed green against the focused contracts for member-memory analysis, escalation routing, campaign offers/templates, agent teams, and member feedback, which means the productive runtime no longer depends on `app.core.models` for domain ownership.
  - The architectural guardrail is now at its target end state: `tests/architecture/test_guardrails.py` uses a baseline of `0` productive `app.core.models` imports in `app/`, making the shim a pure compatibility layer rather than an active dependency surface.
  - The temporary service-local `_db_session` helpers introduced during the first cleanup pass have been deleted again, so the persistence refactor is converging toward a real shared layer instead of reintroducing local duplication.
  - With `app.contacts.service`, the legacy billing compatibility router, the Billing-V2 router, the Billing-V2 admin router, the core platform API routers (`marketplace`, `tenant_portal`, `analytics`), `app.core.feature_gates`, the Swarm admin surface, the main campaign worker, the legacy members CRUD router, the LLM-cost analytics router, and the central swarm dynamic loader off direct sessions, Epic 6 has cleared the largest central web/runtime persistence hotspots and can now focus on the next repo-wide cluster instead of more local hotfixes.
  - This reduces shared-session coupling in the hottest compatibility layer and gives Epic 6 a stable base for the next extraction step toward reusable session/UoW helpers and repository boundaries.
- Epic 3 is complete. Epic 4 is complete. Epic 5 is complete. Epic 6 is complete. Epic 7 is in progress.

## Remaining Execution Plan

### Epic 8 — Active Product Core Migration
- `support` must become the first-class runtime core rather than a spread of gateway, contacts, memory, and webhook slices.
- `campaigns` must be consolidated around the real product flow: opt-in, template, send, reply, analytics, and offer surfaces belong together and need one explicit application boundary.
- `knowledge` must be treated as its own product module with clear ownership for ingestion, storage, indexing, and admin surfaces.
- Integrations that are part of the active core (`WhatsApp`, `Telegram`, `Calendly`, `Magicline`) must be decoupled from gateway fallback code behind stable module interfaces and corruption layers.
- `tenant_management` must be reduced to entitlement/capability management and no longer own unrelated SaaS or admin behavior.
- Verification target:
  - core support, campaign, knowledge, and active integrations run E2E through the edge build,
  - each active module has a single clear runtime entrypoint,
  - cross-module interaction happens through explicit services/events rather than opportunistic imports.
  - Epic 8 has now started with the first two concrete module-assembly cuts: `app.domains.support.module` owns the support-core router surface, and `app.domains.campaigns.module` owns the active campaign/opt-in/tracking surface.
  - The support cut removes edge-level knowledge of individual support routers and explicitly pulls the DSGVO consent surface into the active support core instead of leaving it as an orphaned router.
  - The campaigns cut removes edge-level knowledge of individual campaign routers and makes the public opt-in/tracking path (`public_subscribe`, campaign webhooks, analytics tracking, templates, offers, core campaigns) part of one domain-owned assembly instead of a partially assembled runtime.
  - Epic 8 now also covers the next two active runtime cuts: `app.domains.knowledge.module` owns the knowledge-base assembly for ingestion plus media, and `app.domains.platform.module` owns the tenant-management assembly for portal, marketplace, billing-v2, admin plans, platform analytics, LLM-costs, and tenant AI configuration.
  - The integrations runtime now has an explicit domain-owned assembly as well: `app.domains.integrations.module` owns the active Magicline and WhatsApp entrypoints, and the module contract now asserts real webhook paths rather than a fabricated router prefix.

### Epic 9 — Worker Runtime Separation
- Introduce `worker_runtime/main.py` as the dedicated worker boot path with capability-aware registration.
- Remove campaign, ingestion, sync, and related background jobs from API process startup.
- Standardize idempotency, retry, DLQ, and failure-reporting semantics across worker modules.
- Make container/runtime separation real:
  - API runtime owns HTTP and lightweight orchestration only.
  - Worker runtime owns long-running jobs, scheduled jobs, and async retries.
- Verification target:
  - API and worker boot independently,
  - capability-disabled workers do not start,
  - failure handling is contract-tested instead of best-effort.
  - The first real separation step is now in place: `app.worker_runtime.main` discovers active worker targets through the module registry instead of a hardcoded worker map.
  - The Campaign and Knowledge domain assemblies now expose explicit worker definitions via `get_workers()`, so those modules own both their HTTP and worker boot entrypoints.
  - `app.worker.main` is reduced to a compatibility shim onto the new runtime, which preserves existing operational entrypoints while making the new separation path explicit and testable.
  - The next real runtime cut is now in place as well: the formerly implicit long-running support and integration loops are modeled as explicit worker-runtime targets. `support_core` now exposes `contact-sync-scheduler` and `member-memory-scheduler`, while `integration_magicline` exposes `magicline-sync-scheduler`.
  - `app.worker_runtime.main` now supports both lazy ARQ targets and lazy async loop targets, so worker discovery remains testable without queue dependencies and the API no longer needs to be the conceptual home of those long-running schedulers.
  - The worker-runtime state is now visible through the edge health surface as well: `/health/workers` resolves the active worker footprint from the registry and reports real worker entries instead of the previous `pending_epic_9` stub. That makes the API/worker split observable and contract-testable rather than implicit.
  - The first standardized failure semantics are now in place for the new async worker-runtime targets: `app.worker_runtime.loop_supervisor` applies shared restart behavior with exponential backoff, while `app.worker_runtime.runtime_state` tracks restart count, failure count, last error, and lifecycle timestamps.
  - That shared state now feeds `/health/workers`, so the async scheduler workers are no longer opaque loops; they expose a common operational contract for degraded/running/stopped state even before the deeper ARQ/DLQ standardization is finished.

### Epic 10 — Dormant / Coming Soon Strategy
- Convert non-core features to explicit dormant modules instead of leaving half-mounted legacy surfaces around.
- Ensure frontend navigation and route states are final and consistent: `available`, `upgrade`, `coming_soon`, `hidden`.
- Generate a concrete sunset backlog from dormant code so Epic 11 removal work is based on an audited inventory rather than intuition.
- Verification target:
  - dormant routes are not booted server-side,
  - dormant workers are not registered,
  - frontend contract tests and RBAC route-access tests stay green.
  - The first concrete dormant-runtime leak is now closed: `app.gateway.main` no longer mounts the legacy Voice router unless the `voice_pipeline` module is actually active, so dormant Voice is not silently reintroduced through the compatibility layer.
  - The tenant-facing dormant UI contract is now tighter as well: Sidebar quick actions use the same route-access filtering as the main nav, and the route-access contract explicitly covers dormant `system-prompt` and branding settings routes in addition to analytics, member-memory, and automations.
  - The sunset backlog now exists as an explicit artifact in `refactoring_ddmm/dormant_sunset_backlog.md`, which inventories the current dormant capabilities and names the concrete Epic-11 delete-or-replace candidates instead of leaving that future cleanup implicit.

### Epic 11 — Legacy Code Identification & Replacement Strategy
- Build a complete, usage-aware legacy inventory: active runtime paths, compat shims, dead code, and hybrid surfaces.
- Define replacement targets with explicit target architecture and migration seams.
- Use strangler-style parallel implementations behind adapters, feature flags, or routing cutovers.
- Prove functional equivalence with regression, contract, integration, and targeted load tests before deleting old code.
- Remove legacy implementations only when all productive dependencies have been cut and verified.
- Finish with migration documentation that records architecture decisions, compatibility tradeoffs, and cleanup results.
  - The first execution artifact now exists: `refactoring_ddmm/legacy_inventory.md` classifies the remaining compatibility entrypoints, hybrid adapters, and dormant delete candidates by runtime role, usage, and migration strategy.
  - A new architecture guardrail prevents silent spread of new compatibility shims by restricting top-level `compatibility shim` / `compatibility wrapper` files to the approved entrypoint allowlist.
  - `refactoring_ddmm/legacy_replacement_strategy.md` now defines the initial replacement seams and target architecture for the highest-value legacy entrypoints.
  - `app.gateway.main.apply_legacy_compat_routes(...)` is now the first concrete strangler seam. The verified current hard cutover is `/ws/control`; `/health`, `/webhook/telegram`, and `/admin/billing/plans` remain canonical runtime paths and must not be treated as removable aliases yet.
  - `app.worker.main` is now covered by an explicit compatibility contract: `tests/test_worker_compat_shim.py` proves the legacy entrypoint delegates directly to `app.worker_runtime.main` and remains functionally equivalent while the old ops-facing module path still exists.
  - `app.gateway.admin` has been fully retired: the empty shim is deleted, `app.edge.registry_setup` mounts admin routers directly, and the compatibility-shim allowlist in `tests/architecture/test_guardrails.py` has been reduced accordingly.
  - The first productive `connector_hub` strangler slice is active: typed `/admin/integrations/...` endpoints now cover catalog, connector config, docs, webhook info, and system connector reads/writes; the frontend integrations and members flows are cut over to these new paths while the legacy hub remains as fallback during migration.
  - The `connector_hub` strangler is now complete: `app/gateway/routers/connector_hub.py` has been deleted, `registry_setup.py` no longer mounts the legacy `/admin/connector-hub/*` surface, and `test_connector_hub_catalog.py` is migrated to the typed `/admin/integrations/...` paths. The `connector_hub_repository` remains in use by `admin_integrations_service`, which is correct — only the legacy HTTP surface is gone, not the data-access layer it shared.

## Historical Foundation (Sprint 1 & 2 Focus)

---

### Epic 1 & 2: Capability Framework & Architecture Guardrails

#### [NEW] `app/core/module_registry.py`
Establish the central registry for declaring module capabilities, routers, and workers.
- Define `ModuleDefinition` schema (name, capabilities, routers, workers).
- Implement `CapabilityRegistry` to evaluate tenant entitlements against available modules.

#### [NEW] `tests/architecture/test_guardrails.py`
Enforce architecture rules statically via tests to prevent regression during the refactor.
- Write tests using the [ast](file:///opt/ariia/production/app/gateway/main.py#524-538) module to ban direct imports from `app.core.models` in new domain modules.
- Banish direct `SessionLocal()` instantiation outside of the new `shared/db` layer.

#### [MODIFY] [app/core/feature_gates.py](file:///opt/ariia/production/app/core/feature_gates.py)
Refine the entitlement resolving logic.
- Introduce technical capability names (e.g. `support_core`, `campaigns_opt_in`, `integration_magicline`).
- Map the existing 5 seeded plans and add-ons directly to these binary capabilities.

---

### Epic 3 & 4: Capability Wiring & Edge Refactoring

#### [NEW] `app/edge/app.py`
Create the new, clean FastAPI edge layer.
- Move application initialization here.
- Implement capability-aware router registration: only load a module's routers if the module is active.
- Remove all business logic and inline synchronization tasks.

#### [MODIFY] [app/gateway/main.py](file:///opt/ariia/production/app/gateway/main.py)
Strip down the massive 551-line legacy monolith.
- Remove the 40+ `try/except` silent failure blocks.
- Remove the 8 inline background tasks from the lifespan event.
- Delegate initialization to `app.edge.app`.

#### [NEW] `app/edge/health.py`
Standardize health reporting.
- Implement distinct endpoints for `App Health`, `DB Health`, `Integration Status`, and `Worker Status`.

#### [MODIFY] [frontend/components/NavShell.tsx](file:///opt/ariia/production/frontend/components/NavShell.tsx) (and related routing)
UI representation of the dormant features.
- Introduce feature-flag checks based on capabilities.
- Render "Coming Soon" badges/lock states for deactivated UI routes.

---

## Verification Plan

Because this refactoring touches the core application lifecycle, we will use a strict gate-based verification approach.

### Automated Tests
1. **Architecture Rule Tests**:
   Ensure no new violations are introduced during the separation.
   ```bash
   pytest tests/architecture/ -v
   ```
2. **Existing Regression Suite**:
   The existing 1277 tests must continue to pass. We will heavily rely on the existing isolation and routing tests.
   ```bash
   pytest tests/ -v -n auto
   ```
3. **Capability Gating Unit Tests**:
   New tests to specifically verify that deactivated modules do not register routes or workers.
   ```bash
   pytest tests/test_module_registry.py -v
   ```

### Manual Verification
1. **Startup Cleanliness**:
   Boot the system and verify the console output has zero silent `except Exception` ignores for features.
   ```bash
   uvicorn app.edge.app:app --reload
   ```
2. **UI Verification**:
   - Log in as a Starter tenant and verify that complex modules (e.g., advanced analytics or voice) show the new "Coming Soon" or "Upgrade" lock state.
   - Log in as an Enterprise tenant and verify the Product Core (Support, Campaigns, WA, etc.) remains fully accessible.
