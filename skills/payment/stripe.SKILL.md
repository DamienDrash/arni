# Skill: Stripe Payment & Billing

**Integration:** Stripe (API 2022-11-15)
**Kategorie:** Payment & Billing
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht die vollständige Verwaltung von Zahlungen, Abonnements und Abrechnungen über Stripe. Du kannst Checkout-Sessions erstellen, Abonnements verwalten (Upgrade/Downgrade/Kündigung), Rechnungen abrufen, Usage-basierte Abrechnung tracken und Plan-Limits durchsetzen.

---

## Capabilities

### `payment.checkout.create(price_id: str, success_url: str?, cancel_url: str?, customer_email: str?, mode: str?)`

**Beschreibung:** Erstellt eine Stripe Checkout Session für einen Kauf oder ein Abonnement.

**Beispiel:** `payment.checkout.create(price_id="price_1234", customer_email="kunde@firma.de")`

**Regeln:**
- `price_id` muss eine gültige Stripe Price ID sein.
- `mode` ist standardmäßig "subscription". Für Einmalzahlungen "payment" verwenden.
- Die Session-URL wird zurückgegeben und kann dem Kunden gesendet werden.

---

### `payment.subscription.manage(action: str, new_price_id: str?, proration_behavior: str?)`

**Beschreibung:** Verwaltet ein bestehendes Abonnement – Upgrade, Downgrade, Kündigung oder Reaktivierung.

**Beispiel:** `payment.subscription.manage(action="upgrade", new_price_id="price_pro_monthly")`

**Regeln:**
- `action` muss "upgrade", "downgrade", "cancel" oder "reactivate" sein.
- Für Upgrade/Downgrade ist `new_price_id` erforderlich.
- Kündigung erfolgt zum Ende der aktuellen Abrechnungsperiode (cancel_at_period_end).
- Proration wird standardmäßig berechnet. Mit `proration_behavior="none"` deaktivierbar.

---

### `payment.subscription.status()`

**Beschreibung:** Ruft den aktuellen Abonnement-Status eines Tenants ab.

**Regeln:**
- Gibt Plan-Name, Status, Stripe Customer ID und Abrechnungsperiode zurück.
- Kein Stripe-API-Call nötig – liest aus der lokalen Datenbank.

---

### `payment.invoice.list(limit: int?, status: str?)`

**Beschreibung:** Listet die Rechnungen eines Tenants aus Stripe auf.

**Regeln:**
- `limit` ist standardmäßig 10.
- `status` kann "paid", "open", "draft" oder "void" sein.
- Gibt Links zu gehosteten Rechnungen und PDFs zurück.

---

### `payment.customer.create(email: str?, name: str?)`

**Beschreibung:** Erstellt einen neuen Stripe-Kunden oder ruft den bestehenden ab.

**Regeln:**
- Wenn bereits ein Stripe-Kunde für den Tenant existiert, wird dieser zurückgegeben.
- Email und Name werden automatisch aus den Tenant-Daten ermittelt, wenn nicht angegeben.

---

### `billing.usage.track(usage_type: str, quantity: int?, idempotency_key: str?)`

**Beschreibung:** Trackt eine Nutzungseinheit für die verbrauchsbasierte Abrechnung.

**Regeln:**
- `usage_type` muss einer der folgenden sein: conversation, api_call, token_input, token_output, knowledge_query, voice_minute, email_sent.
- `idempotency_key` verhindert Doppelzählung.
- Nutzt Redis für Echtzeit-Counter.

---

### `billing.usage.get(usage_type: str?, period: str?)`

**Beschreibung:** Ruft aktuelle Nutzungszähler für einen Tenant ab.

**Regeln:**
- Ohne `usage_type` werden alle Zähler zurückgegeben.
- `period` im Format "YYYY-MM" (Standard: aktueller Monat).

---

### `billing.plan.enforce(check_type: str, feature: str?, tier: str?, current_count: int?)`

**Beschreibung:** Prüft Plan-Limits und Feature-Gates.

**Regeln:**
- `check_type` muss "feature", "conversation", "api", "integration" oder "channel" sein.
- Für "feature" ist der `feature`-Name erforderlich.
- Für "integration" und "channel" ist `current_count` erforderlich.

---

### `billing.plan.compare()`

**Beschreibung:** Gibt einen Vergleich aller Plan-Tiers für die Preisseite zurück.

**Regeln:**
- Gibt Limits und Features für Free, Starter, Professional, Business und Enterprise zurück.
- Wird für die Pricing-Page und Plan-Auswahl verwendet.

---

## Allgemeine Regeln

1. **Stripe-Konfiguration:** Stripe muss in den Integrationseinstellungen aktiviert und der Secret Key hinterlegt sein. Bei Fehler "STRIPE_NOT_CONFIGURED" den Tenant-Admin informieren.
2. **Idempotenz:** Webhook-Events und Usage-Records werden mit Idempotency-Keys dedupliziert.
3. **Proration:** Bei Plan-Änderungen wird standardmäßig eine anteilige Berechnung erstellt.
4. **Sicherheit:** Stripe Secret Keys sind hochsensibel – niemals in Logs oder Antworten anzeigen.
5. **Fehlerbehandlung:** Bei Stripe-API-Fehlern den HTTP-Status und die Fehlermeldung strukturiert zurückgeben.
6. **Kündigung:** Folgt dem Bezos One-Way-Door Principle – immer Alternativen anbieten und explizite Bestätigung einholen.
