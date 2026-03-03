"""
ARIIA Billing V2 – API Router

Replaces the monolithic billing.py router with a clean, service-oriented
implementation that delegates all business logic to the V2 service layer.

Endpoints (all under /billing prefix):
    GET  /billing/plans                    → Public plan catalog with entitlements
    GET  /billing/subscription             → Current subscription status
    POST /billing/checkout-session         → Stripe Checkout for plan subscription
    POST /billing/addon-checkout           → Stripe Checkout for add-ons
    POST /billing/token-purchase           → Stripe Checkout for token purchases
    POST /billing/customer-portal          → Stripe Customer Portal session
    POST /billing/verify-session           → Fallback session verification
    POST /billing/preview-plan-change      → Proration preview for plan changes
    POST /billing/change-plan              → Execute plan upgrade/downgrade
    POST /billing/cancel-subscription      → Cancel subscription at period end
    POST /billing/reactivate-subscription  → Reactivate canceled subscription
    POST /billing/deactivate-account       → Deactivate tenant account
    GET  /billing/invoices                 → Invoice history
    GET  /billing/usage                    → Current usage metrics
    GET  /billing/entitlements             → Feature entitlements for current plan
    GET  /billing/events                   → Billing event audit log
    POST /billing/webhook                  → Stripe webhook (HMAC-verified)
    GET  /billing/health                   → Stripe connectivity check

Design:
    - All business logic delegated to V2 services
    - Event sourcing via BillingEventService
    - Proper error handling with structured responses
    - Tenant-scoped access control
"""
from __future__ import annotations

import json as _json
import structlog
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import AuditLog, Tenant

from app.billing.events import billing_events
from app.billing.gating_service import gating_service
from app.billing.metering_service import metering_service
from app.billing.models import (
    BillingEventType,
    BillingInterval,
    PlanV2,
    SubscriptionStatus,
    SubscriptionV2,
)
from app.billing.stripe_service import stripe_service
from app.billing.subscription_service import subscription_service
from app.billing.webhook_processor import webhook_processor
from app.gateway.persistence import persistence

logger = structlog.get_logger()

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _require_billing_access(user: AuthContext) -> None:
    require_role(user, {"system_admin", "tenant_admin"})


