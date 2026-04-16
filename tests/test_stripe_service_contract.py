from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.billing.models import InvoiceRecord, PlanV2, SubscriptionV2
from app.billing.stripe_service import StripeServiceV2
from app.core.db import SessionLocal
from app.core.models import Tenant


TEST_TENANT_ID = 930001
TEST_PLAN_SLUG = "stripe-service-pro"
TEST_PRICE_ID = "price_service_monthly_930001"
TEST_CUSTOMER_ID = "cus_service_930001"
TEST_SUBSCRIPTION_ID = "sub_service_930001"
TEST_INVOICE_ID = "in_service_930001"


def _seed_stripe_service_fixture() -> None:
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

        tenant = Tenant(
            id=TEST_TENANT_ID,
            slug="stripe-service-contract",
            name="Stripe Service Contract",
            is_active=True,
        )
        plan = PlanV2(
            name="Stripe Service Pro",
            slug=TEST_PLAN_SLUG,
            price_monthly_cents=9900,
            stripe_price_monthly_id=TEST_PRICE_ID,
            is_active=True,
        )
        db.add_all([tenant, plan])
        db.flush()

        db.add(
            SubscriptionV2(
                tenant_id=tenant.id,
                plan_id=plan.id,
                stripe_subscription_id=TEST_SUBSCRIPTION_ID,
                stripe_customer_id=None,
                status="active",
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_get_or_create_customer_persists_customer_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_stripe_service_fixture()
    service = StripeServiceV2()

    class _FakeCustomerAPI:
        @staticmethod
        def create(**kwargs):
            return SimpleNamespace(
                id=TEST_CUSTOMER_ID,
                email=kwargs.get("email"),
                name=kwargs.get("name"),
            )

    monkeypatch.setattr(
        "app.billing.stripe_service._get_stripe",
        lambda: SimpleNamespace(Customer=_FakeCustomerAPI),
    )

    db = SessionLocal()
    try:
        result = await service.get_or_create_customer(db, TEST_TENANT_ID)
        assert result["id"] == TEST_CUSTOMER_ID
        assert result["action"] == "created"

        subscription = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == TEST_TENANT_ID).first()
        assert subscription is not None
        assert subscription.stripe_customer_id == TEST_CUSTOMER_ID
    finally:
        db.close()


@pytest.mark.anyio
async def test_create_checkout_session_reads_plan_via_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_stripe_service_fixture()
    service = StripeServiceV2()

    class _FakeCheckoutSessionAPI:
        @staticmethod
        def create(**kwargs):
            assert kwargs["line_items"][0]["price"] == TEST_PRICE_ID
            return SimpleNamespace(id="cs_service_930001", url="https://stripe.test/checkout", status="open")

    monkeypatch.setattr(
        "app.billing.stripe_service._get_stripe",
        lambda: SimpleNamespace(checkout=SimpleNamespace(Session=_FakeCheckoutSessionAPI)),
    )

    async def _fake_get_or_create_customer(db, tenant_id, email=None, name=None):
        return {"id": TEST_CUSTOMER_ID}

    monkeypatch.setattr(service, "get_or_create_customer", _fake_get_or_create_customer)

    db = SessionLocal()
    try:
        result = await service.create_checkout_session(db, TEST_TENANT_ID, TEST_PLAN_SLUG)
        assert result["session_id"] == "cs_service_930001"
        assert result["status"] == "open"
    finally:
        db.close()


@pytest.mark.anyio
async def test_sync_invoices_upserts_local_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_stripe_service_fixture()
    service = StripeServiceV2()

    class _FakeInvoiceAPI:
        @staticmethod
        def list(customer, limit):
            assert customer == TEST_CUSTOMER_ID
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        id=TEST_INVOICE_ID,
                        subscription=TEST_SUBSCRIPTION_ID,
                        number="INV-930001",
                        status="paid",
                        currency="eur",
                        amount_due=9900,
                        amount_paid=9900,
                        amount_remaining=0,
                        hosted_invoice_url="https://stripe.test/invoice",
                        invoice_pdf="https://stripe.test/invoice.pdf",
                        period_start=None,
                        period_end=None,
                        created=1710000000,
                    )
                ]
            )

    monkeypatch.setattr(
        "app.billing.stripe_service._get_stripe",
        lambda: SimpleNamespace(Invoice=_FakeInvoiceAPI),
    )

    db = SessionLocal()
    try:
        subscription = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == TEST_TENANT_ID).first()
        assert subscription is not None
        subscription.stripe_customer_id = TEST_CUSTOMER_ID
        db.commit()

        result = await service.sync_invoices(db, TEST_TENANT_ID)
        assert result[0]["id"] == TEST_INVOICE_ID

        local = db.query(InvoiceRecord).filter(InvoiceRecord.stripe_invoice_id == TEST_INVOICE_ID).first()
        assert local is not None
        assert local.tenant_id == TEST_TENANT_ID
        assert local.status == "paid"
    finally:
        db.close()
