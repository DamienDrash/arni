from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Date, UniqueConstraint, ForeignKey, Float
from app.core.db import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    platform = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_message_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    # Enhanced User Identification (Sprint 13)
    user_name = Column(String, nullable=True)  # "Damien" or "Damien (@username)"
    phone_number = Column(String, nullable=True)  # For verification
    email = Column(String, nullable=True)  # For verification
    member_id = Column(String, nullable=True)  # Link to external Member DB (Sprint 13)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)  # Linking to user_id for simplicity across platforms
    tenant_id = Column(Integer, index=True, nullable=False)
    role = Column(String)  # "user" or "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_json = Column(Text, nullable=True)  # JSON string for extra data


class Setting(Base):
    __tablename__ = "settings"

    tenant_id = Column(Integer, primary_key=True, index=True, nullable=False)
    key = Column(String, primary_key=True, index=True)
    value = Column(String)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TenantConfig(Base):
    __tablename__ = "tenant_configs"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    key = Column(String, index=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

class MemberFeedback(Base):
    """Stores user satisfaction feedback after a chat session."""
    __tablename__ = "member_feedback"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    session_id = Column(String, index=True, nullable=False)
    rating = Column(Integer, nullable=False)  # e.g. 1-5 or 1-10
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserAccount(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="tenant_user", nullable=False)  # system_admin|tenant_admin|tenant_user
    password_hash = Column(String, nullable=False)
    language = Column(String, default="en", nullable=False)  # de|en|bg
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, index=True, nullable=True)
    actor_email = Column(String, nullable=True)
    tenant_id = Column(Integer, index=True, nullable=True)
    action = Column(String, index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    target_type = Column(String, nullable=True)
    target_id = Column(String, nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class StudioMember(Base):
    __tablename__ = "studio_members"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    customer_id = Column(Integer, index=True, nullable=False)
    member_number = Column(String, index=True, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    phone_number = Column(String, nullable=True)
    email = Column(String, nullable=True)

    # --- Bulk sync fields (from /v1/customers, zero extra API calls) ---
    gender = Column(String, nullable=True)               # "MALE" / "FEMALE" / "DIVERSE"
    preferred_language = Column(String, nullable=True)   # "de", "en", …
    member_since = Column(DateTime, nullable=True)       # createdDateTime
    is_paused = Column(Boolean, nullable=True, default=False)
    pause_info = Column(Text, nullable=True)             # JSON: {"is_currently_paused": bool, "pause_until": "YYYY-MM-DD"|null, ...}
    contract_info = Column(Text, nullable=True)          # JSON: {"plan_name": "Premium", "status": "ACTIVE", "end_date": ...}
    additional_info = Column(Text, nullable=True)        # JSON: {"Trainingsziel": "Muskelaufbau", …}

    # --- Lazy enrichment (per-member API, cached with TTL) ---
    checkin_stats = Column(Text, nullable=True)    # JSON: {total_30d, total_90d, avg_per_week, last_visit, days_since, status}
    recent_bookings = Column(Text, nullable=True)  # JSON: [{type, title, start, status}, …]
    enriched_at = Column(DateTime, nullable=True)

    # --- Multi-Source Extensions (PR 2) ---
    source = Column(String, default="manual", nullable=False)  # manual, magicline, shopify, etc.
    source_id = Column(String, nullable=True)                  # External ID in source system
    tags = Column(Text, nullable=True)                         # JSON list: ["vip", "new"]
    custom_fields = Column(Text, nullable=True)                # JSON dict: {"Schuhgröße": "42"}
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MemberCustomColumn(Base):
    """Dynamic custom columns for member table (PR 2)."""
    __tablename__ = "member_custom_columns"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)        # Display name "Schuhgröße"
    slug = Column(String, nullable=False)        # "schuhgroesse"
    field_type = Column(String, nullable=False)  # text, number, date, boolean
    options = Column(Text, nullable=True)        # JSON array for dropdowns
    position = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_member_column_slug"),
    )


class MemberImportLog(Base):
    """Log of bulk import/sync operations (PR 2)."""
    __tablename__ = "member_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    source = Column(String, nullable=False)      # csv, shopify, magicline
    status = Column(String, nullable=False)      # running, completed, failed
    total_rows = Column(Integer, default=0)
    imported = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)      # JSON details
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Billing Models (S4.1) ───────────────────────────────────────────────────

