from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.billing.models import InvoiceRecord, PlanV2, SubscriptionStatus, SubscriptionV2
from app.billing.webhook_processor import webhook_processor
from app.core.db import SessionLocal
from app.core.models import Tenant


TEST_TENANT_ID = 920501
TEST_PLAN_SLUG = "webhook-processor-starter"
TEST_CUSTOMER_ID = "cus_webhook_contract_920501"
TEST_SUBSCRIPTION_ID = "sub_webhook_contract_920501"
TEST_INVOICE_ID = "in_webhook_contract_920501"


def _seed_webhook_fixture() -> None:
    db = SessionLocal()
    try:
        invoice = db.query(InvoiceRecord).filter(InvoiceRecord.stripe_invoice_id == TEST_INVOICE_ID).first()
        if invoice:
            db.delete(invoice)

        subscription = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == TEST_TENANT_ID).first()
        if subscription:
            db.delete(subscription)

        plan = db.query(PlanV2).filter(PlanV2.slug == TEST_PLAN_SLUG).first()
        if plan:
            db.delete(plan)

        tenant = db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).first()
        if tenant:
            db.delete(tenant)

        db.flush()

        tenant = Tenant(id=TEST_TENANT_ID, slug="webhook-processor-contract", name="Webhook Processor Contract", is_active=True)
        plan = PlanV2(slug=TEST_PLAN_SLUG, name="Webhook Starter", price_monthly_cents=2900, is_active=True)
        db.add_all([tenant, plan])
        db.flush()

        db.add(
            SubscriptionV2(
                tenant_id=tenant.id,
                plan_id=plan.id,
                stripe_subscription_id=TEST_SUBSCRIPTION_ID,
                stripe_customer_id=TEST_CUSTOMER_ID,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_webhook_processor_invoice_paid_uses_repository_lookup_and_upsert() -> None:
    _seed_webhook_fixture()
    db = SessionLocal()
    try:
        result = await webhook_processor._handle_invoice_paid(
            db,
            {
                "id": "evt_invoice_paid_contract",
                "data": {
                    "object": {
                        "id": TEST_INVOICE_ID,
                        "customer": TEST_CUSTOMER_ID,
                        "subscription": TEST_SUBSCRIPTION_ID,
                        "number": "INV-920501",
                        "currency": "eur",
                        "amount_due": 2900,
                        "amount_paid": 2900,
                        "hosted_invoice_url": "https://stripe.test/invoice",
                        "invoice_pdf": "https://stripe.test/invoice.pdf",
                    }
                },
            },
        )

        assert result["action"] == "invoice_paid"
        invoice = db.query(InvoiceRecord).filter(InvoiceRecord.stripe_invoice_id == TEST_INVOICE_ID).first()
        assert invoice is not None
        assert invoice.tenant_id == TEST_TENANT_ID
        assert invoice.status == "paid"

        subscription = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == TEST_TENANT_ID).first()
        assert subscription is not None
        assert subscription.stripe_latest_invoice_id == TEST_INVOICE_ID
    finally:
        db.close()


@pytest.mark.anyio
async def test_webhook_processor_subscription_deleted_marks_subscription_canceled() -> None:
    _seed_webhook_fixture()
    db = SessionLocal()
    try:
        result = await webhook_processor._handle_subscription_deleted(
            db,
            {
                "id": "evt_subscription_deleted_contract",
                "data": {
                    "object": {
                        "id": TEST_SUBSCRIPTION_ID,
                        "metadata": {"tenant_id": str(TEST_TENANT_ID)},
                    }
                },
            },
        )

        assert result["action"] == "subscription_canceled"
        subscription = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == TEST_TENANT_ID).first()
        assert subscription is not None
        assert subscription.status == SubscriptionStatus.CANCELED
        assert subscription.canceled_at is not None
    finally:
        db.close()
