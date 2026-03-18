"""Add orchestrator_definitions, orchestrator_versions, orchestrator_tenant_overrides tables.

Revision ID: 2026_03_17_orchestrator_manager
Revises: 2026_03_16_campaign_attachments
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_17_orchestrator_manager"
down_revision = "2026_03_16_campaign_attachments"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("orchestrator_definitions"):
        op.create_table(
            "orchestrator_definitions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(64), nullable=False, unique=True),
            sa.Column("display_name", sa.String(128), nullable=False),
            sa.Column("category", sa.String(16), nullable=False),
            sa.Column("scope", sa.String(16), nullable=False),
            sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
            sa.Column("config_schema", sa.JSON, nullable=True),
            sa.Column("config_current", sa.JSON, nullable=True),
            sa.Column("guardrails", sa.JSON, nullable=True),
            sa.Column("config_version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        )
        op.create_index("ix_orchestrator_definitions_name", "orchestrator_definitions", ["name"])

    if not _table_exists("orchestrator_versions"):
        op.create_table(
            "orchestrator_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("orchestrator_id", sa.String(36), sa.ForeignKey("orchestrator_definitions.id"), nullable=False),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("config_snapshot", sa.JSON, nullable=True),
            sa.Column("changed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rollback_safe", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("change_summary", sa.Text, nullable=True),
        )
        op.create_index("ix_orchestrator_versions_orchestrator_id", "orchestrator_versions", ["orchestrator_id"])

    if not _table_exists("orchestrator_tenant_overrides"):
        op.create_table(
            "orchestrator_tenant_overrides",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("orchestrator_id", sa.String(36), sa.ForeignKey("orchestrator_definitions.id"), nullable=False),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("config_override", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("orchestrator_id", "tenant_id", name="uq_orch_tenant"),
        )
        op.create_index("ix_orchestrator_tenant_overrides_tenant_id", "orchestrator_tenant_overrides", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("orchestrator_tenant_overrides")
    op.drop_table("orchestrator_versions")
    op.drop_table("orchestrator_definitions")
