#!/usr/bin/env python3
"""End-to-End Test: Create and send an email campaign to the test customer."""
import json
import requests

BASE = "https://dev.ariia.ai/proxy/admin/campaigns"

# Login
login_resp = requests.post(
    "https://dev.ariia.ai/proxy/auth/login",
    json={"email": "dfrigewski@gmail.com", "password": "AthletikMove2026!"},
)
COOKIES = login_resp.cookies.get_dict()
print(f"Login: {login_resp.status_code}")

# ── Step 1: Verify template exists ──────────────────────────────────────────
print("\n=== Step 1: Verify Template ===")
resp = requests.get(f"{BASE}/templates", cookies=COOKIES)
print(f"Templates: {resp.status_code}")
print(f"Templates body: {resp.text[:500]}")
if resp.ok:
    templates = resp.json()
    if isinstance(templates, list):
        for t in templates:
            print(f"  [{t['id']}] {t['name']} (primary: {t.get('primary_color')})")
    else:
        print(f"  Unexpected format: {templates}")

# ── Step 2: Create Campaign ─────────────────────────────────────────────────
print("\n=== Step 2: Create Campaign ===")

# Build the email content with Calendly link
email_body = """<p>ich hoffe, es geht dir gut und du fühlst dich fit!</p>

<p>Ich möchte dir heute etwas Besonderes vorstellen: den <strong>SmartMotionScan</strong> – 
deine persönliche, umfassende Bewegungsanalyse. In 60 Minuten finden wir gemeinsam heraus, 
wo die <strong>wahre Ursache</strong> deiner Beschwerden liegt – nicht nur die Symptome.</p>

<p><strong>Was dich erwartet:</strong></p>
<ul style="color: #CCCCCC;">
  <li>Detaillierte Analyse deiner Bewegungsmuster</li>
  <li>Identifikation von Blockaden und Fehlhaltungen</li>
  <li>Individueller Behandlungsplan nach dem SmartMotionApproach</li>
  <li>Konkrete Übungen für zu Hause</li>
</ul>

<p>Als bestehender Kunde bekommst du den SmartMotionScan zum <strong>Vorzugspreis von 129€</strong> 
(statt 149€). Dieses Angebot gilt bis Ende des Monats.</p>

<p>Buche jetzt deinen Termin – ich freue mich auf dich!</p>"""

campaign_data = {
    "name": "SmartMotionScan – Exklusives Angebot für Bestandskunden",
    "description": "Kampagne an bestehende Kunden mit Sonderpreis für den SmartMotionScan. Enthält Calendly-Buchungslink.",
    "type": "broadcast",
    "channel": "email",
    "target_type": "tag",
    "target_filter_json": json.dumps({"tags": ["Testkunde"]}),
    "template_id": 1,
    "content_subject": "Dein exklusiver SmartMotionScan – Jetzt zum Vorzugspreis! 🏃",
    "content_body": email_body,
}

resp = requests.post(BASE, json=campaign_data, cookies=COOKIES)
print(f"Create Campaign: {resp.status_code}")
print(f"Response: {json.dumps(resp.json(), indent=2)}")

if resp.ok:
    campaign = resp.json()
    campaign_id = campaign.get("id")
    print(f"Campaign ID: {campaign_id}")

    # ── Step 3: Check campaign details ──────────────────────────────────────
    print(f"\n=== Step 3: Campaign Details ===")
    resp = requests.get(f"{BASE}/{campaign_id}", cookies=COOKIES)
    print(f"Get Campaign: {resp.status_code}")
    if resp.ok:
        details = resp.json()
        print(f"  Name: {details.get('name')}")
        print(f"  Status: {details.get('status')}")
        print(f"  Channel: {details.get('channel')}")
        print(f"  Target: {details.get('target_type')}")

    # ── Step 4: Send Campaign ───────────────────────────────────────────────
    print(f"\n=== Step 4: Send Campaign ===")
    resp = requests.post(f"{BASE}/{campaign_id}/send", cookies=COOKIES)
    print(f"Send Campaign: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2)}")
else:
    print("Campaign creation failed, skipping send.")
