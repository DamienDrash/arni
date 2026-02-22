# SaaS Readiness Audit – ARNI v1.4
**Datum:** 2026-02-21
**Analysiert von:** Claude Code (claude-sonnet-4-6)
**Zweck:** Baseline-Snapshot vor der Multi-Tenant-SaaS-Finalisierung. Dieser Stand wird nach Abschluss der Roadmap mit dem fertigen System verglichen.

---

## Gesamtbefund

> **ARNI ist aktuell kein Multi-Tenant SaaS-Produkt. Es ist ein Single-Tenant-System mit nachträglich eingezogenen `tenant_id`-Feldern.**

Das Datenbankschema ist zu ~70 % mandantenfähig. Die Applikationsschicht (Agents, Webhooks, Billing) ist es zu ~20 %. Die Infrastrukturschicht bietet keine Tenant-Isolation. Die kritischste Einzelschwachstelle: Alle Agent-System-Prompts sind fest für **GetImpulse Berlin** verdrahtet — jeder weitere Tenant erhält unweigerlich falsche Branding-Daten.

---

## Dimension 1 — Datenbankschema & Datenisolation

### Ist-Stand
Alle Kerntabellen besitzen eine `tenant_id`-Spalte:

| Tabelle | `tenant_id` vorhanden | Composite-Unique-Index |
|---|---|---|
| `chat_sessions` | ✅ (`nullable=True`) | ✅ `(tenant_id, user_id)` |
| `chat_messages` | ✅ (`nullable=True`) | ✅ `(tenant_id, session_id)` |
| `settings` | ✅ (Primary Key) | ✅ `(tenant_id, key)` |
| `users` | ✅ (`nullable=False`) | — |
| `audit_logs` | ✅ (`nullable=True`) | — |
| `studio_members` | ✅ (`nullable=True`) | ✅ `(tenant_id, customer_id)` |
| `tenants` | — (ist selbst die Quelle) | — |

`PersistenceService` (`app/gateway/persistence.py`) filtert in den Hauptpfaden konsistent nach `tenant_id`.

### Kritische Lücken

**L1.1 – Redis-Keys ohne Tenant-Scope**
Datei: `app/gateway/main.py`, ca. Zeile 1026
Verifikations-Tokens werden ohne Tenant-Präfix gespeichert:
```python
# IST (unsicher):
redis.set(f"token:{token}", payload_json)
redis.set(f"user_token:{user_id}", token)
redis.set(f"human_mode:{user_id}", "1")

# SOLL:
redis.set(f"{tenant_id}:token:{token}", payload_json)
redis.set(f"{tenant_id}:user_token:{user_id}", token)
redis.set(f"{tenant_id}:human_mode:{user_id}", "1")
```
Zwei Tenants mit demselben `user_id` (z. B. beide nutzen WhatsApp-Nummer `+49123`) überschreiben gegenseitig ihre Tokens. **Datenkorruption möglich.**

**L1.2 – `tenant_id` in Kerntabellen `nullable=True`**
Datei: `app/core/models.py`, Zeilen 10, 27, 95
`ChatSession.tenant_id`, `ChatMessage.tenant_id`, `StudioMember.tenant_id` sind optional. Ein fehlerhafter Codepfad kann Sessions ohne Tenant anlegen, die dann via `_backfill_legacy_settings_tenant_ids()` dem System-Tenant zugeordnet werden — stille Datenmigration in falsche Bucket.

**L1.3 – Kein Row-Level-Security auf Datenbankebene**
Datei: `app/core/db.py`
Isolation basiert ausschließlich auf `WHERE tenant_id = ?` in Applikations-Queries. Ein einziger vergessener Filter in einem neuen Endpoint gibt alle Mandantendaten preis.

**L1.4 – Magicline `tenant_id` systemweit hardcoded**
Datei: `config/settings.py`, Zeile 67
```python
magicline_tenant_id: str = "getimpulse"
```
Dieser Wert wird für Member-Sync verwendet. Alle Members, unabhängig vom Tenant, werden unter dem Magicline-Slug `"getimpulse"` synchronisiert.

---

## Dimension 2 — Agent-System-Prompts (KRITISCH BLOCKIEREND)

### Ist-Stand
Alle fünf Agent-System-Prompts nennen **GetImpulse Berlin** explizit und enthalten für GetImpulse spezifische Daten (Preise, Persona-Namen, Notfall-Kontext).

