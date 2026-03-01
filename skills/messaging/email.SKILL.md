# Skill: E-Mail Messaging (SMTP + Postmark)

**Integration:** E-Mail (SMTP/IMAP + Postmark API)
**Kategorie:** Messaging
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht den vollständigen E-Mail-Versand und -Empfang. Du kannst E-Mails über SMTP (eigener Mailserver) oder Postmark (Transactional Email Service) senden, Template-E-Mails verschicken und eingehende E-Mails verarbeiten. Tracking für Opens und Bounces ist über Postmark verfügbar.

---

## Capabilities

### `messaging_send_email(to_email: str, subject: str, body: str)`

**Beschreibung:** Sendet eine Plain-Text-E-Mail über den konfigurierten SMTP-Server.

**Beispiel:** `messaging_send_email(to_email="kunde@example.com", subject="Ihre Anfrage", body="Vielen Dank für Ihre Nachricht...")`

**Regeln:**
- Alle drei Parameter sind erforderlich.
- Der Betreff darf keine Zeilenumbrüche enthalten (werden automatisch bereinigt).
- Absender wird aus der Tenant-Konfiguration geladen.

---

### `messaging_send_html_email(to_email: str, subject: str, html_body: str, text_body: str?)`

**Beschreibung:** Sendet eine HTML-E-Mail über SMTP. Optional mit Plain-Text-Fallback.

**Regeln:**
- `html_body` ist erforderlich.
- Wenn `text_body` angegeben wird, wird eine Multipart-E-Mail erstellt.
- HTML sollte inline CSS verwenden für beste Kompatibilität.

---

### `messaging_send_postmark(to_email: str, subject: str, body: str?, html_body: str?)`

**Beschreibung:** Sendet eine E-Mail über die Postmark API mit hoher Zustellbarkeit.

**Regeln:**
- Mindestens `body` oder `html_body` muss angegeben werden.
- Postmark hat eine maximale E-Mail-Größe von 10 MB.
- Verwende Postmark für transaktionale E-Mails (Bestätigungen, Benachrichtigungen).

---

### `messaging_send_template_email(to_email: str, template_alias: str, template_model: dict)`

**Beschreibung:** Sendet eine Postmark-Template-E-Mail mit dynamischen Variablen.

**Beispiel:** `messaging_send_template_email(to_email="kunde@example.com", template_alias="welcome", template_model={"name": "Max", "company": "ARIIA"})`

**Regeln:**
- `template_alias` muss einem existierenden Postmark-Template entsprechen.
- `template_model` enthält die Variablen für das Template.

---

### `messaging_receive_email(payload: dict)`

**Beschreibung:** Verarbeitet eine eingehende E-Mail aus dem Postmark Inbound Webhook.

**Regeln:**
- Wird automatisch vom Gateway aufgerufen.
- Extrahiert Absender, Betreff, Text, HTML und Anhänge.

---

### `messaging_track_opens(payload: dict)`

**Beschreibung:** Verarbeitet ein Open-Tracking-Event von Postmark.

**Regeln:**
- Wird automatisch vom Webhook-Handler aufgerufen.
- Enthält Informationen über Client, OS, Standort und Zeitpunkt.

---

### `messaging_track_bounces(payload: dict)`

**Beschreibung:** Verarbeitet eine Bounce-Benachrichtigung von Postmark.

**Regeln:**
- Bounces können zu einer Deaktivierung der E-Mail-Adresse führen.
- Hard Bounces sollten die Adresse permanent markieren.
- Soft Bounces können nach einer Wartezeit erneut versucht werden.

---

## Allgemeine Regeln

1. **Zustellbarkeit:** Verwende Postmark für wichtige transaktionale E-Mails (höhere Zustellrate als SMTP).
2. **Datenschutz:** E-Mail-Adressen sind PII – nicht in Logs im Klartext anzeigen.
3. **Bounce-Handling:** Bei Hard Bounces die E-Mail-Adresse als ungültig markieren.
4. **Rate Limits:** SMTP-Server haben provider-spezifische Limits. Postmark gibt 429 bei Überschreitung zurück.
5. **Sprache:** Antworte immer in der Sprache des Nutzers.
6. **Templates:** Bevorzuge Template-E-Mails für wiederkehrende Nachrichten (konsistentes Branding).
