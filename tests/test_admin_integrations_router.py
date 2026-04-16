import time
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.gateway.admin_shared import REDACTED_SECRET_VALUE
from app.gateway.persistence import persistence
from app.gateway.services.admin_integrations_service import service


async def _register_tenant(client: AsyncClient, suffix: str) -> str:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    response = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Integrations Tenant {unique}",
            "tenant_slug": f"integrations-tenant-{unique}",
            "email": f"integrations-{unique}@test.example",
            "password": "Password123",
            "full_name": "Integrations Admin",
            "accept_tos": True,
            "accept_privacy": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _login_system_admin(client: AsyncClient) -> str:
    response = await client.post(
        "/auth/login",
        json={"email": "admin@ariia.local", "password": "Password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_integrations_config_masks_secrets_for_tenant_admin(client: AsyncClient) -> None:
    token = await _register_tenant(client, "masking")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]
    persistence.upsert_setting("telegram_bot_token", "topsecret-token", tenant_id=tenant_id)
    persistence.upsert_setting("telegram_admin_chat_id", "12345", tenant_id=tenant_id)

    response = await client.get(
        "/admin/integrations/config",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["telegram"]["bot_token"] == REDACTED_SECRET_VALUE
    assert payload["telegram"]["admin_chat_id"] == "12345"


@pytest.mark.anyio
async def test_integrations_config_persists_non_redacted_secret_updates(client: AsyncClient) -> None:
    token = await _register_tenant(client, "persist")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]

    response = await client.put(
        "/admin/integrations/config",
        headers={"Authorization": f"Bearer {token}"},
        json={"telegram": {"bot_token": "fresh-token", "admin_chat_id": "77"}},
    )

    assert response.status_code == 200
    assert persistence.get_setting("telegram_bot_token", tenant_id=tenant_id) == "fresh-token"
    assert persistence.get_setting("telegram_admin_chat_id", tenant_id=tenant_id) == "77"


@pytest.mark.anyio
async def test_integrations_delete_only_clears_current_tenant_scope(client: AsyncClient) -> None:
    token_a = await _register_tenant(client, "delete-a")
    token_b = await _register_tenant(client, "delete-b")
    me_a = await client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    me_b = await client.get("/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    tenant_a = me_a.json()["tenant_id"]
    tenant_b = me_b.json()["tenant_id"]

    persistence.upsert_setting("telegram_bot_token", "tenant-a-token", tenant_id=tenant_a)
    persistence.upsert_setting("telegram_bot_token", "tenant-b-token", tenant_id=tenant_b)

    response = await client.delete(
        "/admin/integrations/telegram",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    assert persistence.get_setting("telegram_bot_token", tenant_id=tenant_a, fallback_to_system=False) is None
    assert persistence.get_setting("telegram_bot_token", tenant_id=tenant_b, fallback_to_system=False) == "tenant-b-token"


@pytest.mark.anyio
async def test_integrations_delete_whatsapp_also_removes_mode(client: AsyncClient) -> None:
    token = await _register_tenant(client, "delete-whatsapp")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]

    persistence.upsert_setting("whatsapp_mode", "meta", tenant_id=tenant_id)
    persistence.upsert_setting("meta_access_token", "secret", tenant_id=tenant_id)

    response = await client.delete(
        "/admin/integrations/whatsapp",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert persistence.get_setting("whatsapp_mode", tenant_id=tenant_id, fallback_to_system=False) is None
    assert persistence.get_setting("meta_access_token", tenant_id=tenant_id, fallback_to_system=False) is None


@pytest.mark.anyio
async def test_integrations_test_connector_updates_last_status_on_success(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = await _register_tenant(client, "telegram-test")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, **kwargs):
            return SimpleNamespace(status_code=200, content=b'{}', json=lambda: {"result": {"username": "ariia_bot"}})

    monkeypatch.setattr("app.gateway.services.admin_integrations_service.httpx.AsyncClient", _FakeAsyncClient)

    response = await client.post(
        "/admin/integrations/test/telegram",
        headers={"Authorization": f"Bearer {token}"},
        json={"config": {"telegram_bot_token": "abc"}},
    )

    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "telegram"
    assert persistence.get_setting("integration_telegram_last_status", tenant_id=tenant_id) == "ok"
    assert "ariia_bot" in (persistence.get_setting("integration_telegram_last_detail", tenant_id=tenant_id) or "")


@pytest.mark.anyio
async def test_integrations_catalog_replaces_connector_hub_catalog_read(client: AsyncClient) -> None:
    token = await _register_tenant(client, "catalog")

    response = await client.get(
        "/admin/integrations/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    connector_ids = {item["id"] for item in payload}
    assert "telegram" in connector_ids
    assert "whatsapp" in connector_ids


@pytest.mark.anyio
async def test_integrations_webhook_info_generates_whatsapp_verify_token(client: AsyncClient) -> None:
    token = await _register_tenant(client, "webhook-info")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]

    response = await client.get(
        "/admin/integrations/connectors/whatsapp/webhook-info",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["connector_id"] == "whatsapp"
    assert payload["verify_token"]
    assert persistence.get_setting(f"integration_whatsapp_{tenant_id}_verify_token", tenant_id=tenant_id) == payload["verify_token"]


@pytest.mark.anyio
async def test_integrations_system_usage_overview_matches_connector_hub_stats(client: AsyncClient) -> None:
    token = await _login_system_admin(client)

    response = await client.get(
        "/admin/integrations/system/usage-overview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_connectors"] >= 1
    assert "connector_usage" in payload
