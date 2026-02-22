"""app/gateway/billing.py — Stripe Checkout + Webhook Handler (K2).

Endpoints:
    POST /billing/checkout-session   → Erstellt Stripe Checkout Session für Plan-Upgrade
    POST /billing/customer-portal    → Öffnet Stripe Customer Portal (Verwaltung)
    POST /billing/webhook            → Stripe Webhook Empfänger (raw body, HMAC-Signatur)

Design:
    - Stripe Secret Key wird aus Settings-Store geladen (nicht hardcoded/envonly)
    - Webhook-Handler aktualisiert Subscription-Status in DB (event-driven)
    - Alle Checkout-Operationen sind tenant-scoped (tenant_admin erforderlich)
    - Graceful 402 wenn Stripe nicht konfiguriert

Stripe Events verarbeitet:
    checkout.session.completed         → Subscription aktivieren
    customer.subscription.updated      → Status + Periode aktualisieren
    customer.subscription.deleted      → Status auf 'canceled' setzen
    invoice.payment_succeeded          → Periode erneuern
    invoice.payment_failed             → Status auf 'past_due' setzen
"""

from __future__ import annotations

import json as _json
import structlog
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import Plan, Subscription, Tenant, AuditLog
from app.gateway.persistence import persistence

logger = structlog.get_logger()

router = APIRouter(prefix="/billing", tags=["billing"])

# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_stripe_client(tenant_id: int):
    """Return a configured Stripe client using the system-level secret key.

    Raises HTTP 402 if Stripe is not enabled or keys are missing.
    """
    try:
        import stripe as _stripe
    except ImportError:
        raise HTTPException(status_code=500, detail="stripe library not installed")

    enabled = (persistence.get_setting("billing_stripe_enabled", "false") or "false").lower() == "true"
    if not enabled:
        raise HTTPException(
            status_code=402,
            detail="Stripe ist nicht aktiviert. Bitte in den Integrationseinstellungen konfigurieren.",
        )

    secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
    if not secret_key:
        raise HTTPException(
            status_code=402,
            detail="Stripe-Secret-Key fehlt. Bitte in den Integrationseinstellungen eintragen.",
        )

    _stripe.api_key = secret_key
    return _stripe


def _require_tenant_admin(user: AuthContext) -> None:
    require_role(user, {"system_admin", "tenant_admin"})


def _get_or_create_stripe_customer(stripe, tenant_id: int, tenant_name: str, admin_email: str) -> str:
    """Find or create a Stripe customer for this tenant. Returns stripe customer_id."""
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
        if sub and sub.stripe_customer_id:
            return sub.stripe_customer_id

        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=admin_email,
            name=tenant_name,
            metadata={"tenant_id": str(tenant_id)},
        )
        customer_id = customer["id"]

        # Persist to subscription row
        if sub:
            sub.stripe_customer_id = customer_id
            db.commit()
        # (If no subscription yet, it will be set in webhook handler)
        return customer_id
    finally:
        db.close()


def _write_audit_event(actor: AuthContext, action: str, details: dict) -> None:
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
        logger.wariiang("billing.audit_write_failed", error=str(exc))
        db.rollback()
    finally:
        db.close()


# ── Plan-Katalog (extern für Frontend sichtbar) ────────────────────────────────

PLAN_CATALOG = [
    {
        "slug": "starter",
        "name": "Starter",
        "price_monthly_cents": 14900,  # €149/Monat
        "max_members": 500,
        "max_monthly_messages": 10_000,
        "max_channels": 1,
        "whatsapp_enabled": True,
        "telegram_enabled": False,
        "sms_enabled": False,
        "email_channel_enabled": False,
        "voice_enabled": False,
        "memory_analyzer_enabled": False,
        "custom_prompts_enabled": False,
        "features": [
            "WhatsApp KI-Support",
            "Bis zu 500 Mitglieder",
            "10.000 Nachrichten/Monat",
            "E-Mail Support",
        ],
    },
    {
        "slug": "pro",
        "name": "Pro",
        "price_monthly_cents": 34900,  # €349/Monat
        "max_members": 2_500,
        "max_monthly_messages": 50_000,
        "max_channels": 3,
        "whatsapp_enabled": True,
        "telegram_enabled": True,
        "sms_enabled": False,
        "email_channel_enabled": True,
        "voice_enabled": False,
        "memory_analyzer_enabled": True,
        "custom_prompts_enabled": True,
        "features": [
            "WhatsApp + Telegram + E-Mail",
            "Bis zu 2.500 Mitglieder",
            "50.000 Nachrichten/Monat",
            "Member Memory Analyzer",
            "Custom Prompts",
            "Priority Support",
        ],
        "highlight": True,
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "price_monthly_cents": 99900,  # €999/Monat
        "max_members": None,  # unlimited
        "max_monthly_messages": None,
        "max_channels": 10,
        "whatsapp_enabled": True,
        "telegram_enabled": True,
        "sms_enabled": True,
        "email_channel_enabled": True,
        "voice_enabled": True,
        "memory_analyzer_enabled": True,
        "custom_prompts_enabled": True,
        "features": [
            "Alle Kanäle inkl. Voice + SMS",
            "Unbegrenzte Mitglieder",
            "Unbegrenzte Nachrichten",
            "Dedicated CSM",
            "SLA-Garantie",
            "White-Label Option",
        ],
    },
]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans() -> list[dict[str, Any]]:
    """Öffentlicher Plan-Katalog (kein Auth erforderlich — für Marketing-Seite)."""
    return PLAN_CATALOG


