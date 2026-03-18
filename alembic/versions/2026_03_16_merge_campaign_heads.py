"""merge: contact_consents + seed_campaign_agent heads.

Revision ID: 2026_03_16_merge_campaign_heads
Revises: 2026_03_16_contact_consents, 2026_03_16_seed_campaign_agent
Create Date: 2026-03-16
"""
from __future__ import annotations

revision = "2026_03_16_merge_campaign_heads"
down_revision = ("2026_03_16_contact_consents", "2026_03_16_seed_campaign_agent")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
