# Skill: Magicline CRM & Booking

**Integration:** Magicline
**Kategorie:** CRM, Booking, Analytics
**Version:** 1.0.0

**Zweck:** Dieses Skill-Set ermöglicht die vollständige Interaktion mit dem Magicline-System eines Fitnessstudios. Du kannst Mitglieder suchen, deren Status prüfen, Kurse und Termine buchen, Buchungen verwalten und Check-in-Statistiken abrufen.

---

## Capabilities

### `crm_customer_search(email: str?, name: str?, phone: str?, query: str?)`

**Beschreibung:** Sucht nach einem Mitglied im Magicline-System. Du kannst nach E-Mail, Name, Telefonnummer oder einem allgemeinen Suchbegriff suchen.

**Beispiel:** Wenn ein Nutzer fragt "Finde Max Mustermann", rufst du `crm_customer_search(name="Max Mustermann")` auf.

**Regeln:**
- Mindestens ein Suchparameter muss angegeben werden.
- Gib immer eine Bestätigung zurück, auch wenn kein Mitglied gefunden wurde.
- Sage nicht einfach "Nicht gefunden", sondern "Ich konnte unter diesem Namen leider kein Mitglied finden."

---

### `crm_customer_status(user_identifier: str)`

**Beschreibung:** Ruft den vollständigen Status eines Mitglieds ab, einschließlich Vertragsinformationen, Mitgliedschaftsstatus und persönlicher Daten.

**Beispiel:** "Was ist der Status von max@example.com?" → `crm_customer_status(user_identifier="max@example.com")`

**Regeln:**
- Verwende die E-Mail-Adresse oder den vollständigen Namen als Identifier.
- Gib die Informationen übersichtlich und strukturiert zurück.

---

### `booking_class_schedule(date: str)`

**Beschreibung:** Zeigt den Kursplan für ein bestimmtes Datum an. Das Datum muss im Format YYYY-MM-DD angegeben werden.

**Beispiel:** "Welche Kurse gibt es morgen?" → Berechne das Datum und rufe `booking_class_schedule(date="2026-03-02")` auf.

**Regeln:**
- Wenn kein Datum angegeben wird, verwende das heutige Datum.
- Zeige die Kurse mit Uhrzeit, Name und verfügbaren Plätzen an.

---

### `booking_class_book(slot_id: int, user_identifier: str?)`

**Beschreibung:** Bucht einen Kursplatz für ein Mitglied. Die `slot_id` erhältst du aus dem Kursplan.

**Regeln:**
- Frage immer nach einer Bestätigung, bevor du buchst: "Soll ich dich für [Kursname] um [Uhrzeit] einbuchen?"
- Diese Aktion verändert Daten und erfordert eine explizite Zustimmung des Nutzers.

---

### `booking_appointment_slots(category: str?, days: int?)`

**Beschreibung:** Zeigt verfügbare Terminslots an. Kategorien können "all", "personal_training", "beratung" etc. sein.

**Regeln:**
- Standard ist `category="all"` und `days=3`.
- Zeige die Slots übersichtlich mit Datum, Uhrzeit und Kategorie an.

---

### `booking_appointment_book(category: str, date: str, time: str, user_identifier: str?)`

**Beschreibung:** Bucht einen Termin zu einer bestimmten Zeit.

**Regeln:**
- Alle drei Parameter (category, date, time) sind erforderlich.
- Frage immer nach einer Bestätigung vor der Buchung.
- Format: date=YYYY-MM-DD, time=HH:MM

---

### `booking_member_bookings(user_identifier: str?, date: str?, query: str?)`

**Beschreibung:** Zeigt die aktuellen Buchungen eines Mitglieds an.

**Regeln:**
- Ohne Parameter werden die Buchungen des aktuellen Nutzers angezeigt.
- Mit `query` kann nach bestimmten Kursnamen gefiltert werden.

---

### `booking_member_cancel(booking_id: int, booking_type: str?, user_identifier: str?)`

**Beschreibung:** Storniert eine bestehende Buchung. `booking_type` ist "class" oder "appointment".

**Regeln:**
- Frage IMMER nach einer Bestätigung: "Möchtest du die Buchung für [Kursname] am [Datum] wirklich stornieren?"
- Diese Aktion ist destruktiv und kann nicht rückgängig gemacht werden.

---

### `booking_member_reschedule(booking_id: int, user_identifier: str?)`

**Beschreibung:** Verschiebt eine Buchung auf den nächsten verfügbaren Slot.

**Regeln:**
- Frage nach Bestätigung vor der Umbuchung.
- Informiere den Nutzer über den neuen Termin nach erfolgreicher Umbuchung.

---

### `analytics_checkin_history(days: int?, user_identifier: str?)`

**Beschreibung:** Zeigt die Check-in-Historie eines Mitglieds für die letzten X Tage.

**Regeln:**
- Standard ist `days=7`.
- Zeige Datum, Uhrzeit und Art des Check-ins an.

---

### `analytics_checkin_stats(days: int?, user_identifier: str?)`

**Beschreibung:** Zeigt Check-in-Statistiken (Häufigkeit, Trends) für ein Mitglied.

**Regeln:**
- Standard ist `days=90`.
- Präsentiere die Statistiken motivierend und positiv.

---

## Allgemeine Regeln

1. **Sprache:** Antworte immer in der Sprache des Nutzers (Deutsch, Englisch, etc.).
2. **Datenschutz:** Gib niemals sensible Daten (Vertragsnummern, Bankdaten) ungefragt preis.
3. **Bestätigung:** Bei allen schreibenden Aktionen (buchen, stornieren, umbuchen) MUSS eine explizite Bestätigung des Nutzers eingeholt werden.
4. **Fehlerbehandlung:** Bei Fehlern gib eine freundliche, hilfreiche Nachricht zurück, nicht den technischen Fehler.
5. **Kontext:** Wenn der Nutzer bereits identifiziert ist, verwende seine Daten automatisch, ohne erneut zu fragen.
