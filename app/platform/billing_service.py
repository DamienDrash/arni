"""app/platform/billing_service.py — Enterprise Billing Service.

Provides metered billing infrastructure for ARIIA SaaS:
- Usage tracking per conversation/API call
- Stripe webhook processing with idempotency
- Plan enforcement (feature gating based on subscription)
- Proration handling for upgrades/downgrades
- Invoice lifecycle management

This service layer sits between the existing billing router and Stripe,
adding reliability, metering, and enterprise-grade billing logic.
"""
from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

class UsageType(str, Enum):
    """Types of billable usage."""
    CONVERSATION = "conversation"
    API_CALL = "api_call"
    TOKEN_INPUT = "token_input"
    TOKEN_OUTPUT = "token_output"
    KNOWLEDGE_QUERY = "knowledge_query"
    VOICE_MINUTE = "voice_minute"
    EMAIL_SENT = "email_sent"


class BillingEvent(str, Enum):
    """Stripe webhook events we handle."""
    CHECKOUT_COMPLETED = "checkout.session.completed"
    SUB_CREATED = "customer.subscription.created"
    SUB_UPDATED = "customer.subscription.updated"
    SUB_DELETED = "customer.subscription.deleted"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_SUCCEEDED = "invoice.payment_succeeded"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    PAYMENT_INTENT_SUCCEEDED = "payment_intent.succeeded"


