"""Move _backfill_columns() into proper Alembic migration.

These columns were previously added via the runtime _backfill_columns() helper
in db.py. Moving them here ensures they are tracked in the migration history.

Revision ID: 2026_03_15_backfill_to_alembic
Revises: 2026_03_13_fix_tz
Create Date: 2026-03-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "2026_03_15_backfill_to_alembic"
down_revision = "2026_03_13_fix_tz"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    try:
        cols = {c["name"] for c in inspect(conn).get_columns(table)}
        return column in cols
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()

    # ── plans: monthly_image_credits ─────────────────────────────────────────
    if not _has_column(conn, "plans", "monthly_image_credits"):
        with op.batch_alter_table("plans") as batch_op:
            batch_op.add_column(
                sa.Column("monthly_image_credits", sa.Integer(), nullable=True, server_default="0")
            )

    # ── ai_image_providers: ELO + fal category enrichment ────────────────────
    cols_to_add = [
        ("fal_category",          sa.Column("fal_category",          sa.String(32),  nullable=True)),
        ("elo_score",             sa.Column("elo_score",             sa.Integer(),   nullable=True)),
        ("elo_rank",              sa.Column("elo_rank",              sa.Integer(),   nullable=True)),
        ("price_per_image_cents", sa.Column("price_per_image_cents", sa.Integer(),   nullable=True)),
    ]

    try:
        existing = {c["name"] for c in inspect(conn).get_columns("ai_image_providers")}
        missing = [(name, col) for name, col in cols_to_add if name not in existing]
        if missing:
            with op.batch_alter_table("ai_image_providers") as batch_op:
                for _, col in missing:
                    batch_op.add_column(col)
    except Exception:
        pass  # Table may not exist in test environments

    # Backfill fal_category for existing seeded providers
    try:
        conn.execute(text("""
            UPDATE ai_image_providers
            SET fal_category = CASE
                WHEN slug LIKE '%_edit' OR slug = 'flux_kontext_pro' THEN 'image-to-image'
                ELSE 'text-to-image'
            END
            WHERE fal_category IS NULL
              AND provider_type IN ('fal_ai', 'fal_ai_schnell', 'fal_generic', 'recraft_v3', 'ideogram_v2')
        """))
    except Exception:
        pass  # Table may be empty or not exist


def downgrade() -> None:
    conn = op.get_bind()

    for col in ("fal_category", "elo_score", "elo_rank", "price_per_image_cents"):
        if _has_column(conn, "ai_image_providers", col):
            with op.batch_alter_table("ai_image_providers") as batch_op:
                batch_op.drop_column(col)

    if _has_column(conn, "plans", "monthly_image_credits"):
        with op.batch_alter_table("plans") as batch_op:
            batch_op.drop_column("monthly_image_credits")
