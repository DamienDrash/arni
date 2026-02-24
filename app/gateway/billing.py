"""app/gateway/billing.py — Stripe Billing Engine (K2 / S4.2).

Endpoints:
    GET  /billing/plans                → Öffentlicher Plan-Katalog (4 Tiers + Add-ons)
    GET  /billing/addons               → Verfügbare Add-ons
    POST /billing/checkout-session     → Stripe Checkout für Plan-Upgrade
    POST /billing/addon-checkout       → Stripe Checkout für Add-on-Kauf
    POST /billing/change-plan          → Plan-Wechsel (Up/Downgrade) via Stripe
    POST /billing/change-interval      → Wechsel monatlich ↔ jährlich
    POST /billing/customer-portal      → Stripe Customer Portal
    POST /billing/report-usage         → Overage-Metering an Stripe melden
    POST /billing/webhook              → Stripe Webhook (HMAC-verifiziert)

Plans:
    Starter (79 €/mo)      – 1 Kanal, 500 Konversationen, Basic AI, 1 User
    Professional (199 €/mo) – 3 Kanäle, 2.000 Konversationen, Full AI, 5 Users
    Business (399 €/mo)     – Alle Kanäle, 10.000 Konversationen, Priority, 15 Users
    Enterprise (Custom)     – Unlimited, SLA, Dedicated Support, On-Premise

Add-ons:
    Churn Prediction (+49 €), Voice Pipeline (+79 €), Vision AI (+39 €),
    Extra Channel (+29 €), Extra Conversations (+19 €), Extra User (+15 €),
    White-Label (+149 €), API Access (+99 €), Extra Connector (+49 €)
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
from app.core.models import Plan, PlanAddon, Subscription, TenantAddon, Tenant, AuditLog
from app.gateway.persistence import persistence

logger = structlog.get_logger()

router = APIRouter(prefix="/billing", tags=["billing"])

# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_stripe_client(tenant_id: int):
    """Return a configured Stripe client using the system-level secret key."""
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
    """Find or create a Stripe customer for this tenant."""
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
        customer_id = customer["id"]

        if sub:
            sub.stripe_customer_id = customer_id
            db.commit()
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
        logger.warning("billing.audit_write_failed", error=str(exc))
        db.rollback()
    finally:
        db.close()


def _format_plan_for_catalog(plan: Plan) -> dict[str, Any]:
    """Format a Plan DB row for the public catalog endpoint."""
    import json

    features_list = []
    channel_names = {
        "whatsapp_enabled": "WhatsApp",
        "telegram_enabled": "Telegram",
        "sms_enabled": "SMS",
        "email_channel_enabled": "E-Mail",
        "voice_enabled": "Voice",
        "instagram_enabled": "Instagram DM",
        "facebook_enabled": "Facebook Messenger",
        "google_business_enabled": "Google Business",
    }
    channels = [name for key, name in channel_names.items() if getattr(plan, key, False)]
    if channels:
        features_list.append(", ".join(channels[:3]) + (" + mehr" if len(channels) > 3 else ""))

    if plan.max_members is None:
        features_list.append("Unbegrenzte Mitglieder")
    else:
        features_list.append(f"Bis zu {plan.max_members:,} Mitglieder")

    if plan.max_monthly_messages is None:
        features_list.append("Unbegrenzte Konversationen")
    else:
        features_list.append(f"{plan.max_monthly_messages:,} Konversationen/Monat")

    if plan.max_users is None:
        features_list.append("Unbegrenzte Users")
    elif plan.max_users > 1:
        features_list.append(f"{plan.max_users} Users")

    # AI tier
    ai_labels = {"basic": "Basic AI (GPT-4.1 Nano)", "standard": "Standard AI (GPT-4.1 Mini)",
                 "premium": "Premium AI (GPT-4.1 + Gemini)", "unlimited": "Alle AI-Modelle + eigene Keys"}
    features_list.append(ai_labels.get(plan.ai_tier, "Basic AI"))

    if plan.max_monthly_llm_tokens is None:
        features_list.append("Unbegrenzte LLM-Tokens")
    else:
        features_list.append(f"{plan.max_monthly_llm_tokens:,} LLM-Tokens/Monat")

    if getattr(plan, "memory_analyzer_enabled", False):
        features_list.append("Member Memory Analyzer")
    if getattr(plan, "automation_enabled", False):
        features_list.append("Automation Engine")
    if getattr(plan, "churn_prediction_enabled", False):
        features_list.append("Churn Prediction (ML)")
    if getattr(plan, "priority_support", False):
        features_list.append("Priority Support")
    if getattr(plan, "dedicated_support", False):
        features_list.append("Dedicated Support + SLA")

    # Connectors
    conn_count = sum(1 for k in ["connector_magicline_enabled", "connector_shopify_enabled",
                                  "connector_woocommerce_enabled", "connector_hubspot_enabled"]
                     if getattr(plan, k, False))
    if plan.max_connectors and plan.max_connectors > 0:
        if plan.max_connectors >= 99:
            features_list.append("Alle Connectors inklusive")
        else:
            features_list.append(f"{plan.max_connectors} Connector frei wählbar")

    # Parse allowed models
    allowed_models = None
    if plan.allowed_llm_models:
        try:
            allowed_models = json.loads(plan.allowed_llm_models)
        except Exception:
            allowed_models = ["gpt-4.1-nano"]

    return {
        "slug": plan.slug,
        "name": plan.name,
        "price_monthly_cents": plan.price_monthly_cents,
        "price_yearly_cents": plan.price_yearly_cents,
        "is_custom_pricing": plan.is_custom_pricing,
        "max_members": plan.max_members,
        "max_monthly_messages": plan.max_monthly_messages,
        "max_channels": plan.max_channels if plan.max_channels and plan.max_channels < 99 else None,
        "max_users": plan.max_users,
        "max_connectors": plan.max_connectors if plan.max_connectors and plan.max_connectors < 99 else None,
        "max_monthly_llm_tokens": plan.max_monthly_llm_tokens,
        "ai_tier": plan.ai_tier,
        "allowed_llm_models": allowed_models,
        "features": features_list,
        "highlight": plan.slug == "professional",
        "sort_order": plan.sort_order,
        "stripe_price_id": plan.stripe_price_id,
        "stripe_price_id_yearly": plan.stripe_price_id_yearly,
        # Overage pricing
        "overage": {
            "per_conversation_cents": plan.overage_per_conversation_cents,
            "per_user_cents": plan.overage_per_user_cents,
            "per_connector_cents": plan.overage_per_connector_cents,
            "per_channel_cents": plan.overage_per_channel_cents,
        },
    }


# ── Plan & Add-on Catalog ────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans() -> list[dict[str, Any]]:
    """Öffentlicher Plan-Katalog — liest aus DB statt Hardcode."""
    db = SessionLocal()
    try:
        plans = db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.sort_order).all()
        return [_format_plan_for_catalog(p) for p in plans]
    finally:
        db.close()


@router.get("/addons")
async def list_addons() -> list[dict[str, Any]]:
    """Verfügbare Add-ons für Zukauf."""
    db = SessionLocal()
    try:
        addons = db.query(PlanAddon).filter(PlanAddon.is_active.is_(True)).order_by(PlanAddon.sort_order).all()
        return [
            {
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "category": a.category,
                "price_monthly_cents": a.price_monthly_cents,
                "is_per_unit": a.is_per_unit,
                "unit_label": a.unit_label,
                "min_plan_slug": a.min_plan_slug,
                "stripe_price_id": a.stripe_price_id,
            }
            for a in addons
        ]
    finally:
        db.close()


# ── Checkout Endpoints ────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    plan_slug: str
    billing_interval: str = "monthly"  # "monthly" | "yearly"
    success_url: str = ""
    cancel_url: str = ""


@router.post("/checkout-session")
async def create_checkout_session(
    req: CheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Checkout Session für Plan-Upgrade."""
    _require_tenant_admin(user)
    stripe = _get_stripe_client(user.tenant_id)

    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.slug == req.plan_slug, Plan.is_active.is_(True)).first()
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.plan_slug}' nicht gefunden")

        if plan.is_custom_pricing:
            raise HTTPException(
                status_code=422,
                detail="Enterprise-Plan erfordert individuelle Vereinbarung. Bitte kontaktiere unser Sales-Team.",
            )

        # Select price ID based on billing interval
        if req.billing_interval == "yearly" and plan.stripe_price_id_yearly:
            price_id = plan.stripe_price_id_yearly
        elif plan.stripe_price_id:
            price_id = plan.stripe_price_id
        else:
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

    stripe_customer_id = _get_or_create_stripe_customer(
        stripe, tenant_id=user.tenant_id, tenant_name=tenant_name, admin_email=user.email,
    )

    base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
    success_url = req.success_url or f"{base_url}/settings/billing?checkout=success"
    cancel_url = req.cancel_url or f"{base_url}/settings/billing?checkout=canceled"

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=stripe_customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            metadata={
                "tenant_id": str(user.tenant_id),
                "plan_slug": req.plan_slug,
                "ariia_plan_id": str(plan.id),
                "billing_interval": req.billing_interval,
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(user.tenant_id),
                    "plan_id": str(plan.id),
                    "billing_interval": req.billing_interval,
                }
            },
        )
    except Exception as exc:
        logger.error("billing.checkout_session_failed", error=str(exc), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    _write_audit_event(user, "billing.checkout_session_created", {
        "plan_slug": req.plan_slug,
        "billing_interval": req.billing_interval,
        "stripe_session_id": session.get("id"),
    })

    return {"url": session["url"]}


class AddonCheckoutRequest(BaseModel):
    addon_slug: str
    quantity: int = 1
    success_url: str = ""
    cancel_url: str = ""


@router.post("/addon-checkout")
async def create_addon_checkout(
    req: AddonCheckoutRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Erstellt eine Stripe Checkout Session für ein Add-on."""
    _require_tenant_admin(user)
    stripe = _get_stripe_client(user.tenant_id)

    db = SessionLocal()
    try:
        addon = db.query(PlanAddon).filter(PlanAddon.slug == req.addon_slug, PlanAddon.is_active.is_(True)).first()
        if not addon:
            raise HTTPException(status_code=404, detail=f"Add-on '{req.addon_slug}' nicht gefunden")

        if not addon.stripe_price_id:
            raise HTTPException(status_code=422, detail=f"Add-on '{req.addon_slug}' hat keine Stripe Price-ID")

        # Check minimum plan requirement
        if addon.min_plan_slug:
            from app.core.feature_gates import PLAN_HIERARCHY
            sub = db.query(Subscription).filter(
                Subscription.tenant_id == user.tenant_id,
                Subscription.status.in_(["active", "trialing"]),
            ).first()
            current_plan = "starter"
            if sub:
                plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
                if plan:
                    current_plan = plan.slug
            current_idx = PLAN_HIERARCHY.index(current_plan) if current_plan in PLAN_HIERARCHY else 0
            required_idx = PLAN_HIERARCHY.index(addon.min_plan_slug) if addon.min_plan_slug in PLAN_HIERARCHY else 0
            if current_idx < required_idx:
                raise HTTPException(
                    status_code=402,
                    detail=f"Add-on '{addon.name}' erfordert mindestens den {addon.min_plan_slug.title()}-Plan.",
                )

        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_name = tenant.name if tenant else "Tenant"
    finally:
        db.close()

    stripe_customer_id = _get_or_create_stripe_customer(
        stripe, tenant_id=user.tenant_id, tenant_name=tenant_name, admin_email=user.email,
    )

    base_url = (persistence.get_setting("gateway_public_url", "") or "").rstrip("/")
    success_url = req.success_url or f"{base_url}/settings/billing?addon_checkout=success"
    cancel_url = req.cancel_url or f"{base_url}/settings/billing?addon_checkout=canceled"

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=stripe_customer_id,
            line_items=[{"price": addon.stripe_price_id, "quantity": req.quantity}],
            success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(user.tenant_id),
                "addon_slug": req.addon_slug,
                "addon_id": str(addon.id),
                "quantity": str(req.quantity),
                "type": "addon",
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(user.tenant_id),
                    "addon_id": str(addon.id),
                    "type": "addon",
                }
            },
        )
    except Exception as exc:
        logger.error("billing.addon_checkout_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    _write_audit_event(user, "billing.addon_checkout_created", {
        "addon_slug": req.addon_slug,
        "quantity": req.quantity,
    })

    return {"url": session["url"]}


class ChangePlanRequest(BaseModel):
    new_plan_slug: str
    billing_interval: str = "monthly"


@router.post("/change-plan")
async def change_plan(
    req: ChangePlanRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Plan-Wechsel (Upgrade/Downgrade) über Stripe Subscription Update.

    Stripe prorate automatisch — bei Upgrade wird sofort abgerechnet,
    bei Downgrade wird das Guthaben auf die nächste Rechnung angerechnet.
    """
    _require_tenant_admin(user)
    stripe = _get_stripe_client(user.tenant_id)

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.tenant_id == user.tenant_id,
            Subscription.status.in_(["active", "trialing"]),
        ).first()
        if not sub or not sub.stripe_subscription_id:
            raise HTTPException(
                status_code=404,
                detail="Kein aktives Abonnement gefunden. Bitte zuerst einen Plan buchen.",
            )

        new_plan = db.query(Plan).filter(Plan.slug == req.new_plan_slug, Plan.is_active.is_(True)).first()
        if not new_plan:
            raise HTTPException(status_code=404, detail=f"Plan '{req.new_plan_slug}' nicht gefunden")

        if new_plan.is_custom_pricing:
            raise HTTPException(status_code=422, detail="Enterprise-Plan erfordert individuelle Vereinbarung.")

        # Select price ID
        if req.billing_interval == "yearly" and new_plan.stripe_price_id_yearly:
            new_price_id = new_plan.stripe_price_id_yearly
        elif new_plan.stripe_price_id:
            new_price_id = new_plan.stripe_price_id
        else:
            raise HTTPException(status_code=422, detail="Plan hat keine Stripe Price-ID")

        stripe_sub_id = sub.stripe_subscription_id
    finally:
        db.close()

    try:
        # Get current subscription from Stripe
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        current_item_id = stripe_sub["items"]["data"][0]["id"]

        # Update subscription with new price (proration_behavior=create_prorations)
        updated_sub = stripe.Subscription.modify(
            stripe_sub_id,
            items=[{
                "id": current_item_id,
                "price": new_price_id,
            }],
            proration_behavior="create_prorations",
            metadata={
                "tenant_id": str(user.tenant_id),
                "plan_id": str(new_plan.id),
                "billing_interval": req.billing_interval,
            },
        )

        # Update local DB
        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
            if sub:
                sub.plan_id = new_plan.id
            db.commit()
        finally:
            db.close()

    except Exception as exc:
        logger.error("billing.change_plan_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    _write_audit_event(user, "billing.plan_changed", {
        "new_plan_slug": req.new_plan_slug,
        "billing_interval": req.billing_interval,
    })

    return {
        "status": "success",
        "new_plan": req.new_plan_slug,
        "billing_interval": req.billing_interval,
        "message": f"Plan erfolgreich auf {new_plan.name} gewechselt.",
    }


