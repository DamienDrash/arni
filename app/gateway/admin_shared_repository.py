from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.identity.models import AuditLog, Tenant


class AdminSharedRepository:
    """Focused DB access for shared admin helper paths."""

    def get_tenant_by_slug(self, db: Session, *, tenant_slug: str) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.slug == tenant_slug).first()

    def add_audit_log(
        self,
        db: Session,
        *,
        actor_user_id: int | str | None,
        actor_email: str | None,
        tenant_id: int | None,
        action: str,
        category: str,
        target_type: str | None,
        target_id: str | None,
        details_json: str | None,
    ) -> AuditLog:
        row = AuditLog(
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            tenant_id=tenant_id,
            action=action,
            category=category,
            target_type=target_type,
            target_id=target_id,
            details_json=details_json,
        )
        db.add(row)
        return row


admin_shared_repository = AdminSharedRepository()
