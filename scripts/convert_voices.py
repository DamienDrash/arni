"""Convert voices.json to voices.npz."""
import json
import numpy as np
import os

JSON_PATH = "app/voice/models/voices.json"
NPZ_PATH = "app/voice/models/voices.npz"

def main():
    if not os.path.exists(JSON_PATH):
        print(f"File not found: {JSON_PATH}")
        return

    print(f"Loading {JSON_PATH}...")
    with open(JSON_PATH, "r") as f:
        data = json.load(f)
    
    # Convert to dictionary of numpy arrays
    # voices.json has structure: {"voice_name": [[floats...]]}
    # We need to flatten? No, kokoro expects existing shape.
    converted = {}
    for k, v in data.items():
        converted[k] = np.array(v, dtype=np.float32)
        print(f"Converted voice: {k}, shape: {converted[k].shape}")
        
    print(f"Saving to {NPZ_PATH}...")
    np.savez(NPZ_PATH, **converted)
    print("✅ Conversion complete.")

if __name__ == "__main__":
    main()
