"""Campaign Phase 2: Automations Engine tables

Revision ID: camp_phase2
Revises: camp_phase1
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "camp_phase2"
down_revision = "camp_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── automation_workflows ──────────────────────────────────────────
    op.create_table(
        "automation_workflows",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="0", nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False, server_default="segment_entry"),
        sa.Column("trigger_config_json", sa.Text, nullable=True),
        sa.Column("workflow_graph_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("max_concurrent_runs", sa.Integer, server_default="1000", nullable=False),
        sa.Column("re_entry_policy", sa.String(20), server_default="skip", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_aw_tenant_active", "automation_workflows", ["tenant_id", "is_active"])

    # ── automation_runs ───────────────────────────────────────────────
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.Integer, sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.Integer, sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("current_node_id", sa.String(100), nullable=True),
        sa.Column("wait_until", sa.DateTime, nullable=True),
        sa.Column("context_json", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("ix_ar_workflow_status", "automation_runs", ["workflow_id", "status"])
    op.create_index("ix_ar_contact", "automation_runs", ["contact_id", "status"])
    op.create_index("ix_ar_wait", "automation_runs", ["status", "wait_until"])

    # ── automation_step_logs ──────────────────────────────────────────
    op.create_table(
        "automation_step_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(100), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="executed", nullable=False),
        sa.Column("input_json", sa.Text, nullable=True),
        sa.Column("output_json", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("executed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_asl_run", "automation_step_logs", ["run_id"])

    # ── contact_segment_snapshots (for change detection) ──────────────
    op.create_table(
        "contact_segment_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.Integer, sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_id", sa.Integer, sa.ForeignKey("contact_segments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_member", sa.Boolean, server_default="0", nullable=False),
        sa.Column("snapshot_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_css_tenant_segment", "contact_segment_snapshots", ["tenant_id", "segment_id"])
    op.create_index("ix_css_contact", "contact_segment_snapshots", ["contact_id", "segment_id"])


def downgrade() -> None:
    op.drop_table("contact_segment_snapshots")
    op.drop_table("automation_step_logs")
    op.drop_table("automation_runs")
    op.drop_table("automation_workflows")
