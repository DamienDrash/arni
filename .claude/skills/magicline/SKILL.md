---
name: magicline
description: >
  Entwickle, erweitere und debugge den Magicline-Skill in ARIIA. Verwende diesen Skill
  wenn du Magicline-Mitglieder abfragen, Buchungen verwalten, Trainer-Verfügbarkeit
  prüfen oder neue Magicline-Operationen implementieren willst. Greift auch bei
  Fragen wie "wie finde ich ein Mitglied per Telefon/Mail?", "wie buche ich einen
  Termin?", "wie frage ich freie Slots ab?" oder "wie debugge ich einen Magicline-Fehler?".
---

# Magicline Skill — ARIIA

Vollständige Referenz für alle Magicline-Operationen in ARIIA: Member-Lookup,
Buchungen, Trainer, freie Slots, Check-ins.

---

## Architektur (3 Layer)

```
Agent Prompt
     │
     ▼
SkillTool (magicline_booking / magicline_member / magicline_checkin)
  app/swarm/tools/magicline_booking.py
  app/swarm/tools/magicline_member.py
  app/swarm/tools/magicline_checkin.py
     │
     ▼
Business-Logik
  app/swarm/tools/magicline.py          ← _resolve_member_context(), alle Funktionen
     │
     ▼
REST-Client
  app/integrations/magicline/client.py  ← MagiclineClient, ein API-Call pro Methode
  app/integrations/magicline/__init__.py ← get_client(tenant_id) Factory
```

---

## Member-Auflösung (`_resolve_member_context`)

**Datei:** `app/swarm/tools/magicline.py:79`

Reihenfolge der Lookup-Strategien:

| Priorität | Methode | Quelle |
|-----------|---------|--------|
| 0 | Phone → `studio_members` DB | `match_member_by_phone()` in `member_matching.py` |
| 1 | member_id → `customer_get_by(customer_number=...)` | Magicline API |
| 2 | email → `customer_search(email=...)` | Magicline API |

**Wichtig:** Magicline hat keinen Phone-Search-Endpoint. Telefonnummern werden
ausschließlich über die lokale `studio_members`-Tabelle aufgelöst (die per
Nacht-Sync befüllt wird). Die Tabelle hat `customer_id`, `first_name`,
`last_name`, `phone_number`, `email`.

**Identifier-Typen die akzeptiert werden:**
- Telefon: `491743095371`, `+49 174 309 5371`, `0174 309 5371` → normalisiert via `phone_candidates()`
- E-Mail: `max@example.de` → `customer_search(email=...)`
- Mitgliedsnummer: reine Ziffern werden erst als Telefon probiert, dann als `customer_number`

**Phone-Lookup hinzufügen (für neuen Code):**
```python
from app.gateway.member_matching import match_member_by_phone
match = match_member_by_phone(phone_str, tenant_id=tenant_id)
if match:
    customer_id = match.customer_id
    name = f"{match.first_name} {match.last_name}"
```

---

## Tool-Übersicht

### `magicline_booking` — Buchungen, Kursplan & Katalog
**Datei:** `app/swarm/tools/magicline_booking.py`

| action | Pflichtfelder | Beschreibung |
|--------|---------------|--------------|
| `get_appointment_types` | — | Alle buchbaren Terminarten (Name, Kategorie, Dauer) |
| `get_class_types` | — | Alle Kursarten (Name, Kategorie, Dauer, Max TN) |
| `get_class_slots` | — | Kurs-Zeitslots für Datumsbereich (`start_date`, `days`, opt. `class_id`) |
| `get_class_schedule` | `date` | Öffentlicher Kursplan + Trainer für einen Tag |
| `get_appointment_slots` | — | Freie Slots für buchbare Terminarten (`category`, `days`) |
| `get_member_bookings` | — | Gebuchte Termine/Kurse des Users (`date`, `query`) |
| `book_appointment_by_time` | `time` | Termin per Uhrzeit buchen (`date`, `category`) |
| `class_book` | `slot_id` | Kurs per Slot-ID buchen |
| `cancel_member_booking` | `date` | Termin per Datum+Query stornieren |
| `cancel_booking_by_id` | `booking_id`, `booking_type` | Buchung direkt per ID stornieren |
| `reschedule_member_booking_to_latest` | `date` | Auf spätesten freien Slot verschieben |

`user_identifier` wird automatisch aus `context.phone_number` oder `context.member_id` befüllt.

### `magicline_member` — Mitglieder-Info & Verträge
**Datei:** `app/swarm/tools/magicline_member.py`

