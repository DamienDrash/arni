"""ARIIA – Plans & Addons Admin Router (S4.3).

System-Admin-only endpoints for managing subscription plans and add-on definitions.
Supports full CRUD with bidirectional Stripe synchronization.

Endpoints
---------
Plans:
    GET    /admin/plans                 → List all plans (with full details)
    POST   /admin/plans                 → Create a new plan
    PATCH  /admin/plans/{plan_id}       → Update a plan (partial)
    DELETE /admin/plans/{plan_id}       → Delete/archive a plan

Addons:
    GET    /admin/plans/addons          → List all addon definitions
    POST   /admin/plans/addons          → Create a new addon
    PATCH  /admin/plans/addons/{id}     → Update an addon
    DELETE /admin/plans/addons/{id}     → Delete/archive an addon

Sync:
    POST   /admin/plans/sync-now        → Manual full bidirectional sync
    POST   /admin/plans/sync-from-stripe → Pull from Stripe only
    POST   /admin/plans/sync-to-stripe  → Push to Stripe only
    POST   /admin/plans/cleanup         → Remove orphaned plans

Public:
    GET    /admin/plans/public          → Public plan catalog (no auth)
    GET    /admin/plans/public/addons   → Public addon catalog (no auth)
"""

from __future__ import annotations

