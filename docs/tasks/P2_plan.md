# ARNI P2 Implementation Plan: Premium-Qualität vor Launch

Adressiert die 6 verbleibenden P2-Maßnahmen aus dem Critical Analysis Report (2026-02-22).

---

## Proposed Changes

### 1. CI/CD Pipeline

#### [NEW] `.github/workflows/ci.yml`
Eine einzige Workflow-Datei mit 3 sequenziellen Jobs:

```yaml
jobs:
  lint:     ruff check app/ + eslint + tsc --noEmit
  test:     pytest --cov=app --cov-fail-under=70
  build:    docker build + optional push to registry
```

**Trigger:** `push` auf `main`/`dev` + `pull_request`.

---

### 2. Frontend API-Client + React Query

#### [NEW] `frontend/lib/api-client.ts`
Zentrales Fetch-Wrapper:
- Liest Token aus `localStorage` (oder Cookie, nach P1 Security-Upgrade)
- Setzt `Authorization: Bearer ...` Header automatisch
- Interceptiert `401` → Logout + Redirect
- Exportiert typisierte `get<T>`, `post<T>`, `put<T>`, `del<T>` Funktionen

#### [NEW] `frontend/lib/query-client.ts`
```ts
export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } }
})
```

#### [MODIFY] `frontend/app/members/page.tsx`, `live/page.tsx`, `analytics/page.tsx`
Ersetzen von manuellem `useEffect`+`fetch` durch `useQuery(["members"], () => apiClient.get("/admin/members"))`.

#### [NEW] `frontend/components/ui/QueryStates.tsx`
Gemeinsame `<LoadingSpinner>`, `<ErrorCard>`, `<EmptyState>` Komponenten für konsistentes UX-Feedback.

---

### 3. Stripe Integration

#### [MODIFY] `app/gateway/admin.py` (oder neues `app/gateway/routers/billing.py`)
```
POST /admin/billing/checkout   → Stripe Checkout Session erstellen
POST /webhook/stripe           → Stripe Webhook (kein Auth, aber Signatur-Check)
GET  /admin/billing/status     → Aktuellen Subscription-Status abrufen
```

#### [MODIFY] `app/core/models.py` — `Subscription`
Status-Enum erweitern: `active`, `past_due`, `canceled`, `trialing`.

#### [MODIFY] `frontend/app/plans/page.tsx`
"Upgrade"-Button ruft `POST /admin/billing/checkout` auf und leitet auf `stripe.redirectToCheckout(sessionId)` um.

> [!IMPORTANT]
> Stripe Webhook Secret muss als Setting (`billing_stripe_webhook_secret`) konfiguriert sein. Der Endpunkt validiert die Signatur mit `stripe.webhooks.construct_event()`.

---

### 4. Frontend White-Labeling

#### Backend: [MODIFY] `app/gateway/admin.py`
```
GET  /admin/branding    → { primary_color, logo_url, display_name }
POST /admin/branding    → Tenant-Branding speichern (als Settings)
```
Intern gespeichert als Settings-Keys: `tenant_primary_color`, `tenant_logo_url`, `tenant_display_name`.

#### Frontend: [NEW] `frontend/lib/branding.ts`
Hook `useBranding()` — lädt beim App-Start Branding für den aktuellen Tenant und injiziert:
```css
:root {
  --color-primary: #<tenant_primary_color>;
}
```

#### [MODIFY] `frontend/components/Sidebar.tsx`
Logo-`<img>` src aus Branding-Settings, Fallback auf ARNI-Logo.

#### [NEW] `frontend/app/settings/branding/page.tsx`
Einfaches Formular: Farb-Picker, Logo-URL-Input, Anzeigename. Preview-Box zeigt Live-Update.

---

### 5. Cleanup

#### `.gitignore` + `.dockerignore`
```
# .gitignore ergänzen:
*.log
/data/arni.db

# .dockerignore ergänzen:
*.log, *.pt, .env, tests/, docs/, scripts/dev/
```

#### `scripts/`
- Unterverzeichnis `scripts/dev/` anlegen.
- Debug-/Fix-/Simulate-Scripts dorthin verschieben.
- `seed_chat_data.py` → aufteilen in `scripts/seed_tenants.py`, `scripts/seed_members.py`, `scripts/seed_chats.py`.

---

### 6. Foreign Keys via Alembic

#### [NEW] Alembic Migration `add_tenant_fks`
```python
op.create_foreign_key(
    "fk_chat_sessions_tenant", "chat_sessions",
    "tenants", ["tenant_id"], ["id"], ondelete="RESTRICT"
)
# ... analog für chat_messages, studio_members, audit_logs, settings
```

> [!CAUTION]
> Vor dieser Migration sicherstellen, dass keine verwaisten `tenant_id`-Werte in den Tabellen existieren (Backfill-Step oder DATA-Check in der `upgrade()`-Funktion).

---

## Verification Plan

### Automated Tests
- `pytest tests/` → alle bestehenden Tests grün
- CI-Pipeline läuft durch auf einem Test-PR
- `tsc --noEmit` im Frontend ohne Fehler

### Manual Verification
1. Stripe Checkout: Klick auf "Upgrade" → Stripe-Checkout-Seite öffnet sich mit korrektem Plan-Namen und Preis.
2. White-Labeling: Tenant-Farbe ändern → Sidebar-Akzentfarbe ändert sich nach Page-Reload.
3. Docker Build: `docker build .` läuft durch ohne `.env`-Datei oder `.log`-Files im Image.
4. Foreign Key: Direkt in DB eine `chat_session` mit `tenant_id=9999` (inexistent) einzufügen muss mit FK-Violation scheitern.