| action | Pflichtfelder | Beschreibung |
|--------|---------------|--------------|
| `get_member_status` | `user_identifier` | Aktiver Vertrag, Vertragsende |
| `get_member_profile` | `user_identifier` | Vollprofil: Kontaktdaten, Adresse, aktive Verträge |
| `get_member_contracts` | `user_identifier` | Alle Verträge (`status`: ACTIVE\|INACTIVE\|all) |
| `get_member_bookings` | `user_identifier` | Buchungen (auch mit `date`, `query`) |
| `get_checkin_stats` | `user_identifier` | Check-in-Häufigkeit (default: 90 Tage) |

### `magicline_employee` — Mitarbeiter-Info
**Datei:** `app/swarm/tools/magicline_employee.py`

| action | Pflichtfelder | Beschreibung |
|--------|---------------|--------------|
| `get_employee_list` | — | Alle Mitarbeiter mit Rolle und Kompetenzen |
| `get_employee` | `employee_id` | Detailprofil eines einzelnen Mitarbeiters |

### `magicline_checkin` — Check-in-Verlauf
**Datei:** `app/swarm/tools/magicline_checkin.py`

Einzelne Aktion, kein `action`-Feld nötig. Parameter: `user_identifier`, `days` (default: 7).

---

## Typische Abfragen & welches Tool

| Nutzerfrage | Tool | action | Params |
|-------------|------|--------|--------|
| "Wann ist mein nächstes Training?" | `magicline_booking` | `get_member_bookings` | `date=YYYY-MM-DD` |
| "Was läuft heute im Kursplan?" | `magicline_booking` | `get_class_schedule` | `date=heute` |
| "Welche Kurse gibt es nächste Woche?" | `magicline_booking` | `get_class_slots` | `start_date=..., days=7` |
| "Welche Terminarten kann ich buchen?" | `magicline_booking` | `get_appointment_types` | — |
| "Welche Kursarten bietet das Studio?" | `magicline_booking` | `get_class_types` | — |
| "Wann gibt es freie Slots?" | `magicline_booking` | `get_appointment_slots` | `category=all`, `days=7` |
| "Buche mich für 14:30 Uhr ein" | `magicline_booking` | `book_appointment_by_time` | `time=14:30`, `date=heute` |
| "Storniere meinen Termin morgen" | `magicline_booking` | `cancel_member_booking` | `date=morgen`, `query=...` |
| "Storniere Buchung 123456" | `magicline_booking` | `cancel_booking_by_id` | `booking_id=123456`, `booking_type=appointment` |
| "Ist mein Abo noch aktiv?" | `magicline_member` | `get_member_status` | `user_identifier` |
| "Zeig mein vollständiges Profil" | `magicline_member` | `get_member_profile` | `user_identifier` |
| "Welche Verträge habe ich?" | `magicline_member` | `get_member_contracts` | `user_identifier`, `status=all` |
| "Wie oft war ich diese Woche?" | `magicline_checkin` | — | `days=7` |
| "Wer sind die Trainer im Studio?" | `magicline_employee` | `get_employee_list` | — |
| "Was kann Trainer Alexandrine?" | `magicline_employee` | `get_employee` | `employee_id=1233412160` |

---

## Trainer-Verfügbarkeit abfragen

**Wichtig:** Magicline hat **keine Schicht- oder Zeitplan-Endpoints für Mitarbeiter**.
Die `instructors`-Arrays in Slot-Responses sind bei vielen Studios leer.

Trainer-Info kommt indirekt aus dem Kursplan (`get_class_schedule`):

```python
# Aus magicline.py get_class_schedule():
instructors = slot.get("instructors") or []
if instructors and isinstance(instructors[0], dict):
    first = instructors[0]
    trainer_name = f"{first.get('firstName', '')} {first.get('lastName', '')}".strip()
```

Um zu wissen "wann arbeitet Trainer X?", muss man mehrere Tage abfragen und
nach Trainernamen filtern. Beispiel-Script:

```python
from app.swarm.tools.magicline_booking import MagiclineBookingTool
from app.swarm.contracts import TenantContext
import asyncio

async def find_trainer_slots(trainer_name: str, tenant_id: int, days: int = 7):
    tool = MagiclineBookingTool()
    ctx = TenantContext(tenant_id=tenant_id, ...)
    results = []
    from datetime import date, timedelta
    for i in range(days):
        d = (date.today() + timedelta(days=i)).isoformat()
        r = await tool.execute({"action": "get_class_schedule", "date": d}, ctx)
        if trainer_name.lower() in (r.data or "").lower():
            results.append(r.data)
    return results
```

