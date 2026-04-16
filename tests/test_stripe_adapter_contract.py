from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.db import SessionLocal
from app.core.models import Plan, Subscription, Tenant
from app.integrations.adapters.stripe_adapter import StripeAdapter


TEST_TENANT_ID = 920001
TEST_PLAN_SLUG = "stripe-adapter-test"
TEST_CUSTOMER_ID = "cus_contract_920001"
TEST_SUBSCRIPTION_ID = "sub_contract_920001"


def _seed_subscription_fixture() -> None:
    db = SessionLocal()
    try:
        subscription = db.query(Subscription).filter(Subscription.tenant_id == TEST_TENANT_ID).first()
        if subscription:
            db.delete(subscription)

        tenant = db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).first()
        if tenant:
            db.delete(tenant)

        plan = db.query(Plan).filter(Plan.slug == TEST_PLAN_SLUG).first()
        if plan:
            db.delete(plan)

        db.flush()

        plan = Plan(
            name="Stripe Contract Plan",
            slug=TEST_PLAN_SLUG,
            price_monthly_cents=4900,
        )
        tenant = Tenant(
            id=TEST_TENANT_ID,
            slug="stripe-adapter-contract",
            name="Stripe Adapter Contract",
            is_active=True,
        )
        db.add_all([plan, tenant])
        db.flush()

        db.add(
            Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active",
                stripe_subscription_id=TEST_SUBSCRIPTION_ID,
                stripe_customer_id=None,
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_stripe_subscription_status_reads_via_shared_session() -> None:
    _seed_subscription_fixture()
    adapter = StripeAdapter()

    result = await adapter.execute_capability("payment.subscription.status", tenant_id=TEST_TENANT_ID)

    assert result.success is True
    assert result.data["subscription_id"] == TEST_SUBSCRIPTION_ID
    assert result.data["status"] == "active"
    assert result.data["plan_name"] == "Stripe Contract Plan"
    assert result.data["plan_tier"] == TEST_PLAN_SLUG


@pytest.mark.anyio
async def test_stripe_customer_create_persists_customer_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_subscription_fixture()
    adapter = StripeAdapter()

    class _FakeCustomerAPI:
        @staticmethod
        def create(**kwargs):
            return SimpleNamespace(
                id=TEST_CUSTOMER_ID,
                email=kwargs.get("email"),
                name=kwargs.get("name"),
            )

    fake_stripe = SimpleNamespace(Customer=_FakeCustomerAPI)
    monkeypatch.setattr(adapter, "_get_stripe_module", lambda: (fake_stripe, None))

    result = await adapter.execute_capability("payment.customer.create", tenant_id=TEST_TENANT_ID)

    assert result.success is True
    assert result.data["customer_id"] == TEST_CUSTOMER_ID
    assert result.data["action"] == "created_new"
    assert result.data["name"] == "Stripe Adapter Contract"

    db = SessionLocal()
    try:
        subscription = db.query(Subscription).filter(Subscription.tenant_id == TEST_TENANT_ID).first()
        assert subscription is not None
        assert subscription.stripe_customer_id == TEST_CUSTOMER_ID
    finally:
        db.close()
