"""ARIIA AI Config – Observability & Usage Analytics Router.

Provides endpoints for:
- Usage dashboards (per tenant, per agent, per model)
- Budget monitoring and alerts
- Cost analytics and trends
- Request latency metrics
"""

from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, text as sa_text, Integer
from sqlalchemy.orm import Session

from app.domains.billing.models import LLMUsageLog, Plan, Subscription, UsageRecord
from app.domains.identity.models import Tenant
from app.core.auth import AuthContext, get_current_user, require_role
from app.ai_config.models import PlanAIBudget, TenantAIBudgetOverride
from app.shared.db import open_session

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class UsageSummary(BaseModel):
    period: str  # "2026-03"
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_cents: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0


class UsageByModel(BaseModel):
    model_id: str
    provider_slug: str
    request_count: int = 0
    total_tokens: int = 0
    total_cost_cents: float = 0.0
    avg_latency_ms: float = 0.0


class UsageByAgent(BaseModel):
    agent_name: str
    request_count: int = 0
    total_tokens: int = 0
    total_cost_cents: float = 0.0
    avg_latency_ms: float = 0.0


class BudgetStatus(BaseModel):
    tenant_id: int
    plan_name: str = ""
    monthly_token_limit: Optional[int] = None
    monthly_budget_cents: Optional[int] = None
    tokens_used: int = 0
    budget_used_cents: float = 0.0
    tokens_remaining: Optional[int] = None
    budget_remaining_cents: Optional[float] = None
    usage_percent: float = 0.0
    is_over_budget: bool = False
    overage_enabled: bool = False


class DailyUsage(BaseModel):
    date: str
    requests: int = 0
    tokens: int = 0
    cost_cents: float = 0.0


class HourlyUsage(BaseModel):
    hour: int
    requests: int = 0
    tokens: int = 0
    avg_latency_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTERS
# ═══════════════════════════════════════════════════════════════════════════════

admin_obs_router = APIRouter(prefix="/admin/ai/observability", tags=["ai-observability-admin"])
tenant_obs_router = APIRouter(prefix="/api/v1/tenant/ai/observability", tags=["ai-observability-tenant"])


def _get_db():
    db = open_session()
    try:
        yield db
    finally:
        db.close()


def _require_system_admin(user: AuthContext = Depends(get_current_user)) -> AuthContext:
    require_role(user, {"system_admin"})
    return user


def _require_tenant_admin(user: AuthContext = Depends(get_current_user)) -> AuthContext:
    require_role(user, {"system_admin", "tenant_admin"})
    return user


# ── Admin Endpoints ───────────────────────────────────────────────────────────

@admin_obs_router.get("/usage/summary", response_model=UsageSummary)
def admin_usage_summary(
    tenant_id: Optional[int] = Query(None),
    year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year),
    month: int = Query(default_factory=lambda: datetime.now(timezone.utc).month),
    user: AuthContext = Depends(_require_system_admin),
    db: Session = Depends(_get_db),
):
    """Get aggregated usage summary for a period (optionally filtered by tenant)."""
    return _get_usage_summary(db, year, month, tenant_id)


@admin_obs_router.get("/usage/by-model", response_model=list[UsageByModel])
def admin_usage_by_model(
    tenant_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    user: AuthContext = Depends(_require_system_admin),
    db: Session = Depends(_get_db),
):
    """Get usage breakdown by model."""
    return _get_usage_by_model(db, days, tenant_id)


@admin_obs_router.get("/usage/by-agent", response_model=list[UsageByAgent])
def admin_usage_by_agent(
    tenant_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    user: AuthContext = Depends(_require_system_admin),
    db: Session = Depends(_get_db),
):
    """Get usage breakdown by agent."""
    return _get_usage_by_agent(db, days, tenant_id)


@admin_obs_router.get("/usage/daily", response_model=list[DailyUsage])
def admin_daily_usage(
    tenant_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=90),
    user: AuthContext = Depends(_require_system_admin),
    db: Session = Depends(_get_db),
):
    """Get daily usage trend."""
    return _get_daily_usage(db, days, tenant_id)


@admin_obs_router.get("/usage/hourly", response_model=list[HourlyUsage])
def admin_hourly_usage(
    tenant_id: Optional[int] = Query(None),
    user: AuthContext = Depends(_require_system_admin),
    db: Session = Depends(_get_db),
):
    """Get hourly usage distribution for today."""
    return _get_hourly_usage(db, tenant_id)


@admin_obs_router.get("/budget/all", response_model=list[BudgetStatus])
def admin_all_budgets(
    user: AuthContext = Depends(_require_system_admin),
    db: Session = Depends(_get_db),
):
    """Get budget status for all tenants."""
    subs = db.query(Subscription).all()
    results = []
    for sub in subs:
        budget = db.query(PlanAIBudget).filter(PlanAIBudget.plan_id == sub.plan_id).first()
        if not budget:
            continue
        results.append(_compute_budget_status(db, sub.tenant_id, budget, sub.plan_id))
    return results


# ── Tenant Endpoints ──────────────────────────────────────────────────────────

