from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.core.db import SessionLocal
from app.domains.billing.models import ImageCreditPack, Plan, Subscription
from app.domains.identity.models import Tenant
from app.edge.app import app


@pytest.fixture
async def tenant_media_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="tenant-media-admin",
            email="media@test.example",
            tenant_id=972001,
            tenant_slug="media-router-tenant",
            role="tenant_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def _seed_media_router_fixture() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.query(Subscription).filter(Subscription.tenant_id == 972001).delete()
        db.query(Plan).filter(Plan.id == 972001).delete()
        db.query(Tenant).filter(Tenant.id == 972001).delete()
        db.query(ImageCreditPack).filter(ImageCreditPack.slug.in_(["media-pack-a", "media-pack-b"])).delete()

        db.add(Tenant(id=972001, slug="media-router-tenant", name="Media Router Tenant"))
        db.add(
            Plan(
                id=972001,
                name="Media Router Plan",
                slug="media-router-plan",
                price_monthly_cents=0,
                trial_days=0,
                monthly_image_credits=9,
            )
        )
        db.add(
            Subscription(
                tenant_id=972001,
                plan_id=972001,
                status="active",
                current_period_start=now,
            )
        )
        db.add_all(
            [
                ImageCreditPack(
                    slug="media-pack-a",
                    name="Pack A",
                    credits=25,
                    price_once_cents=500,
                    is_active=True,
                    display_order=2,
                ),
                ImageCreditPack(
                    slug="media-pack-b",
                    name="Pack B",
                    credits=50,
                    price_once_cents=900,
                    is_active=True,
                    display_order=1,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_media_credit_balance_uses_billing_query_grant_resolution(
    tenant_media_client: AsyncClient,
) -> None:
    _seed_media_router_fixture()

    response = await tenant_media_client.get("/admin/media/credits/balance")
    assert response.status_code == 200
    payload = response.json()
    assert payload["balance"] == 0
    assert payload["monthly_grant"] == 9
    assert payload["plan_slug"] == "media-router-plan"


@pytest.mark.anyio
async def test_media_credit_packs_returns_active_packs_sorted_by_display_order(
    tenant_media_client: AsyncClient,
) -> None:
    _seed_media_router_fixture()

    response = await tenant_media_client.get("/admin/media/credits/packs")
    assert response.status_code == 200
    payload = response.json()
    assert [pack["slug"] for pack in payload] == ["media-pack-b", "media-pack-a"]
