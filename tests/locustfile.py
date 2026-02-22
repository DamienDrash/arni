"""Locust Load Test for ARIIA Gateway.

Simulates concurrent users interacting with the system.
Targets:
- /health (Baseline)
- /webhook/whatsapp (Inbound Message)
"""

from locust import HttpUser, task, between
import uuid
import json

class AriiaUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3s between tasks

    @task(1)
    def health_check(self):
        """Simple health check."""
        self.client.get("/health", name="/health")

    @task(3)
    def send_whatsapp_message(self):
        """Simulate inbound WhatsApp message."""
        user_id = f"user-{uuid.uuid4()}"
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": user_id,
                                        "id": f"msg-{uuid.uuid4()}",
                                        "timestamp": "1234567890",
                                        "text": {"body": "Hallo Ariia, wie sind die Preise?"},
                                        "type": "text"
                                    }
                                ],
                                "contacts": [{"profile": {"name": "Load Test User"}}]
                            }
                        }
                    ]
                }
            ]
        }
        
        headers = {"Content-Type": "application/json"}
        # Expect 200 OK
        with self.client.post("/webhook/whatsapp", json=payload, headers=headers, catch_response=True, name="/webhook/whatsapp") as response:
            if response.status_code != 200:
                response.failure(f"Failed with {response.status_code}: {response.text}")
            # Note: This checks only ingestion success. 
            # End-to-end latency (Redis -> Agent -> Redis) requires listening to websocket outbound or checking logs.
            # For this test, we verify the Gateway accepts load.
