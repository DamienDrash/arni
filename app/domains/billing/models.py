from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.db import Base, TenantScopedMixin


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    stripe_product_id = Column(String, nullable=True)
    stripe_price_id = Column(String, nullable=True)
    stripe_price_yearly_id = Column(String, nullable=True)
    price_monthly_cents = Column(Integer, nullable=False, default=0)
    price_yearly_cents = Column(Integer, nullable=True)
    trial_days = Column(Integer, nullable=False, default=0)
    display_order = Column(Integer, nullable=False, default=0)
    is_highlighted = Column(Boolean, nullable=False, default=False)
    features_json = Column(Text, nullable=True)
    max_members = Column(Integer, nullable=True)
    max_monthly_messages = Column(Integer, nullable=True)
    max_channels = Column(Integer, nullable=False, default=1)
    max_connectors = Column(Integer, nullable=False, default=0)
    ai_tier = Column(String, nullable=False, default="basic")
    monthly_tokens = Column(Integer, nullable=False, default=100000)
    whatsapp_enabled = Column(Boolean, nullable=False, default=True)
    telegram_enabled = Column(Boolean, nullable=False, default=False)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    email_channel_enabled = Column(Boolean, nullable=False, default=False)
    voice_enabled = Column(Boolean, nullable=False, default=False)
    instagram_enabled = Column(Boolean, nullable=False, default=False)
    facebook_enabled = Column(Boolean, nullable=False, default=False)
    google_business_enabled = Column(Boolean, nullable=False, default=False)
    memory_analyzer_enabled = Column(Boolean, nullable=False, default=False)
    custom_prompts_enabled = Column(Boolean, nullable=False, default=False)
    advanced_analytics_enabled = Column(Boolean, nullable=False, default=False)
    branding_enabled = Column(Boolean, nullable=False, default=False)
    audit_log_enabled = Column(Boolean, nullable=False, default=False)
    automation_enabled = Column(Boolean, nullable=False, default=False)
    api_access_enabled = Column(Boolean, nullable=False, default=False)
    multi_source_members_enabled = Column(Boolean, nullable=False, default=False)
    churn_prediction_enabled = Column(Boolean, nullable=False, default=False)
    vision_ai_enabled = Column(Boolean, nullable=False, default=False)
    white_label_enabled = Column(Boolean, nullable=False, default=False)
    sla_guarantee_enabled = Column(Boolean, nullable=False, default=False)
    on_premise_enabled = Column(Boolean, nullable=False, default=False)
    agent_teams_enabled = Column(Boolean, nullable=False, default=False)
    overage_conversation_cents = Column(Integer, default=5)
    overage_user_cents = Column(Integer, default=1500)
    overage_connector_cents = Column(Integer, default=4900)
    overage_channel_cents = Column(Integer, default=2900)
    allowed_llm_providers_json = Column(Text, nullable=True)
    allowed_llm_models_json = Column(Text, nullable=True)
    token_price_per_1k_cents = Column(Integer, nullable=True, default=10)
    ai_image_generations_per_month = Column(Integer, nullable=True)
    monthly_image_credits = Column(Integer, nullable=True, default=0)
    media_storage_mb = Column(Integer, nullable=True)
    ai_image_previews_per_month = Column(Integer, nullable=True)
    brand_style_enabled = Column(Boolean, nullable=False, default=False)
    text_overlay_images_enabled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AddonDefinition(Base):
    __tablename__ = "addon_definitions"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    icon = Column(String, nullable=True)
    price_monthly_cents = Column(Integer, nullable=False, default=0)
    stripe_product_id = Column(String, nullable=True)
    stripe_price_id = Column(String, nullable=True)
    features_json = Column(Text, nullable=True)
    image_quota_grant = Column(Integer, nullable=True, default=0)
    image_preview_quota_grant = Column(Integer, nullable=True, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TenantAddon(Base, TenantScopedMixin):
    __tablename__ = "tenant_addons"

    id = Column(Integer, primary_key=True, index=True)
    addon_slug = Column(String, nullable=False)
    stripe_subscription_item_id = Column(String, nullable=True)
    quantity = Column(Integer, default=1)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(String, nullable=False, default="active")
    stripe_subscription_id = Column(String, nullable=True, unique=True)
    stripe_customer_id = Column(String, nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    pending_plan_id = Column(Integer, nullable=True)
    billing_interval = Column(String, default="month", nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UsageRecord(Base, TenantScopedMixin):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)
    messages_inbound = Column(Integer, nullable=False, default=0)
    messages_outbound = Column(Integer, nullable=False, default=0)
    active_members = Column(Integer, nullable=False, default=0)
    llm_tokens_used = Column(Integer, nullable=False, default=0)
    llm_tokens_purchased = Column(Integer, nullable=False, default=0)
    ai_image_generations_used = Column(Integer, nullable=False, default=0)
    media_storage_bytes_used = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "period_year", "period_month", name="uq_usage_tenant_period"),
    )


