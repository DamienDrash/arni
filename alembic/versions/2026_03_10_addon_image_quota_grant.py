"""add image_quota_grant columns to addon_definitions

Revision ID: 2026_03_10_addon_img_quota
Revises: 2026_03_10_plan_img_features
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_03_10_addon_img_quota"
down_revision = "2026_03_10_plan_img_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("addon_definitions") as batch_op:
        batch_op.add_column(sa.Column("image_quota_grant", sa.Integer(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("image_preview_quota_grant", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("addon_definitions") as batch_op:
        batch_op.drop_column("image_preview_quota_grant")
        batch_op.drop_column("image_quota_grant")
