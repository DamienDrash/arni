"""ARIIA v2.1 – Campaign Scheduler Worker.

Polls the database every 30 seconds for campaigns with status='scheduled'
whose scheduled_at has passed, then dispatches them via the appropriate
messaging adapter (email, WhatsApp, SMS, Telegram).

@ARCH: Campaign Refactoring Phase 1, Task 1.6
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

import structlog

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = structlog.get_logger()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://ariia:ariia_dev_password@ariia-postgres:5432/ariia",
)
POLL_INTERVAL = int(os.environ.get("CAMPAIGN_POLL_INTERVAL", "30"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=3)
SessionLocal = sessionmaker(bind=engine)


def get_due_campaigns(db: Session):
    """Find all campaigns that are scheduled and due for sending."""
    from app.core.models import Campaign

    now = datetime.now(timezone.utc)
    return (
        db.query(Campaign)
        .filter(
            Campaign.status == "scheduled",
            Campaign.scheduled_at.isnot(None),
            Campaign.scheduled_at <= now,
        )
        .all()
    )


def get_approved_campaigns(db: Session):
    """Find approved campaigns with no scheduled_at (send immediately)."""
    from app.core.models import Campaign

    return (
        db.query(Campaign)
        .filter(
            Campaign.status == "approved",
            Campaign.scheduled_at.is_(None),
        )
        .all()
    )


async def resolve_recipients(db: Session, campaign) -> list:
    """Resolve the target audience to a list of contacts."""
    from app.core.contact_models import Contact

    tenant_id = campaign.tenant_id

    if campaign.target_type == "all_members":
        return (
            db.query(Contact)
            .filter(Contact.tenant_id == tenant_id, Contact.is_active.is_(True))
            .all()
        )

    if campaign.target_type == "segment" and campaign.target_filter_json:
        try:
            filters = json.loads(campaign.target_filter_json)
            segment_id = filters.get("segment_id")
            if segment_id:
                from app.contacts.repository import ContactRepository
                repo = ContactRepository(db)
                return repo.evaluate_segment_v2(segment_id, tenant_id)
        except Exception as e:
            logger.error("scheduler.segment_resolve_failed", error=str(e), campaign_id=campaign.id)
            return []

    # Fallback: all active contacts
    return (
        db.query(Contact)
        .filter(Contact.tenant_id == tenant_id, Contact.is_active.is_(True))
        .all()
    )


async def render_and_send(db: Session, campaign, contacts: list):
    """Render personalized messages and send via the appropriate adapter."""
    from app.campaign_engine.renderer import MessageRenderer
    from app.core.models import CampaignRecipient, Tenant

    renderer = MessageRenderer()
    tenant = db.query(Tenant).filter(Tenant.id == campaign.tenant_id).first()

    # Update campaign status
    campaign.status = "sending"
    campaign.stats_total = len(contacts)
    db.commit()

    sent_count = 0
    failed_count = 0

    for contact in contacts:
        try:
            # Render personalized message
            rendered = await renderer.render(db, campaign, contact)

            # Dispatch via adapter
            success = await dispatch_message(
                db=db,
                tenant=tenant,
                channel=campaign.channel,
                contact=contact,
                rendered=rendered,
            )

            # Record recipient
            recipient = CampaignRecipient(
                campaign_id=campaign.id,
                tenant_id=campaign.tenant_id,
                member_id=getattr(contact, "id", None),
                channel=campaign.channel,
                status="sent" if success else "failed",
                sent_at=datetime.now(timezone.utc) if success else None,
            )
            db.add(recipient)

            if success:
                sent_count += 1
            else:
                failed_count += 1

        except Exception as e:
            logger.error(
                "scheduler.send_failed",
                campaign_id=campaign.id,
                contact_id=getattr(contact, "id", None),
                error=str(e),
            )
            failed_count += 1

    # Update campaign stats
    campaign.stats_sent = sent_count
    campaign.stats_failed = failed_count
    campaign.status = "sent"
    campaign.sent_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "scheduler.campaign_sent",
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        total=len(contacts),
        sent=sent_count,
        failed=failed_count,
    )


async def dispatch_message(db, tenant, channel: str, contact, rendered) -> bool:
    """Dispatch a single message via the integration adapter."""
    try:
        from app.integrations.adapters.base import AdapterRegistry

        registry = AdapterRegistry()

        if channel == "email":
            email = getattr(contact, "email", None)
            if not email:
                return False
            adapter = registry.get_adapter("email", tenant_id=tenant.id if tenant else None)
            if adapter:
                result = await adapter.execute_capability(
                    "send_email",
                    to=email,
                    subject=rendered.subject,
                    body_html=rendered.body_html,
                    body_text=rendered.body_text,
                )
                return result.success if result else False

        elif channel == "whatsapp":
            phone = getattr(contact, "phone", None)
            if not phone:
                return False
            adapter = registry.get_adapter("whatsapp", tenant_id=tenant.id if tenant else None)
            if adapter:
                result = await adapter.execute_capability(
                    "send_message",
                    to=phone,
                    message=rendered.body_text,
                )
                return result.success if result else False

        elif channel == "sms":
            phone = getattr(contact, "phone", None)
            if not phone:
                return False
            adapter = registry.get_adapter("sms", tenant_id=tenant.id if tenant else None)
            if adapter:
                result = await adapter.execute_capability(
                    "send_sms",
                    to=phone,
                    message=rendered.body_text,
                )
                return result.success if result else False

        elif channel == "telegram":
            telegram_id = getattr(contact, "telegram_id", None) or getattr(contact, "phone", None)
            if not telegram_id:
                return False
            adapter = registry.get_adapter("telegram", tenant_id=tenant.id if tenant else None)
            if adapter:
                result = await adapter.execute_capability(
                    "send_message",
                    chat_id=telegram_id,
                    message=rendered.body_text,
                )
                return result.success if result else False

        logger.warning("scheduler.no_adapter", channel=channel)
        return False

    except Exception as e:
        logger.error("scheduler.dispatch_error", channel=channel, error=str(e))
        return False


async def process_campaigns():
    """Main processing loop iteration."""
    db = SessionLocal()
    try:
        # 1. Process scheduled campaigns that are due
        due_campaigns = get_due_campaigns(db)
        for campaign in due_campaigns:
            logger.info("scheduler.processing_scheduled", campaign_id=campaign.id, name=campaign.name)
            contacts = await resolve_recipients(db, campaign)
            if contacts:
                await render_and_send(db, campaign, contacts)
            else:
                logger.warning("scheduler.no_recipients", campaign_id=campaign.id)
                campaign.status = "failed"
                db.commit()

        # 2. Process approved campaigns with immediate send
        immediate_campaigns = get_approved_campaigns(db)
        for campaign in immediate_campaigns:
            logger.info("scheduler.processing_immediate", campaign_id=campaign.id, name=campaign.name)
            contacts = await resolve_recipients(db, campaign)
            if contacts:
                await render_and_send(db, campaign, contacts)
            else:
                logger.warning("scheduler.no_recipients", campaign_id=campaign.id)
                campaign.status = "failed"
                db.commit()

    except Exception as e:
        logger.error("scheduler.process_error", error=str(e))
    finally:
        db.close()


async def main():
    """Main entry point – polls every POLL_INTERVAL seconds."""
    logger.info(
        "campaign_scheduler.started",
        poll_interval=POLL_INTERVAL,
        database=DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "configured",
    )

    while True:
        try:
            await process_campaigns()
        except Exception as e:
            logger.error("campaign_scheduler.loop_error", error=str(e))

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
