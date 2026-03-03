#!/usr/bin/env python3
"""Activate new Calendly event types and deactivate the default one."""
import requests

TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzcyNTI5NTA4LCJqdGkiOiIzZTRhYWExZi04ZWUzLTRmZWItYmIwYi04NzhmZmIyOWNkZjciLCJ1c2VyX3V1aWQiOiI0NDJhNTBjMC04NTYxLTQ5YTktODY1OS1kM2NmZWQyNjVmNzcifQ.-S8G6mf1YPMSZnF1Zh6BcRDV9bE_PugD10gpM0wKHKJYykYM47N4io78vouzz_BXzko6xcRo9Co8Y7aZ8T4aAA"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
BASE = "https://api.calendly.com"
USER_URI = "https://api.calendly.com/users/442a50c0-8561-49a9-8659-d3cfed265f77"

# Event type URIs
events_to_activate = [
    ("Kostenloses Erstgespräch", "https://api.calendly.com/event_types/a750ee18-3809-4ca0-839f-783e1bb00faf"),
    ("SmartMotionScan", "https://api.calendly.com/event_types/1f3fff6e-9294-4ecd-8fb5-bbe83e763ce9"),
    ("Treatment Session", "https://api.calendly.com/event_types/70a21424-1dde-4b49-a27c-099768ec6e25"),
    ("Follow-Up Check (kurz)", "https://api.calendly.com/event_types/49efaf00-40b8-4bac-bb75-6619ade0f45d"),
]

event_to_deactivate = ("30 Minute Meeting", "https://api.calendly.com/event_types/1592525d-411c-4047-a5ca-e6e13626d620")

# Activate new event types
for name, uri in events_to_activate:
    # Extract UUID from URI
    uuid = uri.split("/")[-1]
    resp = requests.patch(f"{BASE}/event_types/{uuid}", headers=HEADERS, json={
        "active": True
    })
    print(f"Activate '{name}': {resp.status_code}")
    if not resp.ok:
        print(f"  Error: {resp.text[:300]}")

# Deactivate default event
name, uri = event_to_deactivate
uuid = uri.split("/")[-1]
resp = requests.patch(f"{BASE}/event_types/{uuid}", headers=HEADERS, json={
    "active": False
})
print(f"Deactivate '{name}': {resp.status_code}")
if not resp.ok:
    print(f"  Error: {resp.text[:300]}")

# Verify final state
print(f"\n{'='*60}")
print("=== Final Event Types ===")
resp = requests.get(f"{BASE}/event_types", headers=HEADERS, params={
    "user": USER_URI,
    "active": True,
})
if resp.ok:
    events = resp.json().get("collection", [])
    for ev in events:
        status = "ACTIVE" if ev["active"] else "INACTIVE"
        desc = (ev.get("description_plain") or "")[:80]
        print(f"  [{status}] {ev['name']} ({ev['duration']}min)")
        print(f"    URL: {ev['scheduling_url']}")
        print(f"    Desc: {desc}")
        print()

# Also list inactive
resp2 = requests.get(f"{BASE}/event_types", headers=HEADERS, params={
    "user": USER_URI,
    "active": False,
})
if resp2.ok:
    events = resp2.json().get("collection", [])
    for ev in events:
        print(f"  [INACTIVE] {ev['name']} ({ev['duration']}min)")
