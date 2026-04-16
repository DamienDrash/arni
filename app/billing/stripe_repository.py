from __future__ import annotations

from sqlalchemy.orm import Session

from app.billing.models import AddonDefinitionV2, InvoiceRecord, PlanV2, SubscriptionV2
from app.domains.identity.models import Tenant


class StripeBillingRepository:
    """Focused data access for Stripe billing service."""

    def get_subscription_by_tenant(self, db: Session, tenant_id: int) -> SubscriptionV2 | None:
        return db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()

    def get_tenant_by_id(self, db: Session, tenant_id: int) -> Tenant | None:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_active_plan_by_slug(self, db: Session, plan_slug: str) -> PlanV2 | None:
        return (
            db.query(PlanV2)
            .filter(PlanV2.slug == plan_slug, PlanV2.is_active.is_(True))
            .first()
        )

    def get_active_addon_by_slug(self, db: Session, addon_slug: str) -> AddonDefinitionV2 | None:
        return (
            db.query(AddonDefinitionV2)
            .filter(AddonDefinitionV2.slug == addon_slug, AddonDefinitionV2.is_active.is_(True))
            .first()
        )

    def list_active_plans(self, db: Session) -> list[PlanV2]:
        return db.query(PlanV2).filter(PlanV2.is_active.is_(True)).all()

    def list_active_addons(self, db: Session) -> list[AddonDefinitionV2]:
        return db.query(AddonDefinitionV2).filter(AddonDefinitionV2.is_active.is_(True)).all()

    def get_invoice_record_by_stripe_id(self, db: Session, stripe_invoice_id: str) -> InvoiceRecord | None:
        return db.query(InvoiceRecord).filter(InvoiceRecord.stripe_invoice_id == stripe_invoice_id).first()

    def get_or_create_invoice_record(
        self,
        db: Session,
        *,
        tenant_id: int,
        stripe_invoice_id: str,
    ) -> InvoiceRecord:
        record = self.get_invoice_record_by_stripe_id(db, stripe_invoice_id)
        if record:
            return record
        record = InvoiceRecord(tenant_id=tenant_id, stripe_invoice_id=stripe_invoice_id)
        db.add(record)
        return record


stripe_billing_repository = StripeBillingRepository()
