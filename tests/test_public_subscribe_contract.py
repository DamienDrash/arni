from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import SessionLocal
from app.domains.campaigns.models import Campaign, CampaignOffer
from app.domains.identity.models import Tenant
from app.edge.app import app
from app.gateway.routers.public_subscribe import _encode_token


def _seed_public_subscribe_fixture() -> tuple[str, str]:
    db = SessionLocal()
    try:
        db.query(CampaignOffer).filter(CampaignOffer.tenant_id == 973001).delete()
        db.query(Campaign).filter(Campaign.tenant_id == 973001).delete()
        db.query(Tenant).filter(Tenant.id == 973001).delete()

        db.add(Tenant(id=973001, slug="public-demo", name="Public Demo", is_active=True))
        db.add(
            Campaign(
                id=973011,
                tenant_id=973001,
                name="Spring Promo",
                description="Jetzt Fruehjahrsvorteile sichern",
                channel="email",
                status="draft",
            )
        )
        db.add(
            CampaignOffer(
                tenant_id=973001,
                slug="welcome-bonus",
                name="Welcome Bonus",
                confirmation_message="Danke fuer deine Anmeldung.",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    subscribe_token = _encode_token(973001, 973011, "email")
    unsubscribe_token = _encode_token(973001, 111111, "email")
    return subscribe_token, unsubscribe_token


@pytest.mark.anyio
async def test_public_subscribe_info_resolves_active_tenant_campaign_and_offer() -> None:
    subscribe_token, _ = _seed_public_subscribe_fixture()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/public/subscribe/{subscribe_token}?offer=welcome-bonus")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_name"] == "Public Demo"
    assert payload["campaign_name"] == "Spring Promo"
    assert payload["description"] == "Jetzt Fruehjahrsvorteile sichern"
    assert payload["offer_name"] == "Welcome Bonus"
    assert payload["channel"] == "email"


@pytest.mark.anyio
async def test_public_unsubscribe_info_resolves_active_tenant() -> None:
    _, unsubscribe_token = _seed_public_subscribe_fixture()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/public/unsubscribe/{unsubscribe_token}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_name"] == "Public Demo"
    assert payload["channel"] == "email"
