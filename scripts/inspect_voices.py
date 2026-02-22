# Inspect available voices in voices.json
import json

with open("app/voice/models/voices.json", "r") as f:
    voices = json.load(f)
    keys = list(voices.keys())
    print("Total voices:", len(keys))
    # Filter for potential German voices
    german_voices = [k for k in keys if "de" in k or "german" in k or k.startswith("d")]
    print("German-candidates:", german_voices)
    print("Sample keys:", keys[:10])
