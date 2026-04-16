from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.integration_models import SyncLog, TenantIntegration
from app.domains.identity.models import Tenant


class ContactSyncRepository:
    """Focused DB access for contact-sync router compatibility paths."""

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

    def list_tenant_integrations(
        self,
        db: Session,
        *,
        tenant_id: int,
    ) -> list[TenantIntegration]:
        return db.query(TenantIntegration).filter(TenantIntegration.tenant_id == tenant_id).all()

    def list_sync_logs_since(
        self,
        db: Session,
        *,
        tenant_id: int,
        started_at_gte: datetime,
    ) -> list[SyncLog]:
        return (
            db.query(SyncLog)
            .filter(
                SyncLog.tenant_id == tenant_id,
                SyncLog.started_at >= started_at_gte,
            )
            .all()
        )

    def get_tenant_by_slug(
        self,
        db: Session,
        *,
        tenant_slug: str,
    ) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.slug == tenant_slug).first()


contact_sync_repository = ContactSyncRepository()
