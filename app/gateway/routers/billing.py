"""app/gateway/routers/billing.py — Stripe Checkout + Webhook Handler (K2).

Vollständige Implementierung, ersetzt den alten Stub.

Endpoints (alle prefix /admin via main.py):
    GET  /billing/plans                → Öffentlicher Plan-Katalog
    POST /billing/checkout-session     → Stripe Checkout Session erstellen
    POST /billing/customer-portal      → Stripe Customer Portal Session
    POST /billing/webhook              → Stripe Webhook (HMAC-signiert)

Stripe Events verarbeitet:
    checkout.session.completed         → Subscription aktivieren / Plan setzen
    customer.subscription.updated      → Status + Abrechnungsperiode sync
    customer.subscription.deleted      → Status → canceled
    invoice.payment_succeeded / .paid  → Status → active, Periode renew
    invoice.payment_failed             → Status → past_due

Design:
    - Stripe-Keys aus Settings-Store (nicht env-only)
    - tenant_id-Scoping für alle DB-Writes
    - Audit-Log pro kritischem Event
    - Graceful 402 wenn Stripe nicht konfiguriert
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

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_billing_access(user: AuthContext) -> None:
    require_role(user, {"system_admin", "tenant_admin"})


def _get_stripe(tenant_id: int | None = None):
    """Return configured stripe module.  Raises HTTP 402 if not enabled/configured."""
    try:
        import stripe as _stripe
    except ImportError:
        raise HTTPException(status_code=500, detail="stripe library not installed")

    enabled = (persistence.get_setting("billing_stripe_enabled", "false") or "").lower() == "true"
    if not enabled:
        raise HTTPException(
            status_code=402,
            detail="Stripe ist nicht aktiviert. Bitte in den Integrationseinstellungen konfigurieren.",
        )
    secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
    if not secret_key:
        raise HTTPException(
            status_code=402,
            detail="Stripe-Secret-Key nicht konfiguriert. Bitte in den Integrationseinstellungen eintragen.",
        )
    _stripe.api_key = secret_key
    return _stripe


def _get_or_create_stripe_customer(stripe, tenant_id: int, admin_email: str, tenant_name: str) -> str:
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
        if sub and sub.stripe_customer_id:
            return sub.stripe_customer_id
        customer = stripe.Customer.create(
            email=admin_email,
            name=tenant_name,
            metadata={"tenant_id": str(tenant_id)},
        )
        cid = customer["id"]
        if sub:
            sub.stripe_customer_id = cid
            db.commit()
        return cid
    finally:
        db.close()


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


# ── Plan-Katalog ───────────────────────────────────────────────────────────────

PLAN_CATALOG: list[dict[str, Any]] = [
    {
        "slug": "starter",
        "name": "Starter",
        "price_monthly_cents": 14900,
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
        "features": ["WhatsApp KI-Support", "Bis zu 500 Mitglieder", "10.000 Nachrichten/Monat", "E-Mail Support"],
    },
    {
        "slug": "pro",
        "name": "Pro",
        "price_monthly_cents": 34900,
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
        "price_monthly_cents": 99900,
        "max_members": None,
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


# ── Public Endpoints ───────────────────────────────────────────────────────────

@router.get("/billing/plans")
async def list_plans() -> list[dict[str, Any]]:
    """Öffentlicher Plan-Katalog — kein Auth erforderlich."""
    return PLAN_CATALOG


class CheckoutRequest(BaseModel):
    plan_slug: str
    success_url: str = ""
    cancel_url: str = ""


@router.post("/billing/checkout-session")
async def create_checkout_session(
    req: CheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Checkout Session.  Returns {'url': '...'}."""
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(
            Plan.slug == req.plan_slug, Plan.is_active.is_(True)
        ).first()
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden")
        if not plan.stripe_price_id:
            raise HTTPException(
                status_code=422,
                detail=f"Plan '{req.plan_slug}' hat keine Stripe Price-ID — im System-Admin konfigurieren.",
            )
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_name = tenant.name if tenant else f"Tenant {user.tenant_id}"
        plan_id_int = plan.id
    finally:
        db.close()

    stripe_customer_id = _get_or_create_stripe_customer(
        stripe, tenant_id=user.tenant_id,
        admin_email=user.email, tenant_name=tenant_name,
    )

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
                "ariia_plan_id": str(plan_id_int),
            },
            subscription_data={"metadata": {
                "tenant_id": str(user.tenant_id),
                "plan_id": str(plan_id_int),
            }},
        )
    except Exception as exc:
        logger.error("billing.checkout_session_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    _audit(user, "billing.checkout_session_created", {
        "plan_slug": req.plan_slug,
        "stripe_session_id": session.get("id"),
    })
    logger.info("billing.checkout_session_created",
                tenant_id=user.tenant_id, plan=req.plan_slug, session_id=session.get("id"))
    return {"url": session["url"]}


