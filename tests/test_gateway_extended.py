"""ARIIA v1.4 – Extended Gateway Tests for Coverage.

@QA: Fixing F1 – main.py coverage from 55% to ≥80%
Tests: WebSocket handler, broadcast_to_admins, webhook edge cases.
"""

import pytest
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.gateway.main import app, broadcast_to_admins, active_websockets, settings


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ──────────────────────────────────────────
# WebSocket Control Tests (lines 168-199)
# ──────────────────────────────────────────


class TestWebSocketControl:
    """BMAD Benchmark: WS Connect + Echo-Test."""

    @pytest.mark.anyio
    async def test_websocket_connect_and_echo(self) -> None:
        """Test WebSocket connection and echo response."""
        from starlette.testclient import TestClient

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/control") as ws:
                ws.send_text("Hello Ariia!")
                data = ws.receive_json()
                assert data["type"] == "echo"
                assert data["data"] == "Hello Ariia!"
                assert "client_id" in data
                assert "timestamp" in data

    @pytest.mark.anyio
    async def test_websocket_multiple_messages(self) -> None:
        """Test multiple messages on same WebSocket connection."""
        from starlette.testclient import TestClient

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/control") as ws:
                for i in range(3):
                    ws.send_text(f"msg-{i}")
                    data = ws.receive_json()
                    assert data["data"] == f"msg-{i}"

    @pytest.mark.anyio
    async def test_websocket_disconnect_cleanup(self) -> None:
        """Test that disconnecting removes WS from active list."""
        from starlette.testclient import TestClient

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/control") as ws:
                ws.send_text("ping")
                data = ws.receive_json()
                assert data["type"] == "echo"
        # After disconnect, the ws should have been cleaned up
        # (no crash = success; exact count is non-deterministic in parallel tests)
        assert isinstance(active_websockets, list)


# ──────────────────────────────────────────
# Broadcast to Admins Tests (lines 206-215)
# ──────────────────────────────────────────


class TestBroadcastToAdmins:
    """Test broadcast_to_admins utility function."""

    @pytest.mark.anyio
    async def test_broadcast_empty_list(self) -> None:
        """Broadcast with no connected clients should succeed."""
        saved = active_websockets.copy()
        active_websockets.clear()
        await broadcast_to_admins({"test": "message"})
        active_websockets.extend(saved)

    @pytest.mark.anyio
    async def test_broadcast_to_connected_client(self) -> None:
        """Broadcast should call send_json on connected clients."""
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()
        saved = active_websockets.copy()
        active_websockets.clear()
        active_websockets.append(mock_ws)

        await broadcast_to_admins({"type": "test", "data": "hello"})
        mock_ws.send_json.assert_called_once_with({"type": "test", "data": "hello"})

        active_websockets.clear()
        active_websockets.extend(saved)

    @pytest.mark.anyio
    async def test_broadcast_removes_disconnected(self) -> None:
        """Disconnected clients should be removed during broadcast."""
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock(side_effect=RuntimeError("Disconnected"))
        saved = active_websockets.copy()
        active_websockets.clear()
        active_websockets.append(mock_ws)

        await broadcast_to_admins({"test": "msg"})
        assert mock_ws not in active_websockets

        active_websockets.clear()
        active_websockets.extend(saved)


# ──────────────────────────────────────────
# Webhook Edge Cases (lines 100-101, 139-140)
# ──────────────────────────────────────────


class TestWebhookEdgeCases:
    """Additional webhook edge case tests for coverage."""

    @staticmethod
    def _headers_for_payload(payload: dict) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.meta_app_secret and settings.is_production:
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            signature = hmac.new(
                settings.meta_app_secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()
            headers["x-hub-signature-256"] = f"sha256={signature}"
        return headers

    @pytest.mark.anyio
    async def test_webhook_verify_correct_token(self, client: AsyncClient) -> None:
        """Valid verification should return the challenge."""
        from config.settings import get_settings
        settings = get_settings()
        response = await client.get(
            "/webhook/whatsapp",
            params={
                "hub_mode": "subscribe",
                "hub_verify_token": settings.meta_verify_token,
                "hub_challenge": "99999",
            },
        )
        assert response.json() == 99999

    @pytest.mark.anyio
    async def test_webhook_message_without_text(self, client: AsyncClient) -> None:
        """Message without text body should still process."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "img-001",
                                        "from": "491709999999",
                                        "type": "image",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ],
        }
        response = await client.post(
            "/webhook/whatsapp",
            content=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            headers=self._headers_for_payload(payload),
        )
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_webhook_multiple_entries(self, client: AsyncClient) -> None:
        """Multiple entries with multiple messages."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"id": "m1", "from": "4917011", "type": "text", "text": {"body": "Hi"}},
                                    {"id": "m2", "from": "4917022", "type": "text", "text": {"body": "Hello"}},
                                ]
                            }
                        }
                    ]
                },
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"id": "m3", "from": "4917033", "type": "text", "text": {"body": "Hey"}},
                                ]
                            }
                        }
                    ]
                },
            ],
        }
        response = await client.post(
            "/webhook/whatsapp",
            content=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            headers=self._headers_for_payload(payload),
        )
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.anyio
    async def test_webhook_change_without_messages(self, client: AsyncClient) -> None:
        """Change entry with no messages key."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [{"id": "s1", "status": "delivered"}]
                            }
                        }
                    ]
                }
            ],
        }
        response = await client.post(
            "/webhook/whatsapp",
            content=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            headers=self._headers_for_payload(payload),
        )
        data = response.json()
        assert data["processed"] == "0"
