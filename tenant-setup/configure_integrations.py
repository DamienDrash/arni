#!/usr/bin/env python3
"""Configure E-Mail SMTP and Calendly integrations via API."""
import requests
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

# 1. Configure E-Mail (SMTP & IMAP)
print("\n--- E-Mail (SMTP & IMAP) ---")
smtp_config = {
    "host": "smtp.gmail.com",
    "port": "587",
    "imap_host": "imap.gmail.com",
    "imap_port": "993",
    "username": "dfrigewski@gmail.com",
    "password": "klxlqqjintdclunq",
    "from_email": "dfrigewski@gmail.com",
    "from_name": "Athletik Movement",
    "enabled": True,
}

resp = session.put(
    f"{BASE_URL}/proxy/admin/connector-hub/smtp_email/config",
    json=smtp_config,
    headers={"Content-Type": "application/json"},
)
print(f"SMTP config: {resp.status_code} - {resp.text}")

# Test SMTP connection
resp_test = session.post(
    f"{BASE_URL}/proxy/admin/connector-hub/smtp_email/test",
    json={},
    headers={"Content-Type": "application/json"},
)
print(f"SMTP test: {resp_test.status_code} - {resp_test.text}")

# Verify config
resp_verify = session.get(f"{BASE_URL}/proxy/admin/connector-hub/smtp_email/config")
print(f"SMTP verify: {resp_verify.status_code} - {resp_verify.text}")

# 2. Configure Calendly
print("\n--- Calendly ---")
# Check what fields Calendly needs
resp_catalog = session.get(f"{BASE_URL}/proxy/admin/connector-hub/catalog")
if resp_catalog.status_code == 200:
    for c in resp_catalog.json():
        if "calendly" in c.get("name", "").lower() or "calendly" in str(c.get("id", "")).lower():
            print(f"Calendly connector: {c}")
            break

print("\nDone!")