class PlanTier(str, Enum):
    """Subscription plan tiers with feature gates."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


@dataclass
class UsageRecord:
    """A single usage event for billing."""
    tenant_id: int
    usage_type: UsageType
    quantity: int = 1
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    idempotency_key: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["usage_type"] = self.usage_type.value
        return d


@dataclass
class PlanLimits:
    """Limits for a subscription plan."""
    max_monthly_conversations: Optional[int] = None
    max_monthly_api_calls: Optional[int] = None
    max_monthly_tokens: Optional[int] = None
    max_channels: int = 1
    max_integrations: int = 0
    max_knowledge_docs: int = 10
    max_team_members: int = 1
    features: list[str] = field(default_factory=list)

    @classmethod
    def for_tier(cls, tier: PlanTier) -> "PlanLimits":
        """Get default limits for a plan tier."""
        defaults = {
            PlanTier.FREE: cls(
                max_monthly_conversations=50,
                max_monthly_api_calls=100,
                max_monthly_tokens=100_000,
                max_channels=1,
                max_integrations=0,
                max_knowledge_docs=5,
                max_team_members=1,
                features=["basic_chat", "knowledge_base"],
            ),
            PlanTier.STARTER: cls(
                max_monthly_conversations=500,
                max_monthly_api_calls=1000,
                max_monthly_tokens=500_000,
                max_channels=2,
                max_integrations=1,
                max_knowledge_docs=50,
                max_team_members=3,
                features=["basic_chat", "knowledge_base", "analytics_basic",
                          "email_channel", "manual_crm"],
            ),
            PlanTier.PROFESSIONAL: cls(
                max_monthly_conversations=5000,
                max_monthly_api_calls=10_000,
                max_monthly_tokens=2_000_000,
                max_channels=5,
                max_integrations=5,
                max_knowledge_docs=500,
                max_team_members=10,
                features=["basic_chat", "knowledge_base", "analytics_advanced",
                          "email_channel", "integrations", "voice",
                          "custom_prompts", "brand_voice", "api_access"],
            ),
            PlanTier.BUSINESS: cls(
                max_monthly_conversations=25_000,
                max_monthly_api_calls=50_000,
                max_monthly_tokens=10_000_000,
                max_channels=10,
                max_integrations=15,
                max_knowledge_docs=2000,
                max_team_members=50,
                features=["basic_chat", "knowledge_base", "analytics_advanced",
                          "email_channel", "integrations", "voice",
                          "custom_prompts", "brand_voice", "api_access",
                          "sso", "audit_log", "priority_support",
                          "white_label_basic"],
            ),
            PlanTier.ENTERPRISE: cls(
                max_monthly_conversations=None,  # Unlimited
                max_monthly_api_calls=None,
                max_monthly_tokens=None,
                max_channels=99,
                max_integrations=99,
                max_knowledge_docs=10_000,
                max_team_members=999,
                features=["basic_chat", "knowledge_base", "analytics_advanced",
                          "email_channel", "integrations", "voice",
                          "custom_prompts", "brand_voice", "api_access",
                          "sso", "audit_log", "priority_support",
                          "white_label_full", "dedicated_support",
                          "custom_models", "on_premise"],
            ),
        }
        return defaults.get(tier, defaults[PlanTier.FREE])


# ══════════════════════════════════════════════════════════════════════════════
# USAGE TRACKER
# ══════════════════════════════════════════════════════════════════════════════

class UsageTracker:
    """Tracks and aggregates usage for metered billing.

    Uses Redis for real-time counters and periodically flushes to the database.
    Supports idempotency keys to prevent double-counting.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_buffer: list[UsageRecord] = []
        self._seen_keys: set[str] = set()

    def _usage_key(self, tenant_id: int, usage_type: str, period: str) -> str:
        """Redis key for usage counter."""
        return f"billing:usage:{tenant_id}:{usage_type}:{period}"

    def _current_period(self) -> str:
        """Current billing period (YYYY-MM)."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    async def record_usage(self, record: UsageRecord) -> bool:
        """Record a usage event. Returns True if recorded, False if duplicate."""
        # Idempotency check
        if record.idempotency_key:
            if record.idempotency_key in self._seen_keys:
                return False
            if self._redis:
                try:
                    dedup_key = f"billing:dedup:{record.idempotency_key}"
                    was_set = await self._redis.set(dedup_key, "1", nx=True, ex=86400)
                    if not was_set:
                        return False
                except Exception:
                    pass
            self._seen_keys.add(record.idempotency_key)

        # Increment Redis counter
        period = self._current_period()
        if self._redis:
            try:
                key = self._usage_key(record.tenant_id, record.usage_type.value, period)
                await self._redis.incrby(key, record.quantity)
                await self._redis.expire(key, 90 * 86400)  # 90 days TTL
            except Exception as e:
                logger.warning("billing.redis_increment_failed", error=str(e))

        self._local_buffer.append(record)
        logger.info("billing.usage_recorded",
                     tenant_id=record.tenant_id,
                     type=record.usage_type.value,
                     quantity=record.quantity)
        return True

    async def get_usage(self, tenant_id: int, usage_type: UsageType,
                        period: Optional[str] = None) -> int:
        """Get current usage count for a tenant."""
        period = period or self._current_period()

        if self._redis:
            try:
                key = self._usage_key(tenant_id, usage_type.value, period)
                val = await self._redis.get(key)
                return int(val) if val else 0
            except Exception:
                pass

        # Fallback: count from local buffer
        return sum(
            r.quantity for r in self._local_buffer
            if r.tenant_id == tenant_id
            and r.usage_type == usage_type
            and r.timestamp.startswith(period)
        )

    async def get_all_usage(self, tenant_id: int,
                            period: Optional[str] = None) -> dict[str, int]:
        """Get all usage counters for a tenant."""
        period = period or self._current_period()
        result = {}
        for ut in UsageType:
            result[ut.value] = await self.get_usage(tenant_id, ut, period)
        return result

    async def check_limit(self, tenant_id: int, usage_type: UsageType,
                          limit: Optional[int]) -> dict[str, Any]:
        """Check if a tenant is within their usage limit."""
        if limit is None:
            return {"within_limit": True, "current": 0, "limit": None, "percent": 0}

        current = await self.get_usage(tenant_id, usage_type)
        percent = round(current / limit * 100, 1) if limit > 0 else 0

        return {
            "within_limit": current < limit,
            "current": current,
            "limit": limit,
            "percent": percent,
            "remaining": max(0, limit - current),
        }

    def flush_buffer(self) -> list[UsageRecord]:
        """Flush the local buffer and return records for DB persistence."""
        records = self._local_buffer.copy()
        self._local_buffer.clear()
        return records


# ══════════════════════════════════════════════════════════════════════════════
# STRIPE WEBHOOK PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

class StripeWebhookProcessor:
    """Processes Stripe webhook events with idempotency and error handling.

    Handles the complete subscription lifecycle:
    - Checkout completion → Subscription activation
    - Subscription updates → Plan changes, status sync
    - Invoice events → Payment tracking, dunning
    """

    def __init__(self):
        self._processed_events: set[str] = set()
        self._handlers: dict[str, Any] = {
            BillingEvent.CHECKOUT_COMPLETED.value: self._handle_checkout_completed,
            BillingEvent.SUB_CREATED.value: self._handle_subscription_created,
            BillingEvent.SUB_UPDATED.value: self._handle_subscription_updated,
            BillingEvent.SUB_DELETED.value: self._handle_subscription_deleted,
            BillingEvent.INVOICE_PAID.value: self._handle_invoice_paid,
            BillingEvent.INVOICE_PAYMENT_SUCCEEDED.value: self._handle_invoice_paid,
            BillingEvent.INVOICE_PAYMENT_FAILED.value: self._handle_invoice_failed,
        }

    async def process_event(self, event_type: str, event_id: str,
                            data: dict) -> dict[str, Any]:
        """Process a Stripe webhook event with idempotency."""
        # Idempotency check
        if event_id in self._processed_events:
            logger.info("billing.event_duplicate", event_id=event_id)
            return {"status": "duplicate", "event_id": event_id}

        handler = self._handlers.get(event_type)
        if not handler:
            logger.info("billing.event_unhandled", event_type=event_type)
            return {"status": "unhandled", "event_type": event_type}

        try:
            result = await handler(data)
            self._processed_events.add(event_id)

            # Limit memory usage
            if len(self._processed_events) > 10_000:
                # Keep only the last 5000
                self._processed_events = set(list(self._processed_events)[-5000:])

            logger.info("billing.event_processed",
                        event_type=event_type, event_id=event_id)
            return {"status": "processed", "event_type": event_type, **result}

        except Exception as e:
            logger.error("billing.event_failed",
                         event_type=event_type, event_id=event_id, error=str(e))
            return {"status": "error", "event_type": event_type, "error": str(e)}

    async def _handle_checkout_completed(self, data: dict) -> dict:
        """Handle checkout.session.completed → Activate subscription."""
        obj = data.get("object", {})
        customer_id = obj.get("customer", "")
        subscription_id = obj.get("subscription", "")
        metadata = obj.get("metadata", {})
        tenant_id = metadata.get("tenant_id")

        logger.info("billing.checkout_completed",
                     customer_id=customer_id, subscription_id=subscription_id,
                     tenant_id=tenant_id)

        return {
            "action": "subscription_activated",
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "tenant_id": tenant_id,
        }

    async def _handle_subscription_created(self, data: dict) -> dict:
        """Handle customer.subscription.created → Initial setup."""
        obj = data.get("object", {})
        return {
            "action": "subscription_created",
            "subscription_id": obj.get("id", ""),
            "status": obj.get("status", ""),
            "plan": obj.get("plan", {}).get("id", ""),
        }

    async def _handle_subscription_updated(self, data: dict) -> dict:
        """Handle customer.subscription.updated → Plan change, status sync."""
        obj = data.get("object", {})
        previous = data.get("previous_attributes", {})

        changes = {}
        if "status" in previous:
            changes["status"] = {"from": previous["status"], "to": obj.get("status")}
        if "plan" in previous:
            changes["plan"] = {
                "from": previous.get("plan", {}).get("id", ""),
                "to": obj.get("plan", {}).get("id", ""),
            }
        if "cancel_at_period_end" in previous:
            changes["cancel_at_period_end"] = obj.get("cancel_at_period_end")

        logger.info("billing.subscription_updated",
                     subscription_id=obj.get("id"), changes=changes)

        return {
            "action": "subscription_updated",
            "subscription_id": obj.get("id", ""),
            "status": obj.get("status", ""),
            "changes": changes,
        }

    async def _handle_subscription_deleted(self, data: dict) -> dict:
        """Handle customer.subscription.deleted → Deactivate."""
        obj = data.get("object", {})
        logger.info("billing.subscription_deleted",
                     subscription_id=obj.get("id"))

        return {
            "action": "subscription_canceled",
            "subscription_id": obj.get("id", ""),
        }

    async def _handle_invoice_paid(self, data: dict) -> dict:
        """Handle invoice.paid → Renew period, update status."""
        obj = data.get("object", {})
        amount = obj.get("amount_paid", 0)
        currency = obj.get("currency", "eur")

        logger.info("billing.invoice_paid",
                     invoice_id=obj.get("id"),
                     amount=amount, currency=currency)

        return {
            "action": "invoice_paid",
            "invoice_id": obj.get("id", ""),
            "amount_cents": amount,
            "currency": currency,
            "subscription_id": obj.get("subscription", ""),
        }

    async def _handle_invoice_failed(self, data: dict) -> dict:
        """Handle invoice.payment_failed → Mark as past_due."""
        obj = data.get("object", {})
        attempt_count = obj.get("attempt_count", 0)

        logger.warning("billing.invoice_failed",
                       invoice_id=obj.get("id"),
                       attempt_count=attempt_count)

        return {
            "action": "payment_failed",
            "invoice_id": obj.get("id", ""),
            "attempt_count": attempt_count,
            "next_attempt": obj.get("next_payment_attempt"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# PLAN ENFORCER
# ══════════════════════════════════════════════════════════════════════════════

class PlanEnforcer:
    """Enforces plan limits and feature gates.

    Checks whether a tenant's requested action is allowed by their current plan.
    Used as middleware/guard in API endpoints and agent runtime.
    """

    def __init__(self, usage_tracker: Optional[UsageTracker] = None):
        self._usage_tracker = usage_tracker or UsageTracker()
        self._plan_cache: dict[int, tuple[PlanTier, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    def _get_cached_plan(self, tenant_id: int) -> Optional[PlanTier]:
        """Get cached plan tier for a tenant."""
        if tenant_id in self._plan_cache:
            tier, cached_at = self._plan_cache[tenant_id]
            if time.time() - cached_at < self._cache_ttl:
                return tier
        return None

    def set_plan(self, tenant_id: int, tier: PlanTier) -> None:
        """Set/cache the plan tier for a tenant."""
        self._plan_cache[tenant_id] = (tier, time.time())

    def get_limits(self, tier: PlanTier) -> PlanLimits:
        """Get the limits for a plan tier."""
        return PlanLimits.for_tier(tier)

    def check_feature(self, tier: PlanTier, feature: str) -> bool:
        """Check if a feature is available in a plan tier."""
        limits = PlanLimits.for_tier(tier)
        return feature in limits.features

    async def check_conversation_limit(self, tenant_id: int,
                                        tier: PlanTier) -> dict[str, Any]:
        """Check if tenant can start a new conversation."""
        limits = PlanLimits.for_tier(tier)
        return await self._usage_tracker.check_limit(
            tenant_id, UsageType.CONVERSATION,
            limits.max_monthly_conversations,
        )

    async def check_api_limit(self, tenant_id: int,
                               tier: PlanTier) -> dict[str, Any]:
        """Check if tenant can make an API call."""
        limits = PlanLimits.for_tier(tier)
        return await self._usage_tracker.check_limit(
            tenant_id, UsageType.API_CALL,
            limits.max_monthly_api_calls,
        )

    def check_integration_limit(self, tier: PlanTier,
                                 current_count: int) -> dict[str, Any]:
        """Check if tenant can activate another integration."""
        limits = PlanLimits.for_tier(tier)
        return {
            "within_limit": current_count < limits.max_integrations,
            "current": current_count,
            "limit": limits.max_integrations,
            "remaining": max(0, limits.max_integrations - current_count),
        }

    def check_channel_limit(self, tier: PlanTier,
                             current_count: int) -> dict[str, Any]:
        """Check if tenant can add another channel."""
        limits = PlanLimits.for_tier(tier)
        return {
            "within_limit": current_count < limits.max_channels,
            "current": current_count,
            "limit": limits.max_channels,
            "remaining": max(0, limits.max_channels - current_count),
        }

    def get_plan_comparison(self) -> list[dict[str, Any]]:
        """Get a comparison of all plan tiers for pricing page."""
        comparison = []
        for tier in PlanTier:
            limits = PlanLimits.for_tier(tier)
            comparison.append({
                "tier": tier.value,
                "limits": {
                    "conversations": limits.max_monthly_conversations,
                    "api_calls": limits.max_monthly_api_calls,
                    "tokens": limits.max_monthly_tokens,
                    "channels": limits.max_channels,
                    "integrations": limits.max_integrations,
                    "knowledge_docs": limits.max_knowledge_docs,
                    "team_members": limits.max_team_members,
                },
                "features": limits.features,
            })
        return comparison
