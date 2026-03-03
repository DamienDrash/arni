#!/usr/bin/env python3
"""Update the test customer's phone number."""
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
    sys.exit(1)

# Contact ID 9 = Damien Testkunde
resp = session.put(
    f"{BASE_URL}/proxy/v2/contacts/9",
    json={"phone": "+491743095371"},
    headers={"Content-Type": "application/json"},
)
print(f"Update phone: {resp.status_code} - {resp.text[:200]}")
