"""app/gateway/routers/llm_costs.py — Admin endpoints for LLM cost management & analytics."""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text, func, desc

from app.core.db import SessionLocal
from app.core.models import LLMModelCost, LLMUsageLog
from app.gateway.auth import get_current_user, AuthContext

def _require_system_admin(user: AuthContext) -> None:
    from fastapi import HTTPException
    if user.role != "system_admin":
        raise HTTPException(403, "System admin required")

logger = structlog.get_logger()
router = APIRouter(tags=["LLM Costs"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ModelCostUpdate(BaseModel):
    provider_id: str
    model_id: str
    display_name: Optional[str] = None
    input_cost_per_million: int
    output_cost_per_million: int
    is_active: bool = True


class ModelCostResponse(BaseModel):
    id: int
    provider_id: str
    model_id: str
    display_name: Optional[str]
    input_cost_per_million: int
    output_cost_per_million: int
    is_active: bool


# ── Model Cost CRUD ───────────────────────────────────────────────────────────

@router.get("/llm/model-costs")
async def list_model_costs(user: AuthContext = Depends(get_current_user)):
    """List all LLM model cost configurations."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        costs = db.query(LLMModelCost).order_by(LLMModelCost.provider_id, LLMModelCost.model_id).all()
        return [
            {
                "id": c.id,
                "provider_id": c.provider_id,
                "model_id": c.model_id,
                "display_name": c.display_name,
                "input_cost_per_million": c.input_cost_per_million,
                "output_cost_per_million": c.output_cost_per_million,
                "is_active": c.is_active,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in costs
        ]
    finally:
        db.close()


@router.put("/llm/model-costs")
async def upsert_model_cost(data: ModelCostUpdate, user: AuthContext = Depends(get_current_user)):
    """Create or update a model cost entry."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        existing = db.query(LLMModelCost).filter(LLMModelCost.model_id == data.model_id).first()
        if existing:
            existing.provider_id = data.provider_id
            existing.display_name = data.display_name
            existing.input_cost_per_million = data.input_cost_per_million
            existing.output_cost_per_million = data.output_cost_per_million
            existing.is_active = data.is_active
            existing.updated_at = datetime.now(timezone.utc)
        else:
            cost = LLMModelCost(
                provider_id=data.provider_id,
                model_id=data.model_id,
                display_name=data.display_name,
                input_cost_per_million=data.input_cost_per_million,
                output_cost_per_million=data.output_cost_per_million,
                is_active=data.is_active,
            )
            db.add(cost)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@router.delete("/llm/model-costs/{model_id}")
async def delete_model_cost(model_id: str, user: AuthContext = Depends(get_current_user)):
    """Delete a model cost entry."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        cost = db.query(LLMModelCost).filter(LLMModelCost.model_id == model_id).first()
        if not cost:
            raise HTTPException(404, "Model not found")
        db.delete(cost)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


# ── Usage Analytics ───────────────────────────────────────────────────────────

@router.get("/llm/usage-summary")
async def get_usage_summary(
    days: int = Query(30, ge=1, le=365),
    tenant_id: Optional[int] = Query(None),
    user: AuthContext = Depends(get_current_user),
):
    """Get aggregated LLM usage summary across all tenants or for a specific tenant."""
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = db.query(
            func.count(LLMUsageLog.id).label("total_requests"),
            func.sum(LLMUsageLog.prompt_tokens).label("total_prompt_tokens"),
            func.sum(LLMUsageLog.completion_tokens).label("total_completion_tokens"),
            func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
            func.sum(LLMUsageLog.total_cost_cents).label("total_cost_cents"),
            func.avg(LLMUsageLog.latency_ms).label("avg_latency_ms"),
            func.count(LLMUsageLog.id).filter(LLMUsageLog.success.is_(False)).label("error_count"),
        ).filter(LLMUsageLog.created_at >= since)
        
        if tenant_id:
            query = query.filter(LLMUsageLog.tenant_id == tenant_id)
        
        row = query.first()
        
        return {
            "period_days": days,
            "total_requests": row.total_requests or 0,
            "total_prompt_tokens": row.total_prompt_tokens or 0,
            "total_completion_tokens": row.total_completion_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost_cents": round(row.total_cost_cents or 0, 2),
            "total_cost_usd": round((row.total_cost_cents or 0) / 100, 4),
            "avg_latency_ms": round(row.avg_latency_ms or 0),
            "error_count": row.error_count or 0,
            "error_rate": round((row.error_count or 0) / max(row.total_requests or 1, 1) * 100, 1),
        }
    finally:
        db.close()


@router.get("/llm/usage-by-model")
async def get_usage_by_model(
    days: int = Query(30, ge=1, le=365),
    tenant_id: Optional[int] = Query(None),
    user: AuthContext = Depends(get_current_user),
):
    """Get LLM usage breakdown by model."""
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = db.query(
            LLMUsageLog.provider_id,
            LLMUsageLog.model_id,
            func.count(LLMUsageLog.id).label("requests"),
            func.sum(LLMUsageLog.total_tokens).label("tokens"),
            func.sum(LLMUsageLog.total_cost_cents).label("cost_cents"),
            func.avg(LLMUsageLog.latency_ms).label("avg_latency"),
        ).filter(
            LLMUsageLog.created_at >= since
        ).group_by(
            LLMUsageLog.provider_id, LLMUsageLog.model_id
        ).order_by(desc("cost_cents"))
        
        if tenant_id:
            query = query.filter(LLMUsageLog.tenant_id == tenant_id)
        
        rows = query.all()
        
        return [
            {
                "provider_id": r.provider_id,
                "model_id": r.model_id,
                "requests": r.requests,
                "tokens": r.tokens or 0,
                "cost_cents": round(r.cost_cents or 0, 2),
                "cost_usd": round((r.cost_cents or 0) / 100, 4),
                "avg_latency_ms": round(r.avg_latency or 0),
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/llm/usage-by-tenant")
async def get_usage_by_tenant(
    days: int = Query(30, ge=1, le=365),
    user: AuthContext = Depends(get_current_user),
):
    """Get LLM usage breakdown by tenant."""
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        rows = db.execute(text("""
            SELECT 
                l.tenant_id,
                t.company_name,
                p.name as plan_name,
                COUNT(l.id) as requests,
                COALESCE(SUM(l.total_tokens), 0) as tokens,
                COALESCE(SUM(l.total_cost_cents), 0) as cost_cents,
                ROUND(AVG(l.latency_ms)) as avg_latency
            FROM llm_usage_log l
            JOIN tenants t ON t.id = l.tenant_id
            LEFT JOIN subscriptions s ON s.tenant_id = t.id AND s.status = 'active'
            LEFT JOIN plans p ON p.id = s.plan_id
            WHERE l.created_at >= :since
            GROUP BY l.tenant_id, t.company_name, p.name
            ORDER BY cost_cents DESC
        """), {"since": since}).fetchall()
        
        return [
            {
                "tenant_id": r[0],
                "company_name": r[1],
                "plan_name": r[2] or "N/A",
                "requests": r[3],
                "tokens": r[4],
                "cost_cents": round(r[5], 2),
                "cost_usd": round(r[5] / 100, 4),
                "avg_latency_ms": r[6] or 0,
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/llm/usage-daily")
async def get_usage_daily(
    days: int = Query(30, ge=1, le=365),
    tenant_id: Optional[int] = Query(None),
    user: AuthContext = Depends(get_current_user),
):
    """Get daily LLM usage for charting."""
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        tenant_filter = "AND l.tenant_id = :tid" if tenant_id else ""
        params = {"since": since}
        if tenant_id:
            params["tid"] = tenant_id
        
        rows = db.execute(text(f"""
            SELECT 
                DATE(l.created_at) as day,
                COUNT(l.id) as requests,
                COALESCE(SUM(l.total_tokens), 0) as tokens,
                COALESCE(SUM(l.total_cost_cents), 0) as cost_cents
            FROM llm_usage_log l
            WHERE l.created_at >= :since {tenant_filter}
            GROUP BY DATE(l.created_at)
            ORDER BY day
        """), params).fetchall()
        
        return [
            {
                "date": str(r[0]),
                "requests": r[1],
                "tokens": r[2],
                "cost_cents": round(r[3], 2),
                "cost_usd": round(r[3] / 100, 4),
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/llm/recent-logs")
async def get_recent_logs(
    limit: int = Query(50, ge=1, le=500),
    tenant_id: Optional[int] = Query(None),
    user: AuthContext = Depends(get_current_user),
):
    """Get recent LLM usage log entries."""
    db = SessionLocal()
    try:
        query = db.query(LLMUsageLog).order_by(desc(LLMUsageLog.created_at)).limit(limit)
        if tenant_id:
            query = query.filter(LLMUsageLog.tenant_id == tenant_id)
        
        logs = query.all()
        
        return [
            {
                "id": l.id,
                "tenant_id": l.tenant_id,
                "user_id": l.user_id,
                "agent_name": l.agent_name,
                "provider_id": l.provider_id,
                "model_id": l.model_id,
                "prompt_tokens": l.prompt_tokens,
                "completion_tokens": l.completion_tokens,
                "total_tokens": l.total_tokens,
                "total_cost_cents": round(l.total_cost_cents, 4),
                "latency_ms": l.latency_ms,
                "success": l.success,
                "error_message": l.error_message,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    finally:
        db.close()
