# Sprint 10 – Deep Integration (Magicline)

**Ziel:** ARIIA mit echten Studio-Daten verbinden (Kursplan, Mitglieder-Status).
**Basis:** Existierender Code aus `magicline_test4` + `.env` aus `getimpulse`.

---

## 📅 Roadmap Context
- **Phase 10:** Deep Integration (API Level)
- **Fokus:** Read-Operations first (Kursplan, Membercheck), dann Write (Buchung).

---

## 🎯 Sprint Ziele
1. **Magicline Client Integration:**
   - `MagiclineClient` aus `workspace/magicline_test4` übernehmen (`app/integrations/magicline/`)
   - `.env` Secrets aus `workspace/getimpulse` sicher einbinden
   - Pydantic Settings erweitern

2. **Ops Agent mit Echtzeit-Daten:**
   - "Wann ist Yoga?" → `client.class_list()`
   - "Gibt es Termine für Massage?" → `client.appointment_get_slots()`
   - "War ich gestern da?" → `client.customer_checkins()`
   - "Wie voll ist es?" → `client.studio_info()` (Check-ins)

3. **Sales Agent mit CRM-Check:**
   - "Bin ich Premium?" → `client.customer_contracts(customer_id)`
   - Upsell nur für Non-Premium Member

---

## 📋 Tasks

### 10.1: Infrastructure Setup (@ARCH)
- [ ] `app/integrations/magicline/` Package erstellen
- [ ] `MagiclineClient` + `Settings` migrieren & anpassen
- [ ] Unit Tests für Client (Mocked)

### 10.2: Ops Agent – Kursplan & Termine (@BACKEND)
- [ ] Tool: `get_class_schedule(date)` implementieren
- [ ] Tool: `get_appointment_slots(category)` implementieren
- [ ] Ops Agent System Prompt anpassen (Tools nutzen)

### 10.3: Sales Agent & Member Context (@BACKEND)
- [ ] Tool: `get_member_status(phone/user_id)`
- [ ] Tool: `get_checkin_history(user_id)` ("War ich fleißig?")
- [ ] Check: Ist User "Active Member"? Welcher Tarif?
- [ ] Sales-Logik: "Du hast schon Premium!" vs "Upgrade jetzt!"

### 10.4: Booking Prototype (P2)
- [ ] "Buche mich für Yoga" → `appointment_book` / `class_book`
- [ ] Confirmation Flow (One-Way-Door Type 2)

### 10.5: Telegram Messaging (Primary Channel)
- [ ] Webhook `/webhook/telegram`
- [ ] Inbound/Outbound Logic
- [ ] Parallelbetrieb mit WhatsApp

---

## 📂 Resources
- **Reference Code:** `/root/.openclaw/workspace/magicline_test4/app/magicline_client.py`
- **Env Config:** `/root/.openclaw/workspace/getimpulse/Magicline/sandbox/.env`
- **API Docs:** `workspace/getimpulse/Magicline/Postman-Collection-OpenAPI-Analyse.md`
