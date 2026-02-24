from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Date, Float, UniqueConstraint, ForeignKey
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

    # --- Multi-Source tracking ---
    source = Column(String, nullable=False, default="manual")  # 'manual'|'magicline'|'shopify'|'woocommerce'|'hubspot'|'csv'|'api'
    source_id = Column(String, nullable=True, index=True)      # External ID in source system

    # --- Bulk sync fields (from /v1/customers, zero extra API calls) ---
    gender = Column(String, nullable=True)               # "MALE" / "FEMALE" / "DIVERSE"
    preferred_language = Column(String, nullable=True)   # "de", "en", …
    member_since = Column(DateTime, nullable=True)       # createdDateTime
    is_paused = Column(Boolean, nullable=True, default=False)
    pause_info = Column(Text, nullable=True)             # JSON: {"is_currently_paused": bool, "pause_until": "YYYY-MM-DD"|null, ...}
    contract_info = Column(Text, nullable=True)          # JSON: {"plan_name": "Premium", "status": "ACTIVE", "end_date": ...}
    additional_info = Column(Text, nullable=True)        # JSON: {"Trainingsziel": "Muskelaufbau", …}

    # --- Custom fields & tags (user-defined per tenant) ---
    tags = Column(Text, nullable=True)                   # JSON array: ["vip", "new", ...]
    custom_fields = Column(Text, nullable=True)          # JSON object: {"slug": "value", ...}
    notes = Column(Text, nullable=True)                  # Free-text notes

    # --- Lazy enrichment (per-member API, cached with TTL) ---
    checkin_stats = Column(Text, nullable=True)    # JSON: {total_30d, total_90d, avg_per_week, last_visit, days_since, status}
    recent_bookings = Column(Text, nullable=True)  # JSON: [{type, title, start, status}, …]
    enriched_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ─── Billing Models (S4.1) ───────────────────────────────────────────────────

