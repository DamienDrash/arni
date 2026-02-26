"""app/gateway/routers/revenue_analytics.py — Revenue & Token Analytics for System Admin.

Endpoints (prefix /admin/revenue):
    GET  /admin/revenue/overview       → MRR, ARR, total revenue, subscriber counts
    GET  /admin/revenue/monthly        → Monthly revenue breakdown (last 12 months)
    GET  /admin/revenue/tenants        → Per-tenant revenue + usage summary
    GET  /admin/revenue/tokens         → Token usage analytics across all tenants
    GET  /admin/revenue/token-costs    → Estimated LLM costs vs revenue
"""
from __future__ import annotations

import json as _json
import structlog
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text, desc

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import (
    Plan, Subscription, Tenant, UsageRecord, TenantAddon,
    AddonDefinition, TokenPurchase,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/revenue", tags=["revenue-analytics"])


def _require_system_admin(user: AuthContext) -> None:
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/overview")
async def revenue_overview(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """High-level revenue KPIs: MRR, ARR, subscriber count, churn."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        # Active subscriptions with their plans
        active_subs = (
            db.query(Subscription, Plan)
            .join(Plan, Subscription.plan_id == Plan.id)
            .filter(Subscription.status.in_(["active", "trialing"]))
            .all()
        )

        mrr_cents = 0
        plan_distribution = {}
        for sub, plan in active_subs:
            mrr_cents += plan.price_monthly_cents or 0
            plan_name = plan.name or plan.slug
            plan_distribution[plan_name] = plan_distribution.get(plan_name, 0) + 1

        # Active addon revenue
        active_addons = (
            db.query(TenantAddon, AddonDefinition)
            .join(AddonDefinition, TenantAddon.addon_slug == AddonDefinition.slug)
            .filter(TenantAddon.status == "active")
            .all()
        )
        addon_mrr_cents = sum((ad.price_monthly_cents or 0) * (ta.quantity or 1) for ta, ad in active_addons)

        # Token purchase revenue (all time)
        token_revenue = db.query(
            func.coalesce(func.sum(TokenPurchase.price_cents), 0)
        ).filter(TokenPurchase.status == "completed").scalar() or 0

        # Canceled in last 30 days
        now = datetime.now(timezone.utc)
        canceled_count = db.query(func.count(Subscription.id)).filter(
            Subscription.status == "canceled",
        ).scalar() or 0

        total_tenants = db.query(func.count(Tenant.id)).filter(Tenant.is_active.is_(True)).scalar() or 0
        paying_tenants = len([s for s, p in active_subs if (p.price_monthly_cents or 0) > 0])

        total_mrr = mrr_cents + addon_mrr_cents

        return {
            "mrr_cents": total_mrr,
            "mrr_formatted": f"{total_mrr / 100:.2f}",
            "arr_cents": total_mrr * 12,
            "arr_formatted": f"{total_mrr * 12 / 100:.2f}",
            "plan_mrr_cents": mrr_cents,
            "addon_mrr_cents": addon_mrr_cents,
            "token_revenue_cents": token_revenue,
            "total_subscribers": len(active_subs),
            "paying_subscribers": paying_tenants,
            "free_subscribers": len(active_subs) - paying_tenants,
            "canceled_total": canceled_count,
            "total_tenants": total_tenants,
            "plan_distribution": plan_distribution,
        }
    finally:
        db.close()


@router.get("/monthly")
async def revenue_monthly(
    months: int = Query(12, ge=1, le=24),
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Monthly revenue breakdown for charts."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        result = []

        for i in range(months - 1, -1, -1):
            month = now.month - i
            year = now.year
            while month <= 0:
                month += 12
                year -= 1

            # Get usage records for this month
            usage = db.query(
                func.coalesce(func.sum(UsageRecord.messages_inbound), 0).label("inbound"),
                func.coalesce(func.sum(UsageRecord.messages_outbound), 0).label("outbound"),
                func.coalesce(func.sum(UsageRecord.llm_tokens_used), 0).label("tokens_used"),
                func.coalesce(func.sum(UsageRecord.active_members), 0).label("members"),
            ).filter(
                UsageRecord.period_year == year,
                UsageRecord.period_month == month,
            ).first()

            # Token purchases for this month
            token_rev = db.query(
                func.coalesce(func.sum(TokenPurchase.price_cents), 0)
            ).filter(
                TokenPurchase.status == "completed",
                func.extract("year", TokenPurchase.created_at) == year,
                func.extract("month", TokenPurchase.created_at) == month,
            ).scalar() or 0

            # Count active subs (approximate: count all non-canceled as of that month)
            active_count = db.query(func.count(Subscription.id)).filter(
                Subscription.status.in_(["active", "trialing"]),
            ).scalar() or 0

            # Estimated MRR for this month (using current plan prices as approximation)
            # For historical accuracy, we'd need to store monthly snapshots
            # For now, use current pricing * active subs as estimate
            estimated_mrr = 0
            subs = (
                db.query(Subscription, Plan)
                .join(Plan, Subscription.plan_id == Plan.id)
                .filter(Subscription.status.in_(["active", "trialing"]))
                .all()
            )
            for sub, plan in subs:
                estimated_mrr += plan.price_monthly_cents or 0

            result.append({
                "year": year,
                "month": month,
                "label": f"{year}-{month:02d}",
                "mrr_cents": estimated_mrr,
                "token_revenue_cents": token_rev,
                "messages_inbound": usage.inbound if usage else 0,
                "messages_outbound": usage.outbound if usage else 0,
                "tokens_used": usage.tokens_used if usage else 0,
                "active_members": usage.members if usage else 0,
                "active_subscribers": active_count,
            })

        return result
    finally:
        db.close()


@router.get("/tenants")
async def revenue_tenants(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Per-tenant revenue and usage summary."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
        result = []

        for tenant in tenants:
            sub = db.query(Subscription).filter(Subscription.tenant_id == tenant.id).first()
            plan = None
            if sub:
                plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()

            usage = db.query(UsageRecord).filter(
                UsageRecord.tenant_id == tenant.id,
                UsageRecord.period_year == now.year,
                UsageRecord.period_month == now.month,
            ).first()

            # Addon count
            addon_count = db.query(func.count(TenantAddon.id)).filter(
                TenantAddon.tenant_id == tenant.id,
                TenantAddon.status == "active",
            ).scalar() or 0

            result.append({
                "tenant_id": tenant.id,
                "tenant_name": tenant.name,
                "tenant_slug": tenant.slug,
                "plan_name": plan.name if plan else "No Plan",
                "plan_slug": plan.slug if plan else None,
                "status": sub.status if sub else "none",
                "mrr_cents": (plan.price_monthly_cents or 0) if plan else 0,
                "addon_count": addon_count,
                "messages_this_month": (usage.messages_inbound + usage.messages_outbound) if usage else 0,
                "tokens_used": usage.llm_tokens_used if usage else 0,
                "token_limit": plan.monthly_tokens if plan else 0,
                "members": usage.active_members if usage else 0,
            })

        return sorted(result, key=lambda x: x["mrr_cents"], reverse=True)
    finally:
        db.close()


@router.get("/tokens")
async def token_analytics(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Token usage analytics across all tenants."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Current month totals
        current = db.query(
            func.coalesce(func.sum(UsageRecord.llm_tokens_used), 0).label("used"),
        ).filter(
            UsageRecord.period_year == now.year,
            UsageRecord.period_month == now.month,
        ).first()

        # Per-tenant breakdown
        tenant_usage = (
            db.query(
                Tenant.name,
                Tenant.id,
                UsageRecord.llm_tokens_used,
                Plan.monthly_tokens,
                Plan.name.label("plan_name"),
            )
            .join(UsageRecord, UsageRecord.tenant_id == Tenant.id)
            .join(Subscription, Subscription.tenant_id == Tenant.id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .filter(
                UsageRecord.period_year == now.year,
                UsageRecord.period_month == now.month,
            )
            .all()
        )

        top_consumers = []
        for name, tid, used, limit, plan_name in tenant_usage:
            pct = round((used / limit * 100), 1) if limit and limit > 0 else 0
            top_consumers.append({
                "tenant_id": tid,
                "tenant_name": name,
                "plan_name": plan_name,
                "tokens_used": used,
                "token_limit": limit,
                "usage_pct": pct,
            })

        top_consumers.sort(key=lambda x: x["tokens_used"], reverse=True)

        # Token purchases
        total_purchased = db.query(
            func.coalesce(func.sum(TokenPurchase.tokens_amount), 0)
        ).filter(TokenPurchase.status == "completed").scalar() or 0

        purchase_revenue = db.query(
            func.coalesce(func.sum(TokenPurchase.price_cents), 0)
        ).filter(TokenPurchase.status == "completed").scalar() or 0

        # Estimated cost (rough: $0.002 per 1K tokens average across providers)
        total_used = current.used if current else 0
        estimated_cost_cents = int(total_used / 1000 * 0.2)  # 0.2 cents per 1K tokens avg

        return {
            "current_month_tokens_used": total_used,
            "total_tokens_purchased": total_purchased,
            "purchase_revenue_cents": purchase_revenue,
            "estimated_cost_cents": estimated_cost_cents,
            "margin_cents": purchase_revenue - estimated_cost_cents,
            "top_consumers": top_consumers[:20],
        }
    finally:
        db.close()
