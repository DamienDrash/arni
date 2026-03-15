"""fix(db): restore FK constraints dropped in fadf7c20edd1 without recreation.

Issue #11: Migration fadf7c20edd1_add_member_feedback_table.py dropped FK
constraints on audit_logs, chat_messages, chat_sessions, settings,
studio_members, and users but never re-added them in the upgrade path.
This migration restores those constraints using NOT VALID + VALIDATE to
avoid locking the table or failing on pre-existing orphan rows.

Revision ID: 2026_03_15_restore_fks
Revises: 2026_03_15_tz_consistency
Create Date: 2026-03-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "2026_03_15_restore_fks"
down_revision = "2026_03_15_tz_consistency"
branch_labels = None
depends_on = None


def _constraint_exists(conn, table: str, constraint_name: str) -> bool:
    """Return True if a named constraint already exists on *table*."""
    try:
        if conn.dialect.name == "postgresql":
            result = conn.execute(
                text(
                    "SELECT 1 FROM pg_constraint "
                    "WHERE conname = :cname AND conrelid = :table::regclass"
                ),
                {"cname": constraint_name, "table": table},
            )
            return result.scalar() is not None
        # SQLite: check via inspector foreign_keys
        fks = inspect(conn).get_foreign_keys(table)
        return any(fk.get("name") == constraint_name for fk in fks)
    except Exception:
        return False


def _table_exists(conn, table: str) -> bool:
    try:
        inspect(conn).get_columns(table)
        return True
    except Exception:
        return False


# FK constraints that were dropped by fadf7c20edd1 and never re-created.
# Format: (table, constraint_name, ref_table, local_col, ref_col)
_MISSING_FKS = [
    ("audit_logs",    "fk_audit_logs_tenant",    "tenants", "tenant_id", "id"),
    ("chat_messages", "fk_chat_messages_tenant", "tenants", "tenant_id", "id"),
    ("chat_sessions", "fk_chat_sessions_tenant", "tenants", "tenant_id", "id"),
    ("settings",      "fk_settings_tenant",      "tenants", "tenant_id", "id"),
    ("studio_members","fk_studio_members_tenant","tenants", "tenant_id", "id"),
    ("users",         "fk_users_tenant",         "tenants", "tenant_id", "id"),
]


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    for table, constraint_name, ref_table, local_col, ref_col in _MISSING_FKS:
        if not _table_exists(conn, table):
            continue
        if _constraint_exists(conn, table, constraint_name):
            continue  # idempotent: already present

        if is_pg:
            # Add WITHOUT validating existing rows first (avoids full table scan /
            # lock and won't fail on pre-existing orphan rows).
            op.execute(
                text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
                    f"FOREIGN KEY ({local_col}) REFERENCES {ref_table}({ref_col}) NOT VALID"
                )
            )
            # Validate in a separate pass (uses ShareUpdateExclusiveLock, not
            # AccessExclusiveLock – safe for concurrent read traffic).
            op.execute(
                text(f"ALTER TABLE {table} VALIDATE CONSTRAINT {constraint_name}")
            )
        else:
            # SQLite: batch_alter_table re-creates the table with the FK
            with op.batch_alter_table(table) as batch_op:
                batch_op.create_foreign_key(
                    constraint_name, ref_table, [local_col], [ref_col]
                )


def downgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    for table, constraint_name, ref_table, local_col, ref_col in reversed(_MISSING_FKS):
        if not _table_exists(conn, table):
            continue
        if not _constraint_exists(conn, table, constraint_name):
            continue  # nothing to drop

        if is_pg:
            op.execute(
                text(f"ALTER TABLE {table} DROP CONSTRAINT {constraint_name}")
            )
        else:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_constraint(constraint_name, type_="foreignkey")
