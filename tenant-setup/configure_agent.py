#!/usr/bin/env python3
"""Configure the AI agent variables for Athletik Movement via API."""
import requests
import json
import sys

BASE_URL = "https://dev.ariia.ai"

session = requests.Session()

# Login
login_resp = session.post(
    f"{BASE_URL}/proxy/auth/login",
    json={"email": "dfrigewski@gmail.com", "password": "AthletikMove2026!"},
    headers={"Content-Type": "application/json"},
)
print(f"Login: {login_resp.status_code}")
if login_resp.status_code != 200:
    print(f"Login failed: {login_resp.text}")
    sys.exit(1)

# Configure agent variables
config = {
    "studio_name": "Athletik Movement",
    "studio_short_name": "Athletik Movement",
    "agent_display_name": "ARIIA",
    "studio_locale": "de-DE",
    "studio_timezone": "Europe/Berlin",
    "studio_emergency_number": "112",
    "studio_address": "Liesenstraße 3, 10115 Berlin",
    "sales_prices_text": """## Preise & Pakete

### Erstgespräch
- **Kostenlos** – Unverbindliches Beratungsgespräch (ca. 20 Min.)

### SmartMotionScan
- **149 €** – Umfassende Bewegungsanalyse mit detailliertem Befundbericht

### Einzelsession
- **120 €** – 60-minütige Personal Training / Therapie-Session

### Pakete
- **5er-Paket**: 550 € (statt 600 €) – 8% Ersparnis
- **10er-Paket**: 1.000 € (statt 1.200 €) – 17% Ersparnis
- **20er-Paket**: 1.800 € (statt 2.400 €) – 25% Ersparnis

Alle Preise verstehen sich als Selbstzahler-Leistungen. Keine ärztliche Überweisung erforderlich.""",
    "sales_retention_rules": """## Retention-Regeln

1. **Paket-Erinnerung**: Wenn ein Kunde weniger als 3 Sessions im Paket übrig hat, proaktiv auf Verlängerung ansprechen.
2. **Inaktivitäts-Follow-up**: Kunden, die seit >2 Wochen keine Session hatten, freundlich kontaktieren und nach Wohlbefinden fragen.
3. **Ergebnis-Check**: Nach 5 Sessions Fortschritte besprechen und nächste Ziele definieren.
4. **Empfehlungsprogramm**: Zufriedene Kunden nach Empfehlungen fragen – Anreiz: 1 kostenlose Session bei erfolgreicher Empfehlung.
5. **Saisonale Angebote**: Zu Jahresbeginn und nach Sommerferien spezielle Pakete anbieten.""",
    "medic_disclaimer_text": "Hinweis: Die Beratung durch unseren KI-Assistenten ersetzt keine ärztliche Diagnose oder Behandlung. Bei akuten Schmerzen, Verletzungen oder medizinischen Notfällen wenden Sie sich bitte an Ihren Arzt oder den Notruf (112). Athletik Movement bietet Bewegungstherapie und Personal Training als Selbstzahler-Leistung an.",
    "persona_bio_text": """Du bist der KI-Assistent von Athletik Movement, einer Praxis für Bewegungstherapie und Personal Training in Berlin-Mitte, geleitet von Niklas Jauch. Du kommunizierst freundlich, professionell und empathisch auf Deutsch. Du verwendest eine klare, verständliche Sprache ohne übermäßigen Fachjargon.

Deine Hauptaufgaben:
- Interessenten über den SmartMotionApproach und SmartMotionScan informieren
- Termine über Calendly koordinieren (kostenloses Erstgespräch empfehlen)
- Fragen zu Preisen, Paketen und Ablauf beantworten
- Bestehende Kunden betreuen und an Termine erinnern
- Bei medizinischen Fragen auf den Disclaimer hinweisen

Du betonst immer den ursachenbasierten Ansatz von Athletik Movement: Nachhaltige Schmerzfreiheit statt kurzfristiger Symptombehandlung. Du weißt, dass Kunden als Selbstzahler kommen und keine Überweisung brauchen.""",
}

resp = session.put(
    f"{BASE_URL}/proxy/admin/prompt-config",
    json=config,
    headers={"Content-Type": "application/json"},
)
print(f"Agent config update: {resp.status_code} - {resp.text}")

# Verify
verify_resp = session.get(f"{BASE_URL}/proxy/admin/prompt-config")
print(f"\nVerification: {verify_resp.status_code}")
data = verify_resp.json()
for key in config:
    val = data.get(key, "NOT SET")
    preview = str(val)[:60] + "..." if len(str(val)) > 60 else str(val)
    print(f"  {key}: {preview}")

print("\nDone! Agent configured for Athletik Movement.")
