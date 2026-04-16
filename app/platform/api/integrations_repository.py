from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.integration_models import (
    CapabilityDefinition,
    IntegrationCapability,
    IntegrationDefinition,
    TenantIntegration,
)


class IntegrationsRepository:
    """Data access for integration-registry and tenant-integration CRUD."""

    def list_integrations(
        self,
        db: Session,
        *,
        category: str | None = None,
        is_public: bool | None = None,
    ) -> list[IntegrationDefinition]:
        query = select(IntegrationDefinition).where(IntegrationDefinition.is_active == True)
        if category:
            query = query.where(IntegrationDefinition.category == category)
        if is_public is not None:
            query = query.where(IntegrationDefinition.is_public == is_public)
        return db.execute(query).scalars().all()

    def get_integration(self, db: Session, *, integration_id: str) -> IntegrationDefinition | None:
        return db.get(IntegrationDefinition, integration_id)

    def create_integration(self, db: Session, *, data: dict) -> IntegrationDefinition:
        integration = IntegrationDefinition(**data)
        db.add(integration)
        return integration

    def list_capability_ids_for_integration(self, db: Session, *, integration_id: str) -> list[str]:
        return list(
            db.execute(
                select(IntegrationCapability.capability_id).where(
                    IntegrationCapability.integration_id == integration_id
                )
            ).scalars().all()
        )

    def get_capability(self, db: Session, *, capability_id: str) -> CapabilityDefinition | None:
        return db.get(CapabilityDefinition, capability_id)

    def list_capabilities(self, db: Session, *, category: str | None = None) -> list[CapabilityDefinition]:
        query = select(CapabilityDefinition)
        if category:
            query = query.where(CapabilityDefinition.category == category)
        return db.execute(query).scalars().all()

    def create_capability(self, db: Session, *, data: dict) -> CapabilityDefinition:
        capability = CapabilityDefinition(**data)
        db.add(capability)
        return capability

    def get_integration_capability_link(
        self,
        db: Session,
        *,
        integration_id: str,
        capability_id: str,
    ) -> IntegrationCapability | None:
        return db.execute(
            select(IntegrationCapability)
            .where(IntegrationCapability.integration_id == integration_id)
            .where(IntegrationCapability.capability_id == capability_id)
        ).scalar_one_or_none()

    def create_integration_capability_link(
        self,
        db: Session,
        *,
        integration_id: str,
        capability_id: str,
    ) -> IntegrationCapability:
        link = IntegrationCapability(integration_id=integration_id, capability_id=capability_id)
        db.add(link)
        return link

    def list_tenant_integrations(self, db: Session, *, tenant_id: int) -> list[TenantIntegration]:
        return list(
            db.execute(
                select(TenantIntegration).where(TenantIntegration.tenant_id == tenant_id)
            ).scalars().all()
        )

    def get_tenant_integration(
        self,
        db: Session,
        *,
        tenant_id: int,
        integration_id: str,
    ) -> TenantIntegration | None:
        return db.execute(
            select(TenantIntegration)
            .where(TenantIntegration.tenant_id == tenant_id)
            .where(TenantIntegration.integration_id == integration_id)
        ).scalar_one_or_none()

    def create_tenant_integration(
        self,
        db: Session,
        *,
        tenant_id: int,
        integration_id: str,
        config_meta: dict | None,
        status: str,
    ) -> TenantIntegration:
        tenant_integration = TenantIntegration(
            tenant_id=tenant_id,
            integration_id=integration_id,
            config_meta=config_meta,
            status=status,
        )
        db.add(tenant_integration)
        return tenant_integration


integrations_repository = IntegrationsRepository()
