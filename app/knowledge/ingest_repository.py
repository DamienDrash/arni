from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.identity.models import Tenant


class KnowledgeIngestRepository:
    """Focused tenant lookup access for knowledge ingestion."""

    def get_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def list_active_tenants(self, db: Session) -> list[Tenant]:
        return db.query(Tenant).filter(Tenant.is_active.is_(True)).all()


ingest_repository = KnowledgeIngestRepository()
