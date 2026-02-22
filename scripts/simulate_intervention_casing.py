import asyncio
import websockets
import json

# Direct backend connection (port 8000)
WS_URL = "ws://localhost:8000/ws/control"

async def test_intervention():
    print(f"Connecting to {WS_URL}...")
    async with websockets.connect(WS_URL) as websocket:
        print("✅ Connected!")
        
        # Test Case: Platform is "WhatsApp" (Mixed Case) and has spaces
        payload = {
            "type": "intervention",
            "user_id": "test_user_case_123",
            "content": "Hello from Mixed Case Script!",
            "platform": " WhatsApp " 
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
    asyncio.run(test_intervention())
