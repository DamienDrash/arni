"""Add ForeignKey constraints on tenant_id columns.

Revision ID: 0261621d54e2
Revises: 42f8a7fcb1f9
Create Date: 2026-02-22

Adds ForeignKey(tenants.id, ondelete=RESTRICT) to all tables that
reference a tenant but lack a proper FK constraint:
  - chat_sessions
  - chat_messages
  - settings
  - users
  - audit_logs
  - studio_members
  - usage_records

Uses render_as_batch=True (already set in env.py) for SQLite compat.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = "0261621d54e2"
down_revision = "4f31e5c56744"
branch_labels = None
depends_on = None

# Tables to constrain: (table_name, fk_name)
TENANT_TABLES = [
    ("chat_sessions",  "fk_chat_sessions_tenant"),
    ("chat_messages",  "fk_chat_messages_tenant"),
    ("settings",       "fk_settings_tenant"),
    ("users",          "fk_users_tenant"),
    ("audit_logs",     "fk_audit_logs_tenant"),
    ("studio_members", "fk_studio_members_tenant"),
    ("usage_records",  "fk_usage_records_tenant"),
]


def _check_orphaned_tenant_ids(conn, table: str) -> None:
    """Raise if there are rows with tenant_id not in tenants table."""
    result = conn.execute(text(
        f"SELECT COUNT(*) FROM {table} t "
        f"WHERE t.tenant_id IS NOT NULL "
        f"AND NOT EXISTS (SELECT 1 FROM tenants tn WHERE tn.id = t.tenant_id)"
    ))
    count = result.scalar()
    if count:
        raise RuntimeError(
            f"Cannot add FK to '{table}': {count} row(s) with orphaned tenant_id. "
            "Fix data before migrating."
        )


def upgrade() -> None:
    conn = op.get_bind()

    # Pre-flight: verify no orphaned tenant_ids exist
    for table, _ in TENANT_TABLES:
        _check_orphaned_tenant_ids(conn, table)

    # Add FK constraints (batch mode handles SQLite)
    for table, fk_name in TENANT_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_foreign_key(
                fk_name,
                "tenants",
                ["tenant_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    for table, fk_name in reversed(TENANT_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
