"""Pricing overhaul: 4-tier plans, add-on system, connector limits.

Revision ID: pricing_overhaul_001
Revises: plan_feature_flags_001
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa

revision = "pricing_overhaul_001"
down_revision = "plan_feature_flags_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend plans table ───────────────────────────────────────────────────
    # Rename stripe_price_id → stripe_price_id_monthly (if exists)
    try:
        op.alter_column("plans", "stripe_price_id", new_column_name="stripe_price_id_monthly")
    except Exception:
        pass  # Column may not exist or already renamed

    # New columns on plans
    new_plan_cols = [
        ("stripe_price_id_yearly", sa.String(), True, None),
        ("price_yearly_cents", sa.Integer(), True, None),
        ("is_custom_pricing", sa.Boolean(), False, False),
        ("max_users", sa.Integer(), True, None),
        ("max_connectors", sa.Integer(), False, 0),
        ("overage_per_conversation_cents", sa.Integer(), True, None),
        ("overage_per_user_cents", sa.Integer(), True, None),
        ("overage_per_connector_cents", sa.Integer(), True, None),
        ("overage_per_channel_cents", sa.Integer(), True, None),
        ("ai_tier", sa.String(), False, "basic"),
        ("allowed_llm_models", sa.Text(), True, None),
        ("max_monthly_llm_tokens", sa.Integer(), True, None),
        ("custom_llm_keys_enabled", sa.Boolean(), False, False),
        ("connector_manual_enabled", sa.Boolean(), False, True),
        ("connector_api_enabled", sa.Boolean(), False, True),
        ("connector_csv_enabled", sa.Boolean(), False, True),
        ("connector_magicline_enabled", sa.Boolean(), False, False),
        ("connector_shopify_enabled", sa.Boolean(), False, False),
        ("connector_woocommerce_enabled", sa.Boolean(), False, False),
        ("connector_hubspot_enabled", sa.Boolean(), False, False),
        ("churn_prediction_enabled", sa.Boolean(), False, False),
        ("vision_ai_enabled", sa.Boolean(), False, False),
        ("priority_support", sa.Boolean(), False, False),
        ("dedicated_support", sa.Boolean(), False, False),
        ("sla_enabled", sa.Boolean(), False, False),
        ("on_premise_option", sa.Boolean(), False, False),
        ("white_label_enabled", sa.Boolean(), False, False),
        ("sort_order", sa.Integer(), False, 0),
    ]

    for col_name, col_type, nullable, default in new_plan_cols:
        try:
            kw = {"nullable": nullable}
            if default is not None:
                kw["server_default"] = str(default).lower() if isinstance(default, bool) else str(default)
            op.add_column("plans", sa.Column(col_name, col_type, **kw))
        except Exception:
            pass  # Column may already exist

    # ── Create plan_addons table ─────────────────────────────────────────────
    op.create_table(
        "plan_addons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=False, server_default="feature"),
        sa.Column("price_monthly_cents", sa.Integer(), nullable=False),
        sa.Column("stripe_price_id", sa.String(), nullable=True),
        sa.Column("is_per_unit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("unit_label", sa.String(), nullable=True),
        sa.Column("min_plan_slug", sa.String(), nullable=True),
        sa.Column("feature_key", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

     # ── Extend usage_records table ─────────────────────────────────────────
    new_usage_cols = [
        ("conversations_count", sa.Integer(), False, 0),
        ("llm_requests_count", sa.Integer(), False, 0),
        ("active_channels_count", sa.Integer(), False, 0),
        ("active_connectors_count", sa.Integer(), False, 0),
        ("active_users_count", sa.Integer(), False, 0),
        ("overage_conversations", sa.Integer(), False, 0),
        ("overage_tokens", sa.Integer(), False, 0),
        ("overage_billed_cents", sa.Integer(), False, 0),
    ]
    for col_name, col_type, nullable, default in new_usage_cols:
        try:
            kw = {"nullable": nullable}
            if default is not None:
                kw["server_default"] = str(default)
            op.add_column("usage_records", sa.Column(col_name, col_type, **kw))
        except Exception:
            pass

    # ── Create tenant_addons table ───────────────────────────────────────────
    op.create_table(
        "tenant_addons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("addon_id", sa.Integer(), sa.ForeignKey("plan_addons.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stripe_subscription_item_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "addon_id", name="uq_tenant_addon"),
    )


def downgrade() -> None:
    op.drop_table("tenant_addons")
    op.drop_table("plan_addons")

    # Drop usage_records new columns
    usage_drop = [
        "conversations_count", "llm_requests_count", "active_channels_count",
        "active_connectors_count", "active_users_count",
        "overage_conversations", "overage_tokens", "overage_billed_cents",
    ]
    for col in usage_drop:
        try:
            op.drop_column("usage_records", col)
        except Exception:
            pass

    drop_cols = [
        "stripe_price_id_yearly", "price_yearly_cents", "is_custom_pricing",
        "max_users", "max_connectors",
        "overage_per_conversation_cents", "overage_per_user_cents",
        "overage_per_connector_cents", "overage_per_channel_cents",
        "ai_tier", "allowed_llm_models", "max_monthly_llm_tokens",
        "custom_llm_keys_enabled",
        "connector_manual_enabled", "connector_api_enabled", "connector_csv_enabled",
        "connector_magicline_enabled", "connector_shopify_enabled",
        "connector_woocommerce_enabled", "connector_hubspot_enabled",
        "churn_prediction_enabled", "vision_ai_enabled",
        "priority_support", "dedicated_support", "sla_enabled",
        "on_premise_option", "white_label_enabled", "sort_order",
    ]
    for col in drop_cols:
        try:
            op.drop_column("plans", col)
        except Exception:
            pass
