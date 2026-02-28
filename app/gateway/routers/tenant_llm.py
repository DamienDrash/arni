"""app/gateway/routers/tenant_llm.py — Tenant-level LLM Provider & Token Management.

Endpoints (prefix /admin/tenant/llm):
    GET  /providers/available       → Available providers/models for tenant's plan
    GET  /configs                   → Tenant's current LLM configurations
    POST /configs                   → Add/update a LLM config
    DELETE /configs/{config_id}     → Remove a LLM config
    POST /configs/{config_id}/default → Set as default
    GET  /token-usage               → Token usage + remaining + progress
    POST /token-purchase            → Purchase additional tokens via Stripe
    GET  /token-packages            → Available token packages
"""
from __future__ import annotations

import json as _json
import structlog
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import (
    Plan, Subscription, TenantLLMConfig, UsageRecord, TokenPurchase, Tenant,
)
from app.gateway.persistence import persistence

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/tenant/llm", tags=["tenant-llm"])

# All supported providers (system-wide catalog)
ALL_PROVIDERS = [
    {
        "id": "openai", "name": "OpenAI",
        "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini"],
        "tier": "standard",
    },
    {
        "id": "anthropic", "name": "Anthropic",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
        "tier": "premium",
    },
    {
        "id": "mistral", "name": "Mistral AI",
        "models": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
        "tier": "standard",
    },
    {
        "id": "groq", "name": "Groq",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"],
        "tier": "basic",
    },
    {
        "id": "gemini", "name": "Google Gemini",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
        "tier": "standard",
    },
    {
        "id": "xai", "name": "xAI (Grok)",
        "models": ["grok-4-1-fast-non-reasoning", "grok-3-mini"],
        "tier": "standard",
    },
]
# Token packages for purchase
TOKEN_PACKAGES = [
    {"id": "tokens_50k", "name": "50K Tokens", "tokens": 50000, "price_cents": 500, "popular": False},
    {"id": "tokens_200k", "name": "200K Tokens", "tokens": 200000, "price_cents": 1500, "popular": True},
    {"id": "tokens_500k", "name": "500K Tokens", "tokens": 500000, "price_cents": 3000, "popular": False},
    {"id": "tokens_1m", "name": "1M Tokens", "tokens": 1000000, "price_cents": 5000, "popular": False},
    {"id": "tokens_5m", "name": "5M Tokens", "tokens": 5000000, "price_cents": 20000, "popular": False},
]


def _get_tenant_plan(db, tenant_id: int) -> Optional[Plan]:
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id,
        Subscription.status.in_(["active", "trialing"]),
    ).first()
    if sub:
        return db.query(Plan).filter(Plan.id == sub.plan_id).first()
    return None


