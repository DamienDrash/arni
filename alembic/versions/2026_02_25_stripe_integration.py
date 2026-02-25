"""Stripe integration — extend plans, addon_definitions, tenant_addons.

Revision ID: 202602250001
Revises: 202602240001
Create Date: 2026-02-25

Changes:
  plans              — add stripe_product_id, stripe_price_id, stripe_price_yearly_id,
                       description, price_yearly_cents, trial_days, display_order,
                       is_highlighted, features_json, is_public, overage_*_cents, updated_at
  addon_definitions  — create table if not exists
  tenant_addons      — add updated_at column
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '202602250001'
down_revision: Union[str, None] = '202602240001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table: str) -> bool:
    try:
        insp = inspect(conn)
        return table in insp.get_table_names()
    except Exception:
        return False


def _table_has_column(conn, table: str, column: str) -> bool:
    try:
        insp = inspect(conn)
        cols = {c["name"] for c in insp.get_columns(table)}
        return column in cols
    except Exception:
        return False


# Columns to add to the plans table (name, type, server_default, nullable)
PLAN_NEW_COLUMNS = [
    ("stripe_product_id", sa.String(), None, True),
    ("stripe_price_id", sa.String(), None, True),
    ("stripe_price_yearly_id", sa.String(), None, True),
    ("description", sa.Text(), None, True),
    ("price_yearly_cents", sa.Integer(), None, True),
    ("trial_days", sa.Integer(), sa.text("0"), False),
    ("display_order", sa.Integer(), sa.text("0"), False),
    ("is_highlighted", sa.Boolean(), sa.text("0"), False),
    ("features_json", sa.Text(), None, True),
    ("is_public", sa.Boolean(), sa.text("1"), False),
    ("overage_conversation_cents", sa.Integer(), sa.text("5"), True),
    ("overage_user_cents", sa.Integer(), sa.text("1500"), True),
    ("overage_connector_cents", sa.Integer(), sa.text("4900"), True),
    ("overage_channel_cents", sa.Integer(), sa.text("2900"), True),
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Extend plans table ────────────────────────────────────────────
    if _table_exists(conn, "plans"):
        with op.batch_alter_table("plans") as batch_op:
            for col_name, col_type, server_default, nullable in PLAN_NEW_COLUMNS:
                if not _table_has_column(conn, "plans", col_name):
                    batch_op.add_column(
                        sa.Column(col_name, col_type, server_default=server_default, nullable=nullable)
                    )
            # updated_at
            if not _table_has_column(conn, "plans", "updated_at"):
                batch_op.add_column(
                    sa.Column("updated_at", sa.DateTime(), nullable=True)
                )

    # ── 2. Create addon_definitions table ────────────────────────────────
    if not _table_exists(conn, "addon_definitions"):
        op.create_table(
            "addon_definitions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("icon", sa.String(), nullable=True),
            sa.Column("price_monthly_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("stripe_product_id", sa.String(), nullable=True),
            sa.Column("stripe_price_id", sa.String(), nullable=True),
            sa.Column("features_json", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
        op.create_index(op.f("ix_addon_definitions_id"), "addon_definitions", ["id"])

    # ── 3. Extend tenant_addons table ────────────────────────────────────
    if _table_exists(conn, "tenant_addons"):
        with op.batch_alter_table("tenant_addons") as batch_op:
            if not _table_has_column(conn, "tenant_addons", "updated_at"):
                batch_op.add_column(
                    sa.Column("updated_at", sa.DateTime(), nullable=True)
                )
            if not _table_has_column(conn, "tenant_addons", "stripe_subscription_item_id"):
                batch_op.add_column(
                    sa.Column("stripe_subscription_item_id", sa.String(), nullable=True)
                )

    # ── 4. Set display_order defaults for existing plans ─────────────────
    if _table_exists(conn, "plans") and _table_has_column(conn, "plans", "display_order"):
        conn.execute(sa.text(
            "UPDATE plans SET display_order = CASE slug "
            "WHEN 'starter' THEN 1 "
            "WHEN 'pro' THEN 2 "
            "WHEN 'business' THEN 3 "
            "WHEN 'enterprise' THEN 4 "
            "ELSE 99 END "
            "WHERE display_order = 0 OR display_order IS NULL"
        ))

    # ── 5. Set is_highlighted for Pro plan ───────────────────────────────
    if _table_exists(conn, "plans") and _table_has_column(conn, "plans", "is_highlighted"):
        conn.execute(sa.text(
            "UPDATE plans SET is_highlighted = 1 WHERE slug = 'pro'"
        ))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove addon_definitions table
    if _table_exists(conn, "addon_definitions"):
        op.drop_index(op.f("ix_addon_definitions_id"), table_name="addon_definitions")
        op.drop_table("addon_definitions")

    # Remove new columns from plans (batch mode for SQLite)
    if _table_exists(conn, "plans"):
        with op.batch_alter_table("plans") as batch_op:
            for col_name, _, _, _ in PLAN_NEW_COLUMNS:
                if _table_has_column(conn, "plans", col_name):
                    batch_op.drop_column(col_name)
            if _table_has_column(conn, "plans", "updated_at"):
                batch_op.drop_column("updated_at")

    # Remove new columns from tenant_addons
    if _table_exists(conn, "tenant_addons"):
        with op.batch_alter_table("tenant_addons") as batch_op:
            if _table_has_column(conn, "tenant_addons", "updated_at"):
                batch_op.drop_column("updated_at")
