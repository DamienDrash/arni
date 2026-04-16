from __future__ import annotations

from sqlalchemy.orm import Session

from app.billing.models import InvoiceRecord, SubscriptionV2, TenantAddonV2


class WebhookRepository:
    """Focused data access for Stripe webhook processing."""

    def get_subscription_by_tenant(self, db: Session, tenant_id: int) -> SubscriptionV2 | None:
        return db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()

    def get_subscription_by_customer(self, db: Session, customer_id: str | None) -> SubscriptionV2 | None:
        if not customer_id:
            return None
        return (
            db.query(SubscriptionV2)
            .filter(SubscriptionV2.stripe_customer_id == customer_id)
            .first()
        )

    def get_invoice_record_by_stripe_id(
        self,
        db: Session,
        stripe_invoice_id: str,
    ) -> InvoiceRecord | None:
        return db.query(InvoiceRecord).filter(InvoiceRecord.stripe_invoice_id == stripe_invoice_id).first()

    def get_or_create_invoice_record(
        self,
        db: Session,
        *,
        tenant_id: int,
        stripe_invoice_id: str,
    ) -> InvoiceRecord:
        existing = self.get_invoice_record_by_stripe_id(db, stripe_invoice_id)
        if existing:
            return existing
        record = InvoiceRecord(tenant_id=tenant_id, stripe_invoice_id=stripe_invoice_id)
        db.add(record)
        return record

    def get_tenant_addon(
        self,
        db: Session,
        *,
        tenant_id: int,
        addon_slug: str,
    ) -> TenantAddonV2 | None:
        return (
            db.query(TenantAddonV2)
            .filter(TenantAddonV2.tenant_id == tenant_id, TenantAddonV2.addon_slug == addon_slug)
            .first()
        )


webhook_repository = WebhookRepository()