@router.get("/providers/available")
async def list_available_providers(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return available LLM providers and models based on tenant's plan."""
    require_role(user, {"tenant_admin", "system_admin"})
    db = SessionLocal()
    try:
        plan = _get_tenant_plan(db, user.tenant_id)
        if not plan:
            return {"providers": [], "plan_name": "No Plan", "plan_slug": "none"}

        # Parse allowed providers from plan
        allowed_providers = None
        if plan.allowed_llm_providers_json:
            try:
                allowed_providers = _json.loads(plan.allowed_llm_providers_json)
            except (ValueError, TypeError):
                pass

        # Filter providers based on plan
        available = []
        for p in ALL_PROVIDERS:
            if allowed_providers is None or p["id"] in allowed_providers:
                # Check if system admin has configured this provider's API key
                has_key = bool(persistence.get_setting(f"platform_llm_key_{p['id']}", "", tenant_id=1))
                available.append({
                    **p,
                    "available": has_key,
                    "reason": None if has_key else "API-Key nicht vom System-Admin konfiguriert",
                })
            else:
                available.append({
                    **p,
                    "available": False,
                    "reason": f"Nicht in Ihrem {plan.name}-Plan enthalten. Bitte upgraden.",
                    "locked_by_plan": True,
                })

        return {
            "providers": available,
            "plan_name": plan.name,
            "plan_slug": plan.slug,
            "ai_tier": plan.ai_tier,
            "monthly_tokens": plan.monthly_tokens,
        }
    finally:
        db.close()


@router.get("/configs")
async def list_configs(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Return tenant's current LLM configurations."""
    require_role(user, {"tenant_admin", "system_admin"})
    db = SessionLocal()
    try:
        configs = db.query(TenantLLMConfig).filter(
            TenantLLMConfig.tenant_id == user.tenant_id,
            TenantLLMConfig.is_active.is_(True),
        ).all()

        return [{
            "id": c.id,
            "provider_id": c.provider_id,
            "provider_name": c.provider_name,
            "model_id": c.model_id,
            "is_default": c.is_default,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        } for c in configs]
    finally:
        db.close()


class LLMConfigRequest(BaseModel):
    provider_id: str
    model_id: str


@router.post("/configs")
async def add_config(
    req: LLMConfigRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Add a new LLM provider/model configuration."""
    require_role(user, {"tenant_admin", "system_admin"})
    db = SessionLocal()
    try:
        plan = _get_tenant_plan(db, user.tenant_id)
        if not plan:
            raise HTTPException(status_code=402, detail="Kein aktiver Plan gefunden.")

        # Validate provider is allowed for this plan
        allowed_providers = None
        if plan.allowed_llm_providers_json:
            try:
                allowed_providers = _json.loads(plan.allowed_llm_providers_json)
            except (ValueError, TypeError):
                pass

        if allowed_providers and req.provider_id not in allowed_providers:
            raise HTTPException(
                status_code=402,
                detail=f"Provider '{req.provider_id}' ist nicht in Ihrem {plan.name}-Plan enthalten.",
            )

        # Check if system admin has configured this provider
        has_key = bool(persistence.get_setting(f"platform_llm_key_{req.provider_id}", "", tenant_id=1))
        if not has_key:
            raise HTTPException(
                status_code=422,
                detail=f"Provider '{req.provider_id}' ist noch nicht vom System-Admin konfiguriert.",
            )

        # Find provider name
        provider_info = next((p for p in ALL_PROVIDERS if p["id"] == req.provider_id), None)
        provider_name = provider_info["name"] if provider_info else req.provider_id

        # Check for duplicate
        existing = db.query(TenantLLMConfig).filter(
            TenantLLMConfig.tenant_id == user.tenant_id,
            TenantLLMConfig.provider_id == req.provider_id,
            TenantLLMConfig.model_id == req.model_id,
            TenantLLMConfig.is_active.is_(True),
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Diese Konfiguration existiert bereits.")

        # If no configs exist yet, make this the default
        has_any = db.query(TenantLLMConfig).filter(
            TenantLLMConfig.tenant_id == user.tenant_id,
            TenantLLMConfig.is_active.is_(True),
        ).first()

        config = TenantLLMConfig(
            tenant_id=user.tenant_id,
            provider_id=req.provider_id,
            provider_name=provider_name,
            model_id=req.model_id,
            is_default=not has_any,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

        return {
            "id": config.id,
            "provider_id": config.provider_id,
            "provider_name": config.provider_name,
            "model_id": config.model_id,
            "is_default": config.is_default,
        }
    finally:
        db.close()


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Remove a LLM configuration."""
    require_role(user, {"tenant_admin", "system_admin"})
    db = SessionLocal()
    try:
        config = db.query(TenantLLMConfig).filter(
            TenantLLMConfig.id == config_id,
            TenantLLMConfig.tenant_id == user.tenant_id,
        ).first()
        if not config:
            raise HTTPException(status_code=404, detail="Konfiguration nicht gefunden.")

        was_default = config.is_default
        config.is_active = False
        db.commit()

        # If this was the default, set another one as default
        if was_default:
            next_config = db.query(TenantLLMConfig).filter(
                TenantLLMConfig.tenant_id == user.tenant_id,
                TenantLLMConfig.is_active.is_(True),
            ).first()
            if next_config:
                next_config.is_default = True
                db.commit()

        return {"status": "ok"}
    finally:
        db.close()


@router.post("/configs/{config_id}/default")
async def set_default_config(
    config_id: int,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Set a LLM configuration as default."""
    require_role(user, {"tenant_admin", "system_admin"})
    db = SessionLocal()
    try:
        config = db.query(TenantLLMConfig).filter(
            TenantLLMConfig.id == config_id,
            TenantLLMConfig.tenant_id == user.tenant_id,
            TenantLLMConfig.is_active.is_(True),
        ).first()
        if not config:
            raise HTTPException(status_code=404, detail="Konfiguration nicht gefunden.")

        # Unset all defaults for this tenant
        db.query(TenantLLMConfig).filter(
            TenantLLMConfig.tenant_id == user.tenant_id,
        ).update({"is_default": False})

        config.is_default = True
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@router.get("/token-usage")
async def get_token_usage(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return token usage, limits, and progress for the current tenant."""
    require_role(user, {"tenant_admin", "tenant_user", "system_admin"})
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        plan = _get_tenant_plan(db, user.tenant_id)

        usage = db.query(UsageRecord).filter(
            UsageRecord.tenant_id == user.tenant_id,
            UsageRecord.period_year == now.year,
            UsageRecord.period_month == now.month,
        ).first()

        tokens_used = usage.llm_tokens_used if usage else 0
        tokens_purchased = getattr(usage, "llm_tokens_purchased", 0) if usage else 0
        plan_limit = plan.monthly_tokens if plan else 100000
        total_available = plan_limit + tokens_purchased

        # Check if tokens are exhausted
        is_exhausted = tokens_used >= total_available and total_available > 0
        # Enterprise plans with 0 monthly_tokens = unlimited
        is_unlimited = plan and plan.monthly_tokens == 0 and plan.slug == "enterprise"

        pct_used = round((tokens_used / total_available * 100), 1) if total_available > 0 else 0
        remaining = max(0, total_available - tokens_used)

        return {
            "tokens_used": tokens_used,
            "tokens_plan_limit": plan_limit,
            "tokens_purchased": tokens_purchased,
            "tokens_total_available": total_available,
            "tokens_remaining": remaining,
            "usage_pct": min(pct_used, 100),
            "is_exhausted": is_exhausted and not is_unlimited,
            "is_unlimited": is_unlimited,
            "plan_name": plan.name if plan else "Starter",
            "plan_slug": plan.slug if plan else "starter",
            "token_price_per_1k_cents": getattr(plan, "token_price_per_1k_cents", 10) if plan else 10,
        }
    finally:
        db.close()


@router.get("/token-packages")
async def list_token_packages(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Return available token top-up packages."""
    require_role(user, {"tenant_admin", "system_admin"})
    db = SessionLocal()
    try:
        plan = _get_tenant_plan(db, user.tenant_id)
        price_multiplier = 1.0
        if plan and plan.token_price_per_1k_cents:
            # Adjust package prices based on plan tier
            base_rate = 10  # default cents per 1K
            price_multiplier = plan.token_price_per_1k_cents / base_rate

        packages = []
        for pkg in TOKEN_PACKAGES:
            adjusted_price = int(pkg["price_cents"] * price_multiplier)
            packages.append({
                **pkg,
                "price_cents": adjusted_price,
                "price_formatted": f"{adjusted_price / 100:.2f}",
            })
        return packages
    finally:
        db.close()


class TokenPurchaseRequest(BaseModel):
    package_id: str
    success_url: str = ""
    cancel_url: str = ""


@router.post("/token-purchase")
async def purchase_tokens(
    req: TokenPurchaseRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for token purchase."""
    require_role(user, {"tenant_admin", "system_admin"})

    package = next((p for p in TOKEN_PACKAGES if p["id"] == req.package_id), None)
    if not package:
        raise HTTPException(status_code=404, detail="Token-Paket nicht gefunden.")

    # Check if Stripe is configured
    enabled = (persistence.get_setting("billing_stripe_enabled", "false") or "").lower() == "true"
    secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()

    if not enabled or not secret_key:
        # Fallback: directly add tokens without payment (for testing/demo)
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            from sqlalchemy import text as sa_text
            from app.core.db import engine

            dialect = engine.dialect.name
            if dialect == "postgresql":
                db.execute(sa_text(
                    "INSERT INTO usage_records (tenant_id, period_year, period_month, llm_tokens_purchased, messages_inbound, messages_outbound, active_members, llm_tokens_used) "
                    "VALUES (:tid, :yr, :mo, :amt, 0, 0, 0, 0) "
                    "ON CONFLICT (tenant_id, period_year, period_month) "
                    "DO UPDATE SET llm_tokens_purchased = usage_records.llm_tokens_purchased + :amt"
                ), {"tid": user.tenant_id, "yr": now.year, "mo": now.month, "amt": package["tokens"]})
            else:
                rec = db.query(UsageRecord).filter(
                    UsageRecord.tenant_id == user.tenant_id,
                    UsageRecord.period_year == now.year,
                    UsageRecord.period_month == now.month,
                ).first()
                if rec:
                    rec.llm_tokens_purchased = (rec.llm_tokens_purchased or 0) + package["tokens"]
                else:
                    db.add(UsageRecord(
                        tenant_id=user.tenant_id,
                        period_year=now.year,
                        period_month=now.month,
                        llm_tokens_purchased=package["tokens"],
                    ))

            purchase = TokenPurchase(
                tenant_id=user.tenant_id,
                tokens_amount=package["tokens"],
                price_cents=package["price_cents"],
                status="completed",
            )
            db.add(purchase)
            db.commit()

            return {"status": "completed", "tokens_added": package["tokens"]}
        finally:
            db.close()

    # Stripe checkout for token purchase
    try:
        import stripe
        stripe.api_key = secret_key

        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
            customer_id = sub.stripe_customer_id if sub else None

            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_name = tenant.name if tenant else f"Tenant {user.tenant_id}"
        finally:
            db.close()

        if not customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=tenant_name,
                metadata={"tenant_id": str(user.tenant_id)},
            )
            customer_id = customer["id"]

        base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
        success_url = req.success_url or f"{base_url}/settings/ai?purchase=success"
        cancel_url = req.cancel_url or f"{base_url}/settings/ai?purchase=canceled"

        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": package["price_cents"],
                    "product_data": {
                        "name": f"ARIIA Token Top-Up: {package['name']}",
                        "description": f"{package['tokens']:,} zusätzliche AI-Tokens",
                    },
                },
                "quantity": 1,
            }],
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(user.tenant_id),
                "type": "token_purchase",
                "package_id": req.package_id,
                "tokens_amount": str(package["tokens"]),
            },
        )

        # Record pending purchase
        db = SessionLocal()
        try:
            purchase = TokenPurchase(
                tenant_id=user.tenant_id,
                tokens_amount=package["tokens"],
                price_cents=package["price_cents"],
                stripe_checkout_session_id=session["id"],
                status="pending",
            )
            db.add(purchase)
            db.commit()
        finally:
            db.close()

        return {"url": session["url"], "session_id": session["id"]}

    except ImportError:
        raise HTTPException(status_code=500, detail="Stripe-Bibliothek nicht installiert.")
    except Exception as e:
        logger.error("tenant_llm.token_purchase_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {e}")
