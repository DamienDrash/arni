# Skill: Mollie Payment

**Integration:** Mollie API v2
**Kategorie:** Payment & Billing
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht die Verarbeitung von Zahlungen über Mollie. Ideal für europäische Zahlungsmethoden wie iDEAL, SEPA-Lastschrift, Bancontact, Sofort und Kreditkarte. Du kannst Zahlungen erstellen, Rückerstattungen durchführen, Abonnements verwalten und verfügbare Zahlungsmethoden abfragen.

---

## Capabilities

### `payment.create(amount: str, description: str, currency: str?, method: str?, redirect_url: str?, webhook_url: str?)`

**Beschreibung:** Erstellt eine Mollie-Zahlung. Der Kunde wird zur Zahlungsseite weitergeleitet.

**Beispiel:** `payment.create(amount="29.99", description="Pro Plan Monat März", method="ideal")`

**Regeln:**
- `amount` und `description` sind erforderlich.
- `currency` ist standardmäßig "EUR".
- `method` kann "ideal", "creditcard", "bancontact", "sofort", "sepadirectdebit", etc. sein.
- Die `checkout_url` muss dem Kunden gesendet werden.

---

### `payment.status(payment_id: str)`

**Beschreibung:** Ruft den aktuellen Status einer Mollie-Zahlung ab.

**Regeln:**
- Mögliche Status: open, canceled, pending, authorized, expired, failed, paid.
- Gibt auch Zeitstempel für paid_at und expired_at zurück.

---

### `payment.refund(payment_id: str, amount: str?, currency: str?, description: str?)`

**Beschreibung:** Erstattet eine Mollie-Zahlung (vollständig oder teilweise).

**Regeln:**
- Ohne `amount` wird eine vollständige Rückerstattung durchgeführt.
- Mit `amount` wird eine Teilrückerstattung erstellt.
- Nur bezahlte Zahlungen können erstattet werden.

---

### `payment.list(limit: int?, from_id: str?)`

**Beschreibung:** Listet Mollie-Zahlungen auf.

**Regeln:**
- `limit` ist standardmäßig 25 (max. 250).
- `from_id` für Pagination verwenden.

---

### `payment.methods.list(amount: str?, currency: str?, locale: str?)`

**Beschreibung:** Listet die verfügbaren Zahlungsmethoden für das Mollie-Konto auf.

**Regeln:**
- `locale` ist standardmäßig "de_DE".
- Mit `amount` werden nur Methoden angezeigt, die für diesen Betrag verfügbar sind.
- Gibt auch Mindest- und Höchstbeträge pro Methode zurück.

---

### `payment.subscription.create(customer_id: str, amount: str, interval: str, description: str, start_date: str?)`

**Beschreibung:** Erstellt ein Mollie-Abonnement für einen Kunden.

**Regeln:**
- `interval` im Format "1 month", "3 months", "1 year", etc.
- Der Kunde muss bereits ein gültiges Mandat haben (erste Zahlung über Mollie).
- `start_date` im Format "YYYY-MM-DD".

---

### `payment.subscription.cancel(customer_id: str, subscription_id: str)`

**Beschreibung:** Kündigt ein Mollie-Abonnement.

---

### `payment.subscription.list(customer_id: str)`

**Beschreibung:** Listet alle Abonnements eines Mollie-Kunden auf.

---

## Allgemeine Regeln

1. **Konfiguration:** Mollie API Key muss in den Integrationseinstellungen hinterlegt sein.
2. **Test vs. Live:** Keys die mit "test_" beginnen arbeiten im Testmodus, "live_" im Produktivmodus.
3. **Europäischer Fokus:** Mollie ist besonders stark bei europäischen Zahlungsmethoden (iDEAL, SEPA, Bancontact).
4. **Webhooks:** Mollie sendet Statusänderungen an die konfigurierte Webhook-URL. Immer eine webhook_url angeben.
5. **Sicherheit:** API Keys niemals in Logs oder Antworten anzeigen.
6. **Mandate:** Für wiederkehrende Zahlungen muss der Kunde zuerst eine initiale Zahlung durchführen, um ein Mandat zu erstellen.
