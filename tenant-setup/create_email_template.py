#!/usr/bin/env python3
"""Create branded email template for Athletik Movement."""
import json
import requests

BASE = "https://dev.ariia.ai/proxy/admin/campaigns/templates"
COOKIES = {"session": ""}  # Will be fetched from login

# First login to get session cookie
login_resp = requests.post(
    "https://dev.ariia.ai/proxy/auth/login",
    json={"email": "dfrigewski@gmail.com", "password": "AthletikMove2026!"},
)
if login_resp.ok:
    COOKIES = login_resp.cookies.get_dict()
    print(f"Login OK, cookies: {list(COOKIES.keys())}")
else:
    print(f"Login failed: {login_resp.status_code} {login_resp.text}")
    exit(1)

# ── Header HTML ──────────────────────────────────────────────────────────────
header_html = """
<div style="background-color: #000000; padding: 30px 20px; text-align: center; border-bottom: 3px solid #6ABF40;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 0 auto;">
    <tr>
      <td style="padding-right: 12px; vertical-align: middle;">
        <div style="width: 48px; height: 48px; background-color: #6ABF40; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;">
          <span style="color: #000000; font-size: 24px; font-weight: bold;">A</span>
        </div>
      </td>
      <td style="vertical-align: middle;">
        <span style="color: #FFFFFF; font-size: 24px; font-weight: 700; letter-spacing: 2px; font-family: 'Helvetica Neue', Arial, sans-serif;">ATHLETIK</span>
        <br>
        <span style="color: #6ABF40; font-size: 11px; font-weight: 400; letter-spacing: 4px; font-family: 'Helvetica Neue', Arial, sans-serif;">MOVEMENT</span>
      </td>
    </tr>
  </table>
</div>
"""

# ── Footer HTML ──────────────────────────────────────────────────────────────
footer_html = """
<div style="background-color: #111111; padding: 30px 20px; text-align: center; border-top: 2px solid #222222;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 0 auto; max-width: 500px;">
    <tr>
      <td style="padding-bottom: 15px;">
        <span style="color: #6ABF40; font-size: 16px; font-weight: 600; font-family: 'Helvetica Neue', Arial, sans-serif;">Athletik Movement</span>
      </td>
    </tr>
    <tr>
      <td style="padding-bottom: 10px;">
        <span style="color: #888888; font-size: 13px; font-family: 'Helvetica Neue', Arial, sans-serif;">
          Niklas Jauch · Liesenstraße 3 · 10115 Berlin
        </span>
      </td>
    </tr>
    <tr>
      <td style="padding-bottom: 10px;">
        <span style="color: #888888; font-size: 13px; font-family: 'Helvetica Neue', Arial, sans-serif;">
          📞 +49 (0) 176 43265161 · ✉ info@athletik-movement.de
        </span>
      </td>
    </tr>
    <tr>
      <td style="padding-bottom: 15px;">
        <a href="https://athletik-movement.de" style="color: #6ABF40; font-size: 13px; text-decoration: none; font-family: 'Helvetica Neue', Arial, sans-serif;">
          athletik-movement.de
        </a>
      </td>
    </tr>
    <tr>
      <td style="border-top: 1px solid #333333; padding-top: 15px;">
        <span style="color: #666666; font-size: 11px; font-family: 'Helvetica Neue', Arial, sans-serif;">
          Du erhältst diese E-Mail, weil du dich bei Athletik Movement angemeldet hast.<br>
          <a href="{{unsubscribe_url}}" style="color: #888888; text-decoration: underline;">Abmelden</a> · 
          <a href="https://athletik-movement.de/datenschutz" style="color: #888888; text-decoration: underline;">Datenschutz</a>
        </span>
      </td>
    </tr>
  </table>
</div>
"""

# ── Body Template ────────────────────────────────────────────────────────────
body_template = """
<div style="background-color: #000000; font-family: 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 0 auto; max-width: 600px; width: 100%;">
    <tr>
      <td style="padding: 40px 30px;">
        <!-- Greeting -->
        <p style="color: #FFFFFF; font-size: 22px; font-weight: 600; margin: 0 0 20px 0;">
          Hallo {{first_name}},
        </p>
        
        <!-- Main Content Area -->
        <div style="color: #CCCCCC; font-size: 15px; line-height: 1.7;">
          {{content}}
        </div>
        
        <!-- CTA Button -->
        <div style="text-align: center; margin: 35px 0;">
          <a href="{{cta_url}}" style="background-color: #6ABF40; color: #000000; padding: 14px 36px; text-decoration: none; font-size: 15px; font-weight: 700; border-radius: 6px; display: inline-block; letter-spacing: 0.5px;">
            {{cta_text}}
          </a>
        </div>
        
        <!-- Closing -->
        <p style="color: #CCCCCC; font-size: 15px; line-height: 1.7; margin: 20px 0 0 0;">
          {{closing}}
        </p>
        
        <!-- Signature -->
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #333333;">
          <p style="color: #FFFFFF; font-size: 15px; margin: 0;">
            Sportliche Grüße,<br>
            <strong style="color: #6ABF40;">Niklas Jauch</strong><br>
            <span style="color: #888888; font-size: 13px;">Movement Coach · Athletik Movement</span>
          </p>
        </div>
      </td>
    </tr>
  </table>
</div>
"""

# ── Variables JSON ───────────────────────────────────────────────────────────
variables = {
    "first_name": {"label": "Vorname", "default": ""},
    "content": {"label": "Hauptinhalt", "default": ""},
    "cta_url": {"label": "Button-Link", "default": "https://athletik-movement.de"},
    "cta_text": {"label": "Button-Text", "default": "Termin buchen"},
    "closing": {"label": "Abschlusstext", "default": "Ich freue mich auf dich!"},
    "unsubscribe_url": {"label": "Abmelde-Link", "default": "#"},
}

# ── Create Template ──────────────────────────────────────────────────────────
payload = {
    "name": "Athletik Movement – Standard",
    "description": "Branded E-Mail-Template im dunklen Premium-Design von Athletik Movement. Passend für Newsletter, Kampagnen und Kundenansprache.",
    "type": "email",
    "header_html": header_html.strip(),
    "footer_html": footer_html.strip(),
    "body_template": body_template.strip(),
    "variables_json": json.dumps(variables, ensure_ascii=False),
    "primary_color": "#6ABF40",
    "logo_url": "https://athletik-movement.de/logo.png",
}

resp = requests.post(BASE, json=payload, cookies=COOKIES)
print(f"Template creation: {resp.status_code}")
print(resp.json())
