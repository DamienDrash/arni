"""ARIIA v1.4 – Gateway Unit Tests.

@QA: Sprint 1, Task 1.8
Tests: Health endpoint, Webhook verification, Webhook ingress.
Coverage target: ≥80% for app/gateway/
"""

import pytest
import hashlib
import hmac
import json
from httpx import ASGITransport, AsyncClient

from app.gateway.main import app, settings


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ──────────────────────────────────────────
# Health Endpoint
# ──────────────────────────────────────────


class TestHealthEndpoint:
    """BMAD Benchmark: curl /health → {"status": ...}"""

    @pytest.mark.anyio
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_health_contains_required_fields(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert data["service"] == "ariia-gateway"
        assert data["version"] == "2.0.0"
        assert "timestamp" in data

    @pytest.mark.anyio
    async def test_health_status_value(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        data = response.json()
        # Status is either "ok" (Redis up) or "degraded" (Redis down)
        assert data["status"] in ("ok", "degraded")


# ──────────────────────────────────────────
# Webhook Verification (GET)
# ──────────────────────────────────────────


class TestWebhookVerification:
    """Meta webhook verification flow."""

    @pytest.mark.anyio
    async def test_webhook_verify_rejects_invalid_token(self, client: AsyncClient) -> None:
        response = await client.get(
            "/webhook/whatsapp",
            params={
                "hub_mode": "subscribe",
                "hub_verify_token": "wrong-token",
                "hub_challenge": "12345",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    @pytest.mark.anyio
    async def test_webhook_verify_rejects_wrong_mode(self, client: AsyncClient) -> None:
        response = await client.get(
            "/webhook/whatsapp",
            params={"hub_mode": "unsubscribe", "hub_verify_token": "", "hub_challenge": "12345"},
        )
        data = response.json()
        assert "error" in data


# ──────────────────────────────────────────
# Webhook Ingress (POST)
# ──────────────────────────────────────────


class TestWebhookIngress:
    """BMAD Benchmark: Webhook → message processed."""

    VALID_PAYLOAD = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "test-msg-001",
                                    "from": "491701234567",
                                    "type": "text",
                                    "text": {"body": "Hey Ariia!"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }

    EMPTY_PAYLOAD = {"object": "whatsapp_business_account", "entry": []}

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
    async def test_webhook_post_returns_200(self, client: AsyncClient) -> None:
        response = await client.post(
            "/webhook/whatsapp/system",
            content=json.dumps(self.VALID_PAYLOAD, separators=(",", ":"), ensure_ascii=False),
            headers=self._headers_for_payload(self.VALID_PAYLOAD),
        )
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_webhook_post_returns_status_ok(self, client: AsyncClient) -> None:
        response = await client.post(
            "/webhook/whatsapp/system",
            content=json.dumps(self.VALID_PAYLOAD, separators=(",", ":"), ensure_ascii=False),
            headers=self._headers_for_payload(self.VALID_PAYLOAD),
        )
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.anyio
    async def test_webhook_post_processes_message(self, client: AsyncClient) -> None:
        """Message should be processed (count may be 0 if Redis is down, that's ok)."""
        response = await client.post(
            "/webhook/whatsapp/system",
            content=json.dumps(self.VALID_PAYLOAD, separators=(",", ":"), ensure_ascii=False),
            headers=self._headers_for_payload(self.VALID_PAYLOAD),
        )
        data = response.json()
        assert "processed" in data

    @pytest.mark.anyio
    async def test_webhook_post_empty_entry(self, client: AsyncClient) -> None:
        response = await client.post(
            "/webhook/whatsapp/system",
            content=json.dumps(self.EMPTY_PAYLOAD, separators=(",", ":"), ensure_ascii=False),
            headers=self._headers_for_payload(self.EMPTY_PAYLOAD),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == "0"

    @pytest.mark.anyio
    async def test_webhook_post_invalid_json(self, client: AsyncClient) -> None:
        headers = {"Content-Type": "application/json"}
        if settings.meta_app_secret and settings.is_production:
            bad_body = b"not json"
            signature = hmac.new(
                settings.meta_app_secret.encode("utf-8"),
                bad_body,
                hashlib.sha256,
            ).hexdigest()
            headers["x-hub-signature-256"] = f"sha256={signature}"
        response = await client.post(
            "/webhook/whatsapp/system",
            content="not json",
            headers=headers,
        )
        assert response.status_code == 422  # Validation error
