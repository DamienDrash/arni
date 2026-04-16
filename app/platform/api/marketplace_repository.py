from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.integration_models import (
    CapabilityDefinition,
    IntegrationCapability,
    IntegrationDefinition,
    TenantIntegration,
)
from app.domains.billing.queries import billing_queries


class MarketplaceRepository:
    """Data access for marketplace self-service flows."""

    def get_tenant_plan_slug(self, db: Session, tenant_id: int) -> str | None:
        return billing_queries.get_tenant_plan_slug(db, tenant_id)

    def list_active_integrations(
        self,
        db: Session,
        *,
        category: str | None = None,
    ) -> list[IntegrationDefinition]:
        query = db.query(IntegrationDefinition).filter(IntegrationDefinition.is_active == True)
        if category:
            query = query.filter(IntegrationDefinition.category == category)
        return query.all()

    def get_integration(
        self,
        db: Session,
        *,
        integration_id: str,
    ) -> IntegrationDefinition | None:
        return db.query(IntegrationDefinition).filter(IntegrationDefinition.id == integration_id).first()

    def list_capabilities(
        self,
        db: Session,
        *,
        integration_id: str,
    ) -> list[CapabilityDefinition]:
        return (
            db.query(CapabilityDefinition)
            .join(IntegrationCapability, IntegrationCapability.capability_id == CapabilityDefinition.id)
            .filter(IntegrationCapability.integration_id == integration_id)
            .all()
        )

    def list_capability_ids(
        self,
        db: Session,
        *,
        integration_id: str,
    ) -> list[str]:
        rows = (
            db.query(IntegrationCapability.capability_id)
            .filter(IntegrationCapability.integration_id == integration_id)
            .all()
        )
        return [row[0] for row in rows]

    def list_tenant_integrations(
        self,
        db: Session,
        *,
        tenant_id: int,
    ) -> list[TenantIntegration]:
        return db.query(TenantIntegration).filter(TenantIntegration.tenant_id == tenant_id).all()

    def get_tenant_integration(
        self,
        db: Session,
        *,
        tenant_id: int,
        integration_id: str,
    ) -> TenantIntegration | None:
        return (
            db.query(TenantIntegration)
            .filter(
                TenantIntegration.tenant_id == tenant_id,
                TenantIntegration.integration_id == integration_id,
            )
            .first()
        )

    def list_active_tenant_integration_ids(
        self,
        db: Session,
        *,
        tenant_id: int,
    ) -> set[str]:
        active = (
            db.query(TenantIntegration.integration_id)
            .filter(
                TenantIntegration.tenant_id == tenant_id,
                TenantIntegration.status != "inactive",
                TenantIntegration.enabled == True,
            )
            .all()
        )
        return {row[0] for row in active}


marketplace_repository = MarketplaceRepository()
