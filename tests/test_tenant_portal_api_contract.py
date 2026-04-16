from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.edge.app import app


@pytest.fixture
async def tenant_admin_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="tenant-admin",
            email="tenant@test.example",
            tenant_id=2,
            tenant_slug="tenant-test",
            role="tenant_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_tenant_portal_overview_returns_tenant_payload(
    tenant_admin_client: AsyncClient,
) -> None:
    response = await tenant_admin_client.get("/api/v1/tenant/portal/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant"]["id"] == 2
    assert "subscription" in payload
    assert "agent" in payload


@pytest.mark.anyio
async def test_tenant_portal_channels_update_roundtrip(
    tenant_admin_client: AsyncClient,
) -> None:
    update = await tenant_admin_client.put(
        "/api/v1/tenant/portal/channels/telegram",
        json={"enabled": True, "config": {"bot_token": "secret-token", "label": "primary"}},
    )
    assert update.status_code == 200

    response = await tenant_admin_client.get("/api/v1/tenant/portal/channels")
    assert response.status_code == 200
    channels = {item["id"]: item for item in response.json()["channels"]}
    telegram = channels["telegram"]
    assert telegram["enabled"] is True
    assert telegram["configured"] is True
    assert telegram["config"]["bot_token"] == "***"
    assert telegram["config"]["label"] == "primary"
