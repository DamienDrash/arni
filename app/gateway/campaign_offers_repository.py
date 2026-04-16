from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.campaigns.models import CampaignOffer


class CampaignOffersRepository:
    """Focused DB access for tenant-scoped campaign offer CRUD."""

    def list_offers(self, db: Session, *, tenant_id: int) -> list[CampaignOffer]:
        return (
            db.query(CampaignOffer)
            .filter(CampaignOffer.tenant_id == tenant_id)
            .order_by(CampaignOffer.name)
            .all()
        )

    def get_offer_by_slug(
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
            )
            .first()
        )

    def get_offer_by_id(
        self,
        db: Session,
        *,
        tenant_id: int,
        offer_id: int,
    ) -> CampaignOffer | None:
        return (
            db.query(CampaignOffer)
            .filter(
                CampaignOffer.id == offer_id,
                CampaignOffer.tenant_id == tenant_id,
            )
            .first()
        )

    def add_offer(self, db: Session, *, offer: CampaignOffer) -> CampaignOffer:
        db.add(offer)
        return offer


campaign_offers_repository = CampaignOffersRepository()
