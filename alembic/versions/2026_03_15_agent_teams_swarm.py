"""Add agent teams, steps, tools, and run tables for the swarm system.

Revision ID: 2026_03_15_agent_teams
Revises: 2026_03_10_addon_img_quota
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_15_agent_teams"
down_revision = "2026_03_10_addon_img_quota"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_team_configs ─────────────────────────────────────────────────────
    op.create_table(
        "agent_team_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lead_agent_slug", sa.String(64), nullable=True),
        sa.Column("execution_mode", sa.String(32), nullable=False, server_default="pipeline"),
        sa.Column("input_schema_json", sa.Text(), nullable=True),
        sa.Column("yaml_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_agent_team_tenant_slug"),
    )
    op.create_index("ix_agent_team_configs_id", "agent_team_configs", ["id"])
    op.create_index("ix_agent_team_configs_tenant_id", "agent_team_configs", ["tenant_id"])
    op.create_index("ix_agent_team_configs_slug", "agent_team_configs", ["slug"])
    op.create_index("ix_agent_team_tenant_active", "agent_team_configs", ["tenant_id", "is_active"])

    # ── agent_team_steps ───────────────────────────────────────────────────────
    op.create_table(
        "agent_team_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agent_slug", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("tools_json", sa.Text(), nullable=True),
        sa.Column("prompt_override", sa.Text(), nullable=True),
        sa.Column("model_override", sa.String(128), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["agent_team_configs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "step_order", name="uq_step_team_order"),
    )
    op.create_index("ix_agent_team_steps_id", "agent_team_steps", ["id"])
    op.create_index("ix_agent_team_steps_team_id", "agent_team_steps", ["team_id"])
    op.create_index("ix_step_team_id_order", "agent_team_steps", ["team_id", "step_order"])

    # ── agent_tool_definitions ─────────────────────────────────────────────────
    op.create_table(
        "agent_tool_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tool_class", sa.String(256), nullable=True),
        sa.Column("config_schema_json", sa.Text(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_tool_tenant_slug"),
    )
    op.create_index("ix_agent_tool_definitions_id", "agent_tool_definitions", ["id"])
    op.create_index("ix_agent_tool_definitions_tenant_id", "agent_tool_definitions", ["tenant_id"])
    op.create_index("ix_agent_tool_definitions_slug", "agent_tool_definitions", ["slug"])
    op.create_index("ix_tool_tenant_active", "agent_tool_definitions", ["tenant_id", "is_active"])

    # ── agent_team_runs ────────────────────────────────────────────────────────
    op.create_table(
        "agent_team_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("team_slug", sa.String(64), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("trigger_source", sa.String(32), nullable=False, server_default="api"),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("steps_json", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_team_runs_id", "agent_team_runs", ["id"])
    op.create_index("ix_agent_team_runs_tenant_id", "agent_team_runs", ["tenant_id"])
    op.create_index("ix_agent_team_runs_team_slug", "agent_team_runs", ["team_slug"])
    op.create_index("ix_run_tenant_team", "agent_team_runs", ["tenant_id", "team_slug"])
    op.create_index("ix_run_started_at", "agent_team_runs", ["started_at"])
    op.create_index("ix_run_tenant_started", "agent_team_runs", ["tenant_id", "started_at"])
    op.create_index("ix_run_tenant_success", "agent_team_runs", ["tenant_id", "success"])


def downgrade() -> None:
    op.drop_table("agent_team_runs")
    op.drop_table("agent_tool_definitions")
    op.drop_table("agent_team_steps")
    op.drop_table("agent_team_configs")