def _audit(actor: AuthContext, action: str, details: dict) -> None:
    db = SessionLocal()
    try:
        db.add(AuditLog(
            actor_user_id=actor.user_id,
            actor_email=actor.email,
            tenant_id=actor.tenant_id,
            action=action,
            category="billing",
            details_json=_json.dumps(details, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    except Exception as exc:
        logger.warning("billing.audit_write_failed", error=str(exc))
        db.rollback()
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class CheckoutRequest(BaseModel):
    plan_slug: str
    billing_interval: str = "month"
    success_url: str = ""
    cancel_url: str = ""
    coupon_code: Optional[str] = None


class AddonCheckoutRequest(BaseModel):
    addon_slug: str
    quantity: int = 1
    success_url: str = ""
    cancel_url: str = ""


class TokenPurchaseRequest(BaseModel):
    tokens_amount: int = Field(..., ge=1000, description="Anzahl der zu kaufenden Tokens")
    success_url: str = ""
    cancel_url: str = ""


class ChangePlanRequest(BaseModel):
    plan_slug: str
    billing_interval: str = "month"


class VerifySessionRequest(BaseModel):
    session_id: str


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/billing/plans")
async def list_plans() -> list[dict[str, Any]]:
    """Öffentlicher Plan-Katalog mit Feature-Entitlements."""
    db = SessionLocal()
    try:
        return await gating_service.get_plan_comparison(db)
    except Exception as exc:
        logger.error("billing.plans.load_failed", error=str(exc))
        return []
    finally:
        db.close()


@router.get("/billing/health")
async def billing_health() -> dict[str, Any]:
    """Stripe-Konnektivitätsprüfung."""
    return await stripe_service.health_check()


# ══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION STATUS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/billing/subscription")
async def get_subscription_status(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Aktuellen Abonnement-Status abrufen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        data = subscription_service.get_subscription_with_plan(db, user.tenant_id)
        if not data:
            return {"has_subscription": False, "status": "none"}

        sub = data["subscription"]
        plan = data["plan"]

        result = {
            "has_subscription": True,
            "status": sub.status.value if isinstance(sub.status, SubscriptionStatus) else str(sub.status),
            "plan_name": plan.name if plan else "Unbekannt",
            "plan_slug": plan.slug if plan else None,
            "plan_id": plan.id if plan else None,
            "cancel_at_period_end": bool(sub.cancel_at_period_end),
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "billing_interval": sub.billing_interval.value if isinstance(sub.billing_interval, BillingInterval) else str(sub.billing_interval) if sub.billing_interval else "month",
            "stripe_subscription_id": sub.stripe_subscription_id,
            "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
            "extra_tokens_balance": sub.extra_tokens_balance or 0,
        }

        if sub.cancel_at_period_end:
            result["cancellation_effective_date"] = (
                sub.current_period_end.strftime("%d.%m.%Y") if sub.current_period_end else None
            )

        if sub.pending_plan_id:
            pending_plan = db.query(PlanV2).filter(PlanV2.id == sub.pending_plan_id).first()
            if pending_plan:
                result["pending_downgrade"] = {
                    "plan_name": pending_plan.name,
                    "plan_slug": pending_plan.slug,
                    "effective_date": sub.scheduled_change_at.strftime("%d.%m.%Y") if sub.scheduled_change_at else (
                        sub.current_period_end.strftime("%d.%m.%Y") if sub.current_period_end else None
                    ),
                }

        return result
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# CHECKOUT & PURCHASE
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/billing/checkout-session")
async def create_checkout_session(
    req: CheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Stripe Checkout Session für Plan-Subscription erstellen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        billing_interval = BillingInterval(req.billing_interval) if req.billing_interval in ("month", "year") else BillingInterval.MONTH

        base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
        success_url = req.success_url or f"{base_url}/settings/billing?checkout=success"
        cancel_url = req.cancel_url or f"{base_url}/settings/billing?checkout=canceled"

        result = await stripe_service.create_checkout_session(
            db=db,
            tenant_id=user.tenant_id,
            plan_slug=req.plan_slug,
            billing_interval=billing_interval,
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            customer_email=user.email,
            coupon_code=req.coupon_code,
        )

        _audit(user, "billing.checkout_session_created", {
            "plan_slug": req.plan_slug,
            "billing_interval": req.billing_interval,
            "session_id": result.get("session_id"),
        })

        return {"url": result["url"]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("billing.checkout_session_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


@router.post("/billing/addon-checkout")
async def create_addon_checkout_session(
    req: AddonCheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Stripe Checkout Session für Add-on-Kauf erstellen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
        success_url = req.success_url or f"{base_url}/settings/billing?addon=success"
        cancel_url = req.cancel_url or f"{base_url}/settings/billing?addon=canceled"

        result = await stripe_service.create_addon_checkout(
            db=db,
            tenant_id=user.tenant_id,
            addon_slug=req.addon_slug,
            quantity=req.quantity,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        _audit(user, "billing.addon_checkout_created", {
            "addon_slug": req.addon_slug,
            "quantity": req.quantity,
        })

        return {"url": result["url"]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("billing.addon_checkout_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


@router.post("/billing/token-purchase")
async def create_token_purchase(
    req: TokenPurchaseRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Token-Kauf via Stripe Checkout."""
    _require_billing_access(user)

    # Token pricing tiers
    TOKEN_PRICES = {
        10000: 499,      # 10k tokens → €4.99
        50000: 1999,     # 50k tokens → €19.99
        100000: 3499,    # 100k tokens → €34.99
        500000: 14999,   # 500k tokens → €149.99
        1000000: 24999,  # 1M tokens → €249.99
    }

    # Find closest tier or calculate custom price
    price_cents = TOKEN_PRICES.get(req.tokens_amount)
    if not price_cents:
        # Custom: €0.05 per 1000 tokens
        price_cents = max(99, int(req.tokens_amount / 1000 * 5))

    db = SessionLocal()
    try:
        base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
        success_url = req.success_url or f"{base_url}/settings/billing?tokens=success"
        cancel_url = req.cancel_url or f"{base_url}/settings/billing?tokens=canceled"

        result = await stripe_service.create_token_purchase_checkout(
            db=db,
            tenant_id=user.tenant_id,
            tokens_amount=req.tokens_amount,
            price_cents=price_cents,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return {"url": result["url"]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("billing.token_purchase_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


@router.post("/billing/customer-portal")
async def create_customer_portal(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Stripe Customer Portal Session erstellen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = subscription_service.get_subscription(db, user.tenant_id)
        if not sub or not sub.stripe_customer_id:
            raise HTTPException(
                status_code=404,
                detail="Kein Stripe-Konto gefunden. Bitte zuerst ein Abonnement abschließen.",
            )

        import stripe as _stripe
        from app.billing.stripe_service import _get_stripe
        stripe = _get_stripe()

        base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
        portal = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{base_url}/settings/billing",
        )

        return {"url": portal["url"]}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("billing.portal_session_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# PLAN CHANGES
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/billing/preview-plan-change")
async def preview_plan_change(
    req: ChangePlanRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Vorschau der Kosten bei Plan-Wechsel (Proration Preview)."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = subscription_service.get_subscription(db, user.tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="Kein aktives Stripe-Abonnement gefunden.")

        current_plan = db.query(PlanV2).filter(PlanV2.id == sub.plan_id).first()
        new_plan = db.query(PlanV2).filter(
            PlanV2.slug == req.plan_slug, PlanV2.is_active.is_(True)
        ).first()
        if not new_plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden.")

        # Determine price ID
        if req.billing_interval == "year" and new_plan.stripe_price_yearly_id:
            new_price_id = new_plan.stripe_price_yearly_id
        else:
            new_price_id = new_plan.stripe_price_monthly_id

        if not new_price_id:
            raise HTTPException(status_code=422, detail="Kein Stripe-Preis für diesen Plan konfiguriert.")

        current_price = current_plan.price_monthly_cents if current_plan else 0
        new_price = new_plan.price_monthly_cents
        is_upgrade = new_price > current_price

        from app.billing.stripe_service import _get_stripe
        stripe = _get_stripe()

        stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
        if not stripe_sub or not stripe_sub.get("items", {}).get("data"):
            raise HTTPException(status_code=502, detail="Stripe-Abonnement konnte nicht abgerufen werden.")

        current_item_id = stripe_sub["items"]["data"][0]["id"]

        result = {
            "current_plan": current_plan.name if current_plan else "Unbekannt",
            "new_plan": new_plan.name,
            "is_upgrade": is_upgrade,
            "current_price_cents": current_price,
            "new_price_cents": new_price,
            "billing_interval": req.billing_interval,
        }

        if is_upgrade:
            try:
                upcoming = stripe.Invoice.create_preview(
                    customer=sub.stripe_customer_id,
                    subscription=sub.stripe_subscription_id,
                    subscription_items=[{"id": current_item_id, "price": new_price_id}],
                    subscription_proration_behavior="create_prorations",
                )
                proration_amount = sum(
                    line.get("amount", 0)
                    for line in upcoming.get("lines", {}).get("data", [])
                    if line.get("proration")
                )
                result["proration_amount_cents"] = proration_amount
                result["proration_formatted"] = f"€{proration_amount / 100:.2f}"
                result["effective_date"] = "Sofort"
                result["message"] = (
                    f"Upgrade auf {new_plan.name}: Sie zahlen jetzt anteilig "
                    f"€{proration_amount / 100:.2f} für die verbleibende Zeit."
                )
            except Exception as exc:
                logger.warning("billing.preview_proration_failed", error=str(exc))
                result["message"] = f"Upgrade auf {new_plan.name} wird sofort wirksam."
                result["proration_amount_cents"] = 0
        else:
            period_end = stripe_sub.get("current_period_end")
            if period_end:
                end_dt = datetime.fromtimestamp(period_end, tz=timezone.utc)
                result["effective_date"] = end_dt.strftime("%d.%m.%Y")
            else:
                result["effective_date"] = "Ende des Abrechnungszeitraums"
            result["proration_amount_cents"] = 0
            result["proration_formatted"] = "€0.00"
            result["message"] = (
                f"Downgrade auf {new_plan.name}: Der Wechsel wird am Ende des aktuellen "
                f"Abrechnungszeitraums ({result['effective_date']}) wirksam."
            )

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("billing.preview_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Fehler: {exc}")
    finally:
        db.close()


@router.post("/billing/change-plan")
async def change_plan(
    req: ChangePlanRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Plan wechseln (Upgrade sofort mit Proration, Downgrade zum Periodenende)."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = subscription_service.get_subscription(db, user.tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="Kein aktives Stripe-Abonnement gefunden.")

        status_val = sub.status
        if isinstance(status_val, SubscriptionStatus):
            status_str = status_val.value
        else:
            status_str = str(status_val)

        if status_str not in ("active", "trialing"):
            raise HTTPException(status_code=400, detail=f"Plan-Wechsel nicht möglich. Status: {status_str}")

        current_plan = db.query(PlanV2).filter(PlanV2.id == sub.plan_id).first()
        new_plan = db.query(PlanV2).filter(
            PlanV2.slug == req.plan_slug, PlanV2.is_active.is_(True)
        ).first()
        if not new_plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden.")

        if current_plan and current_plan.id == new_plan.id:
            raise HTTPException(status_code=400, detail="Sie haben diesen Plan bereits.")

        current_price = current_plan.price_monthly_cents if current_plan else 0
        new_price = new_plan.price_monthly_cents
        is_upgrade = new_price > current_price

        billing_interval = BillingInterval(req.billing_interval) if req.billing_interval in ("month", "year") else BillingInterval.MONTH

        if is_upgrade:
            # Upgrade via Stripe + local service
            await stripe_service.update_stripe_subscription(
                db=db,
                tenant_id=user.tenant_id,
                new_plan_slug=req.plan_slug,
                billing_interval=billing_interval,
                proration_behavior="create_prorations",
            )
            await subscription_service.upgrade(
                db=db,
                tenant_id=user.tenant_id,
                new_plan_slug=req.plan_slug,
                billing_interval=billing_interval,
                actor_type="user",
                actor_id=str(user.user_id),
            )

            _audit(user, "billing.plan_upgraded", {
                "from_plan": current_plan.slug if current_plan else None,
                "to_plan": new_plan.slug,
            })

            return {
                "success": True,
                "type": "upgrade",
                "plan": new_plan.name,
                "effective": "immediate",
                "message": f"Upgrade auf {new_plan.name} erfolgreich! Der neue Plan ist sofort aktiv.",
            }
        else:
            # Downgrade: schedule via Stripe + local service
            from app.billing.stripe_service import _get_stripe
            stripe = _get_stripe()

            stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
            current_item_id = stripe_sub["items"]["data"][0]["id"]

            # Determine new price ID
            if billing_interval == BillingInterval.YEAR and new_plan.stripe_price_yearly_id:
                new_price_id = new_plan.stripe_price_yearly_id
            else:
                new_price_id = new_plan.stripe_price_monthly_id

            if not new_price_id:
                raise HTTPException(status_code=422, detail="Kein Stripe-Preis konfiguriert.")

            # Cancel existing schedules
            try:
                schedules = stripe.SubscriptionSchedule.list(
                    customer=sub.stripe_customer_id, limit=5,
                )
                for sched in schedules.get("data", []):
                    if (sched.get("subscription") == sub.stripe_subscription_id
                            and sched.get("status") in ("not_started", "active")):
                        stripe.SubscriptionSchedule.release(sched["id"])
            except Exception:
                pass

            # Create schedule for deferred downgrade
            schedule = stripe.SubscriptionSchedule.create(
                from_subscription=sub.stripe_subscription_id,
            )
            current_phase_end = stripe_sub.get("current_period_end")
            stripe.SubscriptionSchedule.modify(
                schedule["id"],
                phases=[
                    {
                        "items": [{"price": stripe_sub["items"]["data"][0]["price"]["id"], "quantity": 1}],
                        "start_date": stripe_sub.get("current_period_start"),
                        "end_date": current_phase_end,
                    },
                    {
                        "items": [{"price": new_price_id, "quantity": 1}],
                        "start_date": current_phase_end,
                        "iterations": 1,
                        "proration_behavior": "none",
                        "metadata": {
                            "tenant_id": str(user.tenant_id),
                            "plan_slug": new_plan.slug,
                        },
                    },
                ],
            )

            # Update local state
            await subscription_service.downgrade(
                db=db,
                tenant_id=user.tenant_id,
                new_plan_slug=req.plan_slug,
                billing_interval=billing_interval,
                immediate=False,
                actor_type="user",
                actor_id=str(user.user_id),
            )

            period_end_dt = datetime.fromtimestamp(current_phase_end, tz=timezone.utc) if current_phase_end else None
            effective_date = period_end_dt.strftime("%d.%m.%Y") if period_end_dt else "Ende des Abrechnungszeitraums"

            _audit(user, "billing.plan_downgrade_scheduled", {
                "from_plan": current_plan.slug if current_plan else None,
                "to_plan": new_plan.slug,
                "effective_date": effective_date,
            })

            return {
                "success": True,
                "type": "downgrade",
                "plan": new_plan.name,
                "effective": effective_date,
                "message": (
                    f"Downgrade auf {new_plan.name} geplant. "
                    f"Der Wechsel wird am {effective_date} wirksam."
                ),
            }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("billing.change_plan_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# CANCELLATION & REACTIVATION
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/billing/cancel-subscription")
async def cancel_subscription(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Abonnement zum Ende des Abrechnungszeitraums kündigen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = subscription_service.get_subscription(db, user.tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="Kein aktives Abonnement gefunden.")

        status_str = sub.status.value if isinstance(sub.status, SubscriptionStatus) else str(sub.status)
        if status_str == "canceled":
            raise HTTPException(status_code=400, detail="Das Abonnement ist bereits gekündigt.")

        # Cancel in Stripe
        stripe_result = await stripe_service.cancel_stripe_subscription(db, user.tenant_id, immediate=False)

        # Cancel locally
        await subscription_service.cancel(
            db=db,
            tenant_id=user.tenant_id,
            reason="user_requested",
            immediate=False,
            actor_type="user",
            actor_id=str(user.user_id),
        )

        effective_date = sub.current_period_end.strftime("%d.%m.%Y") if sub.current_period_end else "Ende des Abrechnungszeitraums"

        _audit(user, "billing.subscription_canceled", {
            "effective_date": effective_date,
            "cancel_at_period_end": True,
        })

        return {
            "success": True,
            "effective_date": effective_date,
            "message": (
                f"Ihr Abonnement wurde gekündigt. Es bleibt bis zum {effective_date} aktiv. "
                f"Danach wird es nicht erneuert."
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("billing.cancel_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


@router.post("/billing/reactivate-subscription")
async def reactivate_subscription(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Gekündigtes Abonnement reaktivieren."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = subscription_service.get_subscription(db, user.tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="Kein Abonnement gefunden.")

        status_str = sub.status.value if isinstance(sub.status, SubscriptionStatus) else str(sub.status)
        if status_str == "canceled":
            raise HTTPException(status_code=400, detail="Das Abonnement ist bereits abgelaufen.")

        if not sub.cancel_at_period_end:
            raise HTTPException(status_code=400, detail="Das Abonnement ist nicht zur Kündigung vorgemerkt.")

        # Reactivate in Stripe
        await stripe_service.reactivate_stripe_subscription(db, user.tenant_id)

        # Reactivate locally
        await subscription_service.reactivate(
            db=db,
            tenant_id=user.tenant_id,
            actor_type="user",
            actor_id=str(user.user_id),
        )

        _audit(user, "billing.subscription_reactivated", {})

        return {
            "success": True,
            "message": "Ihr Abonnement wurde erfolgreich reaktiviert.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("billing.reactivate_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# VERIFY SESSION (Fallback)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/billing/verify-session")
async def verify_checkout_session(
    req: VerifySessionRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Stripe Checkout Session verifizieren (Fallback für Webhook)."""
    _require_billing_access(user)

    try:
        from app.billing.stripe_service import _get_stripe
        stripe = _get_stripe()
        session = stripe.checkout.Session.retrieve(req.session_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    meta = session.get("metadata", {})
    session_tenant_id = meta.get("tenant_id")
    if session_tenant_id and int(session_tenant_id) != user.tenant_id:
        raise HTTPException(status_code=403, detail="Session gehört nicht zu diesem Tenant")

    payment_status = session.get("payment_status", "")
    status = session.get("status", "")

    result = {
        "session_id": req.session_id,
        "status": status,
        "payment_status": payment_status,
        "plan_activated": False,
    }

    if status != "complete" or payment_status != "paid":
        result["message"] = "Zahlung noch nicht abgeschlossen"
        return result

    # Process the completed session
    session_type = meta.get("checkout_type", meta.get("type", "subscription"))
    plan_slug = meta.get("plan_slug", "")
    stripe_sub_id = session.get("subscription")
    stripe_cid = session.get("customer")

    db = SessionLocal()
    try:
        if session_type in ("subscription", "plan_upgrade"):
            plan = db.query(PlanV2).filter(PlanV2.slug == plan_slug).first()
            if plan:
                sub = subscription_service.get_subscription(db, user.tenant_id)
                if sub:
                    sub.plan_id = plan.id
                    sub.status = SubscriptionStatus.ACTIVE
                    sub.stripe_subscription_id = stripe_sub_id
                    sub.stripe_customer_id = stripe_cid
                else:
                    billing_interval_str = meta.get("billing_interval", "month")
                    billing_interval = BillingInterval(billing_interval_str) if billing_interval_str in ("month", "year") else BillingInterval.MONTH
                    await subscription_service.create_subscription(
                        db=db,
                        tenant_id=user.tenant_id,
                        plan_slug=plan_slug,
                        billing_interval=billing_interval,
                        stripe_subscription_id=stripe_sub_id,
                        stripe_customer_id=stripe_cid,
                        trial_days=0,
                        actor_type="user",
                        actor_id=str(user.user_id),
                    )
                db.commit()
                result["plan_activated"] = True
                result["message"] = f"Plan '{plan_slug}' erfolgreich aktiviert"

        elif session_type == "token_purchase":
            tokens_amount = int(meta.get("tokens_amount", 0))
            if tokens_amount > 0:
                sub = subscription_service.get_subscription(db, user.tenant_id)
                if sub:
                    sub.extra_tokens_balance = (sub.extra_tokens_balance or 0) + tokens_amount
                    db.commit()
                result["plan_activated"] = True
                result["message"] = f"{tokens_amount:,} Tokens erfolgreich hinzugefügt"

        _audit(user, "billing.session_verified", {
            "session_id": req.session_id,
            "type": session_type,
            "plan_activated": result["plan_activated"],
        })
    except Exception as exc:
        db.rollback()
        logger.error("billing.verify_session_failed", error=str(exc))
    finally:
        db.close()

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ACCOUNT DEACTIVATION
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/billing/deactivate-account")
async def deactivate_account(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Konto deaktivieren."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = subscription_service.get_subscription(db, user.tenant_id)

        if sub:
            status_str = sub.status.value if isinstance(sub.status, SubscriptionStatus) else str(sub.status)
            if status_str == "active" and not sub.cancel_at_period_end:
                raise HTTPException(
                    status_code=400,
                    detail="Bitte kündigen Sie zuerst Ihr Abonnement.",
                )

            # Cancel immediately in Stripe if still active
            if sub.stripe_subscription_id and status_str != "canceled":
                try:
                    await stripe_service.cancel_stripe_subscription(db, user.tenant_id, immediate=True)
                except Exception as exc:
                    logger.warning("billing.deactivate_stripe_cancel_failed", error=str(exc))

                await subscription_service.cancel(
                    db=db,
                    tenant_id=user.tenant_id,
                    reason="account_deactivation",
                    immediate=True,
                    actor_type="user",
                    actor_id=str(user.user_id),
                )

        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if tenant:
            tenant.is_active = False

        db.commit()

        _audit(user, "account.deactivated", {"tenant_id": user.tenant_id})

        return {
            "success": True,
            "message": "Ihr Konto wurde deaktiviert.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("account.deactivation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Fehler bei der Konto-Deaktivierung.")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# USAGE & ENTITLEMENTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/billing/usage")
async def get_usage(
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Aktuelle Nutzungsmetriken abrufen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        summaries = await metering_service.get_all_usage(db, user.tenant_id)
        return [
            {
                "feature_key": s.feature_key,
                "feature_name": s.feature_name,
                "usage_count": s.usage_count,
                "soft_limit": s.soft_limit,
                "hard_limit": s.hard_limit,
                "percentage_used": s.percentage_used,
                "in_overage": s.in_overage,
                "remaining": s.remaining,
            }
            for s in summaries
        ]
    finally:
        db.close()


@router.get("/billing/entitlements")
async def get_entitlements(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Feature-Entitlements für den aktuellen Plan abrufen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        return await gating_service.get_entitlements(db, user.tenant_id)
    finally:
        db.close()


@router.get("/billing/invoices")
async def get_invoices(
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Rechnungshistorie von Stripe abrufen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        return await stripe_service.sync_invoices(db, user.tenant_id)
    except Exception as exc:
        logger.error("billing.invoices_failed", error=str(exc))
        return []
    finally:
        db.close()


@router.get("/billing/events")
async def get_billing_events(
    user: AuthContext = Depends(get_current_user),
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Billing-Event-Audit-Log abrufen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        events = billing_events.get_events_for_tenant(db, user.tenant_id, limit=limit)
        return [
            {
                "id": e.id,
                "event_type": e.event_type.value if isinstance(e.event_type, BillingEventType) else str(e.event_type),
                "payload": _json.loads(e.payload_json) if e.payload_json else None,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "stripe_event_id": e.stripe_event_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/billing/webhook", include_in_schema=False)
async def stripe_webhook(request: Request) -> Response:
    """Stripe Webhook — HMAC-verifiziert, verarbeitet über WebhookProcessorV2."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    db = SessionLocal()
    try:
        result = await webhook_processor.process(db, payload, sig_header)
        return Response(
            content=_json.dumps({"received": True, **result}),
            status_code=200,
            media_type="application/json",
        )
    except Exception as exc:
        logger.error("billing.webhook.unhandled_error", error=str(exc))
        return Response(
            content=_json.dumps({"received": True, "error": str(exc)}),
            status_code=200,  # Always return 200 to Stripe
            media_type="application/json",
        )
    finally:
        db.close()
