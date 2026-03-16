"""app/gateway/routers/consent.py — Contact consent management (DSGVO)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user
from app.core.models import ContactConsent

router = APIRouter(prefix="/admin/contacts", tags=["consent"])


class ConsentIn(BaseModel):
    channel: str
    consent_given: bool = True
    consent_source: str = "import"
    ip_address: Optional[str] = None


@router.post("/{contact_id}/consent")
async def record_consent(
    contact_id: int,
    body: ConsentIn,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record or update consent for a contact on a specific channel."""
    existing = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == user.tenant_id,
        ContactConsent.contact_id == contact_id,
        ContactConsent.channel == body.channel,
    ).first()

    if existing:
        existing.consent_given = body.consent_given
        existing.given_at = datetime.now(timezone.utc) if body.consent_given else existing.given_at
        existing.revoked_at = datetime.now(timezone.utc) if not body.consent_given else None
        existing.consent_source = body.consent_source
    else:
        consent = ContactConsent(
            tenant_id=user.tenant_id,
            contact_id=contact_id,
            channel=body.channel,
            consent_given=body.consent_given,
            given_at=datetime.now(timezone.utc),
            consent_source=body.consent_source,
            ip_address=body.ip_address,
        )
        db.add(consent)

    db.commit()
    return {"status": "ok", "contact_id": contact_id, "channel": body.channel}


@router.delete("/{contact_id}/consent/{channel}")
async def revoke_consent(
    contact_id: int,
    channel: str,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke consent for a contact on a specific channel."""
    consent = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == user.tenant_id,
        ContactConsent.contact_id == contact_id,
        ContactConsent.channel == channel,
    ).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent record not found")
    consent.consent_given = False
    consent.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "revoked"}


@router.get("/{contact_id}/consents")
async def list_consents(
    contact_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all consent records for a contact."""
    consents = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == user.tenant_id,
        ContactConsent.contact_id == contact_id,
    ).all()
    return [
        {
            "id": c.id,
            "channel": c.channel,
            "consent_given": c.consent_given,
            "given_at": c.given_at.isoformat() if c.given_at else None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            "consent_source": c.consent_source,
        }
        for c in consents
    ]
