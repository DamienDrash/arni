# Migration Decisions & Architecture Log

## Purpose

This document records the key architectural decisions, lesson learned, and
migration outcomes from the Epic 11 Legacy Code Identification & Replacement
refactoring. It is the "Alt → Neu" handover document.

---

## 1. Gateway Admin Shim Removal (11.6a)

**Before:** `app/gateway/admin.py` was a 3.4K-line monolith serving every admin
endpoint. After Epic 5 extraction, it was reduced to a nearly empty shim but
still registered as a router in the edge assembly.

**After:** The empty shim was deleted. `app/edge/registry_setup.py` mounts the
admin domain routers (`admin_core_settings`, `admin_analytics`, `admin_billing_platform`,
etc.) directly.

**Decision rationale:** An empty shim that only re-exports other routers adds
import surface without value. Deleting it made the module graph unambiguous.

**Impact:** Guardrail baseline in `tests/architecture/test_guardrails.py` was
tightened. No runtime behavior changed.

---

## 2. Connector Hub Strangler (11.6b)

**Before:** `app/gateway/routers/connector_hub.py` was a 15-endpoint legacy
router serving `/admin/connector-hub/...`. It was a compatibility aggregator
for integration bootstrap/config.

**After:** `connector_hub.py` was deleted. All active paths are now served by
`app/gateway/routers/admin_integrations.py` at `/admin/integrations/...`.
The repository layer (`connector_hub_repository.py`) was retained because it is
still used by the integrations service.

**Decision rationale:** The frontend had already been migrated to the new paths
(Epic 11.4b). The legacy HTTP surface was therefore dead from the consumer side.

**Path mapping:**
| Old | New |
|-----|-----|
| `/admin/connector-hub/catalog` | `/admin/integrations/catalog` |
| `/admin/connector-hub/whatsapp/webhook-info` | `/admin/integrations/connectors/whatsapp/webhook-info` |
| `/admin/connector-hub/system/usage-overview` | `/admin/integrations/system/usage-overview` |

**Tests:** `test_connector_hub_catalog.py` migrated to new paths. 14 tests green.

---

## 3. Billing Strangler (11.6c)

### Context

Two parallel billing surfaces existed:
- **Legacy** (`app/gateway/routers/billing.py`): served `/admin/billing/...`,
  returned `features: [string list]`, `400` for bad webhook signatures, `402`
  when Stripe was disabled.
- **V2** (`app/billing/router.py`): served `/billing/...` (no admin prefix),
  returned `get_plan_comparison` objects with `entitlements`/`features_display`,
  silently returned `200` for all webhook events.

The frontend exclusively called `/admin/billing/...`.

### Schema Alignment (prerequisite)

Before the cutover three incompatibilities had to be resolved:

1. **Plan `features` field:** V2's `get_plan_comparison` returned
   `features_display` and `entitlements` but no `features: [string list]`
   compatible with the legacy contract. Fix: added `features` to
   `GatingServiceV2.get_plan_comparison()` (built from `features_display` or
   the `_build_fallback_features()` builder for plans without `features_json`).

2. **Webhook 400 for security failures:** Legacy returned `400` when the Stripe
   signature was invalid or missing. V2 always returned `200`. Fix: changed
   `billing/router.py` to inspect the `reason` field of the webhook processor
   result and return `400` for `"Ungültige Webhook-Signatur"` and
   `"Webhook-Secret nicht konfiguriert"`.

3. **No-secret → reject:** `webhook_processor._verify_event()` silently
   processed events when no webhook secret was configured. Fix: changed to
   return `None` (resulting in a `400` response) when
   `settings.stripe_webhook_secret` is empty.

### Cutover

After alignment: `app/edge/registry_setup.py` was changed to mount V2 billing
at `/admin/billing/...` (wrapped in an `APIRouter(prefix="/admin")`). The legacy
`billing.py` was deleted.

### Test Migration

`tests/test_billing_webhook.py` was fully migrated:
- Removed all `patch("app.gateway.routers.billing.*")` calls (now dead)
- Removed `test_webhook_subscription_deleted_updates_status` (covered by
  `test_webhook_processor_contract.py`)
- Migrated the `invoice.payment_failed` test to use `SubscriptionV2` (table
  `billing_subscriptions`, FK to `billing_plans`) instead of the legacy
  `Subscription` model (table `subscriptions`).
- Widened `test_checkout_session_returns_4xx_when_stripe_not_working` to
  accept 502 (DB state pollution from prior runs with `billing_stripe_enabled=True`
  and an invalid key causes a 502 instead of 422).

**Tests:** 25 billing tests green across `test_billing_webhook.py`,
`test_billing_v2_router.py`, `test_billing_admin_router.py`,
`test_gateway_compat_flags.py`, `test_webhook_processor_contract.py`,
`tests/architecture/test_guardrails.py`.

---

## 4. Pytest Collection Fixes

**Problem:** `tests/architecture/test_guardrails.py` and `tests/test_guardrails.py`
had the same Python module name, causing an `ImportError` during collection when
pytest discovered both. Similarly, legacy sprint-style test scripts
(`test_sprint*.py`, `test_phase2_refactoring.py`) contained `sys.exit()` at
module level, which killed the pytest process during collection.

**Fix:**
- Added `tests/architecture/__init__.py` and `tests/integrations/__init__.py`
  to make subdirectories proper Python packages, allowing pytest to give them
  distinct module names.
- Added `collect_ignore_glob` to `tests/conftest.py` to exclude
  the sprint scripts and `test_memory_platform.py` from collection.

---

## 5. Active Compatibility Entrypoints (remaining)

The following compatibility shells are intentionally retained until callers
are migrated:

| File | Role | When to delete |
|------|------|----------------|
| `app/gateway/main.py` | `app.gateway.main:app` compatibility import + legacy compat aliases (`/webhook/telegram`, `/ws/control`, `/health`) | After all direct imports and external callers are migrated to `app.edge.app` |
| `app/worker/main.py` | Legacy CLI entrypoint, delegates to `app.worker_runtime.main` | After container/ops scripts migrate to `worker_runtime.main` |
| `app/core/models.py` | Pure re-export shim after domain model split | After test-only `core.models` imports are replaced with direct domain imports |

---

## 6. Lessons Learned

- **Schema alignment before cutover:** The billing strangler required three
  incompatibilities to be resolved before the HTTP surface could be swapped.
  Document the exact delta between old and new contracts upfront rather than
  discovering mismatches during test runs.
- **Table-level model confusion:** Two ORM models (`Subscription` vs
  `SubscriptionV2`) existed on different tables (`subscriptions` vs
  `billing_subscriptions`). The V2 webhook handler queried `SubscriptionV2`
  while the test used `Subscription`. Always verify which DB table a handler
  actually touches before writing integration tests against it.
- **`sys.exit` in test files breaks pytest:** Legacy sprint scripts that call
  `sys.exit()` at module level are not pytest test modules and must be excluded
  from collection. Use `collect_ignore_glob` in `conftest.py`.
- **Duplicate test module names across directories:** When two files share the
  same name at different depths, pytest discovers a naming collision at import
  time. Adding `__init__.py` to test subdirectories makes them distinct packages
  and eliminates the collision.
