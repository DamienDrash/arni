from __future__ import annotations

from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.domains.billing.models import ImageCreditBalance, Plan, Subscription
from app.domains.identity.models import Tenant
from app.media.credit_service import add_credits, deduct_credits, get_balance, maybe_grant_monthly_credits


def _seed_credit_fixture(tenant_id: int, monthly_credits: int = 12) -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.query(ImageCreditBalance).filter(ImageCreditBalance.tenant_id == tenant_id).delete()
        db.query(Subscription).filter(Subscription.tenant_id == tenant_id).delete()
        db.query(Plan).filter(Plan.id == tenant_id).delete()
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()

        db.add(Tenant(id=tenant_id, slug=f"credits-{tenant_id}", name=f"Credits {tenant_id}"))
        db.add(
            Plan(
                id=tenant_id,
                name="Credits Plan",
                slug=f"credits-plan-{tenant_id}",
                price_monthly_cents=0,
                trial_days=0,
                monthly_image_credits=monthly_credits,
            )
        )
        db.add(
            Subscription(
                tenant_id=tenant_id,
                plan_id=tenant_id,
                status="active",
                current_period_start=now,
            )
        )
        db.commit()
    finally:
        db.close()


def test_media_credit_service_reads_balance_and_monthly_grant_via_billing_queries() -> None:
    tenant_id = 971001
    _seed_credit_fixture(tenant_id, monthly_credits=7)

    db = SessionLocal()
    try:
        assert get_balance(db, tenant_id) == 0
        assert maybe_grant_monthly_credits(db, tenant_id) == 7
        assert get_balance(db, tenant_id) == 7
        assert maybe_grant_monthly_credits(db, tenant_id) == 0
    finally:
        db.close()


def test_media_credit_service_add_and_deduct_preserve_balance() -> None:
    tenant_id = 971002
    _seed_credit_fixture(tenant_id, monthly_credits=0)

    db = SessionLocal()
    try:
        assert add_credits(db, tenant_id, 10, reason="manual_adjustment") == 10
        assert deduct_credits(db, tenant_id, 4, reason="generation") is True
        assert get_balance(db, tenant_id) == 6
        assert deduct_credits(db, tenant_id, 99, reason="generation") is False
        assert get_balance(db, tenant_id) == 6
    finally:
        db.close()
