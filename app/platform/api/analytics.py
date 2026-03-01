"""app/platform/api/analytics.py — Enterprise Analytics API.

Provides comprehensive analytics for tenant admins:
- Conversation metrics (volume, resolution rate, response times)
- Intent analysis (top intents, unresolved queries)
- Customer satisfaction (feedback scores, NPS)
- Channel performance comparison
- Trend analysis with configurable time windows

Endpoints (prefix /api/v1/analytics):
    GET /dashboard          → Overview dashboard with key KPIs
    GET /conversations      → Conversation metrics over time
    GET /intents            → Intent distribution and trends
    GET /feedback           → Customer satisfaction scores
    GET /channels           → Channel performance comparison
    GET /agents             → Agent/specialist performance
    GET /escalations        → Escalation analysis
    GET /export             → Export analytics data as CSV/JSON
"""
from __future__ import annotations

import json
import csv
import io
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import ChatSession, Tenant

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _require_tenant_admin(user: AuthContext) -> AuthContext:
    require_role(user, {"system_admin", "tenant_admin"})
    return user


def _parse_period(days: int) -> tuple[datetime, datetime]:
    """Parse a period into start/end datetimes."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    return start, now


def _bucket_by_day(items: list, date_field: str = "created_at",
                   days: int = 30) -> dict[str, int]:
    """Bucket items by day for time-series data."""
    now = datetime.now(timezone.utc)
    buckets = {}
    for i in range(days):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[day] = 0

    for item in items:
        dt = getattr(item, date_field, None)
        if dt:
            day = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)[:10]
            if day in buckets:
                buckets[day] += 1

    # Return sorted by date
    return dict(sorted(buckets.items()))


def _safe_avg(values: list[float]) -> float:
    """Safe average that handles empty lists."""
    return round(sum(values) / len(values), 2) if values else 0.0


def _trend_percent(current: float, previous: float) -> float:
    """Calculate trend percentage change."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsEngine:
    """Core analytics computation engine.

    Processes raw conversation data into meaningful metrics.
    Can be used both by the API and for scheduled report generation.
    """

    @staticmethod
    def compute_conversation_metrics(conversations: list, days: int = 30) -> dict[str, Any]:
        """Compute conversation-level metrics."""
        if not conversations:
            return {
                "total": 0,
                "daily_average": 0,
                "by_day": {},
                "by_channel": {},
                "resolution_rate": 0,
                "avg_messages_per_conversation": 0,
            }

        total = len(conversations)
        daily_avg = round(total / max(days, 1), 1)

        # By channel
        channel_counts = Counter()
        for c in conversations:
            channel = getattr(c, "channel", None) or getattr(c, "source", "unknown")
            channel_counts[str(channel)] += 1

        # Resolution rate (conversations that ended without escalation)
        resolved = sum(1 for c in conversations
                      if not getattr(c, "escalated", False))
        resolution_rate = round(resolved / total * 100, 1) if total > 0 else 0

        # Average messages per conversation
        msg_counts = []
        for c in conversations:
            if hasattr(c, "message_count") and c.message_count:
                msg_counts.append(c.message_count)
            elif hasattr(c, "messages") and c.messages:
                try:
                    msgs = json.loads(c.messages) if isinstance(c.messages, str) else c.messages
                    msg_counts.append(len(msgs))
                except (json.JSONDecodeError, TypeError):
                    pass

        return {
            "total": total,
            "daily_average": daily_avg,
            "by_channel": dict(channel_counts.most_common(10)),
            "resolution_rate": resolution_rate,
            "avg_messages_per_conversation": _safe_avg(msg_counts),
        }

    @staticmethod
    def compute_intent_analysis(conversations: list) -> dict[str, Any]:
        """Analyze intents from conversation data."""
        intent_counts = Counter()
        unresolved_intents = Counter()
        intent_examples = defaultdict(list)

        for c in conversations:
            intent = getattr(c, "intent", None) or getattr(c, "detected_intent", None)
            if intent:
                intent_str = str(intent)
                intent_counts[intent_str] += 1

                # Track unresolved
                if getattr(c, "escalated", False) or getattr(c, "unresolved", False):
                    unresolved_intents[intent_str] += 1

                # Collect example messages
                msg = getattr(c, "user_message", None) or getattr(c, "first_message", None)
                if msg and len(intent_examples[intent_str]) < 3:
                    intent_examples[intent_str].append(str(msg)[:100])

        top_intents = [
            {
                "intent": intent,
                "count": count,
                "percent": round(count / sum(intent_counts.values()) * 100, 1)
                    if intent_counts else 0,
                "unresolved": unresolved_intents.get(intent, 0),
                "examples": intent_examples.get(intent, []),
            }
            for intent, count in intent_counts.most_common(20)
        ]

        return {
            "total_intents_detected": sum(intent_counts.values()),
            "unique_intents": len(intent_counts),
            "top_intents": top_intents,
            "unresolved_rate": round(
                sum(unresolved_intents.values()) / max(sum(intent_counts.values()), 1) * 100, 1
            ),
        }

    @staticmethod
    def compute_feedback_metrics(conversations: list) -> dict[str, Any]:
        """Compute customer satisfaction metrics from feedback data."""
        ratings = []
        feedback_texts = []
        sentiment_counts = Counter()

        for c in conversations:
            rating = getattr(c, "feedback_rating", None) or getattr(c, "rating", None)
            if rating is not None:
                try:
                    ratings.append(float(rating))
                except (ValueError, TypeError):
                    pass

            feedback = getattr(c, "feedback_text", None) or getattr(c, "feedback", None)
            if feedback:
                feedback_texts.append(str(feedback)[:200])

            sentiment = getattr(c, "sentiment", None)
            if sentiment:
                sentiment_counts[str(sentiment)] += 1

        avg_rating = _safe_avg(ratings)
        rating_distribution = Counter(int(r) for r in ratings if 1 <= r <= 5)

        # NPS calculation (ratings 1-5 mapped to 1-10 scale)
        promoters = sum(1 for r in ratings if r >= 4.5)
        detractors = sum(1 for r in ratings if r <= 2)
        nps = round((promoters - detractors) / max(len(ratings), 1) * 100, 1) if ratings else 0

        return {
            "total_feedback": len(ratings),
            "average_rating": avg_rating,
            "nps_score": nps,
            "rating_distribution": {str(k): v for k, v in sorted(rating_distribution.items())},
            "sentiment": dict(sentiment_counts.most_common()),
            "recent_feedback": feedback_texts[:10],
            "feedback_rate": round(len(ratings) / max(len(conversations), 1) * 100, 1)
                if conversations else 0,
        }

    @staticmethod
    def compute_escalation_metrics(conversations: list) -> dict[str, Any]:
        """Compute escalation analysis."""
        total = len(conversations)
        escalated = [c for c in conversations if getattr(c, "escalated", False)]
        escalation_reasons = Counter()

        for c in escalated:
            reason = getattr(c, "escalation_reason", None) or "unknown"
            escalation_reasons[str(reason)] += 1

        return {
            "total_conversations": total,
            "escalated": len(escalated),
            "escalation_rate": round(len(escalated) / max(total, 1) * 100, 1),
            "reasons": dict(escalation_reasons.most_common(10)),
        }


