from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.core.db import SessionLocal
from app.core.integration_models import (
    CapabilityDefinition,
    IntegrationCapability,
    IntegrationDefinition,
    TenantIntegration,
)
from app.core.models import Plan, Subscription, Tenant
from app.edge.app import app


TEST_TENANT_ID = 920201
TEST_PLAN_SLUG = "marketplace-contract-starter"
TEST_INTEGRATION_ID = "marketplace_magicline_test"
TEST_CAPABILITY_ID = "marketplace.capability.contract"


def _seed_marketplace_registry_fixture() -> None:
    db = SessionLocal()
    try:
        tenant_integration = (
            db.query(TenantIntegration)
            .filter(
                TenantIntegration.tenant_id == TEST_TENANT_ID,
                TenantIntegration.integration_id == TEST_INTEGRATION_ID,
            )
            .first()
        )
        if tenant_integration:
            db.delete(tenant_integration)

        integration_capability = (
            db.query(IntegrationCapability)
            .filter(
                IntegrationCapability.integration_id == TEST_INTEGRATION_ID,
                IntegrationCapability.capability_id == TEST_CAPABILITY_ID,
            )
            .first()
        )
        if integration_capability:
            db.delete(integration_capability)

        capability = db.get(CapabilityDefinition, TEST_CAPABILITY_ID)
        if capability:
            db.delete(capability)

        integration = db.get(IntegrationDefinition, TEST_INTEGRATION_ID)
        if integration:
            db.delete(integration)

        subscription = db.query(Subscription).filter(Subscription.tenant_id == TEST_TENANT_ID).first()
        if subscription:
            db.delete(subscription)

        plan = db.query(Plan).filter(Plan.slug == TEST_PLAN_SLUG).first()
        if plan:
            db.delete(plan)

        tenant = db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).first()
        if tenant:
            db.delete(tenant)

        db.flush()

        tenant = Tenant(id=TEST_TENANT_ID, slug="marketplace-contract", name="Marketplace Contract", is_active=True)
        plan = Plan(name="Marketplace Starter", slug=TEST_PLAN_SLUG, price_monthly_cents=0, is_active=True)
        integration = IntegrationDefinition(
            id=TEST_INTEGRATION_ID,
            name="Marketplace Magicline",
            description="Contract registry integration",
            category="crm",
            is_active=True,
            is_public=True,
            min_plan="starter",
        )
        capability = CapabilityDefinition(
            id=TEST_CAPABILITY_ID,
            name="Contract Capability",
            description="Capability wired through integration_capabilities",
            category="crm",
        )

        db.add_all([tenant, plan, integration, capability])
        db.flush()

        db.add(Subscription(tenant_id=tenant.id, plan_id=plan.id, status="active"))
        db.add(
            IntegrationCapability(
                integration_id=integration.id,
                capability_id=capability.id,
            )
        )
        db.add(
            TenantIntegration(
                tenant_id=tenant.id,
                integration_id=integration.id,
                status="active",
                enabled=True,
                config_meta={"enabled_capabilities": [capability.id]},
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture
async def tenant_admin_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="tenant-admin",
            email="tenant@test.example",
            tenant_id=TEST_TENANT_ID,
            tenant_slug="marketplace-contract",
            role="tenant_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_marketplace_catalog_fallback_returns_plan_filtered_connectors(
    tenant_admin_client: AsyncClient,
) -> None:
    connectors = [
        {
            "id": "whatsapp",
            "name": "WhatsApp",
            "description": "Messaging integration",
            "category": "messaging",
            "min_plan": "starter",
        },
        {
            "id": "salesforce",
            "name": "Salesforce",
            "description": "CRM integration",
            "category": "crm",
            "min_plan": "enterprise",
        },
    ]

    with patch("app.platform.api.marketplace._get_integration_registry", return_value=(None, None)), patch(
        "app.platform.api.marketplace.marketplace_repository.get_tenant_plan_slug",
        return_value="starter",
    ), patch(
        "app.integrations.connector_registry.list_connectors",
        return_value=connectors,
    ):
        response = await tenant_admin_client.get("/api/v1/marketplace/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    by_id = {item["id"]: item for item in payload["catalog"]}
    assert by_id["whatsapp"]["available_for_plan"] is True
    assert by_id["salesforce"]["available_for_plan"] is False


@pytest.mark.anyio
async def test_marketplace_activate_returns_501_without_registry(
    tenant_admin_client: AsyncClient,
) -> None:
    with patch("app.platform.api.marketplace._get_integration_registry", return_value=(None, None)):
        response = await tenant_admin_client.post("/api/v1/marketplace/activate/123", json={})

    assert response.status_code == 501
    assert response.json()["detail"] == "Integration Registry not available"


@pytest.mark.anyio
async def test_marketplace_registry_detail_and_capabilities_follow_current_models(
    tenant_admin_client: AsyncClient,
) -> None:
    _seed_marketplace_registry_fixture()

    detail_response = await tenant_admin_client.get(f"/api/v1/marketplace/catalog/{TEST_INTEGRATION_ID}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["integration"]["id"] == TEST_INTEGRATION_ID
    assert detail_payload["capabilities"][0]["id"] == TEST_CAPABILITY_ID
    assert detail_payload["tenant_status"]["enabled_capabilities"] == [TEST_CAPABILITY_ID]

    caps_response = await tenant_admin_client.get(f"/api/v1/marketplace/capabilities/{TEST_INTEGRATION_ID}")
    assert caps_response.status_code == 200
    caps_payload = caps_response.json()
    assert caps_payload["capabilities"][0]["id"] == TEST_CAPABILITY_ID
    assert caps_payload["capabilities"][0]["enabled"] is True
