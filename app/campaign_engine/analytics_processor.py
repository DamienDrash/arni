"""ARIIA v2.2 – Analytics Event Processor.

Reads raw tracking events from the Redis queue, validates them,
persists to the analytics_events table, and updates aggregate
statistics on campaigns and recipients.

@ARCH: Campaign Refactoring Phase 3, Task 3.3/3.4
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.analytics_models import AnalyticsEvent
from app.core.models import Campaign, CampaignRecipient
from app.core.contact_models import ContactActivity

logger = structlog.get_logger()


class AnalyticsProcessor:
    """Processes raw tracking events from Redis and persists them."""

    def process_event(self, db: Session, raw_event: dict) -> bool:
        """Process a single raw event from the Redis queue.

        Returns True if the event was successfully processed.
        """
        event_type = raw_event.get("event_type")
        recipient_id = raw_event.get("recipient_id")

        if not event_type:
            logger.warning("analytics.missing_event_type", raw=raw_event)
            return False

        # Resolve recipient → campaign → tenant → contact
        recipient = None
        campaign = None
        contact_id = None
        tenant_id = None
        channel = None

        if recipient_id:
            recipient = db.query(CampaignRecipient).filter(
                CampaignRecipient.id == recipient_id
            ).first()

        if recipient:
            campaign = db.query(Campaign).filter(
                Campaign.id == recipient.campaign_id
            ).first()
            contact_id = recipient.contact_id
            tenant_id = recipient.tenant_id or (campaign.tenant_id if campaign else None)
            channel = recipient.channel or (campaign.channel if campaign else raw_event.get("channel", "email"))
        else:
            channel = raw_event.get("channel", "email")
            tenant_id = raw_event.get("tenant_id")

        # 1. Persist to analytics_events
        analytics_event = AnalyticsEvent(
            tenant_id=tenant_id,
            campaign_id=campaign.id if campaign else None,
            recipient_id=recipient_id,
            contact_id=contact_id,
            event_type=event_type,
            channel=channel,
            url=raw_event.get("url"),
            user_agent=raw_event.get("user_agent"),
            ip_address=raw_event.get("ip_address"),
            metadata_json=json.dumps(raw_event.get("metadata")) if raw_event.get("metadata") else None,
        )
        db.add(analytics_event)

        # 2. Update recipient status — returns True only if this is a new/unique event
        is_unique = False
        if recipient:
            is_unique = self._update_recipient(recipient, event_type)

        # 3. Update campaign aggregate stats — only count unique events per recipient
        if campaign and is_unique:
            self._update_campaign_stats(campaign, event_type)

        # 4. Create ContactActivity entry for timeline
        if contact_id and tenant_id and campaign:
            self._create_contact_activity(db, contact_id, tenant_id, campaign, event_type)

        try:
            db.commit()
            logger.debug(
                "analytics.event_processed",
                event_type=event_type,
                recipient_id=recipient_id,
                campaign_id=campaign.id if campaign else None,
            )
            return True
        except Exception as e:
            db.rollback()
            logger.error("analytics.commit_failed", error=str(e))
            return False

    def _update_recipient(self, recipient: CampaignRecipient, event_type: str) -> bool:
        """Update the recipient record based on the event type.

        Returns True if this is the FIRST time this event occurred for this
        recipient (i.e. it should be counted as a unique stat).
        """
        now = datetime.now(timezone.utc)
        is_unique = False

        # Set timestamps only on first occurrence — use as uniqueness gate
        if event_type == "delivered" and not recipient.delivered_at:
            recipient.delivered_at = now
            is_unique = True
        elif event_type == "opened" and not recipient.opened_at:
            recipient.opened_at = now
            is_unique = True
        elif event_type == "clicked" and not recipient.clicked_at:
            recipient.clicked_at = now
            is_unique = True
        elif event_type == "converted" and not recipient.converted_at:
            recipient.converted_at = now
            is_unique = True
        elif event_type in ("bounced", "unsubscribed"):
            is_unique = True  # These are one-time events by nature

        # Upgrade status (never downgrade)
        status_map = {
            "delivered": "delivered",
            "opened": "opened",
            "clicked": "clicked",
            "bounced": "bounced",
            "unsubscribed": "unsubscribed",
            "converted": "converted",
        }
        new_status = status_map.get(event_type)
        if new_status:
            status_priority = ["pending", "sent", "delivered", "opened", "clicked", "converted"]
            current_idx = status_priority.index(recipient.status) if recipient.status in status_priority else -1
            new_idx = status_priority.index(new_status) if new_status in status_priority else -1
            if new_idx > current_idx:
                recipient.status = new_status

        return is_unique

    def _update_campaign_stats(self, campaign: Campaign, event_type: str):
        """Increment the aggregate stats counter on the campaign."""
        stat_map = {
            "delivered": "stats_delivered",
            "opened": "stats_opened",
            "clicked": "stats_clicked",
            "bounced": "stats_failed",
        }
        stat_field = stat_map.get(event_type)
        if stat_field:
            current = getattr(campaign, stat_field, 0) or 0
            setattr(campaign, stat_field, current + 1)

    def _create_contact_activity(
        self,
        db: Session,
        contact_id: int,
        tenant_id: int,
        campaign: Campaign,
        event_type: str,
    ):
        """Create a ContactActivity entry for the contact timeline."""
        activity_map = {
            "opened": "campaign_opened",
            "clicked": "campaign_clicked",
            "converted": "campaign_converted",
            "unsubscribed": "campaign_unsubscribed",
        }
        activity_type = activity_map.get(event_type)
        if not activity_type:
            return

        description = {
            "campaign_opened": f"Kampagne \"{campaign.name}\" geöffnet",
            "campaign_clicked": f"Link in Kampagne \"{campaign.name}\" geklickt",
            "campaign_converted": f"Conversion in Kampagne \"{campaign.name}\"",
            "campaign_unsubscribed": f"Abmeldung von Kampagne \"{campaign.name}\"",
        }.get(activity_type, f"Kampagnen-Event: {event_type}")

        title_map = {
            "campaign_opened": f"Kampagne geöffnet",
            "campaign_clicked": f"Link geklickt",
            "campaign_converted": f"Conversion",
            "campaign_unsubscribed": f"Abmeldung",
        }
        title = title_map.get(activity_type, f"Kampagnen-Event")

        activity = ContactActivity(
            contact_id=contact_id,
            tenant_id=tenant_id,
            activity_type=activity_type,
            title=title,
            description=description,
            metadata_json=json.dumps({
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "event_type": event_type,
            }),
        )
        db.add(activity)
