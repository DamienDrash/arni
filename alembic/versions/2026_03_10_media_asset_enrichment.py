"""Media asset enrichment: add metadata columns for display_name, description, tags, usage_context, dominant_colors, brightness, orientation, aspect_ratio

Revision ID: 2026_03_10_media_enrichment
Revises: 2026_03_09_campaign_quotas
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_10_media_enrichment"
down_revision = "2026_03_09_campaign_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("media_assets") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("usage_context", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("dominant_colors", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("brightness", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("orientation", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("aspect_ratio", sa.String(16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("media_assets") as batch_op:
        batch_op.drop_column("aspect_ratio")
        batch_op.drop_column("orientation")
        batch_op.drop_column("brightness")
        batch_op.drop_column("dominant_colors")
        batch_op.drop_column("usage_context")
        batch_op.drop_column("tags")
        batch_op.drop_column("description")
        batch_op.drop_column("display_name")
