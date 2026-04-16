import time
from types import SimpleNamespace

import pytest
from httpx import AsyncClient


async def _register_tenant(client: AsyncClient, suffix: str) -> str:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    resp = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Settings Tenant {unique}",
            "tenant_slug": f"settings-tenant-{unique}",
            "email": f"admin-{unique}@test.example",
            "password": "Password123",
            "full_name": "Settings Admin",
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
async def test_prompt_config_is_available_for_tenant_admin(client: AsyncClient) -> None:
    token = await _register_tenant(client, "prompt")
    response = await client.get(
        "/admin/prompt-config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "studio_name" in data
    assert "agent_display_name" in data


@pytest.mark.anyio
async def test_prompt_config_schema_is_available_for_tenant_admin(client: AsyncClient) -> None:
    token = await _register_tenant(client, "schema")
    response = await client.get(
        "/admin/prompt-config/schema",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "categories" in payload
    assert "variables" in payload


@pytest.mark.anyio
async def test_whatsapp_qr_metadata_is_available_for_tenant_admin(client: AsyncClient) -> None:
    token = await _login_system_admin(client)
    response = await client.get(
        "/admin/platform/whatsapp/qr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["tenant_slug"] == "system"


@pytest.mark.anyio
async def test_platform_email_test_is_system_admin_only(client: AsyncClient) -> None:
    token = await _register_tenant(client, "email-guard")
    response = await client.post(
        "/admin/platform/email/test",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "host": "smtp.example.com",
            "port": 587,
            "user": "bot@example.com",
            "pass": "secret",
            "from_name": "ARIIA",
            "from_addr": "bot@example.com",
            "recipient": "ops@example.com",
        },
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_whatsapp_qr_image_returns_png_when_bridge_has_qr(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = await _login_system_admin(client)

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, **kwargs):
            if url.endswith("/api/sessions"):
                return SimpleNamespace(status_code=200, json=lambda: [{"name": "system", "status": "SCAN_QR_CODE"}])
            return SimpleNamespace(status_code=200, headers={"content-type": "image/png"}, content=b"png-bytes")

        async def post(self, url: str, **kwargs):
            return SimpleNamespace(status_code=200, json=lambda: {})

    monkeypatch.setattr("app.gateway.services.admin_settings_service.httpx.AsyncClient", _FakeAsyncClient)

    response = await client.get(
        "/admin/platform/whatsapp/qr-image",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == b"png-bytes"


@pytest.mark.anyio
async def test_whatsapp_reset_returns_ok_when_bridge_fails(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = await _login_system_admin(client)

    class _FailingAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, **kwargs):
            raise RuntimeError("bridge down")

    monkeypatch.setattr("app.gateway.services.admin_settings_service.httpx.AsyncClient", _FailingAsyncClient)

    response = await client.post(
        "/admin/platform/whatsapp/reset",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