class Plan(Base):
    """SaaS subscription plan with feature limits."""

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)               # "Starter", "Pro", "Enterprise"
    slug = Column(String, unique=True, nullable=False)  # "starter", "pro", "enterprise"
    description = Column(Text, nullable=True)            # Short description for UI/Landing Page
    stripe_product_id = Column(String, nullable=True)    # Stripe Product ID
    stripe_price_id = Column(String, nullable=True)      # Stripe Price ID (NULL for free plans)
    stripe_price_yearly_id = Column(String, nullable=True)  # Stripe Price ID for yearly billing
    price_monthly_cents = Column(Integer, nullable=False, default=0)  # 0 = free
    price_yearly_cents = Column(Integer, nullable=True)  # Yearly price (NULL = no yearly option)
    trial_days = Column(Integer, nullable=False, default=0)  # Free trial period
    display_order = Column(Integer, nullable=False, default=0)  # Sort order on pricing page
    is_highlighted = Column(Boolean, nullable=False, default=False)  # "Most Popular" badge
    features_json = Column(Text, nullable=True)          # JSON list of feature strings for UI display

    # Feature limits (NULL = unlimited)
    max_members = Column(Integer, nullable=True)
    max_monthly_messages = Column(Integer, nullable=True)
    max_channels = Column(Integer, nullable=False, default=1)
    max_connectors = Column(Integer, nullable=False, default=0)
    ai_tier = Column(String, nullable=False, default="basic")  # basic, standard, premium, unlimited
    monthly_tokens = Column(Integer, nullable=False, default=100000)

    # Channel toggles
    whatsapp_enabled = Column(Boolean, nullable=False, default=True)
    telegram_enabled = Column(Boolean, nullable=False, default=False)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    email_channel_enabled = Column(Boolean, nullable=False, default=False)
    voice_enabled = Column(Boolean, nullable=False, default=False)
    instagram_enabled = Column(Boolean, nullable=False, default=False)
    facebook_enabled = Column(Boolean, nullable=False, default=False)
    google_business_enabled = Column(Boolean, nullable=False, default=False)

    # Feature toggles
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

    # Overage Pricing (in cents)
    overage_conversation_cents = Column(Integer, default=5)
    overage_user_cents = Column(Integer, default=1500)
    overage_connector_cents = Column(Integer, default=4900)
    overage_channel_cents = Column(Integer, default=2900)

    # LLM Provider/Model restrictions per plan
    allowed_llm_providers_json = Column(Text, nullable=True)  # JSON list of provider IDs
    allowed_llm_models_json = Column(Text, nullable=True)     # JSON list of model IDs (optional fine-grained)
    token_price_per_1k_cents = Column(Integer, nullable=True, default=10)  # Price for 1K extra tokens

    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=True)  # Show on public pricing page
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AddonDefinition(Base):
    """Global add-on catalog (system-level). Defines available add-ons with pricing."""
    __tablename__ = "addon_definitions"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False)   # "voice_pipeline", "churn_prediction"
    name = Column(String, nullable=False)                 # "Voice Pipeline"
    description = Column(Text, nullable=True)             # For UI display
    category = Column(String, nullable=True)              # "ai", "channel", "analytics"
    icon = Column(String, nullable=True)                  # Lucide icon name
    price_monthly_cents = Column(Integer, nullable=False, default=0)
    stripe_product_id = Column(String, nullable=True)
    stripe_price_id = Column(String, nullable=True)
    features_json = Column(Text, nullable=True)           # JSON list of feature keys this addon unlocks
    is_active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TenantAddon(Base):
    """Active add-ons for a tenant (e.g., extra channel, white-label)."""
    __tablename__ = "tenant_addons"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    addon_slug = Column(String, nullable=False)  # "voice_pipeline", "churn_prediction"
    stripe_subscription_item_id = Column(String, nullable=True)
    quantity = Column(Integer, default=1)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Subscription(Base):
    """Active subscription linking a tenant to a plan."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)

    # Status: active | trialing | past_due | canceled | unpaid
    status = Column(String, nullable=False, default="active")

    stripe_subscription_id = Column(String, nullable=True, unique=True)
    stripe_customer_id = Column(String, nullable=True)

    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    pending_plan_id = Column(Integer, nullable=True)
    billing_interval = Column(String, default="month", nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UsageRecord(Base):
    """Monthly usage counters per tenant for plan enforcement and billing."""

    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)  # 1–12

    messages_inbound = Column(Integer, nullable=False, default=0)
    messages_outbound = Column(Integer, nullable=False, default=0)
    active_members = Column(Integer, nullable=False, default=0)
    llm_tokens_used = Column(Integer, nullable=False, default=0)

    llm_tokens_purchased = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "period_year", "period_month", name="uq_usage_tenant_period"),
    )


class TenantLLMConfig(Base):
    """Per-tenant LLM provider/model selection."""
    __tablename__ = "tenant_llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    provider_id = Column(String, nullable=False)     # e.g. "openai", "anthropic"
    provider_name = Column(String, nullable=False)    # e.g. "OpenAI"
    model_id = Column(String, nullable=False)         # e.g. "gpt-4o"
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TokenPurchase(Base):
    """Token top-up purchases by tenants."""
    __tablename__ = "token_purchases"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    tokens_amount = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    stripe_payment_intent_id = Column(String, nullable=True)
    stripe_checkout_session_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending | completed | failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))




class LLMModelCost(Base):
    """Cost configuration per LLM model – used for real-time cost calculation."""
    __tablename__ = "llm_model_costs"
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String, nullable=False, index=True)       # e.g. "openai", "gemini"
    model_id = Column(String, nullable=False, unique=True, index=True)  # e.g. "gpt-4.1-mini"
    display_name = Column(String, nullable=True)                    # Human-readable name
    input_cost_per_million = Column(Integer, nullable=False, default=0)   # Cost in USD-cents per 1M input tokens
    output_cost_per_million = Column(Integer, nullable=False, default=0)  # Cost in USD-cents per 1M output tokens
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class LLMUsageLog(Base):
    """Per-request LLM usage log with cost attribution per tenant."""
    __tablename__ = "llm_usage_log"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=True)                         # WhatsApp/Telegram user or admin email
    agent_name = Column(String, nullable=True)                      # e.g. "persona", "sales", "medic"
    provider_id = Column(String, nullable=False)
    model_id = Column(String, nullable=False, index=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    input_cost_cents = Column(Float, nullable=False, default=0.0)   # Actual cost in USD-cents
    output_cost_cents = Column(Float, nullable=False, default=0.0)
    total_cost_cents = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class Campaign(Base):
    """Marketing campaign / broadcast / scheduled message."""
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Type: broadcast | scheduled | follow_up | drip
    type = Column(String, nullable=False, default="broadcast")
    # Status: draft | ai_generating | pending_review | approved | scheduled | sending | sent | failed | cancelled
    status = Column(String, nullable=False, default="draft")
    # Channel: email | whatsapp | telegram | sms | multi
    channel = Column(String, nullable=False, default="email")

    # Targeting
    target_type = Column(String, nullable=False, default="all_members")  # all_members | segment | selected | tags
    target_filter_json = Column(Text, nullable=True)  # JSON: member_ids, tags, segment criteria

    # Template
    template_id = Column(Integer, ForeignKey("campaign_templates.id"), nullable=True)

    # Content
    content_subject = Column(String, nullable=True)
    content_body = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)

    # AI Generation
    ai_prompt = Column(Text, nullable=True)
    ai_generated_content = Column(Text, nullable=True)

    # Preview / Approval
    preview_token = Column(String, nullable=True, unique=True, index=True)
    preview_expires_at = Column(DateTime, nullable=True)

    # Scheduling
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    # Stats
    stats_total = Column(Integer, nullable=False, default=0)
    stats_sent = Column(Integer, nullable=False, default=0)
    stats_delivered = Column(Integer, nullable=False, default=0)
    stats_opened = Column(Integer, nullable=False, default=0)
    stats_clicked = Column(Integer, nullable=False, default=0)
    stats_failed = Column(Integer, nullable=False, default=0)

    # A/B Testing
    is_ab_test = Column(Boolean, nullable=False, default=False)
    ab_winner_variant = Column(String, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CampaignTemplate(Base):
    """Reusable message/email templates for campaigns."""
    __tablename__ = "campaign_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Type: email | whatsapp | sms | telegram
    type = Column(String, nullable=False, default="email")

    # Email template parts
    header_html = Column(Text, nullable=True)
    footer_html = Column(Text, nullable=True)
    body_template = Column(Text, nullable=True)

    # Variables available in template
    variables_json = Column(Text, nullable=True)  # JSON: ["first_name", "studio_name", ...]

    # Styling
    primary_color = Column(String, nullable=True, default="#6C5CE7")
    logo_url = Column(String, nullable=True)

    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CampaignVariant(Base):
    """A/B test variants for campaigns."""
    __tablename__ = "campaign_variants"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    variant_name = Column(String, nullable=False, default="A")  # "A", "B"
    content_subject = Column(String, nullable=True)
    content_body = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    percentage = Column(Integer, nullable=False, default=50)  # % of recipients
    stats_sent = Column(Integer, nullable=False, default=0)
    stats_opened = Column(Integer, nullable=False, default=0)
    stats_clicked = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CampaignRecipient(Base):
    """Individual recipient tracking for campaigns."""
    __tablename__ = "campaign_recipients"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("studio_members.id"), nullable=False, index=True)
    variant_name = Column(String, nullable=True)  # For A/B tests

    # Status: pending | sent | delivered | opened | clicked | failed | bounced | unsubscribed
    status = Column(String, nullable=False, default="pending")
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class MemberSegment(Base):
    """Reusable member segments for targeting."""
    __tablename__ = "member_segments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Filter criteria as JSON
    filter_json = Column(Text, nullable=True)  # {"status": "active", "tags": ["vip"], ...}
    is_dynamic = Column(Boolean, nullable=False, default=True)  # Re-evaluate on use

    member_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ScheduledFollowUp(Base):
    """Chat-based scheduled follow-ups for individual members."""
    __tablename__ = "scheduled_follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("studio_members.id"), nullable=True, index=True)

    # Context
    conversation_id = Column(String, nullable=True)  # Reference to chat session
    reason = Column(Text, nullable=True)  # "Pause - Rückkehr nach 2 Wochen"
    ai_context_json = Column(Text, nullable=True)  # Relevant chat context for the follow-up

    # Scheduling
    follow_up_at = Column(DateTime, nullable=False)
    message_template = Column(Text, nullable=True)
    channel = Column(String, nullable=False, default="whatsapp")

    # Status: pending | sent | cancelled | failed
    status = Column(String, nullable=False, default="pending")
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
