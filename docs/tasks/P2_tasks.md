# ARNI P2 Task Tracker: Premium-Qualität vor Launch

Basierend auf dem Critical Analysis Report (2026-02-22). Alle Punkte sind Voraussetzung für einen stabilen Multi-Tenant Launch.

- [ ] **1. CI/CD Pipeline (GitHub Actions)**
  - [ ] Lint-Job: `ruff` (Backend) + `eslint` / `tsc --noEmit` (Frontend)
  - [ ] Test-Job: `pytest --cov=app` mit Coverage-Gate (≥ 70%)
  - [ ] Build-Job: Docker Image bauen + auf Registry pushen
  - [ ] Deploy-Job: optional (Trigger auf `main`-Push, z.B. via SSH oder Docker Hub)
  - [ ] Workflow-Datei: `.github/workflows/ci.yml`

- [ ] **2. Frontend: Zentraler API-Client + React Query**
  - [ ] `frontend/lib/api-client.ts` — zentrales Fetch-Wrapper mit Auth-Header, Token-Refresh und Error-Handling
  - [ ] `frontend/lib/query-client.ts` — React Query `QueryClient` Setup mit globalem stale-time und retry-Policy
  - [ ] Migration der kritischsten Seiten auf React Query Hooks: `/members`, `/live`, `/analytics`
  - [ ] Einheitliches Loading/Error/Empty State Pattern (gemeinsame Komponenten)

- [ ] **3. Stripe Integration abschließen**
  - [ ] Stripe Checkout Session erstellen (API-Endpunkt: `POST /admin/billing/checkout`)
  - [ ] Stripe Webhook empfangen (`POST /webhook/stripe`) — Events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`
  - [ ] `Subscription`-Modell in DB bei Webhook-Events aktualisieren (Status, Zeitraum, Plan)
  - [ ] Frontend `/plans`-Seite: "Upgrade"-Button triggert echten Stripe Checkout (kein Mock mehr)

- [ ] **4. Frontend White-Labeling**
  - [ ] Backend: `GET /admin/branding` und `POST /admin/branding` — Tenant-Farbe (hex), Logo-URL, Display-Name
  - [ ] Branding im DB als Settings (`tenant_primary_color`, `tenant_logo_url`, `tenant_display_name`)
  - [ ] Frontend: Branding beim Login laden und als CSS Custom Properties (`--color-primary`, etc.) setzen
  - [ ] Sidebar-Logo dynamisch aus Branding-Settings laden
  - [ ] Frontend `/settings/branding` — Editor für Logo-URL, Farbe, Name

- [ ] **5. Aufräumen: Logs, Debug-Scripts und .dockerignore**
  - [ ] Log-Dateien aus Git-Tracking entfernen (`.gitignore` erweitern: `*.log`)
  - [ ] `scripts/` auditieren: Debug-/Fix-/Simulate-Scripts in `scripts/dev/` verschieben oder löschen
  - [ ] `.dockerignore` erweitern: `*.log`, `scripts/dev/`, `*.pt`, `.env`, `tests/`, `docs/`
  - [ ] `seed_chat_data.py` (51KB!) refactoren oder in separate, fokussierte Faker-Scripts aufteilen

- [ ] **6. Foreign Keys auf alle tenant_id-Spalten**
  - [ ] Alembic Migration: `ForeignKey("tenants.id", ondelete="RESTRICT")` auf `chat_sessions`, `chat_messages`, `studio_members`, `audit_logs`, `settings`
  - [ ] Cascade-Strategie festlegen: Was passiert bei Tenant-Löschung? (RESTRICT als sicherer Default)
  - [ ] Tests: Sicherstellen, dass kein Insert mit ungültiger `tenant_id` möglich ist
