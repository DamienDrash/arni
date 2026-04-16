from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domains.billing.models import Plan, Subscription, UsageRecord
from app.domains.billing.queries import billing_queries
from app.domains.identity.models import AuditLog, Tenant
from app.domains.identity.queries import identity_queries
from app.domains.platform.models import TenantConfig
from app.domains.platform.queries import platform_queries
from app.domains.support.queries import support_queries


class TenantPortalRepository:
    """Read/write data access for tenant portal self-service flows."""

    def get_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return identity_queries.get_tenant_by_id(db, tenant_id)

    def get_subscription_by_tenant(self, db: Session, tenant_id: int) -> Subscription | None:
        return billing_queries.get_subscription_by_tenant(db, tenant_id)

    def get_plan_by_id(self, db: Session, plan_id: int | None) -> Plan | None:
        return billing_queries.get_plan_by_id(db, plan_id)

    def count_conversations_since(self, db: Session, *, tenant_id: int, since: datetime) -> int:
        return support_queries.count_conversations_since(db, tenant_id=tenant_id, since=since)

    def list_recent_audits(self, db: Session, *, tenant_id: int, limit: int) -> list[AuditLog]:
        return identity_queries.list_recent_audits(db, tenant_id=tenant_id, limit=limit)

    def list_usage_records_since(self, db: Session, *, tenant_id: int, since: datetime) -> list[UsageRecord]:
        return billing_queries.list_usage_records_since(db, tenant_id=tenant_id, since=since)

    def count_audit_logs(
        self,
        db: Session,
        *,
        tenant_id: int,
        action_filter: str | None = None,
    ) -> int:
        return identity_queries.count_audit_logs(
            db,
            tenant_id=tenant_id,
            action_filter=action_filter,
        )

    def list_audit_logs(
        self,
        db: Session,
        *,
        tenant_id: int,
        limit: int,
        offset: int,
        action_filter: str | None = None,
    ) -> list[AuditLog]:
        return identity_queries.list_audit_logs(
            db,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            action_filter=action_filter,
        )

    def get_tenant_config(self, db: Session, *, tenant_id: int, key: str) -> TenantConfig | None:
        return platform_queries.get_tenant_config(db, tenant_id=tenant_id, key=key)

    def set_tenant_config(self, db: Session, *, tenant_id: int, key: str, value: str) -> TenantConfig:
        return platform_queries.set_tenant_config(db, tenant_id=tenant_id, key=key, value=value)


tenant_portal_repository = TenantPortalRepository()
