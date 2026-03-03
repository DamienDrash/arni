#!/usr/bin/env python3
"""Send a test campaign with the updated template to verify all fixes:
1. Real logo from website
2. Correct {{first_name}} personalization (no double greeting)
3. Working unsubscribe link
"""
import requests, json

BASE = "https://dev.ariia.ai/proxy"

# Login
r = requests.post(f"{BASE}/auth/login", json={
    "email": "dfrigewski@gmail.com",
    "password": "AthletikMove2026!",
})
assert r.ok, f"Login failed: {r.status_code} {r.text}"
C = r.cookies.get_dict()
print("✓ Login OK")

# Create campaign - NOTE: content_body should NOT contain "Hallo {{first_name}}"
# because the TEMPLATE already handles the greeting
campaign_data = {
    "name": "Frühlings-Angebot: Dein SmartMotionScan",
    "channel": "email",
    "content_subject": "{{first_name}}, starte schmerzfrei in den Frühling!",
    "content_body": (
        "Der Frühling steht vor der Tür – die perfekte Zeit, um deinen Körper "
        "auf ein neues Level zu bringen!<br><br>"
        "Mit unserem <strong>SmartMotionScan</strong> analysieren wir deine "
        "Bewegungsmuster in nur 60 Minuten und erstellen einen individuellen "
        "Trainingsplan, der genau auf deine Bedürfnisse zugeschnitten ist.<br><br>"
        "<strong>Nur diesen Monat:</strong> Buche deinen SmartMotionScan zum "
        "Sonderpreis von <span style='color:#6ABF40;font-weight:700;'>99€ statt 149€</span>."
    ),
    "template_id": 1,
    "target_type": "tags",
    "target_value": "Testkunde",
}

r = requests.post(f"{BASE}/admin/campaigns", json=campaign_data, cookies=C)
print(f"✓ Campaign created: {r.status_code}")
cid = r.json().get("id")
print(f"  Campaign ID: {cid}")

# Send
r = requests.post(f"{BASE}/admin/campaigns/{cid}/send", cookies=C)
print(f"✓ Campaign sent: {r.status_code}")
print(f"  Response: {json.dumps(r.json(), indent=2)}")
