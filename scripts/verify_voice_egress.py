import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.voice.pipeline import generate_voice_reply
from app.voice.tts import get_tts

async def main():
    print("🔊 Testing Voice Egress Pipeline...")
    
    # Test 1: English (Sarah)
    print("\n[1] Testing English Generation (Sarah)...")
    try:
        path_en = await generate_voice_reply("Hello, this is a test.", voice="af_sarah")
        if path_en and os.path.exists(path_en):
            print(f"✅ Success! File generated: {path_en}")
        else:
            print("❌ Failed! No file returned.")
    except Exception as e:
        print(f"❌ Exception: {e}")

    # Test 2: German (Thorsten) - The one that failed before
    print("\n[2] Testing German Generation (Thorsten)...")
    try:
        path_de = await generate_voice_reply("Hallo, das ist ein Test.", voice="de_thorsten")
        if path_de and os.path.exists(path_de):
            print(f"✅ Success! File generated: {path_de}")
            # Check size to ensure it's not empty
            size = os.path.getsize(path_de)
            print(f"   Size: {size} bytes")
        else:
            print("❌ Failed! No file returned.")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