class TokenPurchase(Base, TenantScopedMixin):
    __tablename__ = "token_purchases"

    id = Column(Integer, primary_key=True, index=True)
    tokens_amount = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    stripe_payment_intent_id = Column(String, nullable=True)
    stripe_checkout_session_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ImageCreditPack(Base):
    __tablename__ = "image_credit_packs"

    id = Column(Integer, primary_key=True)
    slug = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    credits = Column(Integer, nullable=False)
    price_once_cents = Column(Integer, nullable=True)
    price_monthly_cents = Column(Integer, nullable=True)
    price_yearly_cents = Column(Integer, nullable=True)
    stripe_product_id = Column(String(100), nullable=True)
    stripe_price_once_id = Column(String(100), nullable=True)
    stripe_price_monthly_id = Column(String(100), nullable=True)
    stripe_price_yearly_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ImageCreditBalance(Base, TenantScopedMixin):
    __tablename__ = "image_credit_balances"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False)
    balance = Column(Integer, default=0, nullable=False)
    last_grant_year = Column(Integer, nullable=True)
    last_grant_month = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ImageCreditTransaction(Base, TenantScopedMixin):
    __tablename__ = "image_credit_transactions"

    id = Column(Integer, primary_key=True)
    delta = Column(Integer, nullable=False)
    reason = Column(String(50), nullable=False)
    reference_id = Column(String(200), nullable=True)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class ImageCreditPurchase(Base, TenantScopedMixin):
    __tablename__ = "image_credit_purchases"

    id = Column(Integer, primary_key=True)
    pack_slug = Column(String(50), nullable=False)
    billing_interval = Column(String(20), nullable=False)
    credits_granted = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    stripe_session_id = Column(String(200), nullable=True)
    stripe_subscription_id = Column(String(200), nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LLMModelCost(Base):
    __tablename__ = "llm_model_costs"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String, nullable=False, index=True)
    model_id = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=True)
    input_cost_per_million = Column(Integer, nullable=False, default=0)
    output_cost_per_million = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LLMUsageLog(Base, TenantScopedMixin):
    __tablename__ = "llm_usage_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=True)
    agent_name = Column(String, nullable=True)
    provider_id = Column(String, nullable=False)
    model_id = Column(String, nullable=False, index=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    input_cost_cents = Column(Float, nullable=False, default=0.0)
    output_cost_cents = Column(Float, nullable=False, default=0.0)
    total_cost_cents = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


__all__ = [
    "AddonDefinition",
    "ImageCreditBalance",
    "ImageCreditPack",
    "ImageCreditPurchase",
    "ImageCreditTransaction",
    "LLMModelCost",
    "LLMUsageLog",
    "Plan",
    "Subscription",
    "TenantAddon",
    "TokenPurchase",
    "UsageRecord",
]
