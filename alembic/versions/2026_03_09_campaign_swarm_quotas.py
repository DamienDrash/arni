"""Add image generation and media storage quota columns.

Revision ID: 2026_03_09_campaign_quotas
Revises: 2026_03_05_media_image
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_09_campaign_quotas"
down_revision = "2026_03_05_media_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("ai_image_generations_per_month", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("media_storage_mb", sa.Integer(), nullable=True))
    op.add_column("usage_records", sa.Column("ai_image_generations_used", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("usage_records", sa.Column("media_storage_bytes_used", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("usage_records", "media_storage_bytes_used")
    op.drop_column("usage_records", "ai_image_generations_used")
    op.drop_column("plans", "media_storage_mb")
    op.drop_column("plans", "ai_image_generations_per_month")
