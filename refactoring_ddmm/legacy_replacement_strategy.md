# Legacy Replacement Strategy

## Purpose

This document turns the raw inventory in
[legacy_inventory.md](/opt/ariia/staging/refactoring_ddmm/legacy_inventory.md)
into concrete Epic-11 replacement targets and cutover seams.

## Replacement Candidates

### `app.gateway.main`
- Current role:
  - compatibility shell for `app.gateway.main:app`
  - legacy aliases for `/health`, `/webhook/telegram`, `/ws/control`, `/admin/billing/*`
- Replacement target:
  - `app.edge.app` as the single HTTP runtime
  - explicit adapter layer only for externally required aliases
- Cutover seam:
  - config flags in [settings.py](/opt/ariia/staging/config/settings.py):
    - `enable_legacy_health_endpoint`
    - `enable_legacy_telegram_webhook_alias`
    - `enable_legacy_billing_admin_alias`
    - `enable_legacy_ws_control`
    - `enable_legacy_voice_routes`
- Migration strategy:
  - strangler via flag-by-flag shutdown
  - remove `gateway.main` after callers stop importing it directly

### `app.worker.main`
- Current role:
  - compatibility CLI entrypoint
- Replacement target:
  - [worker_runtime/main.py](/opt/ariia/staging/app/worker_runtime/main.py)
- Cutover seam:
  - container/ops command migration
- Migration strategy:
  - switch runtime entrypoints first
  - delete shim later

### `app.core.models`
- Current role:
  - pure compatibility import shim
- Replacement target:
  - domain modules plus domain query services
- Cutover seam:
  - direct import removal in remaining compat/test surfaces
- Migration strategy:
  - delete last after compatibility callers are gone

### `gateway/routers/billing.py`
- Current role:
  - hybrid V1 compatibility billing surface
- Replacement target:
  - `app.billing.router` / `app.billing.admin_router`
- Cutover seam:
  - `enable_legacy_billing_admin_alias`
- Migration strategy:
  - keep read-only/public plan contract during migration
  - cut legacy alias once all consumers are on V2

### `gateway/routers/connector_hub.py`
- Current role:
  - compatibility aggregator for integration bootstrap/config
- Replacement target:
  - domain-specific integration APIs
- Cutover seam:
  - frontend callers move to typed per-domain endpoints
  - the first productive seam is now live under `/admin/integrations/...`
- Migration strategy:
  - strangler replace path-by-path
  - keep `connector_hub` only for the not-yet-migrated paths while typed routes absorb active UI traffic

## Corruption Layers

### HTTP Compatibility Layer
- Files:
  - [main.py](/opt/ariia/staging/app/gateway/main.py)
  - [main.py](/opt/ariia/staging/app/worker/main.py)
- Responsibility:
  - isolate legacy ingress/CLI shapes from the new runtime

### Persistence Compatibility Layer
- File:
  - [persistence.py](/opt/ariia/staging/app/gateway/persistence.py)
- Responsibility:
  - contain old settings/session access patterns while newer repositories/services exist

### Dormant Runtime Boundary
- Files:
  - [registry_setup.py](/opt/ariia/staging/app/edge/registry_setup.py)
  - [route-access.ts](/opt/ariia/staging/frontend/lib/route-access.ts)
- Responsibility:
  - ensure dormant capabilities stay explicitly off in runtime and UI

## Immediate Epic 11 Execution Order

1. Gateway alias cutovers via config flags
2. Worker CLI cutover to `worker_runtime.main`
3. Legacy billing alias shutdown after V2 verification
4. Connector-hub strangler replacement
5. Final removal of `gateway.admin`, `gateway.main`, `worker.main`, `core.models`
