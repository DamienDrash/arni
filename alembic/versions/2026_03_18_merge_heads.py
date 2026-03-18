"""Merge analytics_idempotency and optin_offers heads.

Revision ID: 2026_03_18_merge_heads
Revises: 2026_03_17_analytics_idempotency, 2026_03_18_optin_offers
Create Date: 2026-03-18
"""
from alembic import op

revision = "2026_03_18_merge_heads"
down_revision = ("2026_03_17_analytics_idempotency", "2026_03_18_optin_offers")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