| Agent | Datei | Hardcoded Inhalt |
|---|---|---|
| Router | `app/swarm/router/intents.py:31` | `"KI-Assistent von GetImpulse Berlin"` |
| Persona | `app/swarm/agents/persona.py` | `"digitale Fitness-Buddy von GetImpulse Berlin"` |
| Sales | `app/swarm/agents/sales.py:19` | `"Retention-Agent von GetImpulse Berlin"` + Tarifpreise |
| Medic | `app/swarm/agents/medic.py` | `"Fitness-Coach-Agent von GetImpulse Berlin"` |
| Vision | `app/swarm/agents/vision.py` | GetImpulse-spezifischer Kontext |

**Konsequenz:** Tenant B (z. B. "SportPark München") empfängt Nachrichten wie: *"Hallo! Ich bin ARNI, der digitale Fitness-Buddy von GetImpulse Berlin."* Das ist für ein SaaS-Produkt unakzeptabel.

**Es existiert kein Mechanismus** um Prompts zur Laufzeit mit Tenant-Konfigurationsdaten zu befüllen.

Konkret fehlende Platzhalter:
- `{studio_name}` — Name des Studios
- `{agent_name}` — individueller Agenten-Name des Tenants
- `{prices}` — Tarifstruktur des Tenants
- `{locale}` — Sprache/Tonalität
- `{emergency_number}` — landesspezifische Notrufnummer

---

## Dimension 3 — Integration-Konfiguration

### Per-Tenant konfigurierbar (gut)
Folgende Werte werden in der `settings`-Tabelle per Tenant gespeichert (`app/gateway/admin.py:1346–1376`):

