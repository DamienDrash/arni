"""feat(swarm-v3): create agent/tool definition and tenant config tables.

Revision ID: 2026_03_16_swarm_v3
Revises: 2026_03_16_ingestion_jobs
Create Date: 2026-03-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "2026_03_16_swarm_v3"
down_revision = "2026_03_16_ingestion_jobs"
branch_labels = None
depends_on = None


def _table_exists(conn, table: str) -> bool:
    try:
        return table in inspect(conn).get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()

    # ── tool_definitions ──────────────────────────────────────────────────
    if not _table_exists(conn, "tool_definitions"):
        op.create_table(
            "tool_definitions",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("display_name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("required_integration", sa.String(), nullable=True),
            sa.Column("min_plan_tier", sa.String(), nullable=False, server_default="starter"),
            sa.Column("config_schema", sa.Text(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── agent_definitions ─────────────────────────────────────────────────
    if not _table_exists(conn, "agent_definitions"):
        op.create_table(
            "agent_definitions",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("display_name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("system_prompt", sa.Text(), nullable=True),
            sa.Column("default_tools", sa.Text(), nullable=True),
            sa.Column("max_turns", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("qa_profile", sa.String(), nullable=True),
            sa.Column("min_plan_tier", sa.String(), nullable=False, server_default="starter"),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── tenant_agent_configs ──────────────────────────────────────────────
    if not _table_exists(conn, "tenant_agent_configs"):
        op.create_table(
            "tenant_agent_configs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("agent_id", sa.String(), sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("system_prompt_override", sa.Text(), nullable=True),
            sa.Column("tool_overrides", sa.Text(), nullable=True),
            sa.Column("extra_config", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("tenant_id", "agent_id", name="uq_tenant_agent_config"),
        )
        op.create_index("ix_tenant_agent_configs_tenant_id", "tenant_agent_configs", ["tenant_id"])
        op.create_index("ix_tenant_agent_configs_agent_id", "tenant_agent_configs", ["agent_id"])

    # ── tenant_tool_configs ───────────────────────────────────────────────
    if not _table_exists(conn, "tenant_tool_configs"):
        op.create_table(
            "tenant_tool_configs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tool_id", sa.String(), sa.ForeignKey("tool_definitions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("config", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("tenant_id", "tool_id", name="uq_tenant_tool_config"),
        )
        op.create_index("ix_tenant_tool_configs_tenant_id", "tenant_tool_configs", ["tenant_id"])
        op.create_index("ix_tenant_tool_configs_tool_id", "tenant_tool_configs", ["tool_id"])


def downgrade() -> None:
    op.drop_table("tenant_tool_configs")
    op.drop_table("tenant_agent_configs")
    op.drop_table("agent_definitions")
    op.drop_table("tool_definitions")