### Mitarbeiterliste abrufen (neu in client.py)

`MagiclineClient.employee_list()` und `employee_get(id)` sind verfügbar.
Felder: `id`, `firstName`, `lastName`, `businessRole` (STUDIO_OWNER|TRAINER|MARKETING|null),
`employeeCompetences[]`, `publicName`, `employeeInitials`, `phone1`, `phone2`, `email`.

```python
from app.integrations.magicline import get_client
client = get_client(tenant_id=4)
employees = client.employee_list()
trainers = [e for e in employees if e.get("businessRole") == "TRAINER"]
```

---

## Mitgliedsnummer per E-Mail/Telefon ermitteln

```python
from app.swarm.tools.magicline import _resolve_member_context

# Per Telefon (nutzt studio_members DB)
member, err = _resolve_member_context("491743095371", tenant_id=4)
if member:
    print(f"customer_id={member.customer_id}, name={member.display_name}")

# Per E-Mail (nutzt Magicline customer_search API)
member, err = _resolve_member_context("max@example.de", tenant_id=4)

# MemberContext Felder:
# .customer_id   → Magicline interne ID (für API-Calls)
# .first_name    → Vorname
# .last_name     → Nachname
# .display_name  → "Max Mustermann" oder "Kunde 12345"
# .source        → "phone_db" | "member_id" | "email"
```

---

## Neue Magicline-Operation hinzufügen

**Schritt 1** — Funktion in `magicline.py`:
```python
def get_trainer_schedule(trainer_name: str, days: int = 7, tenant_id: int | None = None) -> str:
    client = get_client(tenant_id=tenant_id)
    if not client:
        return "Error: Magicline Integration nicht konfiguriert."
    # ... Logik
    return result_string
```

**Schritt 2** — Import + enum in `magicline_booking.py` (oder neuem SkillTool):
```python
from app.swarm.tools.magicline import ..., get_trainer_schedule

# In parameters_schema["properties"]["action"]["enum"]:
"get_trainer_schedule",

# In execute():
elif action == "get_trainer_schedule":
    result = get_trainer_schedule(
        trainer_name=params.get("query", ""),
        days=params.get("days", 7),
        tenant_id=tenant_id,
    )
```

**Schritt 3** — Prompt aktualisieren (DB-Tabelle `ai_prompt_versions`, id=3 für ops/system):
```sql
-- Neue Zeile im TOOL-GUIDE ergänzen
UPDATE ai_prompt_versions SET content = '...' WHERE id = 3;
```
Dann Service restarten: `docker restart production-ariia-core-1`

---

## Fehler-Erkennung

`MagiclineBookingTool.execute()` prüft ob der Result-String ein Fehler ist:

```python
_ERROR_SIGNALS = (
    "Error:", "Fehler", "technischen Fehler",
    "nicht konfiguriert", "Umbuchen nicht möglich",
    "nicht aufgelöst werden", "nicht eindeutig zuordnen",
)
is_error = any(sig in result for sig in _ERROR_SIGNALS)
```

Gibt `ToolResult(success=False)` zurück bei Fehlern. Der Agent-Loop
behandelt das als "Tool schlug fehl" und informiert den User.

---

## Wichtige Datei-Referenzen

| Datei | Zweck |
|-------|-------|
| `app/swarm/tools/magicline.py` | Alle Business-Funktionen, `_resolve_member_context` |
| `app/swarm/tools/magicline_booking.py` | SkillTool: Buchungen, Kursplan, Katalog (11 actions) |
| `app/swarm/tools/magicline_member.py` | SkillTool: Mitglieder-Info & Verträge (5 actions) |
| `app/swarm/tools/magicline_employee.py` | SkillTool: Mitarbeiter-Info (2 actions) — NEU |
| `app/swarm/tools/magicline_checkin.py` | SkillTool: Check-in-Verlauf |
| `app/integrations/magicline/client.py` | Low-level REST-Client (1 Methode = 1 API-Call) |
| `app/integrations/magicline/members_sync.py` | Nacht-Sync → `studio_members` Tabelle |
| `app/gateway/member_matching.py` | `match_member_by_phone()` + Normalisierung |
| `app/swarm/contracts.py` | `TenantContext` (hat `member_id`, `phone_number`) |
| `app/swarm/tools/registry.py` | Tool-Registrierung + `AGENT_TOOL_MAP` |

---

## Magicline API Audit (Stand: März 2026, Tenant: get-impulse)

Basierend auf der offiziellen Postman Collection und Live-API-Tests.

