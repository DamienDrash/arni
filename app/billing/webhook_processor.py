"""
ARIIA Billing V2 – Webhook Processor

Handles all Stripe webhook events with:
- Signature verification
- Idempotent processing (via BillingEvent idempotency_key)
- Event routing to appropriate handlers
- Full audit trail via BillingEventService

Supported events:
- checkout.session.completed
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.paid
- invoice.payment_failed
- invoice.finalized
- customer.created
- customer.updated

Usage:
    from app.billing.webhook_processor import webhook_processor

    result = await webhook_processor.process(db, payload, sig_header)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.billing.events import billing_events
from app.billing.models import (
    BillingEventType,
    BillingInterval,
    InvoiceRecord,
    PlanV2,
    SubscriptionStatus,
    SubscriptionV2,
    TenantAddonV2,
)
from app.billing.subscription_service import subscription_service

logger = structlog.get_logger()


class WebhookProcessorV2:
    """
    Centralized Stripe webhook processor.

    Each event type is handled by a dedicated method.
    All handlers are idempotent via the Stripe event ID.
    """

    # ── Main Entry Point ────────────────────────────────────────────────

    async def process(
        self,
        db: Session,
        payload: bytes,
        sig_header: str,
    ) -> dict[str, Any]:
        """
        Verify and process a Stripe webhook event.

        Args:
            db: Database session.
            payload: Raw request body.
            sig_header: Stripe-Signature header value.

        Returns:
            {"status": "processed"|"skipped"|"error", "event_type": str, ...}
        """
        # Verify signature
        event = self._verify_event(payload, sig_header)
        if not event:
            return {"status": "error", "reason": "Ungültige Webhook-Signatur"}

        event_type = event.get("type", "unknown")
        event_id = event.get("id", "unknown")

        logger.info("billing.webhook.received", event_type=event_type, event_id=event_id)

        # Check idempotency
        existing = billing_events.get_events_by_stripe_id(db, event_id)
        if existing:
            logger.info("billing.webhook.duplicate", event_id=event_id)
            return {"status": "skipped", "reason": "already_processed", "event_type": event_type}

        # Route to handler
        handler = self._get_handler(event_type)
        if not handler:
            logger.info("billing.webhook.unhandled", event_type=event_type)
            return {"status": "skipped", "reason": "unhandled_event_type", "event_type": event_type}

        try:
            result = await handler(db, event)
            return {"status": "processed", "event_type": event_type, **result}
        except Exception as exc:
            logger.error(
                "billing.webhook.handler_error",
                event_type=event_type,
                event_id=event_id,
                error=str(exc),
            )
            # Still record the event for audit
            await billing_events.emit(
                db=db,
                tenant_id=None,
                event_type=BillingEventType.WEBHOOK_PROCESSING_FAILED,
                payload={"event_type": event_type, "event_id": event_id, "error": str(exc)},
                actor_type="stripe",
                stripe_event_id=event_id,
                idempotency_key=f"webhook_error_{event_id}",
            )
            db.commit()
            return {"status": "error", "event_type": event_type, "reason": str(exc)}

    # ── Event Verification ──────────────────────────────────────────────

    def _verify_event(self, payload: bytes, sig_header: str) -> Optional[dict]:
        """Verify Stripe webhook signature and return the event."""
        try:
            import stripe as _stripe
            from app.gateway.persistence import persistence

            webhook_secret = (persistence.get_setting("billing_stripe_webhook_secret", "") or "").strip()

            if webhook_secret:
                event = _stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            else:
                # No webhook secret configured — parse but log warning
                logger.warning("billing.webhook.no_secret", msg="Webhook-Secret nicht konfiguriert, Signatur wird nicht geprüft")
                event = json.loads(payload)

            return event
        except _stripe.error.SignatureVerificationError:
            logger.error("billing.webhook.invalid_signature")
            return None
        except Exception as exc:
            logger.error("billing.webhook.parse_error", error=str(exc))
            return None

    # ── Handler Router ──────────────────────────────────────────────────

    def _get_handler(self, event_type: str):
        """Map event type to handler method."""
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
            "invoice.finalized": self._handle_invoice_finalized,
            "customer.created": self._handle_customer_created,
            "customer.updated": self._handle_customer_updated,
        }
        return handlers.get(event_type)

    # ── Checkout Completed ──────────────────────────────────────────────

    async def _handle_checkout_completed(self, db: Session, event: dict) -> dict:
        """Handle checkout.session.completed — create or activate subscription."""
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        tenant_id = int(metadata.get("tenant_id", 0))
        checkout_type = metadata.get("checkout_type", "subscription")
        event_id = event["id"]

        if not tenant_id:
            logger.warning("billing.webhook.no_tenant_id", event_id=event_id)
            return {"action": "skipped", "reason": "no_tenant_id"}

        if checkout_type == "token_purchase":
            return await self._handle_token_purchase(db, session, tenant_id, event_id)

        if checkout_type == "addon":
            return await self._handle_addon_checkout(db, session, tenant_id, event_id)

        if checkout_type == "image_credit_purchase":
            return await self._handle_image_credit_purchase(db, session, tenant_id, event_id)

        # Standard subscription checkout
        plan_slug = metadata.get("plan_slug", "")
        billing_interval_str = metadata.get("billing_interval", "month")
        stripe_subscription_id = session.get("subscription")
        stripe_customer_id = session.get("customer")

        plan = db.query(PlanV2).filter(PlanV2.slug == plan_slug).first()
        if not plan:
            logger.error("billing.webhook.plan_not_found", plan_slug=plan_slug)
            return {"action": "error", "reason": f"Plan '{plan_slug}' nicht gefunden"}

        # Check if subscription already exists
        existing_sub = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()

        if existing_sub:
            # Update existing subscription
            existing_sub.plan_id = plan.id
            existing_sub.status = SubscriptionStatus.ACTIVE
            existing_sub.stripe_subscription_id = stripe_subscription_id
            existing_sub.stripe_customer_id = stripe_customer_id
            existing_sub.billing_interval = BillingInterval(billing_interval_str)
        else:
            # Create new subscription
            try:
                billing_interval = BillingInterval(billing_interval_str)
            except ValueError:
                billing_interval = BillingInterval.MONTH

            await subscription_service.create_subscription(
                db=db,
                tenant_id=tenant_id,
                plan_slug=plan_slug,
                billing_interval=billing_interval,
                stripe_subscription_id=stripe_subscription_id,
                stripe_customer_id=stripe_customer_id,
                trial_days=0,  # Already paid
                actor_type="stripe",
                actor_id=event_id,
            )

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.CHECKOUT_COMPLETED,
            payload={
                "session_id": session.get("id"),
                "plan_slug": plan_slug,
                "stripe_subscription_id": stripe_subscription_id,
                "checkout_type": checkout_type,
            },
            actor_type="stripe",
            stripe_event_id=event_id,
            idempotency_key=f"checkout_{event_id}",
        )

        db.commit()
        return {"action": "subscription_created", "tenant_id": tenant_id, "plan_slug": plan_slug}

    # ── Token Purchase ──────────────────────────────────────────────────

    async def _handle_token_purchase(self, db: Session, session: dict, tenant_id: int, event_id: str) -> dict:
        """Handle token purchase checkout completion."""
        metadata = session.get("metadata", {})
        tokens_amount = int(metadata.get("tokens_amount", 0))

        if tokens_amount > 0:
            # Add tokens to tenant's balance
            sub = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()
            if sub:
                current_extra = sub.extra_tokens_balance or 0
                sub.extra_tokens_balance = current_extra + tokens_amount

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.TOKEN_PURCHASE_COMPLETED,
            payload={
                "tokens_amount": tokens_amount,
                "session_id": session.get("id"),
            },
            actor_type="stripe",
            stripe_event_id=event_id,
            idempotency_key=f"token_purchase_{event_id}",
        )

        db.commit()
        return {"action": "token_purchase", "tokens_amount": tokens_amount}

    # ── Image Credit Purchase ────────────────────────────────────────────

    async def _handle_image_credit_purchase(self, db: Session, session: dict, tenant_id: int, event_id: str) -> dict:
        """Handle image credit pack purchase checkout completion."""
        from app.core.models import ImageCreditPurchase
        from app.media.credit_service import add_credits

        metadata = session.get("metadata", {})
        pack_slug = metadata.get("pack_slug", "")
        credits = int(metadata.get("credits", 0))
        billing_interval = metadata.get("billing_interval", "once")
        session_id = session.get("id")
        stripe_sub_id = session.get("subscription")

        # Find pending purchase record
        purchase = db.query(ImageCreditPurchase).filter(
            ImageCreditPurchase.stripe_session_id == session_id,
            ImageCreditPurchase.tenant_id == tenant_id,
        ).first()

        if purchase:
            # Idempotency check — don't grant credits twice
            if purchase.status in ("active", "completed"):
                logger.info("billing.webhook.image_credit_already_processed",
                            session_id=session_id, tenant_id=tenant_id)
                return {"action": "skipped", "reason": "already_processed"}
            purchase.status = "completed" if billing_interval == "once" else "active"
            if stripe_sub_id:
                purchase.stripe_subscription_id = stripe_sub_id
            db.flush()

        if credits > 0:
            add_credits(
                db=db,
                tenant_id=tenant_id,
                amount=credits,
                reason="topup",
                reference_id=str(purchase.id) if purchase else session_id,
            )

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.CHECKOUT_COMPLETED,
            payload={
                "pack_slug": pack_slug,
                "credits": credits,
                "billing_interval": billing_interval,
                "session_id": session_id,
                "checkout_type": "image_credit_purchase",
            },
            actor_type="stripe",
            stripe_event_id=event_id,
            idempotency_key=f"image_credits_{event_id}",
        )

        db.commit()
        logger.info("billing.webhook.image_credits_granted",
                    tenant_id=tenant_id, credits=credits, pack_slug=pack_slug)
        return {"action": "image_credits_granted", "credits": credits, "pack_slug": pack_slug}

    # ── Addon Checkout ──────────────────────────────────────────────────

    async def _handle_addon_checkout(self, db: Session, session: dict, tenant_id: int, event_id: str) -> dict:
        """Handle addon checkout completion."""
        metadata = session.get("metadata", {})
        addon_slug = metadata.get("addon_slug", "")
        quantity = int(metadata.get("quantity", 1))

        # Create or update tenant addon
        existing = (
            db.query(TenantAddonV2)
            .filter(TenantAddonV2.tenant_id == tenant_id, TenantAddonV2.addon_slug == addon_slug)
            .first()
        )

        if existing:
            existing.quantity += quantity
            existing.status = "active"
        else:
            addon = TenantAddonV2(
                tenant_id=tenant_id,
                addon_slug=addon_slug,
                quantity=quantity,
                status="active",
                stripe_subscription_item_id=session.get("subscription"),
            )
            db.add(addon)

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.ADDON_PURCHASED,
            payload={"addon_slug": addon_slug, "quantity": quantity},
            actor_type="stripe",
            stripe_event_id=event_id,
            idempotency_key=f"addon_{event_id}",
        )

        db.commit()
        return {"action": "addon_purchased", "addon_slug": addon_slug, "quantity": quantity}

    # ── Subscription Created ────────────────────────────────────────────

    async def _handle_subscription_created(self, db: Session, event: dict) -> dict:
        """Handle customer.subscription.created."""
        sub_data = event["data"]["object"]
        tenant_id = self._extract_tenant_id(sub_data)
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id"}

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_CREATED,
            payload={"stripe_subscription_id": sub_data.get("id"), "status": sub_data.get("status")},
            actor_type="stripe",
            stripe_event_id=event["id"],
            idempotency_key=f"sub_created_{event['id']}",
        )

        db.commit()
        return {"action": "subscription_created", "tenant_id": tenant_id}

    # ── Subscription Updated ────────────────────────────────────────────

    async def _handle_subscription_updated(self, db: Session, event: dict) -> dict:
        """Handle customer.subscription.updated — sync status changes."""
        sub_data = event["data"]["object"]
        tenant_id = self._extract_tenant_id(sub_data)
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id"}

        try:
            await subscription_service.sync_from_stripe(db, tenant_id, sub_data)
        except ValueError:
            pass

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_UPDATED,
            payload={
                "stripe_subscription_id": sub_data.get("id"),
                "status": sub_data.get("status"),
                "cancel_at_period_end": sub_data.get("cancel_at_period_end"),
            },
            actor_type="stripe",
            stripe_event_id=event["id"],
            idempotency_key=f"sub_updated_{event['id']}",
        )

        db.commit()
        return {"action": "subscription_updated", "tenant_id": tenant_id}

    # ── Subscription Deleted ────────────────────────────────────────────

    async def _handle_subscription_deleted(self, db: Session, event: dict) -> dict:
        """Handle customer.subscription.deleted — mark as canceled."""
        sub_data = event["data"]["object"]
        tenant_id = self._extract_tenant_id(sub_data)
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id"}

        sub = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()
        if sub:
            sub.status = SubscriptionStatus.CANCELED
            sub.canceled_at = datetime.now(timezone.utc)

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.SUBSCRIPTION_CANCELED,
            payload={
                "stripe_subscription_id": sub_data.get("id"),
                "reason": "stripe_deleted",
            },
            actor_type="stripe",
            stripe_event_id=event["id"],
            idempotency_key=f"sub_deleted_{event['id']}",
        )

        db.commit()
        return {"action": "subscription_canceled", "tenant_id": tenant_id}

    # ── Invoice Paid ────────────────────────────────────────────────────

    async def _handle_invoice_paid(self, db: Session, event: dict) -> dict:
        """Handle invoice.paid — record payment and update subscription."""
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        tenant_id = self._tenant_from_customer(db, customer_id)
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id"}

        # Update or create invoice record
        local = db.query(InvoiceRecord).filter(InvoiceRecord.stripe_invoice_id == invoice["id"]).first()
        if not local:
            local = InvoiceRecord(
                tenant_id=tenant_id,
                stripe_invoice_id=invoice["id"],
            )
            db.add(local)

        local.stripe_subscription_id = invoice.get("subscription")
        local.number = invoice.get("number")
        local.status = "paid"
        local.currency = invoice.get("currency", "eur")
        local.amount_due_cents = invoice.get("amount_due", 0)
        local.amount_paid_cents = invoice.get("amount_paid", 0)
        local.amount_remaining_cents = 0
        local.hosted_invoice_url = invoice.get("hosted_invoice_url")
        local.invoice_pdf_url = invoice.get("invoice_pdf")
        local.paid_at = datetime.now(timezone.utc)

        # Update subscription latest invoice
        sub = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()
        if sub:
            sub.stripe_latest_invoice_id = invoice["id"]

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.INVOICE_PAID,
            payload={
                "invoice_id": invoice["id"],
                "amount_paid": invoice.get("amount_paid"),
                "currency": invoice.get("currency"),
            },
            actor_type="stripe",
            stripe_event_id=event["id"],
            idempotency_key=f"invoice_paid_{event['id']}",
        )

        db.commit()
        return {"action": "invoice_paid", "tenant_id": tenant_id, "amount": invoice.get("amount_paid")}

    # ── Invoice Payment Failed ──────────────────────────────────────────

    async def _handle_invoice_payment_failed(self, db: Session, event: dict) -> dict:
        """Handle invoice.payment_failed — mark subscription as past_due."""
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        tenant_id = self._tenant_from_customer(db, customer_id)
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id"}

        sub = db.query(SubscriptionV2).filter(SubscriptionV2.tenant_id == tenant_id).first()
        if sub:
            sub.status = SubscriptionStatus.PAST_DUE

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.PAYMENT_FAILED,
            payload={
                "invoice_id": invoice["id"],
                "amount_due": invoice.get("amount_due"),
                "attempt_count": invoice.get("attempt_count"),
            },
            actor_type="stripe",
            stripe_event_id=event["id"],
            idempotency_key=f"payment_failed_{event['id']}",
        )

        db.commit()
        return {"action": "payment_failed", "tenant_id": tenant_id}

    # ── Invoice Finalized ───────────────────────────────────────────────

    async def _handle_invoice_finalized(self, db: Session, event: dict) -> dict:
        """Handle invoice.finalized — cache the invoice."""
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        tenant_id = self._tenant_from_customer(db, customer_id)
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id"}

        local = db.query(InvoiceRecord).filter(InvoiceRecord.stripe_invoice_id == invoice["id"]).first()
        if not local:
            local = InvoiceRecord(
                tenant_id=tenant_id,
                stripe_invoice_id=invoice["id"],
            )
            db.add(local)

        local.stripe_subscription_id = invoice.get("subscription")
        local.number = invoice.get("number")
        local.status = invoice.get("status", "open")
        local.currency = invoice.get("currency", "eur")
        local.amount_due_cents = invoice.get("amount_due", 0)
        local.hosted_invoice_url = invoice.get("hosted_invoice_url")
        local.invoice_pdf_url = invoice.get("invoice_pdf")

        db.commit()
        return {"action": "invoice_cached", "tenant_id": tenant_id}

    # ── Customer Events ─────────────────────────────────────────────────

    async def _handle_customer_created(self, db: Session, event: dict) -> dict:
        """Handle customer.created."""
        customer = event["data"]["object"]
        tenant_id = int(customer.get("metadata", {}).get("tenant_id", 0))
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id_in_metadata"}

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.CUSTOMER_CREATED,
            payload={"customer_id": customer["id"], "email": customer.get("email")},
            actor_type="stripe",
            stripe_event_id=event["id"],
            idempotency_key=f"customer_created_{event['id']}",
        )

        db.commit()
        return {"action": "customer_created", "tenant_id": tenant_id}

    async def _handle_customer_updated(self, db: Session, event: dict) -> dict:
        """Handle customer.updated."""
        customer = event["data"]["object"]
        tenant_id = int(customer.get("metadata", {}).get("tenant_id", 0))
        if not tenant_id:
            return {"action": "skipped", "reason": "no_tenant_id_in_metadata"}

        await billing_events.emit(
            db=db,
            tenant_id=tenant_id,
            event_type=BillingEventType.CUSTOMER_UPDATED,
            payload={"customer_id": customer["id"]},
            actor_type="stripe",
            stripe_event_id=event["id"],
            idempotency_key=f"customer_updated_{event['id']}",
        )

        db.commit()
        return {"action": "customer_updated", "tenant_id": tenant_id}

    # ── Helpers ─────────────────────────────────────────────────────────

    def _extract_tenant_id(self, stripe_obj: dict) -> Optional[int]:
        """Extract tenant_id from Stripe object metadata."""
        metadata = stripe_obj.get("metadata", {})
        tid = metadata.get("tenant_id")
        if tid:
            try:
                return int(tid)
            except (ValueError, TypeError):
                pass
        return None

    def _tenant_from_customer(self, db: Session, customer_id: Optional[str]) -> Optional[int]:
        """Find tenant_id from Stripe customer_id."""
        if not customer_id:
            return None
        sub = db.query(SubscriptionV2).filter(SubscriptionV2.stripe_customer_id == customer_id).first()
        return sub.tenant_id if sub else None


# Singleton
webhook_processor = WebhookProcessorV2()
