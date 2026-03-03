#!/usr/bin/env python3
"""Create Calendly event types for Athletik Movement."""
import requests
import json

TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzcyNTI5NTA4LCJqdGkiOiIzZTRhYWExZi04ZWUzLTRmZWItYmIwYi04NzhmZmIyOWNkZjciLCJ1c2VyX3V1aWQiOiI0NDJhNTBjMC04NTYxLTQ5YTktODY1OS1kM2NmZWQyNjVmNzcifQ.-S8G6mf1YPMSZnF1Zh6BcRDV9bE_PugD10gpM0wKHKJYykYM47N4io78vouzz_BXzko6xcRo9Co8Y7aZ8T4aAA"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
BASE = "https://api.calendly.com"
USER_URI = "https://api.calendly.com/users/442a50c0-8561-49a9-8659-d3cfed265f77"

# First, deactivate the default "30 Minute Meeting"
existing_uri = "https://api.calendly.com/event_types/1592525d-411c-4047-a5ca-e6e13626d620"

# Event types for Athletik Movement
event_types = [
    {
        "name": "Kostenloses Erstgespräch",
        "description_plain": "Lerne den SmartMotionApproach kennen! In diesem kostenlosen 20-minütigen Gespräch besprechen wir deine Beschwerden, Ziele und wie ich dir helfen kann, schmerzfrei zu werden. Keine Verpflichtung – nur ein ehrliches Gespräch über deinen Weg zu mehr Bewegungsfreiheit.",
        "slug": "erstgespraech",
        "duration": 20,
        "color": "#6ABF40",
        "kind": "solo",
        "type": "StandardEventType",
        "location": {
            "kind": "physical",
            "location": "Athletik Movement, Liesenstraße 3, 10115 Berlin"
        }
    },
    {
        "name": "SmartMotionScan",
        "description_plain": "Der SmartMotionScan ist deine umfassende Bewegungsanalyse (60 Min). Gemeinsam finden wir die Ursache deiner Beschwerden – nicht nur die Symptome. Du erhältst eine detaillierte Auswertung und einen individuellen Behandlungsplan. Preis: 149€",
        "slug": "smartmotionscan",
        "duration": 60,
        "color": "#4CAF50",
        "kind": "solo",
        "type": "StandardEventType",
        "location": {
            "kind": "physical",
            "location": "Athletik Movement, Liesenstraße 3, 10115 Berlin"
        }
    },
    {
        "name": "Treatment Session",
        "description_plain": "Deine individuelle Behandlungssession (60 Min) nach dem SmartMotionApproach. Wir arbeiten gezielt an deinen Blockaden und Bewegungseinschränkungen mit dem 4-Phasen-System: MoveFlexRelax, MoveFlexStretch, MoveSyncActivation, MoveSyncIntegration. Preis: 120€ (Einzelsession) oder im Paket.",
        "slug": "treatment-session",
        "duration": 60,
        "color": "#2196F3",
        "kind": "solo",
        "type": "StandardEventType",
        "location": {
            "kind": "physical",
            "location": "Athletik Movement, Liesenstraße 3, 10115 Berlin"
        }
    },
    {
        "name": "Follow-Up Check (kurz)",
        "description_plain": "Kurzer Check-in (30 Min) um deinen Fortschritt zu besprechen, Übungen anzupassen und sicherzustellen, dass du auf dem richtigen Weg bist. Ideal zwischen den regulären Sessions.",
        "slug": "follow-up-check",
        "duration": 30,
        "color": "#FF9800",
        "kind": "solo",
        "type": "StandardEventType",
        "location": {
            "kind": "physical",
            "location": "Athletik Movement, Liesenstraße 3, 10115 Berlin"
        }
    },
]

# Try creating each event type
for ev in event_types:
    payload = {
        "name": ev["name"],
        "host": USER_URI,
        "duration": ev["duration"],
        "kind": ev["kind"],
        "slug": ev["slug"],
        "description_plain": ev["description_plain"],
        "location": ev["location"],
        "owner": USER_URI,
    }
    
    resp = requests.post(f"{BASE}/event_types", headers=HEADERS, json=payload)
    print(f"\n{'='*60}")
    print(f"Creating: {ev['name']}")
    print(f"Status: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        resource = data.get("resource", {})
        print(f"  URI: {resource.get('uri', 'N/A')}")
        print(f"  Scheduling URL: {resource.get('scheduling_url', 'N/A')}")
        print(f"  Active: {resource.get('active', 'N/A')}")
    else:
        print(f"  Error: {resp.text[:500]}")

# List all event types after creation
print(f"\n{'='*60}")
print("=== All Event Types ===")
resp = requests.get(f"{BASE}/event_types", headers=HEADERS, params={"user": USER_URI})
if resp.ok:
    events = resp.json().get("collection", [])
    for ev in events:
        status = "ACTIVE" if ev["active"] else "INACTIVE"
        print(f"  [{status}] {ev['name']} ({ev['duration']}min) → {ev['scheduling_url']}")
