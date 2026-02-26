# ARIIA Trial Plan – Gold Standard Konzept

## Übersicht

Wenn sich ein neuer Tenant registriert, wird er automatisch in einen **14-tägigen kostenlosen Trial** des **Professional Plans** geschoben. Während des Trials hat der Tenant Zugriff auf alle Professional-Features mit einem schwächeren LLM (Groq/basic). Nach Ablauf der 14 Tage wird der Tenant automatisch auf einen **eingeschränkten Free-Modus** herabgestuft, in dem nur noch die Billing-Seite und ein Upgrade-Banner aktiv sind.

## Architektur

### 1. Neuer "Trial" Plan in der DB

Ein neuer Plan mit slug `trial` wird in `seed_plans()` hinzugefügt:

| Eigenschaft | Wert |
|---|---|
| Name | Trial |
| Slug | trial |
| Preis | 0 (kostenlos) |
| trial_days | 14 |
| is_public | false (nicht auf Pricing-Seite) |
| Features | Wie Professional, aber mit basic AI-Tier |
| LLM Provider | Nur Groq (schwächstes LLM) |
| max_monthly_messages | 100 (stark limitiert) |
| max_members | 50 |
| max_channels | 1 |
| max_connectors | 0 |

### 2. Registrierungs-Flow (Backend)

Bei der Registrierung:
1. Tenant wird erstellt
2. Subscription wird mit `status="trialing"` und `trial_ends_at = now + 14 Tage` erstellt
3. Plan ist der Trial-Plan
4. Ein Cron-Job/Startup-Check prüft abgelaufene Trials und setzt `status="expired"`

### 3. Frontend Trial-Banner

Ein dauerhafter Banner in der Sidebar zeigt:
- "Trial: X Tage verbleibend"
- Fortschrittsbalken
- "Jetzt upgraden" Button
- Nach Ablauf: "Trial abgelaufen – Bitte Plan wählen"

### 4. Expired-State

Nach Ablauf des Trials:
- Alle API-Endpunkte geben 402 zurück (außer Permissions, Billing, Auth)
- Frontend zeigt nur noch Billing-Seite und Upgrade-Modal
- Keine Nachrichten, keine Chats, keine Daten-Löschung
- Daten bleiben 30 Tage erhalten

## Implementierung

### Backend-Änderungen:
1. `seed_plans()` – Trial Plan hinzufügen
2. `auth.py register()` – Trial statt Starter zuweisen
3. `permissions.py` – trial_ends_at ans Frontend liefern
4. `feature_gates.py` – Expired-Trial blockieren
5. Startup-Check für abgelaufene Trials

### Frontend-Änderungen:
1. `permissions.ts` – trial_ends_at Interface erweitern
2. `Sidebar.tsx` – Trial-Banner hinzufügen
3. Expired-Overlay Komponente