- Telegram: `telegram_bot_token`, `telegram_admin_chat_id`, `telegram_webhook_secret`
- WhatsApp: `wa_verify_token`, `wa_access_token`, `wa_app_secret`, `wa_phone_number_id`
- Magicline: `magicline_base_url`, `magicline_api_key`
- SMTP: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`

### Kritische Lücken

**L3.1 – Magicline Studio-ID nicht per Tenant konfigurierbar**
Der Magicline-Account-Tenant (`magicline_tenant_id`) ist global in `config/settings.py:67` gesetzt. Tenant B mit eigenem Magicline-Vertrag kann keine eigene Studio-ID hinterlegen.

**L3.2 – WhatsApp & Telegram: Einzelner Webhook für alle Tenants**
Datei: `app/gateway/main.py`
```
POST /webhook/whatsapp   → für ALLE Tenants (Tenant aus Payload gelesen)
POST /webhook/telegram   → für ALLE Tenants (Tenant aus Metadata gelesen)
POST /webhook/sms/{tenant_slug}    → ✅ KORREKT per-tenant
POST /webhook/email/{tenant_slug}  → ✅ KORREKT per-tenant
```
Fehlt `tenant_id` im WhatsApp/Telegram-Payload, fällt die Message an den System-Tenant. Kein Fehler, keine Warnung — stille Fehlerrouting.

**L3.3 – Billing: Stripe ist Global-Setting**
Datei: `app/gateway/persistence.py:10–19`
```python
GLOBAL_SYSTEM_SETTING_KEYS = {
    "billing_stripe_secret_key",
    "billing_stripe_publishable_key",
    ...
}
```
Alle Tenants teilen einen einzigen Stripe-Account. Für ein B2B-SaaS-Produkt muss der Platform-Operator eigene Stripe-Webhooks für Subscription-Management erhalten — das ist anders als Tenant-eigene Abrechnungen, beides fehlt.

---

## Dimension 4 — Billing & Subscription Management

### Ist-Stand
- Stripe-Konfigurationsfelder in Settings-Tabelle vorhanden
- Kein Subscription-Modell in der Datenbank (`app/core/models.py`)
- Kein Usage-Metering
- Keine Plan-basierte Feature-Gates
- Kein Stripe-Webhook-Handler für Payment-Events
- Kein Onboarding-Flow mit Plan-Auswahl

**Aktuell existiert null Billing-Funktionalität.**

### Fehlende Datenbank-Entitäten
```python
# Vollständig fehlend:
class Subscription(Base): ...      # Plan, Status, Stripe-Sub-ID, Periode
class UsageRecord(Base): ...       # Messages, Members, Channels pro Tenant/Monat
class Plan(Base): ...              # Feature-Limits, Preis, Stripe-Price-ID
```

---

## Dimension 5 — Tenant-Onboarding & Lifecycle

### Ist-Stand
- `POST /auth/register` erstellt Tenant + ersten Admin-User (funktioniert)
- `POST /auth/tenants` (system_admin only) für manuelle Erstellung
- Slug-Collision-Detection implementiert

### Lücken

**L5.1 – Default-Admin-Passwort schwach**
Datei: `app/core/auth.py`, Zeile 240
```python
admin_password = os.getenv("SYSTEM_ADMIN_PASSWORD", "password123")
```
Fehlt die Umgebungsvariable, startet das System mit `password123` als Admin-Passwort ohne Fehler oder Warnung.

**L5.2 – Keine E-Mail-Verifizierung bei Registrierung**
Jeder kann sich mit beliebiger E-Mail-Adresse registrieren. Kein Verifizierungs-Link, keine Bestätigungs-Mail.

**L5.3 – Keine Session-Invalidierung**
Tokens sind stateless (HMAC, kein JWT-Store). Wird ein User deaktiviert (`is_active = False`), funktionieren seine Tokens noch bis zum TTL-Ablauf (Standard: 12 Stunden).

**L5.4 – Kein Tenant-Activation-Workflow**
Neuer Tenant ist sofort aktiv — kein Approval-Schritt, keine Zahlungsverifizierung, keine Plan-Auswahl.

---

## Dimension 6 — Frontend Multi-Tenancy

### Ist-Stand
- Auth-Token enthält `tenant_id` und `tenant_slug`
- Settings-Seiten holen Daten per-tenant
- RBAC funktioniert (System-Admin sieht alle Tenants, Tenant-Admin nur eigenen)

### Lücken

**L6.1 – Kein Tenant-Switcher**
Ein User ist exklusiv an einen Tenant gebunden. Kein UI um zwischen Tenants zu wechseln (relevant für system_admin und zukünftige Multi-Tenant-User).

**L6.2 – Kein White-Label-Layer**
Logo, Primärfarbe, Studio-Name: Fix als "ARNI" und GetImpulse-Kontext. Kein Branding-System.

**L6.3 – Keine Subdomain-basierte Tenant-Auflösung**
Kein `{tenant-slug}.arni.app` Routing. Alle Tenants teilen eine URL.

---

## Dimension 7 — Infrastruktur-Isolation

### Ist-Stand (`docker-compose.yml`)

| Resource | Tenant-Isolation | Anmerkung |
|---|---|---|
| `arni-core` Container | ❌ Geteilt | Monolith für alle Tenants |
| PostgreSQL | ❌ Shared Schema | App-Level Isolation via `tenant_id` |
| Redis | ❌ Kein Namespace | Keys ohne Tenant-Präfix |
| Qdrant | ⚠️ Logisch | Collections `arni_knowledge_{tenant_slug}` — korrekt |
| Netzwerk | ❌ Bridge shared | Alle Container im selben Netz |

Shared Infrastructure für Early-Stage SaaS akzeptabel — aber ohne Redis-Namespacing und DB-RLS ist das Blast-Radius bei einem Bug maximal.

---

## Dimension 8 — Memory & Knowledge Isolation

### Ist-Stand
Dies ist die **am besten implementierte** Multi-Tenant-Dimension.

- Knowledge-Files: `data/knowledge/tenants/{tenant_slug}/` ✅
- Member-Memory: `data/knowledge/tenants/{tenant_slug}/members/` ✅
- Qdrant-Collections: `arni_knowledge_{tenant_slug}` ✅
- Cron-Einstellungen für Memory-Analyzer: per-tenant konfigurierbar ✅

**Keine kritischen Lücken in dieser Dimension.**

---

## Vollständige Schwachstellen-Matrix

| ID | Schwachstelle | Datei(en) | Schwere | Kategorie |
|---|---|---|---|---|
| L1.1 | Redis-Keys ohne Tenant-Scope | `app/gateway/main.py` | 🔴 KRITISCH | Datenisolation |
| L1.2 | `tenant_id` nullable in Kerntabellen | `app/core/models.py` | 🟠 HOCH | Datenisolation |
| L1.3 | Kein DB-Level Row-Level-Security | `app/core/db.py` | 🟠 HOCH | Datenisolation |
| L1.4 | Magicline `tenant_id` systemweit hardcoded | `config/settings.py:67` | 🔴 KRITISCH | Integration |
| L2.1 | Router-Prompt hardcoded GetImpulse | `app/swarm/router/intents.py:31` | 🔴 KRITISCH | Agent-Config |
| L2.2 | Sales-Prompt + Preise hardcoded | `app/swarm/agents/sales.py:19` | 🔴 KRITISCH | Agent-Config |
| L2.3 | Medic-Prompt hardcoded | `app/swarm/agents/medic.py` | 🔴 KRITISCH | Agent-Config |
| L2.4 | Persona-Prompt hardcoded | `app/swarm/agents/persona.py` | 🔴 KRITISCH | Agent-Config |
| L2.5 | Kein Prompt-Template-System | Gesamte `app/swarm/` | 🔴 KRITISCH | Agent-Config |
| L3.1 | Magicline Studio-ID nicht per Tenant | `config/settings.py` | 🔴 KRITISCH | Integration |
| L3.2 | WA/TG Webhooks ohne Tenant-URL-Scope | `app/gateway/main.py` | 🟠 HOCH | Webhook |
| L3.3 | Stripe als Global-Setting | `app/gateway/persistence.py:10` | 🟠 HOCH | Billing |
| L4.1 | Kein Subscription-Modell | `app/core/models.py` | 🔴 KRITISCH | Billing |
| L4.2 | Kein Usage-Metering | gesamte App | 🟠 HOCH | Billing |
| L4.3 | Keine Plan-Feature-Gates | gesamte App | 🟠 HOCH | Billing |
| L5.1 | Default-Passwort `password123` | `app/core/auth.py:240` | 🔴 KRITISCH | Security |
| L5.2 | Keine E-Mail-Verifizierung | `app/gateway/auth.py` | 🟠 HOCH | Security |
| L5.3 | Keine Session-Invalidierung | `app/core/auth.py` | 🟠 HOCH | Security |
| L5.4 | Kein Tenant-Activation-Workflow | `app/gateway/auth.py` | 🟡 MITTEL | Onboarding |
| L6.1 | Kein Tenant-Switcher im Frontend | `frontend/` | 🟡 MITTEL | UX |
| L6.2 | Kein White-Label-Layer | `frontend/` | 🟡 MITTEL | UX |
| L6.3 | Keine Subdomain-Routing | `frontend/` | 🟡 MITTEL | UX |

---

## Zusammenfassung nach Kategorie

| Kategorie | Bewertung | Kernproblem |
|---|---|---|
| Datenbankschema | 🟡 70 % | nullable tenant_ids, kein RLS |
| Agent-Prompts | 🔴 0 % | 100 % GetImpulse-hardcoded |
| Integrations | 🟡 60 % | Magicline-TenantID, Webhook-Routing |
| Billing | 🔴 5 % | Nur Config-Felder, keine Logik |
| Onboarding | 🟡 50 % | Funktioniert, aber unsicher |
| Frontend UX | 🟡 55 % | Kein White-Label, kein Switcher |
| Infrastruktur | 🟡 40 % | Redis ungesichert, kein RLS |
| Memory/Knowledge | 🟢 90 % | Gut implementiert |
| Security Basics | 🟠 60 % | Default-Passwort, keine Session-Revocation |

---

## Baseline-Metriken für Vergleich nach Roadmap-Abschluss

Diese Werte werden nach Abschluss der Roadmap erneut gemessen:

| Metrik | Baseline (2026-02-21) | Ziel |
|---|---|---|
| Hardcoded „GetImpulse Berlin" Vorkommen | 9 (kritisch/hoch) | 0 |
| Prompt-Template-Platzhalter | 0 | 5+ pro Agent |
| `tenant_id` nullable Felder in Kerntabellen | 3 | 0 |
| Redis-Keys mit Tenant-Scope | 0 % | 100 % |
| Subscription-Modell vorhanden | ❌ | ✅ |
| Plan-Feature-Gates aktiv | ❌ | ✅ |
| E-Mail-Verifizierung bei Signup | ❌ | ✅ |
| Session-Invalidierung | ❌ | ✅ |
| White-Label (Logo + Name) konfigurierbar | ❌ | ✅ |
| Magicline Studio-ID per Tenant konfigurierbar | ❌ | ✅ |

---

*Dieses Dokument ist ein unveränderlicher Snapshot. Änderungen am Code sind in der Roadmap dokumentiert.*
