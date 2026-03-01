# Skill: Telegram Bot Messaging & Admin

**Integration:** Telegram Bot API
**Kategorie:** Messaging, Admin
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht die vollständige Telegram-Bot-Kommunikation. Du kannst Textnachrichten, Sprachnachrichten und Alerts senden, Kontaktdaten anfordern, Admin-Befehle verarbeiten und Webhooks verwalten. Der Bot dient sowohl der Kundenkommunikation als auch der Admin-Überwachung.

---

## Capabilities

### `messaging_send_text(chat_id: str, text: str, parse_mode: str?, reply_markup: dict?)`

**Beschreibung:** Sendet eine Textnachricht an einen Telegram-Chat.

**Beispiel:** `messaging_send_text(chat_id="123456789", text="Hallo! Wie kann ich helfen?", parse_mode="HTML")`

**Regeln:**
- `chat_id` kann eine User-ID, Gruppen-ID oder Kanal-ID sein.
- `parse_mode` unterstützt "HTML" oder "Markdown" (optional).
- `reply_markup` kann Inline-Keyboards oder Custom-Keyboards enthalten.
- Maximale Nachrichtenlänge: 4.096 Zeichen.

---

### `messaging_send_voice(chat_id: str, voice_path: str, caption: str?)`

**Beschreibung:** Sendet eine Sprachnachricht an einen Telegram-Chat.

**Regeln:**
- `voice_path` muss ein gültiger Dateipfad zu einer OGG/OPUS-Datei sein.
- Maximale Dateigröße: 50 MB.
- Timeout: 60 Sekunden für den Upload.

---

### `messaging_send_alert(message: str, severity: str?, chat_id: str?)`

**Beschreibung:** Sendet einen System-Alert an den Admin-Chat.

**Beispiel:** `messaging_send_alert(message="Redis-Verbindung verloren", severity="error")`

**Regeln:**
- `severity` kann "info", "warning", "error" oder "critical" sein (Standard: "info").
- Ohne `chat_id` wird der konfigurierte Admin-Chat verwendet.
- Alerts werden mit Severity-Emojis formatiert.

---

### `messaging_send_emergency(user_id: str, message_content: str)`

**Beschreibung:** Sendet einen Notfall-Alarm an das Staff-Team (Medic Rule – AGENTS.md §2).

**Regeln:**
- Wird automatisch ausgelöst, wenn Notfall-Keywords erkannt werden.
- User-ID wird maskiert (PII-Schutz).
- Dem Nutzer wird empfohlen, 112 anzurufen.
- **KRITISCH:** Dieser Alert darf NIEMALS unterdrückt werden.

---

### `messaging_send_contact_request(chat_id: str, text: str?)`

**Beschreibung:** Sendet eine Nachricht mit einem Button zum Teilen der Kontaktdaten.

**Regeln:**
- Wird verwendet, um die Telefonnummer eines Telegram-Nutzers zu erhalten.
- Der Button ist ein One-Time-Keyboard und verschwindet nach dem Teilen.

---

### `messaging_receive_normalize(update: dict)`

**Beschreibung:** Normalisiert ein rohes Telegram-Update in strukturierte Daten.

**Regeln:**
- Wird automatisch vom Gateway aufgerufen.
- Unterstützt Text, Voice, Contact, Photo, Audio, Location und Sticker.

---

### `admin_command_handle(command: str, args: str, chat_id: str, health_data: dict?)`

**Beschreibung:** Verarbeitet einen Admin-Bot-Befehl.

**Verfügbare Befehle:**
- `/status` – System-Status anzeigen
- `/ghost on|off` – Ghost Mode ein-/ausschalten
- `/help` – Hilfe anzeigen

---

### `admin_webhook_set(url: str)`

**Beschreibung:** Registriert eine Webhook-URL bei Telegram.

**Regeln:**
- URL muss HTTPS sein.
- Unterstützte Ports: 443, 80, 88, 8443.

---

### `admin_webhook_delete(drop_pending_updates: bool?)`

**Beschreibung:** Entfernt die Webhook-Integration.

---

## Allgemeine Regeln

1. **Rate Limits:** Telegram hat eine Flood-Control. Bei 429-Fehlern den `retry_after`-Wert abwarten.
2. **Datenschutz:** Chat-IDs und User-IDs sind PII – nicht in Klartext loggen.
3. **Bot-Befehle:** Nur Admin-Befehle verarbeiten, keine User-Befehle als Admin interpretieren.
4. **Sprache:** Antworte immer in der Sprache des Nutzers.
5. **Notfall-Alerts:** Haben höchste Priorität und dürfen niemals verzögert oder gefiltert werden.
