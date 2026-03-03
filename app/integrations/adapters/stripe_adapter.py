"""ARIIA v2.0 – Stripe Payment Adapter.

@ARCH: Sprint 3 (Integration Roadmap), Task S3.1
Concrete adapter for Stripe payment processing. Wraps the existing
billing.py router logic and billing_service.py into the BaseAdapter
interface, providing standardized capability routing for the DynamicToolResolver.

Supported Capabilities:
  - payment.checkout.create        → Create a Stripe Checkout Session
  - payment.subscription.manage    → Manage subscriptions (upgrade/downgrade/cancel/reactivate)
  - payment.subscription.status    → Get current subscription status
  - payment.invoice.list           → List invoices for a tenant
  - payment.customer.create        → Create or retrieve a Stripe customer
  - payment.webhook.process        → Process a Stripe webhook event
  - billing.usage.track            → Track metered usage for a tenant
  - billing.usage.get              → Get current usage counters
  - billing.plan.enforce           → Check plan limits and feature gates
  - billing.plan.compare           → Get plan comparison for pricing page
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class StripeAdapter(BaseAdapter):
    """Adapter for Stripe payment processing and billing management.

    Routes capability calls to the existing billing infrastructure,
    wrapping results in the standardized AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "stripe"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "payment.checkout.create",
            "payment.subscription.manage",
            "payment.subscription.status",
            "payment.invoice.list",
            "payment.customer.create",
            "payment.webhook.process",
            "billing.usage.track",
            "billing.usage.get",
            "billing.plan.enforce",
            "billing.plan.compare",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "Stripe"

    @property
    def category(self) -> str:
        return "payment"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "secret_key",
                    "label": "Secret Key",
                    "type": "password",
                    "required": True,
                    "help_text": "Stripe Secret Key (sk_live_... oder sk_test_...).",
                },
                {
                    "key": "webhook_secret",
                    "label": "Webhook Secret",
                    "type": "password",
                    "required": False,
                    "help_text": "Stripe Webhook Signing Secret (whsec_...).",
                },
            ],
        }

    async def get_contacts(
        self,
        tenant_id: int,
        config: dict,
        last_sync_at=None,
        sync_mode=None,
    ) -> "SyncResult":
        from app.integrations.adapters.base import SyncResult
        return SyncResult(
            success=True,
            records_fetched=0,
            contacts=[],
            metadata={"note": "Stripe does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="Stripe-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate Stripe/billing method."""
        handlers = {
            "payment.checkout.create": self._create_checkout,
            "payment.subscription.manage": self._manage_subscription,
            "payment.subscription.status": self._get_subscription_status,
            "payment.invoice.list": self._list_invoices,
            "payment.customer.create": self._create_customer,
            "payment.webhook.process": self._process_webhook,
            "billing.usage.track": self._track_usage,
            "billing.usage.get": self._get_usage,
            "billing.plan.enforce": self._enforce_plan,
            "billing.plan.compare": self._compare_plans,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_stripe_module(self):
        """Get configured stripe module. Returns (stripe, error_result)."""
        try:
            import stripe as _stripe
        except ImportError:
            return None, AdapterResult(
                success=False,
                error="stripe library not installed. Run: pip install stripe",
                error_code="DEPENDENCY_MISSING",
            )

        try:
            from app.gateway.persistence import persistence
            enabled = (persistence.get_setting("billing_stripe_enabled", "false") or "").lower() == "true"
            if not enabled:
                return None, AdapterResult(
                    success=False,
                    error="Stripe ist nicht aktiviert. Bitte in den Integrationseinstellungen konfigurieren.",
                    error_code="STRIPE_NOT_ENABLED",
                )
            secret_key = (persistence.get_setting("billing_stripe_secret_key", "") or "").strip()
            if not secret_key:
                return None, AdapterResult(
                    success=False,
                    error="Stripe-Secret-Key nicht konfiguriert.",
                    error_code="STRIPE_NOT_CONFIGURED",
                )
            _stripe.api_key = secret_key
            return _stripe, None
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"Stripe configuration error: {exc}",
                error_code="STRIPE_CONFIG_ERROR",
            )

    # ── payment.checkout.create ──────────────────────────────────────────

    async def _create_checkout(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a Stripe Checkout Session.

        Required kwargs:
            price_id (str): The Stripe Price ID for the plan.
        Optional kwargs:
            success_url (str): Redirect URL after successful payment.
            cancel_url (str): Redirect URL after cancelled payment.
            customer_email (str): Pre-fill the customer email.
            mode (str): 'subscription' (default) or 'payment'.
            metadata (dict): Additional metadata to attach.
        """
        price_id = kwargs.get("price_id")
        if not price_id:
            return AdapterResult(
                success=False,
                error="Parameter 'price_id' is required for payment.checkout.create",
                error_code="MISSING_PARAM",
            )

        stripe, err = self._get_stripe_module()
        if err:
            return err

        try:
            session_params = {
                "mode": kwargs.get("mode", "subscription"),
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": kwargs.get("success_url", "https://app.ariia.io/billing/success?session_id={CHECKOUT_SESSION_ID}"),
                "cancel_url": kwargs.get("cancel_url", "https://app.ariia.io/billing/cancel"),
                "metadata": {"tenant_id": str(tenant_id), **(kwargs.get("metadata") or {})},
            }

            if kwargs.get("customer_email"):
                session_params["customer_email"] = kwargs["customer_email"]

            session = stripe.checkout.Session.create(**session_params)

            return AdapterResult(
                success=True,
                data={
                    "session_id": session.id,
                    "url": session.url,
                    "status": session.status,
                    "mode": session.mode,
                },
                metadata={"tenant_id": tenant_id},
            )
        except Exception as exc:
            logger.error("stripe_adapter.checkout_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Checkout creation failed: {exc}")

    # ── payment.subscription.manage ──────────────────────────────────────

    async def _manage_subscription(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Manage a subscription (upgrade, downgrade, cancel, reactivate).

        Required kwargs:
            action (str): 'upgrade', 'downgrade', 'cancel', 'reactivate'.
        Optional kwargs:
            new_price_id (str): Required for upgrade/downgrade.
            subscription_id (str): Override auto-detected subscription.
            proration_behavior (str): 'create_prorations' (default), 'none', 'always_invoice'.
        """
        action = kwargs.get("action")
        if not action:
            return AdapterResult(
                success=False,
                error="Parameter 'action' is required (upgrade/downgrade/cancel/reactivate)",
                error_code="MISSING_PARAM",
            )

        stripe, err = self._get_stripe_module()
        if err:
            return err

        try:
            from app.core.db import SessionLocal
            from app.core.models import Subscription

            db = SessionLocal()
            try:
                sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
                if not sub or not sub.stripe_subscription_id:
                    return AdapterResult(
                        success=False,
                        error="Kein aktives Abonnement für diesen Tenant gefunden.",
                        error_code="NO_SUBSCRIPTION",
                    )
                subscription_id = kwargs.get("subscription_id") or sub.stripe_subscription_id
            finally:
                db.close()

            if action in ("upgrade", "downgrade"):
                new_price_id = kwargs.get("new_price_id")
                if not new_price_id:
                    return AdapterResult(
                        success=False,
                        error="Parameter 'new_price_id' is required for upgrade/downgrade",
                        error_code="MISSING_PARAM",
                    )

                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                updated = stripe.Subscription.modify(
                    subscription_id,
                    items=[{
                        "id": stripe_sub["items"]["data"][0]["id"],
                        "price": new_price_id,
                    }],
                    proration_behavior=kwargs.get("proration_behavior", "create_prorations"),
                )

                return AdapterResult(
                    success=True,
                    data={
                        "action": action,
                        "subscription_id": subscription_id,
                        "new_price_id": new_price_id,
                        "status": updated.status,
                    },
                )

            elif action == "cancel":
                updated = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
                return AdapterResult(
                    success=True,
                    data={
                        "action": "cancel_scheduled",
                        "subscription_id": subscription_id,
                        "cancel_at_period_end": True,
                        "current_period_end": updated.get("current_period_end"),
                    },
                )

            elif action == "reactivate":
                updated = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=False,
                )
                return AdapterResult(
                    success=True,
                    data={
                        "action": "reactivated",
                        "subscription_id": subscription_id,
                        "cancel_at_period_end": False,
                    },
                )

            else:
                return AdapterResult(
                    success=False,
                    error=f"Unknown action: {action}. Valid: upgrade, downgrade, cancel, reactivate",
                    error_code="INVALID_ACTION",
                )

        except Exception as exc:
            logger.error("stripe_adapter.subscription_manage_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Subscription management failed: {exc}")

    # ── payment.subscription.status ──────────────────────────────────────

    async def _get_subscription_status(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get the current subscription status for a tenant."""
        try:
            from app.core.db import SessionLocal
            from app.core.models import Subscription, Plan

            db = SessionLocal()
            try:
                sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
                if not sub:
                    return AdapterResult(
                        success=True,
                        data={"status": "no_subscription", "tenant_id": tenant_id},
                    )

                plan = db.query(Plan).filter(Plan.id == sub.plan_id).first() if sub.plan_id else None

                return AdapterResult(
                    success=True,
                    data={
                        "subscription_id": sub.stripe_subscription_id,
                        "status": sub.status,
                        "plan_name": plan.name if plan else None,
                        "plan_tier": plan.tier if plan else None,
                        "stripe_customer_id": sub.stripe_customer_id,
                        "current_period_start": str(sub.current_period_start) if hasattr(sub, "current_period_start") else None,
                        "current_period_end": str(sub.current_period_end) if hasattr(sub, "current_period_end") else None,
                        "cancel_at_period_end": getattr(sub, "cancel_at_period_end", False),
                    },
                    metadata={"tenant_id": tenant_id},
                )
            finally:
                db.close()
        except Exception as exc:
            logger.error("stripe_adapter.status_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Status retrieval failed: {exc}")

    # ── payment.invoice.list ─────────────────────────────────────────────

    async def _list_invoices(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List invoices for a tenant from Stripe.

        Optional kwargs:
            limit (int): Number of invoices to return (default: 10).
            status (str): Filter by status ('paid', 'open', 'draft', 'void').
        """
        stripe, err = self._get_stripe_module()
        if err:
            return err

        try:
            from app.core.db import SessionLocal
            from app.core.models import Subscription

            db = SessionLocal()
            try:
                sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
                if not sub or not sub.stripe_customer_id:
                    return AdapterResult(
                        success=True,
                        data=[],
                        metadata={"message": "No Stripe customer found for this tenant"},
                    )
                customer_id = sub.stripe_customer_id
            finally:
                db.close()

            params = {
                "customer": customer_id,
                "limit": kwargs.get("limit", 10),
            }
            if kwargs.get("status"):
                params["status"] = kwargs["status"]

            invoices = stripe.Invoice.list(**params)

            invoice_list = []
            for inv in invoices.data:
                invoice_list.append({
                    "id": inv.id,
                    "number": inv.number,
                    "status": inv.status,
                    "amount_due": inv.amount_due,
                    "amount_paid": inv.amount_paid,
                    "currency": inv.currency,
                    "created": inv.created,
                    "due_date": inv.due_date,
                    "hosted_invoice_url": inv.hosted_invoice_url,
                    "pdf": inv.invoice_pdf,
                })

            return AdapterResult(
                success=True,
                data=invoice_list,
                metadata={"total": len(invoice_list), "customer_id": customer_id},
            )
        except Exception as exc:
            logger.error("stripe_adapter.invoices_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Invoice listing failed: {exc}")

    # ── payment.customer.create ──────────────────────────────────────────

    async def _create_customer(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create or retrieve a Stripe customer for a tenant.

        Optional kwargs:
            email (str): Customer email address.
            name (str): Customer/company name.
            metadata (dict): Additional metadata.
        """
        stripe, err = self._get_stripe_module()
        if err:
            return err

        try:
            from app.core.db import SessionLocal
            from app.core.models import Subscription, Tenant

            db = SessionLocal()
            try:
                sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
                if sub and sub.stripe_customer_id:
                    customer = stripe.Customer.retrieve(sub.stripe_customer_id)
                    return AdapterResult(
                        success=True,
                        data={
                            "customer_id": customer.id,
                            "email": customer.email,
                            "name": customer.name,
                            "action": "retrieved_existing",
                        },
                    )

                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                email = kwargs.get("email") or (tenant.admin_email if tenant else None)
                name = kwargs.get("name") or (tenant.name if tenant else f"Tenant {tenant_id}")

                customer = stripe.Customer.create(
                    email=email,
                    name=name,
                    metadata={"tenant_id": str(tenant_id), **(kwargs.get("metadata") or {})},
                )

                if sub:
                    sub.stripe_customer_id = customer.id
                    db.commit()

                return AdapterResult(
                    success=True,
                    data={
                        "customer_id": customer.id,
                        "email": customer.email,
                        "name": customer.name,
                        "action": "created_new",
                    },
                )
            finally:
                db.close()
        except Exception as exc:
            logger.error("stripe_adapter.customer_create_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Customer creation failed: {exc}")

    # ── payment.webhook.process ──────────────────────────────────────────

    async def _process_webhook(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Process a Stripe webhook event.

        Required kwargs:
            event_type (str): The Stripe event type.
            event_id (str): The Stripe event ID.
            data (dict): The event data object.
        """
        event_type = kwargs.get("event_type")
        event_id = kwargs.get("event_id")
        data = kwargs.get("data")

        if not all([event_type, event_id, data]):
            return AdapterResult(
                success=False,
                error="Parameters 'event_type', 'event_id', and 'data' are required",
                error_code="MISSING_PARAM",
            )

        try:
            from app.platform.billing_service import StripeWebhookProcessor

            processor = StripeWebhookProcessor()
            result = await processor.process_event(event_type, event_id, data)

            return AdapterResult(
                success=result.get("status") != "error",
                data=result,
                metadata={"event_type": event_type, "event_id": event_id},
            )
        except Exception as exc:
            logger.error("stripe_adapter.webhook_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Webhook processing failed: {exc}")

    # ── billing.usage.track ──────────────────────────────────────────────

    async def _track_usage(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Track metered usage for a tenant.

        Required kwargs:
            usage_type (str): Type of usage (conversation, api_call, token_input, etc.).
        Optional kwargs:
            quantity (int): Usage quantity (default: 1).
            metadata (dict): Additional metadata.
            idempotency_key (str): Key for deduplication.
        """
        usage_type_str = kwargs.get("usage_type")
        if not usage_type_str:
            return AdapterResult(
                success=False,
                error="Parameter 'usage_type' is required",
                error_code="MISSING_PARAM",
            )

        try:
            from app.platform.billing_service import UsageTracker, UsageRecord, UsageType

            try:
                usage_type = UsageType(usage_type_str)
            except ValueError:
                valid = [ut.value for ut in UsageType]
                return AdapterResult(
                    success=False,
                    error=f"Invalid usage_type: {usage_type_str}. Valid: {valid}",
                    error_code="INVALID_PARAM",
                )

            tracker = UsageTracker()
            record = UsageRecord(
                tenant_id=tenant_id,
                usage_type=usage_type,
                quantity=kwargs.get("quantity", 1),
                metadata=kwargs.get("metadata", {}),
                idempotency_key=kwargs.get("idempotency_key"),
            )

            recorded = await tracker.record_usage(record)

            return AdapterResult(
                success=True,
                data={
                    "recorded": recorded,
                    "usage_type": usage_type_str,
                    "quantity": record.quantity,
                    "duplicate": not recorded,
                },
            )
        except Exception as exc:
            logger.error("stripe_adapter.track_usage_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Usage tracking failed: {exc}")

    # ── billing.usage.get ────────────────────────────────────────────────

    async def _get_usage(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get current usage counters for a tenant.

        Optional kwargs:
            usage_type (str): Specific type to query (returns all if omitted).
            period (str): Billing period in YYYY-MM format (defaults to current).
        """
        try:
            from app.platform.billing_service import UsageTracker, UsageType

            tracker = UsageTracker()
            period = kwargs.get("period")

            if kwargs.get("usage_type"):
                try:
                    ut = UsageType(kwargs["usage_type"])
                except ValueError:
                    valid = [u.value for u in UsageType]
                    return AdapterResult(
                        success=False,
                        error=f"Invalid usage_type. Valid: {valid}",
                        error_code="INVALID_PARAM",
                    )
                count = await tracker.get_usage(tenant_id, ut, period)
                return AdapterResult(
                    success=True,
                    data={"usage_type": kwargs["usage_type"], "count": count, "period": period},
                )

            all_usage = await tracker.get_all_usage(tenant_id, period)
            return AdapterResult(
                success=True,
                data=all_usage,
                metadata={"tenant_id": tenant_id, "period": period},
            )
        except Exception as exc:
            logger.error("stripe_adapter.get_usage_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Usage retrieval failed: {exc}")

    # ── billing.plan.enforce ─────────────────────────────────────────────

    async def _enforce_plan(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Check plan limits and feature gates for a tenant.

        Required kwargs:
            check_type (str): 'feature', 'conversation', 'api', 'integration', 'channel'.
        Optional kwargs:
            feature (str): Feature name (required for check_type='feature').
            tier (str): Plan tier override (auto-detected if omitted).
            current_count (int): Current count (for integration/channel checks).
        """
        check_type = kwargs.get("check_type")
        if not check_type:
            return AdapterResult(
                success=False,
                error="Parameter 'check_type' is required (feature/conversation/api/integration/channel)",
                error_code="MISSING_PARAM",
            )

        try:
            from app.platform.billing_service import PlanEnforcer, PlanTier, UsageTracker

            tier_str = kwargs.get("tier")
            if tier_str:
                try:
                    tier = PlanTier(tier_str)
                except ValueError:
                    valid = [t.value for t in PlanTier]
                    return AdapterResult(
                        success=False,
                        error=f"Invalid tier: {tier_str}. Valid: {valid}",
                        error_code="INVALID_PARAM",
                    )
            else:
                tier = PlanTier.FREE

            enforcer = PlanEnforcer(UsageTracker())

            if check_type == "feature":
                feature = kwargs.get("feature")
                if not feature:
                    return AdapterResult(success=False, error="'feature' is required for check_type='feature'")
                allowed = enforcer.check_feature(tier, feature)
                return AdapterResult(
                    success=True,
                    data={"feature": feature, "allowed": allowed, "tier": tier.value},
                )

            elif check_type == "conversation":
                result = await enforcer.check_conversation_limit(tenant_id, tier)
                return AdapterResult(success=True, data=result)

            elif check_type == "api":
                result = await enforcer.check_api_limit(tenant_id, tier)
                return AdapterResult(success=True, data=result)

            elif check_type == "integration":
                current_count = kwargs.get("current_count", 0)
                result = enforcer.check_integration_limit(tier, current_count)
                return AdapterResult(success=True, data=result)

            elif check_type == "channel":
                current_count = kwargs.get("current_count", 0)
                result = enforcer.check_channel_limit(tier, current_count)
                return AdapterResult(success=True, data=result)

            else:
                return AdapterResult(
                    success=False,
                    error=f"Unknown check_type: {check_type}",
                    error_code="INVALID_PARAM",
                )

        except Exception as exc:
            logger.error("stripe_adapter.enforce_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Plan enforcement failed: {exc}")

    # ── billing.plan.compare ─────────────────────────────────────────────

    async def _compare_plans(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get a comparison of all plan tiers for the pricing page."""
        try:
            from app.platform.billing_service import PlanEnforcer

            enforcer = PlanEnforcer()
            comparison = enforcer.get_plan_comparison()

            return AdapterResult(
                success=True,
                data=comparison,
                metadata={"total_tiers": len(comparison)},
            )
        except Exception as exc:
            logger.error("stripe_adapter.compare_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Plan comparison failed: {exc}")

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Stripe is configured and accessible."""
        stripe, err = self._get_stripe_module()
        if err:
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": err.error},
            )

        try:
            account = stripe.Account.retrieve()
            return AdapterResult(
                success=True,
                data={
                    "status": "CONNECTED",
                    "account_id": account.id,
                    "business_name": getattr(account, "business_profile", {}).get("name", ""),
                    "country": account.country,
                },
            )
        except Exception as exc:
            return AdapterResult(
                success=True,
                data={"status": "ERROR", "reason": str(exc)},
            )