@router.post("/customer-portal")
async def create_customer_portal(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Stripe Customer Portal (Abo verwalten, kündigen, Zahlungsdaten ändern)."""
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
        logger.error("billing.portal_session_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Stripe-Fehler: {exc}")

    return {"url": portal["url"]}


# ── Overage Metering ──────────────────────────────────────────────────────────


@router.post("/report-usage")
async def report_overage_usage(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Report current month's overage to Stripe for metered billing.

    Called periodically (e.g. cron job) or at end of billing period.
    Reports overage conversations and tokens as Stripe usage records.
    """
    _require_tenant_admin(user)
    stripe = _get_stripe_client(user.tenant_id)

    from app.core.feature_gates import FeatureGate
    gate = FeatureGate(user.tenant_id)
    usage = gate._get_current_usage()
    plan = gate.plan_data

    overage_conversations = 0
    max_msgs = plan.get("max_monthly_messages")
    if max_msgs is not None:
        total_msgs = usage.get("messages_inbound", 0) + usage.get("messages_outbound", 0)
        if total_msgs > int(max_msgs):
            overage_conversations = total_msgs - int(max_msgs)

    overage_tokens = 0
    max_tokens = plan.get("max_monthly_llm_tokens")
    if max_tokens is not None:
        used_tokens = usage.get("llm_tokens_used", 0)
        if used_tokens > int(max_tokens):
            overage_tokens = used_tokens - int(max_tokens)

    # Report to Stripe if there's overage
    reported = {"overage_conversations": overage_conversations, "overage_tokens": overage_tokens}

    if overage_conversations > 0 or overage_tokens > 0:
        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).first()
            if sub and sub.stripe_subscription_id:
                # Update local usage record
                from app.core.models import UsageRecord
                now = datetime.now(timezone.utc)
                rec = db.query(UsageRecord).filter(
                    UsageRecord.tenant_id == user.tenant_id,
                    UsageRecord.period_year == now.year,
                    UsageRecord.period_month == now.month,
                ).first()
                if rec:
                    rec.overage_conversations = overage_conversations
                    rec.overage_tokens = overage_tokens
                    # Calculate overage cost
                    conv_cost = overage_conversations * (plan.get("overage_per_conversation_cents") or 0)
                    rec.overage_billed_cents = conv_cost
                    db.commit()

                reported["stripe_reported"] = True
                reported["overage_cost_cents"] = conv_cost if overage_conversations else 0
        except Exception as exc:
            logger.warning("billing.report_usage_failed", error=str(exc))
            reported["stripe_reported"] = False
        finally:
            db.close()

    return reported


