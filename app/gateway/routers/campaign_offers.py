"""Admin API for Campaign Offers — opt-in lead magnets with URL-param routing."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, get_current_user
from app.core.db import get_db
from app.core.models import CampaignOffer

router = APIRouter(prefix="/admin/campaign-offers", tags=["campaign-offers"])


class OfferBody(BaseModel):
    slug: str
    name: str
    confirmation_message: str
    attachment_url: Optional[str] = None
    attachment_filename: Optional[str] = None
    is_active: bool = True


class OfferPatch(BaseModel):
    name: Optional[str] = None
    confirmation_message: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_filename: Optional[str] = None
    is_active: Optional[bool] = None


def _out(o: CampaignOffer) -> dict:
    return {
        "id": o.id,
        "slug": o.slug,
        "name": o.name,
        "confirmation_message": o.confirmation_message,
        "attachment_url": o.attachment_url,
        "attachment_filename": o.attachment_filename,
        "is_active": o.is_active,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


@router.get("")
def list_offers(user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_out(o) for o in db.query(CampaignOffer).filter(
        CampaignOffer.tenant_id == user.tenant_id
    ).order_by(CampaignOffer.name).all()]


@router.post("", status_code=201)
def create_offer(body: OfferBody, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    slug = body.slug.lower().strip().replace(" ", "-")
    existing = db.query(CampaignOffer).filter(
        CampaignOffer.tenant_id == user.tenant_id,
        CampaignOffer.slug == slug,
    ).first()
    if existing:
        raise HTTPException(409, f"Angebot mit slug '{slug}' existiert bereits")
    now = datetime.now(timezone.utc)
    offer = CampaignOffer(
        tenant_id=user.tenant_id,
        slug=slug,
        name=body.name,
        confirmation_message=body.confirmation_message,
        attachment_url=body.attachment_url,
        attachment_filename=body.attachment_filename,
        is_active=body.is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return _out(offer)


@router.patch("/{offer_id}")
def update_offer(offer_id: int, body: OfferPatch, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    offer = db.query(CampaignOffer).filter(
        CampaignOffer.id == offer_id,
        CampaignOffer.tenant_id == user.tenant_id,
    ).first()
    if not offer:
        raise HTTPException(404, "Angebot nicht gefunden")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(offer, k, v)
    offer.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(offer)
    return _out(offer)


@router.delete("/{offer_id}", status_code=204)
def delete_offer(offer_id: int, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    offer = db.query(CampaignOffer).filter(
        CampaignOffer.id == offer_id,
        CampaignOffer.tenant_id == user.tenant_id,
    ).first()
    if not offer:
        raise HTTPException(404, "Angebot nicht gefunden")
    db.delete(offer)
    db.commit()
