import asyncio
import websockets
import json

# Direct connection to backend
WS_URL = "ws://localhost:8000/ws/control"

async def test_telegram_raw_text():
    print(f"Connecting to {WS_URL}...")
    async with websockets.connect(WS_URL) as websocket:
        print("✅ Connected!")
        
        # User ID from the webhook simulation
        payload = {
            "type": "intervention",
            "user_id": "123456789", 
            "content": "Hello_World with *markdown* chars but sent as RAW text!",
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
    asyncio.run(test_telegram_raw_text())
