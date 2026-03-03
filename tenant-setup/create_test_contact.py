#!/usr/bin/env python3
"""Create a test customer contact for campaign email testing."""
import requests
import sys

BASE_URL = "https://dev.ariia.ai"

session = requests.Session()

login_resp = session.post(
    f"{BASE_URL}/proxy/auth/login",
    json={"email": "dfrigewski@gmail.com", "password": "AthletikMove2026!"},
    headers={"Content-Type": "application/json"},
)
print(f"Login: {login_resp.status_code}")
if login_resp.status_code != 200:
    print(f"Login failed: {login_resp.text}")
    sys.exit(1)

contact = {
    "first_name": "Damien",
    "last_name": "Testkunde",
    "email": "dfrigewski+testkunde@gmail.com",
    "phone": "+491701234567",
    "lifecycle_stage": "customer",
    "source": "manual",
    "consent_email": True,
    "consent_whatsapp": True,
    "tags": ["Testkunde", "10er-Paket", "Rückenschmerzen"],
    "notes": "Testkontakt für E-Mail-Kampagnen-Tests. Alle Kommunikationskanäle freigeschaltet.",
}

resp = session.post(
    f"{BASE_URL}/proxy/v2/contacts",
    json=contact,
    headers={"Content-Type": "application/json"},
)
print(f"Create contact: {resp.status_code} - {resp.text[:200]}")
