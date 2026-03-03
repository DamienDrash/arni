#!/usr/bin/env python3
"""Send a real campaign email to the test customer via SMTP."""
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

# ── Create Campaign targeting only the test customer ────────────────────────
print("\n=== Creating Campaign ===")

campaign_data = {
    "name": "SmartMotionScan – Exklusives Angebot für dich",
    "description": "Test-Kampagne an den Testkunden mit Calendly-Buchungslink.",
    "type": "broadcast",
    "channel": "email",
    "target_type": "tags",  # Fixed: plural
    "target_filter_json": json.dumps({"tags": ["Testkunde"]}),
    "template_id": 1,
    "content_subject": "Dein exklusiver SmartMotionScan – Jetzt zum Vorzugspreis!",
    "content_body": """<div style="padding: 20px 30px; color: #CCCCCC; font-family: Arial, sans-serif; line-height: 1.7;">
  <p style="color: #FFFFFF; font-size: 18px;">Hallo {{first_name}},</p>

  <p>ich hoffe, es geht dir gut und du fühlst dich fit!</p>

  <p>Ich möchte dir heute etwas Besonderes vorstellen: den <strong style="color: #6ABF40;">SmartMotionScan</strong> –
  deine persönliche, umfassende Bewegungsanalyse. In 60 Minuten finden wir gemeinsam heraus,
  wo die <strong>wahre Ursache</strong> deiner Beschwerden liegt – nicht nur die Symptome.</p>

  <p style="color: #FFFFFF;"><strong>Was dich erwartet:</strong></p>
  <ul style="color: #CCCCCC; padding-left: 20px;">
    <li>Detaillierte Analyse deiner Bewegungsmuster</li>
    <li>Identifikation von Blockaden und Fehlhaltungen</li>
    <li>Individueller Behandlungsplan nach dem SmartMotionApproach</li>
    <li>Konkrete Übungen für zu Hause</li>
  </ul>

  <p>Als bestehender Kunde bekommst du den SmartMotionScan zum <strong style="color: #6ABF40;">Vorzugspreis von 129€</strong>
  (statt 149€). Dieses Angebot gilt bis Ende des Monats.</p>

  <p style="text-align: center; margin: 30px 0;">
    <a href="https://calendly.com/dfrigewski/smartmotionscan"
       style="display: inline-block; background-color: #6ABF40; color: #000000; padding: 14px 32px;
              text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">
      Jetzt SmartMotionScan buchen
    </a>
  </p>

  <p>Ich freue mich auf dich!</p>

  <p style="color: #FFFFFF;">Sportliche Grüße,<br>
  <strong>Niklas Jauch</strong><br>
  <span style="color: #6ABF40;">Athletik Movement</span></p>
</div>""",
}

resp = requests.post(BASE, json=campaign_data, cookies=COOKIES)
print(f"Create: {resp.status_code}")
if not resp.ok:
    print(f"Error: {resp.text}")
    exit(1)

campaign = resp.json()
campaign_id = campaign["id"]
print(f"Campaign ID: {campaign_id}, Status: {campaign['status']}")

# ── Send Campaign ───────────────────────────────────────────────────────────
print(f"\n=== Sending Campaign {campaign_id} ===")
resp = requests.post(f"{BASE}/{campaign_id}/send", cookies=COOKIES)
print(f"Send: {resp.status_code}")
print(f"Response: {json.dumps(resp.json(), indent=2)}")
