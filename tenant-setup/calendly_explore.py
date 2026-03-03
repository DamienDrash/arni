#!/usr/bin/env python3
"""Explore Calendly API – list user info and existing event types."""
import requests

TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzcyNTI5NTA4LCJqdGkiOiIzZTRhYWExZi04ZWUzLTRmZWItYmIwYi04NzhmZmIyOWNkZjciLCJ1c2VyX3V1aWQiOiI0NDJhNTBjMC04NTYxLTQ5YTktODY1OS1kM2NmZWQyNjVmNzcifQ.-S8G6mf1YPMSZnF1Zh6BcRDV9bE_PugD10gpM0wKHKJYykYM47N4io78vouzz_BXzko6xcRo9Co8Y7aZ8T4aAA"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
BASE = "https://api.calendly.com"

# 1. Get current user info
print("=== Current User ===")
resp = requests.get(f"{BASE}/users/me", headers=HEADERS)
print(f"Status: {resp.status_code}")
if resp.ok:
    user = resp.json()["resource"]
    print(f"  Name: {user['name']}")
    print(f"  Email: {user['email']}")
    print(f"  URI: {user['uri']}")
    print(f"  Scheduling URL: {user['scheduling_url']}")
    print(f"  Timezone: {user['timezone']}")
    user_uri = user["uri"]
else:
    print(resp.text)
    exit(1)

# 2. List existing event types
print("\n=== Existing Event Types ===")
resp = requests.get(f"{BASE}/event_types", headers=HEADERS, params={"user": user_uri})
print(f"Status: {resp.status_code}")
if resp.ok:
    data = resp.json()
    events = data.get("collection", [])
    print(f"  Total: {len(events)}")
    for ev in events:
        print(f"\n  - Name: {ev['name']}")
        print(f"    Slug: {ev['slug']}")
        print(f"    Duration: {ev['duration']} min")
        print(f"    Active: {ev['active']}")
        print(f"    Kind: {ev['kind']}")
        print(f"    Type: {ev['type']}")
        print(f"    URI: {ev['uri']}")
        print(f"    Scheduling URL: {ev['scheduling_url']}")
        print(f"    Color: {ev.get('color')}")
        print(f"    Description: {ev.get('description_plain', '')[:100]}")
else:
    print(resp.text)

# 3. Check available API endpoints for creating event types
print("\n=== Test POST event_types ===")
test_resp = requests.post(f"{BASE}/event_types", headers=HEADERS, json={
    "name": "test",
    "host": user_uri,
    "duration": 15,
    "kind": "solo",
})
print(f"Status: {test_resp.status_code}")
print(f"Response: {test_resp.text[:500]}")
