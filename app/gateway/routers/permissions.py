from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user
from app.core.models import Plan, Subscription, UsageRecord, StudioMember
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["permissions"])

@router.get("/permissions")
async def get_permissions(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gold Standard Permission Mapping.
    System Admins receive absolute access ('God Mode').
    Tenants are restricted by their subscription plan.
    """
    is_sys = user.role == "system_admin"
    
    # 1. Base Data
    sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first() if sub else None
    
    # 2. Gott-Modus Logik für System-Admins
    if is_sys:
        # Virtueller "God-Mode" Plan
        plan_data = {
            "slug": "system_admin",
            "name": "Platform Administrator",
            "features": {
                "advanced_analytics": True,
                "multi_source_members": True,
                "memory_analyzer": True,
                "custom_prompts": True,
                "white_label": True,
                "audit_log": True,
                "vision_ai": True,
                "churn_prediction": True,
                "automation": True,
                "api_access": True,
                "voice": True,
                "whatsapp": True,
                "telegram": True,
                "branding": True
            },
            "limits": {
                "max_members": None, # Unendlich
                "max_monthly_messages": None,
                "max_channels": 9999,
                "max_connectors": 9999,
            }
        }
        # Alle Seiten für Admins offen
        pages_data = {
            "/dashboard": True,
            "/tenants": True,
            "/users": True,
            "/members": True,
            "/knowledge": True,
            "/member-memory": True,
            "/system-prompt": True,
            "/magicline": True,
            "/escalations": True,
            "/live": True,
            "/analytics": True,
            "/plans": True,
            "/audit": True,
            "/settings": True,
            "/settings/billing": True,
            "/settings/branding": True,
            "/settings/automation": True,
            "/settings/integrations": True,
            "/health": True
        }
    else:
        # Standard SaaS-Logik für normale Tenants
        plan_data = {
            "slug": plan.slug if plan else "starter",
            "name": plan.name if plan else "Starter",
            "features": {
                "advanced_analytics": getattr(plan, "advanced_analytics_enabled", False),
                "multi_source_members": getattr(plan, "multi_source_members_enabled", True),
                "memory_analyzer": getattr(plan, "memory_analyzer_enabled", False),
                "custom_prompts": getattr(plan, "custom_prompts_enabled", False),
                "white_label": getattr(plan, "white_label_enabled", False),
                "audit_log": getattr(plan, "audit_log_enabled", False),
                "vision_ai": getattr(plan, "vision_ai_enabled", False),
                "churn_prediction": getattr(plan, "churn_prediction_enabled", False),
            },
            "limits": {
                "max_members": getattr(plan, "max_members", 500),
                "max_monthly_messages": getattr(plan, "max_monthly_messages", 500),
                "max_channels": getattr(plan, "max_channels", 1),
                "max_connectors": getattr(plan, "max_connectors", 0),
            }
        }
        pages_data = {
            "/dashboard": True,
            "/live": True,
            "/escalations": True,
            "/members": True,
            "/knowledge": True,
            "/users": True,
            "/settings": True,
            "/settings/billing": True,
            "/settings/account": True,
            "/tenants": False, # Nur System Admin
            "/plans": False,   # Nur System Admin
            "/health": False   # Nur System Admin
        }

    # 3. Usage Data
    now = datetime.now()
    usage_rec = db.query(UsageRecord).filter(
        UsageRecord.tenant_id == user.tenant_id,
        UsageRecord.period_year == now.year,
        UsageRecord.period_month == now.month
    ).first()
    members_count = db.query(StudioMember).filter(StudioMember.tenant_id == user.tenant_id).count()

    return {
        "role": user.role,
        "plan": plan_data,
        "subscription": {
            "has_subscription": sub is not None or is_sys,
            "status": sub.status if sub else "active",
            "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        },
        "usage": {
            "messages_used": (usage_rec.messages_inbound + usage_rec.messages_outbound) if usage_rec else 0,
            "messages_inbound": usage_rec.messages_inbound if usage_rec else 0,
            "messages_outbound": usage_rec.messages_outbound if usage_rec else 0,
            "members_count": members_count,
            "llm_tokens_used": usage_rec.llm_tokens_used if usage_rec else 0,
        },
        "pages": pages_data
    }
