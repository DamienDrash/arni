# ARNI P2 Task Tracker: Premium-Qualität vor Launch

- [x] **1. CI/CD Pipeline (GitHub Actions)**
  - [x] Lint, Test, Docker Build/Push, SSH Auto-Deploy Jobs
  - [x] `.github/workflows/ci.yml` deployed

- [x] **2. Frontend: Zentraler API-Client + React Query**
  - [x] `@tanstack/react-query` installiert
  - [x] `frontend/lib/query-client.ts` — QueryClient mit globalen Defaults
  - [x] `frontend/app/providers.tsx` — QueryClientProvider als Client Component
  - [x] `frontend/app/layout.tsx` — Providers-Wrapper eingebunden
  - [x] `frontend/components/ui/QueryStates.tsx` — LoadingSpinner, ErrorCard, EmptyState
  - [x] `frontend/lib/api-hooks.ts` — 12 useQuery/useMutation Hooks (members, analytics, live, audit, tenants, users, billing)

- [x] **3. Stripe Integration**
  - [x] Checkout, Webhook, Status Endpoints live
  - [x] Webhook `whsec_` konfiguriert

- [ ] **4. Frontend White-Labeling**
  - [ ] Backend: `GET/POST /admin/branding` Endpoints
  - [ ] Frontend: CSS Custom Properties aus Branding laden
  - [ ] `/settings/branding` Editor-Seite

- [ ] **5. Aufräumen: Logs, Debug-Scripts und .dockerignore**
  - [ ] Log-Dateien aus Git-Tracking (`.gitignore`)
  - [ ] `scripts/dev/` für Debug-Scripts
  - [ ] `.dockerignore` härten

- [ ] **6. Foreign Keys auf alle tenant_id-Spalten**
  - [ ] Alembic Migration mit FK-Constraints
