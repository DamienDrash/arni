from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.gateway.main import app
from app.gateway.persistence import persistence


@pytest.fixture
async def system_admin_client():
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
async def tenant_admin_client():
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="tenant-admin",
            email="tenant@test.example",
            tenant_id=1,
            tenant_slug="tenant-test",
            role="tenant_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_billing_connectors_masks_sensitive_values_for_system_admin(
    system_admin_client: AsyncClient,
) -> None:
    persistence.upsert_setting("billing_stripe_enabled", "true", tenant_id=1)
    persistence.upsert_setting("billing_stripe_mode", "test", tenant_id=1)
    persistence.upsert_setting("billing_stripe_publishable_key", "pk_test_visible", tenant_id=1)
    persistence.upsert_setting("billing_stripe_secret_key", "sk_test_hidden", tenant_id=1)
    persistence.upsert_setting("billing_stripe_webhook_secret", "whsec_hidden", tenant_id=1)

    response = await system_admin_client.get("/admin/billing/connectors")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stripe"]["enabled"] is True
    assert payload["stripe"]["publishable_key"] == "pk_test_visible"
    assert payload["stripe"]["secret_key"] == "__REDACTED__"
    assert payload["stripe"]["webhook_secret"] == "__REDACTED__"


@pytest.mark.anyio
async def test_platform_llm_predefined_is_system_admin_only(tenant_admin_client: AsyncClient) -> None:
    response = await tenant_admin_client.get("/admin/platform/llm/predefined")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_billing_subscription_returns_shaped_payload(
    tenant_admin_client: AsyncClient,
) -> None:
    response = await tenant_admin_client.get("/admin/billing/subscription")
    assert response.status_code == 200
    payload = response.json()
    assert "has_subscription" in payload
    assert "status" in payload
    assert "plan" in payload
    assert payload["plan"]["slug"]
