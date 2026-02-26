"""app/gateway/routers/permissions.py — Gold Standard Permission Mapping.

Returns the complete permission set for the current user including:
- Plan features & limits (from DB, dynamically)
- Active addons for the tenant
- Usage data
- Page-level access control
- Channel availability
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user
from app.core.models import Plan, Subscription, UsageRecord, StudioMember, TenantAddon, AddonDefinition

router = APIRouter(prefix="/admin", tags=["permissions"])


def _build_features_dict(plan: Plan | None) -> dict[str, bool]:
    """Build a complete features dict from a Plan object."""
    if not plan:
        return {
            "advanced_analytics": False,
            "multi_source_members": True,
            "memory_analyzer": False,
            "custom_prompts": False,
            "white_label": False,
            "audit_log": False,
            "vision_ai": False,
            "churn_prediction": False,
            "automation": False,
            "api_access": False,
            "branding": False,
            # Channels as features
            "whatsapp": True,
            "telegram": False,
            "sms": False,
            "email_channel": False,
            "voice": False,
            "instagram": False,
            "facebook": False,
            "google_business": False,
            "sla_guarantee": False,
            "on_premise": False,
        }

    return {
        "advanced_analytics": getattr(plan, "advanced_analytics_enabled", False),
        "multi_source_members": getattr(plan, "multi_source_members_enabled", True),
        "memory_analyzer": getattr(plan, "memory_analyzer_enabled", False),
        "custom_prompts": getattr(plan, "custom_prompts_enabled", False),
        "white_label": getattr(plan, "white_label_enabled", False),
        "audit_log": getattr(plan, "audit_log_enabled", False),
        "vision_ai": getattr(plan, "vision_ai_enabled", False),
        "churn_prediction": getattr(plan, "churn_prediction_enabled", False),
        "automation": getattr(plan, "automation_enabled", False),
        "api_access": getattr(plan, "api_access_enabled", False),
        "branding": getattr(plan, "branding_enabled", False),
        # Channels as features
        "whatsapp": getattr(plan, "whatsapp_enabled", True),
        "telegram": getattr(plan, "telegram_enabled", False),
        "sms": getattr(plan, "sms_enabled", False),
        "email_channel": getattr(plan, "email_channel_enabled", False),
        "voice": getattr(plan, "voice_enabled", False),
        "instagram": getattr(plan, "instagram_enabled", False),
        "facebook": getattr(plan, "facebook_enabled", False),
        "google_business": getattr(plan, "google_business_enabled", False),
        "sla_guarantee": getattr(plan, "sla_guarantee_enabled", False),
        "on_premise": getattr(plan, "on_premise_enabled", False),
    }


def _build_limits_dict(plan: Plan | None) -> dict[str, int | None]:
    """Build limits dict from a Plan object."""
    if not plan:
        return {
            "max_members": 500,
            "max_monthly_messages": 500,
            "max_channels": 1,
            "max_connectors": 0,
        }
    return {
        "max_members": getattr(plan, "max_members", 500),
        "max_monthly_messages": getattr(plan, "max_monthly_messages", 500),
        "max_channels": getattr(plan, "max_channels", 1),
        "max_connectors": getattr(plan, "max_connectors", 0),
    }


def _get_active_addons(db: Session, tenant_id: int) -> list[dict]:
    """Return list of active addons for the tenant."""
    tenant_addons = db.query(TenantAddon).filter(
        TenantAddon.tenant_id == tenant_id,
        TenantAddon.status == "active",
    ).all()

    result = []
    for ta in tenant_addons:
        addon_def = db.query(AddonDefinition).filter(
            AddonDefinition.slug == ta.addon_slug,
            AddonDefinition.is_active.is_(True),
        ).first()

        addon_info = {
            "slug": ta.addon_slug,
            "name": addon_def.name if addon_def else ta.addon_slug,
            "description": addon_def.description if addon_def else None,
            "category": addon_def.category if addon_def else None,
            "quantity": ta.quantity,
            "status": ta.status,
        }

        # Parse addon features_json to extend tenant capabilities
        if addon_def and addon_def.features_json:
            try:
                addon_info["features"] = json.loads(addon_def.features_json)
            except (json.JSONDecodeError, TypeError):
                addon_info["features"] = []

        result.append(addon_info)

    return result


def _get_features_display(plan: Plan | None) -> list[str]:
    """Get the display features list from plan's features_json."""
    if not plan:
        return []
    features_json = getattr(plan, "features_json", None)
    if features_json:
        try:
            return json.loads(features_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return []


@router.get("/permissions")
async def get_permissions(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Gold Standard Permission Mapping.
    System Admins receive absolute access ('God Mode').
    Tenants are restricted by their subscription plan + active addons.
    """
    is_sys = user.role == "system_admin"

    # 1. Base Data
    sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first() if sub else None

    # 2. Active Addons for this tenant
    active_addons = _get_active_addons(db, user.tenant_id) if not is_sys else []

    # 3. Build permission response
    if is_sys:
        # God Mode for System Admins
        features_data = {k: True for k in _build_features_dict(None).keys()}
        limits_data = {
            "max_members": None,
            "max_monthly_messages": None,
            "max_channels": 9999,
            "max_connectors": 9999,
        }
        plan_data = {
            "slug": "system_admin",
            "name": "Platform Administrator",
            "description": "Vollzugriff auf alle Funktionen",
            "features": features_data,
            "limits": limits_data,
            "ai_tier": "unlimited",
            "features_display": [],
        }
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
            "/health": True,
            "/revenue": True,
            "/settings/ai": True,
            "/campaigns": True,
        }
    else:
        # Standard SaaS logic for Tenants
        features_data = _build_features_dict(plan)
        limits_data = _build_limits_dict(plan)

        # Extend features based on active addons
        # Addons can unlock additional features (e.g., voice_pipeline addon enables voice)
        addon_feature_map = {
            "voice_pipeline": {"voice": True},
            "vision_ai": {"vision_ai": True},
            "churn_prediction": {"churn_prediction": True},
            "white_label": {"white_label": True},
            "extra_channel": {},  # Handled via limits
            "advanced_analytics": {"advanced_analytics": True},
        }
        for addon in active_addons:
            slug = addon["slug"]
            if slug in addon_feature_map:
                for feat_key, feat_val in addon_feature_map[slug].items():
                    features_data[feat_key] = feat_val

        plan_data = {
            "slug": plan.slug if plan else "starter",
            "name": plan.name if plan else "Starter",
            "description": getattr(plan, "description", None) if plan else None,
            "features": features_data,
            "limits": limits_data,
            "ai_tier": getattr(plan, "ai_tier", "basic") if plan else "basic",
            "features_display": _get_features_display(plan),
        }

        # Page access based on plan features
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
            "/settings/integrations": features_data.get("api_access", False) or (plan and plan.slug not in ("starter",)),
            "/settings/prompts": features_data.get("custom_prompts", False),
            "/settings/branding": features_data.get("branding", False),
            "/settings/automation": features_data.get("automation", False),
            "/analytics": features_data.get("advanced_analytics", False),
            "/member-memory": features_data.get("memory_analyzer", False),
            "/audit": features_data.get("audit_log", False),
            # System Admin only
            "/tenants": False,
            "/plans": False,
            "/health": False,
            "/revenue": False,
            "/settings/ai": True,
            "/campaigns": True,
        }

    # 4. Usage Data
    now = datetime.now(timezone.utc)
    usage_rec = db.query(UsageRecord).filter(
        UsageRecord.tenant_id == user.tenant_id,
        UsageRecord.period_year == now.year,
        UsageRecord.period_month == now.month,
    ).first()
    members_count = db.query(StudioMember).filter(
        StudioMember.tenant_id == user.tenant_id
    ).count()

    # 5. Overage info
    overage_data = None
    if plan and not is_sys:
        overage_data = {
            "conversation_cents": getattr(plan, "overage_conversation_cents", 5),
            "user_cents": getattr(plan, "overage_user_cents", 1500),
            "connector_cents": getattr(plan, "overage_connector_cents", 4900),
            "channel_cents": getattr(plan, "overage_channel_cents", 2900),
        }

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
        "pages": pages_data,
        "addons": active_addons,
        "overage": overage_data,
    }
