"""Add campaign_offers, agent_teams, offer_slug, orchestrator status/tenant_id.

Revision ID: 2026_03_18_optin_offers
Revises: 2026_03_17_orchestrator_manager
Create Date: 2026-03-18
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "2026_03_18_optin_offers"
down_revision = "2026_03_17_orchestrator_manager"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    cols = [c["name"] for c in inspect(op.get_bind()).get_columns(table)]
    return column in cols


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. campaign_recipients.offer_slug ────────────────────────────────
    if _table_exists("campaign_recipients") and not _column_exists("campaign_recipients", "offer_slug"):
        op.add_column("campaign_recipients", sa.Column("offer_slug", sa.String(64), nullable=True))

    # ── 2. campaign_offers (new table) ───────────────────────────────────
    if not _table_exists("campaign_offers"):
        op.create_table(
            "campaign_offers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("slug", sa.String(64), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("confirmation_message", sa.Text(), nullable=False),
            sa.Column("attachment_url", sa.String(512), nullable=True),
            sa.Column("attachment_filename", sa.String(256), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("tenant_id", "slug", name="uq_campaign_offer_slug"),
        )
        op.create_index("ix_campaign_offers_tenant_id", "campaign_offers", ["tenant_id"])

    # ── 3. agent_teams (new table) ───────────────────────────────────────
    if not _table_exists("agent_teams"):
        op.create_table(
            "agent_teams",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(64), nullable=False, unique=True),
            sa.Column("display_name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("agent_ids", sa.JSON(), nullable=True),
            sa.Column("orchestrator_name", sa.String(64), nullable=True),
            sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
        )
        op.create_index("ix_agent_teams_name", "agent_teams", ["name"])

    # ── 4. orchestrator_definitions: rename state→status, add tenant_id ──
    if _table_exists("orchestrator_definitions"):
        # Rename state → status
        if _column_exists("orchestrator_definitions", "state") and not _column_exists("orchestrator_definitions", "status"):
            op.alter_column("orchestrator_definitions", "state", new_column_name="status")

        # Add tenant_id (from TenantScopedMixin)
        if not _column_exists("orchestrator_definitions", "tenant_id"):
            op.add_column("orchestrator_definitions", sa.Column("tenant_id", sa.Integer(), nullable=True))
            op.create_index("ix_orchestrator_definitions_tenant_id", "orchestrator_definitions", ["tenant_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists("agent_teams"):
        op.drop_table("agent_teams")
    if _table_exists("campaign_offers"):
        op.drop_table("campaign_offers")
    if _table_exists("campaign_recipients") and _column_exists("campaign_recipients", "offer_slug"):
        op.drop_column("campaign_recipients", "offer_slug")
    if _table_exists("orchestrator_definitions"):
        if _column_exists("orchestrator_definitions", "status") and not _column_exists("orchestrator_definitions", "state"):
            op.alter_column("orchestrator_definitions", "status", new_column_name="state")
