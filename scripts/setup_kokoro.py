"""Setup Kokoro-82M TTS Models.

Downloads the ONNX model and voices.json required for local inference.
"""
import os
import httpx
import asyncio

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"

TARGET_DIR = "app/voice/models"

async def download_file(url: str, filename: str):
    print(f"⬇️ Downloading {filename} from {url}...")
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        
        path = os.path.join(TARGET_DIR, filename)
        with open(path, "wb") as f:
            f.write(resp.content)
            
        print(f"✅ Saved to {path} ({len(resp.content)/1024/1024:.2f} MB)")

async def main():
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        
    await download_file(MODEL_URL, "kokoro-v0_19.onnx")
    await download_file(VOICES_URL, "voices.json")
    print("🎉 Kokoro-82M Setup Complete!")

if __name__ == "__main__":
    asyncio.run(main())
