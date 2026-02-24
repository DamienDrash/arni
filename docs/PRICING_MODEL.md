# ARIIA Pricing-Modell — Technische Dokumentation

## Übersicht

ARIIA verwendet ein 4-Tier-Pricing-Modell mit modularen Add-ons und nutzungsbasierter Overage-Abrechnung. Alle Zahlungen werden über Stripe abgewickelt.

## Basis-Pläne

| | Starter | Professional | Business | Enterprise |
|:---|:---|:---|:---|:---|
| **Preis/Monat** | 79 € | 199 € | 399 € | Individuell |
| **Preis/Jahr** | 63 €/mo (756 €) | 159 €/mo (1.908 €) | 319 €/mo (3.828 €) | Individuell |
| **Rabatt jährlich** | 20% | 20% | 20% | — |

## Reglementierung pro Plan

### Kommunikationskanäle

| Kanal | Starter | Professional | Business | Enterprise |
|:---|:---|:---|:---|:---|
| WhatsApp | ✓ | ✓ | ✓ | ✓ |
| Telegram | ✗ | ✓ | ✓ | ✓ |
| E-Mail | ✗ | ✓ | ✓ | ✓ |
| SMS (Twilio) | ✗ | ✓ | ✓ | ✓ |
| Instagram DM | ✗ | ✓ | ✓ | ✓ |
| Facebook Messenger | ✗ | ✓ | ✓ | ✓ |
| Voice Pipeline | ✗ | ✗ | ✓ | ✓ |
| Google Business | ✗ | ✗ | ✓ | ✓ |
| **Max. Kanäle** | **1** | **3** | **Alle** | **Alle** |

### Mitglieder-Quellen & Connectors

| Quelle | Starter | Professional | Business | Enterprise |
|:---|:---|:---|:---|:---|
| Manuelle Pflege | ✓ | ✓ | ✓ | ✓ |
| API | ✓ | ✓ | ✓ | ✓ |
| CSV Import/Export | ✓ | ✓ | ✓ | ✓ |
| Magicline | ✗ | 1 wählbar | ✓ | ✓ |
| Shopify | ✗ | 1 wählbar | ✓ | ✓ |
| WooCommerce | ✗ | 1 wählbar | ✓ | ✓ |
| HubSpot | ✗ | 1 wählbar | ✓ | ✓ |
| **Max. Connectors** | **0** | **1** | **Alle** | **Alle + Custom** |

### KI & LLM-Modelle

| | Starter | Professional | Business | Enterprise |
|:---|:---|:---|:---|:---|
| **AI Tier** | Basic | Standard | Premium | Unlimited |
| GPT-4.1 Nano | ✓ | ✓ | ✓ | ✓ |
| GPT-4.1 Mini | ✗ | ✓ | ✓ | ✓ |
| GPT-4.1 | ✗ | ✗ | ✓ | ✓ |
| Gemini 2.5 Flash | ✗ | ✗ | ✓ | ✓ |
| Eigene API-Keys | ✗ | ✗ | ✗ | ✓ |
| **Tokens/Monat** | **100K** | **500K** | **2M** | **Unbegrenzt** |

### Usage-Limits

| Ressource | Starter | Professional | Business | Enterprise |
|:---|:---|:---|:---|:---|
| Konversationen/Monat | 500 | 2.000 | 10.000 | Unbegrenzt |
| Mitglieder | 500 | Unbegrenzt | Unbegrenzt | Unbegrenzt |
| Users | 1 | 5 | 15 | Unbegrenzt |

### Features

| Feature | Starter | Professional | Business | Enterprise |
|:---|:---|:---|:---|:---|
| Member Memory | ✗ | ✓ | ✓ | ✓ |
| Custom Prompts | ✗ | ✓ | ✓ | ✓ |
| Analytics+ | ✗ | ✓ | ✓ | ✓ |
| Branding | ✗ | ✓ | ✓ | ✓ |
| Audit Log | ✗ | ✓ | ✓ | ✓ |
| API Access | ✗ | ✓ | ✓ | ✓ |
| Automation Engine | ✗ | ✗ | ✓ | ✓ |
| Churn Prediction | ✗ | ✗ | ✓ | ✓ |
| Vision AI | ✗ | ✗ | ✓ | ✓ |
| White-Label | ✗ | ✗ | ✗ | ✓ |
| SLA-Garantie | ✗ | ✗ | ✗ | ✓ |
| On-Premise | ✗ | ✗ | ✗ | ✓ |

## Add-ons

