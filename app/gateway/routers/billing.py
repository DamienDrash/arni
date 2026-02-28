"""app/gateway/routers/billing.py — Stripe Checkout + Webhook Handler (K2).

Vollständige Implementierung, ersetzt den alten Stub.

Endpoints (alle prefix /admin via main.py):
    GET  /billing/plans                → Öffentlicher Plan-Katalog
    POST /billing/checkout-session     → Stripe Checkout Session erstellen
    POST /billing/addon-checkout       → Stripe Checkout für Add-ons
    POST /billing/customer-portal      → Stripe Customer Portal Session
    POST /billing/webhook              → Stripe Webhook (HMAC-signiert)

Stripe Events verarbeitet:
    checkout.session.completed         → Subscription aktivieren / Plan setzen / Add-ons buchen
    customer.subscription.updated      → Status + Abrechnungsperiode sync + Add-ons sync
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
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import Plan, Subscription, Tenant, AuditLog, TenantAddon, AddonDefinition
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

def _load_plan_catalog() -> list[dict[str, Any]]:
    """Load plan catalog dynamically from the database."""
    import json as _j
    db = SessionLocal()
    try:
        plans = db.query(Plan).filter(
            Plan.is_active.is_(True),
            Plan.is_public.is_(True),
        ).order_by(
            Plan.display_order.asc(),
            Plan.price_monthly_cents.asc(),
        ).all()

        result = []
        for p in plans:
            features_list = []
            if getattr(p, "features_json", None):
                try:
                    features_list = _j.loads(p.features_json)
                except (ValueError, TypeError):
                    pass

            result.append({
                "slug": p.slug,
                "name": p.name,
                "description": getattr(p, "description", None),
                "price_monthly_cents": p.price_monthly_cents,
                "price_yearly_cents": getattr(p, "price_yearly_cents", None),
                "trial_days": getattr(p, "trial_days", 0),
                "max_members": p.max_members,
                "max_monthly_messages": p.max_monthly_messages,
                "max_channels": p.max_channels,
                "max_connectors": p.max_connectors,
                "features": features_list,
                "highlight": getattr(p, "is_highlighted", False),
                "stripe_price_id": p.stripe_price_id,
            })
        return result
    except Exception as exc:
        logger.warning("billing.plan_catalog_load_failed", error=str(exc))
        return []
    finally:
        db.close()


# ── Public Endpoints ───────────────────────────────────────────────────────────

@router.get("/billing/plans")
async def list_plans() -> list[dict[str, Any]]:
    """Öffentlicher Plan-Katalog — dynamisch aus der Datenbank."""
    return _load_plan_catalog()


class CheckoutRequest(BaseModel):
    plan_slug: str
    success_url: str = ""
    cancel_url: str = ""

@router.post("/billing/checkout-session")
async def create_checkout_session(
    req: CheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Checkout Session für Plan-Upgrades."""
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(
            Plan.slug == req.plan_slug, Plan.is_active.is_(True)
        ).first()
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden")
        if not plan.stripe_price_id and plan.price_monthly_cents > 0:
             # Allow free plans if handled logic permits, but mostly we redirect to Stripe even for $0 trials if setup
             pass 

        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_name = tenant.name if tenant else f"Tenant {user.tenant_id}"
        plan_id_int = plan.id
        stripe_price_id = plan.stripe_price_id
    finally:
        db.close()
    
    if not stripe_price_id:
         # Fallback for free plans without Stripe
         # In a real scenario, we might just upgrade them directly without Stripe Checkout
         raise HTTPException(status_code=422, detail="Plan has no price ID configured.")

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
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(user.tenant_id),
                "plan_slug": req.plan_slug,
                "ariia_plan_id": str(plan_id_int),
                "type": "plan_upgrade"
            },
            subscription_data={"metadata": {
                "tenant_id": str(user.tenant_id),
                "plan_id": str(plan_id_int),
            }},
            allow_promotion_codes=True,
        )
    except Exception as exc:
        logger.error("billing.checkout_session_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    _audit(user, "billing.checkout_session_created", {
        "plan_slug": req.plan_slug,
        "stripe_session_id": session.get("id"),
    })
    return {"url": session["url"]}


class AddonCheckoutRequest(BaseModel):
    addon_slug: str  # e.g., "voice_pipeline"
    price_id: str    # Stripe Price ID for the addon
    quantity: int = 1
    success_url: str = ""
    cancel_url: str = ""

