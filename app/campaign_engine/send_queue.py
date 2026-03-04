"""ARIIA – Campaign Send Queue Interface.

Provides a clean API for enqueuing send jobs into the Redis queue
that the SendingWorker consumes.

Usage:
    from app.campaign_engine.send_queue import enqueue_send_job, enqueue_campaign_batch

    # Single message
    enqueue_send_job(
        campaign_id=1,
        recipient_id=42,
        contact_id=7,
        tenant_id=2,
        channel="email",
    )

    # Batch of recipients
    enqueue_campaign_batch(campaign, recipients_with_contacts)
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

import redis
import structlog

logger = structlog.get_logger()

REDIS_URL = os.environ.get("REDIS_URL", "redis://ariia-redis:6379/0")
SEND_QUEUE_KEY = "campaign:send_queue"

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Get or create a Redis client (singleton)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def enqueue_send_job(
    campaign_id: int,
    recipient_id: int,
    contact_id: int,
    tenant_id: int,
    channel: str = "email",
    variant_name: Optional[str] = None,
) -> bool:
    """Enqueue a single send job into the Redis queue.

    Returns True if the job was enqueued successfully.
    """
    job = {
        "campaign_id": campaign_id,
        "recipient_id": recipient_id,
        "contact_id": contact_id,
        "tenant_id": tenant_id,
        "channel": channel,
        "variant_name": variant_name,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        r = _get_redis()
        r.rpush(SEND_QUEUE_KEY, json.dumps(job))
        return True
    except Exception as e:
        logger.error(
            "send_queue.enqueue_failed",
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            error=str(e),
        )
        return False


def enqueue_campaign_batch(
    campaign_id: int,
    tenant_id: int,
    channel: str,
    recipients: list[dict],
) -> int:
    """Enqueue a batch of send jobs for a campaign.

    Args:
        campaign_id: The campaign ID.
        tenant_id: The tenant ID.
        channel: The messaging channel.
        recipients: List of dicts with keys: recipient_id, contact_id, variant_name (optional).

    Returns:
        Number of jobs successfully enqueued.
    """
    enqueued = 0
    now = datetime.now(timezone.utc).isoformat()

    try:
        r = _get_redis()
        pipeline = r.pipeline()

        for rec in recipients:
            job = {
                "campaign_id": campaign_id,
                "recipient_id": rec["recipient_id"],
                "contact_id": rec["contact_id"],
                "tenant_id": tenant_id,
                "channel": channel,
                "variant_name": rec.get("variant_name"),
                "enqueued_at": now,
            }
            pipeline.rpush(SEND_QUEUE_KEY, json.dumps(job))
            enqueued += 1

        pipeline.execute()

        logger.info(
            "send_queue.batch_enqueued",
            campaign_id=campaign_id,
            count=enqueued,
            channel=channel,
        )

    except Exception as e:
        logger.error(
            "send_queue.batch_enqueue_failed",
            campaign_id=campaign_id,
            error=str(e),
        )

    return enqueued


def get_queue_length() -> int:
    """Get the current length of the send queue."""
    try:
        r = _get_redis()
        return r.llen(SEND_QUEUE_KEY)
    except Exception:
        return -1


def get_dlq_length() -> int:
    """Get the current length of the dead letter queue."""
    try:
        r = _get_redis()
        return r.llen("campaign:send_dlq")
    except Exception:
        return -1
