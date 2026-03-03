"""
ARIIA Billing V2 – Data Models

Enterprise-grade billing data model with:
- Versioned plan definitions with decoupled feature sets
- Event-sourced audit trail for all billing state changes
- Granular usage metering with daily/monthly aggregation
- Idempotent webhook event tracking
- Coupon/discount support
- Invoice history

All V2 tables use the prefix 'billing_' to coexist with V1 during migration.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.db import Base


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class SubscriptionStatus(str, enum.Enum):
    """Canonical subscription statuses aligned with Stripe."""
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"


class BillingInterval(str, enum.Enum):
    MONTH = "month"
    YEAR = "year"


class FeatureType(str, enum.Enum):
    """How a feature is gated."""
    BOOLEAN = "boolean"          # On/off toggle (e.g., api_access_enabled)
    LIMIT = "limit"              # Numeric limit (e.g., max 500 contacts)
    TIER = "tier"                # Tiered value (e.g., ai_tier = "basic"|"premium")
    METERED = "metered"          # Usage-based, tracked per period


class BillingEventType(str, enum.Enum):
    """All billing-relevant events for the audit trail."""
    # Subscription lifecycle
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_ACTIVATED = "subscription.activated"
    SUBSCRIPTION_UPGRADED = "subscription.upgraded"
    SUBSCRIPTION_DOWNGRADED = "subscription.downgraded"
    SUBSCRIPTION_CANCELED = "subscription.canceled"
    SUBSCRIPTION_REACTIVATED = "subscription.reactivated"
    SUBSCRIPTION_EXPIRED = "subscription.expired"
    SUBSCRIPTION_PAUSED = "subscription.paused"
    SUBSCRIPTION_RESUMED = "subscription.resumed"
    SUBSCRIPTION_TRIAL_STARTED = "subscription.trial_started"
    SUBSCRIPTION_TRIAL_ENDED = "subscription.trial_ended"
    # Payment events
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    # Invoice events
    INVOICE_CREATED = "invoice.created"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    INVOICE_VOIDED = "invoice.voided"
    # Plan & feature changes
    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"
    PLAN_ARCHIVED = "plan.archived"
    FEATURE_SET_UPDATED = "feature_set.updated"
    # Addon events
    ADDON_ACTIVATED = "addon.activated"
    ADDON_DEACTIVATED = "addon.deactivated"
    # Usage events
    USAGE_LIMIT_REACHED = "usage.limit_reached"
    USAGE_OVERAGE_STARTED = "usage.overage_started"
    # Token purchases
    TOKEN_PURCHASE_COMPLETED = "token_purchase.completed"
    # Stripe sync
    STRIPE_SYNC_COMPLETED = "stripe.sync_completed"
    STRIPE_WEBHOOK_RECEIVED = "stripe.webhook_received"
    STRIPE_WEBHOOK_PROCESSED = "stripe.webhook_processed"
    STRIPE_WEBHOOK_FAILED = "stripe.webhook_failed"


def _utcnow():
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

class Feature(Base):
    """
    A single gatable feature in the ARIIA platform.

    Features are the atomic units of access control. Each feature has a type
    that determines how it is enforced:
    - BOOLEAN: simple on/off (e.g., 'api_access')
    - LIMIT: numeric cap (e.g., 'max_monthly_messages' = 500)
    - TIER: string tier (e.g., 'ai_tier' = 'premium')
    - METERED: usage-tracked per billing period
    """
    __tablename__ = "billing_features"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    feature_type = Column(
        Enum(FeatureType, name="billing_feature_type_enum"),
        nullable=False,
        default=FeatureType.BOOLEAN,
    )
    category = Column(String(50), nullable=True)  # "channel", "ai", "analytics", "integration"
    unit = Column(String(50), nullable=True)       # "messages", "tokens", "members", "channels"
    is_active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    entitlements = relationship("FeatureEntitlement", back_populates="feature", cascade="all, delete-orphan")


class FeatureSet(Base):
    """
    A named collection of feature entitlements.

    Each Plan references a FeatureSet. This decouples plan pricing from
    feature definitions, allowing:
    - Multiple plans to share the same feature set
    - Feature sets to be versioned independently of plans
    - A/B testing of feature configurations
    """
    __tablename__ = "billing_feature_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    entitlements = relationship("FeatureEntitlement", back_populates="feature_set", cascade="all, delete-orphan")
    plans = relationship("PlanV2", back_populates="feature_set", foreign_keys="[PlanV2.feature_set_id]")


class FeatureEntitlement(Base):
    """
    Links a Feature to a FeatureSet with a specific configuration.

    This is the join table that defines what a feature set grants:
    - For BOOLEAN features: value_bool = True/False
    - For LIMIT features: value_limit = 500 (NULL = unlimited)
    - For TIER features: value_tier = "premium"
    - For METERED features: value_limit = soft cap, hard_limit = hard cap
    """
    __tablename__ = "billing_feature_entitlements"

    id = Column(Integer, primary_key=True, index=True)
    feature_set_id = Column(Integer, ForeignKey("billing_feature_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_id = Column(Integer, ForeignKey("billing_features.id", ondelete="CASCADE"), nullable=False, index=True)

    # Value fields — use the one matching the feature type
    value_bool = Column(Boolean, nullable=True)
    value_limit = Column(Integer, nullable=True)       # NULL = unlimited for LIMIT type
    value_tier = Column(String(50), nullable=True)
    hard_limit = Column(Integer, nullable=True)         # For METERED: hard cap (blocks usage)
    overage_price_cents = Column(Integer, nullable=True) # Price per unit above soft limit

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    feature_set = relationship("FeatureSet", back_populates="entitlements")
    feature = relationship("Feature", back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint("feature_set_id", "feature_id", name="uq_entitlement_set_feature"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# PLANS V2
# ══════════════════════════════════════════════════════════════════════════════

class PlanV2(Base):
    """
    Versioned subscription plan.

    Key improvements over V1:
    - Feature definitions are decoupled into FeatureSets
    - Supports multiple price points (monthly, yearly, custom intervals)
    - Built-in trial configuration
    - Stripe IDs for both monthly and yearly prices
    - Display metadata for pricing pages
    """
    __tablename__ = "billing_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    tagline = Column(String(300), nullable=True)  # Short marketing text

    # Pricing
    price_monthly_cents = Column(Integer, nullable=False, default=0)
    price_yearly_cents = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, default="eur")

    # Stripe references
    stripe_product_id = Column(String(100), nullable=True, index=True)
    stripe_price_monthly_id = Column(String(100), nullable=True)
    stripe_price_yearly_id = Column(String(100), nullable=True)

    # Feature set reference (decoupled)
    feature_set_id = Column(Integer, ForeignKey("billing_feature_sets.id"), nullable=True)

    # Trial configuration
    trial_days = Column(Integer, nullable=False, default=0)
    trial_feature_set_id = Column(Integer, ForeignKey("billing_feature_sets.id"), nullable=True)

    # Display
    display_order = Column(Integer, nullable=False, default=0)
    is_highlighted = Column(Boolean, nullable=False, default=False)
    highlight_label = Column(String(50), nullable=True)  # e.g., "Beliebteste Wahl"
    icon = Column(String(50), nullable=True)
    features_json = Column(Text, nullable=True)  # JSON list of display strings for pricing page
    cta_text = Column(String(100), nullable=True)  # Call-to-action button text

    # Visibility
    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=True)

    # Versioning
    version = Column(Integer, nullable=False, default=1)

    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    feature_set = relationship("FeatureSet", back_populates="plans", foreign_keys=[feature_set_id])
    subscriptions = relationship("SubscriptionV2", back_populates="plan")


# ══════════════════════════════════════════════════════════════════════════════
# ADDON DEFINITIONS V2
# ══════════════════════════════════════════════════════════════════════════════

class AddonDefinitionV2(Base):
    """
    Global add-on catalog with improved feature linking.

    Add-ons can grant additional features or increase limits beyond
    what the base plan provides. Each addon references a FeatureSet
    that defines what it unlocks.
    """
    __tablename__ = "billing_addon_definitions"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    icon = Column(String(50), nullable=True)

    # Pricing
    price_monthly_cents = Column(Integer, nullable=False, default=0)
    price_yearly_cents = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, default="eur")

    # Stripe references
    stripe_product_id = Column(String(100), nullable=True, index=True)
    stripe_price_id = Column(String(100), nullable=True)

    # Feature set this addon grants
    feature_set_id = Column(Integer, ForeignKey("billing_feature_sets.id"), nullable=True)

    # Legacy: JSON list of feature keys (for backward compat)
    features_json = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    is_stackable = Column(Boolean, nullable=False, default=False)  # Can be purchased multiple times
    max_quantity = Column(Integer, nullable=True)  # Max quantity if stackable
    display_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTIONS V2
# ══════════════════════════════════════════════════════════════════════════════

class SubscriptionV2(Base):
    """
    Tenant subscription with full lifecycle tracking.

    Improvements over V1:
    - Explicit status enum aligned with Stripe
    - Billing interval tracking
    - Scheduled plan changes (pending_plan_id + scheduled_change_at)
    - Stripe metadata caching
    """
    __tablename__ = "billing_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    plan_id = Column(Integer, ForeignKey("billing_plans.id"), nullable=False, index=True)

    # Status
    status = Column(
        Enum(SubscriptionStatus, name="billing_subscription_status_enum"),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )

    # Billing
    billing_interval = Column(
        Enum(BillingInterval, name="billing_interval_enum"),
        nullable=False,
        default=BillingInterval.MONTH,
    )

    # Stripe references
    stripe_subscription_id = Column(String(100), nullable=True, unique=True, index=True)
    stripe_customer_id = Column(String(100), nullable=True, index=True)
    stripe_latest_invoice_id = Column(String(100), nullable=True)

    # Period tracking
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)

    # Trial
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)

    # Cancellation
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    canceled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)

    # Scheduled plan change (for downgrades)
    pending_plan_id = Column(Integer, ForeignKey("billing_plans.id"), nullable=True)
    scheduled_change_at = Column(DateTime, nullable=True)

    # Metadata
    metadata_json = Column(Text, nullable=True)  # Arbitrary JSON metadata

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    plan = relationship("PlanV2", back_populates="subscriptions", foreign_keys=[plan_id])
    addons = relationship("TenantAddonV2", back_populates="subscription", cascade="all, delete-orphan")


class TenantAddonV2(Base):
    """
    Active add-on instance for a tenant's subscription.
    """
    __tablename__ = "billing_tenant_addons"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("billing_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    addon_slug = Column(String(100), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="active")  # active, canceled, expired

    # Stripe references
    stripe_subscription_item_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    subscription = relationship("SubscriptionV2", back_populates="addons")

    __table_args__ = (
        Index("ix_tenant_addon_sub_slug", "subscription_id", "addon_slug"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# USAGE METERING
# ══════════════════════════════════════════════════════════════════════════════

class UsageRecordV2(Base):
    """
    Granular usage record for metered billing.

    Stores per-tenant, per-feature, per-period usage counters.
    Supports both soft limits (warnings) and hard limits (blocks).
    """
    __tablename__ = "billing_usage_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    feature_key = Column(String(100), nullable=False, index=True)

    # Period
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)

    # Counters
    usage_count = Column(Integer, nullable=False, default=0)
    overage_count = Column(Integer, nullable=False, default=0)  # Usage above soft limit

    # Snapshot of limits at time of recording (for historical accuracy)
    soft_limit_snapshot = Column(Integer, nullable=True)
    hard_limit_snapshot = Column(Integer, nullable=True)

    # Timestamps
    first_recorded_at = Column(DateTime, default=_utcnow)
    last_recorded_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "feature_key", "period_year", "period_month",
            name="uq_usage_tenant_feature_period",
        ),
        Index("ix_usage_tenant_period", "tenant_id", "period_year", "period_month"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# BILLING EVENTS (Event Sourcing / Audit Trail)
# ══════════════════════════════════════════════════════════════════════════════

class BillingEvent(Base):
    """
    Immutable event log for all billing-related state changes.

    This is the core of the event-sourcing approach. Every billing action
    (subscription change, payment, usage threshold, etc.) is recorded as
    an immutable event. This provides:
    - Complete audit trail for compliance
    - Ability to reconstruct billing state at any point in time
    - Debugging and dispute resolution
    - Analytics and reporting
    """
    __tablename__ = "billing_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    event_type = Column(
        Enum(BillingEventType, name="billing_event_type_enum"),
        nullable=False,
        index=True,
    )

    # Event payload (JSON)
    payload_json = Column(Text, nullable=True)

    # Actor (who triggered this event)
    actor_type = Column(String(20), nullable=True)  # "user", "system", "stripe", "cron"
    actor_id = Column(String(100), nullable=True)    # user_id, "stripe_webhook", "system"

    # Stripe correlation
    stripe_event_id = Column(String(100), nullable=True, index=True)

    # Idempotency
    idempotency_key = Column(String(200), nullable=True, unique=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=_utcnow, index=True)

    __table_args__ = (
        Index("ix_billing_event_tenant_type", "tenant_id", "event_type"),
        Index("ix_billing_event_created", "created_at"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK EVENT LOG
# ══════════════════════════════════════════════════════════════════════════════

class WebhookEventLog(Base):
    """
    Tracks all incoming Stripe webhook events for idempotency and debugging.

    Every webhook is logged before processing. The processing_status tracks
    whether it was handled successfully, failed, or is still pending.
    """
    __tablename__ = "billing_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    stripe_event_id = Column(String(100), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload_json = Column(Text, nullable=True)

    # Processing status
    processing_status = Column(String(20), nullable=False, default="pending")  # pending, processed, failed, skipped
    processing_error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)

    # Timing
    received_at = Column(DateTime, default=_utcnow)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_webhook_status", "processing_status"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# INVOICE HISTORY
# ══════════════════════════════════════════════════════════════════════════════

class InvoiceRecord(Base):
    """
    Local cache of Stripe invoices for quick access and reporting.
    """
    __tablename__ = "billing_invoices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    stripe_invoice_id = Column(String(100), unique=True, nullable=False, index=True)
    stripe_subscription_id = Column(String(100), nullable=True)

    # Invoice details
    number = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False)  # draft, open, paid, void, uncollectible
    currency = Column(String(3), nullable=False, default="eur")
    amount_due_cents = Column(Integer, nullable=False, default=0)
    amount_paid_cents = Column(Integer, nullable=False, default=0)
    amount_remaining_cents = Column(Integer, nullable=False, default=0)

    # URLs
    hosted_invoice_url = Column(Text, nullable=True)
    invoice_pdf_url = Column(Text, nullable=True)

    # Period
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=_utcnow)
    paid_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)


# ══════════════════════════════════════════════════════════════════════════════
# COUPON / DISCOUNT
# ══════════════════════════════════════════════════════════════════════════════

class CouponV2(Base):
    """
    Discount coupons that can be applied to subscriptions.
    """
    __tablename__ = "billing_coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Discount type
    discount_type = Column(String(20), nullable=False)  # "percent" or "fixed"
    discount_percent = Column(Float, nullable=True)      # e.g., 20.0 for 20%
    discount_amount_cents = Column(Integer, nullable=True)  # Fixed amount in cents

    # Validity
    currency = Column(String(3), nullable=True)
    max_redemptions = Column(Integer, nullable=True)
    current_redemptions = Column(Integer, nullable=False, default=0)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)

    # Stripe reference
    stripe_coupon_id = Column(String(100), nullable=True)

    # Restrictions
    applicable_plan_slugs_json = Column(Text, nullable=True)  # JSON list, NULL = all plans

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow)
