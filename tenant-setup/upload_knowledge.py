#!/usr/bin/env python3
"""Upload knowledge base documents to ARIIA via API."""
import requests
import json
import os
import sys

BASE_URL = "https://dev.ariia.ai"

# First, login to get session cookies
session = requests.Session()

# Login
login_resp = session.post(
    f"{BASE_URL}/proxy/auth/login",
    json={"email": "dfrigewski@gmail.com", "password": "AthletikMove2026!"},
    headers={"Content-Type": "application/json"},
    verify=True,
)
print(f"Login: {login_resp.status_code}")
if login_resp.status_code != 200:
    print(f"Login failed: {login_resp.text}")
    sys.exit(1)

print(f"Cookies: {dict(session.cookies)}")

# Knowledge base files to upload
kb_dir = "/home/ubuntu/arni/tenant-setup/wissensbasis"
files = sorted([f for f in os.listdir(kb_dir) if f.endswith(".md")])

for filename in files:
    filepath = os.path.join(kb_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    payload = {
        "content": content,
        "reason": f"Initial knowledge base upload: {filename}",
        "base_mtime": None,
    }
    
    resp = session.post(
        f"{BASE_URL}/proxy/admin/knowledge/file/{filename}",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    print(f"Upload {filename}: {resp.status_code} - {resp.text[:200]}")

print("\nDone! All knowledge base documents uploaded.")
