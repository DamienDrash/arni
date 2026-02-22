import asyncio
import websockets
import json

# Target the Next.js frontend proxy, NOT the backend directly
# This mimics what the browser is doing
WS_URL = "ws://localhost:3000/arni/ws/control"

async def test_proxy_connection():
    print(f"Attempting to connect to {WS_URL}...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✅ Connected to WebSocket via Next.js Proxy!")
            
            # Send a test ping
            await websocket.send(json.dumps({"type": "ping"}))
            
            # Wait for any response (even error or echo is fine, just proving connection)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📩 Received: {response}")
            except asyncio.TimeoutError:
                print("⚠️ No response received, but connection stayed open.")
            
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(test_proxy_connection())
