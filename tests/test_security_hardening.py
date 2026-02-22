import hashlib
import hmac

import pytest

from app.gateway.main import _whatsapp_verifier, app, settings
from app.gateway.persistence import persistence


@pytest.mark.anyio
async def test_telegram_webhook_requires_secret_when_configured(client) -> None:
    previous = settings.telegram_webhook_secret
    previous_env = settings.environment
    try:
        settings.environment = "production"
        settings.telegram_webhook_secret = "test-secret"
        response = await client.post("/webhook/telegram", json={})
        assert response.status_code == 403

        response_ok = await client.post(
            "/webhook/telegram",
            json={},
            headers={"x-telegram-webhook-secret": "test-secret"},
        )
        assert response_ok.status_code == 200
    finally:
        settings.telegram_webhook_secret = previous
        settings.environment = previous_env


@pytest.mark.anyio
async def test_whatsapp_webhook_requires_valid_signature_when_secret_configured(client) -> None:
    previous = settings.meta_app_secret
    previous_client_secret = _whatsapp_verifier._app_secret
    previous_env = settings.environment
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    try:
        settings.environment = "production"
        settings.meta_app_secret = "wa-secret"
        _whatsapp_verifier._app_secret = "wa-secret"

        response = await client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 403

        signature = hmac.new(b"wa-secret", body, hashlib.sha256).hexdigest()
        response_ok = await client.post(
            "/webhook/whatsapp",
            content=body,
            headers={
                "content-type": "application/json",
                "x-hub-signature-256": f"sha256={signature}",
            },
        )
        assert response_ok.status_code == 200
    finally:
        settings.meta_app_secret = previous
        _whatsapp_verifier._app_secret = previous_client_secret
        settings.environment = previous_env


@pytest.mark.anyio
async def test_settings_secret_redaction_and_write_only_semantics(client) -> None:
    login = await client.post(
        "/auth/login",
        json={"email": "admin@ariia.local", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    persistence.upsert_setting("telegram_bot_token", "real-token-value", "test")
    response = await client.get("/admin/settings", headers=headers)
    assert response.status_code == 200
    row = next(item for item in response.json() if item["key"] == "telegram_bot_token")
    assert row["value"] == "__REDACTED__"

    update_response = await client.put(
        "/admin/settings/telegram_bot_token",
        json={"value": "__REDACTED__", "description": "keep existing"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert persistence.get_setting("telegram_bot_token") == "real-token-value"
