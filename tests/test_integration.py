"""ARNI v1.4 – Integration Tests.

@QA: Sprint 1, Task 1.10
E2E Test: Webhook → Redis Bus → Message Pipeline.
Validates the full ingress path.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.gateway.main import app
from app.gateway.schemas import InboundMessage, OutboundMessage, Platform, SystemEvent


# ──────────────────────────────────────────
# Schema Validation Tests
# ──────────────────────────────────────────


class TestSchemaValidation:
    """Validate Pydantic models accept and reject correctly."""

    def test_inbound_message_valid(self) -> None:
        msg = InboundMessage(
            message_id="int-test-001",
            platform=Platform.WHATSAPP,
            user_id="491701234567",
            content="Ist heute voll?",
        )
        assert msg.content_type == "text"
        assert msg.platform == Platform.WHATSAPP
        assert msg.media_url is None

    def test_inbound_message_with_media(self) -> None:
        msg = InboundMessage(
            message_id="int-test-002",
            platform=Platform.TELEGRAM,
            user_id="tg-12345",
            content="",
            content_type="image",
            media_url="https://example.com/photo.jpg",
        )
        assert msg.content_type == "image"
        assert msg.media_url is not None

    def test_outbound_message_valid(self) -> None:
        msg = OutboundMessage(
            message_id="out-001",
            platform=Platform.WHATSAPP,
            user_id="491701234567",
            content="Hey! 💪 Heute ist Leg Day!",
        )
        assert msg.reply_to is None

    def test_system_event_defaults(self) -> None:
        event = SystemEvent(
            event_type="test.ping",
            source="integration_test",
        )
        assert event.severity == "info"
        assert event.payload == {}

    def test_platform_enum_values(self) -> None:
        assert Platform.WHATSAPP.value == "whatsapp"
        assert Platform.TELEGRAM.value == "telegram"
        assert Platform.VOICE.value == "voice"
        assert Platform.DASHBOARD.value == "dashboard"

    def test_inbound_serialization_roundtrip(self) -> None:
        msg = InboundMessage(
            message_id="rt-001",
            platform=Platform.WHATSAPP,
            user_id="test-user",
            content="Servus!",
        )
        json_str = msg.model_dump_json()
        restored = InboundMessage.model_validate_json(json_str)
        assert restored.message_id == msg.message_id
        assert restored.content == msg.content


# ──────────────────────────────────────────
# E2E Pipeline Tests
# ──────────────────────────────────────────


class TestWebhookToRedisPipeline:
    """End-to-End test: Webhook POST → normalization → Redis publish attempt."""

    @pytest.fixture
    async def client(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.anyio
    async def test_full_pipeline_valid_message(self, client: AsyncClient) -> None:
        """Send a valid WhatsApp payload → expect successful processing."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "e2e-msg-001",
                                        "from": "491709876543",
                                        "type": "text",
                                        "text": {"body": "Habt ihr auf?"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.anyio
    async def test_full_pipeline_multiple_messages(self, client: AsyncClient) -> None:
        """Multiple messages in one webhook delivery."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"id": "multi-1", "from": "4917001", "type": "text", "text": {"body": "Msg 1"}},
                                    {"id": "multi-2", "from": "4917002", "type": "text", "text": {"body": "Msg 2"}},
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_full_pipeline_image_message(self, client: AsyncClient) -> None:
        """Image message type flows through pipeline."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"id": "img-001", "from": "4917003", "type": "image", "text": {"body": ""}},
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        response = await client.post("/webhook/whatsapp", json=payload)
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_health_reflects_system_state(self, client: AsyncClient) -> None:
        """Health endpoint accurately reflects Redis connection state."""
        response = await client.get("/health")
        data = response.json()
        assert data["redis"] in ("connected", "disconnected")
        if data["redis"] == "connected":
            assert data["status"] == "ok"
        else:
            assert data["status"] == "degraded"

    @pytest.mark.anyio
    async def test_openapi_schema_available(self, client: AsyncClient) -> None:
        """OpenAPI docs must be accessible."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "/health" in data["paths"]
        assert "/webhook/whatsapp" in data["paths"]
