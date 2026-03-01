# Skill: SMS & Voice (Twilio)

**Integration:** Twilio (SMS + Voice)
**Kategorie:** Messaging, Voice
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht SMS-Kommunikation und Voice-Anrufe über Twilio. Du kannst SMS senden und empfangen, ausgehende Anrufe initiieren, TwiML-Antworten generieren und Call-Status-Updates verarbeiten.

---

## Capabilities

### `messaging_send_sms(to: str, body: str, media_url: str?)`

**Beschreibung:** Sendet eine SMS-Nachricht über Twilio.

**Beispiel:** `messaging_send_sms(to="+491234567890", body="Ihr Termin ist morgen um 10:00 Uhr.")`

**Regeln:**
- `to` muss im E.164-Format sein (z.B. +491234567890).
- `body` darf maximal 1.600 Zeichen lang sein (wird sonst in Segmente aufgeteilt).
- `media_url` ist optional und ermöglicht MMS-Versand (nur in unterstützten Regionen).
- Rate Limits: 1 MPS für Long Codes, 3 MPS für Toll-Free, 100 MPS für Short Codes.

---

### `messaging_receive_sms(payload: dict)`

**Beschreibung:** Verarbeitet eine eingehende SMS aus dem Twilio-Webhook.

**Regeln:**
- Wird automatisch vom Gateway aufgerufen.
- Extrahiert Absender, Empfänger, Nachrichtentext und Medien-Anhänge.

---

### `messaging_sms_status(payload: dict)`

**Beschreibung:** Verarbeitet ein SMS-Status-Update von Twilio.

**Status-Werte:** queued, sending, sent, delivered, undelivered, failed

---

### `voice_call_outbound(to: str, twiml_url: str?, twiml: str?)`

**Beschreibung:** Initiiert einen ausgehenden Sprachanruf über Twilio.

**Beispiel:** `voice_call_outbound(to="+491234567890", twiml="<Response><Say>Hallo, hier ist ARIIA.</Say></Response>")`

**Regeln:**
- Entweder `twiml_url` (URL zu TwiML-Dokument) oder `twiml` (inline TwiML) ist erforderlich.
- Anrufe erfordern eine verifizierte Twilio-Telefonnummer.
- **WICHTIG:** Ausgehende Anrufe erfordern explizite Zustimmung des Nutzers.

---

### `voice_call_twiml(action: str, text: str?, language: str?, voice: str?)`

**Beschreibung:** Generiert eine TwiML-Antwort für die Anrufsteuerung.

**Aktionen:**
- `say` – Text vorlesen (Standard: Deutsch, Polly.Vicki)
- `play` – Audio-Datei abspielen
- `gather` – Sprach-/Tastatureingabe sammeln
- `record` – Anruf aufnehmen
- `dial` – Weiterleitung an eine Nummer

**Regeln:**
- Standard-Sprache: "de-DE"
- Standard-Stimme: "Polly.Vicki" (Amazon Polly)
- Aufnahmen sind maximal 120 Sekunden lang.

---

### `voice_call_status(payload: dict)`

**Beschreibung:** Verarbeitet ein Voice-Call-Status-Update von Twilio.

**Status-Werte:** queued, ringing, in-progress, completed, busy, no-answer, canceled, failed

---

## Allgemeine Regeln

1. **Einwilligung:** SMS und Anrufe erfordern die vorherige Einwilligung des Empfängers (DSGVO/TCPA).
2. **Rate Limits:** Beachte die Twilio-Rate-Limits je nach Nummerntyp.
3. **Datenschutz:** Telefonnummern sind PII – nicht in Logs im Klartext anzeigen.
4. **Kosten:** Jede SMS und jeder Anruf verursacht Kosten – sparsam einsetzen.
5. **Sprache:** Standard-Sprache für TTS ist Deutsch (de-DE).
6. **Notfall:** Bei Notfall-Erkennung sofort den Telegram-Alert-Kanal benachrichtigen.
