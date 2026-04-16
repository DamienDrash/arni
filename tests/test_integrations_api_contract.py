from __future__ import annotations

from app.core.db import SessionLocal
from app.core.integration_models import (
    CapabilityDefinition,
    IntegrationCapability,
    IntegrationDefinition,
    TenantIntegration,
)
from app.core.models import Tenant
from app.platform.api.integrations import (
    TenantIntegrationCreate,
    TenantIntegrationUpdate,
    activate_integration,
    list_tenant_integrations,
    update_tenant_integration,
)


TEST_TENANT_ID = 920301
TEST_INTEGRATION_ID = "registry_contract_integration"
TEST_CAPABILITY_ID = "registry.contract.capability"


def _seed_integrations_fixture() -> None:
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

        tenant = db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).first()
        if tenant is None:
            db.add(Tenant(id=TEST_TENANT_ID, slug="registry-contract", name="Registry Contract", is_active=True))

        link = (
            db.query(IntegrationCapability)
            .filter(
                IntegrationCapability.integration_id == TEST_INTEGRATION_ID,
                IntegrationCapability.capability_id == TEST_CAPABILITY_ID,
            )
            .first()
        )
        if link:
            db.delete(link)

        capability = db.get(CapabilityDefinition, TEST_CAPABILITY_ID)
        if capability:
            db.delete(capability)

        integration = db.get(IntegrationDefinition, TEST_INTEGRATION_ID)
        if integration:
            db.delete(integration)

        db.flush()

        db.add(
            IntegrationDefinition(
                id=TEST_INTEGRATION_ID,
                name="Registry Contract Integration",
                description="Integration registry contract",
                category="crm",
                is_active=True,
                is_public=True,
                min_plan="starter",
            )
        )
        db.add(
            CapabilityDefinition(
                id=TEST_CAPABILITY_ID,
                name="Registry Contract Capability",
                description="Capability for repository contract",
                category="crm",
            )
        )
        db.flush()
        db.add(
            IntegrationCapability(
                integration_id=TEST_INTEGRATION_ID,
                capability_id=TEST_CAPABILITY_ID,
            )
        )
        db.commit()
    finally:
        db.close()


def test_tenant_integration_activation_update_and_listing_use_repository_contract() -> None:
    _seed_integrations_fixture()
    db = SessionLocal()
    try:
        created = activate_integration(
            TEST_TENANT_ID,
            TenantIntegrationCreate(
                integration_id=TEST_INTEGRATION_ID,
                config_meta={"region": "eu"},
            ),
            db,
        )
        assert created.integration_id == TEST_INTEGRATION_ID
        assert created.integration_name == "Registry Contract Integration"
        assert created.status == "pending_setup"

        updated = update_tenant_integration(
            TEST_TENANT_ID,
            TEST_INTEGRATION_ID,
            TenantIntegrationUpdate(
                enabled=False,
                status="inactive",
                config_meta={"region": "us"},
            ),
            db,
        )
        assert updated.enabled is False
        assert updated.status == "inactive"
        assert updated.config_meta == {"region": "us"}

        listed = list_tenant_integrations(TEST_TENANT_ID, db)
        assert len(listed) == 1
        assert listed[0].integration_name == "Registry Contract Integration"
        assert listed[0].integration_id == TEST_INTEGRATION_ID
    finally:
        db.close()
