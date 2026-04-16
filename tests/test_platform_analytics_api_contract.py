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
async def test_platform_analytics_dashboard_returns_kpis(
    tenant_admin_client: AsyncClient,
) -> None:
    response = await tenant_admin_client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert "kpis" in payload
    assert "total_conversations" in payload["kpis"]
    assert "channels" in payload


@pytest.mark.anyio
async def test_platform_analytics_export_csv_returns_attachment(
    tenant_admin_client: AsyncClient,
) -> None:
    response = await tenant_admin_client.get("/api/v1/analytics/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=analytics_30d.csv" in response.headers["content-disposition"]
    assert "Metric,Value,Category" in response.text
