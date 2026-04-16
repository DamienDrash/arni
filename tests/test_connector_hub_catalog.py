import time
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.gateway.main import app
from app.gateway.persistence import persistence


async def _register_tenant(client: AsyncClient, suffix: str) -> tuple[str, int, str]:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    response = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Connector Hub Tenant {unique}",
            "tenant_slug": f"connector-hub-tenant-{unique}",
            "email": f"connector-hub-{unique}@test.example",
            "password": "Password123",
            "full_name": "Connector Hub Admin",
            "accept_tos": True,
            "accept_privacy": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["access_token"], payload["user"]["tenant_id"], payload["user"]["tenant_slug"]


@pytest.fixture
async def tenant_admin_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="connector-tenant-admin",
            email="tenant-admin@test.example",
            tenant_id=1,
            tenant_slug="default",
            role="tenant_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def system_admin_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="connector-system-admin",
            email="system-admin@test.example",
            tenant_id=1,
            tenant_slug="system",
            role="system_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_connector_hub_catalog_is_read_only_under_repeated_calls(client: AsyncClient) -> None:
    token, tenant_id, tenant_slug = await _register_tenant(client, "catalog")

    enabled_key = f"integration_whatsapp_{tenant_id}_enabled"
    persistence.delete_setting(enabled_key, tenant_id=tenant_id)
    persistence.upsert_setting(f"wa_session_status_{tenant_slug}", "WORKING", tenant_id=tenant_id)

    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(6):
        response = await client.get("/admin/integrations/catalog", headers=headers)
        assert response.status_code == 200, response.text
        whatsapp = next(item for item in response.json() if item["id"] == "whatsapp")
        assert whatsapp["status"] == "connected"
        assert whatsapp["setup_progress"] == 100

    responses = await asyncio.gather(
        *[client.get("/admin/integrations/catalog", headers=headers) for _ in range(3)]
    )
    assert all(response.status_code == 200 for response in responses)

    assert persistence.get_setting(enabled_key, tenant_id=tenant_id, fallback_to_system=False) is None


@pytest.mark.anyio
async def test_connector_hub_webhook_info_exposes_whatsapp_verify_token(
    tenant_admin_client: AsyncClient,
) -> None:
    verify_key = "integration_whatsapp_1_verify_token"
    persistence.delete_setting(verify_key, tenant_id=1)

    response = await tenant_admin_client.get("/admin/integrations/connectors/whatsapp/webhook-info")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["connector_id"] == "whatsapp"
    assert payload["tenant_slug"] == "default"
    assert payload["webhook_url"].endswith("/webhook/whatsapp/default")
    assert payload["verify_token"]
    assert persistence.get_setting(verify_key, tenant_id=1)


@pytest.mark.anyio
async def test_connector_hub_system_usage_overview_counts_enabled_connectors(
    system_admin_client: AsyncClient,
) -> None:
    enabled_key = "integration_whatsapp_1_enabled"
    persistence.upsert_setting(enabled_key, "true", tenant_id=1)

    response = await system_admin_client.get("/admin/integrations/system/usage-overview")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["total_connectors"] >= 1
    assert payload["total_tenants"] >= 1
    assert payload["connector_usage"].get("whatsapp", 0) >= 1
