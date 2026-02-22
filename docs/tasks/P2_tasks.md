# ARNI P2 Task Tracker: Premium-Qualität vor Launch

- [x] **1. CI/CD Pipeline** — `.github/workflows/ci.yml` mit SSH Auto-Deploy live
- [x] **2. Frontend React Query** — `query-client`, `providers`, `api-hooks` (14 Hooks), `QueryStates`
- [x] **3. Stripe Integration** — Checkout, Webhook (`whsec_`), Status-Endpoints live
- [x] **4. Frontend White-Labeling** — NavShell, Sidebar, branding.ts, `/settings/branding` und `useBranding` Hook vollständig

- [ ] **5. Aufräumen**
  - [ ] `.gitignore` — `*.log` ergänzen
  - [ ] `scripts/dev/` für Debug-Scripts anlegen
  - [ ] `.dockerignore` härten

- [ ] **6. Foreign Keys auf alle tenant_id-Spalten**
  - [ ] Alembic Migration: `ForeignKey("tenants.id", ondelete="RESTRICT")`
  - [ ] Cascade-Strategie festlegen
