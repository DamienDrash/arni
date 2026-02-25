# Stripe Integration – Analyse & Plan

## Bestehende Infrastruktur
- **Plan Model**: Vollständig mit Feature-Flags, Limits, Overage-Pricing
- **Subscription Model**: tenant_id → plan_id, Stripe IDs, Status
- **TenantAddon Model**: Addon-Zuordnung pro Tenant
- **UsageRecord Model**: Monatliche Nutzungszähler
- **billing_sync.py**: Grundlegender Sync (nur Name/Price, keine Features)
- **feature_gates.py**: FeatureGate-Klasse + seed_plans()
- **plans_admin.py**: CRUD für Pläne, Sync-Trigger, Addon-CRUD
- **billing.py**: Checkout, Portal, Webhook-Handler
- **admin.py**: Stripe Connector Config (Credentials), Test-Endpoint

## Identifizierte Lücken

### 1. Plan Model – Fehlende Felder
- `stripe_product_id` fehlt (nur stripe_price_id vorhanden)
- `description` fehlt (für Landing Page)
- `display_order` fehlt (Sortierung)
- `price_yearly_cents` fehlt (Jahrespreise)
- `trial_days` fehlt
- `features_json` fehlt (dynamische Feature-Liste für UI)
- `updated_at` fehlt

### 2. Addon Definition Model fehlt komplett
- Aktuell werden Addons nur aus Stripe gelesen (kein lokales Model)
- Braucht: AddonDefinition mit slug, name, description, price, stripe_product_id, stripe_price_id, features_json

### 3. Bidirektionaler Sync unvollständig
- sync_from_stripe: Nur Name/Price, keine Feature-Flags
- push_to_stripe: Grundlegend, aber keine Metadata-Sync
- Kein Webhook für product.updated / price.updated
- Kein Conflict-Resolution

### 4. Stripe Credentials
- Bereits in admin.py implementiert (GET/PUT /billing/connectors)
- Verschlüsselt gespeichert via crypto.py
- Test-Endpoint vorhanden
- ABER: Kein dediziertes Frontend dafür im System-Admin

### 5. Tenant-Sichtbarkeit
- Pricing Page: Hardcoded Plans im Frontend
- Billing Page: Liest von /admin/billing/plans (hardcoded PLAN_CATALOG)
- Muss dynamisch aus DB kommen

### 6. Feature Gating
- FeatureGate-Klasse existiert und funktioniert
- Frontend FeatureGate-Komponente existiert
- Permissions-Endpoint liefert Features
- ABER: Nicht alle Features werden im permissions-Endpoint gemappt
