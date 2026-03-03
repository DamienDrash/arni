#!/usr/bin/env python3
"""Create sample contacts for Athletik Movement via API."""
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

# Sample contacts for a Berlin-based movement therapy practice
contacts = [
    {
        "first_name": "Markus",
        "last_name": "Weber",
        "email": "markus.weber@example.com",
        "phone": "+491761234567",
        "company": "",
        "lifecycle_stage": "customer",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": True,
        "tags": ["10er-Paket", "Rückenschmerzen"],
        "notes": "Kommt seit 3 Monaten regelmäßig. Rückenschmerzen deutlich verbessert. Hat noch 4 Sessions im 10er-Paket.",
    },
    {
        "first_name": "Julia",
        "last_name": "Schneider",
        "email": "julia.schneider@example.com",
        "phone": "+491769876543",
        "company": "SAP SE",
        "job_title": "Software Entwicklerin",
        "lifecycle_stage": "customer",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": True,
        "tags": ["5er-Paket", "Nackenschmerzen", "Büroarbeit"],
        "notes": "Nackenverspannungen durch Büroarbeit. SmartMotionScan durchgeführt. Sehr motiviert.",
    },
    {
        "first_name": "Thomas",
        "last_name": "Müller",
        "email": "thomas.mueller@example.com",
        "phone": "+491752345678",
        "lifecycle_stage": "lead",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": True,
        "tags": ["Erstgespräch-gebucht", "Knieschmerzen"],
        "notes": "Hat über Website Erstgespräch gebucht. Knieschmerzen nach Lauftraining.",
    },
    {
        "first_name": "Anna",
        "last_name": "Fischer",
        "email": "anna.fischer@example.com",
        "phone": "+491763456789",
        "lifecycle_stage": "opportunity",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": False,
        "tags": ["SmartMotionScan", "Hüftschmerzen"],
        "notes": "Erstgespräch war sehr positiv. Interesse an SmartMotionScan. Follow-up nächste Woche.",
    },
    {
        "first_name": "Stefan",
        "last_name": "Braun",
        "email": "stefan.braun@example.com",
        "phone": "+491774567890",
        "company": "CrossFit Berlin",
        "lifecycle_stage": "customer",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": True,
        "tags": ["20er-Paket", "Sportler", "Schulter"],
        "notes": "CrossFit-Athlet mit Schulterimpingement. Langzeitkunde mit 20er-Paket. Empfiehlt aktiv weiter.",
    },
    {
        "first_name": "Lisa",
        "last_name": "Hoffmann",
        "email": "lisa.hoffmann@example.com",
        "phone": "+491785678901",
        "lifecycle_stage": "subscriber",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": False,
        "tags": ["Newsletter", "Interessent"],
        "notes": "Hat sich für Newsletter angemeldet. Noch kein Termin gebucht.",
    },
    {
        "first_name": "Michael",
        "last_name": "Krause",
        "email": "michael.krause@example.com",
        "phone": "+491796789012",
        "lifecycle_stage": "churned",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": True,
        "tags": ["Inaktiv", "Rückenschmerzen"],
        "notes": "War vor 3 Monaten zuletzt da. 5er-Paket aufgebraucht. Retention-Kontakt ausstehend.",
    },
    {
        "first_name": "Sandra",
        "last_name": "Klein",
        "email": "sandra.klein@example.com",
        "phone": "+491707890123",
        "company": "Yoga Studio Mitte",
        "job_title": "Yoga-Lehrerin",
        "lifecycle_stage": "customer",
        "source": "manual",
        "consent_email": True,
        "consent_whatsapp": True,
        "tags": ["10er-Paket", "Kooperation", "Yoga"],
        "notes": "Yoga-Lehrerin, empfiehlt Athletik Movement an ihre Schüler. Potenzielle Kooperationspartnerin.",
    },
]

for contact in contacts:
    resp = session.post(
        f"{BASE_URL}/proxy/v2/contacts",
        json=contact,
        headers={"Content-Type": "application/json"},
    )
    name = f"{contact['first_name']} {contact['last_name']}"
    print(f"  {name}: {resp.status_code} - {resp.text[:100]}")

print(f"\nDone! {len(contacts)} contacts created.")
