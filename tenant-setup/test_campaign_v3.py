#!/usr/bin/env python3
"""Test campaign with target_value convenience field – should send to only 1 contact (Testkunde tag)."""
import requests, json

BASE = "https://dev.ariia.ai/proxy"

r = requests.post(f"{BASE}/auth/login", json={
    "email": "dfrigewski@gmail.com",
    "password": "AthletikMove2026!",
})
assert r.ok, f"Login failed: {r.status_code}"
C = r.cookies.get_dict()
print("✓ Login OK")

# Create campaign using target_value (convenience field)
campaign_data = {
    "name": "Tag-Filter Test – Nur Testkunde",
    "channel": "email",
    "content_subject": "{{first_name}}, dein persönlicher Trainingsplan wartet!",
    "content_body": (
        "Wir haben basierend auf deinem letzten SmartMotionScan einen "
        "<strong>individuellen Trainingsplan</strong> für dich erstellt.<br><br>"
        "Dein Plan umfasst gezielte Übungen für deine Problemzonen und "
        "ist perfekt auf deine Bewegungsmuster abgestimmt.<br><br>"
        "Lade dir deinen Plan jetzt herunter oder buche direkt deine nächste Session!"
    ),
    "template_id": 1,
    "target_type": "tags",
    "target_value": "Testkunde",  # Convenience field – should auto-convert to filter_json
}

r = requests.post(f"{BASE}/admin/campaigns", json=campaign_data, cookies=C)
print(f"✓ Campaign created: {r.status_code}")
data = r.json()
cid = data.get("id")
print(f"  Campaign ID: {cid}")
print(f"  target_filter_json: {data.get('target_filter_json')}")

# Send
r = requests.post(f"{BASE}/admin/campaigns/{cid}/send", cookies=C)
print(f"✓ Campaign sent: {r.status_code}")
result = r.json()
print(f"  Recipients: {result.get('recipients')}")
print(f"  Failed: {result.get('failed')}")
print(f"  Status: {result.get('status')}")

if result.get("recipients") == 1:
    print("\n✅ TAG FILTER WORKS! Only 1 recipient (Testkunde)")
else:
    print(f"\n❌ TAG FILTER BUG: Expected 1 recipient, got {result.get('recipients')}")
