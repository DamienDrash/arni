"""
Billing V2 Refactoring — Create all V2 billing tables.

New tables:
- billing_features: Atomic feature definitions
- billing_feature_sets: Named collections of feature entitlements
- billing_feature_entitlements: Feature-to-FeatureSet join with config
- billing_plans: Versioned plans referencing feature sets
- billing_addon_definitions: Addon catalog with feature set linking
- billing_subscriptions: Tenant subscriptions with full lifecycle
- billing_tenant_addons: Active addon instances
- billing_usage_records: Granular per-feature usage metering
- billing_events: Event-sourced audit trail
- billing_webhook_events: Webhook idempotency tracking
- billing_invoices: Local invoice cache
- billing_coupons: Discount coupon definitions

All V2 tables use the 'billing_' prefix to coexist with V1 during migration.
"""

from alembic import op
import sqlalchemy as sa

revision = "billing_v2_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── billing_features ────────────────────────────────────────────────
    op.create_table(
        "billing_features",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("feature_type", sa.String(20), nullable=False, server_default="boolean"),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── billing_feature_sets ────────────────────────────────────────────
    op.create_table(
        "billing_feature_sets",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── billing_feature_entitlements ────────────────────────────────────
    op.create_table(
        "billing_feature_entitlements",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("feature_set_id", sa.Integer, sa.ForeignKey("billing_feature_sets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("feature_id", sa.Integer, sa.ForeignKey("billing_features.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("value_bool", sa.Boolean, nullable=True),
        sa.Column("value_limit", sa.Integer, nullable=True),
        sa.Column("value_tier", sa.String(50), nullable=True),
        sa.Column("hard_limit", sa.Integer, nullable=True),
        sa.Column("overage_price_cents", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("feature_set_id", "feature_id", name="uq_entitlement_set_feature"),
    )

    # ── billing_plans ───────────────────────────────────────────────────
    op.create_table(
        "billing_plans",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tagline", sa.String(300), nullable=True),
        sa.Column("price_monthly_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("price_yearly_cents", sa.Integer, nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="eur"),
        sa.Column("stripe_product_id", sa.String(100), nullable=True, index=True),
        sa.Column("stripe_price_monthly_id", sa.String(100), nullable=True),
        sa.Column("stripe_price_yearly_id", sa.String(100), nullable=True),
        sa.Column("feature_set_id", sa.Integer, sa.ForeignKey("billing_feature_sets.id"), nullable=True),
        sa.Column("trial_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("trial_feature_set_id", sa.Integer, sa.ForeignKey("billing_feature_sets.id"), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_highlighted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("highlight_label", sa.String(50), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("features_json", sa.Text, nullable=True),
        sa.Column("cta_text", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── billing_addon_definitions ───────────────────────────────────────
    op.create_table(
        "billing_addon_definitions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("slug", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("price_monthly_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("price_yearly_cents", sa.Integer, nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="eur"),
        sa.Column("stripe_product_id", sa.String(100), nullable=True, index=True),
        sa.Column("stripe_price_id", sa.String(100), nullable=True),
        sa.Column("feature_set_id", sa.Integer, sa.ForeignKey("billing_feature_sets.id"), nullable=True),
        sa.Column("features_json", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_stackable", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("max_quantity", sa.Integer, nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── billing_subscriptions ───────────────────────────────────────────
    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, unique=True, index=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("billing_plans.id"), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("billing_interval", sa.String(10), nullable=False, server_default="month"),
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True, unique=True, index=True),
        sa.Column("stripe_customer_id", sa.String(100), nullable=True, index=True),
        sa.Column("stripe_latest_invoice_id", sa.String(100), nullable=True),
        sa.Column("current_period_start", sa.DateTime, nullable=True),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("trial_start", sa.DateTime, nullable=True),
        sa.Column("trial_end", sa.DateTime, nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("canceled_at", sa.DateTime, nullable=True),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
        sa.Column("pending_plan_id", sa.Integer, sa.ForeignKey("billing_plans.id"), nullable=True),
        sa.Column("scheduled_change_at", sa.DateTime, nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── billing_tenant_addons ───────────────────────────────────────────
    op.create_table(
        "billing_tenant_addons",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("subscription_id", sa.Integer, sa.ForeignKey("billing_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("addon_slug", sa.String(100), nullable=False, index=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("stripe_subscription_item_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_addon_sub_slug", "billing_tenant_addons", ["subscription_id", "addon_slug"])

    # ── billing_usage_records ───────────────────────────────────────────
    op.create_table(
        "billing_usage_records",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("feature_key", sa.String(100), nullable=False, index=True),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("soft_limit_snapshot", sa.Integer, nullable=True),
        sa.Column("hard_limit_snapshot", sa.Integer, nullable=True),
        sa.Column("first_recorded_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_recorded_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "feature_key", "period_year", "period_month", name="uq_usage_tenant_feature_period"),
    )
    op.create_index("ix_usage_tenant_period", "billing_usage_records", ["tenant_id", "period_year", "period_month"])

    # ── billing_events ──────────────────────────────────────────────────
    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=True),
        sa.Column("actor_id", sa.String(100), nullable=True),
        sa.Column("stripe_event_id", sa.String(100), nullable=True, index=True),
        sa.Column("idempotency_key", sa.String(200), nullable=True, unique=True, index=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_billing_event_tenant_type", "billing_events", ["tenant_id", "event_type"])

    # ── billing_webhook_events ──────────────────────────────────────────
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("stripe_event_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("received_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_webhook_status", "billing_webhook_events", ["processing_status"])

    # ── billing_invoices ────────────────────────────────────────────────
    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("stripe_invoice_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True),
        sa.Column("number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="eur"),
        sa.Column("amount_due_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount_paid_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount_remaining_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("hosted_invoice_url", sa.Text, nullable=True),
        sa.Column("invoice_pdf_url", sa.Text, nullable=True),
        sa.Column("period_start", sa.DateTime, nullable=True),
        sa.Column("period_end", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime, nullable=True),
        sa.Column("due_date", sa.DateTime, nullable=True),
    )

    # ── billing_coupons ─────────────────────────────────────────────────
    op.create_table(
        "billing_coupons",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("discount_type", sa.String(20), nullable=False),
        sa.Column("discount_percent", sa.Float, nullable=True),
        sa.Column("discount_amount_cents", sa.Integer, nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("max_redemptions", sa.Integer, nullable=True),
        sa.Column("current_redemptions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("valid_from", sa.DateTime, nullable=True),
        sa.Column("valid_until", sa.DateTime, nullable=True),
        sa.Column("stripe_coupon_id", sa.String(100), nullable=True),
        sa.Column("applicable_plan_slugs_json", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("billing_coupons")
    op.drop_table("billing_invoices")
    op.drop_index("ix_webhook_status", table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")
    op.drop_index("ix_billing_event_tenant_type", table_name="billing_events")
    op.drop_table("billing_events")
    op.drop_index("ix_usage_tenant_period", table_name="billing_usage_records")
    op.drop_table("billing_usage_records")
    op.drop_index("ix_tenant_addon_sub_slug", table_name="billing_tenant_addons")
    op.drop_table("billing_tenant_addons")
    op.drop_table("billing_subscriptions")
    op.drop_table("billing_addon_definitions")
    op.drop_table("billing_plans")
    op.drop_table("billing_feature_entitlements")
    op.drop_table("billing_feature_sets")
    op.drop_table("billing_features")