import json
from typing import Any, Optional, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import Plan, AddonDefinition, Subscription
from app.core.billing_sync import (
    push_plan_to_stripe,
    push_addon_to_stripe,
    sync_plans_from_stripe,
    sync_addons_from_stripe,
    full_bidirectional_sync,
    get_stripe_client,
    is_stripe_configured,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class PlanCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    price_monthly_cents: int = 0
    price_yearly_cents: Optional[int] = None
    trial_days: int = 0
    display_order: int = 0
    is_highlighted: bool = False
    is_active: bool = True
    is_public: bool = True
    features_json: Optional[str] = None

    # Limits
    max_members: Optional[int] = 500
    max_monthly_messages: Optional[int] = 500
    max_channels: int = 1
    max_connectors: int = 0
    ai_tier: str = "basic"
    monthly_tokens: int = 100000

    # Channel toggles
    whatsapp_enabled: bool = True
    telegram_enabled: bool = False
    sms_enabled: bool = False
    email_channel_enabled: bool = False
    voice_enabled: bool = False
    instagram_enabled: bool = False
    facebook_enabled: bool = False
    google_business_enabled: bool = False

    # Feature toggles
    memory_analyzer_enabled: bool = False
    custom_prompts_enabled: bool = False
    advanced_analytics_enabled: bool = False
    branding_enabled: bool = False
    audit_log_enabled: bool = False
    automation_enabled: bool = False
    api_access_enabled: bool = False
    multi_source_members_enabled: bool = False
    churn_prediction_enabled: bool = False
    vision_ai_enabled: bool = False
    white_label_enabled: bool = False
    sla_guarantee_enabled: bool = False
    on_premise_enabled: bool = False

    # Overage
    overage_conversation_cents: int = 5
    overage_user_cents: int = 1500
    overage_connector_cents: int = 4900
    overage_channel_cents: int = 2900


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly_cents: Optional[int] = None
    price_yearly_cents: Optional[int] = None
    trial_days: Optional[int] = None
    display_order: Optional[int] = None
    is_highlighted: Optional[bool] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    features_json: Optional[str] = None

    # Limits
    max_members: Optional[int] = Field(None, description="NULL = unlimited")
    max_monthly_messages: Optional[int] = Field(None, description="NULL = unlimited")
    max_channels: Optional[int] = None
    max_connectors: Optional[int] = None
    ai_tier: Optional[str] = None
    monthly_tokens: Optional[int] = None

    # Channel toggles
    whatsapp_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    email_channel_enabled: Optional[bool] = None
    voice_enabled: Optional[bool] = None
    instagram_enabled: Optional[bool] = None
    facebook_enabled: Optional[bool] = None
    google_business_enabled: Optional[bool] = None

    # Feature toggles
    memory_analyzer_enabled: Optional[bool] = None
    custom_prompts_enabled: Optional[bool] = None
    advanced_analytics_enabled: Optional[bool] = None
    branding_enabled: Optional[bool] = None
    audit_log_enabled: Optional[bool] = None
    automation_enabled: Optional[bool] = None
    api_access_enabled: Optional[bool] = None
    multi_source_members_enabled: Optional[bool] = None
    churn_prediction_enabled: Optional[bool] = None
    vision_ai_enabled: Optional[bool] = None
    white_label_enabled: Optional[bool] = None
    sla_guarantee_enabled: Optional[bool] = None
    on_premise_enabled: Optional[bool] = None

    # Overage
    overage_conversation_cents: Optional[int] = None
    overage_user_cents: Optional[int] = None
    overage_connector_cents: Optional[int] = None
    overage_channel_cents: Optional[int] = None


class AddonCreate(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    price_monthly_cents: int = 0
    features_json: Optional[str] = None
    is_active: bool = True
    display_order: int = 0


class AddonUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    price_monthly_cents: Optional[int] = None
    features_json: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _plan_to_dict(plan: Plan) -> dict[str, Any]:
    """Serialize a Plan ORM object to a dict for API response."""
    features_list = []
    if plan.features_json:
        try:
            features_list = json.loads(plan.features_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": plan.id,
        "name": plan.name,
        "slug": plan.slug,
        "description": plan.description,
        "stripe_product_id": plan.stripe_product_id,
        "stripe_price_id": plan.stripe_price_id,
        "stripe_price_yearly_id": getattr(plan, "stripe_price_yearly_id", None),
        "price_monthly_cents": plan.price_monthly_cents,
        "price_yearly_cents": getattr(plan, "price_yearly_cents", None),
        "trial_days": getattr(plan, "trial_days", 0),
        "display_order": getattr(plan, "display_order", 0),
        "is_highlighted": getattr(plan, "is_highlighted", False),
        "is_active": plan.is_active,
        "is_public": getattr(plan, "is_public", True),
        "features_json": plan.features_json,
        "features_display": features_list,
        # Limits
        "max_members": plan.max_members,
        "max_monthly_messages": plan.max_monthly_messages,
        "max_channels": plan.max_channels,
        "max_connectors": plan.max_connectors,
        "ai_tier": plan.ai_tier,
        "monthly_tokens": plan.monthly_tokens,
        # Channel toggles
        "whatsapp_enabled": plan.whatsapp_enabled,
        "telegram_enabled": plan.telegram_enabled,
        "sms_enabled": plan.sms_enabled,
        "email_channel_enabled": plan.email_channel_enabled,
        "voice_enabled": plan.voice_enabled,
        "instagram_enabled": plan.instagram_enabled,
        "facebook_enabled": plan.facebook_enabled,
        "google_business_enabled": plan.google_business_enabled,
        # Feature toggles
        "memory_analyzer_enabled": plan.memory_analyzer_enabled,
        "custom_prompts_enabled": plan.custom_prompts_enabled,
        "advanced_analytics_enabled": plan.advanced_analytics_enabled,
        "branding_enabled": plan.branding_enabled,
        "audit_log_enabled": plan.audit_log_enabled,
        "automation_enabled": plan.automation_enabled,
        "api_access_enabled": plan.api_access_enabled,
        "multi_source_members_enabled": plan.multi_source_members_enabled,
        "churn_prediction_enabled": plan.churn_prediction_enabled,
        "vision_ai_enabled": plan.vision_ai_enabled,
        "white_label_enabled": plan.white_label_enabled,
        "sla_guarantee_enabled": plan.sla_guarantee_enabled,
        "on_premise_enabled": plan.on_premise_enabled,
        # Overage
        "overage_conversation_cents": plan.overage_conversation_cents,
        "overage_user_cents": plan.overage_user_cents,
        "overage_connector_cents": plan.overage_connector_cents,
        "overage_channel_cents": plan.overage_channel_cents,
        # Timestamps
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if getattr(plan, "updated_at", None) else None,
    }


def _addon_to_dict(addon: AddonDefinition) -> dict[str, Any]:
    """Serialize an AddonDefinition ORM object to a dict."""
    features_list = []
    if addon.features_json:
        try:
            features_list = json.loads(addon.features_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": addon.id,
        "slug": addon.slug,
        "name": addon.name,
        "description": addon.description,
        "category": addon.category,
        "icon": addon.icon,
        "price_monthly_cents": addon.price_monthly_cents,
        "stripe_product_id": addon.stripe_product_id,
        "stripe_price_id": addon.stripe_price_id,
        "features_json": addon.features_json,
        "features_display": features_list,
        "is_active": addon.is_active,
        "display_order": addon.display_order,
        "created_at": addon.created_at.isoformat() if addon.created_at else None,
        "updated_at": addon.updated_at.isoformat() if addon.updated_at else None,
    }


# ── Plan CRUD ────────────────────────────────────────────────────────────────

@router.get("")
async def list_all_plans(user: AuthContext = Depends(get_current_user)):
    """List all plans with full details (system_admin only)."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        plans = db.query(Plan).order_by(Plan.display_order.asc(), Plan.price_monthly_cents.asc()).all()
        return [_plan_to_dict(p) for p in plans]
    finally:
        db.close()


@router.post("")
async def create_plan(data: PlanCreate, user: AuthContext = Depends(get_current_user)):
    """Create a new plan and optionally push to Stripe."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        if db.query(Plan).filter(Plan.slug == data.slug).first():
            raise HTTPException(status_code=400, detail=f"Plan mit Slug '{data.slug}' existiert bereits")

        plan = Plan(**data.model_dump())
        db.add(plan)
        db.commit()
        db.refresh(plan)

        # Auto-push to Stripe if configured
        if is_stripe_configured():
            await push_plan_to_stripe(db, plan)

        return _plan_to_dict(plan)
    finally:
        db.close()


@router.patch("/{plan_id}")
async def update_plan(plan_id: int, data: PlanUpdate, user: AuthContext = Depends(get_current_user)):
    """Update a plan (partial update) and sync to Stripe."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan nicht gefunden")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(plan, key, value)

        db.commit()
        db.refresh(plan)

        # Auto-push to Stripe if configured
        if is_stripe_configured():
            await push_plan_to_stripe(db, plan)

        return _plan_to_dict(plan)
    finally:
        db.close()


@router.delete("/{plan_id}")
async def delete_plan(plan_id: int, user: AuthContext = Depends(get_current_user)):
    """Delete a plan. Archives in Stripe if linked."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan nicht gefunden")

        # Check if any tenant is using this plan
        active_subs = db.query(Subscription).filter(
            Subscription.plan_id == plan_id,
            Subscription.status.in_(["active", "trialing"]),
        ).count()
        if active_subs > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Plan wird von {active_subs} aktiven Abonnements genutzt. Bitte zuerst migrieren.",
            )

        # Archive in Stripe
        s = get_stripe_client()
        if s and plan.stripe_product_id:
            try:
                s.Product.modify(plan.stripe_product_id, active=False)
            except Exception as e:
                logger.warning("billing.stripe_archive_failed", error=str(e))

        db.delete(plan)
        db.commit()
        return {"status": "deleted", "plan_id": plan_id}
    finally:
        db.close()


