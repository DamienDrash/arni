import asyncio
import websockets
import json

WS_URL = "ws://localhost:8000/ws/control"

async def test_frontend_payload():
    print(f"Connecting to {WS_URL}...")
    async with websockets.connect(WS_URL) as websocket:
        print("✅ Connected!")
        
        # This is what frontend sends (based on page.tsx logic)
        # Assuming frontend gets "telegram" from sessions list
        payload = {
            "type": "intervention",
            "subtype": "request_contact",
            "user_id": "7473721797",
            "content": "Share your contact info please",
            "platform": "telegram"
        }
        
        print(f"Sending payload: {json.dumps(payload)}")
        await websocket.send(json.dumps(payload))
        
        # Listen for broadcast
        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"📩 Received: {data}")
                
                if data.get("type") == "ghost.message_out" and data.get("response") == payload["content"]:
                    print("🎉 SUCCESS: Intervention broadcasted back!")
                    break
        except asyncio.TimeoutError:
            print("❌ TIMEOUT: No broadcast received.")

if __name__ == "__main__":
    asyncio.run(test_frontend_payload())