@tenant_obs_router.get("/usage/summary", response_model=UsageSummary)
def tenant_usage_summary(
    year: int = Query(default_factory=lambda: datetime.now(timezone.utc).year),
    month: int = Query(default_factory=lambda: datetime.now(timezone.utc).month),
    user: AuthContext = Depends(_require_tenant_admin),
    db: Session = Depends(_get_db),
):
    """Get usage summary for the current tenant."""
    return _get_usage_summary(db, year, month, user.tenant_id)


@tenant_obs_router.get("/usage/by-model", response_model=list[UsageByModel])
def tenant_usage_by_model(
    days: int = Query(30, ge=1, le=365),
    user: AuthContext = Depends(_require_tenant_admin),
    db: Session = Depends(_get_db),
):
    return _get_usage_by_model(db, days, user.tenant_id)


@tenant_obs_router.get("/usage/by-agent", response_model=list[UsageByAgent])
def tenant_usage_by_agent(
    days: int = Query(30, ge=1, le=365),
    user: AuthContext = Depends(_require_tenant_admin),
    db: Session = Depends(_get_db),
):
    return _get_usage_by_agent(db, days, user.tenant_id)


@tenant_obs_router.get("/usage/daily", response_model=list[DailyUsage])
def tenant_daily_usage(
    days: int = Query(30, ge=1, le=90),
    user: AuthContext = Depends(_require_tenant_admin),
    db: Session = Depends(_get_db),
):
    return _get_daily_usage(db, days, user.tenant_id)


@tenant_obs_router.get("/budget", response_model=BudgetStatus)
def tenant_budget_status(
    user: AuthContext = Depends(_require_tenant_admin),
    db: Session = Depends(_get_db),
):
    """Get budget status for the current tenant."""
    sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
    if not sub:
        raise HTTPException(404, "No subscription found")
    budget = db.query(PlanAIBudget).filter(PlanAIBudget.plan_id == sub.plan_id).first()
    if not budget:
        return BudgetStatus(tenant_id=user.tenant_id)
    return _compute_budget_status(db, user.tenant_id, budget, sub.plan_id)


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_usage_summary(db: Session, year: int, month: int, tenant_id: Optional[int] = None) -> UsageSummary:
    """Aggregate usage for a specific month."""
    q = db.query(
        func.count(LLMUsageLog.id).label("total"),
        func.sum(func.cast(LLMUsageLog.success, Integer)).label("success_count"),
        func.sum(LLMUsageLog.total_tokens).label("tokens"),
        func.sum(LLMUsageLog.prompt_tokens).label("pt"),
        func.sum(LLMUsageLog.completion_tokens).label("ct"),
        func.sum(LLMUsageLog.total_cost_cents).label("cost"),
        func.avg(LLMUsageLog.latency_ms).label("avg_lat"),
    ).filter(
        func.extract("year", LLMUsageLog.created_at) == year,
        func.extract("month", LLMUsageLog.created_at) == month,
    )
    if tenant_id:
        q = q.filter(LLMUsageLog.tenant_id == tenant_id)

    row = q.first()
    total = row.total or 0
    return UsageSummary(
        period=f"{year}-{month:02d}",
        total_requests=total,
        successful_requests=int(row.success_count or 0),
        failed_requests=total - int(row.success_count or 0),
        total_tokens=int(row.tokens or 0),
        prompt_tokens=int(row.pt or 0),
        completion_tokens=int(row.ct or 0),
        total_cost_cents=round(float(row.cost or 0), 4),
        avg_latency_ms=round(float(row.avg_lat or 0), 1),
    )


def _get_usage_by_model(db: Session, days: int, tenant_id: Optional[int] = None) -> list[UsageByModel]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(
        LLMUsageLog.model_id,
        LLMUsageLog.provider_id,
        func.count(LLMUsageLog.id).label("cnt"),
        func.sum(LLMUsageLog.total_tokens).label("tokens"),
        func.sum(LLMUsageLog.total_cost_cents).label("cost"),
        func.avg(LLMUsageLog.latency_ms).label("avg_lat"),
    ).filter(LLMUsageLog.created_at >= cutoff)
    if tenant_id:
        q = q.filter(LLMUsageLog.tenant_id == tenant_id)
    q = q.group_by(LLMUsageLog.model_id, LLMUsageLog.provider_id)

    results = []
    for row in q.all():
        results.append(UsageByModel(
            model_id=row.model_id or "unknown",
            provider_slug=row.provider_id or "unknown",
            request_count=row.cnt or 0,
            total_tokens=int(row.tokens or 0),
            total_cost_cents=round(float(row.cost or 0), 4),
            avg_latency_ms=round(float(row.avg_lat or 0), 1),
        ))
    return sorted(results, key=lambda x: x.total_cost_cents, reverse=True)