@router.post("/billing/customer-portal")
async def create_customer_portal(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Customer Portal Session (Abo-Verwaltung)."""
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

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
    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{base_url}/settings/billing",
        )
    except Exception as exc:
        logger.error("billing.portal_session_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    return {"url": portal["url"]}


# ── Webhook (raw body, HMAC verification) ─────────────────────────────────────

def _ts_to_dt(ts: int | None) -> datetime | None:
    if ts:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return None


def _on_checkout_completed(obj: dict) -> None:
    meta = obj.get("metadata", {})
    tenant_id = meta.get("tenant_id")
    plan_id   = meta.get("ariia_plan_id")
    stripe_sub_id = obj.get("subscription")
    stripe_cid    = obj.get("customer")
    if not tenant_id:
        return
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == int(tenant_id)).first()
        if sub:
            if plan_id:
                sub.plan_id = int(plan_id)
            sub.status = "active"
            sub.stripe_subscription_id = stripe_sub_id
            sub.stripe_customer_id = stripe_cid
        else:
            db.add(Subscription(
                tenant_id=int(tenant_id),
                plan_id=int(plan_id) if plan_id else 1,
                status="active",
                stripe_subscription_id=stripe_sub_id,
                stripe_customer_id=stripe_cid,
            ))
        db.commit()
        logger.info("billing.webhook.checkout_activated", tenant_id=tenant_id)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.checkout_db_failed", error=str(exc))
    finally:
        db.close()


def _on_subscription_event(event_type: str, obj: dict) -> None:
    stripe_sub_id = obj.get("id")
    meta = obj.get("metadata", {})
    tenant_id = meta.get("tenant_id")
    db = SessionLocal()
    try:
        q = db.query(Subscription)
        sub = q.filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
        if not sub and tenant_id:
            sub = q.filter(Subscription.tenant_id == int(tenant_id)).first()
        if not sub:
            return
        if event_type == "customer.subscription.deleted":
            sub.status = "canceled"
            sub.canceled_at = datetime.now(timezone.utc)
        else:
            sub.status = obj.get("status", sub.status)
            sub.current_period_start = _ts_to_dt(obj.get("current_period_start"))
            sub.current_period_end   = _ts_to_dt(obj.get("current_period_end"))
        db.commit()
        logger.info("billing.webhook.subscription_updated", event_type=event_type,
                    status=sub.status, sub_id=stripe_sub_id)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.subscription_db_failed", error=str(exc))
    finally:
        db.close()


def _on_invoice_event(event_type: str, obj: dict) -> None:
    stripe_sub_id = obj.get("subscription")
    if not stripe_sub_id:
        return
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()
        if not sub:
            return
        if event_type in ("invoice.payment_succeeded", "invoice.paid"):
            sub.status = "active"
            # Update period end from line items
            lines = obj.get("lines", {}).get("data", [])
            if lines:
                period_end = lines[0].get("period", {}).get("end")
                if period_end:
                    sub.current_period_end = _ts_to_dt(period_end)
        elif event_type == "invoice.payment_failed":
            sub.status = "past_due"
        db.commit()
        logger.info("billing.webhook.invoice_event", event_type=event_type, sub_id=stripe_sub_id)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.invoice_db_failed", error=str(exc))
    finally:
        db.close()


@router.post("/billing/webhook", include_in_schema=False)
async def stripe_webhook(request: Request) -> Response:
    """Stripe Webhook — HMAC-verifiziert, antwortet immer 200."""
    try:
        import stripe as _stripe
    except ImportError:
        return Response(content="stripe not installed", status_code=500)

    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    webhook_secret = (persistence.get_setting("billing_stripe_webhook_secret", "") or "").strip()
    secret_key     = (persistence.get_setting("billing_stripe_secret_key", "")     or "").strip()

    if not webhook_secret:
        logger.warning("billing.webhook.no_secret_configured")
        return Response(content="webhook_secret not configured", status_code=400)

    _stripe.api_key = secret_key
    try:
        event = _stripe.Webhook.construct_event(
            payload=payload, sig_header=sig_header, secret=webhook_secret,
        )
    except ValueError:
        return Response(content="invalid payload", status_code=400)
    except Exception as exc:
        logger.warning("billing.webhook.sig_invalid", error=str(exc))
        return Response(content="invalid signature", status_code=400)

    event_type = event.get("type", "")
    event_data = event.get("data", {})
    logger.info("billing.webhook.received", event_type=event_type, id=event.get("id"))

    HANDLERS: dict[str, Any] = {
        "checkout.session.completed":    lambda: _on_checkout_completed(event_data.get("object", {})),
        "customer.subscription.updated": lambda: _on_subscription_event(event_type, event_data.get("object", {})),
        "customer.subscription.deleted": lambda: _on_subscription_event(event_type, event_data.get("object", {})),
        "invoice.payment_succeeded":     lambda: _on_invoice_event(event_type, event_data.get("object", {})),
        "invoice.paid":                  lambda: _on_invoice_event(event_type, event_data.get("object", {})),
        "invoice.payment_failed":        lambda: _on_invoice_event(event_type, event_data.get("object", {})),
    }

    handler = HANDLERS.get(event_type)
    if handler:
        try:
            handler()
        except Exception as exc:
            logger.error("billing.webhook.handler_error", event_type=event_type, error=str(exc))

    return Response(
        content=_json.dumps({"received": True}),
        status_code=200,
        media_type="application/json",
    )
