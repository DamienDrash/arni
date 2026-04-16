from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.billing.models import BillingInterval, SubscriptionStatus, SubscriptionV2
from app.core.db import SessionLocal


async def _register_tenant(client: AsyncClient, suffix: str) -> tuple[str, int]:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    response = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Billing V2 {unique}",
            "tenant_slug": f"billing-v2-{unique}",
            "email": f"admin-{unique}@billing-v2.example",
            "password": "TestPass!1234",
            "full_name": "Billing V2 Admin",
            "accept_tos": True,
            "accept_privacy": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["access_token"], data["user"]["tenant_id"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_billing_v2_plans_is_public(client: AsyncClient) -> None:
    response = await client.get("/billing/plans")
    assert response.status_code == 200
    plans = response.json()
    slugs = {plan["slug"] for plan in plans}
    assert {"starter", "pro", "enterprise"}.issubset(slugs)


@pytest.mark.anyio
async def test_billing_v2_subscription_returns_default_state_for_new_tenant(
    client: AsyncClient,
) -> None:
    token, _tenant_id = await _register_tenant(client, "sub-default")
    response = await client.get("/billing/subscription", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json() == {"has_subscription": False, "status": "none"}


@pytest.mark.anyio
async def test_billing_v2_subscription_includes_pending_downgrade(
    client: AsyncClient,
) -> None:
    token, tenant_id = await _register_tenant(client, "pending-downgrade")

    db = SessionLocal()
    try:
        from app.billing.models import PlanV2

        current_plan = db.query(PlanV2).filter(PlanV2.slug == "pro").first()
        pending_plan = db.query(PlanV2).filter(PlanV2.slug == "starter").first()
        assert current_plan is not None
        assert pending_plan is not None

        db.add(
            SubscriptionV2(
                tenant_id=tenant_id,
                plan_id=current_plan.id,
                status=SubscriptionStatus.ACTIVE,
                billing_interval=BillingInterval.MONTH,
                stripe_subscription_id=f"sub_test_{tenant_id}",
                stripe_customer_id=f"cus_test_{tenant_id}",
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
                cancel_at_period_end=False,
                pending_plan_id=pending_plan.id,
                scheduled_change_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
        )
        db.commit()
    finally:
        db.close()

    response = await client.get("/billing/subscription", headers=_auth_header(token))
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_subscription"] is True
    assert payload["plan_slug"] == "pro"
    assert payload["pending_downgrade"]["plan_slug"] == "starter"
    assert payload["pending_downgrade"]["plan_name"] == "Starter"
