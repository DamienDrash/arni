from __future__ import annotations

from sqlalchemy.orm import Session

from app.billing.models import AddonDefinitionV2, PlanV2
from app.domains.billing.models import AddonDefinition, Plan, Subscription
from app.domains.identity.models import Tenant


class AdminBillingRepository:
    """Focused data access for admin billing read models."""

    def list_plans(self, db: Session) -> list[Plan]:
        return db.query(Plan).order_by(Plan.price_monthly_cents.asc()).all()

    def list_plans_for_admin(self, db: Session) -> list[Plan]:
        return (
            db.query(Plan)
            .order_by(Plan.display_order.asc(), Plan.price_monthly_cents.asc())
            .all()
        )

    def get_subscription_by_tenant(self, db: Session, tenant_id: int) -> Subscription | None:
        return db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()

    def get_plan_by_id(self, db: Session, plan_id: int | None) -> Plan | None:
        if plan_id is None:
            return None
        return db.query(Plan).filter(Plan.id == plan_id).first()

    def get_tenant_by_id(self, db: Session, tenant_id: int | None) -> Tenant | None:
        if tenant_id is None:
            return None
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def list_subscribers(self, db: Session) -> list[Subscription]:
        return (
            db.query(Subscription)
            .filter(Subscription.status.in_(["active", "trialing", "past_due"]))
            .all()
        )

    def list_public_plans(self, db: Session) -> list[Plan]:
        return (
            db.query(Plan)
            .filter(Plan.is_active.is_(True), Plan.is_public.is_(True))
            .order_by(Plan.display_order.asc(), Plan.price_monthly_cents.asc())
            .all()
        )

    def list_active_addons(self, db: Session) -> list[AddonDefinition]:
        return (
            db.query(AddonDefinition)
            .filter(AddonDefinition.is_active.is_(True))
            .order_by(AddonDefinition.display_order.asc(), AddonDefinition.name.asc())
            .all()
        )

    def list_addons_for_admin(self, db: Session) -> list[AddonDefinition]:
        return (
            db.query(AddonDefinition)
            .order_by(AddonDefinition.display_order.asc(), AddonDefinition.name.asc())
            .all()
        )

    def list_v2_plans(self, db: Session) -> list[PlanV2]:
        return (
            db.query(PlanV2)
            .order_by(PlanV2.display_order.asc(), PlanV2.price_monthly_cents.asc())
            .all()
        )

    def list_v2_addons(self, db: Session) -> list[AddonDefinitionV2]:
        return (
            db.query(AddonDefinitionV2)
            .order_by(AddonDefinitionV2.display_order.asc(), AddonDefinitionV2.name.asc())
            .all()
        )


admin_billing_repository = AdminBillingRepository()
