"""Inspect model files via Python."""
import os

files = ["app/voice/models/kokoro-v0_19.onnx", "app/voice/models/voices.json"]

for f in files:
    if os.path.exists(f):
        print(f"--- {f} ---")
        try:
            with open(f, "rb") as fp:
                content = fp.read(100)
                print(content)
        except Exception as e:
            print(f"Error reading {f}: {e}")
    else:
        print(f"File not found: {f}")
