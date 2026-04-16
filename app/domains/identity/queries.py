from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.identity.models import AuditLog, Tenant


class IdentityQueries:
    """Cross-domain read access for identity-owned entities."""

    def get_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_active_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return (
            db.query(Tenant)
            .filter(Tenant.id == tenant_id, Tenant.is_active.is_(True))
            .first()
        )

    def list_recent_audits(self, db: Session, *, tenant_id: int, limit: int) -> list[AuditLog]:
        return (
            db.query(AuditLog)
            .filter(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_audit_logs(
        self,
        db: Session,
        *,
        tenant_id: int,
        action_filter: str | None = None,
    ) -> int:
        query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
        if action_filter:
            query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
        return query.count()

    def list_audit_logs(
        self,
        db: Session,
        *,
        tenant_id: int,
        limit: int,
        offset: int,
        action_filter: str | None = None,
    ) -> list[AuditLog]:
        query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
        if action_filter:
            query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
        return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()


identity_queries = IdentityQueries()
