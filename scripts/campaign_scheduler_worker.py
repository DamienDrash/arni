"""ARIIA v2.2 – Campaign Scheduler Worker with Omnichannel Orchestration.

Polls the database every 30 seconds for campaigns with status='scheduled'
whose scheduled_at has passed, then dispatches them via the appropriate
messaging adapter. Supports multi-step orchestration sequences.

@ARCH: Campaign Refactoring Phase 1 Task 1.6, Phase 3 Task 3.5
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

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


# ── Campaign Discovery ────────────────────────────────────────────────

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


def get_orchestration_pending(db: Session):
    """Find recipients waiting for the next orchestration step."""
    from app.core.models import CampaignRecipient, Campaign
    from app.core.analytics_models import CampaignOrchestrationStep

    now = datetime.now(timezone.utc)

    # Find recipients in multi-step campaigns that need the next step
    results = (
        db.query(CampaignRecipient, Campaign)
        .join(Campaign, CampaignRecipient.campaign_id == Campaign.id)
        .filter(
            Campaign.status == "sent",
            CampaignRecipient.status.in_(["sent", "delivered"]),
            CampaignRecipient.current_step.isnot(None),
        )
        .all()
    )

    pending = []
    for recipient, campaign in results:
        # Check if there's a next step
        next_step = (
            db.query(CampaignOrchestrationStep)
            .filter(
                CampaignOrchestrationStep.campaign_id == campaign.id,
                CampaignOrchestrationStep.step_order == (recipient.current_step or 1) + 1,
            )
            .first()
        )
        if not next_step:
            continue

        # Check wait time
        sent_at = recipient.sent_at or recipient.delivered_at
        if not sent_at:
            continue

        wait_until = sent_at + timedelta(hours=next_step.wait_hours)
        if now < wait_until:
            continue

        # Check condition
        if _check_step_condition(recipient, next_step.condition_type):
            pending.append((recipient, campaign, next_step))

    return pending


def _check_step_condition(recipient, condition_type: str | None) -> bool:
    """Check if the condition for the next orchestration step is met."""
    if not condition_type or condition_type == "always":
        return True
    if condition_type == "if_not_opened":
        return recipient.opened_at is None
    if condition_type == "if_not_clicked":
        return recipient.clicked_at is None
    return True


# ── Recipient Resolution ──────────────────────────────────────────────

async def resolve_recipients(db: Session, campaign) -> list:
    """Resolve the target audience to a list of contacts."""
    from app.core.contact_models import Contact

    tenant_id = campaign.tenant_id

    if campaign.target_type == "all_members":
        return (
            db.query(Contact)
            .filter(Contact.tenant_id == tenant_id, Contact.deleted_at.is_(None))
            .all()
        )

    if campaign.target_type == "segment" and campaign.target_filter_json:
        try:
            filters = json.loads(campaign.target_filter_json)
            segment_id = filters.get("segment_id")
            if segment_id:
                from app.contacts.repository import ContactRepository
                from app.core.contact_models import ContactSegment
                repo = ContactRepository()
                # Load the segment from DB to get filter_groups
                segment = db.query(ContactSegment).filter(
                    ContactSegment.id == segment_id,
                    ContactSegment.tenant_id == tenant_id,
                ).first()
                if segment and segment.filter_groups_json:
                    filter_groups = json.loads(segment.filter_groups_json)
                    group_connector = segment.group_connector or "and"
                    contacts, _total = repo.evaluate_segment_v2(
                        db, tenant_id, filter_groups, group_connector,
                        page=1, page_size=100000,
                    )
                    return contacts
                elif segment and segment.filter_json:
                    # Legacy flat filter fallback
                    filter_data = json.loads(segment.filter_json)
                    filter_groups = [{"connector": "and", "rules": [
                        {"field": k, "operator": "eq", "value": v}
                        for k, v in filter_data.items() if v
                    ]}]
                    contacts, _total = repo.evaluate_segment_v2(
                        db, tenant_id, filter_groups, "and",
                        page=1, page_size=100000,
                    )
                    return contacts
                else:
                    logger.warning("scheduler.segment_no_filters", segment_id=segment_id)
                    return []
        except Exception as e:
            logger.error("scheduler.segment_resolve_failed", error=str(e), campaign_id=campaign.id)
            return []

    # Fallback: all active contacts (not soft-deleted)
    return (
        db.query(Contact)
        .filter(Contact.tenant_id == tenant_id, Contact.deleted_at.is_(None))
        .all()
    )


# ── Orchestration Helpers ─────────────────────────────────────────────

def get_orchestration_steps(db: Session, campaign_id: int) -> list:
    """Get all orchestration steps for a campaign, ordered by step_order."""
    from app.core.analytics_models import CampaignOrchestrationStep

    return (
        db.query(CampaignOrchestrationStep)
        .filter(CampaignOrchestrationStep.campaign_id == campaign_id)
        .order_by(CampaignOrchestrationStep.step_order)
        .all()
    )


def get_step_channel(campaign, step=None) -> str:
    """Determine the channel for sending. Uses step channel if available."""
    if step and step.channel:
        return step.channel
    return campaign.channel


# ── Rendering & Sending ──────────────────────────────────────────────

async def render_and_send(db: Session, campaign, contacts: list):
    """Render personalized messages and send via the appropriate adapter.

    Supports both single-channel and multi-step orchestration campaigns.
    """
    from app.campaign_engine.renderer import MessageRenderer
    from app.core.models import CampaignRecipient, Tenant

    renderer = MessageRenderer()
    tenant = db.query(Tenant).filter(Tenant.id == campaign.tenant_id).first()

    # Check for orchestration steps
    steps = get_orchestration_steps(db, campaign.id)
    first_step = steps[0] if steps else None
    has_orchestration = len(steps) > 1

    # Determine channel for first step
    channel = get_step_channel(campaign, first_step)

    # Update campaign status
    campaign.status = "sending"
    campaign.stats_total = len(contacts)
    db.commit()

    sent_count = 0
    failed_count = 0

    for contact in contacts:
        try:
            # Create recipient record first (needed for tracking)
            recipient = CampaignRecipient(
                campaign_id=campaign.id,
                tenant_id=campaign.tenant_id,
                member_id=getattr(contact, "id", None),
                contact_id=getattr(contact, "id", None),
                channel=channel,
                status="pending",
                current_step=1 if has_orchestration else None,
            )
            db.add(recipient)
            db.flush()  # Get the recipient.id for tracking

            # Render personalized message (with tracking pixel/link rewriting)
            rendered = await renderer.render(
                db, campaign, contact,
                recipient_id=recipient.id,
            )

            # Dispatch via adapter
            success = await dispatch_message(
                db=db,
                tenant=tenant,
                channel=channel,
                contact=contact,
                rendered=rendered,
            )

            # Update recipient status
            recipient.status = "sent" if success else "failed"
            recipient.sent_at = datetime.now(timezone.utc) if success else None
            if not success:
                recipient.error_message = "Dispatch failed"

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
        has_orchestration=has_orchestration,
        steps_count=len(steps),
    )


async def process_orchestration_step(db: Session, recipient, campaign, step):
    """Process a single orchestration follow-up step for a recipient."""
    from app.campaign_engine.renderer import MessageRenderer
    from app.core.models import Tenant
    from app.core.contact_models import Contact

    renderer = MessageRenderer()
    tenant = db.query(Tenant).filter(Tenant.id == campaign.tenant_id).first()
    contact = db.query(Contact).filter(Contact.id == (recipient.contact_id or recipient.member_id)).first()

    if not contact:
        logger.warning("scheduler.orchestration_no_contact", recipient_id=recipient.id)
        return

    channel = step.channel

    try:
        # Render with step-specific content override if available
        rendered = await renderer.render(
            db, campaign, contact,
            recipient_id=recipient.id,
        )

        # Override body if step has content_override
        if step.content_override_json:
            try:
                override = json.loads(step.content_override_json)
                if override.get("body"):
                    rendered.body_html = override["body"]
                    rendered.body_text = override.get("body_text", override["body"])
                if override.get("subject"):
                    rendered.subject = override["subject"]
            except json.JSONDecodeError:
                pass

        success = await dispatch_message(
            db=db,
            tenant=tenant,
            channel=channel,
            contact=contact,
            rendered=rendered,
        )

        # Update recipient
        recipient.current_step = step.step_order
        recipient.channel = channel
        if success:
            recipient.status = "sent"
            recipient.sent_at = datetime.now(timezone.utc)
        else:
            recipient.status = "failed"
            recipient.error_message = f"Orchestration step {step.step_order} failed"

        db.commit()

        logger.info(
            "scheduler.orchestration_step_sent",
            recipient_id=recipient.id,
            campaign_id=campaign.id,
            step_order=step.step_order,
            channel=channel,
            success=success,
        )

    except Exception as e:
        logger.error(
            "scheduler.orchestration_step_error",
            recipient_id=recipient.id,
            step_order=step.step_order,
            error=str(e),
        )


# ── Message Dispatch ──────────────────────────────────────────────────

async def dispatch_message(db, tenant, channel: str, contact, rendered) -> bool:
    """Dispatch a single message via the integration adapter."""
    try:
        from app.integrations.adapters.registry import get_adapter_registry

        registry = get_adapter_registry()
        tenant_id = tenant.id if tenant else 0

        if channel == "email":
            email = getattr(contact, "email", None)
            if not email:
                return False
            adapter = registry.get_adapter("email")
            if adapter:
                result = await adapter.execute_capability(
                    "messaging.send.html_email",
                    tenant_id=tenant_id,
                    to_email=email,
                    subject=rendered.subject,
                    html_body=rendered.body_html,
                    text_body=rendered.body_text,
                )
                return result.success if result else False

        elif channel == "whatsapp":
            phone = getattr(contact, "phone", None)
            if not phone:
                return False
            adapter = registry.get_adapter("whatsapp")
            if adapter:
                result = await adapter.execute_capability(
                    "messaging.send.whatsapp",
                    tenant_id=tenant_id,
                    to=phone,
                    message=rendered.body_text,
                )
                return result.success if result else False

        elif channel == "sms":
            phone = getattr(contact, "phone", None)
            if not phone:
                return False
            adapter = registry.get_adapter("sms")
            if adapter:
                result = await adapter.execute_capability(
                    "messaging.send.sms",
                    tenant_id=tenant_id,
                    to=phone,
                    message=rendered.body_text,
                )
                return result.success if result else False

        elif channel == "telegram":
            telegram_id = getattr(contact, "telegram_id", None) or getattr(contact, "phone", None)
            if not telegram_id:
                return False
            adapter = registry.get_adapter("telegram")
            if adapter:
                result = await adapter.execute_capability(
                    "messaging.send.telegram",
                    tenant_id=tenant_id,
                    chat_id=telegram_id,
                    message=rendered.body_text,
                )
                return result.success if result else False

        logger.warning("scheduler.no_adapter", channel=channel)
        return False

    except Exception as e:
        logger.error("scheduler.dispatch_error", channel=channel, error=str(e))
        return False


# ── Main Processing Loop ─────────────────────────────────────────────

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

        # 3. Process orchestration follow-up steps
        pending_steps = get_orchestration_pending(db)
        for recipient, campaign, step in pending_steps:
            logger.info(
                "scheduler.processing_orchestration",
                recipient_id=recipient.id,
                campaign_id=campaign.id,
                step_order=step.step_order,
            )
            await process_orchestration_step(db, recipient, campaign, step)

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
        features=["single_channel", "omnichannel_orchestration", "tracking"],
    )

    while True:
        try:
            await process_campaigns()
        except Exception as e:
            logger.error("campaign_scheduler.loop_error", error=str(e))

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
