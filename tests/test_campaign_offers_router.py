from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.core.db import SessionLocal
from app.core.models import CampaignOffer


def _tenant_admin_headers() -> dict[str, str]:
    token = create_access_token(
        user_id=2,
        email="tenantadmin@test.local",
        tenant_id=1,
        tenant_slug="default",
        role="tenant_admin",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def tenant_admin_client() -> AsyncClient:
    from app.edge.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=_tenant_admin_headers(),
    ) as client:
        yield client


def _cleanup_offer(slug: str) -> None:
    db = SessionLocal()
    try:
        db.query(CampaignOffer).filter(
            CampaignOffer.tenant_id == 1,
            CampaignOffer.slug == slug,
        ).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_create_and_list_campaign_offer_is_tenant_scoped(
    tenant_admin_client: AsyncClient,
) -> None:
    slug = f"lead-magnet-{int(time.time() * 1000)}"
    try:
        create_response = await tenant_admin_client.post(
            "/admin/campaign-offers",
            json={
                "slug": slug,
                "name": "Lead Magnet",
                "confirmation_message": "Danke fuer deine Anmeldung",
                "is_active": True,
            },
        )
        assert create_response.status_code == 201
        assert create_response.json()["slug"] == slug

        list_response = await tenant_admin_client.get("/admin/campaign-offers")
        assert list_response.status_code == 200
        slugs = {item["slug"] for item in list_response.json()}
        assert slug in slugs
    finally:
        _cleanup_offer(slug)


@pytest.mark.anyio
async def test_duplicate_slug_conflicts_and_patch_updates_offer(
    tenant_admin_client: AsyncClient,
) -> None:
    slug = f"offer-{int(time.time() * 1000)}"
    try:
        create_response = await tenant_admin_client.post(
            "/admin/campaign-offers",
            json={
                "slug": slug,
                "name": "Original",
                "confirmation_message": "Willkommen",
                "is_active": True,
            },
        )
        assert create_response.status_code == 201
        offer_id = create_response.json()["id"]

        duplicate_response = await tenant_admin_client.post(
            "/admin/campaign-offers",
            json={
                "slug": slug,
                "name": "Original",
                "confirmation_message": "Willkommen",
                "is_active": True,
            },
        )
        assert duplicate_response.status_code == 409

        patch_response = await tenant_admin_client.patch(
            f"/admin/campaign-offers/{offer_id}",
            json={"name": "Updated", "is_active": False},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["name"] == "Updated"
        assert patch_response.json()["is_active"] is False
    finally:
        _cleanup_offer(slug)
