"""fix(db): convert all DateTime columns to TIMESTAMPTZ for timezone consistency.

Issue #7: All DateTime columns should use timezone=True (TIMESTAMPTZ in PostgreSQL)
to avoid offset-naive/aware TypeError when comparing with datetime.now(timezone.utc).

Revision ID: 2026_03_15_tz_consistency
Revises: 2026_03_15_backfill_to_alembic
Create Date: 2026-03-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "2026_03_15_tz_consistency"
down_revision = "2026_03_15_backfill_to_alembic"
branch_labels = None
depends_on = None


def _table_has_column(conn, table: str, column: str) -> bool:
    """Return True if *column* exists in *table*, False otherwise."""
    try:
        cols = {c["name"] for c in inspect(conn).get_columns(table)}
        return column in cols
    except Exception:
        return False


def _table_exists(conn, table: str) -> bool:
    """Return True if *table* exists in the current schema."""
    try:
        inspect(conn).get_columns(table)
        return True
    except Exception:
        return False


# Map of table → list of DateTime columns that need TIMESTAMPTZ conversion.
# Only tables with previously-naive DateTime columns are listed here.
# Columns already converted in 2026_03_13_fix_tz (email_verified_at etc.) are excluded.
_TABLE_COLUMNS: dict[str, list[str]] = {
    "chat_sessions": ["created_at", "last_message_at"],
    "chat_messages": ["timestamp"],
    "settings": ["updated_at"],
    "tenant_configs": ["updated_at"],
    "member_feedback": ["created_at", "updated_at"],
    "tenants": [
        "created_at",
        "updated_at",
        "tos_accepted_at",
        "privacy_accepted_at",
        "onboarding_completed_at",
    ],
    "users": [
        "created_at",
        "updated_at",
        "locked_until",
        "last_failed_login_at",
        "mfa_enabled_at",
        "last_login_at",
    ],
    "audit_logs": ["created_at"],
    "studio_members": ["member_since", "enriched_at", "created_at", "updated_at"],
    "subscriptions": [
        "current_period_start",
        "current_period_end",
        "trial_ends_at",
        "canceled_at",
        "created_at",
        "updated_at",
    ],
    "plans": ["created_at", "updated_at"],
    "addon_definitions": ["created_at", "updated_at"],
    "tenant_addons": ["created_at"],
    "tenant_llm_configs": ["created_at", "updated_at"],
    "token_purchases": ["created_at"],
    "image_credit_packs": ["created_at"],
    "image_credit_balances": ["updated_at"],
    "image_credit_transactions": ["created_at"],
    "image_credit_purchases": ["created_at", "updated_at"],
    "llm_model_costs": ["updated_at"],
    "llm_usage_log": ["created_at"],
    "campaigns": ["preview_expires_at", "scheduled_at", "sent_at", "created_at", "updated_at"],
    "campaign_templates": ["created_at", "updated_at"],
    "campaign_variants": ["winner_selected_at", "created_at"],
    "campaign_recipients": ["sent_at", "delivered_at", "opened_at", "clicked_at", "converted_at"],
    "member_segments": ["created_at", "updated_at"],
    "scheduled_follow_ups": ["follow_up_at", "sent_at", "created_at", "updated_at"],
    "pending_invitations": ["expires_at", "accepted_at", "created_at"],
    "refresh_tokens": ["expires_at", "created_at"],
    "user_sessions": ["last_active_at", "created_at"],
    "member_import_logs": ["created_at"],
}


def upgrade() -> None:
    conn = op.get_bind()

    # PostgreSQL: use ALTER COLUMN … TYPE TIMESTAMPTZ USING … AT TIME ZONE 'UTC'
    # SQLite (test env): batch_alter_table with sa.DateTime(timezone=True) is a no-op
    # for SQLite but keeps the migration idempotent.
    is_pg = conn.dialect.name == "postgresql"

    for table, columns in _TABLE_COLUMNS.items():
        if not _table_exists(conn, table):
            continue

        if is_pg:
            for col in columns:
                if _table_has_column(conn, table, col):
                    op.execute(
                        text(
                            f"ALTER TABLE {table} ALTER COLUMN {col} "
                            f"TYPE TIMESTAMPTZ USING {col} AT TIME ZONE 'UTC'"
                        )
                    )
        else:
            # SQLite: use batch_alter_table for compatibility
            cols_present = [
                col for col in columns if _table_has_column(conn, table, col)
            ]
            if cols_present:
                with op.batch_alter_table(table) as batch_op:
                    for col in cols_present:
                        batch_op.alter_column(
                            col,
                            type_=sa.DateTime(timezone=True),
                            existing_type=sa.DateTime(),
                        )


def downgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    for table, columns in _TABLE_COLUMNS.items():
        if not _table_exists(conn, table):
            continue

        if is_pg:
            for col in columns:
                if _table_has_column(conn, table, col):
                    op.execute(
                        text(
                            f"ALTER TABLE {table} ALTER COLUMN {col} "
                            f"TYPE TIMESTAMP WITHOUT TIME ZONE "
                            f"USING {col} AT TIME ZONE 'UTC'"
                        )
                    )
        else:
            cols_present = [
                col for col in columns if _table_has_column(conn, table, col)
            ]
            if cols_present:
                with op.batch_alter_table(table) as batch_op:
                    for col in cols_present:
                        batch_op.alter_column(
                            col,
                            type_=sa.DateTime(),
                            existing_type=sa.DateTime(timezone=True),
                        )
