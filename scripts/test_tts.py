"""Test TTS Generation."""
import sys
import os

# Ensure app is in path
sys.path.append(os.getcwd())

from app.voice.tts import get_tts

def main():
    print("🎤 Initializing TTS...")
    try:
        tts = get_tts()
        print("✅ TTS Initialized.")
        
        text = "Hello! This is Ariia testing voice generation."
        print(f"🗣️  Generating audio for: '{text}'")
        
        path = tts.generate_audio(text)
        
        if path and os.path.exists(path):
            print(f"✅ Audio generated successfully at: {path}")
            print(f"📁 Size: {os.path.getsize(path)} bytes")
        else:
            print("❌ Audio generation returned no path or file missing.")
            
    except Exception as e:
        print(f"❌ TTS Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
