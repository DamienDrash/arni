# ARIIA – Stripe Billing Setup Guide

> Vollständige Anleitung zur Konfiguration der Stripe-Integration für die ARIIA SaaS-Plattform.

---

## Inhaltsverzeichnis

1. [Übersicht](#übersicht)
2. [Voraussetzungen](#voraussetzungen)
3. [Schritt 1: Stripe-Konto einrichten](#schritt-1-stripe-konto-einrichten)
4. [Schritt 2: API-Keys konfigurieren](#schritt-2-api-keys-konfigurieren)
5. [Schritt 3: Produkte & Preise anlegen](#schritt-3-produkte--preise-anlegen)
6. [Schritt 4: Webhook einrichten](#schritt-4-webhook-einrichten)
7. [Schritt 5: Stripe im ARIIA-Dashboard aktivieren](#schritt-5-stripe-im-ariia-dashboard-aktivieren)
8. [Schritt 6: Checkout testen](#schritt-6-checkout-testen)
9. [Go-Live Checkliste](#go-live-checkliste)
10. [Architektur-Referenz](#architektur-referenz)
11. [Troubleshooting](#troubleshooting)

---

## Übersicht

ARIIA verwendet Stripe für die Abrechnung der SaaS-Pläne (Starter, Pro, Enterprise). Die Integration umfasst:

| Komponente | Beschreibung |
|:---|:---|
| **Stripe Checkout** | Hosted Payment Page für neue Abonnements |
| **Customer Portal** | Self-Service für Abo-Verwaltung (Kündigung, Zahlungsmethode ändern) |
| **Webhooks** | Event-driven Subscription-Status-Synchronisation |
| **Feature Gates** | Plan-basierte Zugriffskontrolle auf Kanäle und Features |

### Datenfluss

```
Tenant-Admin → Checkout-Session → Stripe Checkout (hosted)
                                        ↓
                                  Zahlung erfolgreich
                                        ↓
Stripe → Webhook (POST /admin/billing/webhook) → DB Update (Subscription)
                                                       ↓
                                                 Feature Gates aktiv
```

---

## Voraussetzungen

- ARIIA-Instanz läuft (Docker Compose oder manuell)
- Zugang zum [Stripe Dashboard](https://dashboard.stripe.com)
- Öffentlich erreichbare URL für Webhooks (oder [Stripe CLI](https://stripe.com/docs/stripe-cli) für lokale Entwicklung)

---

## Schritt 1: Stripe-Konto einrichten

1. Registriere dich unter [https://dashboard.stripe.com/register](https://dashboard.stripe.com/register)
2. Bestätige deine E-Mail-Adresse
3. Für Produktionsbetrieb: Vervollständige die Kontoverifizierung unter **Settings → Business details**

> **Hinweis:** Für Entwicklung und Tests reicht der Test-Modus. Alle Schritte können zuerst im Test-Modus durchgeführt werden.

---

## Schritt 2: API-Keys konfigurieren

### Keys finden

Navigiere zu [https://dashboard.stripe.com/test/apikeys](https://dashboard.stripe.com/test/apikeys) (Test) oder [https://dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys) (Live).

Du benötigst:

| Key | Format | Verwendung |
|:---|:---|:---|
| **Publishable Key** | `pk_test_...` / `pk_live_...` | Frontend (optional, für Stripe.js) |
| **Secret Key** | `sk_test_...` / `sk_live_...` | Backend (Checkout, Customer Portal, API-Calls) |

### Keys in ARIIA eintragen

Es gibt **zwei Wege**, die Keys zu konfigurieren:

#### Option A: Über das ARIIA-Dashboard (empfohlen)

1. Melde dich als **System-Admin** im Studio Deck an
2. Navigiere zu **Plans** (Seitenleiste)
3. Scrolle zum Abschnitt **Stripe Connector (global)**
4. Trage ein:
   - **Mode:** `test` (oder `live` für Produktion)
   - **Enabled:** `enabled`
   - **Publishable Key:** `pk_test_...`
   - **Secret Key:** `sk_test_...`
   - **Webhook Secret:** (wird in Schritt 4 generiert)
5. Klicke **Connector speichern**

#### Option B: Über die API (für Automatisierung)

```bash
# Stripe-Connector konfigurieren
curl -X PUT "${GATEWAY_URL}/admin/billing/connectors" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "stripe": {
      "enabled": true,
      "mode": "test",
      "publishable_key": "pk_test_...",
      "secret_key": "sk_test_...",
      "webhook_secret": "whsec_..."
    }
  }'
```

### Verbindung testen

```bash
# Über die API
curl -X POST "${GATEWAY_URL}/admin/billing/connectors/stripe/test" \
  -H "Authorization: Bearer ${TOKEN}"

# Erwartete Antwort:
# {"status":"ok","provider":"stripe","mode":"test","account_id":"acct_...","charges_enabled":true}
```

Oder im Dashboard: Klicke **Verbindung testen** im Stripe-Connector-Bereich.

---

## Schritt 3: Produkte & Preise anlegen

Jeder ARIIA-Plan benötigt ein Stripe-Produkt mit einem monatlichen Preis. Die `price_id` muss dann in der ARIIA-Datenbank hinterlegt werden.

### Option A: Automatisch per Script (empfohlen)

```bash
# Im Docker-Container:
docker compose exec ariia-core python scripts/seed_stripe_products.py

# Oder lokal mit Umgebungsvariable:
STRIPE_SECRET_KEY=sk_test_... python scripts/seed_stripe_products.py

# Nur Vorschau (kein API-Call):
python scripts/seed_stripe_products.py --dry-run

# Vorhandene Price-IDs überschreiben:
python scripts/seed_stripe_products.py --force
```

Das Script erstellt automatisch:

| Plan | Produkt | Preis |
|:---|:---|:---|
| Starter | ARIIA Starter | €149/Monat |
| Pro | ARIIA Pro | €349/Monat |
| Enterprise | ARIIA Enterprise | €999/Monat |

### Option B: Manuell im Stripe Dashboard

1. Gehe zu [Products](https://dashboard.stripe.com/test/products)
2. Erstelle für jeden Plan ein Produkt:
   - **Name:** z.B. "ARIIA Pro"
   - **Pricing:** Recurring, Monthly
   - **Amount:** z.B. €349.00
3. Nach dem Erstellen: Kopiere die **Price ID** (Format: `price_...`)

### Option C: Über die ARIIA-API

```bash
# Aktuelle Plans mit stripe_price_id anzeigen:
curl "${GATEWAY_URL}/admin/billing/plans/db" \
  -H "Authorization: Bearer ${TOKEN}"

# Price ID für einen Plan setzen:
curl -X PUT "${GATEWAY_URL}/admin/billing/plans/db/pro/stripe-price" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"stripe_price_id": "price_1Abc..."}'
```

### Verknüpfung prüfen

```bash
# Alle Plans mit ihren Stripe-Verknüpfungen auflisten:
curl "${GATEWAY_URL}/admin/billing/plans/db" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
```

Jeder Plan sollte eine `stripe_price_id` haben, die nicht `null` ist:

```json
[
  {"slug": "starter",    "stripe_price_id": "price_1Abc..."},
  {"slug": "pro",        "stripe_price_id": "price_2Def..."},
  {"slug": "enterprise", "stripe_price_id": "price_3Ghi..."}
]
```

---

## Schritt 4: Webhook einrichten

Webhooks sind **essentiell** — ohne sie wird der Subscription-Status nach einer Zahlung nicht aktualisiert.

### Webhook-URL

```
https://<deine-domain>/admin/billing/webhook
```

Beispiel: `https://services.frigew.ski/arni/admin/billing/webhook`

### Im Stripe Dashboard

1. Gehe zu [Webhooks](https://dashboard.stripe.com/test/webhooks)
2. Klicke **Add endpoint**
3. Trage die Webhook-URL ein
4. Wähle folgende Events:

| Event | Beschreibung |
|:---|:---|
| `checkout.session.completed` | Checkout erfolgreich → Abo aktivieren |
| `customer.subscription.updated` | Abo-Änderung (Upgrade/Downgrade) |
| `customer.subscription.deleted` | Abo gekündigt |
| `invoice.payment_succeeded` | Zahlung erfolgreich → Periode erneuern |
| `invoice.paid` | Rechnung bezahlt |
| `invoice.payment_failed` | Zahlung fehlgeschlagen → Status "past_due" |

5. Klicke **Add endpoint**
6. Kopiere das **Signing Secret** (`whsec_...`)
7. Trage es in ARIIA ein (Dashboard oder API, siehe Schritt 2)

### Für lokale Entwicklung: Stripe CLI

```bash
# Stripe CLI installieren
brew install stripe/stripe-cli/stripe  # macOS
# oder: https://stripe.com/docs/stripe-cli#install

# Login
stripe login

# Webhook-Events an lokalen Server weiterleiten
stripe listen --forward-to localhost:8000/admin/billing/webhook

# Das CLI zeigt das Signing Secret an:
# > Ready! Your webhook signing secret is whsec_...
```

---

## Schritt 5: Stripe im ARIIA-Dashboard aktivieren

### Zusammenfassung der Settings

Nach Abschluss der Schritte 2–4 sollten folgende Settings in der DB gesetzt sein:

| Setting-Key | Wert | Beschreibung |
|:---|:---|:---|
| `billing_stripe_enabled` | `true` | Stripe-Integration aktiv |
| `billing_stripe_mode` | `test` oder `live` | Betriebsmodus |
| `billing_stripe_publishable_key` | `pk_test_...` | Frontend-Key |
| `billing_stripe_secret_key` | `sk_test_...` | Backend-Key (verschlüsselt gespeichert) |
| `billing_stripe_webhook_secret` | `whsec_...` | Webhook-Signaturprüfung (verschlüsselt) |

### Verifizierung

1. **API-Test:**
   ```bash
   curl -X POST "${GATEWAY_URL}/admin/billing/connectors/stripe/test" \
     -H "Authorization: Bearer ${TOKEN}"
   ```

2. **Plans-Check:**
   ```bash
   curl "${GATEWAY_URL}/admin/billing/plans/db" \
     -H "Authorization: Bearer ${TOKEN}"
   ```
   → Alle Plans sollten eine `stripe_price_id` haben.

3. **Webhook-Test:**
   Im Stripe Dashboard unter Webhooks → **Send test webhook** → `checkout.session.completed`

---

## Schritt 6: Checkout testen

### Über das Frontend

1. Melde dich als Tenant-Admin an
2. Navigiere zu **Settings → Abonnement & Nutzung**
3. Klicke auf einen Plan → **"Zu Pro wechseln"**
4. Du wirst zu Stripe Checkout weitergeleitet

### Test-Kreditkarten

| Karte | Nummer | Ergebnis |
|:---|:---|:---|
| Visa (Erfolg) | `4242 4242 4242 4242` | Zahlung erfolgreich |
| Visa (Ablehnung) | `4000 0000 0000 0002` | Zahlung abgelehnt |
| 3D Secure | `4000 0025 0000 3155` | 3D-Secure-Authentifizierung |
| Unzureichende Deckung | `4000 0000 0000 9995` | Insufficient funds |

Verwende ein beliebiges Ablaufdatum in der Zukunft und eine beliebige CVC.

### Über die API

```bash
# 1. Checkout-Session erstellen
curl -X POST "${GATEWAY_URL}/admin/billing/checkout-session" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_slug": "pro",
    "success_url": "https://example.com/success",
    "cancel_url": "https://example.com/cancel"
  }'

# Antwort: {"url": "https://checkout.stripe.com/c/pay/..."}
# → Öffne die URL im Browser

# 2. Customer Portal öffnen (nach aktivem Abo)
curl -X POST "${GATEWAY_URL}/admin/billing/customer-portal" \
  -H "Authorization: Bearer ${TOKEN}"
```

---

## Go-Live Checkliste

Bevor du von Test auf Live wechselst:

- [ ] Stripe-Kontoverifizierung abgeschlossen
- [ ] Live-API-Keys generiert (`sk_live_...`, `pk_live_...`)
- [ ] Produkte & Preise im Live-Modus erstellt (oder Script mit Live-Key ausgeführt)
- [ ] Webhook-Endpoint im Live-Modus erstellt mit neuer `whsec_...`
- [ ] ARIIA-Settings auf Live-Keys aktualisiert
- [ ] `billing_stripe_mode` auf `live` gesetzt
- [ ] Testzahlung mit echter Karte durchgeführt (kleiner Betrag, dann storniert)
- [ ] Customer Portal konfiguriert: [Portal Settings](https://dashboard.stripe.com/settings/billing/portal)
- [ ] Steuern konfiguriert: [Tax Settings](https://dashboard.stripe.com/settings/tax) (falls erforderlich)
- [ ] E-Mail-Benachrichtigungen konfiguriert: [Email Settings](https://dashboard.stripe.com/settings/emails)

---

## Architektur-Referenz

### Relevante Dateien

| Datei | Beschreibung |
|:---|:---|
| `app/gateway/routers/billing.py` | Stripe Checkout, Portal & Webhook-Endpoints |
| `app/gateway/billing.py` | Legacy Billing-Modul (Referenz) |
| `app/gateway/admin.py` | Admin-API: Connector-Config, Plans/DB, Subscription, Usage |
| `app/core/models.py` | DB-Modelle: `Plan`, `Subscription`, `UsageRecord` |
| `app/core/feature_gates.py` | Plan-basierte Feature-Kontrolle + Plan-Seeding |
| `app/gateway/persistence.py` | Settings-Store (verschlüsselte Stripe-Keys) |
| `scripts/seed_stripe_products.py` | Automatisches Anlegen von Stripe-Produkten/Preisen |
| `frontend/app/settings/billing/page.tsx` | Billing-UI für Tenant-Admins |
| `frontend/app/plans/page.tsx` | Plans-Konfiguration & Stripe-Connector (System-Admin) |

### API-Endpoints

| Method | Endpoint | Auth | Beschreibung |
|:---|:---|:---|:---|
| `GET` | `/admin/billing/plans` | — | Öffentlicher Plan-Katalog |
| `GET` | `/admin/billing/plans/db` | System-Admin | DB-Plans mit stripe_price_id |
| `PUT` | `/admin/billing/plans/db/{slug}/stripe-price` | System-Admin | stripe_price_id setzen |
| `POST` | `/admin/billing/checkout-session` | Tenant-Admin | Stripe Checkout starten |
| `POST` | `/admin/billing/customer-portal` | Tenant-Admin | Stripe Portal öffnen |
| `POST` | `/admin/billing/webhook` | — (HMAC) | Stripe Webhook-Empfänger |
| `GET` | `/admin/billing/subscription` | Tenant-Admin | Aktuelles Abo + Plan |
| `GET` | `/admin/billing/usage` | Tenant-Admin | Monatsverbrauch |
| `GET` | `/admin/billing/connectors` | System-Admin | Stripe-Konfiguration lesen |
| `PUT` | `/admin/billing/connectors` | System-Admin | Stripe-Konfiguration schreiben |
| `POST` | `/admin/billing/connectors/stripe/test` | System-Admin | Stripe-Verbindung testen |

### Webhook-Event-Handling

```
checkout.session.completed
  → _on_checkout_completed()
  → Subscription.status = "active", plan_id gesetzt

customer.subscription.updated
  → _on_subscription_event()
  → Status + Abrechnungsperiode synchronisiert

customer.subscription.deleted
  → _on_subscription_event()
  → Subscription.status = "canceled"

invoice.payment_succeeded / invoice.paid
  → _on_invoice_event()
  → Subscription.status = "active", Periode erneuert

invoice.payment_failed
  → _on_invoice_event()
  → Subscription.status = "past_due"
```

---

## Troubleshooting

### "Stripe ist nicht aktiviert" (HTTP 402)

**Ursache:** `billing_stripe_enabled` ist nicht auf `true` gesetzt.
**Lösung:** Im Dashboard unter Plans → Stripe Connector → Enabled auf `enabled` setzen und speichern.

### "Stripe-Secret-Key fehlt" (HTTP 402)

**Ursache:** `billing_stripe_secret_key` ist leer oder nicht gesetzt.
**Lösung:** Secret Key im Dashboard eintragen oder über API setzen.

### "Plan hat keine Stripe Price-ID" (HTTP 422)

**Ursache:** Der Plan in der DB hat kein `stripe_price_id`.
**Lösung:** `seed_stripe_products.py` ausführen oder manuell über die API setzen:
```bash
curl -X PUT "${GATEWAY_URL}/admin/billing/plans/db/pro/stripe-price" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"stripe_price_id": "price_..."}'
```

### Webhook liefert "invalid signature" (HTTP 400)

**Ursache:** `billing_stripe_webhook_secret` stimmt nicht mit dem Stripe-Endpoint überein.
**Lösung:**
1. Prüfe das Signing Secret im Stripe Dashboard unter Webhooks
2. Aktualisiere den Wert in ARIIA

### Subscription-Status wird nach Checkout nicht aktualisiert

**Ursache:** Webhook nicht korrekt konfiguriert oder nicht erreichbar.
**Lösung:**
1. Prüfe im Stripe Dashboard unter Webhooks → **Event deliveries** ob Events ankommen
2. Prüfe die ARIIA-Logs: `docker compose logs ariia-core | grep billing.webhook`
3. Stelle sicher, dass die Webhook-URL öffentlich erreichbar ist

### Lokale Entwicklung: Webhooks funktionieren nicht

**Lösung:** Verwende die Stripe CLI:
```bash
stripe listen --forward-to localhost:8000/admin/billing/webhook
```

---

> **Letzte Aktualisierung:** 2026-02-24 | ARIIA v2.0.0
