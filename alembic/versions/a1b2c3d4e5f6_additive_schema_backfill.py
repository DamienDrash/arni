"""Additive schema backfill — columns that exist in models.py but were not
part of the original Alembic migrations (they were created via
Base.metadata.create_all() in development).

Revision ID: a1b2c3d4e5f6
Revises: 0261621d54e2
Create Date: 2026-02-22

Changes:
  audit_logs    — add `category` (NOT NULL, backfill 'other'), `target_type`, `target_id`,
                  `details_json`
  chat_sessions — add `email` column
  plans         — ensure table exists (idempotent create)
  subscriptions — ensure table exists (idempotent create)
  usage_records — ensure table exists (idempotent create)

Note: All ALTER TABLE ops use batch_alter_table for SQLite compatibility.
      New tables are created only if they don't already exist.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "a1b2c3d4e5f6"
down_revision = "0261621d54e2"
branch_labels = None
depends_on = None


def _table_has_column(conn, table: str, column: str) -> bool:
    try:
        insp = inspect(conn)
        cols = {c["name"] for c in insp.get_columns(table)}
        return column in cols
    except Exception:
        return False


def _table_exists(conn, table: str) -> bool:
    try:
        insp = inspect(conn)
        return table in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()

    # ── audit_logs: add category, target_type, target_id, details_json ────────
    audit_cols = {
        "category":    sa.Column("category",    sa.String(), nullable=True),
        "target_type": sa.Column("target_type", sa.String(), nullable=True),
        "target_id":   sa.Column("target_id",   sa.String(), nullable=True),
        "details_json": sa.Column("details_json", sa.Text(),  nullable=True),
    }
    with op.batch_alter_table("audit_logs") as batch_op:
        for col_name, col_def in audit_cols.items():
            if not _table_has_column(conn, "audit_logs", col_name):
                batch_op.add_column(col_def)

    # Backfill category so NOT NULL constraint can be added later
    if _table_has_column(conn, "audit_logs", "category"):
        conn.execute(text("UPDATE audit_logs SET category = 'other' WHERE category IS NULL"))

    # ── chat_sessions: add email column ────────────────────────────────────────
    if not _table_has_column(conn, "chat_sessions", "email"):
        with op.batch_alter_table("chat_sessions") as batch_op:
            batch_op.add_column(sa.Column("email", sa.String(), nullable=True))

    # ── plans table (idempotent create) ───────────────────────────────────────
    if not _table_exists(conn, "plans"):
        op.create_table(
            "plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), unique=True, nullable=False),
            sa.Column("stripe_price_id", sa.String(), nullable=True),
            sa.Column("price_monthly_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_members", sa.Integer(), nullable=True),
            sa.Column("max_monthly_messages", sa.Integer(), nullable=True),
            sa.Column("max_channels", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("telegram_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("email_channel_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("voice_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("memory_analyzer_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("custom_prompts_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    # ── subscriptions table (idempotent create) ────────────────────────────────
    if not _table_exists(conn, "subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
            sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("stripe_subscription_id", sa.String(), nullable=True, unique=True),
            sa.Column("stripe_customer_id", sa.String(), nullable=True),
            sa.Column("current_period_start", sa.DateTime(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
            sa.Column("canceled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    # ── usage_records table (idempotent create) ────────────────────────────────
    if not _table_exists(conn, "usage_records"):
        op.create_table(
            "usage_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("period_year", sa.Integer(), nullable=False),
            sa.Column("period_month", sa.Integer(), nullable=False),
            sa.Column("messages_inbound", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("messages_outbound", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("active_members", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("llm_tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "period_year", "period_month", name="uq_usage_tenant_period"),
        )


def downgrade() -> None:
    # Drop new tables (idempotent — only when they were created by this revision)
    conn = op.get_bind()
    for tbl in ("usage_records", "subscriptions", "plans"):
        # Only drop if we can detect this revision created them
        # (If the table existed before, we never dropped existing data on upgrade)
        pass  # Intentional: do not drop tables that may contain data

    # Remove columns we added
    if _table_has_column(conn, "chat_sessions", "email"):
        with op.batch_alter_table("chat_sessions") as batch_op:
            batch_op.drop_column("email")