# Singleton engine
_engine = AnalyticsEngine()


# ══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_dashboard(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
) -> dict[str, Any]:
    """Overview dashboard with key KPIs."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, end = _parse_period(days)

        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        ).all()

        # Previous period for trend comparison
        prev_start = start - timedelta(days=days)
        prev_conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= prev_start,
            ChatSession.created_at < start,
        ).all()

        conv_metrics = _engine.compute_conversation_metrics(conversations, days)
        prev_conv_metrics = _engine.compute_conversation_metrics(prev_conversations, days)

        feedback = _engine.compute_feedback_metrics(conversations)
        escalations = _engine.compute_escalation_metrics(conversations)

        return {
            "period": {"days": days, "start": start.isoformat(), "end": end.isoformat()},
            "kpis": {
                "total_conversations": {
                    "value": conv_metrics["total"],
                    "trend": _trend_percent(conv_metrics["total"], prev_conv_metrics["total"]),
                },
                "daily_average": {
                    "value": conv_metrics["daily_average"],
                    "trend": _trend_percent(conv_metrics["daily_average"], prev_conv_metrics["daily_average"]),
                },
                "resolution_rate": {
                    "value": conv_metrics["resolution_rate"],
                    "trend": _trend_percent(conv_metrics["resolution_rate"], prev_conv_metrics["resolution_rate"]),
                },
                "customer_satisfaction": {
                    "value": feedback["average_rating"],
                    "nps": feedback["nps_score"],
                },
                "escalation_rate": {
                    "value": escalations["escalation_rate"],
                    "trend": _trend_percent(escalations["escalation_rate"],
                        _engine.compute_escalation_metrics(prev_conversations)["escalation_rate"]),
                },
            },
            "channels": conv_metrics["by_channel"],
            "top_escalation_reasons": escalations["reasons"],
        }
    finally:
        db.close()


@router.get("/conversations")
async def get_conversation_metrics(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
    channel: Optional[str] = Query(None, description="Filter by channel"),
) -> dict[str, Any]:
    """Detailed conversation metrics over time."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, end = _parse_period(days)

        query = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        )

        if channel:
            if hasattr(ChatSession, "channel"):
                query = query.filter(ChatSession.channel == channel)
            elif hasattr(ChatSession, "source"):
                query = query.filter(ChatSession.source == channel)

        conversations = query.all()
        metrics = _engine.compute_conversation_metrics(conversations, days)
        by_day = _bucket_by_day(conversations, "created_at", days)

        return {
            "period": {"days": days, "start": start.isoformat(), "end": end.isoformat()},
            "metrics": metrics,
            "time_series": by_day,
            "filter": {"channel": channel},
        }
    finally:
        db.close()


