from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.domains.campaigns.models import Campaign, CampaignOffer


class CampaignQueries:
    """Cross-domain read access for campaign-owned entities."""

    def get_campaign_for_tenant(
        self,
        db: Session,
        *,
        tenant_id: int,
        campaign_id: int,
    ) -> Campaign | None:
        return (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
            .first()
        )

    def get_active_offer_for_tenant(
        self,
        db: Session,
        *,
        tenant_id: int,
        slug: str,
    ) -> CampaignOffer | None:
        return (
            db.query(CampaignOffer)
            .filter(
                CampaignOffer.tenant_id == tenant_id,
                CampaignOffer.slug == slug,
                CampaignOffer.is_active.is_(True),
            )
            .first()
        )

    def get_active_campaign_by_featured_asset(
        self,
        db: Session,
        *,
        tenant_id: int,
        asset_id: int,
        statuses: Iterable[str] = ("draft", "scheduled", "sending"),
    ) -> Campaign | None:
        normalized_statuses = tuple(statuses)
        if not normalized_statuses:
            return None
        return (
            db.query(Campaign)
            .filter(
                Campaign.tenant_id == tenant_id,
                Campaign.featured_image_asset_id == asset_id,
                Campaign.status.in_(normalized_statuses),
            )
            .first()
        )


campaign_queries = CampaignQueries()
