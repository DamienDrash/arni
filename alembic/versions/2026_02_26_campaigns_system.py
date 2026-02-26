"""campaigns_system – Campaign, Template, Segment, FollowUp tables

Revision ID: camp_001
Revises: 202602260001
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "camp_001"
down_revision = "202602260001"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    return table in inspect(conn).get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # Campaign Templates
    if not _table_exists(conn, "campaign_templates"):
        op.create_table(
            "campaign_templates",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("type", sa.String, nullable=False, server_default="email"),
            sa.Column("header_html", sa.Text, nullable=True),
            sa.Column("footer_html", sa.Text, nullable=True),
            sa.Column("body_template", sa.Text, nullable=True),
            sa.Column("variables_json", sa.Text, nullable=True),
            sa.Column("primary_color", sa.String, nullable=True, server_default="#6C5CE7"),
            sa.Column("logo_url", sa.String, nullable=True),
            sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    # Campaigns
    if not _table_exists(conn, "campaigns"):
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("type", sa.String, nullable=False, server_default="broadcast"),
            sa.Column("status", sa.String, nullable=False, server_default="draft"),
            sa.Column("channel", sa.String, nullable=False, server_default="email"),
            sa.Column("target_type", sa.String, nullable=False, server_default="all_members"),
            sa.Column("target_filter_json", sa.Text, nullable=True),
            sa.Column("template_id", sa.Integer, sa.ForeignKey("campaign_templates.id"), nullable=True),
            sa.Column("content_subject", sa.String, nullable=True),
            sa.Column("content_body", sa.Text, nullable=True),
            sa.Column("content_html", sa.Text, nullable=True),
            sa.Column("ai_prompt", sa.Text, nullable=True),
            sa.Column("ai_generated_content", sa.Text, nullable=True),
            sa.Column("preview_token", sa.String, nullable=True, unique=True, index=True),
            sa.Column("preview_expires_at", sa.DateTime, nullable=True),
            sa.Column("scheduled_at", sa.DateTime, nullable=True),
            sa.Column("sent_at", sa.DateTime, nullable=True),
            sa.Column("stats_total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stats_sent", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stats_delivered", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stats_opened", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stats_clicked", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stats_failed", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_ab_test", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("ab_winner_variant", sa.String, nullable=True),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    # Campaign Variants (A/B Testing)
    if not _table_exists(conn, "campaign_variants"):
        op.create_table(
            "campaign_variants",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id"), nullable=False, index=True),
            sa.Column("variant_name", sa.String, nullable=False, server_default="A"),
            sa.Column("content_subject", sa.String, nullable=True),
            sa.Column("content_body", sa.Text, nullable=True),
            sa.Column("content_html", sa.Text, nullable=True),
            sa.Column("percentage", sa.Integer, nullable=False, server_default="50"),
            sa.Column("stats_sent", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stats_opened", sa.Integer, nullable=False, server_default="0"),
            sa.Column("stats_clicked", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )

    # Campaign Recipients
    if not _table_exists(conn, "campaign_recipients"):
        op.create_table(
            "campaign_recipients",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id"), nullable=False, index=True),
            sa.Column("member_id", sa.Integer, sa.ForeignKey("studio_members.id"), nullable=False, index=True),
            sa.Column("variant_name", sa.String, nullable=True),
            sa.Column("status", sa.String, nullable=False, server_default="pending"),
            sa.Column("sent_at", sa.DateTime, nullable=True),
            sa.Column("delivered_at", sa.DateTime, nullable=True),
            sa.Column("opened_at", sa.DateTime, nullable=True),
            sa.Column("clicked_at", sa.DateTime, nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
        )

    # Member Segments
    if not _table_exists(conn, "member_segments"):
        op.create_table(
            "member_segments",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("filter_json", sa.Text, nullable=True),
            sa.Column("is_dynamic", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("member_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    # Scheduled Follow-Ups
    if not _table_exists(conn, "scheduled_follow_ups"):
        op.create_table(
            "scheduled_follow_ups",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("member_id", sa.Integer, sa.ForeignKey("studio_members.id"), nullable=True, index=True),
            sa.Column("conversation_id", sa.String, nullable=True),
            sa.Column("reason", sa.Text, nullable=True),
            sa.Column("ai_context_json", sa.Text, nullable=True),
            sa.Column("follow_up_at", sa.DateTime, nullable=False),
            sa.Column("message_template", sa.Text, nullable=True),
            sa.Column("channel", sa.String, nullable=False, server_default="whatsapp"),
            sa.Column("status", sa.String, nullable=False, server_default="pending"),
            sa.Column("sent_at", sa.DateTime, nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("scheduled_follow_ups")
    op.drop_table("member_segments")
    op.drop_table("campaign_recipients")
    op.drop_table("campaign_variants")
    op.drop_table("campaigns")
    op.drop_table("campaign_templates")
