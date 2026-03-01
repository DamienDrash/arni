# Skill: PayPal Payment

**Integration:** PayPal REST API v2
**Kategorie:** Payment & Billing
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht die Verarbeitung von Zahlungen über PayPal. Du kannst Bestellungen erstellen und erfassen, Abonnements verwalten, Webhooks verarbeiten und Auszahlungen an Empfänger senden.

---

## Capabilities

### `payment.order.create(amount: str, currency: str?, description: str?, return_url: str?, cancel_url: str?)`

**Beschreibung:** Erstellt eine PayPal-Bestellung. Der Kunde wird zur PayPal-Genehmigungsseite weitergeleitet.

**Beispiel:** `payment.order.create(amount="29.99", currency="EUR", description="Pro Plan")`

**Regeln:**
- `amount` ist erforderlich (als String, z.B. "29.99").
- `currency` ist standardmäßig "EUR".
- Die `approval_url` muss dem Kunden gesendet werden, damit er die Zahlung genehmigen kann.

---

### `payment.order.capture(order_id: str)`

**Beschreibung:** Erfasst eine genehmigte PayPal-Bestellung und schließt die Zahlung ab.

**Regeln:**
- Nur nach Genehmigung durch den Kunden aufrufen.
- Gibt die Capture-ID und den Betrag zurück.

---

### `payment.order.details(order_id: str)`

**Beschreibung:** Ruft Details einer PayPal-Bestellung ab.

---

### `payment.subscription.create(plan_id: str, subscriber: dict?)`

**Beschreibung:** Erstellt ein PayPal-Abonnement basierend auf einem Billing Plan.

**Regeln:**
- `plan_id` muss eine gültige PayPal Billing Plan ID sein.
- Die `approval_url` muss dem Kunden gesendet werden.

---

### `payment.subscription.cancel(subscription_id: str, reason: str?)`

**Beschreibung:** Kündigt ein PayPal-Abonnement.

**Regeln:**
- Immer einen Grund angeben für bessere Nachverfolgung.
- Kündigung ist sofort wirksam (kein cancel_at_period_end wie bei Stripe).

---

### `payment.subscription.details(subscription_id: str)`

**Beschreibung:** Ruft Details eines PayPal-Abonnements ab.

---

### `payment.webhook.process(event_type: str, resource: dict)`

**Beschreibung:** Verarbeitet ein PayPal-Webhook-Event.

**Regeln:**
- Unterstützte Events: PAYMENT.CAPTURE.COMPLETED, BILLING.SUBSCRIPTION.CREATED/ACTIVATED/CANCELLED.
- Unbekannte Events werden als "unhandled" markiert.

---

### `payment.payout.create(recipient_email: str, amount: str, currency: str?, note: str?)`

**Beschreibung:** Erstellt eine Auszahlung an einen PayPal-Empfänger.

**Regeln:**
- `recipient_email` muss eine gültige PayPal-Email sein.
- Für Affiliate-Auszahlungen und Partner-Provisionen verwenden.

---

## Allgemeine Regeln

1. **Konfiguration:** PayPal Client ID und Secret müssen in den Integrationseinstellungen hinterlegt sein.
2. **Sandbox vs. Live:** Standardmäßig wird die Sandbox verwendet. Für Live-Zahlungen muss `paypal_sandbox` auf "false" gesetzt werden.
3. **OAuth 2.0:** Access Tokens werden automatisch per Client Credentials Grant bezogen.
4. **Sicherheit:** Client Secrets niemals in Logs oder Antworten anzeigen.
5. **Webhooks:** PayPal-Webhook-Signatur sollte vor der Verarbeitung verifiziert werden.
