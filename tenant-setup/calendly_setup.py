#!/usr/bin/env python3
"""Configure Calendly event types for Athletik Movement via API."""
import requests
import json

TOKEN = "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzcyNTI5NTA4LCJqdGkiOiIzZTRhYWExZi04ZWUzLTRmZWItYmIwYi04NzhmZmIyOWNkZjciLCJ1c2VyX3V1aWQiOiI0NDJhNTBjMC04NTYxLTQ5YTktODY1OS1kM2NmZWQyNjVmNzcifQ.-S8G6mf1YPMSZnF1Zh6BcRDV9bE_PugD10gpM0wKHKJYykYM47N4io78vouzz_BXzko6xcRo9Co8Y7aZ8T4aAA"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
BASE = "https://api.calendly.com"

user_uri = "https://api.calendly.com/users/442a50c0-8561-49a9-8659-d3cfed265f77"

# Calendly API v2 does NOT support POST /event_types for creating new event types.
# Event types must be created via the Calendly web UI.
# However, we CAN use the undocumented internal API or configure via the web.
# Let's try the POST endpoint first to confirm.

print("=== Test: Create Event Type via API ===")
test = requests.post(f"{BASE}/event_types", headers=HEADERS, json={
    "name": "Kostenloses Erstgespräch",
    "host": user_uri,
    "duration": 15,
    "kind": "solo",
})
print(f"POST /event_types: {test.status_code}")
print(f"Response: {test.text[:300]}")

# If POST doesn't work, let's try the one-off event type endpoint
print("\n=== Test: One-Off Event Type ===")
one_off = requests.post(f"{BASE}/one_off_event_types", headers=HEADERS, json={
    "name": "Kostenloses Erstgespräch",
    "host": user_uri,
    "duration": 15,
    "location": {
        "kind": "physical",
        "location": "Liesenstraße 3, 10115 Berlin",
    },
})
print(f"POST /one_off_event_types: {one_off.status_code}")
print(f"Response: {one_off.text[:300]}")

# Let's also check if we can list available scheduling links
print("\n=== Test: Scheduling Links ===")
links = requests.get(f"{BASE}/scheduling_links", headers=HEADERS)
print(f"GET /scheduling_links: {links.status_code}")
print(f"Response: {links.text[:300]}")

# Check if we can create scheduling links
print("\n=== Test: Create Scheduling Link ===")
sched = requests.post(f"{BASE}/scheduling_links", headers=HEADERS, json={
    "max_event_count": 1,
    "owner": "https://api.calendly.com/event_types/1592525d-411c-4047-a5ca-e6e13626d620",
    "owner_type": "EventType",
})
print(f"POST /scheduling_links: {sched.status_code}")
print(f"Response: {sched.text[:500]}")
