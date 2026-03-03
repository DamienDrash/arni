#!/usr/bin/env python3
"""Configure Calendly integration via API."""
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

# First, get the organization URI from Calendly API
CALENDLY_TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzcyNTI5NTA4LCJqdGkiOiIzZTRhYWExZi04ZWUzLTRmZWItYmIwYi04NzhmZmIyOWNkZjciLCJ1c2VyX3V1aWQiOiI0NDJhNTBjMC04NTYxLTQ5YTktODY1OS1kM2NmZWQyNjVmNzcifQ.-S8G6mf1YPMSZnF1Zh6BcRDV9bE_PugD10gpM0wKHKJYykYM47N4io78vouzz_BXzko6xcRo9Co8Y7aZ8T4aAA"

# Get user info from Calendly to find organization URI
calendly_resp = requests.get(
    "https://api.calendly.com/users/me",
    headers={"Authorization": f"Bearer {CALENDLY_TOKEN}"},
)
print(f"Calendly user info: {calendly_resp.status_code}")
org_uri = ""
if calendly_resp.status_code == 200:
    user_data = calendly_resp.json().get("resource", {})
    org_uri = user_data.get("current_organization", "")
    print(f"  Name: {user_data.get('name')}")
    print(f"  Email: {user_data.get('email')}")
    print(f"  Organization URI: {org_uri}")
    print(f"  Scheduling URL: {user_data.get('scheduling_url')}")
else:
    print(f"  Error: {calendly_resp.text}")

# Configure Calendly in ARIIA
calendly_config = {
    "api_key": CALENDLY_TOKEN,
    "organization_uri": org_uri,
    "enabled": True,
}

resp = session.put(
    f"{BASE_URL}/proxy/admin/connector-hub/calendly/config",
    json=calendly_config,
    headers={"Content-Type": "application/json"},
)
print(f"\nCalendly config: {resp.status_code} - {resp.text}")

# Test Calendly connection
resp_test = session.post(
    f"{BASE_URL}/proxy/admin/connector-hub/calendly/test",
    json={},
    headers={"Content-Type": "application/json"},
)
print(f"Calendly test: {resp_test.status_code} - {resp_test.text}")

# Verify
resp_verify = session.get(f"{BASE_URL}/proxy/admin/connector-hub/calendly/config")
print(f"Calendly verify: {resp_verify.status_code} - {resp_verify.text}")

print("\nDone!")