@router.get("/intents")
async def get_intent_analysis(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Intent distribution and trend analysis."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, _ = _parse_period(days)

        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        ).all()

        intents = _engine.compute_intent_analysis(conversations)

        return {
            "period": {"days": days},
            "analysis": intents,
        }
    finally:
        db.close()


@router.get("/feedback")
async def get_feedback_metrics(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Customer satisfaction scores and feedback analysis."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, _ = _parse_period(days)

        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        ).all()

        feedback = _engine.compute_feedback_metrics(conversations)

        return {
            "period": {"days": days},
            "feedback": feedback,
        }
    finally:
        db.close()


@router.get("/channels")
async def get_channel_performance(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Channel performance comparison."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, _ = _parse_period(days)

        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        ).all()

        # Group by channel
        channel_data = defaultdict(list)
        for c in conversations:
            ch = getattr(c, "channel", None) or getattr(c, "source", "unknown")
            channel_data[str(ch)].append(c)

        channels = {}
        for ch_name, ch_convs in channel_data.items():
            metrics = _engine.compute_conversation_metrics(ch_convs, days)
            feedback = _engine.compute_feedback_metrics(ch_convs)
            channels[ch_name] = {
                "conversations": metrics["total"],
                "resolution_rate": metrics["resolution_rate"],
                "avg_messages": metrics["avg_messages_per_conversation"],
                "satisfaction": feedback["average_rating"],
                "feedback_count": feedback["total_feedback"],
            }

        return {
            "period": {"days": days},
            "channels": channels,
        }
    finally:
        db.close()


@router.get("/escalations")
async def get_escalation_analysis(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Escalation analysis with reasons and trends."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, _ = _parse_period(days)

        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        ).all()

        escalations = _engine.compute_escalation_metrics(conversations)

        # Time series of escalations
        escalated_convs = [c for c in conversations if getattr(c, "escalated", False)]
        by_day = _bucket_by_day(escalated_convs, "created_at", days)

        return {
            "period": {"days": days},
            "escalations": escalations,
            "time_series": by_day,
        }
    finally:
        db.close()


@router.get("/agents")
async def get_agent_performance(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    """Agent/specialist performance metrics."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, _ = _parse_period(days)

        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        ).all()

        # Group by agent/specialist
        agent_data = defaultdict(list)
        for c in conversations:
            agent = getattr(c, "agent", None) or getattr(c, "specialist", "general")
            agent_data[str(agent)].append(c)

        agents = {}
        for agent_name, agent_convs in agent_data.items():
            metrics = _engine.compute_conversation_metrics(agent_convs, days)
            feedback = _engine.compute_feedback_metrics(agent_convs)
            agents[agent_name] = {
                "conversations": metrics["total"],
                "resolution_rate": metrics["resolution_rate"],
                "avg_messages": metrics["avg_messages_per_conversation"],
                "satisfaction": feedback["average_rating"],
            }

        return {
            "period": {"days": days},
            "agents": agents,
        }
    finally:
        db.close()


@router.get("/export")
async def export_analytics(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
    format: str = Query("json", description="Export format: json or csv"),
) -> Any:
    """Export analytics data."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        start, end = _parse_period(days)

        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= start,
        ).all()

        conv_metrics = _engine.compute_conversation_metrics(conversations, days)
        intent_analysis = _engine.compute_intent_analysis(conversations)
        feedback = _engine.compute_feedback_metrics(conversations)
        escalations = _engine.compute_escalation_metrics(conversations)

        export_data = {
            "tenant_id": user.tenant_id,
            "period": {"days": days, "start": start.isoformat(), "end": end.isoformat()},
            "conversations": conv_metrics,
            "intents": intent_analysis,
            "feedback": feedback,
            "escalations": escalations,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(["Metric", "Value", "Category"])

            # Flatten metrics
            writer.writerow(["Total Conversations", conv_metrics["total"], "conversations"])
            writer.writerow(["Daily Average", conv_metrics["daily_average"], "conversations"])
            writer.writerow(["Resolution Rate %", conv_metrics["resolution_rate"], "conversations"])
            writer.writerow(["Avg Rating", feedback["average_rating"], "feedback"])
            writer.writerow(["NPS Score", feedback["nps_score"], "feedback"])
            writer.writerow(["Escalation Rate %", escalations["escalation_rate"], "escalations"])

            for intent_data in intent_analysis.get("top_intents", []):
                writer.writerow([
                    f"Intent: {intent_data['intent']}",
                    intent_data["count"],
                    "intents",
                ])

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=analytics_{days}d.csv"},
            )

        return export_data
    finally:
        db.close()
