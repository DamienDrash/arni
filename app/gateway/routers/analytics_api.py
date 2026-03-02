"""ARIIA v2.2 – Campaign Analytics API.

Authenticated admin endpoints for retrieving campaign analytics,
funnel data, channel comparisons, and orchestration step performance.

@ARCH: Campaign Refactoring Phase 3, Task 3.5
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, and_
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, get_current_user
from app.core.db import get_db
from app.core.models import Campaign, CampaignRecipient
from app.core.analytics_models import AnalyticsEvent, CampaignOrchestrationStep

logger = structlog.get_logger()

router = APIRouter(prefix="/v2/admin/analytics", tags=["analytics"])


# ── Overview KPIs ─────────────────────────────────────────────────────

@router.get("/overview")
async def analytics_overview(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
):
    """Get high-level KPI overview for all campaigns.

    Returns total sent, delivered, opened, clicked, and conversion
    counts with calculated rates for the specified time period.
    """
    tenant_id = auth.tenant_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Aggregate from campaigns table (fast)
    stats = (
        db.query(
            func.count(Campaign.id).label("total_campaigns"),
            func.coalesce(func.sum(Campaign.stats_sent), 0).label("total_sent"),
            func.coalesce(func.sum(Campaign.stats_delivered), 0).label("total_delivered"),
            func.coalesce(func.sum(Campaign.stats_opened), 0).label("total_opened"),
            func.coalesce(func.sum(Campaign.stats_clicked), 0).label("total_clicked"),
            func.coalesce(func.sum(Campaign.stats_failed), 0).label("total_failed"),
        )
        .filter(
            Campaign.tenant_id == tenant_id,
            Campaign.status == "sent",
            Campaign.sent_at >= since,
        )
        .first()
    )

    # Count conversions from recipients
    conversions = (
        db.query(func.count(CampaignRecipient.id))
        .join(Campaign, CampaignRecipient.campaign_id == Campaign.id)
        .filter(
            Campaign.tenant_id == tenant_id,
            Campaign.sent_at >= since,
            CampaignRecipient.converted_at.isnot(None),
        )
        .scalar()
    ) or 0

    conversion_value = (
        db.query(func.coalesce(func.sum(CampaignRecipient.conversion_value), 0))
        .join(Campaign, CampaignRecipient.campaign_id == Campaign.id)
        .filter(
            Campaign.tenant_id == tenant_id,
            Campaign.sent_at >= since,
            CampaignRecipient.converted_at.isnot(None),
        )
        .scalar()
    ) or 0

    total_sent = stats.total_sent or 1  # Avoid division by zero
    total_delivered = stats.total_delivered or 1

    return {
        "period_days": days,
        "total_campaigns": stats.total_campaigns,
        "total_sent": stats.total_sent,
        "total_delivered": stats.total_delivered,
        "total_opened": stats.total_opened,
        "total_clicked": stats.total_clicked,
        "total_failed": stats.total_failed,
        "total_conversions": conversions,
        "total_conversion_value": round(float(conversion_value), 2),
        "delivery_rate": round(stats.total_delivered / total_sent * 100, 1),
        "open_rate": round(stats.total_opened / total_delivered * 100, 1),
        "click_rate": round(stats.total_clicked / total_delivered * 100, 1),
        "conversion_rate": round(conversions / total_delivered * 100, 1) if conversions else 0,
    }


# ── Campaign Funnel ───────────────────────────────────────────────────

@router.get("/funnel")
async def analytics_funnel(
    campaign_id: int = Query(..., description="Campaign ID"),
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get funnel data for a specific campaign.

    Returns the count at each stage: Sent → Delivered → Opened → Clicked → Converted.
    """
    tenant_id = auth.tenant_id

    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == tenant_id,
    ).first()

    if not campaign:
        return {"error": "Campaign not found"}

    # Count recipients at each stage
    base_q = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == campaign_id
    )

    total = base_q.count()
    sent = base_q.filter(CampaignRecipient.status != "pending").count()
    delivered = base_q.filter(CampaignRecipient.delivered_at.isnot(None)).count()
    opened = base_q.filter(CampaignRecipient.opened_at.isnot(None)).count()
    clicked = base_q.filter(CampaignRecipient.clicked_at.isnot(None)).count()
    converted = base_q.filter(CampaignRecipient.converted_at.isnot(None)).count()
    bounced = base_q.filter(CampaignRecipient.status == "bounced").count()
    unsubscribed = base_q.filter(CampaignRecipient.status == "unsubscribed").count()

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "funnel": [
            {"stage": "Gesendet", "count": sent, "rate": 100.0},
            {"stage": "Zugestellt", "count": delivered, "rate": round(delivered / max(sent, 1) * 100, 1)},
            {"stage": "Geöffnet", "count": opened, "rate": round(opened / max(sent, 1) * 100, 1)},
            {"stage": "Geklickt", "count": clicked, "rate": round(clicked / max(sent, 1) * 100, 1)},
            {"stage": "Konvertiert", "count": converted, "rate": round(converted / max(sent, 1) * 100, 1)},
        ],
        "bounced": bounced,
        "unsubscribed": unsubscribed,
        "total_recipients": total,
    }