def _get_usage_by_agent(db: Session, days: int, tenant_id: Optional[int] = None) -> list[UsageByAgent]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(
        LLMUsageLog.agent_name,
        func.count(LLMUsageLog.id).label("cnt"),
        func.sum(LLMUsageLog.total_tokens).label("tokens"),
        func.sum(LLMUsageLog.total_cost_cents).label("cost"),
        func.avg(LLMUsageLog.latency_ms).label("avg_lat"),
    ).filter(LLMUsageLog.created_at >= cutoff)
    if tenant_id:
        q = q.filter(LLMUsageLog.tenant_id == tenant_id)
    q = q.group_by(LLMUsageLog.agent_name)

    results = []
    for row in q.all():
        results.append(UsageByAgent(
            agent_name=row.agent_name or "unknown",
            request_count=row.cnt or 0,
            total_tokens=int(row.tokens or 0),
            total_cost_cents=round(float(row.cost or 0), 4),
            avg_latency_ms=round(float(row.avg_lat or 0), 1),
        ))
    return sorted(results, key=lambda x: x.total_cost_cents, reverse=True)


def _get_daily_usage(db: Session, days: int, tenant_id: Optional[int] = None) -> list[DailyUsage]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(
        func.date(LLMUsageLog.created_at).label("day"),
        func.count(LLMUsageLog.id).label("cnt"),
        func.sum(LLMUsageLog.total_tokens).label("tokens"),
        func.sum(LLMUsageLog.total_cost_cents).label("cost"),
    ).filter(LLMUsageLog.created_at >= cutoff)
    if tenant_id:
        q = q.filter(LLMUsageLog.tenant_id == tenant_id)
    q = q.group_by(func.date(LLMUsageLog.created_at)).order_by(func.date(LLMUsageLog.created_at))

    return [
        DailyUsage(
            date=str(row.day),
            requests=row.cnt or 0,
            tokens=int(row.tokens or 0),
            cost_cents=round(float(row.cost or 0), 4),
        )
        for row in q.all()
    ]


def _get_hourly_usage(db: Session, tenant_id: Optional[int] = None) -> list[HourlyUsage]:
    today = datetime.now(timezone.utc).date()
    q = db.query(
        func.extract("hour", LLMUsageLog.created_at).label("hr"),
        func.count(LLMUsageLog.id).label("cnt"),
        func.sum(LLMUsageLog.total_tokens).label("tokens"),
        func.avg(LLMUsageLog.latency_ms).label("avg_lat"),
    ).filter(func.date(LLMUsageLog.created_at) == today)
    if tenant_id:
        q = q.filter(LLMUsageLog.tenant_id == tenant_id)
    q = q.group_by(func.extract("hour", LLMUsageLog.created_at))

    return [
        HourlyUsage(
            hour=int(row.hr),
            requests=row.cnt or 0,
            tokens=int(row.tokens or 0),
            avg_latency_ms=round(float(row.avg_lat or 0), 1),
        )
        for row in q.all()
    ]


def _compute_budget_status(db: Session, tenant_id: int, budget: PlanAIBudget, plan_id: int) -> BudgetStatus:
    """Compute the current budget status for a tenant."""
    now = datetime.now(timezone.utc)

    # Check for budget override
    override = db.query(TenantAIBudgetOverride).filter(TenantAIBudgetOverride.tenant_id == tenant_id).first()
    effective_token_limit = override.monthly_token_limit if override and override.monthly_token_limit else budget.monthly_token_limit
    effective_budget_cents = override.monthly_budget_cents if override and override.monthly_budget_cents else budget.monthly_budget_cents

    # Get current usage
    usage = db.query(UsageRecord).filter(
        UsageRecord.tenant_id == tenant_id,
        UsageRecord.period_year == now.year,
        UsageRecord.period_month == now.month,
    ).first()
    tokens_used = usage.llm_tokens_used if usage else 0

    # Get cost usage from logs
    cost_used = db.query(func.sum(LLMUsageLog.total_cost_cents)).filter(
        LLMUsageLog.tenant_id == tenant_id,
        func.extract("year", LLMUsageLog.created_at) == now.year,
        func.extract("month", LLMUsageLog.created_at) == now.month,
    ).scalar() or 0.0

    tokens_remaining = max(0, effective_token_limit - tokens_used) if effective_token_limit else None
    budget_remaining = max(0, effective_budget_cents - cost_used) if effective_budget_cents else None

    usage_percent = 0.0
    if effective_token_limit and effective_token_limit > 0:
        usage_percent = round((tokens_used / effective_token_limit) * 100, 1)
    elif effective_budget_cents and effective_budget_cents > 0:
        usage_percent = round((cost_used / effective_budget_cents) * 100, 1)

    is_over = usage_percent >= 100.0

    # Get plan name
    plan = db.query(Plan).filter(Plan.id == plan_id).first()

    return BudgetStatus(
        tenant_id=tenant_id,
        plan_name=plan.name if plan else "",
        monthly_token_limit=effective_token_limit,
        monthly_budget_cents=effective_budget_cents,
        tokens_used=tokens_used,
        budget_used_cents=round(float(cost_used), 4),
        tokens_remaining=tokens_remaining,
        budget_remaining_cents=round(float(budget_remaining), 4) if budget_remaining is not None else None,
        usage_percent=usage_percent,
        is_over_budget=is_over,
        overage_enabled=budget.overage_enabled,
    )
