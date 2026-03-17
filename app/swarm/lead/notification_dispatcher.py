"""ARIIA Swarm v3 — Notification Dispatcher.

Polls the ``orch:pending_notifications`` sorted set in Redis and delivers
due notifications via the RedisBus outbound channel.

Designed to run as a long-lived background task inside the Gateway lifespan.
"""

from __future__ import annotations

import asyncio
import json
import time

import structlog

from app.gateway.redis_bus import RedisBus

logger = structlog.get_logger()

# How often (in seconds) the dispatcher checks for due notifications.
POLL_INTERVAL = 10

SORTED_SET_KEY = "orch:pending_notifications"


async def poll_pending_notifications(redis_bus: RedisBus) -> None:
    """Continuously poll Redis for due confirmation notifications.

    Reads all entries from the ``orch:pending_notifications`` sorted set
    whose score (unix timestamp) is <= now, publishes them to the
    ``ariia:outbound`` channel, and removes them from the set.

    Args:
        redis_bus: Connected :class:`RedisBus` instance.
    """
    logger.info("notification_dispatcher.started")

    while True:
        try:
            now = time.time()
            # Fetch all entries whose scheduled time has passed
            entries: list[str] = await redis_bus.client.zrangebyscore(
                SORTED_SET_KEY, 0, now,
            )

            for entry in entries:
                try:
                    data = json.loads(entry)
                    outbound_payload = json.dumps({
                        "tenant_id": data.get("tenant_id"),
                        "member_id": data.get("member_id"),
                        "channel": data.get("channel", "whatsapp"),
                        "message": data.get("message", ""),
                        "type": data.get("type", "notification"),
                    })
                    await redis_bus.publish(
                        RedisBus.CHANNEL_OUTBOUND,
                        outbound_payload,
                    )
                    logger.info(
                        "notification_dispatcher.delivered",
                        type=data.get("type"),
                        tenant_id=data.get("tenant_id"),
                        member_id=data.get("member_id"),
                    )
                except Exception as deliver_err:
                    logger.error(
                        "notification_dispatcher.deliver_failed",
                        error=str(deliver_err),
                        entry=entry[:200],
                    )

                # Remove the processed entry regardless of delivery outcome
                # to avoid infinite retry loops on malformed entries.
                await redis_bus.client.zrem(SORTED_SET_KEY, entry)

        except Exception as poll_err:
            logger.error(
                "notification_dispatcher.poll_failed",
                error=str(poll_err),
            )

        await asyncio.sleep(POLL_INTERVAL)
