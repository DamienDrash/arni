"""ARIIA v2.4 – Contact Insights Engine.

Analyzes campaign interaction data (opens, clicks, conversions) from the last
90 days to compute per-contact channel affinity scores and optimal send times.

Results are written directly to the contacts table:
  - preferred_channel: The channel with the highest weighted interaction rate
  - optimal_send_hour_utc: The hour (0-23) with the most opens
  - channel_affinity_json: JSON object with per-channel scores (0.0-1.0)
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.contact_models import Contact

logger = structlog.get_logger(__name__)


class ContactInsightsEngine:
    """Computes channel affinity and optimal send time for each contact."""

    LOOKBACK_DAYS = 90

    # Weights for different interaction types
    WEIGHTS = {
        "sent": 0.0,
        "delivered": 0.1,
        "opened": 0.5,
        "clicked": 1.0,
        "converted": 1.5,
    }

    CHANNELS = ["email", "whatsapp", "sms", "telegram"]

    def __init__(self, db: Session):
        self.db = db

    def compute_all(self, tenant_id: int) -> dict:
        """Compute insights for all contacts of a tenant.

        Returns:
            {"processed": int, "updated": int, "errors": int}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.LOOKBACK_DAYS)
        stats = {"processed": 0, "updated": 0, "errors": 0}

        # Fetch all contacts for this tenant
        contacts = (
            self.db.query(Contact)
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None),
            )
            .all()
        )

        if not contacts:
            logger.info("contact_insights_no_contacts", tenant_id=tenant_id)
            return stats

        # Batch-fetch all relevant events for this tenant
        # Using raw SQL for performance with the analytics_events table
        events_query = text("""
            SELECT
                cr.contact_id,
                cr.channel,
                ce.event_type,
                ce.created_at
            FROM campaign_events ce
            JOIN campaign_recipients cr ON cr.id = ce.recipient_id
            WHERE cr.tenant_id = :tenant_id
              AND ce.created_at >= :cutoff
              AND cr.contact_id IS NOT NULL
            ORDER BY cr.contact_id, ce.created_at
        """)

        try:
            result = self.db.execute(events_query, {
                "tenant_id": tenant_id,
                "cutoff": cutoff,
            })
            rows = result.fetchall()
        except Exception as e:
            logger.warning("contact_insights_query_error", error=str(e))
            rows = []

        # Group events by contact
        contact_events: dict[int, list] = defaultdict(list)
        for row in rows:
            contact_events[row[0]].append({
                "channel": row[1],
                "event_type": row[2],
                "hour_utc": row[3].hour if row[3] else None,
            })

        # Process each contact
        for contact in contacts:
            stats["processed"] += 1
            try:
                events = contact_events.get(contact.id, [])
                if not events:
                    continue

                affinity = self._compute_channel_affinity(events)
                optimal_hour = self._compute_optimal_send_hour(events)
                preferred = max(affinity, key=affinity.get) if affinity else None

                # Update contact
                contact.channel_affinity_json = json.dumps(affinity)
                contact.optimal_send_hour_utc = optimal_hour
                contact.preferred_channel = preferred

                stats["updated"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.warning(
                    "contact_insights_error",
                    contact_id=contact.id,
                    error=str(e),
                )

        self.db.commit()

        logger.info(
            "contact_insights_complete",
            tenant_id=tenant_id,
            **stats,
        )
        return stats

    def _compute_channel_affinity(self, events: list[dict]) -> dict[str, float]:
        """Compute weighted affinity score per channel.

        Returns:
            {"email": 0.72, "whatsapp": 0.45, ...} — normalized to 0.0-1.0
        """
        channel_scores: dict[str, float] = defaultdict(float)
        channel_counts: dict[str, int] = defaultdict(int)

        for event in events:
            channel = event.get("channel")
            event_type = event.get("event_type")
            if not channel or not event_type:
                continue

            weight = self.WEIGHTS.get(event_type, 0.0)
            channel_scores[channel] += weight
            channel_counts[channel] += 1

        if not channel_scores:
            return {}

        # Normalize: divide by count to get average weighted score, then scale to 0-1
        max_possible = max(self.WEIGHTS.values())
        result = {}
        for channel in self.CHANNELS:
            if channel in channel_scores and channel_counts[channel] > 0:
                avg_score = channel_scores[channel] / channel_counts[channel]
                result[channel] = round(min(1.0, avg_score / max_possible), 2)
            else:
                result[channel] = 0.0

        return result

    def _compute_optimal_send_hour(self, events: list[dict]) -> int | None:
        """Determine the hour (0-23 UTC) with the most opens.

        Returns:
            The optimal hour, or None if no open events exist.
        """
        hour_counts: dict[int, int] = defaultdict(int)

        for event in events:
            if event.get("event_type") == "opened" and event.get("hour_utc") is not None:
                hour_counts[event["hour_utc"]] += 1

        if not hour_counts:
            return None

        return max(hour_counts, key=hour_counts.get)