# ── Addon CRUD ───────────────────────────────────────────────────────────────

@router.get("/addons")
async def list_all_addons(user: AuthContext = Depends(get_current_user)):
    """List all addon definitions (system_admin only)."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        addons = db.query(AddonDefinition).order_by(
            AddonDefinition.display_order.asc(),
            AddonDefinition.name.asc(),
        ).all()
        return [_addon_to_dict(a) for a in addons]
    finally:
        db.close()


@router.post("/addons")
async def create_addon(data: AddonCreate, user: AuthContext = Depends(get_current_user)):
    """Create a new addon definition and push to Stripe."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        if db.query(AddonDefinition).filter(AddonDefinition.slug == data.slug).first():
            raise HTTPException(status_code=400, detail=f"Addon mit Slug '{data.slug}' existiert bereits")

        addon = AddonDefinition(**data.model_dump())
        db.add(addon)
        db.commit()
        db.refresh(addon)

        if is_stripe_configured():
            await push_addon_to_stripe(db, addon)

        return _addon_to_dict(addon)
    finally:
        db.close()


@router.patch("/addons/{addon_id}")
async def update_addon(addon_id: int, data: AddonUpdate, user: AuthContext = Depends(get_current_user)):
    """Update an addon definition and sync to Stripe."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        addon = db.query(AddonDefinition).filter(AddonDefinition.id == addon_id).first()
        if not addon:
            raise HTTPException(status_code=404, detail="Addon nicht gefunden")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(addon, key, value)

        db.commit()
        db.refresh(addon)

        if is_stripe_configured():
            await push_addon_to_stripe(db, addon)

        return _addon_to_dict(addon)
    finally:
        db.close()


@router.delete("/addons/{addon_id}")
async def delete_addon(addon_id: int, user: AuthContext = Depends(get_current_user)):
    """Delete an addon definition. Archives in Stripe if linked."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        addon = db.query(AddonDefinition).filter(AddonDefinition.id == addon_id).first()
        if not addon:
            raise HTTPException(status_code=404, detail="Addon nicht gefunden")

        s = get_stripe_client()
        if s and addon.stripe_product_id:
            try:
                s.Product.modify(addon.stripe_product_id, active=False)
            except Exception as e:
                logger.warning("billing.stripe_addon_archive_failed", error=str(e))

        db.delete(addon)
        db.commit()
        return {"status": "deleted", "addon_id": addon_id}
    finally:
        db.close()


# ── Sync Endpoints ───────────────────────────────────────────────────────────

@router.post("/sync-now")
async def trigger_full_sync(user: AuthContext = Depends(get_current_user)):
    """Full bidirectional sync: push local → Stripe, then pull Stripe → local."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        result = await full_bidirectional_sync(db)
        return {"status": "ok", "result": result}
    finally:
        db.close()


@router.post("/sync-from-stripe")
async def trigger_sync_from_stripe(user: AuthContext = Depends(get_current_user)):
    """Pull all plan and addon data from Stripe into local DB."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        plans_result = await sync_plans_from_stripe(db)
        addons_result = await sync_addons_from_stripe(db)
        return {"status": "ok", "plans": plans_result, "addons": addons_result}
    finally:
        db.close()


