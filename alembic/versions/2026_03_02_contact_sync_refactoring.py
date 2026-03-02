"""2026-03-02: Contact-Sync Refactoring.

Adds sync_logs, sync_schedules, webhook_endpoints tables and extends
tenant_integrations with sync-specific columns.

Revision ID: 2026_03_02_contact_sync_refactoring
Revises: None (standalone)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "2026_03_02_contact_sync_refactoring"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sync_logs ────────────────────────────────────────────────────────
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_integration_id",
            sa.Integer,
            sa.ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sync_type", sa.String(32), nullable=False, server_default="full"),
        sa.Column("trigger", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("records_fetched", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("records_created", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("records_updated", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("records_deleted", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("records_unchanged", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("records_failed", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_details", JSONB, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sync_logs_tenant_integration_id", "sync_logs", ["tenant_integration_id"])
    op.create_index("ix_sync_logs_tenant_id", "sync_logs", ["tenant_id"])
    op.create_index("ix_sync_logs_status", "sync_logs", ["status"])
    op.create_index("ix_sync_logs_created_at", "sync_logs", ["created_at"])

    # ── sync_schedules ───────────────────────────────────────────────────
    op.create_table(
        "sync_schedules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_integration_id",
            sa.Integer,
            sa.ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("cron_expression", sa.String(64), nullable=False, server_default="0 */6 * * *"),
        sa.Column("last_run_at", sa.DateTime, nullable=True),
        sa.Column("next_run_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sync_schedules_tenant_id", "sync_schedules", ["tenant_id"])
    op.create_index("ix_sync_schedules_next_run", "sync_schedules", ["next_run_at"])

    # ── webhook_endpoints ────────────────────────────────────────────────
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_integration_id",
            sa.Integer,
            sa.ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_path", sa.String(255), nullable=False, unique=True),
        sa.Column("secret_token", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("events_filter", JSONB, nullable=True),
        sa.Column("last_received_at", sa.DateTime, nullable=True),
        sa.Column("total_received", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_endpoints_tenant_id", "webhook_endpoints", ["tenant_id"])
    op.create_index("ix_webhook_endpoints_path", "webhook_endpoints", ["endpoint_path"])

    # ── Extend tenant_integrations with sync-specific columns ────────────
    for col_name, col_type, default in [
        ("last_sync_at", sa.DateTime(), None),
        ("last_sync_status", sa.String(16), "idle"),
        ("last_sync_error", sa.Text(), None),
        ("sync_direction", sa.String(16), "inbound"),
        ("sync_mode", sa.String(16), "full"),
        ("records_synced_total", sa.Integer(), "0"),
        ("health_status", sa.String(16), "unknown"),
        ("health_checked_at", sa.DateTime(), None),
    ]:
        try:
            if default is not None and isinstance(default, str) and col_name not in ("last_sync_status", "sync_direction", "sync_mode", "health_status"):
                op.add_column("tenant_integrations", sa.Column(col_name, col_type, server_default=sa.text(default)))
            elif default is not None:
                op.add_column("tenant_integrations", sa.Column(col_name, col_type, server_default=default))
            else:
                op.add_column("tenant_integrations", sa.Column(col_name, col_type, nullable=True))
        except Exception:
            pass  # Column may already exist

    # ── RLS policies ─────────────────────────────────────────────────────
    for table in ("sync_logs", "sync_schedules", "webhook_endpoints"):
        op.execute(f"""
            ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};
            CREATE POLICY tenant_isolation_{table} ON {table}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::int);
        """)


def downgrade() -> None:
    for table in ("webhook_endpoints", "sync_schedules", "sync_logs"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
        op.drop_table(table)

    for col_name in (
        "last_sync_at", "last_sync_status", "last_sync_error",
        "sync_direction", "sync_mode", "records_synced_total",
        "health_status", "health_checked_at",
    ):
        try:
            op.drop_column("tenant_integrations", col_name)
        except Exception:
            pass
