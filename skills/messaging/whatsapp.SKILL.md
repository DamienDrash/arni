# Skill: WhatsApp Business Messaging

**Integration:** WhatsApp (Meta Cloud API / WAHA Bridge)
**Kategorie:** Messaging
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht die vollständige WhatsApp-Kommunikation mit Endkunden. Du kannst Textnachrichten, Template-Nachrichten, interaktive Nachrichten (Buttons, Listen) und Medien senden. Zusätzlich stehen WhatsApp Flows für Buchungsbestätigungen, Terminauswahl und Kündigungsbestätigungen zur Verfügung.

---

## Capabilities

### `messaging_send_text(to: str, body: str)`

**Beschreibung:** Sendet eine Textnachricht an einen WhatsApp-Nutzer.

**Beispiel:** Wenn der Agent eine Antwort an den Kunden senden soll → `messaging_send_text(to="491234567890", body="Vielen Dank für Ihre Nachricht!")`

**Regeln:**
- `to` muss eine gültige Telefonnummer im internationalen Format sein (z.B. 491234567890).
- `body` darf maximal 4.096 Zeichen lang sein.
- Nachrichten außerhalb des 24-Stunden-Fensters erfordern eine Template-Nachricht.

---

### `messaging_send_template(to: str, template_name: str, language_code: str?, components: list?)`

**Beschreibung:** Sendet eine genehmigte Template-Nachricht. Templates werden für die Initiierung von Konversationen außerhalb des 24-Stunden-Fensters benötigt.

**Beispiel:** `messaging_send_template(to="491234567890", template_name="welcome_message", language_code="de")`

**Regeln:**
- Der Template-Name muss einem genehmigten Meta-Template entsprechen.
- `language_code` ist standardmäßig "de".
- `components` sind optional und enthalten Header-, Body- oder Button-Parameter.

---

### `messaging_send_interactive(to: str, interactive: dict)`

**Beschreibung:** Sendet eine interaktive Nachricht mit Buttons oder Listen.

**Regeln:**
- Das `interactive` Objekt muss dem WhatsApp Interactive Message Format entsprechen.
- Maximal 3 Buttons pro Nachricht.
- Listen können bis zu 10 Einträge enthalten.

---

### `messaging_send_media(to: str, media_type: str, media_url: str?, media_id: str?, caption: str?)`

**Beschreibung:** Sendet eine Mediennachricht (Bild, Dokument, Audio, Video).

**Regeln:**
- `media_type` muss "image", "document", "audio" oder "video" sein.
- Entweder `media_url` (öffentliche URL) oder `media_id` (Meta Media ID) muss angegeben werden.
- Maximale Dateigröße: 16 MB für Medien, 100 MB für Dokumente.

---

### `messaging_mark_read(message_id: str)`

**Beschreibung:** Markiert eine empfangene Nachricht als gelesen (blaue Häkchen).

**Regeln:**
- Sollte nach der Verarbeitung jeder eingehenden Nachricht aufgerufen werden.
- Nicht-kritisch – Fehler werden ignoriert.

---

### `messaging_verify_webhook(payload_body: bytes, signature_header: str)`

**Beschreibung:** Verifiziert die HMAC-SHA256-Signatur eines Meta-Webhooks.

**Regeln:**
- Wird automatisch vom Gateway aufgerufen, nicht vom Agent direkt.

---

### `messaging_flow_booking(to: str, course_name: str, time_slot: str, date: str, studio_name: str?)`

**Beschreibung:** Sendet eine Buchungsbestätigung als interaktive Nachricht mit Ja/Nein-Buttons.

**Beispiel:** `messaging_flow_booking(to="491234567890", course_name="Yoga", time_slot="10:00", date="2026-03-05")`

**Regeln:**
- Alle Parameter außer `studio_name` sind erforderlich.
- Der Nutzer antwortet mit "book_confirm" oder "book_cancel".

---

### `messaging_flow_time_slots(to: str, available_slots: list, course_name: str, studio_name: str?)`

**Beschreibung:** Sendet eine Terminauswahl als interaktive Liste.

**Regeln:**
- `available_slots` ist eine Liste von Dicts mit 'id', 'time', 'spots' Keys.
- Maximal 10 Slots werden angezeigt (WhatsApp-Limit).

---

### `messaging_flow_cancellation(to: str)`

**Beschreibung:** Sendet eine Kündigungsbestätigung mit Alternativen (Pause, Downgrade, Bonus-Monat).

**Regeln:**
- Folgt dem Bezos One-Way-Door Principle: Destruktive Aktionen erfordern explizite Bestätigung.
- Biete immer Alternativen an, bevor die Kündigung bestätigt wird.

---

## Allgemeine Regeln

1. **24-Stunden-Fenster:** WhatsApp erlaubt freie Nachrichten nur innerhalb von 24 Stunden nach der letzten Nutzer-Nachricht. Danach sind nur Template-Nachrichten erlaubt.
2. **Rate Limits:** Maximal 80 Nachrichten pro Sekunde pro Telefonnummer.
3. **Datenschutz:** Telefonnummern sind PII – niemals in Logs oder Antworten im Klartext anzeigen.
4. **Fehlerbehandlung:** Bei "WHATSAPP_NOT_CONNECTED" den Nutzer informieren, dass die WhatsApp-Verbindung neu hergestellt werden muss.
5. **Sprache:** Antworte immer in der Sprache des Nutzers.
6. **Bestätigung:** Bei Flows (Buchung, Kündigung) immer auf die Nutzer-Antwort warten, bevor die Aktion ausgeführt wird.
