"""app/gateway/routers/permissions.py — Frontend Permissions & Feature Flags (PR 4).

Endpoints:
    GET /admin/permissions
"""
from __future__ import annotations

from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user
from app.core.db import SessionLocal
from app.core.models import Plan, Subscription
from app.core.feature_gates import FeatureGate

router = APIRouter(prefix="/admin", tags=["permissions"])


class PlanSchema(BaseModel):
    slug: str
    name: str
    price_monthly_cents: int
    features: Dict[str, bool]
    limits: Dict[str, Optional[int]]

class SubscriptionSchema(BaseModel):
    has_subscription: bool
    status: str
    current_period_end: Optional[str] = None
    trial_ends_at: Optional[str] = None

class UsageSchema(BaseModel):
    messages_used: int
    messages_inbound: int
    messages_outbound: int
    members_count: int
    llm_tokens_used: int

class PermissionsResponse(BaseModel):
    role: str
    plan: Optional[PlanSchema] = None
    subscription: SubscriptionSchema
    usage: UsageSchema
    pages: Dict[str, bool]


@router.get("/permissions", response_model=PermissionsResponse)
def get_permissions(user: AuthContext = Depends(get_current_user)):
    """Return the full permission map for the current user/tenant context."""
    
    # 1. Load Feature Gate (Usage & Plan data)
    gate = FeatureGate(user.tenant_id)
    plan_data = gate._plan_data
    usage_data = gate._get_current_usage()
    
    # 2. Load Subscription Details
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.tenant_id == user.tenant_id,
            Subscription.status.in_(["active", "trialing", "past_due"])
        ).first()
        
        sub_schema = SubscriptionSchema(
            has_subscription=bool(sub),
            status=sub.status if sub else "none",
            current_period_end=sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
            trial_ends_at=sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
        )
    finally:
        db.close()
        
    # 3. Construct Plan Schema
    # Map raw plan_data keys to structured features/limits
    features = {
        k.replace("_enabled", ""): bool(v) 
        for k, v in plan_data.items() 
        if k.endswith("_enabled")
    }
    
    limits = {
        "max_members": plan_data.get("max_members"),
        "max_monthly_messages": plan_data.get("max_monthly_messages"),
        "max_channels": plan_data.get("max_channels", 1),
        "max_connectors": plan_data.get("max_connectors", 0),
    }
    
    plan_schema = PlanSchema(
        slug=str(plan_data.get("slug", "starter")),
        name=str(plan_data.get("name", "Starter")),
        price_monthly_cents=int(plan_data.get("price_monthly_cents", 0)),
        features=features,
        limits=limits
    )
    
    # 4. Construct Usage Schema
    msgs_in = usage_data.get("messages_inbound", 0)
    msgs_out = usage_data.get("messages_outbound", 0)
    usage_schema = UsageSchema(
        messages_used=msgs_in + msgs_out,
        messages_inbound=msgs_in,
        messages_outbound=msgs_out,
        members_count=usage_data.get("active_members", 0),
        llm_tokens_used=usage_data.get("llm_tokens_used", 0)
    )
    
    # 5. Calculate Page Access (Role + Feature based)
    # Default to allowed, then restrict based on features
    pages = {
        "/dashboard": True,
        "/live": True,
        "/escalations": True,
        "/analytics": features.get("advanced_analytics", False) or user.role == "system_admin", # Basic analytics usually open
        "/members": True,
        "/member-memory": features.get("memory_analyzer", False),
        "/knowledge": True,
        "/magicline": features.get("multi_source_members", False), # Legacy magicline
        "/users": user.role in ("system_admin", "tenant_admin"),
        "/audit": features.get("audit_log", False),
        "/settings/integrations": user.role in ("system_admin", "tenant_admin"),
        "/settings/prompts": features.get("custom_prompts", False),
        "/settings/billing": user.role in ("system_admin", "tenant_admin"),
        "/settings/branding": features.get("branding", False),
        "/settings/automation": features.get("automation", False),
        "/settings/account": True,
    }
    
    # Role overrides
    if user.role == "tenant_user":
        # Restrict admin pages
        for p in ["/users", "/settings/billing", "/settings/integrations", "/settings/branding"]:
            pages[p] = False

    return PermissionsResponse(
        role=user.role,
        plan=plan_schema,
        subscription=sub_schema,
        usage=usage_schema,
        pages=pages
    )
