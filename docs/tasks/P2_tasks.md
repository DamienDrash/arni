# ARNI P2 Task Tracker: Premium-Qualität vor Launch

- [x] **1. CI/CD Pipeline** — GitHub Actions mit SSH Auto-Deploy live
- [x] **2. Frontend React Query** — `api-hooks` (14 Hooks), `QueryStates`, `providers`
- [x] **3. Stripe Integration** — Checkout, Webhook (`whsec_`), Status live
- [x] **4. Frontend White-Labeling** — NavShell, Sidebar, Branding-Editor, `useBranding` Hook
- [x] **5. Cleanup** — 19 Debug-Scripts → `scripts/dev/`, `.gitignore` + `.dockerignore` gehärtet, Logs aus Git

- [ ] **6. Foreign Keys auf alle tenant_id-Spalten**
  - [ ] Alembic Migration: `ForeignKey("tenants.id", ondelete="RESTRICT")`
  - [ ] Daten-Check vor Migration (keine verwaisten tenant_ids)
