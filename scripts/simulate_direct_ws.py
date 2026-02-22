import asyncio
import websockets
import json

# Target the Backend directly (mimicking the browser's behavior in Dev)
WS_URL = "ws://localhost:8000/ws/control"

async def test_direct_connection():
    print(f"Attempting to connect to {WS_URL}...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✅ Connected to WebSocket directly!")
            
            # Send a test ping
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Wait for any response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📩 Received: {response}")
            except asyncio.TimeoutError:
                print("⚠️ No response received, but connection stayed open.")
            
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct_connection())
