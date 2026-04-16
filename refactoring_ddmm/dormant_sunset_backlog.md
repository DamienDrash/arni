# Dormant Sunset Backlog

## Goal

Inventory of non-core, currently dormant capabilities and the code surfaces that
must either stay explicitly dormant behind the edge/module boundary or be
deleted during Epic 11.

## Dormant Capability Inventory

### `voice_pipeline`
- Runtime module: [registry_setup.py](/opt/ariia/staging/app/edge/registry_setup.py)
- Router surface: [voice.py](/opt/ariia/staging/app/gateway/routers/voice.py)
- Frontend/add-on references:
  - [settings/integrations/page.tsx](/opt/ariia/staging/frontend/app/settings/integrations/page.tsx)
  - plan/add-on config in [page.tsx](/opt/ariia/staging/frontend/app/plans/page.tsx)
- Current strategy:
  - not booted in `app.edge.app`
  - no longer mounted by [main.py](/opt/ariia/staging/app/gateway/main.py)
- Epic 11 target:
  - either replace behind a dedicated voice service boundary
  - or delete legacy Twilio ingress/runtime glue entirely

### `advanced_analytics`
- Runtime module: [registry_setup.py](/opt/ariia/staging/app/edge/registry_setup.py)
- Dormant router surface: [ab_testing_api.py](/opt/ariia/staging/app/gateway/routers/ab_testing_api.py)
- Frontend “coming soon” surfaces:
  - [route-access.ts](/opt/ariia/staging/frontend/lib/route-access.ts)
  - [Sidebar.tsx](/opt/ariia/staging/frontend/components/Sidebar.tsx)
- Current strategy:
  - no server boot for dormant A/B testing router
  - tenant-facing `/analytics` route stays “coming soon”
- Epic 11 target:
  - keep only the active admin/platform analytics paths
  - remove legacy/dormant experimentation surface if no replacement is pursued

### `brand_style`
- Runtime state:
  - feature gate exists in [feature_gates.py](/opt/ariia/staging/app/core/feature_gates.py)
  - tenant-facing settings surface marked “coming soon” in [route-access.ts](/opt/ariia/staging/frontend/lib/route-access.ts)
- Related runtime path:
  - gated media generation in [media.py](/opt/ariia/staging/app/gateway/routers/media.py)
- Epic 11 target:
  - either formalize as an AI/media capability with a dedicated module
  - or delete residual gating/UI scaffolding

### `churn_prediction`
- Runtime state:
  - capability/add-on only, no active module assembly
  - plan/add-on references remain in [feature_gates.py](/opt/ariia/staging/app/core/feature_gates.py) and [page.tsx](/opt/ariia/staging/frontend/app/plans/page.tsx)
- Epic 11 target:
  - decide replace-vs-delete before exposing any runtime surface

### `vision_ai`
- Runtime state:
  - capability/add-on only, no active module assembly
  - residual billing/plan references remain
- Epic 11 target:
  - replace with a dedicated media/vision module or remove the dormant capability

### `multi_channel_routing`
- Runtime state:
  - derived capability in [feature_gates.py](/opt/ariia/staging/app/core/feature_gates.py)
  - no dedicated active runtime assembly
- Epic 11 target:
  - either fold into active messaging orchestration
  - or remove capability-only scaffolding

## Frontend “Coming Soon” Contract

The following tenant-visible routes are intentionally rendered as `coming_soon`
and must remain aligned with the dormant runtime inventory:

- `/analytics`
- `/member-memory`
- `/system-prompt`
- `/settings/prompts`
- `/automations`
- `/settings/automation`
- `/settings/branding`

Contract sources:
- [route-access.ts](/opt/ariia/staging/frontend/lib/route-access.ts)
- [route-access.contract.test.ts](/opt/ariia/staging/frontend/tests/route-access.contract.test.ts)

## Epic 11 Cleanup Candidates

- Remove dormant compatibility mounting from [main.py](/opt/ariia/staging/app/gateway/main.py)
- Delete [voice.py](/opt/ariia/staging/app/gateway/routers/voice.py) if no replacement service is chosen
- Delete [ab_testing_api.py](/opt/ariia/staging/app/gateway/routers/ab_testing_api.py) if experimentation stays out of scope
- Prune dormant plan/add-on/UI scaffolding for `vision_ai`, `churn_prediction`, `brand_style`, `multi_channel_routing`
