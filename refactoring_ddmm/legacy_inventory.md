# Legacy Inventory

## Purpose

This inventory classifies the remaining legacy and compatibility surfaces after
Epic 10. It is the execution baseline for Epic 11.

Classification dimensions:

- `runtime_role`: active_runtime, compatibility_entrypoint, dormant_surface, replaceable_adapter
- `usage`: high, medium, low
- `strategy`: keep_temporarily, strangler_replace, delete_when_safe

## Active Compatibility Entrypoints

### `app.gateway.main`
- File: [main.py](/opt/ariia/staging/app/gateway/main.py)
- Runtime role: `compatibility_entrypoint`
- Usage: `high`
- Why it still exists:
  - preserves `app.gateway.main:app`
  - preserves `/health`, `/ws/control`, legacy Telegram webhook alias, selected compatibility exports
- Current strategy: `keep_temporarily`
- Epic 11 target:
  - keep only as an ingress compatibility shell during strangler cutover
  - delete once all direct imports and compatibility aliases are removed

### `app.gateway.admin`
- Status: removed
- Removal result:
  - the empty `/admin` shim has been deleted
  - `app.edge.registry_setup` now mounts admin domain routers directly
- Epic 11 outcome:
  - compatibility entrypoint retired successfully

### `app.worker.main`
- File: [main.py](/opt/ariia/staging/app/worker/main.py)
- Runtime role: `compatibility_entrypoint`
- Usage: `medium`
- Why it still exists:
  - preserves the historical worker CLI entrypoint
  - now delegates to [worker_runtime/main.py](/opt/ariia/staging/app/worker_runtime/main.py)
- Current strategy: `keep_temporarily`
- Epic 11 target:
  - delete after operational scripts/container entrypoints migrate to `app.worker_runtime.main`

### `app.core.models`
- File: [models.py](/opt/ariia/staging/app/core/models.py)
- Runtime role: `compatibility_entrypoint`
- Usage: `medium`
- Why it still exists:
  - backwards-compatible import shim after domain model split
- Current strategy: `keep_temporarily`
- Epic 11 target:
  - delete after all non-test consumers outside explicit compatibility surfaces are gone

## Replaceable Adapters / Hybrid Surfaces

### Legacy billing compatibility router
- Status: removed
- Removal result:
  - `app/gateway/routers/billing.py` has been deleted
  - Schema aligned: `get_plan_comparison` now includes `features: [string list]` compatible output
  - Webhook secured: returns `400` for missing/invalid Stripe secret
  - `app.billing.router` now serves `/admin/billing/...` directly via registry_setup
  - `test_billing_webhook.py` fully migrated to V2 handler and models
- Epic 11 outcome:
  - strangler replace completed; V2 billing is the sole billing surface

### Connector hub compatibility surface
- Status: removed
- Removal result:
  - `app/gateway/routers/connector_hub.py` has been deleted
  - `app.edge.registry_setup` no longer mounts the legacy `/admin/connector-hub/*` surface
  - `test_connector_hub_catalog.py` migrated to `/admin/integrations/...` paths
  - `app.gateway.connector_hub_repository` is still in use by `admin_integrations_service`
- Epic 11 outcome:
  - strangler replace completed; typed `/admin/integrations/...` endpoints are the sole active surface

### Memory-platform legacy compatibility entrypoints
- Files:
  - [__init__.py](/opt/ariia/staging/app/memory_platform/api/__init__.py)
  - [__init__.py](/opt/ariia/staging/app/memory_platform/ingestion/__init__.py)
- Runtime role: `replaceable_adapter`
- Usage: `medium`
- Notes:
  - preserve older ingestion/content entrypoints while newer knowledge/module paths exist
- Strategy: `strangler_replace`

## Dormant Legacy Surfaces

See [dormant_sunset_backlog.md](/opt/ariia/staging/refactoring_ddmm/dormant_sunset_backlog.md).

Highest-value dormant delete candidates:
- [voice.py](/opt/ariia/staging/app/gateway/routers/voice.py)
- [ab_testing_api.py](/opt/ariia/staging/app/gateway/routers/ab_testing_api.py)

## Prioritized Replacement Queue

### Tier 1
- `app.gateway.main`
- `app.worker.main`
- `app.core.models`

Reason:
- highest blast radius
- still define project-wide compatibility contracts

### Tier 2
- `app.gateway.admin` (completed)
- `gateway/routers/billing.py` (completed)
- `gateway/routers/connector_hub.py` (completed)
- `memory_platform/api` — unmounted router, safe to delete
- `memory_platform/ingestion` — still used by worker/ingestion_tasks.py

Reason:
- active hybrid surfaces with clearer strangler seams

### Tier 3
- dormant runtime remnants from [dormant_sunset_backlog.md](/opt/ariia/staging/refactoring_ddmm/dormant_sunset_backlog.md)

Reason:
- low current usage, best removed once replacement/no-replacement decision is explicit

## Initial Epic 11 Decisions

- `app.gateway.main`, `app.worker.main`, and `app.core.models` are not immediate delete targets.
  They are controlled compatibility entrypoints.
- `app.gateway.admin` is already near-dead and should likely be the first true deletion target once import references are gone.
- Dormant voice and dormant A/B testing should not be reactivated. They are delete-or-replace candidates, not dormant forever candidates.
