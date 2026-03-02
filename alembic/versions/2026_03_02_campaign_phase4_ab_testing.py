"""Campaign Phase 4: A/B Testing, AI Optimization & Planning

Revision ID: camp_phase4
Revises: camp_phase3
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "camp_phase4"
down_revision = "camp_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Campaign model extensions ---
    # A/B Testing fields
    op.add_column("campaigns", sa.Column("is_ab_test", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("campaigns", sa.Column("ab_test_percentage", sa.Integer(), nullable=True))
    op.add_column("campaigns", sa.Column("ab_test_duration_hours", sa.Integer(), nullable=True))
    op.add_column("campaigns", sa.Column("ab_test_metric", sa.String(50), nullable=True))
    op.add_column("campaigns", sa.Column("ab_test_auto_send", sa.Boolean(), server_default="true", nullable=True))
    op.add_column("campaigns", sa.Column("ab_test_winner_variant_id", sa.Integer(), nullable=True))
    # Calendar fields
    op.add_column("campaigns", sa.Column("calendar_color", sa.String(20), nullable=True))
    op.add_column("campaigns", sa.Column("calendar_category", sa.String(50), nullable=True))

    # --- CampaignVariant extensions ---
    op.add_column("campaign_variants", sa.Column("is_winner", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("campaign_variants", sa.Column("confidence_level", sa.Float(), nullable=True))
    op.add_column("campaign_variants", sa.Column("test_sent_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("campaign_variants", sa.Column("test_open_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("campaign_variants", sa.Column("test_click_count", sa.Integer(), server_default="0", nullable=False))

    # --- Contact model extensions for AI optimization ---
    op.add_column("contacts", sa.Column("preferred_channel", sa.String(30), nullable=True))
    op.add_column("contacts", sa.Column("best_send_hour", sa.Integer(), nullable=True))
    op.add_column("contacts", sa.Column("best_send_day", sa.Integer(), nullable=True))
    op.add_column("contacts", sa.Column("engagement_score", sa.Float(), nullable=True))
    op.add_column("contacts", sa.Column("channel_affinity_json", JSONB(), nullable=True))
    op.add_column("contacts", sa.Column("last_insight_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Contact extensions
    op.drop_column("contacts", "last_insight_at")
    op.drop_column("contacts", "channel_affinity_json")
    op.drop_column("contacts", "engagement_score")
    op.drop_column("contacts", "best_send_day")
    op.drop_column("contacts", "best_send_hour")
    op.drop_column("contacts", "preferred_channel")

    # CampaignVariant extensions
    op.drop_column("campaign_variants", "test_click_count")
    op.drop_column("campaign_variants", "test_open_count")
    op.drop_column("campaign_variants", "test_sent_count")
    op.drop_column("campaign_variants", "confidence_level")
    op.drop_column("campaign_variants", "is_winner")

    # Campaign extensions
    op.drop_column("campaigns", "calendar_category")
    op.drop_column("campaigns", "calendar_color")
    op.drop_column("campaigns", "ab_test_winner_variant_id")
    op.drop_column("campaigns", "ab_test_auto_send")
    op.drop_column("campaigns", "ab_test_metric")
    op.drop_column("campaigns", "ab_test_duration_hours")
    op.drop_column("campaigns", "ab_test_percentage")
    op.drop_column("campaigns", "is_ab_test")
