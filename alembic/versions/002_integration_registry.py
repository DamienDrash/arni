"""002: Integration Registry tables.

Phase 2, Meilenstein 2.1 – Creates the core tables for the
dynamic Integration & Skills architecture:
  - integration_definitions
  - capability_definitions
  - integration_capabilities
  - tenant_integrations

Revision ID: 002_integration_registry
Revises: 001_add_rls_policies
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002_integration_registry"
down_revision = None  # Standalone migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── integration_definitions ──────────────────────────────────────────
    op.create_table(
        "integration_definitions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(32), nullable=False, server_default="custom"),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("auth_type", sa.String(16), nullable=False, server_default="api_key"),
        sa.Column("config_schema", JSONB, nullable=True),
        sa.Column("adapter_class", sa.String(255), nullable=True),
        sa.Column("skill_file", sa.String(255), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("min_plan", sa.String(32), nullable=True, server_default="professional"),
        sa.Column("version", sa.String(16), nullable=True, server_default="1.0.0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── capability_definitions ───────────────────────────────────────────
    op.create_table(
        "capability_definitions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("input_schema", JSONB, nullable=True),
        sa.Column("output_schema", JSONB, nullable=True),
        sa.Column("is_destructive", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── integration_capabilities (many-to-many) ─────────────────────────
    op.create_table(
        "integration_capabilities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "integration_id",
            sa.String(32),
            sa.ForeignKey("integration_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capability_id",
            sa.String(64),
            sa.ForeignKey("capability_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("integration_id", "capability_id", name="uq_integration_capability"),
    )
    op.create_index("ix_ic_integration_id", "integration_capabilities", ["integration_id"])
    op.create_index("ix_ic_capability_id", "integration_capabilities", ["capability_id"])

    # ── tenant_integrations ──────────────────────────────────────────────
    op.create_table(
        "tenant_integrations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            sa.String(32),
            sa.ForeignKey("integration_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending_setup"),
        sa.Column("config_encrypted", sa.Text, nullable=True),
        sa.Column("config_meta", JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_health_check", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "integration_id", name="uq_tenant_integration"),
    )
    op.create_index("ix_ti_tenant_id", "tenant_integrations", ["tenant_id"])
    op.create_index("ix_ti_integration_id", "tenant_integrations", ["integration_id"])

    # ── RLS for tenant_integrations ──────────────────────────────────────
    op.execute("""
        ALTER TABLE tenant_integrations ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_tenant_integrations ON tenant_integrations;
        CREATE POLICY tenant_isolation_tenant_integrations ON tenant_integrations
            USING (tenant_id = current_setting('app.current_tenant_id', true)::int);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenant_integrations ON tenant_integrations;")
    op.drop_table("tenant_integrations")
    op.drop_table("integration_capabilities")
    op.drop_table("capability_definitions")
    op.drop_table("integration_definitions")
