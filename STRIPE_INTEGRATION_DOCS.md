# ARIIA – Stripe Integration Dokumentation

## Übersicht

Die Stripe-Integration ermöglicht die vollständige Verwaltung von Abonnement-Plänen und Add-ons mit bidirektionalem Sync zwischen dem ARIIA Admin-Interface und Stripe.

---

## Architektur

### Datenfluss

```
Admin UI (Plans Page)
    ↕ REST API
Backend (plans_admin.py, billing_sync.py)
    ↕ Stripe API + Webhooks
Stripe Dashboard
```

### Bidirektionaler Sync

| Richtung | Trigger | Was wird synchronisiert |
|----------|---------|------------------------|
| **Admin → Stripe** | Plan/Addon erstellen/bearbeiten | Product, Price (monthly + yearly) |
| **Stripe → Admin** | Webhook (product.*, price.*) | Name, Beschreibung, Preis, Status |
| **Stripe → Admin** | Periodischer Sync (15 Min.) | Alle Produkte + Preise |
| **Admin → Stripe** | Manueller Sync-Button | Alle Plans/Addons ohne Stripe-ID |

---

## Geänderte Dateien

### Backend

| Datei | Änderungen |
|-------|-----------|
| `app/core/models.py` | Plan-Model erweitert (stripe_product_id, stripe_price_id, stripe_price_yearly_id, description, price_yearly_cents, trial_days, display_order, is_highlighted, features_json, is_public, overage_*_cents, updated_at). AddonDefinition-Model hinzugefügt. |
| `app/core/billing_sync.py` | Komplette Sync-Engine: push_plan_to_stripe, push_addon_to_stripe, sync_plans_from_stripe, sync_addons_from_stripe, full_bidirectional_sync |
| `app/core/feature_gates.py` | FeatureGate mit Addon-Support. seed_plans() erweitert mit Addon-Seeding, Display-Metadaten, features_json |
| `app/gateway/routers/plans_admin.py` | Vollständiges CRUD für Plans + Addons mit Auto-Stripe-Sync. Public Endpoints für Landing Page |
| `app/gateway/routers/billing.py` | Webhook-Handler für product.updated/deleted, price.updated/created |
| `app/gateway/routers/permissions.py` | Erweitert mit Addon-Info, AI-Tier, Overage-Pricing, Feature-Flags |
| `app/gateway/admin.py` | Stripe Credentials CRUD (GET/PUT/POST test) mit Verschlüsselung |
| `app/gateway/main.py` | Billing-Sync-Loop synchronisiert jetzt Plans UND Addons |

### Frontend

| Datei | Änderungen |
|-------|-----------|
| `frontend/app/plans/page.tsx` | Komplett neues Admin-Interface mit 3 Tabs: Plans (CRUD + Grid), Addons (CRUD), Stripe Credentials (Config + Test) |
| `frontend/app/settings/billing/page.tsx` | Dynamische Plan-Anzeige aus DB, Addon-Checkout, Current-Plan-Highlighting |
| `frontend/app/pricing/PricingClient.tsx` | Dynamische Pricing-Page aus Public API, Monthly/Yearly Toggle, Addon-Showcase |
| `frontend/components/FeatureGate.tsx` | LimitGate, SubscriptionGate, Addon-aware Feature-Checking |
| `frontend/lib/permissions.ts` | Addon-Support, AI-Tier, Overage-Info |

### Migration

| Datei | Änderungen |
|-------|-----------|
| `alembic/versions/2026_02_25_stripe_integration.py` | Plans-Tabelle erweitern, addon_definitions erstellen, tenant_addons erweitern |

---

## API Endpoints

### Admin (System-Admin only)

| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| GET | `/admin/plans` | Alle Pläne auflisten |
| POST | `/admin/plans` | Neuen Plan erstellen + Stripe Sync |
| PATCH | `/admin/plans/{id}` | Plan bearbeiten + Stripe Sync |
| DELETE | `/admin/plans/{id}` | Plan löschen (nur ohne aktive Subs) |
| GET | `/admin/plans/addons` | Alle Addon-Definitionen |
| POST | `/admin/plans/addons` | Neues Addon erstellen + Stripe Sync |
| PATCH | `/admin/plans/addons/{id}` | Addon bearbeiten + Stripe Sync |
| DELETE | `/admin/plans/addons/{id}` | Addon löschen |
| POST | `/admin/plans/sync-now` | Bidirektionaler Sync |
| POST | `/admin/plans/sync-from-stripe` | Stripe → DB |
| POST | `/admin/plans/sync-to-stripe` | DB → Stripe (alle ohne Stripe-ID) |
| POST | `/admin/plans/cleanup` | Verwaiste Pläne entfernen |
| GET | `/admin/billing/connectors` | Stripe Credentials lesen (maskiert) |
| PUT | `/admin/billing/connectors` | Stripe Credentials aktualisieren |
| POST | `/admin/billing/connectors/stripe/test` | Stripe-Verbindung testen |

