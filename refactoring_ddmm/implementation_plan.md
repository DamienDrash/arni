# Implementation Plan: Domain-Driven Modular Monolith Refactoring

This plan translates the 10-Epic product and architecture consolidation roadmap into a concrete, executable strategy.

## Goal Description
Transform the current highly-coupled 106K LOC monolithic backend into a capability-based, modular monolith. We will aggressively trim the active execution footprint down to the real product core, dormitize unused features, and establish firm boundaries using a Thin API Edge, Module Registry, and Event/Capability wiring.

## User Review Required
> [!IMPORTANT]
> The exact subset of features to keep active (Product Core) is defined as: Support, Campaigns, Knowledge, WhatsApp QR, Telegram, Calendly, and Magicline.
> Any feature outside this list will be technically dormitized (disabled at router/worker registration) and marked "Coming Soon" in the UI. Please confirm this strict cut-off before we proceed with the code changes.

## Proposed Changes (Sprint 1 & 2 Focus)

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
