"""app/gateway/routers/public_subscribe.py — Public subscription + unsubscribe endpoints (no auth).

Subscribe token format:   base64url("tenant_id:campaign_id:channel")
Unsubscribe token format: base64url("tenant_id:contact_id:channel")
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Campaign, CampaignOffer, ContactConsent, Tenant

logger = structlog.get_logger()

router = APIRouter(prefix="/public", tags=["public-subscribe"])


# ── Token helpers ──────────────────────────────────────────────────────────


def _encode_token(a: int, b: int, channel: str) -> str:
    raw = f"{a}:{b}:{channel}"
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def _decode_token(token: str) -> tuple[int, int, str]:
    """Decode a 3-part token into (int, int, channel)."""
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) != 3:
            raise ValueError("Expected 3 parts")
        a = int(parts[0])
        b = int(parts[1])
        channel = parts[2]
        if channel not in ("email", "whatsapp", "sms", "telegram"):
            raise ValueError(f"Invalid channel: {channel}")
        return a, b, channel
    except Exception as exc:
        logger.warning("public_token.invalid", token=token[:40], error=str(exc))
        raise HTTPException(status_code=400, detail="Ungültiger Link.") from exc


# ── Schemas ────────────────────────────────────────────────────────────────


class SubscribeIn(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# SUBSCRIBE
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/subscribe/{token}")
async def subscribe_info(token: str, offer: Optional[str] = None, db: Session = Depends(get_db)):
    """Return public context for the subscribe landing page."""
    tenant_id, campaign_id, channel = _decode_token(token)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    campaign_name: str | None = None
    description: str | None = None
    if campaign_id:
        campaign = db.query(Campaign).filter(
            Campaign.id == campaign_id, Campaign.tenant_id == tenant_id
        ).first()
        if campaign:
            campaign_name = campaign.name
            description = campaign.description

    # Resolve offer info so landing page can show tailored copy
    offer_name: str | None = None
    if offer:
        db_offer = db.query(CampaignOffer).filter(
            CampaignOffer.tenant_id == tenant_id,
            CampaignOffer.slug == offer.lower(),
            CampaignOffer.is_active.is_(True),
        ).first()
        if db_offer:
            offer_name = db_offer.name

    return {
        "tenant_name": tenant.name,
        "campaign_name": campaign_name,
        "channel": channel,
        "description": description,
        "offer_name": offer_name,
    }


@router.post("/subscribe/{token}")
async def subscribe(
    token: str,
    body: SubscribeIn,
    request: Request,
    offer: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Subscribe a contact. Stores offer_slug so double-opt-in reply delivers the right content."""
    tenant_id, campaign_id, channel = _decode_token(token)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    from app.core.contact_models import Contact

    contact = db.query(Contact).filter(
        Contact.tenant_id == tenant_id,
        Contact.email == body.email,
        Contact.deleted_at.is_(None),
    ).first() if body.email else None

    if not contact:
        contact = Contact(
            tenant_id=tenant_id,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            phone=body.phone,
            source="subscribe_form",
            lifecycle_stage="subscriber",
        )
        db.add(contact)
        db.flush()
    else:
        contact.first_name = body.first_name
        contact.last_name = body.last_name
        if body.phone:
            contact.phone = body.phone

    # Record DSGVO consent
    ip_address = request.client.host if request.client else None
    existing_consent = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == tenant_id,
        ContactConsent.contact_id == contact.id,
        ContactConsent.channel == channel,
    ).first()

    if existing_consent:
        existing_consent.consent_given = True
        existing_consent.given_at = datetime.now(timezone.utc)
        existing_consent.revoked_at = None
        existing_consent.consent_source = "form"
        existing_consent.ip_address = ip_address
    else:
        db.add(ContactConsent(
            tenant_id=tenant_id,
            contact_id=contact.id,
            channel=channel,
            consent_given=True,
            given_at=datetime.now(timezone.utc),
            consent_source="form",
            ip_address=ip_address,
        ))

    db.commit()

    # Enqueue campaign recipient, storing offer_slug for later delivery
    if campaign_id:
        campaign = db.query(Campaign).filter(
            Campaign.id == campaign_id, Campaign.tenant_id == tenant_id
        ).first()
        if campaign:
            try:
                from app.core.models import CampaignRecipient

                # Determine status: awaiting_optin if double-optin required, else pending
                requires_optin = getattr(campaign, "optin_require_reply", False)
                status = "awaiting_optin" if requires_optin else "pending"

                recipient = CampaignRecipient(
                    campaign_id=campaign.id,
                    tenant_id=tenant_id,
                    contact_id=contact.id,
                    channel=channel,
                    status=status,
                    offer_slug=offer.lower() if offer else None,
                )
                db.add(recipient)
                db.commit()

                if not requires_optin:
                    from app.campaign_engine.send_queue import enqueue_send_job
                    enqueue_send_job(
                        campaign_id=campaign.id,
                        recipient_id=recipient.id,
                        contact_id=contact.id,
                        tenant_id=tenant_id,
                        channel=channel,
                    )
            except Exception as exc:
                logger.error("public_subscribe.enqueue_failed", error=str(exc))

    logger.info("public_subscribe.success", tenant_id=tenant_id, contact_id=contact.id, offer=offer)
    return {"status": "ok", "message": "Erfolgreich angemeldet."}


# ══════════════════════════════════════════════════════════════════════════════
# UNSUBSCRIBE
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/unsubscribe/{token}")
async def unsubscribe_info(token: str, db: Session = Depends(get_db)):
    """Return context for the unsubscribe landing page."""
    tenant_id, contact_id, channel = _decode_token(token)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    return {
        "tenant_name": tenant.name,
        "channel": channel,
    }


@router.post("/unsubscribe/{token}")
async def unsubscribe(token: str, db: Session = Depends(get_db)):
    """Revoke consent for a contact via a tokenized unsubscribe link."""
    tenant_id, contact_id, channel = _decode_token(token)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    now = datetime.now(timezone.utc)
    consents = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == tenant_id,
        ContactConsent.contact_id == contact_id,
        ContactConsent.channel == channel,
        ContactConsent.consent_given.is_(True),
    ).all()

    for c in consents:
        c.consent_given = False
        c.revoked_at = now

    db.commit()

    logger.info("public_unsubscribe.success", tenant_id=tenant_id, contact_id=contact_id, channel=channel)
    return {"status": "ok", "message": "Erfolgreich abgemeldet."}


# ── Helper: generate an unsubscribe token for a contact ──────────────────────

def make_unsubscribe_token(tenant_id: int, contact_id: int, channel: str) -> str:
    return _encode_token(tenant_id, contact_id, channel)
