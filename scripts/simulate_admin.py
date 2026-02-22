import asyncio
import websockets
import json
import uuid

WS_URL = "ws://localhost:8000/ws/control"
USER_ID = "test_user_6ec4ec81" # Use existing user from previous sims

async def simulate_admin():
    async with websockets.connect(WS_URL) as websocket:
        print("Connected to WebSocket")
        
        # Send Intervention
        payload = {
            "type": "intervention",
            "user_id": USER_ID,
            "content": "This is a test intervention from Admin Script.",
            "platform": "whatsapp"
        }
        await websocket.send(json.dumps(payload))
        print("Sent Intervention")

        # Wait for response
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Received: {data['type']}")
            
            if data['type'] == 'ghost.message_out':
                print("SUCCESS: Intervention broadcasted back to admin!")
                break
            
            if data['type'] == 'error': # Should not happen, but safety check
                print("ERROR: Received error message")
                break

if __name__ == "__main__":
    asyncio.run(simulate_admin())
