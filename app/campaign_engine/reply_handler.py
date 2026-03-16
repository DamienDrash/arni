"""ARIIA – Inbound Reply Opt-in Handler.

When a contact replies to a campaign with an opt-in keyword (e.g. "JA", "YES"),
this handler:
1. Records ContactConsent for the campaign channel (DSGVO)
2. Transitions the CampaignRecipient status from "awaiting_optin" → "confirmed"
3. Enqueues the actual campaign send job
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.models import Campaign, CampaignRecipient, ContactConsent

logger = structlog.get_logger()

OPT_IN_KEYWORDS = {"ja", "yes", "anmelden", "subscribe", "ok", "1", "join"}


def _resolve_contact_id(db: Session, tenant_id: int, phone: str) -> int | None:
    """Resolve a contact ID from a phone number."""
    try:
        from app.core.contact_models import Contact
        contact = db.query(Contact).filter(
            Contact.tenant_id == tenant_id,
            Contact.phone == phone,
        ).first()
        return contact.id if contact else None
    except Exception:
        return None


async def handle_campaign_reply(
    tenant_id: int,
    phone: str,
    message_text: str,
    db: Session,
) -> bool:
    """Check if an inbound message is an opt-in reply and handle it.

    Returns True if the message was handled (caller should skip swarm routing).
    """
    text_lower = message_text.strip().lower()
    if text_lower not in OPT_IN_KEYWORDS:
        return False

    # Resolve contact_id from phone
    contact_id = _resolve_contact_id(db, tenant_id, phone)
    if not contact_id:
        return False

    # Find pending CampaignRecipient with status "awaiting_optin"
    pending = db.query(CampaignRecipient).filter(
        CampaignRecipient.contact_id == contact_id,
        CampaignRecipient.tenant_id == tenant_id,
        CampaignRecipient.status == "awaiting_optin",
    ).first()

    if not pending:
        return False

    # Determine channel from campaign
    campaign = db.query(Campaign).filter(Campaign.id == pending.campaign_id).first()
    channel = pending.channel or (campaign.channel if campaign else "whatsapp")

    # Record consent (DSGVO)
    existing_consent = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == tenant_id,
        ContactConsent.contact_id == contact_id,
        ContactConsent.channel == channel,
    ).first()

    if existing_consent:
        existing_consent.consent_given = True
        existing_consent.given_at = datetime.now(timezone.utc)
        existing_consent.revoked_at = None
        existing_consent.consent_source = "double_optin"
    else:
        db.add(ContactConsent(
            tenant_id=tenant_id,
            contact_id=contact_id,
            channel=channel,
            consent_given=True,
            given_at=datetime.now(timezone.utc),
            consent_source="double_optin",
        ))

    # Transition recipient status
    pending.status = "confirmed"
    db.commit()

    logger.info(
        "campaign_reply.optin_confirmed",
        tenant_id=tenant_id,
        contact_id=contact_id,
        campaign_id=pending.campaign_id,
        channel=channel,
    )

    # Enqueue the actual send
    from app.campaign_engine.send_queue import enqueue_send_job
    enqueue_send_job(
        campaign_id=pending.campaign_id,
        recipient_id=pending.id,
        contact_id=contact_id,
        tenant_id=tenant_id,
        channel=channel,
    )

    return True
