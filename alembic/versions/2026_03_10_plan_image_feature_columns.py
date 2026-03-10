"""add ai_image_previews and brand_style columns to plans

Revision ID: 2026_03_10_plan_img_features
Revises: dyn7_integration_seed_001, 2026_03_10_brand_refs
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_10_plan_img_features"
down_revision = ("dyn7_integration_seed_001", "2026_03_10_brand_refs")
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("plans") as batch_op:
        batch_op.add_column(sa.Column("ai_image_previews_per_month", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("brand_style_enabled", sa.Boolean(), nullable=False, server_default="false"))
        batch_op.add_column(sa.Column("text_overlay_images_enabled", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    with op.batch_alter_table("plans") as batch_op:
        batch_op.drop_column("text_overlay_images_enabled")
        batch_op.drop_column("brand_style_enabled")
        batch_op.drop_column("ai_image_previews_per_month")