# ── Webhook Handlers ──────────────────────────────────────────────────────────


def _handle_checkout_completed(event_data: dict) -> None:
    """Stripe checkout.session.completed → Subscription oder Add-on aktivieren."""
    session = event_data.get("object", {})
    metadata = session.get("metadata", {})
    tenant_id = metadata.get("tenant_id")
    checkout_type = metadata.get("type", "plan")
    stripe_subscription_id = session.get("subscription")
    stripe_customer_id = session.get("customer")

    if not tenant_id:
        logger.warning("billing.webhook.checkout_completed.missing_tenant_id", metadata=metadata)
        return

    db = SessionLocal()
    try:
        if checkout_type == "addon":
            # Add-on checkout
            addon_id = metadata.get("addon_id")
            quantity = int(metadata.get("quantity", 1))
            if addon_id:
                existing = db.query(TenantAddon).filter(
                    TenantAddon.tenant_id == int(tenant_id),
                    TenantAddon.addon_id == int(addon_id),
                ).first()
                if existing:
                    existing.quantity += quantity
                    existing.status = "active"
                    existing.stripe_subscription_item_id = stripe_subscription_id
                else:
                    db.add(TenantAddon(
                        tenant_id=int(tenant_id),
                        addon_id=int(addon_id),
                        quantity=quantity,
                        status="active",
                        stripe_subscription_item_id=stripe_subscription_id,
                        activated_at=datetime.now(timezone.utc),
                    ))
                db.commit()
                logger.info("billing.webhook.addon_activated",
                            tenant_id=tenant_id, addon_id=addon_id, quantity=quantity)
        else:
            # Plan checkout
            plan_id = metadata.get("ariia_plan_id")
            if not plan_id:
                logger.warning("billing.webhook.checkout_completed.missing_plan_id", metadata=metadata)
                return

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
    metadata = sub_obj.get("metadata", {})
    tenant_id = metadata.get("tenant_id")

    period_start_ts = sub_obj.get("current_period_start")
    period_end_ts = sub_obj.get("current_period_end")

    def _ts(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

    db = SessionLocal()
    try:
        q = db.query(Subscription)
        if stripe_sub_id:
            sub = q.filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
        elif tenant_id:
            sub = q.filter(Subscription.tenant_id == int(tenant_id)).first()
        else:
            return

        if not sub:
            # Check if it's an add-on subscription
            addon = db.query(TenantAddon).filter(
                TenantAddon.stripe_subscription_item_id == stripe_sub_id,
            ).first()
            if addon:
                if event_type == "customer.subscription.deleted":
                    addon.status = "canceled"
                    addon.canceled_at = datetime.now(timezone.utc)
                db.commit()
            return

        if event_type == "customer.subscription.deleted":
            sub.status = "canceled"
            sub.canceled_at = datetime.now(timezone.utc)
            # Downgrade to Starter
            starter = db.query(Plan).filter(Plan.slug == "starter", Plan.is_active.is_(True)).first()
            if starter:
                sub.plan_id = starter.id
        else:
            sub.status = stripe_status
            sub.current_period_start = _ts(period_start_ts)
            sub.current_period_end = _ts(period_end_ts)
            # Update plan if changed
            plan_id = metadata.get("plan_id")
            if plan_id:
                sub.plan_id = int(plan_id)

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
    """Stripe Webhook Endpoint — HMAC-verifiziert, verarbeitet alle relevanten Events."""
    try:
        import stripe as _stripe
    except ImportError:
        return Response(content="stripe not installed", status_code=500)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    webhook_secret = (persistence.get_setting("billing_stripe_webhook_secret", "") or "").strip()
    if not webhook_secret:
        logger.warning("billing.webhook.received_without_secret")
        return Response(content="webhook_secret not configured", status_code=400)

    secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
    _stripe.api_key = secret_key

    try:
        event = _stripe.Webhook.construct_event(
            payload=payload, sig_header=sig_header, secret=webhook_secret,
        )
    except ValueError:
        return Response(content="invalid payload", status_code=400)
    except Exception as exc:
        logger.warning("billing.webhook.signature_invalid", error=str(exc))
        return Response(content="invalid signature", status_code=400)

    event_type = event.get("type", "")
    event_data = event.get("data", {})

    logger.info("billing.webhook.received", event_type=event_type, event_id=event.get("id"))

    HANDLERS = {
        "checkout.session.completed": lambda: _handle_checkout_completed(event_data),
        "customer.subscription.updated": lambda: _handle_subscription_event(event_type, event_data),
        "customer.subscription.deleted": lambda: _handle_subscription_event(event_type, event_data),
        "invoice.payment_succeeded": lambda: _handle_invoice_event(event_type, event_data),
        "invoice.payment_failed": lambda: _handle_invoice_event(event_type, event_data),
    }

    handler = HANDLERS.get(event_type)
    if handler:
        try:
            handler()
        except Exception as exc:
            logger.error("billing.webhook.handler_failed", event_type=event_type, error=str(exc))
    else:
        logger.debug("billing.webhook.event_ignored", event_type=event_type)

    return Response(
        content=_json.dumps({"received": True}),
        status_code=200,
        media_type="application/json",
    )
