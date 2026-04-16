from __future__ import annotations

from datetime import datetime, timezone
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.core.db import SessionLocal
from app.core.models import Plan, Subscription, Tenant, TokenPurchase, UsageRecord
from app.gateway.main import app


@pytest.fixture
async def system_admin_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="revenue-admin",
            email="revenue-admin@test.example",
            tenant_id=1,
            tenant_slug="system",
            role="system_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def _seed_revenue_fixture() -> tuple[int, int]:
    slug = f"revenue-router-test-{int(time.time() * 1000)}"
    plan_slug = "revenue-router-plan"
    db = SessionLocal()
    try:
        db.query(TokenPurchase).filter(TokenPurchase.tenant_id == 1).delete()
        db.query(UsageRecord).filter(UsageRecord.tenant_id == 1).delete()

        plan = db.query(Plan).filter(Plan.slug == plan_slug).first()
        if not plan:
            plan = Plan(
                name="Revenue Router Plan",
                slug=plan_slug,
                price_monthly_cents=9900,
                monthly_tokens=50000,
                is_active=True,
                is_public=False,
            )
            db.add(plan)
            db.flush()

        tenant = Tenant(name="Revenue Router Tenant", slug=slug, is_active=True)
        db.add(tenant)
        db.flush()

        now = datetime.now(timezone.utc)
        db.add(
            Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active",
                stripe_customer_id="cus_revenue_router_test",
                current_period_start=now,
                current_period_end=now,
            )
        )
        db.add(
            UsageRecord(
                tenant_id=tenant.id,
                period_year=now.year,
                period_month=now.month,
                messages_inbound=12,
                messages_outbound=8,
                active_members=5,
                llm_tokens_used=3456,
            )
        )
        db.add(
            TokenPurchase(
                tenant_id=tenant.id,
                tokens_amount=10000,
                price_cents=1200,
                status="completed",
            )
        )
        db.commit()
        return tenant.id, plan.id
    finally:
        db.close()


@pytest.mark.anyio
async def test_revenue_overview_falls_back_to_local_data_when_stripe_fails(
    system_admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_revenue_fixture()
    monkeypatch.setattr(
        "app.gateway.routers.revenue_analytics._get_stripe_for_system",
        lambda: (_ for _ in ()).throw(RuntimeError("stripe unavailable")),
    )

    response = await system_admin_client.get("/admin/revenue/overview")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["data_source"] == "stripe"
    assert payload["plan_mrr_cents"] >= 9900
    assert payload["token_revenue_cents"] >= 1200
    assert payload["total_subscribers"] >= 1
