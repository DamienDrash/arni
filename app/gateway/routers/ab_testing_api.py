"""ARIIA v2.4 – A/B Testing & Calendar API Router.

Provides endpoints for:
- A/B test results and management
- Campaign calendar data (for the planning view)
- Contact insights summary
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user
from app.domains.campaigns.models import Campaign, CampaignVariant

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v2/admin", tags=["ab-testing-calendar"])


# ═══════════════════════════════════════════════════════════════════════════
# A/B TESTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/campaigns/{campaign_id}/ab-test")
async def get_ab_test_results(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get A/B test results for a campaign."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.is_ab_test:
        raise HTTPException(status_code=400, detail="Campaign is not an A/B test")

    from app.campaign_engine.ab_testing import ABTestingEngine
    engine = ABTestingEngine(db)
    return engine.get_test_results_summary(campaign)


class ABTestConfigUpdate(BaseModel):
    ab_test_percentage: int | None = None
    ab_test_duration_hours: int | None = None
    ab_test_metric: str | None = None
    ab_test_auto_send: bool | None = None


@router.put("/campaigns/{campaign_id}/ab-test/config")
async def update_ab_test_config(
    campaign_id: int,
    payload: ABTestConfigUpdate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update A/B test configuration for a campaign."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if payload.ab_test_percentage is not None:
        campaign.ab_test_percentage = max(5, min(50, payload.ab_test_percentage))
    if payload.ab_test_duration_hours is not None:
        campaign.ab_test_duration_hours = max(1, min(72, payload.ab_test_duration_hours))
    if payload.ab_test_metric is not None:
        if payload.ab_test_metric not in ("open_rate", "click_rate"):
            raise HTTPException(status_code=400, detail="Invalid metric")
        campaign.ab_test_metric = payload.ab_test_metric
    if payload.ab_test_auto_send is not None:
        campaign.ab_test_auto_send = payload.ab_test_auto_send

    db.commit()
    return {"status": "ok"}


class VariantCreate(BaseModel):
    variant_name: str
    content_subject: str | None = None
    content_body: str | None = None
    content_html: str | None = None
    percentage: int = 50


@router.post("/campaigns/{campaign_id}/ab-test/variants")
async def create_variant(
    campaign_id: int,
    payload: VariantCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new A/B test variant for a campaign."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Check max variants (4)
    count = db.query(func.count(CampaignVariant.id)).filter(
        CampaignVariant.campaign_id == campaign_id
    ).scalar()
    if count >= 4:
        raise HTTPException(status_code=400, detail="Maximum 4 variants allowed")

    variant = CampaignVariant(
        campaign_id=campaign_id,
        variant_name=payload.variant_name,
        content_subject=payload.content_subject,
        content_body=payload.content_body,
        content_html=payload.content_html,
        percentage=payload.percentage,
    )
    db.add(variant)

    # Enable A/B test on campaign if not already
    if not campaign.is_ab_test:
        campaign.is_ab_test = True

    db.commit()
    db.refresh(variant)

    return {
        "id": variant.id,
        "variant_name": variant.variant_name,
        "content_subject": variant.content_subject,
        "percentage": variant.percentage,
    }


@router.delete("/campaigns/{campaign_id}/ab-test/variants/{variant_id}")
async def delete_variant(
    campaign_id: int,
    variant_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an A/B test variant."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    variant = db.query(CampaignVariant).filter(
        CampaignVariant.id == variant_id,
        CampaignVariant.campaign_id == campaign_id,
    ).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    db.delete(variant)
    db.commit()
    return {"status": "deleted"}


@router.post("/campaigns/{campaign_id}/ab-test/evaluate")
async def trigger_ab_evaluation(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger A/B test evaluation."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.is_ab_test:
        raise HTTPException(status_code=400, detail="Campaign is not an A/B test")

    from app.campaign_engine.ab_testing import ABTestingEngine
    engine = ABTestingEngine(db)
    winner = engine.evaluate_test(campaign)

    return {
        "winner_variant": winner.variant_name if winner else None,
        "confidence_level": winner.confidence_level if winner else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CALENDAR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/campaigns/calendar")
async def get_campaign_calendar(
    start: str = Query(None, description="ISO date string for range start"),
    end: str = Query(None, description="ISO date string for range end"),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get campaigns formatted for calendar display.

    Returns events compatible with FullCalendar's event format.
    """
    query = db.query(Campaign).filter(Campaign.tenant_id == user.tenant_id)

    # Filter by date range if provided
    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            query = query.filter(
                (Campaign.scheduled_at >= start_dt) | (Campaign.created_at >= start_dt)
            )
        except ValueError:
            pass

    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            query = query.filter(
                (Campaign.scheduled_at <= end_dt) | (Campaign.created_at <= end_dt)
            )
        except ValueError:
            pass

    campaigns = query.order_by(Campaign.scheduled_at.asc().nullslast()).all()

    # Channel color defaults
    CHANNEL_COLORS = {
        "email": "#6C5CE7",
        "whatsapp": "#25D366",
        "sms": "#FF6B6B",
        "telegram": "#0088CC",
        "multi": "#F39C12",
    }

    STATUS_OPACITY = {
        "draft": 0.5,
        "pending_review": 0.7,
        "approved": 0.85,
        "scheduled": 0.9,
        "sending": 1.0,
        "sent": 1.0,
        "failed": 0.4,
    }

    events = []
    for c in campaigns:
        event_date = c.scheduled_at or c.created_at
        if not event_date:
            continue

        color = c.calendar_color or CHANNEL_COLORS.get(c.channel, "#6C5CE7")

        events.append({
            "id": c.id,
            "title": c.name,
            "start": event_date.isoformat(),
            "end": event_date.isoformat(),
            "backgroundColor": color,
            "borderColor": color,
            "textColor": "#FFFFFF",
            "extendedProps": {
                "campaign_id": c.id,
                "status": c.status,
                "channel": c.channel,
                "is_ab_test": c.is_ab_test,
                "stats_sent": c.stats_sent,
                "stats_opened": c.stats_opened,
                "smart_send": c.smart_send_enabled,
            },
        })

    return events


