"""Campaign Phase 3: Analytics, Tracking & Orchestration

Revision ID: camp_phase3
Revises: camp_phase2
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "camp_phase3"
down_revision = "camp_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── campaign_events ──────────────────────────────────────────────
    op.create_table(
        "campaign_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.Integer, sa.ForeignKey("campaign_recipients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_id", sa.Integer, sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),  # sent, delivered, opened, clicked, bounced, unsubscribed, converted, failed
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("link_url", sa.Text, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_campaign_events_tenant_campaign", "campaign_events", ["tenant_id", "campaign_id"])
    op.create_index("ix_campaign_events_type", "campaign_events", ["event_type"])
    op.create_index("ix_campaign_events_created", "campaign_events", ["created_at"])
    op.create_index("ix_campaign_events_recipient", "campaign_events", ["recipient_id"])

    # ── campaign_orchestration_steps ─────────────────────────────────
    op.create_table(
        "campaign_orchestration_steps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer, nullable=False, server_default="1"),
        sa.Column("channel", sa.String(30), nullable=False, server_default="email"),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("campaign_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content_override_json", JSONB, nullable=True),
        sa.Column("wait_hours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("condition_type", sa.String(50), nullable=False, server_default="always"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_orch_steps_campaign", "campaign_orchestration_steps", ["campaign_id", "step_order"])

    # ── Extend campaign_recipients with orchestration fields ─────────
    # current_step
    op.add_column("campaign_recipients", sa.Column("current_step", sa.Integer, server_default="1"))
    # converted_at
    op.add_column("campaign_recipients", sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True))
    # conversion_value
    op.add_column("campaign_recipients", sa.Column("conversion_value", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("campaign_recipients", "conversion_value")
    op.drop_column("campaign_recipients", "converted_at")
    op.drop_column("campaign_recipients", "current_step")
    op.drop_index("ix_orch_steps_campaign", table_name="campaign_orchestration_steps")
    op.drop_table("campaign_orchestration_steps")
    op.drop_index("ix_campaign_events_recipient", table_name="campaign_events")
    op.drop_index("ix_campaign_events_created", table_name="campaign_events")
    op.drop_index("ix_campaign_events_type", table_name="campaign_events")
    op.drop_index("ix_campaign_events_tenant_campaign", table_name="campaign_events")
    op.drop_table("campaign_events")