# ── Campaign Performance Table ────────────────────────────────────────

@router.get("/campaigns")
async def analytics_campaigns(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("sent_at", description="Sort field"),
    sort_dir: str = Query("desc", description="Sort direction"),
):
    """Get a paginated list of campaigns with performance metrics."""
    tenant_id = auth.tenant_id

    query = db.query(Campaign).filter(
        Campaign.tenant_id == tenant_id,
        Campaign.status == "sent",
    )

    # Sorting
    sort_col = getattr(Campaign, sort_by, Campaign.sent_at)
    if sort_dir == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = query.count()
    campaigns = query.offset((page - 1) * per_page).limit(per_page).all()

    results = []
    for c in campaigns:
        delivered = c.stats_delivered or 0
        safe_delivered = max(delivered, 1)
        results.append({
            "id": c.id,
            "name": c.name,
            "channel": c.channel,
            "sent_at": c.sent_at.isoformat() if c.sent_at else None,
            "stats_total": c.stats_total,
            "stats_sent": c.stats_sent,
            "stats_delivered": delivered,
            "stats_opened": c.stats_opened,
            "stats_clicked": c.stats_clicked,
            "stats_failed": c.stats_failed,
            "open_rate": round((c.stats_opened or 0) / safe_delivered * 100, 1),
            "click_rate": round((c.stats_clicked or 0) / safe_delivered * 100, 1),
        })

    return {
        "campaigns": results,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ── Channel Comparison ────────────────────────────────────────────────

@router.get("/by-channel")
async def analytics_by_channel(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Get aggregated analytics broken down by channel."""
    tenant_id = auth.tenant_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    results = (
        db.query(
            Campaign.channel,
            func.count(Campaign.id).label("campaigns"),
            func.coalesce(func.sum(Campaign.stats_sent), 0).label("sent"),
            func.coalesce(func.sum(Campaign.stats_delivered), 0).label("delivered"),
            func.coalesce(func.sum(Campaign.stats_opened), 0).label("opened"),
            func.coalesce(func.sum(Campaign.stats_clicked), 0).label("clicked"),
        )
        .filter(
            Campaign.tenant_id == tenant_id,
            Campaign.status == "sent",
            Campaign.sent_at >= since,
        )
        .group_by(Campaign.channel)
        .all()
    )

    channels = []
    for r in results:
        safe_delivered = max(r.delivered, 1)
        channels.append({
            "channel": r.channel,
            "campaigns": r.campaigns,
            "sent": r.sent,
            "delivered": r.delivered,
            "opened": r.opened,
            "clicked": r.clicked,
            "open_rate": round(r.opened / safe_delivered * 100, 1),
            "click_rate": round(r.clicked / safe_delivered * 100, 1),
        })

    return {"period_days": days, "channels": channels}


# ── Orchestration Step Performance ────────────────────────────────────

@router.get("/orchestration/{campaign_id}")
async def analytics_orchestration(
    campaign_id: int,
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get per-step performance for a multi-channel campaign."""
    tenant_id = auth.tenant_id

    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == tenant_id,
    ).first()

    if not campaign:
        return {"error": "Campaign not found"}

    steps = (
        db.query(CampaignOrchestrationStep)
        .filter(CampaignOrchestrationStep.campaign_id == campaign_id)
        .order_by(CampaignOrchestrationStep.step_order)
        .all()
    )

    step_data = []
    for step in steps:
        # Count recipients that reached this step
        recipients_at_step = (
            db.query(func.count(CampaignRecipient.id))
            .filter(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.current_step >= step.step_order,
            )
            .scalar()
        ) or 0

        step_data.append({
            "step_order": step.step_order,
            "channel": step.channel,
            "wait_hours": step.wait_hours,
            "condition_type": step.condition_type,
            "recipients_reached": recipients_at_step,
        })

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "steps": step_data,
    }


# ── Event Timeline ────────────────────────────────────────────────────

@router.get("/events")
async def analytics_events(
    auth: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
    campaign_id: int = Query(None, description="Filter by campaign"),
    event_type: str = Query(None, description="Filter by event type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Get a paginated list of raw analytics events."""
    tenant_id = auth.tenant_id

    query = db.query(AnalyticsEvent).filter(
        AnalyticsEvent.tenant_id == tenant_id,
    )

    if campaign_id:
        query = query.filter(AnalyticsEvent.campaign_id == campaign_id)
    if event_type:
        query = query.filter(AnalyticsEvent.event_type == event_type)

    total = query.count()
    events = (
        query.order_by(AnalyticsEvent.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "channel": e.channel,
                "campaign_id": e.campaign_id,
                "contact_id": e.contact_id,
                "url": e.url,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
