"""Add extended feature flags to plans table.

Revision ID: plan_feature_flags_001
Revises: member_multi_source_001
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa

revision = "plan_feature_flags_001"
down_revision = "member_multi_source_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New channel toggles
    op.add_column("plans", sa.Column("instagram_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("plans", sa.Column("facebook_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("plans", sa.Column("google_business_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    # New feature toggles
    op.add_column("plans", sa.Column("advanced_analytics_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("plans", sa.Column("branding_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("plans", sa.Column("audit_log_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("plans", sa.Column("automation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("plans", sa.Column("api_access_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("plans", sa.Column("multi_source_members_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    # Update Pro plan
    op.execute("""
        UPDATE plans SET
            instagram_enabled = 1,
            facebook_enabled = 1,
            google_business_enabled = 0,
            advanced_analytics_enabled = 1,
            branding_enabled = 1,
            audit_log_enabled = 1,
            automation_enabled = 0,
            api_access_enabled = 1,
            multi_source_members_enabled = 1
        WHERE slug = 'pro'
    """)

    # Update Enterprise plan
    op.execute("""
        UPDATE plans SET
            instagram_enabled = 1,
            facebook_enabled = 1,
            google_business_enabled = 1,
            advanced_analytics_enabled = 1,
            branding_enabled = 1,
            audit_log_enabled = 1,
            automation_enabled = 1,
            api_access_enabled = 1,
            multi_source_members_enabled = 1
        WHERE slug = 'enterprise'
    """)


def downgrade() -> None:
    op.drop_column("plans", "multi_source_members_enabled")
    op.drop_column("plans", "api_access_enabled")
    op.drop_column("plans", "automation_enabled")
    op.drop_column("plans", "audit_log_enabled")
    op.drop_column("plans", "branding_enabled")
    op.drop_column("plans", "advanced_analytics_enabled")
    op.drop_column("plans", "google_business_enabled")
    op.drop_column("plans", "facebook_enabled")
    op.drop_column("plans", "instagram_enabled")
