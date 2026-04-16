import time

import pytest
from httpx import AsyncClient

from app.gateway.admin_shared import REDACTED_SECRET_VALUE
from app.gateway.persistence import persistence


async def _register_tenant(client: AsyncClient, suffix: str) -> str:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    resp = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Core Settings Tenant {unique}",
            "tenant_slug": f"core-settings-tenant-{unique}",
            "email": f"admin-{unique}@test.example",
            "password": "Password123",
            "full_name": "Core Settings Admin",
            "accept_tos": True,
            "accept_privacy": True,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _login_system_admin(client: AsyncClient) -> str:
    resp = await client.post(
        "/auth/login",
        json={"email": "admin@ariia.local", "password": "Password123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.anyio
async def test_settings_endpoint_masks_sensitive_values_for_tenant_admin(client: AsyncClient) -> None:
    token = await _register_tenant(client, "mask-sensitive")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]
    persistence.upsert_setting("telegram_bot_token", "super-secret", tenant_id=tenant_id)

    response = await client.get("/admin/settings", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    payload = response.json()
    row = next(item for item in payload if item["key"].endswith("telegram_bot_token"))
    assert row["value"] == REDACTED_SECRET_VALUE


@pytest.mark.anyio
async def test_sensitive_setting_update_keeps_existing_secret_when_redacted_placeholder_is_sent(client: AsyncClient) -> None:
    token = await _login_system_admin(client)
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_id = me.json()["tenant_id"]
    persistence.upsert_setting("telegram_bot_token", "existing-secret", tenant_id=tenant_id)

    response = await client.put(
        "/admin/settings/telegram_bot_token",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": REDACTED_SECRET_VALUE, "description": "keep current"},
    )

    assert response.status_code == 200, response.text
    assert persistence.get_setting("telegram_bot_token", tenant_id=tenant_id) == "existing-secret"
    assert response.json()["value"] == REDACTED_SECRET_VALUE


@pytest.mark.anyio
async def test_tenant_preferences_fall_back_to_tenant_name(client: AsyncClient) -> None:
    token = await _register_tenant(client, "tenant-fallback")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    tenant_name = me.json()["tenant_name"]

    response = await client.get("/admin/tenant-preferences", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    assert response.json()["tenant_display_name"] == tenant_name