Add-ons sind monatlich kündbar und werden als separate Stripe Subscription Items abgerechnet.

| Add-on | Preis/Monat | Kategorie | Min. Plan |
|:---|:---|:---|:---|
| Churn Prediction | +49 € | AI | Business |
| Voice Pipeline | +79 € | Communication | Business |
| Vision AI | +39 € | AI | Business |
| Zusätzlicher Kanal | +29 € | Communication | Starter |
| Extra Konversationen (+1.000) | +19 € | Platform | Starter |
| Zusätzlicher User | +15 € | Platform | Starter |
| White-Label | +149 € | Platform | Business |
| API Access | +99 € | Platform | Professional |
| Extra Connector | +49 € | Members | Professional |

## Overage-Abrechnung

Wenn ein Tenant sein Limit überschreitet, wird der Service **nicht unterbrochen**. Stattdessen wird der Mehrverbrauch automatisch über Stripe Metered Billing abgerechnet:

| Ressource | Overage-Preis |
|:---|:---|
| Zusätzliche Konversation | 0,05 € |
| Zusätzlicher User | 15 €/Monat |
| Zusätzlicher Connector | 49 €/Monat |
| Zusätzlicher Kanal | 29 €/Monat |

## Stripe-Integration

### Checkout-Flow

1. Tenant Admin klickt "Plan wechseln" oder "Add-on kaufen"
2. Backend erstellt Stripe Checkout Session mit korrektem Price ID
3. Redirect zu Stripe Checkout
4. Webhook empfängt `checkout.session.completed`
5. Backend aktualisiert Subscription + Plan in DB
6. Frontend zeigt neuen Status

### Plan-Wechsel

- **Upgrade**: Sofortige anteilige Abrechnung (`proration_behavior: create_prorations`)
- **Downgrade**: Guthaben wird auf nächste Rechnung angerechnet
- Backend nutzt `stripe.Subscription.modify()` mit neuem Price ID

### Webhook-Events

| Event | Aktion |
|:---|:---|
| `checkout.session.completed` | Subscription erstellen/aktivieren |
| `customer.subscription.updated` | Plan-Wechsel verarbeiten |
| `customer.subscription.deleted` | Auf Starter zurücksetzen |
| `invoice.paid` | Zahlung bestätigen, Periode aktualisieren |
| `invoice.payment_failed` | Status auf `past_due` setzen |
| `customer.subscription.trial_will_end` | Trial-Warnung (3 Tage vorher) |

### Metered Billing (Overage)

```python
# Overage am Monatsende melden
stripe.SubscriptionItem.create_usage_record(
    subscription_item_id,
    quantity=overage_conversations,
    timestamp=int(time.time()),
    action="set",
)
```

## Technische Architektur

### Backend

| Datei | Funktion |
|:---|:---|
| `app/core/models.py` | `Plan`, `Subscription`, `TenantAddon`, `UsageRecord` Modelle |
| `app/core/feature_gates.py` | `FeatureGate` Klasse + `seed_default_plans()` |
| `app/gateway/billing.py` | Stripe Checkout, Portal, Webhooks, Plan-Wechsel, Add-on-Checkout |
| `app/gateway/admin.py` | `/admin/permissions`, `/admin/billing/*` Endpoints |

### Frontend

| Datei | Funktion |
|:---|:---|
| `frontend/lib/permissions.ts` | `usePermissions()` Hook mit Plan, Usage, LLM, Connectors, Add-ons |
| `frontend/app/pricing/PricingClient.tsx` | Öffentliche Pricing-Seite mit Vergleichstabelle |
| `frontend/app/settings/billing/page.tsx` | Billing-Dashboard mit Usage-Tracking und Add-on-Verwaltung |
| `frontend/components/Sidebar.tsx` | Plan-Indikator, Upgrade-CTA, Feature-Locks |
| `frontend/components/FeatureGate.tsx` | `<FeatureGate>` und `<UpgradePrompt>` Komponenten |

### Datenbank-Migrationen

```bash
docker compose exec ariia-core alembic upgrade head
```

Relevante Migrationen:
- `2026_02_24_pricing_overhaul.py` — Plan-Modell, Add-on-Tabelle, Usage-Erweiterung
- `2026_02_24_plan_feature_flags.py` — Feature-Flags auf Plan-Modell

### Seed-Daten

```python
from app.core.feature_gates import seed_default_plans
await seed_default_plans(session)
```

Erstellt die 4 Pläne (Starter, Professional, Business, Enterprise) mit allen Limits, Features, LLM-Konfiguration und Overage-Preisen.