class CheckoutRequest(BaseModel):
    plan_slug: str
    success_url: str = ""   # Frontend-URL nach erfolgreichem Checkout
    cancel_url: str = ""    # Frontend-URL bei Abbruch


@router.post("/checkout-session")
async def create_checkout_session(
    req: CheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Checkout Session für das gewünschte Plan-Upgrade.

    Returns:
        {"url": "https://checkout.stripe.com/..."} — Frontend redirectet dorthin
    """
    _require_tenant_admin(user)
    stripe = _get_stripe_client(user.tenant_id)

    # Lookup plan in DB (Stripe Price ID)
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(
            Plan.slug == req.plan_slug,
            Plan.is_active.is_(True),
        ).first()

        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden")

        if not plan.stripe_price_id:
            raise HTTPException(
                status_code=422,
                detail=f"Plan '{req.plan_slug}' hat keine Stripe Price-ID — bitte im System-Admin konfigurieren.",
            )

        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant nicht gefunden")

        tenant_name = tenant.name
    finally:
        db.close()

    # Get/create Stripe customer
    stripe_customer_id = _get_or_create_stripe_customer(
        stripe,
        tenant_id=user.tenant_id,
        tenant_name=tenant_name,
        admin_email=user.email,
    )

    # Build success/cancel URLs
    base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
    success_url = req.success_url or f"{base_url}/settings/billing?checkout=success"
    cancel_url  = req.cancel_url  or f"{base_url}/settings/billing?checkout=canceled"

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=stripe_customer_id,
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(user.tenant_id),
                "plan_slug": req.plan_slug,
                "ariia_plan_id": str(plan.id),
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(user.tenant_id),
                    "plan_id": str(plan.id),
                }
            },
        )
    except Exception as exc:  # stripe.error.StripeError
        logger.error("billing.checkout_session_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    _write_audit_event(user, "billing.checkout_session_created", {
        "plan_slug": req.plan_slug,
        "stripe_session_id": session.get("id"),
        "stripe_customer_id": stripe_customer_id,
    })

    logger.info("billing.checkout_session_created",
                tenant_id=user.tenant_id, plan=req.plan_slug, session_id=session.get("id"))
    return {"url": session["url"]}


@router.post("/customer-portal")
async def create_customer_portal(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Customer Portal Session (Abo verwalten, kündigen, Zahlungsdaten ändern)."""
    _require_tenant_admin(user)
    stripe = _get_stripe_client(user.tenant_id)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not sub or not sub.stripe_customer_id:
            raise HTTPException(
                status_code=404,
                detail="Kein Stripe-Konto gefunden. Bitte zuerst ein Abonnement abschließen.",
            )
        customer_id = sub.stripe_customer_id
    finally:
        db.close()

    base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
    return_url = f"{base_url}/settings/billing"

    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
    except Exception as exc:
        logger.error("billing.portal_session_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    return {"url": portal["url"]}


# ── Webhook (no auth — verified via HMAC signature) ────────────────────────────

def _handle_checkout_completed(event_data: dict) -> None:
    """Stripe checkout.session.completed → Subscription aktivieren."""
    session = event_data.get("object", {})
    metadata = session.get("metadata", {})
    tenant_id = metadata.get("tenant_id")
    plan_id   = metadata.get("ariia_plan_id")
    stripe_subscription_id = session.get("subscription")
    stripe_customer_id     = session.get("customer")

    if not tenant_id or not plan_id:
        logger.wariiang("billing.webhook.checkout_completed.missing_metadata", metadata=metadata)
        return

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == int(tenant_id)).first()
        if sub:
            sub.plan_id = int(plan_id)
            sub.status = "active"
            sub.stripe_subscription_id = stripe_subscription_id
            sub.stripe_customer_id = stripe_customer_id
        else:
            db.add(Subscription(
                tenant_id=int(tenant_id),
                plan_id=int(plan_id),
                status="active",
                stripe_subscription_id=stripe_subscription_id,
                stripe_customer_id=stripe_customer_id,
            ))
        db.commit()
        logger.info("billing.webhook.checkout_completed",
                    tenant_id=tenant_id, plan_id=plan_id, sub_id=stripe_subscription_id)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.checkout_completed.db_failed", error=str(exc))
    finally:
        db.close()


def _handle_subscription_event(event_type: str, event_data: dict) -> None:
    """customer.subscription.updated / .deleted"""
    sub_obj = event_data.get("object", {})
    stripe_sub_id = sub_obj.get("id")
    stripe_status = sub_obj.get("status", "unknown")
    metadata  = sub_obj.get("metadata", {})
    tenant_id = metadata.get("tenant_id")

    period_start_ts = sub_obj.get("current_period_start")
    period_end_ts   = sub_obj.get("current_period_end")

    def _ts(ts):
        if ts:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return None

    db = SessionLocal()
    try:
        q = db.query(Subscription)
        if stripe_sub_id:
            sub = q.filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
        elif tenant_id:
            sub = q.filter(Subscription.tenant_id == int(tenant_id)).first()
        else:
            logger.wariiang("billing.webhook.subscription_event.no_identifier",
                           event_type=event_type, sub_id=stripe_sub_id)
            return

        if not sub:
            logger.wariiang("billing.webhook.subscription_event.not_found",
                           stripe_sub_id=stripe_sub_id, tenant_id=tenant_id)
            return

        if event_type == "customer.subscription.deleted":
            sub.status = "canceled"
            sub.canceled_at = datetime.now(timezone.utc)
        else:
            sub.status = stripe_status
            sub.current_period_start = _ts(period_start_ts)
            sub.current_period_end   = _ts(period_end_ts)

        db.commit()
        logger.info("billing.webhook.subscription_updated",
                    event_type=event_type, status=stripe_status, sub_id=stripe_sub_id)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.subscription_event.db_failed", error=str(exc))
    finally:
        db.close()


def _handle_invoice_event(event_type: str, event_data: dict) -> None:
    """invoice.payment_succeeded / invoice.payment_failed"""
    invoice = event_data.get("object", {})
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()
        if not sub:
            return

        if event_type == "invoice.payment_succeeded":
            sub.status = "active"
            period_end_ts = invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
            if period_end_ts:
                sub.current_period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
        elif event_type == "invoice.payment_failed":
            sub.status = "past_due"

        db.commit()
        logger.info("billing.webhook.invoice_event", event_type=event_type, sub_id=stripe_sub_id)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.invoice_event.db_failed", error=str(exc))
    finally:
        db.close()


@router.post("/webhook")
async def stripe_webhook(request: Request) -> Response:
    """Stripe Webhook Endpoint.

    - Validiert HMAC-Signatur (whsec_...) aus billing_stripe_webhook_secret
    - Verarbeitet relevante Events asynchron
    - Antwortet immer mit 200 OK (Stripe erwartet dies, auch bei Fehlern)
    """
    try:
        import stripe as _stripe
    except ImportError:
        return Response(content="stripe not installed", status_code=500)

    # Read raw body for signature verification
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    webhook_secret = (persistence.get_setting("billing_stripe_webhook_secret", "") or "").strip()
    if not webhook_secret:
        logger.wariiang("billing.webhook.received_without_secret")
        return Response(content="webhook_secret not configured", status_code=400)

    secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
    _stripe.api_key = secret_key

    try:
        event = _stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=webhook_secret,
        )
    except ValueError:
        logger.wariiang("billing.webhook.invalid_payload")
        return Response(content="invalid payload", status_code=400)
    except Exception as exc:
        # stripe.error.SignatureVerificationError
        logger.wariiang("billing.webhook.signature_invalid", error=str(exc))
        return Response(content="invalid signature", status_code=400)

    event_type = event.get("type", "")
    event_data = event.get("data", {})

    logger.info("billing.webhook.received", event_type=event_type, event_id=event.get("id"))

    HANDLERS = {
        "checkout.session.completed":        lambda: _handle_checkout_completed(event_data),
        "customer.subscription.updated":     lambda: _handle_subscription_event(event_type, event_data),
        "customer.subscription.deleted":     lambda: _handle_subscription_event(event_type, event_data),
        "invoice.payment_succeeded":         lambda: _handle_invoice_event(event_type, event_data),
        "invoice.payment_failed":            lambda: _handle_invoice_event(event_type, event_data),
    }

    handler = HANDLERS.get(event_type)
    if handler:
        try:
            handler()
        except Exception as exc:
            # Do NOT return non-200 — Stripe would retry endlessly
            logger.error("billing.webhook.handler_failed", event_type=event_type, error=str(exc))
    else:
        logger.debug("billing.webhook.event_ignored", event_type=event_type)

    return Response(content=_json.dumps({"received": True}),
                    status_code=200,
                    media_type="application/json")