### Studio-Daten (Tenant 4 = get-impulse)
- **Name:** GETIMPULSE BERLIN, studioId=1229488490
- **Öffnungszeiten:** Mo-Fr 07:30-20:30, Sa 09:00-14:00 (public)

### Terminarten (10 Stück)
| Name | ID | Kategorie | Dauer |
|------|----|-----------|-------|
| KRAFT TRAINING | 1212261472 | ems | 30 min |
| CARDIO TRAINING | 1212261580 | ems | 30 min |
| BODY & GOAL CHECK | 1212261670 | analysis | 30 min |
| KRAFT TRAINING ohne Trainer*in | 1212298330 | ems | 30 min |
| Nutrition Coaching bei Julia | 1229489817 | nutrition | 60 min |
| MOBILITY | 1229490012 | fascia | 30 min |
| PERSONAL TRAINING | 1229490013 | personaltraining | 60 min |
| LYMPHMASSAGE | 1229490015 | shaping | 30 min |
| Assisted Stretching by Amy | 1236171650 | fascia | 60 min |
| Freies Training | 1236853760 | fitness | 60 min |

### Kursarten (1 Stück)
| Name | ID | Kategorie | Dauer | Max TN |
|------|----|-----------|-------|--------|
| Mobility & Stretch | 1229490120 | fascia | 30 min | 4 |

### Mitarbeiter (17 gesamt)
Abfragbar über `GET /v1/employees` (implementiert als `client.employee_list()`).

Relevante Trainer-Felder:
- `businessRole`: STUDIO_OWNER | TRAINER | MARKETING | null
- `employeeCompetences`: z.B. ["Personal Trainer", "EMS Kraft", "EMS Kraft 2", "Functional Training Class", "Trainer", "Probetraining EMS"]

### Offizielle API-Endpunkte (vollständige Liste)

**Appointments:** GET bookable, GET bookable/{id}, GET bookable/{id}/slots, POST validate, POST book, GET booking, DELETE booking/{id}, GET booking (by customer)

**Classes:** GET classes, GET classes/{id}, GET classes/slots, GET classes/{id}/slots, GET classes/{id}/slots/{slotId}, POST booking/book, POST booking/validate, GET booking/{id}, DELETE booking/{id}, GET booking (by customer)

**Customers:** GET, GET/{id}, GET/by (customerNumber/cardNumber/barcode/pin/qrCodeUuid), POST/search, GET/{id}/contracts, GET/{id}/activities/checkins, GET/additional-information-fields, POST/create, und weitere

**Employees:** GET /v1/employees, GET /v1/employees/{id} — **NUR DIESE ZWEI**

**Studios:** GET /v1/studios/information, GET /v1/studios/utilization

### Nicht verfügbare Endpoints (wichtig für AI-Trainer-Queries)
- ❌ `/v1/employees/{id}/shifts` — 404 Not Found
- ❌ `/v1/employees/{id}/schedule` — 404 Not Found
- ❌ `/v1/employees/{id}/appointments` — 404 Not Found
- ❌ `/v1/employees/shifts` — 400 Bad Request (existiert laut Postman Collection nicht)
- ❌ Kein Phone-Search-Endpoint für Kunden

### instructors[] in Slots
Bei diesem Studio sind `instructors: []` in appointment slots und class slots
immer leer. Trainer-Zuordnung zu Terminen ist API-seitig nicht sichtbar.

---

## Bekannte Einschränkungen

- **Kein Phone-Endpoint in Magicline API** — Telefon-Lookup nur via `studio_members` DB (Nacht-Sync). Neue Mitglieder sind erst nach dem nächsten Sync auffindbar.
- **Trainer-Suche** — Kein dedizierter Endpoint; Trainer-Daten kommen aus dem Kursplan. Bei vielen Studios sind `instructors[]` leer.
- **Keine Schichtpläne** — `/v1/employees/shifts` existiert nicht in der offiziellen API.
- **`customer_get_by`** — Unterstützt `customerNumber`, `cardNumber`, `barcode`, `pin`, `qrCodeUuid`, `debtorId`.
- **Kapazität** — Freie Plätze = `maxParticipants - bookedParticipants - waitingListParticipants` (nicht `availableSlots`).
- **Reschedule-Rollback** — Wenn nach `appointment_book` das `appointment_cancel` fehlschlägt, entsteht eine Doppelbuchung. Kein automatisches Rollback implementiert.
- **daysAhead-Limit** — Magicline limitiert auf max. 3 Tage pro Slot-Request. Für längere Zeiträume `appointment_get_slots_range()` verwenden (sliding window).
