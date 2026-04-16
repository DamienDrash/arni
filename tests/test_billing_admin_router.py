from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.gateway.main import app


@pytest.fixture
async def system_admin_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="sys-admin",
            email="admin@ariia.local",
            tenant_id=1,
            tenant_slug="system",
            role="system_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


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
async def test_admin_plans_public_catalog_is_available(client: AsyncClient) -> None:
    response = await client.get("/admin/plans/public")
    assert response.status_code == 200
    plans = response.json()
    slugs = {plan["slug"] for plan in plans}
    assert {"starter", "pro", "enterprise"}.issubset(slugs)


@pytest.mark.anyio
async def test_admin_plans_subscribers_is_system_admin_only(
    tenant_admin_client: AsyncClient,
) -> None:
    response = await tenant_admin_client.get("/admin/plans/subscribers")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_admin_plans_subscribers_returns_list_for_system_admin(
    system_admin_client: AsyncClient,
) -> None:
    response = await system_admin_client.get("/admin/plans/subscribers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_admin_plans_v2_catalogs_are_available_for_system_admin(
    system_admin_client: AsyncClient,
) -> None:
    plans_response = await system_admin_client.get("/admin/plans/v2/plans")
    addons_response = await system_admin_client.get("/admin/plans/v2/addons")

    assert plans_response.status_code == 200
    assert addons_response.status_code == 200
    assert isinstance(plans_response.json(), list)
    assert isinstance(addons_response.json(), list)