@router.post("/sync-to-stripe")
async def trigger_sync_to_stripe(user: AuthContext = Depends(get_current_user)):
    """Push all local plans and addons to Stripe."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        plans = db.query(Plan).filter(Plan.is_active.is_(True)).all()
        addons = db.query(AddonDefinition).filter(AddonDefinition.is_active.is_(True)).all()

        plans_ok = 0
        addons_ok = 0

        for plan in plans:
            if await push_plan_to_stripe(db, plan):
                plans_ok += 1

        for addon in addons:
            if await push_addon_to_stripe(db, addon):
                addons_ok += 1

        return {"status": "ok", "plans_pushed": plans_ok, "addons_pushed": addons_ok}
    finally:
        db.close()


@router.post("/cleanup")
async def cleanup_orphaned_plans(user: AuthContext = Depends(get_current_user)):
    """Remove all plans that have no Stripe Product ID and no active subscriptions."""
    require_role(user, {"system_admin"})
    db = SessionLocal()
    try:
        orphaned = db.query(Plan).filter(
            Plan.stripe_product_id.is_(None),
            Plan.stripe_price_id.is_(None),
        ).all()

        deleted = 0
        skipped = 0
        for plan in orphaned:
            active_subs = db.query(Subscription).filter(
                Subscription.plan_id == plan.id,
                Subscription.status.in_(["active", "trialing"]),
            ).count()
            if active_subs == 0:
                db.delete(plan)
                deleted += 1
            else:
                skipped += 1

        db.commit()
        return {"status": "ok", "deleted_count": deleted, "skipped_count": skipped}
    finally:
        db.close()


# ── Public Endpoints (No Auth) ───────────────────────────────────────────────

@router.get("/public")
async def list_public_plans():
    """Public plan catalog for landing page and pricing page. No auth required."""
    db = SessionLocal()
    try:
        plans = db.query(Plan).filter(
            Plan.is_active.is_(True),
            Plan.is_public.is_(True),
        ).order_by(Plan.display_order.asc(), Plan.price_monthly_cents.asc()).all()

        # Deduplicate by slug — keep first occurrence (by display_order)
        seen_slugs = set()
        unique_plans = []
        for p in plans:
            if p.slug in seen_slugs:
                continue
            seen_slugs.add(p.slug)
            unique_plans.append(p)

        result = []
        for p in unique_plans:
            features_list = []
            if p.features_json:
                try:
                    features_list = json.loads(p.features_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            result.append({
                "slug": p.slug,
                "name": p.name,
                "description": p.description,
                "price_monthly_cents": p.price_monthly_cents,
                "price_yearly_cents": getattr(p, "price_yearly_cents", None),
                "trial_days": getattr(p, "trial_days", 0),
                "is_highlighted": getattr(p, "is_highlighted", False),
                "max_members": p.max_members,
                "max_monthly_messages": p.max_monthly_messages,
                "max_channels": p.max_channels,
                "max_connectors": p.max_connectors,
                "features": features_list,
                # Channel info for display
                "channels": {
                    "whatsapp": p.whatsapp_enabled,
                    "telegram": p.telegram_enabled,
                    "sms": p.sms_enabled,
                    "email": p.email_channel_enabled,
                    "voice": p.voice_enabled,
                    "instagram": p.instagram_enabled,
                    "facebook": p.facebook_enabled,
                    "google_business": p.google_business_enabled,
                },
                # Feature flags for display
                "feature_flags": {
                    "memory_analyzer": p.memory_analyzer_enabled,
                    "custom_prompts": p.custom_prompts_enabled,
                    "advanced_analytics": p.advanced_analytics_enabled,
                    "branding": p.branding_enabled,
                    "audit_log": p.audit_log_enabled,
                    "automation": p.automation_enabled,
                    "api_access": p.api_access_enabled,
                    "churn_prediction": p.churn_prediction_enabled,
                    "vision_ai": p.vision_ai_enabled,
                    "white_label": p.white_label_enabled,
                },
            })

        return result
    finally:
        db.close()


@router.get("/public/addons")
async def list_public_addons():
    """Public addon catalog. No auth required."""
    db = SessionLocal()
    try:
        addons = db.query(AddonDefinition).filter(
            AddonDefinition.is_active.is_(True),
        ).order_by(AddonDefinition.display_order.asc()).all()

        return [
            {
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "category": a.category,
                "icon": a.icon,
                "price_monthly_cents": a.price_monthly_cents,
                "stripe_price_id": a.stripe_price_id,
            }
            for a in addons
        ]
    finally:
        db.close()
