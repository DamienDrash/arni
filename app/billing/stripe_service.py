"""
ARIIA Billing V2 – Stripe Service

Centralized Stripe communication layer. All Stripe API calls go through
this service, which provides:
- Customer management (create, retrieve, update)
- Checkout session creation
- Subscription management (create, update, cancel)
- Product/Price synchronization (bidirectional)
- Invoice retrieval
- Coupon management

This replaces the scattered Stripe calls in V1 (billing_sync.py,
billing_service.py, billing.py router).

Usage:
    from app.billing.stripe_service import stripe_service

    customer = await stripe_service.get_or_create_customer(db, tenant_id=42)
    session = await stripe_service.create_checkout_session(
        plan_slug="professional",
        customer_id=customer["id"],
        success_url="https://ariia.ai/billing/success",
    )
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.billing.events import billing_events
from app.billing.models import (
    AddonDefinitionV2,
    BillingEventType,
    BillingInterval,
    InvoiceRecord,
    PlanV2,
    SubscriptionV2,
)
from app.billing.stripe_repository import stripe_billing_repository

logger = structlog.get_logger()


def _get_stripe():
    """Get configured Stripe module. Raises ImportError or ValueError."""
    try:
        import stripe as _stripe
    except ImportError:
        raise ImportError("stripe library not installed. Run: pip install stripe")

    from app.gateway.persistence import persistence

    enabled = (persistence.get_setting("billing_stripe_enabled", "false") or "").lower() == "true"
    if not enabled:
        raise ValueError("Stripe ist nicht aktiviert.")

    secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
    if not secret_key:
        raise ValueError("Stripe-Secret-Key nicht konfiguriert.")

    _stripe.api_key = secret_key
    return _stripe


class StripeServiceV2:
    """
    Centralized Stripe API service for the V2 billing system.
    """

    # ── Customer Management ─────────────────────────────────────────────

    async def get_or_create_customer(
        self,
        db: Session,
        tenant_id: int,
        email: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get existing or create new Stripe customer for a tenant.

        Checks the subscription table for an existing customer_id first.
        """
        stripe = _get_stripe()

        sub = stripe_billing_repository.get_subscription_by_tenant(db, tenant_id)
        if sub and sub.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(sub.stripe_customer_id)
                return {
                    "id": customer.id,
                    "email": customer.email,
                    "name": customer.name,
                    "action": "retrieved",
                }
            except Exception:
                pass  # Customer might have been deleted, create new

        # Get tenant info for defaults
        if not email or not name:
            tenant = stripe_billing_repository.get_tenant_by_id(db, tenant_id)
            if tenant:
                email = email or getattr(tenant, "admin_email", None)
                name = name or getattr(tenant, "name", f"Tenant {tenant_id}")

        customer = stripe.Customer.create(
            email=email,
            name=name or f"Tenant {tenant_id}",
            metadata={"tenant_id": str(tenant_id), "platform": "ariia"},
        )

        # Store customer ID
        if sub:
            sub.stripe_customer_id = customer.id
            db.commit()

        logger.info("billing.stripe.customer_created", tenant_id=tenant_id, customer_id=customer.id)

        return {
            "id": customer.id,
            "email": customer.email,
            "name": customer.name,
            "action": "created",
        }

    # ── Checkout Sessions ───────────────────────────────────────────────

    async def create_checkout_session(
        self,
        db: Session,
        tenant_id: int,
        plan_slug: str,
        billing_interval: BillingInterval = BillingInterval.MONTH,
        success_url: str = "https://www.ariia.ai/settings/billing?success=true",
        cancel_url: str = "https://www.ariia.ai/settings/billing?canceled=true",
        customer_id: Optional[str] = None,
        customer_email: Optional[str] = None,
        coupon_code: Optional[str] = None,
        trial_days: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Create a Stripe Checkout Session for a plan subscription.
        """
        stripe = _get_stripe()

        plan = stripe_billing_repository.get_active_plan_by_slug(db, plan_slug)
        if not plan:
            raise ValueError(f"Plan '{plan_slug}' nicht gefunden.")

        # Determine price ID based on interval
        if billing_interval == BillingInterval.YEAR:
            price_id = plan.stripe_price_yearly_id
        else:
            price_id = plan.stripe_price_monthly_id

        if not price_id:
            raise ValueError(f"Kein Stripe-Preis für Plan '{plan_slug}' ({billing_interval.value}) konfiguriert.")

        # Get or create customer
        if not customer_id:
            customer_data = await self.get_or_create_customer(db, tenant_id, email=customer_email)
            customer_id = customer_data["id"]

        session_params: dict[str, Any] = {
            "mode": "subscription",
            "customer": customer_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "tenant_id": str(tenant_id),
                "plan_slug": plan_slug,
                "billing_interval": billing_interval.value,
                "checkout_type": "subscription",
            },
            "subscription_data": {
                "metadata": {
                    "tenant_id": str(tenant_id),
                    "plan_slug": plan_slug,
                },
            },
        }

        # Trial
        effective_trial = trial_days if trial_days is not None else plan.trial_days
        if effective_trial > 0:
            session_params["subscription_data"]["trial_period_days"] = effective_trial

        # Coupon
        if coupon_code:
            session_params["discounts"] = [{"coupon": coupon_code}]

        session = stripe.checkout.Session.create(**session_params)

        logger.info(
            "billing.stripe.checkout_created",
            tenant_id=tenant_id,
            plan_slug=plan_slug,
            session_id=session.id,
        )

        return {
            "session_id": session.id,
            "url": session.url,
            "status": session.status,
        }

    # ── Addon Checkout ──────────────────────────────────────────────────

    async def create_addon_checkout(
        self,
        db: Session,
        tenant_id: int,
        addon_slug: str,
        quantity: int = 1,
        success_url: str = "https://www.ariia.ai/settings/billing?addon_success=true",
        cancel_url: str = "https://www.ariia.ai/settings/billing?canceled=true",
    ) -> dict[str, Any]:
        """Create a checkout session for an addon purchase."""
        stripe = _get_stripe()

        addon = stripe_billing_repository.get_active_addon_by_slug(db, addon_slug)
        if not addon:
            raise ValueError(f"Addon '{addon_slug}' nicht gefunden.")

        if not addon.stripe_price_id:
            raise ValueError(f"Kein Stripe-Preis für Addon '{addon_slug}' konfiguriert.")

        customer_data = await self.get_or_create_customer(db, tenant_id)

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_data["id"],
            line_items=[{"price": addon.stripe_price_id, "quantity": quantity}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(tenant_id),
                "addon_slug": addon_slug,
                "quantity": str(quantity),
                "checkout_type": "addon",
            },
        )

        return {
            "session_id": session.id,
            "url": session.url,
            "status": session.status,
        }

    # ── Token Purchase ──────────────────────────────────────────────────

    async def create_token_purchase_checkout(
        self,
        db: Session,
        tenant_id: int,
        tokens_amount: int,
        price_cents: int,
        success_url: str = "https://www.ariia.ai/settings/billing?tokens_success=true",
        cancel_url: str = "https://www.ariia.ai/settings/billing?canceled=true",
    ) -> dict[str, Any]:
        """Create a one-time checkout for token purchases."""
        stripe = _get_stripe()

        customer_data = await self.get_or_create_customer(db, tenant_id)

        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_data["id"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": f"{tokens_amount:,} KI-Tokens",
                        "description": f"Token-Aufladung für ARIIA",
                    },
                    "unit_amount": price_cents,
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(tenant_id),
                "tokens_amount": str(tokens_amount),
                "checkout_type": "token_purchase",
            },
        )

        return {
            "session_id": session.id,
            "url": session.url,
            "status": session.status,
        }

    # ── Subscription Management ─────────────────────────────────────────

    async def update_stripe_subscription(
        self,
        db: Session,
        tenant_id: int,
        new_plan_slug: str,
        billing_interval: Optional[BillingInterval] = None,
        proration_behavior: str = "create_prorations",
    ) -> dict[str, Any]:
        """
        Update a Stripe subscription (upgrade/downgrade).
        """
        stripe = _get_stripe()

        sub = stripe_billing_repository.get_subscription_by_tenant(db, tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise ValueError("Kein aktives Stripe-Abonnement gefunden.")

        plan = stripe_billing_repository.get_active_plan_by_slug(db, new_plan_slug)
        if not plan:
            raise ValueError(f"Plan '{new_plan_slug}' nicht gefunden.")

        interval = billing_interval or (
            BillingInterval(sub.billing_interval)
            if isinstance(sub.billing_interval, str)
            else sub.billing_interval
        )

        price_id = plan.stripe_price_yearly_id if interval == BillingInterval.YEAR else plan.stripe_price_monthly_id
        if not price_id:
            raise ValueError(f"Kein Stripe-Preis für Plan '{new_plan_slug}' ({interval.value}).")

        stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
        updated = stripe.Subscription.modify(
            sub.stripe_subscription_id,
            items=[{
                "id": stripe_sub["items"]["data"][0]["id"],
                "price": price_id,
            }],
            proration_behavior=proration_behavior,
            metadata={
                "tenant_id": str(tenant_id),
                "plan_slug": new_plan_slug,
            },
        )

        logger.info(
            "billing.stripe.subscription_updated",
            tenant_id=tenant_id,
            new_plan=new_plan_slug,
            status=updated.status,
        )

        return {
            "subscription_id": updated.id,
            "status": updated.status,
            "plan_slug": new_plan_slug,
        }

    async def cancel_stripe_subscription(
        self,
        db: Session,
        tenant_id: int,
        immediate: bool = False,
    ) -> dict[str, Any]:
        """Cancel a Stripe subscription."""
        stripe = _get_stripe()

        sub = stripe_billing_repository.get_subscription_by_tenant(db, tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise ValueError("Kein aktives Stripe-Abonnement gefunden.")

        if immediate:
            result = stripe.Subscription.cancel(sub.stripe_subscription_id)
        else:
            result = stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True,
            )

        return {
            "subscription_id": result.id,
            "status": result.status,
            "cancel_at_period_end": result.cancel_at_period_end,
        }

    async def reactivate_stripe_subscription(
        self,
        db: Session,
        tenant_id: int,
    ) -> dict[str, Any]:
        """Reactivate a canceled Stripe subscription."""
        stripe = _get_stripe()

        sub = stripe_billing_repository.get_subscription_by_tenant(db, tenant_id)
        if not sub or not sub.stripe_subscription_id:
            raise ValueError("Kein aktives Stripe-Abonnement gefunden.")

        result = stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        return {
            "subscription_id": result.id,
            "status": result.status,
            "cancel_at_period_end": False,
        }

    # ── Product/Price Sync ──────────────────────────────────────────────

    async def sync_plan_to_stripe(self, db: Session, plan: PlanV2) -> bool:
        """Push a plan to Stripe (create or update product + prices)."""
        stripe = _get_stripe()

        try:
            # Create or update product
            if plan.stripe_product_id:
                stripe.Product.modify(
                    plan.stripe_product_id,
                    name=plan.name,
                    description=plan.description or "",
                    active=plan.is_active,
                    metadata={"plan_slug": plan.slug, "platform": "ariia"},
                )
            else:
                product = stripe.Product.create(
                    name=plan.name,
                    description=plan.description or "",
                    metadata={"plan_slug": plan.slug, "platform": "ariia"},
                )
                plan.stripe_product_id = product.id

            # Create monthly price if needed
            if plan.price_monthly_cents > 0 and not plan.stripe_price_monthly_id:
                price = stripe.Price.create(
                    product=plan.stripe_product_id,
                    unit_amount=plan.price_monthly_cents,
                    currency=plan.currency,
                    recurring={"interval": "month"},
                    metadata={"plan_slug": plan.slug, "interval": "month"},
                )
                plan.stripe_price_monthly_id = price.id

            # Create yearly price if needed
            if plan.price_yearly_cents and plan.price_yearly_cents > 0 and not plan.stripe_price_yearly_id:
                price = stripe.Price.create(
                    product=plan.stripe_product_id,
                    unit_amount=plan.price_yearly_cents,
                    currency=plan.currency,
                    recurring={"interval": "year"},
                    metadata={"plan_slug": plan.slug, "interval": "year"},
                )
                plan.stripe_price_yearly_id = price.id

            db.commit()
            logger.info("billing.stripe.plan_synced", plan_slug=plan.slug)
            return True

        except Exception as exc:
            logger.error("billing.stripe.plan_sync_failed", plan_slug=plan.slug, error=str(exc))
            return False

    async def sync_addon_to_stripe(self, db: Session, addon: AddonDefinitionV2) -> bool:
        """Push an addon to Stripe."""
        stripe = _get_stripe()

        try:
            if addon.stripe_product_id:
                stripe.Product.modify(
                    addon.stripe_product_id,
                    name=addon.name,
                    description=addon.description or "",
                    active=addon.is_active,
                    metadata={"addon_slug": addon.slug, "platform": "ariia"},
                )
            else:
                product = stripe.Product.create(
                    name=addon.name,
                    description=addon.description or "",
                    metadata={"addon_slug": addon.slug, "platform": "ariia"},
                )
                addon.stripe_product_id = product.id

            if addon.price_monthly_cents > 0 and not addon.stripe_price_id:
                price = stripe.Price.create(
                    product=addon.stripe_product_id,
                    unit_amount=addon.price_monthly_cents,
                    currency=addon.currency,
                    recurring={"interval": "month"},
                    metadata={"addon_slug": addon.slug},
                )
                addon.stripe_price_id = price.id

            db.commit()
            return True

        except Exception as exc:
            logger.error("billing.stripe.addon_sync_failed", addon_slug=addon.slug, error=str(exc))
            return False

    async def full_sync_to_stripe(self, db: Session) -> dict[str, int]:
        """Push all active plans and addons to Stripe."""
        plans = stripe_billing_repository.list_active_plans(db)
        addons = stripe_billing_repository.list_active_addons(db)

        plans_ok = sum(1 for p in plans if await self.sync_plan_to_stripe(db, p))
        addons_ok = sum(1 for a in addons if await self.sync_addon_to_stripe(db, a))

        await billing_events.emit_and_commit(
            db=db,
            tenant_id=None,
            event_type=BillingEventType.STRIPE_SYNC_COMPLETED,
            payload={"plans_synced": plans_ok, "addons_synced": addons_ok},
            actor_type="system",
        )

        return {"plans_synced": plans_ok, "addons_synced": addons_ok}

    # ── Invoice Management ──────────────────────────────────────────────

    async def sync_invoices(
        self,
        db: Session,
        tenant_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch and cache invoices from Stripe."""
        stripe = _get_stripe()

        sub = stripe_billing_repository.get_subscription_by_tenant(db, tenant_id)
        if not sub or not sub.stripe_customer_id:
            return []

        invoices = stripe.Invoice.list(customer=sub.stripe_customer_id, limit=limit)
        result = []

        for inv in invoices.data:
            # Upsert local cache
            local = stripe_billing_repository.get_or_create_invoice_record(
                db,
                tenant_id=tenant_id,
                stripe_invoice_id=inv.id,
            )

            local.stripe_subscription_id = inv.subscription
            local.number = inv.number
            local.status = inv.status
            local.currency = inv.currency
            local.amount_due_cents = inv.amount_due
            local.amount_paid_cents = inv.amount_paid
            local.amount_remaining_cents = inv.amount_remaining
            local.hosted_invoice_url = inv.hosted_invoice_url
            local.invoice_pdf_url = inv.invoice_pdf
            if inv.period_start:
                local.period_start = datetime.fromtimestamp(inv.period_start, tz=timezone.utc)
            if inv.period_end:
                local.period_end = datetime.fromtimestamp(inv.period_end, tz=timezone.utc)

            result.append({
                "id": inv.id,
                "number": inv.number,
                "status": inv.status,
                "amount_due": inv.amount_due,
                "amount_paid": inv.amount_paid,
                "currency": inv.currency,
                "hosted_invoice_url": inv.hosted_invoice_url,
                "pdf": inv.invoice_pdf,
                "created": inv.created,
            })

        db.commit()
        return result

    # ── Health Check ────────────────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """Check Stripe connectivity."""
        try:
            stripe = _get_stripe()
            account = stripe.Account.retrieve()
            return {
                "status": "connected",
                "account_id": account.id,
                "business_name": getattr(account, "business_profile", {}).get("name", ""),
                "country": account.country,
            }
        except ImportError:
            return {"status": "not_installed"}
        except ValueError as e:
            return {"status": "not_configured", "reason": str(e)}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def is_configured(self) -> bool:
        """Quick check if Stripe is configured."""
        try:
            _get_stripe()
            return True
        except Exception:
            return False


# Singleton
stripe_service = StripeServiceV2()
