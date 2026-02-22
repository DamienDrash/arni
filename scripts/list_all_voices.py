import json
import os

try:
    with open("app/voice/models/voices.json", "r") as f:
        data = json.load(f)
        print(f"Total voices: {len(data)}")
        print("Keys:", list(data.keys()))
except Exception as e:
    print(e)