class CalendarMovePayload(BaseModel):
    scheduled_at: str  # ISO datetime string


@router.put("/campaigns/{campaign_id}/calendar-move")
async def move_campaign_on_calendar(
    campaign_id: int,
    payload: CalendarMovePayload,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move a campaign to a new date/time (drag & drop from calendar)."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status in ("sent", "sending"):
        raise HTTPException(status_code=400, detail="Cannot move a sent campaign")

    try:
        new_dt = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    campaign.scheduled_at = new_dt
    db.commit()

    return {"status": "ok", "scheduled_at": new_dt.isoformat()}


# ═══════════════════════════════════════════════════════════════════════════
# CONTACT INSIGHTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/contacts/insights/summary")
async def get_contact_insights_summary(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregated contact insights for the tenant."""
    from app.core.contact_models import Contact
    from sqlalchemy import case

    total = db.query(func.count(Contact.id)).filter(
        Contact.tenant_id == user.tenant_id,
        Contact.deleted_at.is_(None),
    ).scalar() or 0

    with_insights = db.query(func.count(Contact.id)).filter(
        Contact.tenant_id == user.tenant_id,
        Contact.deleted_at.is_(None),
        Contact.preferred_channel.isnot(None),
    ).scalar() or 0

    # Channel preference distribution
    channel_dist = (
        db.query(Contact.preferred_channel, func.count(Contact.id))
        .filter(
            Contact.tenant_id == user.tenant_id,
            Contact.deleted_at.is_(None),
            Contact.preferred_channel.isnot(None),
        )
        .group_by(Contact.preferred_channel)
        .all()
    )

    return {
        "total_contacts": total,
        "contacts_with_insights": with_insights,
        "coverage_percentage": round(with_insights / total * 100, 1) if total > 0 else 0,
        "channel_distribution": {ch: cnt for ch, cnt in channel_dist},
    }
