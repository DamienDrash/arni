"""ARNI Stripe Billing Integration.

Endpoints:
  POST /admin/billing/checkout   – Create Stripe Checkout Session
  POST /webhook/stripe           – Handle Stripe Webhook events
  GET  /admin/billing/status     – Get current subscription status for tenant
"""

import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any

from app.core.auth import get_current_user, AuthContext
from app.core.models import Subscription
from app.core.db import SessionLocal
import structlog

logger = structlog.get_logger()


def _require_billing_access(user: AuthContext) -> None:
    """Allow tenant_admin and system_admin, deny tenant_user."""
    if user.role not in ("system_admin", "tenant_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

router = APIRouter()

# ── Stripe Config ─────────────────────────────────────────────────────────────

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICE_MAP = {
    "starter":    os.getenv("STRIPE_PRICE_STARTER", ""),
    "growth":     os.getenv("STRIPE_PRICE_GROWTH", ""),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
}

PLAN_CHANNEL_FEATURES = {
    "starter":    ["whatsapp", "telegram"],
    "growth":     ["whatsapp", "telegram", "email", "sms"],
    "enterprise": ["whatsapp", "telegram", "email", "sms", "voice"],
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str  # "starter" | "growth" | "enterprise"
    success_url: str = "https://app.arni.io/settings/billing?success=1"
    cancel_url: str = "https://app.arni.io/settings/billing?canceled=1"


# ── Checkout ──────────────────────────────────────────────────────────────────

@router.post("/billing/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for a given plan."""
    _require_billing_access(user)

    plan = body.plan.lower()
    price_id = PRICE_MAP.get(plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}. Use starter, growth or enterprise.")
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe not configured.")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            metadata={
                "tenant_id": str(user.tenant_id),
                "plan": plan,
            },
        )
        logger.info("stripe.checkout_created", tenant_id=user.tenant_id, plan=plan, session_id=session.id)
        return {"url": session.url, "session_id": session.id}
    except stripe.StripeError as e:
        logger.error("stripe.checkout_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message}")


# ── Webhook ───────────────────────────────────────────────────────────────────

@router.post("/stripe", include_in_schema=False)
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle incoming Stripe webhook events."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    else:
        # No webhook secret configured (dev mode) — trust event directly
        import json
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)

    event_type = event["type"]
    logger.info("stripe.webhook_received", event_type=event_type)

    db = SessionLocal()
    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(db, event["data"]["object"])

        elif event_type in ("invoice.paid",):
            _handle_invoice_paid(db, event["data"]["object"])

        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(db, event["data"]["object"])

    finally:
        db.close()

    return {"status": "ok"}


def _handle_checkout_completed(db, session: dict) -> None:
    meta = session.get("metadata", {})
    tenant_id = int(meta.get("tenant_id", 0))
    plan = meta.get("plan", "starter")
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")
    if not tenant_id or not subscription_id:
        return

    existing = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if existing:
        existing.stripe_subscription_id = subscription_id
        existing.stripe_customer_id = customer_id
        existing.status = "active"
        # Store plan name in customer_id field or use a dedicated column
        # For now, we annotate via stripe metadata — plan is stored in Stripe itself
    else:
        # Use plan_id=1 as default (Starter); the real plan tier is tracked via Stripe
        db.add(Subscription(
            tenant_id=tenant_id,
            plan_id=1,  # FK to plans table — set to starter by default
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
            status="active",
        ))
    db.commit()
    logger.info("stripe.subscription_activated", tenant_id=tenant_id, plan=plan)


def _handle_invoice_paid(db, invoice: dict) -> None:
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    if sub:
        sub.status = "active"
        db.commit()
        logger.info("stripe.invoice_paid", subscription_id=subscription_id)


def _handle_subscription_deleted(db, subscription: dict) -> None:
    subscription_id = subscription.get("id")
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    if sub:
        sub.status = "canceled"
        db.commit()
        logger.info("stripe.subscription_canceled", subscription_id=subscription_id)


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/billing/status")
async def get_billing_status(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current subscription status for the calling tenant."""
    _require_billing_access(user)
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not sub:
            return {"plan": None, "status": "no_subscription", "channels": []}
        return {
            "plan": sub.plan_id,
            "status": sub.status,
            "channels": PLAN_CHANNEL_FEATURES.get(sub.plan_id or "starter", []),
            "stripe_subscription_id": sub.stripe_subscription_id,
        }
    finally:
        db.close()
