# ARNI P2 Task Tracker: Premium-Qualität vor Launch

- [x] **1. CI/CD Pipeline (GitHub Actions)**
  - [x] Lint-Job: `ruff` + `eslint` / `tsc --noEmit`
  - [x] Test-Job: `pytest --cov=app`
  - [x] Build-Job: Docker Image → `ghcr.io`
  - [x] Deploy-Job: SSH Auto-Deploy auf VPS
  - [x] Workflow-Datei: `.github/workflows/ci.yml`

- [x] **3. Stripe Integration abschließen**
  - [x] `stripe` Package installiert (v14.3.0)
  - [x] `app/gateway/routers/billing.py` — Checkout, Webhook, Status
  - [x] `POST /admin/billing/checkout` — Checkout Session erstellen
  - [x] `POST /admin/stripe` — Stripe Webhooks empfangen (Signatur-Verifizierung)
  - [x] `GET /admin/billing/status` — Subscription-Status abrufen
  - [x] Nginx Route `https://services.frigew.ski/arni/stripe` → Port 8000
  - [x] Stripe Webhook `we_1T3TvuEmo0m7USTcv5V0Pjod` registriert + `whsec_` in .env
  - [x] 3 Produkte angelegt: Starter (€149), Growth (€349), Enterprise (€999)

- [ ] **2. Frontend: Zentraler API-Client + React Query**
  - [ ] `frontend/lib/api-client.ts` — zentraler Fetch-Wrapper
  - [ ] `frontend/lib/query-client.ts` — React Query Setup
  - [ ] Migration der kritischsten Seiten: `/members`, `/live`, `/analytics`
  - [ ] Einheitliche Loading/Error/Empty State Komponenten

- [ ] **4. Frontend White-Labeling**
  - [ ] Backend: `GET/POST /admin/branding` Endpoints
  - [ ] Branding in Settings-DB speichern
  - [ ] Frontend: CSS Custom Properties aus Branding laden
  - [ ] `/settings/branding` Editor-Seite

- [ ] **5. Aufräumen: Logs, Debug-Scripts und .dockerignore**
  - [ ] Log-Dateien aus Git-Tracking (`.gitignore` erweitern)
  - [ ] `scripts/dev/` für Debug-Scripts anlegen
  - [ ] `.dockerignore` härten

- [ ] **6. Foreign Keys auf alle tenant_id-Spalten**
  - [ ] Alembic Migration: `ForeignKey("tenants.id", ondelete="RESTRICT")`
  - [ ] Cascade-Strategie für Tenant-Löschung festlegen