class Plan(Base):
    """SaaS subscription plan with feature limits and pricing tiers.

    Plans: Starter (79€), Professional (199€), Business (399€), Enterprise (custom).
    """

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)               # "Starter", "Professional", "Business", "Enterprise"
    slug = Column(String, unique=True, nullable=False)  # "starter", "professional", "business", "enterprise"
    stripe_price_id_monthly = Column(String, nullable=True)   # Stripe Price ID for monthly billing
    stripe_price_id_yearly = Column(String, nullable=True)    # Stripe Price ID for yearly billing (20% off)
    price_monthly_cents = Column(Integer, nullable=False, default=0)  # e.g. 7900 = 79€
    price_yearly_cents = Column(Integer, nullable=True)       # e.g. 75840 = 758.40€ (79*12*0.8)
    is_custom_pricing = Column(Boolean, nullable=False, default=False)  # Enterprise: custom pricing

    # ── Limits (NULL = unlimited) ────────────────────────────────────────────
    max_members = Column(Integer, nullable=True)              # Starter: 500, others: NULL
    max_monthly_messages = Column(Integer, nullable=True)     # Starter: 500, Pro: 2000, Biz: 10000
    max_channels = Column(Integer, nullable=False, default=1) # Starter: 1, Pro: 3, Biz: unlimited(99)
    max_users = Column(Integer, nullable=True)                # Starter: 1, Pro: 5, Biz: 15, Ent: NULL
    max_connectors = Column(Integer, nullable=False, default=0)  # Starter: 0, Pro: 1, Biz: unlimited(99)

    # ── Overage pricing (cents per unit above limit) ─────────────────────────
    overage_per_conversation_cents = Column(Integer, nullable=True)  # e.g. 5 = 0.05€
    overage_per_user_cents = Column(Integer, nullable=True)          # e.g. 1500 = 15€
    overage_per_connector_cents = Column(Integer, nullable=True)     # e.g. 4900 = 49€
    overage_per_channel_cents = Column(Integer, nullable=True)       # e.g. 2900 = 29€

    # ── Channel toggles ──────────────────────────────────────────────────────
    whatsapp_enabled = Column(Boolean, nullable=False, default=True)
    telegram_enabled = Column(Boolean, nullable=False, default=False)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    email_channel_enabled = Column(Boolean, nullable=False, default=False)
    voice_enabled = Column(Boolean, nullable=False, default=False)
    instagram_enabled = Column(Boolean, nullable=False, default=False)
    facebook_enabled = Column(Boolean, nullable=False, default=False)
    google_business_enabled = Column(Boolean, nullable=False, default=False)

    # ── Feature toggles ──────────────────────────────────────────────────────
    memory_analyzer_enabled = Column(Boolean, nullable=False, default=False)
    custom_prompts_enabled = Column(Boolean, nullable=False, default=False)
    advanced_analytics_enabled = Column(Boolean, nullable=False, default=False)
    branding_enabled = Column(Boolean, nullable=False, default=False)
    audit_log_enabled = Column(Boolean, nullable=False, default=False)
    automation_enabled = Column(Boolean, nullable=False, default=False)
    api_access_enabled = Column(Boolean, nullable=False, default=False)
    multi_source_members_enabled = Column(Boolean, nullable=False, default=False)

    # ── AI & LLM tier ────────────────────────────────────────────────────────
    ai_tier = Column(String, nullable=False, default="basic")  # "basic", "standard", "premium", "unlimited"
    # LLM model access: JSON list of allowed model identifiers
    # Starter: ["gpt-4.1-nano"], Pro: ["gpt-4.1-nano","gpt-4.1-mini"],
    # Business: ["gpt-4.1-nano","gpt-4.1-mini","gpt-4.1","gemini-2.5-flash"],
    # Enterprise: all + custom keys
    allowed_llm_models = Column(Text, nullable=True)  # JSON array, NULL = all models
    max_monthly_llm_tokens = Column(Integer, nullable=True)  # Starter: 100000, Pro: 500000, Biz: 2000000, Ent: NULL
    custom_llm_keys_enabled = Column(Boolean, nullable=False, default=False)  # Enterprise: bring your own keys

    # ── Connector source toggles (member data sources) ───────────────────────
    connector_manual_enabled = Column(Boolean, nullable=False, default=True)   # Always true
    connector_api_enabled = Column(Boolean, nullable=False, default=True)      # Always true (via api_access)
    connector_csv_enabled = Column(Boolean, nullable=False, default=True)      # Always true
    connector_magicline_enabled = Column(Boolean, nullable=False, default=False)  # Pro+
    connector_shopify_enabled = Column(Boolean, nullable=False, default=False)    # Pro+
    connector_woocommerce_enabled = Column(Boolean, nullable=False, default=False)  # Pro+
    connector_hubspot_enabled = Column(Boolean, nullable=False, default=False)    # Pro+

    # ── Premium features ─────────────────────────────────────────────────────
    churn_prediction_enabled = Column(Boolean, nullable=False, default=False)
    vision_ai_enabled = Column(Boolean, nullable=False, default=False)
    priority_support = Column(Boolean, nullable=False, default=False)
    dedicated_support = Column(Boolean, nullable=False, default=False)
    sla_enabled = Column(Boolean, nullable=False, default=False)
    on_premise_option = Column(Boolean, nullable=False, default=False)
    white_label_enabled = Column(Boolean, nullable=False, default=False)

    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)  # Display order
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PlanAddon(Base):
    """Purchasable add-on modules that extend a plan's capabilities.

    Add-ons: Churn Prediction (+49€), Voice Pipeline (+79€), Vision AI (+39€),
    Extra Channel (+29€), Extra Conversations, Extra Users (+15€),
    White-Label (+149€), API Access (+99€), Extra Connector (+49€).
    """

    __tablename__ = "plan_addons"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False)        # "churn_prediction", "voice_pipeline", etc.
    name = Column(String, nullable=False)                     # "Churn Prediction"
    description = Column(Text, nullable=True)                 # Short description
    category = Column(String, nullable=False, default="feature")  # "feature", "channel", "capacity", "support"
    price_monthly_cents = Column(Integer, nullable=False)     # e.g. 4900 = 49€
    stripe_price_id = Column(String, nullable=True)           # Stripe recurring price
    is_per_unit = Column(Boolean, nullable=False, default=False)  # True for "per channel", "per user" etc.
    unit_label = Column(String, nullable=True)                # "Kanal", "User", "Connector"
    min_plan_slug = Column(String, nullable=True)             # Minimum plan required (NULL = any)
    feature_key = Column(String, nullable=True)               # Feature flag this addon enables
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TenantAddon(Base):
    """Active add-on subscription for a tenant."""

    __tablename__ = "tenant_addons"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    addon_id = Column(Integer, ForeignKey("plan_addons.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)     # For per-unit addons
    stripe_subscription_item_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")  # active | canceled
    activated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    canceled_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "addon_id", name="uq_tenant_addon"),
    )


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

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MemberCustomColumn(Base):
    """Tenant-defined custom columns for member data."""

    __tablename__ = "member_custom_columns"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)                # Display name: "Schuhgröße"
    slug = Column(String, nullable=False)                # Key in custom_fields: "schuhgroesse"
    field_type = Column(String, nullable=False, default="text")  # 'text'|'number'|'date'|'select'|'boolean'
    options = Column(Text, nullable=True)                # JSON for select type: ["S","M","L","XL"]
    position = Column(Integer, nullable=False, default=0)
    is_visible = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_custom_column_tenant_slug"),
    )


class MemberImportLog(Base):
    """Tracks member import operations from any source."""

    __tablename__ = "member_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    source = Column(String, nullable=False)              # 'csv'|'shopify'|'woocommerce'|'hubspot'|'api'
    status = Column(String, nullable=False, default="running")  # 'running'|'completed'|'failed'
    total_rows = Column(Integer, nullable=False, default=0)
    imported = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    error_log = Column(Text, nullable=True)              # JSON array with error details
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class UsageRecord(Base):
    """Monthly usage counters per tenant for plan enforcement and billing."""

    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)  # 1–12

    messages_inbound = Column(Integer, nullable=False, default=0)
    messages_outbound = Column(Integer, nullable=False, default=0)
    conversations_count = Column(Integer, nullable=False, default=0)  # Unique conversations this month
    active_members = Column(Integer, nullable=False, default=0)
    llm_tokens_used = Column(Integer, nullable=False, default=0)
    llm_requests_count = Column(Integer, nullable=False, default=0)  # Number of LLM API calls
    active_channels_count = Column(Integer, nullable=False, default=0)  # Channels used this month
    active_connectors_count = Column(Integer, nullable=False, default=0)  # Connectors used this month
    active_users_count = Column(Integer, nullable=False, default=0)  # Users who logged in this month

    # Overage tracking (billed via Stripe metered billing)
    overage_conversations = Column(Integer, nullable=False, default=0)
    overage_tokens = Column(Integer, nullable=False, default=0)
    overage_billed_cents = Column(Integer, nullable=False, default=0)  # Total overage billed

    __table_args__ = (
        UniqueConstraint("tenant_id", "period_year", "period_month", name="uq_usage_tenant_period"),
    )
