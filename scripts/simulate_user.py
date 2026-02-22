import requests
import time
import uuid

BASE_URL = "http://localhost:8000"
USER_ID = f"test_user_{uuid.uuid4().hex[:8]}"

def send_message(content):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "1234567890",
                        "phone_number_id": "PHONE_NUMBER_ID"
                    },
                    "contacts": [{
                        "profile": {
                            "name": "Test User"
                        },
                        "wa_id": USER_ID
                    }],
                    "messages": [{
                        "from": USER_ID,
                        "id": f"wamid.{uuid.uuid4().hex}",
                        "timestamp": str(int(time.time())),
                        "text": {
                            "body": content
                        },
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    print(f"Sending message from {USER_ID}: {content}")
    res = requests.post(f"{BASE_URL}/webhook/whatsapp", json=payload)
    print(f"Status: {res.status_code}")
    return res

if __name__ == "__main__":
    # Send "Hello" to trigger greeting
    send_message("Hello Arni! Is the database working?")
    
    # Wait for processing
    time.sleep(2)
    
    # Check Stats
    print("\n--- Checking Admin Stats ---")
    try:
        stats = requests.get(f"{BASE_URL}/admin/stats").json()
        print("Stats:", stats)
    except Exception as e:
        print("Failed to fetch stats:", e)

    # Check Chat History
    print(f"\n--- Checking History for {USER_ID} ---")
    try:
        history = requests.get(f"{BASE_URL}/admin/chats/{USER_ID}/history").json()
        for msg in history:
            print(f"[{msg['timestamp']}] {msg['role']}: {msg['content']}")
    except Exception as e:
        print("Failed to fetch history:", e)
