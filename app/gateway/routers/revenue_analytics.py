"""app/gateway/routers/revenue_analytics.py — Revenue & Token Analytics for System Admin.

Revenue data is sourced from **Stripe Invoices & Charges** (source of truth)
with local DB data as fallback / enrichment for usage metrics.

Endpoints (prefix /admin/revenue):
    GET  /admin/revenue/overview       → MRR, ARR, total revenue, subscriber counts (Stripe-backed)
    GET  /admin/revenue/monthly        → Monthly revenue breakdown from Stripe invoices
    GET  /admin/revenue/tenants        → Per-tenant revenue from Stripe + local usage
    GET  /admin/revenue/tokens         → Token usage analytics across all tenants
    GET  /admin/revenue/stripe-invoices → Raw Stripe invoice list for verification
"""
from __future__ import annotations

import json as _json
import structlog
from datetime import datetime, timezone, timedelta
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


def _get_stripe_for_system():
    """Get Stripe module configured with the system-level secret key."""
    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=500, detail="stripe package not installed")

    from app.gateway.persistence import persistence
    secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
    if not secret_key:
        raise HTTPException(status_code=500, detail="Stripe secret key not configured")
    stripe.api_key = secret_key
    return stripe


@router.get("/overview")
async def revenue_overview(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """High-level revenue KPIs sourced from Stripe + local DB."""
    _require_system_admin(user)

    db = SessionLocal()
    try:
        # ── Local DB: subscriber counts & plan distribution ──
        active_subs = (
            db.query(Subscription, Plan)
            .join(Plan, Subscription.plan_id == Plan.id)
            .filter(Subscription.status.in_(["active", "trialing"]))
            .all()
        )

        plan_distribution = {}
        for sub, plan in active_subs:
            plan_name = plan.name or plan.slug
            plan_distribution[plan_name] = plan_distribution.get(plan_name, 0) + 1

        canceled_count = db.query(func.count(Subscription.id)).filter(
            Subscription.status == "canceled",
        ).scalar() or 0

        total_tenants = db.query(func.count(Tenant.id)).filter(Tenant.is_active.is_(True)).scalar() or 0

        # ── Stripe: actual revenue data ──
        stripe_mrr_cents = 0
        stripe_total_revenue_cents = 0
        paying_tenants = 0

        try:
            stripe = _get_stripe_for_system()

            # Get all active subscriptions from Stripe for accurate MRR
            stripe_subs = stripe.Subscription.list(status="active", limit=100)
            for s in stripe_subs.auto_paging_iter():
                for item in s.get("items", {}).get("data", []):
                    price = item.get("price", {})
                    amount = price.get("unit_amount", 0)
                    interval = price.get("recurring", {}).get("interval", "month")
                    if interval == "year":
                        stripe_mrr_cents += amount // 12
                    else:
                        stripe_mrr_cents += amount
                paying_tenants += 1

            # Get total revenue from paid invoices (last 12 months)
            twelve_months_ago = int((datetime.now(timezone.utc) - timedelta(days=365)).timestamp())
            invoices = stripe.Invoice.list(
                status="paid",
                created={"gte": twelve_months_ago},
                limit=100,
            )
            for inv in invoices.auto_paging_iter():
                stripe_total_revenue_cents += inv.get("amount_paid", 0)

        except Exception as exc:
            logger.warning("revenue.stripe_fetch_failed", error=str(exc))
            # Fallback to local DB estimates
            for sub, plan in active_subs:
                stripe_mrr_cents += plan.price_monthly_cents or 0
                if (plan.price_monthly_cents or 0) > 0:
                    paying_tenants += 1

        # Active addon revenue from Stripe (or local fallback)
        addon_mrr_cents = 0
        try:
            active_addons = (
                db.query(TenantAddon, AddonDefinition)
                .join(AddonDefinition, TenantAddon.addon_slug == AddonDefinition.slug)
                .filter(TenantAddon.status == "active")
                .all()
            )
            addon_mrr_cents = sum((ad.price_monthly_cents or 0) * (ta.quantity or 1) for ta, ad in active_addons)
        except Exception:
            pass

        # Token purchase revenue
        token_revenue = db.query(
            func.coalesce(func.sum(TokenPurchase.price_cents), 0)
        ).filter(TokenPurchase.status == "completed").scalar() or 0

        total_mrr = stripe_mrr_cents + addon_mrr_cents

        return {
            "mrr_cents": total_mrr,
            "mrr_formatted": f"{total_mrr / 100:.2f}",
            "arr_cents": total_mrr * 12,
            "arr_formatted": f"{total_mrr * 12 / 100:.2f}",
            "plan_mrr_cents": stripe_mrr_cents,
            "addon_mrr_cents": addon_mrr_cents,
            "token_revenue_cents": token_revenue,
            "stripe_total_revenue_12m_cents": stripe_total_revenue_cents,
            "stripe_total_revenue_12m_formatted": f"{stripe_total_revenue_cents / 100:.2f}",
            "total_subscribers": len(active_subs),
            "paying_subscribers": paying_tenants,
            "free_subscribers": max(0, len(active_subs) - paying_tenants),
            "canceled_total": canceled_count,
            "total_tenants": total_tenants,
            "plan_distribution": plan_distribution,
            "data_source": "stripe",
        }
    finally:
        db.close()


@router.get("/monthly")
async def revenue_monthly(
    months: int = Query(12, ge=1, le=24),
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Monthly revenue breakdown from Stripe invoices (source of truth)."""
    _require_system_admin(user)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # ── Fetch paid invoices from Stripe for the requested period ──
        start_date = datetime(now.year, now.month, 1, tzinfo=timezone.utc) - timedelta(days=30 * months)
        start_ts = int(start_date.timestamp())

        monthly_revenue = {}  # "YYYY-MM" -> cents

        try:
            stripe = _get_stripe_for_system()
            invoices = stripe.Invoice.list(
                status="paid",
                created={"gte": start_ts},
                limit=100,
            )
            for inv in invoices.auto_paging_iter():
                paid_at = inv.get("status_transitions", {}).get("paid_at") or inv.get("created")
                if paid_at:
                    dt = datetime.fromtimestamp(paid_at, tz=timezone.utc)
                    key = f"{dt.year}-{dt.month:02d}"
                    monthly_revenue[key] = monthly_revenue.get(key, 0) + inv.get("amount_paid", 0)
        except Exception as exc:
            logger.warning("revenue.monthly_stripe_failed", error=str(exc))

        # ── Build result with local usage data enrichment ──
        result = []
        for i in range(months - 1, -1, -1):
            month = now.month - i
            year = now.year
            while month <= 0:
                month += 12
                year -= 1

            key = f"{year}-{month:02d}"

            # Local usage data
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

            # Active subscriber count
            active_count = db.query(func.count(Subscription.id)).filter(
                Subscription.status.in_(["active", "trialing"]),
            ).scalar() or 0

            stripe_revenue = monthly_revenue.get(key, 0)

            result.append({
                "year": year,
                "month": month,
                "label": key,
                "stripe_revenue_cents": stripe_revenue,
                "stripe_revenue_formatted": f"{stripe_revenue / 100:.2f}",
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
    """Per-tenant revenue from Stripe invoices + local usage data."""
    _require_system_admin(user)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

        # ── Build a map of Stripe customer → total paid (current month) ──
        customer_revenue = {}  # stripe_customer_id -> cents
        customer_total_revenue = {}  # stripe_customer_id -> all-time cents

        try:
            stripe = _get_stripe_for_system()

            # Current month invoices
            month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            month_start_ts = int(month_start.timestamp())

            invoices = stripe.Invoice.list(
                status="paid",
                created={"gte": month_start_ts},
                limit=100,
            )
            for inv in invoices.auto_paging_iter():
                cid = inv.get("customer")
                if cid:
                    customer_revenue[cid] = customer_revenue.get(cid, 0) + inv.get("amount_paid", 0)

            # All-time invoices (last 12 months for performance)
            twelve_months_ago = int((now - timedelta(days=365)).timestamp())
            all_invoices = stripe.Invoice.list(
                status="paid",
                created={"gte": twelve_months_ago},
                limit=100,
            )
            for inv in all_invoices.auto_paging_iter():
                cid = inv.get("customer")
                if cid:
                    customer_total_revenue[cid] = customer_total_revenue.get(cid, 0) + inv.get("amount_paid", 0)

        except Exception as exc:
            logger.warning("revenue.tenants_stripe_failed", error=str(exc))

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

            addon_count = db.query(func.count(TenantAddon.id)).filter(
                TenantAddon.tenant_id == tenant.id,
                TenantAddon.status == "active",
            ).scalar() or 0

            stripe_cid = sub.stripe_customer_id if sub else None
            stripe_monthly = customer_revenue.get(stripe_cid, 0) if stripe_cid else 0
            stripe_total = customer_total_revenue.get(stripe_cid, 0) if stripe_cid else 0

            # Fallback to plan price if no Stripe data
            mrr = stripe_monthly if stripe_monthly > 0 else ((plan.price_monthly_cents or 0) if plan else 0)

            result.append({
                "tenant_id": tenant.id,
                "tenant_name": tenant.name,
                "tenant_slug": tenant.slug,
                "plan_name": plan.name if plan else "No Plan",
                "plan_slug": plan.slug if plan else None,
                "status": sub.status if sub else "none",
                "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)) if sub else False,
                "mrr_cents": mrr,
                "stripe_revenue_this_month_cents": stripe_monthly,
                "stripe_revenue_12m_cents": stripe_total,
                "addon_count": addon_count,
                "messages_this_month": (usage.messages_inbound + usage.messages_outbound) if usage else 0,
                "tokens_used": usage.llm_tokens_used if usage else 0,
                "token_limit": plan.monthly_tokens if plan else 0,
                "members": usage.active_members if usage else 0,
            })

        return sorted(result, key=lambda x: x["stripe_revenue_12m_cents"], reverse=True)
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

        # Estimated cost
        total_used = current.used if current else 0
        estimated_cost_cents = int(total_used / 1000 * 0.2)

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


@router.get("/stripe-invoices")
async def list_stripe_invoices(
    limit: int = Query(25, ge=1, le=100),
    status: str = Query("paid", regex="^(paid|open|draft|void|uncollectible|all)$"),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Direkte Stripe-Rechnungsliste für Verifizierung und Audit.
    
    Zeigt die tatsächlichen Rechnungen aus Stripe an, damit der System-Admin
    die Daten mit dem Dashboard abgleichen kann.
    """
    _require_system_admin(user)

    try:
        stripe = _get_stripe_for_system()

        params = {"limit": limit}
        if status != "all":
            params["status"] = status

        invoices = stripe.Invoice.list(**params)

        result = []
        for inv in invoices.get("data", []):
            customer_email = inv.get("customer_email", "")
            customer_name = inv.get("customer_name", "")

            # Try to find tenant from metadata or customer
            tenant_name = ""
            meta = inv.get("subscription_details", {}).get("metadata", {}) if inv.get("subscription_details") else {}
            tenant_id = meta.get("tenant_id")
            if tenant_id:
                db = SessionLocal()
                try:
                    t = db.query(Tenant).filter(Tenant.id == int(tenant_id)).first()
                    if t:
                        tenant_name = t.name
                finally:
                    db.close()

            result.append({
                "invoice_id": inv.get("id"),
                "number": inv.get("number"),
                "customer_email": customer_email,
                "customer_name": customer_name,
                "tenant_name": tenant_name,
                "status": inv.get("status"),
                "amount_paid_cents": inv.get("amount_paid", 0),
                "amount_paid_formatted": f"€{inv.get('amount_paid', 0) / 100:.2f}",
                "amount_due_cents": inv.get("amount_due", 0),
                "currency": inv.get("currency", "eur"),
                "created": datetime.fromtimestamp(inv.get("created", 0), tz=timezone.utc).isoformat(),
                "paid_at": (
                    datetime.fromtimestamp(
                        inv.get("status_transitions", {}).get("paid_at", 0), tz=timezone.utc
                    ).isoformat()
                    if inv.get("status_transitions", {}).get("paid_at")
                    else None
                ),
                "invoice_pdf": inv.get("invoice_pdf"),
                "hosted_invoice_url": inv.get("hosted_invoice_url"),
                "subscription_id": inv.get("subscription"),
                "lines": [
                    {
                        "description": line.get("description", ""),
                        "amount_cents": line.get("amount", 0),
                        "period_start": (
                            datetime.fromtimestamp(
                                line.get("period", {}).get("start", 0), tz=timezone.utc
                            ).isoformat()
                            if line.get("period", {}).get("start")
                            else None
                        ),
                        "period_end": (
                            datetime.fromtimestamp(
                                line.get("period", {}).get("end", 0), tz=timezone.utc
                            ).isoformat()
                            if line.get("period", {}).get("end")
                            else None
                        ),
                    }
                    for line in inv.get("lines", {}).get("data", [])
                ],
            })

        return {
            "invoices": result,
            "total_count": len(result),
            "has_more": invoices.get("has_more", False),
            "data_source": "stripe_api",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("revenue.stripe_invoices_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