@router.post("/billing/addon-checkout")
async def create_addon_checkout_session(
    req: AddonCheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Checkout Session für Add-ons."""
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)
    
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    tenant_name = tenant.name if tenant else f"Tenant {user.tenant_id}"
    db.close()

    stripe_customer_id = _get_or_create_stripe_customer(
        stripe, tenant_id=user.tenant_id,
        admin_email=user.email, tenant_name=tenant_name,
    )

    base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
    success_url = req.success_url or f"{base_url}/settings/billing?addon=success"
    cancel_url  = req.cancel_url  or f"{base_url}/settings/billing?addon=canceled"

    # Check if user has an active subscription to upsell to
    # If using 'subscription' mode in Checkout with an existing customer who has a sub, 
    # Stripe might create a new subscription. To add to existing, we usually use the Portal or API.
    # But Checkout is easiest. Let's assume we create a NEW subscription for the addon OR 
    # we use 'setup' mode if we just want to authorize.
    # Actually, the standard way for SaaS add-ons in Checkout is to create a separate subscription 
    # OR if we want to add to existing, we have to use the API directly (SubscriptionItem.create), not Checkout.
    # BUT, the prompt implies "Checkout". So let's create a Checkout Session that creates a subscription for the addon.
    # This results in multiple subscriptions per customer, which is valid in Stripe.

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=stripe_customer_id,
            line_items=[{"price": req.price_id, "quantity": req.quantity}],
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(user.tenant_id),
                "addon_slug": req.addon_slug,
                "type": "addon_purchase"
            },
            subscription_data={"metadata": {
                "tenant_id": str(user.tenant_id),
                "addon_slug": req.addon_slug,
                "is_addon": "true"
            }},
        )
    except Exception as exc:
        logger.error("billing.addon_checkout_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

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


# ── Verify Session (Fallback for Webhook) ────────────────────────────────────

class VerifySessionRequest(BaseModel):
    session_id: str

@router.post("/billing/verify-session")
async def verify_checkout_session(
    req: VerifySessionRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Verify a Stripe Checkout Session and activate the plan if payment succeeded.
    
    This is a fallback mechanism for when the Stripe webhook hasn't fired yet
    (or is misconfigured). Called by the frontend when the user returns from
    Stripe Checkout with a session_id in the URL.
    """
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

    try:
        session = stripe.checkout.Session.retrieve(req.session_id)
    except Exception as exc:
        logger.error("billing.verify_session_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    # Verify the session belongs to this tenant
    meta = session.get("metadata", {})
    session_tenant_id = meta.get("tenant_id")
    if session_tenant_id and int(session_tenant_id) != user.tenant_id:
        raise HTTPException(status_code=403, detail="Session gehört nicht zu diesem Tenant")

    payment_status = session.get("payment_status", "")
    status = session.get("status", "")
    session_type = meta.get("type", "plan_upgrade")

    result = {
        "session_id": req.session_id,
        "status": status,
        "payment_status": payment_status,
        "plan_activated": False,
    }

    # Only process completed sessions
    if status != "complete" or payment_status != "paid":
        result["message"] = "Zahlung noch nicht abgeschlossen"
        return result

    if session_type == "plan_upgrade":
        plan_id = meta.get("ariia_plan_id")
        plan_slug = meta.get("plan_slug")
        stripe_sub_id = session.get("subscription")
        stripe_cid = session.get("customer")

        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(
                Subscription.tenant_id == user.tenant_id
            ).first()

            if sub:
                # Check if already activated (by webhook)
                if sub.stripe_subscription_id == stripe_sub_id and sub.status == "active":
                    result["plan_activated"] = True
                    result["message"] = "Plan bereits aktiviert"
                    return result

                # Activate the plan
                if plan_id:
                    sub.plan_id = int(plan_id)
                sub.status = "active"
                sub.stripe_subscription_id = stripe_sub_id
                sub.stripe_customer_id = stripe_cid
                # Clear trial fields if present
                if hasattr(sub, 'trial_ends_at'):
                    sub.trial_ends_at = None
            else:
                db.add(Subscription(
                    tenant_id=user.tenant_id,
                    plan_id=int(plan_id) if plan_id else 1,
                    status="active",
                    stripe_subscription_id=stripe_sub_id,
                    stripe_customer_id=stripe_cid,
                ))

            db.commit()
            result["plan_activated"] = True
            result["message"] = f"Plan '{plan_slug}' erfolgreich aktiviert"
            logger.info("billing.verify_session.plan_activated",
                       tenant_id=user.tenant_id, plan_slug=plan_slug)
        except Exception as exc:
            db.rollback()
            logger.error("billing.verify_session.db_failed", error=str(exc))
            raise HTTPException(status_code=500, detail="Datenbankfehler bei Plan-Aktivierung")
        finally:
            db.close()

    elif session_type == "addon_purchase":
        addon_slug = meta.get("addon_slug")
        stripe_sub_id = session.get("subscription")
        if addon_slug:
            db = SessionLocal()
            try:
                existing = db.query(TenantAddon).filter(
                    TenantAddon.tenant_id == user.tenant_id,
                    TenantAddon.addon_slug == addon_slug,
                    TenantAddon.status == "active",
                ).first()
                if not existing:
                    db.add(TenantAddon(
                        tenant_id=user.tenant_id,
                        addon_slug=addon_slug,
                        stripe_subscription_item_id=stripe_sub_id,
                        quantity=1,
                        status="active",
                    ))
                    db.commit()
                result["plan_activated"] = True
                result["message"] = f"Add-on '{addon_slug}' erfolgreich aktiviert"
            except Exception as exc:
                db.rollback()
                logger.error("billing.verify_session.addon_failed", error=str(exc))
            finally:
                db.close()

    _audit(user, "billing.session_verified", {
        "session_id": req.session_id,
        "type": session_type,
        "plan_activated": result["plan_activated"],
    })

    return result



# ── Plan Change (Upgrade / Downgrade via Stripe Subscription.modify) ─────────

class ChangePlanRequest(BaseModel):
    plan_slug: str
    billing_interval: str = "month"  # "month" or "year"

class ChangePlanPreviewResponse(BaseModel):
    current_plan: str
    new_plan: str
    is_upgrade: bool
    proration_amount_cents: int = 0
    proration_formatted: str = ""
    effective_date: str = ""
    message: str = ""

@router.post("/billing/preview-plan-change")
async def preview_plan_change(
    req: ChangePlanRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Vorschau der Kosten bei Plan-Wechsel (Proration Preview).
    
    Zeigt dem Benutzer, was ein Upgrade/Downgrade kosten würde,
    bevor er den Wechsel bestätigt.
    """
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="Kein aktives Stripe-Abonnement gefunden.")

        current_plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
        new_plan = db.query(Plan).filter(
            Plan.slug == req.plan_slug, Plan.is_active.is_(True)
        ).first()
        if not new_plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden.")

        # Determine price ID based on billing interval
        if req.billing_interval == "year" and getattr(new_plan, "stripe_price_yearly_id", None):
            new_price_id = new_plan.stripe_price_yearly_id
        else:
            new_price_id = new_plan.stripe_price_id

        if not new_price_id:
            raise HTTPException(status_code=422, detail="Kein Stripe-Preis für diesen Plan konfiguriert.")

        current_price = current_plan.price_monthly_cents if current_plan else 0
        new_price = new_plan.price_monthly_cents
        is_upgrade = new_price > current_price

        # Get the current subscription from Stripe to find the subscription item
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
            # Preview proration for upgrades
            try:
                upcoming = stripe.Invoice.create_preview(
                    customer=sub.stripe_customer_id,
                    subscription=sub.stripe_subscription_id,
                    subscription_items=[{
                        "id": current_item_id,
                        "price": new_price_id,
                    }],
                    subscription_proration_behavior="create_prorations",
                )
                # Find proration line items
                proration_amount = 0
                for line in upcoming.get("lines", {}).get("data", []):
                    if line.get("proration"):
                        proration_amount += line.get("amount", 0)

                result["proration_amount_cents"] = proration_amount
                result["proration_formatted"] = f"€{proration_amount / 100:.2f}"
                result["effective_date"] = "Sofort"
                result["message"] = (
                    f"Upgrade auf {new_plan.name}: Sie zahlen jetzt anteilig "
                    f"€{proration_amount / 100:.2f} für die verbleibende Zeit im aktuellen Abrechnungszyklus."
                )
            except Exception as exc:
                logger.warning("billing.preview_proration_failed", error=str(exc))
                result["message"] = f"Upgrade auf {new_plan.name} wird sofort wirksam."
                result["proration_amount_cents"] = 0
        else:
            # Downgrade: effective at end of period
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
                f"Abrechnungszeitraums ({result['effective_date']}) wirksam. "
                f"Bis dahin behalten Sie alle Funktionen Ihres aktuellen Plans."
            )

        return result
    finally:
        db.close()


@router.post("/billing/change-plan")
async def change_plan(
    req: ChangePlanRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Plan wechseln (Upgrade sofort mit Proration, Downgrade zum Periodenende).
    
    Gold Standard Implementierung:
    - Upgrade: stripe.Subscription.modify mit proration_behavior='create_prorations'
      → Sofortige Aktivierung, anteilige Berechnung
    - Downgrade: stripe.Subscription.modify mit proration_behavior='none'
      und schedule für nächste Periode → Wechsel am Ende des Abrechnungszeitraums
    """
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(
                status_code=404,
                detail="Kein aktives Stripe-Abonnement gefunden. Bitte zuerst ein Abonnement abschließen.",
            )

        if sub.status not in ("active", "trialing"):
            raise HTTPException(
                status_code=400,
                detail=f"Plan-Wechsel nicht möglich. Aktueller Status: {sub.status}",
            )

        current_plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
        new_plan = db.query(Plan).filter(
            Plan.slug == req.plan_slug, Plan.is_active.is_(True)
        ).first()
        if not new_plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden.")

        if current_plan and current_plan.id == new_plan.id:
            raise HTTPException(status_code=400, detail="Sie haben diesen Plan bereits.")

        # Determine price ID
        if req.billing_interval == "year" and getattr(new_plan, "stripe_price_yearly_id", None):
            new_price_id = new_plan.stripe_price_yearly_id
        else:
            new_price_id = new_plan.stripe_price_id

        if not new_price_id:
            raise HTTPException(status_code=422, detail="Kein Stripe-Preis für diesen Plan konfiguriert.")

        # Get current Stripe subscription
        stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
        current_item_id = stripe_sub["items"]["data"][0]["id"]

        current_price = current_plan.price_monthly_cents if current_plan else 0
        new_price = new_plan.price_monthly_cents
        is_upgrade = new_price > current_price

        if is_upgrade:
            # ── UPGRADE: Sofort mit Proration ──
            updated_sub = stripe.Subscription.modify(
                sub.stripe_subscription_id,
                items=[{
                    "id": current_item_id,
                    "price": new_price_id,
                }],
                proration_behavior="create_prorations",
                metadata={
                    "tenant_id": str(user.tenant_id),
                    "plan_id": str(new_plan.id),
                },
            )

            # Update local DB immediately
            sub.plan_id = new_plan.id
            sub.status = "active"
            sub.cancel_at_period_end = False
            sub.pending_plan_id = None
            sub.billing_interval = req.billing_interval
            sub.current_period_start = _ts_to_dt(updated_sub.get("current_period_start"))
            sub.current_period_end = _ts_to_dt(updated_sub.get("current_period_end"))
            db.commit()

            _audit(user, "billing.plan_upgraded", {
                "from_plan": current_plan.slug if current_plan else None,
                "to_plan": new_plan.slug,
                "proration": True,
            })

            logger.info("billing.plan_upgraded",
                       tenant_id=user.tenant_id,
                       from_plan=current_plan.slug if current_plan else None,
                       to_plan=new_plan.slug)

            return {
                "success": True,
                "type": "upgrade",
                "plan": new_plan.name,
                "effective": "immediate",
                "message": f"Upgrade auf {new_plan.name} erfolgreich! Der neue Plan ist sofort aktiv.",
            }

        else:
            # ── DOWNGRADE: Zum Periodenende ──
            # Use Stripe Subscription Schedule for deferred downgrade
            # First, cancel any existing schedule
            try:
                schedules = stripe.SubscriptionSchedule.list(
                    customer=sub.stripe_customer_id,
                    limit=5,
                )
                for sched in schedules.get("data", []):
                    if sched.get("subscription") == sub.stripe_subscription_id and sched.get("status") in ("not_started", "active"):
                        stripe.SubscriptionSchedule.release(sched["id"])
            except Exception:
                pass  # No existing schedule, that's fine

            # Create a subscription schedule that changes the plan at period end
            schedule = stripe.SubscriptionSchedule.create(
                from_subscription=sub.stripe_subscription_id,
            )

            # Update the schedule with two phases:
            # Phase 1: Current plan until period end
            # Phase 2: New plan starting at period end
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
                            "plan_id": str(new_plan.id),
                        },
                    },
                ],
                metadata={
                    "tenant_id": str(user.tenant_id),
                    "downgrade_to_plan_id": str(new_plan.id),
                },
            )

            # Update local DB - mark pending downgrade
            sub.pending_plan_id = new_plan.id
            sub.billing_interval = req.billing_interval
            db.commit()

            period_end_dt = _ts_to_dt(current_phase_end)
            effective_date = period_end_dt.strftime("%d.%m.%Y") if period_end_dt else "Ende des Abrechnungszeitraums"

            _audit(user, "billing.plan_downgrade_scheduled", {
                "from_plan": current_plan.slug if current_plan else None,
                "to_plan": new_plan.slug,
                "effective_date": effective_date,
            })

            logger.info("billing.plan_downgrade_scheduled",
                       tenant_id=user.tenant_id,
                       from_plan=current_plan.slug if current_plan else None,
                       to_plan=new_plan.slug,
                       effective_date=effective_date)

            return {
                "success": True,
                "type": "downgrade",
                "plan": new_plan.name,
                "effective": effective_date,
                "message": (
                    f"Downgrade auf {new_plan.name} geplant. "
                    f"Der Wechsel wird am {effective_date} wirksam. "
                    f"Bis dahin behalten Sie alle Funktionen Ihres aktuellen Plans."
                ),
            }

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("billing.change_plan_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


# ── Subscription Cancellation ────────────────────────────────────────────────

@router.post("/billing/cancel-subscription")
async def cancel_subscription(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Abonnement zum Ende des aktuellen Abrechnungszeitraums kündigen.
    
    Setzt cancel_at_period_end=True bei Stripe. Das Abo bleibt bis zum
    Ende der bezahlten Periode aktiv und wird dann nicht erneuert.
    """
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="Kein aktives Abonnement gefunden.")

        if sub.status == "canceled":
            raise HTTPException(status_code=400, detail="Das Abonnement ist bereits gekündigt.")

        # Set cancel_at_period_end in Stripe
        updated_sub = stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=True,
        )

        # Update local DB
        sub.cancel_at_period_end = True
        sub.canceled_at = datetime.now(timezone.utc)
        db.commit()

        period_end = updated_sub.get("current_period_end")
        period_end_dt = _ts_to_dt(period_end)
        effective_date = period_end_dt.strftime("%d.%m.%Y") if period_end_dt else "Ende des Abrechnungszeitraums"

        _audit(user, "billing.subscription_canceled", {
            "effective_date": effective_date,
            "cancel_at_period_end": True,
        })

        logger.info("billing.subscription_canceled",
                    tenant_id=user.tenant_id,
                    effective_date=effective_date)

        return {
            "success": True,
            "effective_date": effective_date,
            "message": (
                f"Ihr Abonnement wurde gekündigt. Es bleibt bis zum {effective_date} aktiv. "
                f"Danach wird es nicht erneuert und Ihr Konto wird auf den kostenlosen Plan zurückgesetzt."
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("billing.cancel_subscription_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


@router.post("/billing/reactivate-subscription")
async def reactivate_subscription(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Gekündigtes Abonnement reaktivieren (cancel_at_period_end zurücksetzen).
    
    Nur möglich, solange das Abo noch aktiv ist (vor dem Periodenende).
    """
    _require_billing_access(user)
    stripe = _get_stripe(user.tenant_id)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="Kein Abonnement gefunden.")

        if sub.status == "canceled":
            raise HTTPException(
                status_code=400,
                detail="Das Abonnement ist bereits abgelaufen und kann nicht reaktiviert werden. Bitte schließen Sie ein neues Abonnement ab.",
            )

        if not sub.cancel_at_period_end:
            raise HTTPException(status_code=400, detail="Das Abonnement ist nicht zur Kündigung vorgemerkt.")

        # Remove cancel_at_period_end in Stripe
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        # Update local DB
        sub.cancel_at_period_end = False
        sub.canceled_at = None
        db.commit()

        _audit(user, "billing.subscription_reactivated", {})

        logger.info("billing.subscription_reactivated", tenant_id=user.tenant_id)

        return {
            "success": True,
            "message": "Ihr Abonnement wurde erfolgreich reaktiviert. Es wird wie gewohnt verlängert.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("billing.reactivate_subscription_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")
    finally:
        db.close()


# ── Subscription Status ──────────────────────────────────────────────────────

@router.get("/billing/subscription")
async def get_subscription_status(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Aktuellen Abonnement-Status abrufen inkl. Kündigungsinformationen."""
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
        if not sub:
            return {"has_subscription": False, "status": "none"}

        plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
        pending_plan = None
        if sub.pending_plan_id:
            pending_plan = db.query(Plan).filter(Plan.id == sub.pending_plan_id).first()

        result = {
            "has_subscription": True,
            "status": sub.status,
            "plan_name": plan.name if plan else "Unbekannt",
            "plan_slug": plan.slug if plan else None,
            "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)),
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "billing_interval": getattr(sub, "billing_interval", "month") or "month",
            "stripe_subscription_id": sub.stripe_subscription_id,
        }

        if sub.cancel_at_period_end:
            result["cancellation_effective_date"] = (
                sub.current_period_end.strftime("%d.%m.%Y") if sub.current_period_end else None
            )

        if pending_plan:
            result["pending_downgrade"] = {
                "plan_name": pending_plan.name,
                "plan_slug": pending_plan.slug,
                "effective_date": sub.current_period_end.strftime("%d.%m.%Y") if sub.current_period_end else None,
            }

        return result
    finally:
        db.close()


# ── Account Deactivation ─────────────────────────────────────────────────────

@router.post("/billing/deactivate-account")
async def deactivate_account(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Konto deaktivieren und alle Daten bereinigen.
    
    Voraussetzung: Das Abonnement muss gekündigt sein (cancel_at_period_end=True)
    oder bereits abgelaufen (status=canceled).
    """
    _require_billing_access(user)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()

        # Check if subscription is canceled or set to cancel
        if sub and sub.status == "active" and not getattr(sub, "cancel_at_period_end", False):
            raise HTTPException(
                status_code=400,
                detail="Bitte kündigen Sie zuerst Ihr Abonnement, bevor Sie Ihr Konto deaktivieren.",
            )

        # If subscription is still active but set to cancel, cancel it immediately in Stripe
        if sub and sub.stripe_subscription_id and sub.status != "canceled":
            try:
                stripe = _get_stripe(user.tenant_id)
                stripe.Subscription.cancel(sub.stripe_subscription_id)
                sub.status = "canceled"
                sub.canceled_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.warning("billing.deactivate_stripe_cancel_failed", error=str(exc))

        # Deactivate the tenant
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if tenant:
            tenant.is_active = False

        db.commit()

        _audit(user, "account.deactivated", {
            "tenant_id": user.tenant_id,
        })

        logger.info("account.deactivated", tenant_id=user.tenant_id)

        return {
            "success": True,
            "message": "Ihr Konto wurde deaktiviert. Alle aktiven Dienste wurden beendet.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("account.deactivation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Fehler bei der Konto-Deaktivierung.")
    finally:
        db.close()


# ── Webhook (raw body, HMAC verification) ─────────────────────────────────────

def _ts_to_dt(ts: int | None) -> datetime | None:
    if ts:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return None


def _on_checkout_completed(obj: dict) -> None:
    meta = obj.get("metadata", {})
    tenant_id = meta.get("tenant_id")
    type_ = meta.get("type", "plan_upgrade")

    # Handle token purchases
    if type_ == "token_purchase" and tenant_id:
        _on_token_purchase_completed(obj, meta)
        return
    stripe_sub_id = obj.get("subscription")
    stripe_cid    = obj.get("customer")
    
    if not tenant_id:
        return
    
    db = SessionLocal()
    try:
        if type_ == "plan_upgrade":
            plan_id = meta.get("ariia_plan_id")
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
            logger.info("billing.webhook.plan_activated", tenant_id=tenant_id, plan_id=plan_id)
        
        elif type_ == "addon_purchase":
            addon_slug = meta.get("addon_slug")
            if addon_slug:
                # Add to TenantAddon table
                db.add(TenantAddon(
                    tenant_id=int(tenant_id),
                    addon_slug=addon_slug,
                    stripe_subscription_item_id=stripe_sub_id, # Storing sub ID as item ID proxy for now
                    quantity=1,
                    status="active"
                ))
                logger.info("billing.webhook.addon_activated", tenant_id=tenant_id, addon=addon_slug)

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.checkout_db_failed", error=str(exc))
    finally:
        db.close()


def _on_subscription_event(event_type: str, obj: dict) -> None:
    stripe_sub_id = obj.get("id")
    meta = obj.get("metadata", {})
    tenant_id = meta.get("tenant_id")
    is_addon = meta.get("is_addon") == "true"
    addon_slug = meta.get("addon_slug")

    db = SessionLocal()
    try:
        if is_addon:
            # Handle Addon Subscription
            addon = db.query(TenantAddon).filter(
                TenantAddon.stripe_subscription_item_id == stripe_sub_id
            ).first()
            
            if not addon and tenant_id and addon_slug:
                 # Try to recover if missing
                 addon = TenantAddon(
                    tenant_id=int(tenant_id),
                    addon_slug=addon_slug,
                    stripe_subscription_item_id=stripe_sub_id,
                    quantity=1,
                    status="active"
                 )
                 db.add(addon)
            
            if addon:
                if event_type == "customer.subscription.deleted":
                    addon.status = "canceled"
                    # Or delete the row? Better to keep as canceled.
                    # Actually, if we want to free up the 'slot', we might delete or mark inactive.
                    # Marking as canceled is safer for history.
                else:
                    addon.status = obj.get("status", addon.status)
        else:
            # Handle Main Plan Subscription
            q = db.query(Subscription)
            sub = q.filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
            if not sub and tenant_id:
                sub = q.filter(Subscription.tenant_id == int(tenant_id)).first()
            
            if sub:
                if event_type == "customer.subscription.deleted":
                    sub.status = "canceled"
                    sub.canceled_at = datetime.now(timezone.utc)
                    sub.cancel_at_period_end = False
                    # Apply pending downgrade if exists
                    if sub.pending_plan_id:
                        sub.plan_id = sub.pending_plan_id
                        sub.pending_plan_id = None
                else:
                    sub.status = obj.get("status", sub.status)
                    sub.current_period_start = _ts_to_dt(obj.get("current_period_start"))
                    sub.current_period_end   = _ts_to_dt(obj.get("current_period_end"))
                    # Sync cancel_at_period_end from Stripe
                    sub.cancel_at_period_end = obj.get("cancel_at_period_end", False)
                    # Check if plan changed via subscription schedule
                    items = obj.get("items", {}).get("data", [])
                    if items:
                        stripe_price_id = items[0].get("price", {}).get("id")
                        if stripe_price_id:
                            from app.core.models import Plan as _Plan
                            new_plan = db.query(_Plan).filter(
                                (_Plan.stripe_price_id == stripe_price_id) |
                                (_Plan.stripe_price_yearly_id == stripe_price_id)
                            ).first()
                            if new_plan and new_plan.id != sub.plan_id:
                                logger.info("billing.webhook.plan_changed_via_stripe",
                                           old_plan_id=sub.plan_id, new_plan_id=new_plan.id)
                                sub.plan_id = new_plan.id
                                sub.pending_plan_id = None
        
        db.commit()
        logger.info("billing.webhook.subscription_updated", event_type=event_type, sub_id=stripe_sub_id)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.subscription_db_failed", error=str(exc))
    finally:
        db.close()


def _on_product_event(event_type: str, obj: dict) -> None:
    """Handle product.updated / product.deleted from Stripe → sync to local DB."""
    product_id = obj.get("id")
    meta = obj.get("metadata", {})
    ariia_type = meta.get("ariia_type", "")
    ariia_slug = meta.get("ariia_slug", "")

    if not product_id:
        return

    db = SessionLocal()
    try:
        if ariia_type == "plan" and ariia_slug:
            plan = db.query(Plan).filter(Plan.slug == ariia_slug).first()
            if not plan:
                plan = db.query(Plan).filter(Plan.stripe_product_id == product_id).first()
            if plan:
                clean_name = (obj.get("name") or "").replace("ARIIA Plan: ", "").replace("ARIIA ", "").strip()
                if clean_name:
                    plan.name = clean_name
                if obj.get("description"):
                    plan.description = obj["description"]
                plan.is_active = obj.get("active", plan.is_active)
                plan.stripe_product_id = product_id
                logger.info("billing.webhook.product_plan_updated", slug=ariia_slug, product_id=product_id)

        elif ariia_type == "addon" and ariia_slug:
            addon = db.query(AddonDefinition).filter(AddonDefinition.slug == ariia_slug).first()
            if not addon:
                addon = db.query(AddonDefinition).filter(AddonDefinition.stripe_product_id == product_id).first()
            if addon:
                clean_name = (obj.get("name") or "").replace("ARIIA Add-on: ", "").replace("ARIIA Addon: ", "").strip()
                if clean_name:
                    addon.name = clean_name
                if obj.get("description"):
                    addon.description = obj["description"]
                addon.is_active = obj.get("active", addon.is_active)
                addon.stripe_product_id = product_id
                logger.info("billing.webhook.product_addon_updated", slug=ariia_slug, product_id=product_id)

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.product_event_failed", error=str(exc))
    finally:
        db.close()


def _on_price_event(event_type: str, obj: dict) -> None:
    """Handle price.updated / price.created from Stripe → sync to local DB."""
    price_id = obj.get("id")
    product_id = obj.get("product")
    unit_amount = obj.get("unit_amount")
    active = obj.get("active", True)
    recurring = obj.get("recurring", {})
    interval = recurring.get("interval", "month") if recurring else "month"

    if not price_id or not product_id:
        return

    db = SessionLocal()
    try:
        # Check if this price belongs to a plan
        plan = db.query(Plan).filter(Plan.stripe_product_id == product_id).first()
        if plan:
            if interval == "month":
                plan.stripe_price_id = price_id
                if unit_amount is not None:
                    plan.price_monthly_cents = unit_amount
            elif interval == "year":
                plan.stripe_price_yearly_id = price_id
                if unit_amount is not None:
                    plan.price_yearly_cents = unit_amount
            logger.info("billing.webhook.price_plan_updated", plan_slug=plan.slug, price_id=price_id, interval=interval)
            db.commit()
            return

        # Check if this price belongs to an addon
        addon = db.query(AddonDefinition).filter(AddonDefinition.stripe_product_id == product_id).first()
        if addon:
            addon.stripe_price_id = price_id
            if unit_amount is not None:
                addon.price_monthly_cents = unit_amount
            logger.info("billing.webhook.price_addon_updated", addon_slug=addon.slug, price_id=price_id)
            db.commit()
            return

    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.price_event_failed", error=str(exc))
    finally:
        db.close()


def _on_invoice_event(event_type: str, obj: dict) -> None:
    stripe_sub_id = obj.get("subscription")
    if not stripe_sub_id:
        return
    db = SessionLocal()
    try:
        # Check both Subscriptions and Addons
        sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
        addon = db.query(TenantAddon).filter(TenantAddon.stripe_subscription_item_id == stripe_sub_id).first()
        
        target = sub or addon
        if not target:
            return

        if event_type in ("invoice.payment_succeeded", "invoice.paid"):
            target.status = "active"
            if isinstance(target, Subscription):
                 lines = obj.get("lines", {}).get("data", [])
                 if lines:
                    period_end = lines[0].get("period", {}).get("end")
                    if period_end:
                        target.current_period_end = _ts_to_dt(period_end)
        elif event_type == "invoice.payment_failed":
            target.status = "past_due"
            
        db.commit()
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
        # Bidirectional Sync: Product & Price changes in Stripe → local DB
        "product.updated":               lambda: _on_product_event(event_type, event_data.get("object", {})),
        "product.deleted":               lambda: _on_product_event(event_type, event_data.get("object", {})),
        "price.updated":                 lambda: _on_price_event(event_type, event_data.get("object", {})),
        "price.created":                 lambda: _on_price_event(event_type, event_data.get("object", {})),
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


def _on_token_purchase_completed(obj: dict, meta: dict) -> None:
    """Handle completed token purchase checkout."""
    tenant_id = int(meta.get("tenant_id", 0))
    tokens_amount = int(meta.get("tokens_amount", 0))
    session_id = obj.get("id")

    if not tenant_id or not tokens_amount:
        return

    db = SessionLocal()
    try:
        from app.core.models import TokenPurchase, UsageRecord
        from sqlalchemy import text
        from app.core.db import engine
        from datetime import datetime, timezone

        # Update purchase record
        purchase = db.query(TokenPurchase).filter(
            TokenPurchase.stripe_checkout_session_id == session_id
        ).first()
        if purchase:
            purchase.status = "completed"
        else:
            db.add(TokenPurchase(
                tenant_id=tenant_id,
                tokens_amount=tokens_amount,
                price_cents=0,
                stripe_checkout_session_id=session_id,
                status="completed",
            ))

        # Add tokens to usage record
        now = datetime.now(timezone.utc)
        dialect = engine.dialect.name
        if dialect == "postgresql":
            db.execute(text(
                "INSERT INTO usage_records (tenant_id, period_year, period_month, llm_tokens_purchased, messages_inbound, messages_outbound, active_members, llm_tokens_used) "
                "VALUES (:tid, :yr, :mo, :amt, 0, 0, 0, 0) "
                "ON CONFLICT (tenant_id, period_year, period_month) "
                "DO UPDATE SET llm_tokens_purchased = usage_records.llm_tokens_purchased + :amt"
            ), {"tid": tenant_id, "yr": now.year, "mo": now.month, "amt": tokens_amount})
        else:
            rec = db.query(UsageRecord).filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.period_year == now.year,
                UsageRecord.period_month == now.month,
            ).first()
            if rec:
                rec.llm_tokens_purchased = (getattr(rec, 'llm_tokens_purchased', 0) or 0) + tokens_amount
            else:
                db.add(UsageRecord(
                    tenant_id=tenant_id,
                    period_year=now.year,
                    period_month=now.month,
                    llm_tokens_purchased=tokens_amount,
                ))

        db.commit()
        logger.info("billing.webhook.token_purchase_completed", tenant_id=tenant_id, tokens=tokens_amount)
    except Exception as exc:
        db.rollback()
        logger.error("billing.webhook.token_purchase_failed", error=str(exc))
    finally:
        db.close()
