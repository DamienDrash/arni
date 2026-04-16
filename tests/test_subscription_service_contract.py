from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.billing.models import BillingInterval, PlanV2, SubscriptionStatus, SubscriptionV2
from app.billing.subscription_service import SubscriptionServiceV2
from app.core.db import SessionLocal
from app.core.models import Tenant


TEST_TENANT_ID = 920401
TEST_PLAN_SLUG = "subscription-service-starter"
TEST_UPGRADE_PLAN_SLUG = "subscription-service-pro"


def _seed_subscription_fixture() -> None:
    db = SessionLocal()
    try:
        existing = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == TEST_TENANT_ID).first()
        if existing:
            db.delete(existing)

        for slug in (TEST_PLAN_SLUG, TEST_UPGRADE_PLAN_SLUG):
            plan = db.query(PlanV2).filter(PlanV2.slug == slug).first()
            if plan:
                db.delete(plan)

        tenant = db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).first()
        if tenant:
            db.delete(tenant)

        db.flush()

        db.add(Tenant(id=TEST_TENANT_ID, slug="subscription-service-contract", name="Subscription Service Contract", is_active=True))
        db.add(
            PlanV2(
                slug=TEST_PLAN_SLUG,
                name="Subscription Starter",
                price_monthly_cents=1900,
                is_active=True,
                trial_days=0,
            )
        )
        db.add(
            PlanV2(
                slug=TEST_UPGRADE_PLAN_SLUG,
                name="Subscription Pro",
                price_monthly_cents=4900,
                is_active=True,
                trial_days=0,
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_subscription_service_create_and_upgrade_use_repository_contract() -> None:
    _seed_subscription_fixture()
    service = SubscriptionServiceV2()
    db = SessionLocal()
    try:
        created = await service.create_subscription(
            db,
            tenant_id=TEST_TENANT_ID,
            plan_slug=TEST_PLAN_SLUG,
            billing_interval=BillingInterval.MONTH,
        )
        assert created.status == SubscriptionStatus.ACTIVE

        upgraded = await service.upgrade(
            db,
            tenant_id=TEST_TENANT_ID,
            new_plan_slug=TEST_UPGRADE_PLAN_SLUG,
        )
        plan = db.query(PlanV2).filter(PlanV2.id == upgraded.plan_id).first()
        assert plan is not None
        assert plan.slug == TEST_UPGRADE_PLAN_SLUG
    finally:
        db.close()


@pytest.mark.anyio
async def test_subscription_service_apply_pending_changes_uses_repository_due_query() -> None:
    _seed_subscription_fixture()
    db = SessionLocal()
    try:
        starter = db.query(PlanV2).filter(PlanV2.slug == TEST_PLAN_SLUG).first()
        pro = db.query(PlanV2).filter(PlanV2.slug == TEST_UPGRADE_PLAN_SLUG).first()
        assert starter is not None
        assert pro is not None

        db.add(
            SubscriptionV2(
                tenant_id=TEST_TENANT_ID,
                plan_id=starter.id,
                pending_plan_id=pro.id,
                scheduled_change_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                status=SubscriptionStatus.ACTIVE,
                billing_interval=BillingInterval.MONTH,
            )
        )
        db.commit()

        service = SubscriptionServiceV2()
        updated_tenants = await service.apply_pending_changes(db)
        assert updated_tenants == [TEST_TENANT_ID]

        refreshed = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == TEST_TENANT_ID).first()
        assert refreshed is not None
        assert refreshed.plan_id == pro.id
        assert refreshed.pending_plan_id is None
    finally:
        db.close()
