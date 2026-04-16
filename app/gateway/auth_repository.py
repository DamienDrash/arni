from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domains.billing.models import Plan
from app.domains.identity.models import PendingInvitation, Tenant, UserAccount


class AuthRepository:
    """Focused data-access helpers for the auth surface."""

    def get_user_by_email(self, db: Session, email: str) -> UserAccount | None:
        return db.query(UserAccount).filter(UserAccount.email == email).first()

    def get_user_by_id(self, db: Session, user_id: int) -> UserAccount | None:
        return db.query(UserAccount).filter(UserAccount.id == user_id).first()

    def get_active_user_by_id(self, db: Session, user_id: int) -> UserAccount | None:
        return (
            db.query(UserAccount)
            .filter(UserAccount.id == user_id, UserAccount.is_active.is_(True))
            .first()
        )

    def user_email_exists(self, db: Session, email: str) -> bool:
        return self.get_user_by_email(db, email) is not None

    def list_users_for_scope(self, db: Session, tenant_id: int | None = None) -> list[UserAccount]:
        query = db.query(UserAccount)
        if tenant_id is not None:
            query = query.filter(UserAccount.tenant_id == tenant_id)
        return query.all()

    def get_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_active_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return (
            db.query(Tenant)
            .filter(Tenant.id == tenant_id, Tenant.is_active.is_(True))
            .first()
        )

    def list_tenants(self, db: Session) -> list[Tenant]:
        return db.query(Tenant).all()

    def tenant_slug_exists(self, db: Session, slug: str, *, exclude_id: int | None = None) -> bool:
        query = db.query(Tenant).filter(Tenant.slug == slug)
        if exclude_id is not None:
            query = query.filter(Tenant.id != exclude_id)
        return query.first() is not None

    def get_plan_by_slug(self, db: Session, slug: str) -> Plan | None:
        return db.query(Plan).filter(Plan.slug == slug, Plan.is_active.is_(True)).first()

    def get_pending_invitation(
        self,
        db: Session,
        *,
        invitation_id: int | None = None,
        token_hash: str | None = None,
        tenant_id: int | None = None,
        email: str | None = None,
        only_unaccepted: bool = False,
        only_unexpired: bool = False,
    ) -> PendingInvitation | None:
        query = db.query(PendingInvitation)
        if invitation_id is not None:
            query = query.filter(PendingInvitation.id == invitation_id)
        if token_hash is not None:
            query = query.filter(PendingInvitation.token == token_hash)
        if tenant_id is not None:
            query = query.filter(PendingInvitation.tenant_id == tenant_id)
        if email is not None:
            query = query.filter(PendingInvitation.email == email)
        if only_unaccepted:
            query = query.filter(PendingInvitation.accepted_at.is_(None))
        if only_unexpired:
            query = query.filter(PendingInvitation.expires_at > datetime.now(timezone.utc))
        return query.first()

    def list_invitations_for_tenant(self, db: Session, tenant_id: int) -> list[PendingInvitation]:
        return (
            db.query(PendingInvitation)
            .filter(PendingInvitation.tenant_id == tenant_id)
            .order_by(PendingInvitation.created_at.desc())
            .all()
        )


auth_repo = AuthRepository()
