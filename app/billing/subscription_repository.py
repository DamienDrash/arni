from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.billing.models import PlanV2, SubscriptionV2, TenantAddonV2


class SubscriptionRepository:
    """Focused data access for subscription lifecycle operations."""

    def get_subscription_by_tenant(self, db: Session, tenant_id: int) -> SubscriptionV2 | None:
        return db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()

    def get_active_plan_by_slug(self, db: Session, plan_slug: str) -> PlanV2 | None:
        return (
            db.query(PlanV2)
            .filter(PlanV2.slug == plan_slug, PlanV2.is_active.is_(True))
            .first()
        )

    def get_plan_by_id(self, db: Session, plan_id: int | None) -> PlanV2 | None:
        if plan_id is None:
            return None
        return db.query(PlanV2).filter(PlanV2.id == plan_id).first()

    def list_pending_subscriptions_due(self, db: Session, *, now: datetime) -> list[SubscriptionV2]:
        return (
            db.query(SubscriptionV2)
            .filter(
                SubscriptionV2.pending_plan_id.isnot(None),
                SubscriptionV2.scheduled_change_at <= now,
            )
            .all()
        )

    def list_active_addons_by_tenant(self, db: Session, tenant_id: int) -> list[TenantAddonV2]:
        return (
            db.query(TenantAddonV2)
            .filter(TenantAddonV2.tenant_id == tenant_id, TenantAddonV2.is_active.is_(True))
            .all()
        )


subscription_repository = SubscriptionRepository()
