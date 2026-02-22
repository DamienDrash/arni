import httpx
import asyncio

# Token extracted from previous logs
BOT_TOKEN = "REDACTED_TELEGRAM_TOKEN"
# Dummy User ID from simulation (or the one the user might be testing with if they used the simulation)
# If the user is testing with a REAL Telegram account, this ID "123456789" will fail with "chat not found".
# But that proves the API call went through.
CHAT_ID = "7473721797" 

async def debug_telegram():
    # Direct Send to known Chat ID
    print(f"🚀 Sending to REAL CHAT {CHAT_ID}...")
    url_send = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
       "chat_id": CHAT_ID,
       "text": "Das ist ein Test (Manual Force)"
    }
    
    async with httpx.AsyncClient() as client:
        resp_send = await client.post(url_send, json=payload)
        print(f"Send Status: {resp_send.status_code}")
        print(f"Send Response: {resp_send.text}")

if __name__ == "__main__":
    asyncio.run(debug_telegram())