### Public (kein Auth)

| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| GET | `/admin/plans/public` | Öffentliche Pläne für Landing Page |
| GET | `/admin/plans/public/addons` | Öffentliche Addons für Landing Page |

### Tenant

| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| GET | `/permissions` | Plan-Features, Limits, Addons für aktuellen Tenant |

---

## Stripe Naming Convention

| Typ | Product Name | Metadata |
|-----|-------------|----------|
| Plan | `ARIIA Plan: <Name>` | `ariia_type=plan`, `ariia_slug=<slug>`, `ariia_plan_id=<id>` |
| Addon | `ARIIA Add-on: <Name>` | `ariia_type=addon`, `ariia_slug=<slug>`, `ariia_addon_id=<id>` |

---

## Webhook Events

Konfiguriere den Stripe Webhook-Endpoint auf `/billing/webhook` mit folgenden Events:

- `checkout.session.completed` — Subscription aktivieren
- `customer.subscription.updated` — Status + Periode sync
- `customer.subscription.deleted` — Status → canceled
- `invoice.payment_succeeded` / `invoice.paid` — Status → active
- `invoice.payment_failed` — Status → past_due
- `product.updated` / `product.deleted` — Plan/Addon-Daten sync
- `price.updated` / `price.created` — Preis-Daten sync

---

## Feature Gating

### Plan-basierte Features

Jeder Plan definiert Feature-Toggles (Boolean-Spalten im Plan-Model):
- Channel-Toggles: whatsapp, telegram, sms, email, voice, instagram, facebook, google_business
- Feature-Toggles: memory_analyzer, custom_prompts, advanced_analytics, branding, audit_log, automation, api_access, multi_source_members, churn_prediction, vision_ai, white_label, sla_guarantee, on_premise

### Addon-basierte Feature-Erweiterung

Addons können Features freischalten, die im Plan nicht enthalten sind:
- `voice_pipeline` → voice_enabled
- `vision_ai` → vision_ai_enabled
- `white_label` → white_label_enabled
- `churn_prediction` → churn_prediction_enabled
- `automation_pack` → automation_enabled
- `extra_channel` → zusätzlicher Kanal

### Backend-Enforcement

```python
from app.core.feature_gates import FeatureGate

gate = FeatureGate(tenant_id=7)
gate.require_channel("telegram")    # HTTP 402 wenn nicht im Plan/Addon
gate.require_feature("vision_ai")   # HTTP 402 wenn nicht verfügbar
gate.check_message_limit()          # HTTP 429 wenn Limit erreicht
gate.check_member_limit()           # HTTP 402 wenn Limit erreicht
```

### Frontend-Enforcement

```tsx
import { FeatureGate, LimitGate, SubscriptionGate } from "@/components/FeatureGate";

<FeatureGate feature="advanced_analytics">
  <AnalyticsDashboard />
</FeatureGate>

<LimitGate limitKey="max_members" current={memberCount}>
  <AddMemberButton />
</LimitGate>

<SubscriptionGate minPlan="pro">
  <ProFeaturePanel />
</SubscriptionGate>
```

---

## Seed-Daten

### Standard-Pläne

| Plan | Preis/Mo | Mitglieder | Nachrichten | Kanäle | AI Tier |
|------|----------|-----------|-------------|--------|---------|
| Starter | 79€ | 500 | 500 | 1 | Basic |
| Professional | 199€ | ∞ | 2.000 | 3 | Standard |
| Business | 399€ | ∞ | 10.000 | Alle | Premium |
| Enterprise | Custom | ∞ | ∞ | Alle | Unlimited |

### Standard-Addons

| Addon | Preis/Mo | Kategorie | Schaltet frei |
|-------|----------|-----------|---------------|
| Voice Pipeline | 49€ | Channel | voice_enabled |
| Vision AI | 29€ | AI | vision_ai_enabled |
| White Label | 99€ | Integration | white_label_enabled |
| Churn Prediction | 39€ | Analytics | churn_prediction_enabled |
| Extra Channel | 29€ | Channel | extra_channel |
| Automation Pack | 49€ | Integration | automation_enabled |
