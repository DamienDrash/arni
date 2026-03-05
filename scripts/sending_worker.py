"""ARIIA v2.3 – Sending Worker (Asynchronous Message Dispatch).

Reads send jobs from the Redis queue `campaign:send_queue` and dispatches
messages via the appropriate adapter. This decouples the scheduling/API layer
from the actual sending, improving resilience and scalability.

Jobs are enqueued by:
  - campaign_scheduler_worker.py (scheduled/approved campaigns)
  - campaigns.py send_campaign endpoint (manual sends)

Each job is a JSON object with the structure:
  {
    "campaign_id": int,
    "recipient_id": int,
    "contact_id": int,
    "tenant_id": int,
    "channel": str,           # email | whatsapp | sms | telegram
    "variant_name": str|null, # For A/B tests
    "enqueued_at": str,       # ISO 8601 timestamp
  }

@ARCH: Campaign Refactoring Phase 2 – TASK-009
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

import redis
import structlog

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = structlog.get_logger()

# ── Configuration ────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://ariia:ariia_dev_password@ariia-postgres:5432/ariia",
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://ariia-redis:6379/0")
SEND_QUEUE_KEY = "campaign:send_queue"
DEAD_LETTER_QUEUE_KEY = "campaign:send_dlq"
BATCH_SIZE = int(os.environ.get("SEND_BATCH_SIZE", "50"))
POLL_INTERVAL = float(os.environ.get("SEND_POLL_INTERVAL", "1"))
MAX_RETRIES = int(os.environ.get("SEND_MAX_RETRIES", "3"))
CONCURRENCY = int(os.environ.get("SEND_CONCURRENCY", "10"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(bind=engine)


def get_redis() -> redis.Redis:
    """Create a Redis client."""
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


# ── Message Dispatch ──────────────────────────────────────────────────────

async def dispatch_message(db: Session, tenant, channel: str, contact, rendered) -> bool:
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

        logger.warning("sending_worker.no_adapter", channel=channel)
        return False

    except Exception as e:
        logger.error("sending_worker.dispatch_error", channel=channel, error=str(e))
        return False


# ── Job Processing ────────────────────────────────────────────────────────

async def process_send_job(db: Session, job: dict) -> bool:
    """Process a single send job from the queue.

    Returns True if the message was sent successfully, False otherwise.
    """
    from app.campaign_engine.renderer import MessageRenderer
    from app.core.models import Campaign, CampaignRecipient, CampaignVariant, Tenant
    from app.core.contact_models import Contact

    campaign_id = job["campaign_id"]
    recipient_id = job["recipient_id"]
    contact_id = job["contact_id"]
    tenant_id = job["tenant_id"]
    channel = job.get("channel", "email")
    variant_name = job.get("variant_name")

    # Load entities from DB
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.id == recipient_id).first()
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not campaign or not recipient or not contact:
        logger.warning(
            "sending_worker.missing_entity",
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            contact_id=contact_id,
            campaign_found=campaign is not None,
            recipient_found=recipient is not None,
            contact_found=contact is not None,
        )
        if recipient:
            recipient.status = "failed"
            recipient.error_message = "Missing campaign, recipient, or contact entity"
            db.commit()
        return False

    try:
        renderer = MessageRenderer()

        # If this is an A/B test variant, temporarily override campaign content
        original_subject = campaign.content_subject
        original_body = campaign.content_body
        original_html = campaign.content_html

        if variant_name and variant_name != "holdout":
            variant = (
                db.query(CampaignVariant)
                .filter(
                    CampaignVariant.campaign_id == campaign_id,
                    CampaignVariant.variant_name == variant_name,
                )
                .first()
            )
            if variant:
                if variant.content_subject:
                    campaign.content_subject = variant.content_subject
                if variant.content_body:
                    campaign.content_body = variant.content_body
                if variant.content_html:
                    campaign.content_html = variant.content_html

        # Render personalized message
        rendered = await renderer.render(
            db, campaign, contact,
            recipient_id=recipient.id,
        )

        # Restore original content
        campaign.content_subject = original_subject
        campaign.content_body = original_body
        campaign.content_html = original_html

        # Dispatch via adapter
        success = await dispatch_message(
            db=db, tenant=tenant, channel=channel,
            contact=contact, rendered=rendered,
        )

        # Update recipient status
        recipient.status = "sent" if success else "failed"
        recipient.sent_at = datetime.now(timezone.utc) if success else None
        if not success:
            recipient.error_message = "Dispatch failed"

        db.commit()

        logger.info(
            "sending_worker.message_sent",
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            contact_id=contact_id,
            channel=channel,
            success=success,
        )
        return success

    except Exception as e:
        logger.error(
            "sending_worker.process_error",
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            error=str(e),
        )
        if recipient:
            recipient.status = "failed"
            recipient.error_message = str(e)[:500]
            db.commit()
        return False


# ── Queue Consumer ────────────────────────────────────────────────────────

async def process_batch(redis_client: redis.Redis):
    """Read and process a batch of send jobs from the Redis queue."""
    db = SessionLocal()
    processed = 0
    succeeded = 0
    failed = 0

    try:
        queue_len = redis_client.llen(SEND_QUEUE_KEY)
        if queue_len == 0:
            return 0

        batch_count = min(queue_len, BATCH_SIZE)

        for _ in range(batch_count):
            raw = redis_client.lpop(SEND_QUEUE_KEY)
            if not raw:
                break

            try:
                job = json.loads(raw)
            except json.JSONDecodeError:
                logger.error("sending_worker.invalid_json", raw=raw[:200])
                continue

            # Process with retry logic
            retries = job.get("_retries", 0)
            success = await process_send_job(db, job)

            if success:
                succeeded += 1
            else:
                failed += 1
                # Retry logic: re-enqueue with incremented retry count
                if retries < MAX_RETRIES:
                    job["_retries"] = retries + 1
                    redis_client.rpush(SEND_QUEUE_KEY, json.dumps(job))
                    logger.info(
                        "sending_worker.retry",
                        campaign_id=job.get("campaign_id"),
                        recipient_id=job.get("recipient_id"),
                        retry=retries + 1,
                    )
                else:
                    # Move to dead letter queue after max retries
                    job["_failed_at"] = datetime.now(timezone.utc).isoformat()
                    tenant_id = job.get("tenant_id")
                    if tenant_id:
                        redis_client.rpush(f"campaign:send_dlq:{tenant_id}", json.dumps(job))
                    else:
                        redis_client.rpush(DEAD_LETTER_QUEUE_KEY, json.dumps(job))

                    logger.warning(
                        "sending_worker.dead_letter",
                        campaign_id=job.get("campaign_id"),
                        recipient_id=job.get("recipient_id"),
                        tenant_id=tenant_id,
                        retries=retries,
                    )

            processed += 1

        if processed > 0:
            logger.info(
                "sending_worker.batch_complete",
                processed=processed,
                succeeded=succeeded,
                failed=failed,
                queue_remaining=redis_client.llen(SEND_QUEUE_KEY),
            )

            # Update campaign stats and status after each batch
            campaign_ids_processed = set()
            # Re-parse jobs to get campaign IDs (we track them during processing)
            # For simplicity, update stats for all active campaigns
            _update_active_campaigns(db)

    except Exception as e:
        logger.error("sending_worker.batch_error", error=str(e))
    finally:
        db.close()

    return processed


def _update_active_campaigns(db: Session):
    """Update stats and status for all campaigns that are currently being sent."""
    from app.core.models import Campaign, CampaignRecipient
    from sqlalchemy import func

    # Find campaigns with status 'queued' or 'sending'
    active_campaigns = (
        db.query(Campaign)
        .filter(Campaign.status.in_(['queued', 'sending']))
        .all()
    )

    for campaign in active_campaigns:
        stats = (
            db.query(
                func.count(CampaignRecipient.id).label('total'),
                func.count(CampaignRecipient.id).filter(CampaignRecipient.status == 'sent').label('sent'),
                func.count(CampaignRecipient.id).filter(CampaignRecipient.status == 'failed').label('failed'),
                func.count(CampaignRecipient.id).filter(CampaignRecipient.status == 'pending').label('pending'),
            )
            .filter(CampaignRecipient.campaign_id == campaign.id)
            .first()
        )

        if stats:
            campaign.stats_total = stats.total
            campaign.stats_sent = stats.sent
            campaign.stats_failed = stats.failed
            campaign.stats_delivered = stats.sent  # Assume delivered = sent for now

            # If no more pending recipients, mark campaign as sent
            if stats.pending == 0 and stats.total > 0:
                campaign.status = 'sent'
                campaign.sent_at = datetime.now(timezone.utc)
                logger.info(
                    'sending_worker.campaign_completed',
                    campaign_id=campaign.id,
                    total=stats.total,
                    sent=stats.sent,
                    failed=stats.failed,
                )

    db.commit()


# ── Campaign Stats Updater ────────────────────────────────────────────────

def update_campaign_stats(db: Session, campaign_id: int):
    """Update campaign aggregate stats from recipient records."""
    from app.core.models import Campaign, CampaignRecipient
    from sqlalchemy import func

    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return

    stats = (
        db.query(
            func.count(CampaignRecipient.id).label("total"),
            func.count(CampaignRecipient.id).filter(CampaignRecipient.status == "sent").label("sent"),
            func.count(CampaignRecipient.id).filter(CampaignRecipient.status == "failed").label("failed"),
        )
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .first()
    )

    if stats:
        campaign.stats_total = stats.total
        campaign.stats_sent = stats.sent
        campaign.stats_failed = stats.failed
        db.commit()


# ── Main Loop ─────────────────────────────────────────────────────────────

async def main():
    """Main entry point – continuously processes the send queue."""
    logger.info(
        "sending_worker.started",
        redis=REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL,
        database=DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "configured",
        batch_size=BATCH_SIZE,
        poll_interval=POLL_INTERVAL,
        max_retries=MAX_RETRIES,
    )

    redis_client = get_redis()

    while True:
        try:
            processed = await process_batch(redis_client)

            # If we processed a full batch, immediately check for more
            if processed >= BATCH_SIZE:
                continue

        except redis.ConnectionError:
            logger.error("sending_worker.redis_connection_lost")
            await asyncio.sleep(5)
            try:
                redis_client = get_redis()
            except Exception:
                pass
            continue

        except Exception as e:
            logger.error("sending_worker.loop_error", error=str(e))

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
