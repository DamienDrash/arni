import httpx
import asyncio

URL = "http://localhost:8000/webhook/telegram"

PAYLOAD = {
    "message": {
        "message_id": 4001,
        "from": {"id": 7473721797, "username": "dmc", "first_name": "Damien"},
        "chat": {"id": 7473721797, "type": "private"},
        "date": 1678889200,
        "contact": {
            "phone_number": "+491701234567",
            "first_name": "Damien",
            "user_id": 7473721797
        }
    }
}

async def send_webhook():
    print(f"Sending Telegram Webhook to {URL}...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(URL, json=PAYLOAD)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")

if __name__ == "__main__":
    asyncio.run(send_webhook())
