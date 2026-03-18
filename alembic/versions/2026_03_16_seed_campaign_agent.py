"""feat(swarm): seed campaign agent and tools.

Revision ID: 2026_03_16_seed_campaign_agent
Revises: 2026_03_16_seed_swarm
Create Date: 2026-03-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "2026_03_16_seed_campaign_agent"
down_revision = "2026_03_16_seed_swarm"
branch_labels = None
depends_on = None

NOW = datetime.now(timezone.utc)

CAMPAIGN_TOOLS = [
    {
        "id": "campaign_composer",
        "display_name": "Campaign Composer",
        "description": "KI-gestützte Erstellung von Kampagnen-Texten (WhatsApp, SMS, E-Mail).",
        "category": "campaigns",
        "required_integration": None,
        "min_plan_tier": "pro",
        "is_system": True,
    },
    {
        "id": "campaign_scheduler",
        "display_name": "Campaign Scheduler",
        "description": "Optimale Versandzeit-Empfehlungen und Kampagnen-Planung.",
        "category": "campaigns",
        "required_integration": None,
        "min_plan_tier": "pro",
        "is_system": True,
    },
]

CAMPAIGN_AGENT = {
    "id": "campaign",
    "display_name": "Campaign Agent",
    "description": "Erstellt, plant und optimiert Marketing-Kampagnen für Fitnessstudios.",
    "system_prompt": None,
    "default_tools": '["campaign_composer", "campaign_scheduler"]',
    "max_turns": 6,
    "qa_profile": "standard",
    "min_plan_tier": "pro",
    "is_system": True,
}


def upgrade() -> None:
    conn = op.get_bind()

    tool_table = sa.table(
        "tool_definitions",
        sa.column("id", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("required_integration", sa.String),
        sa.column("min_plan_tier", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    agent_table = sa.table(
        "agent_definitions",
        sa.column("id", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("system_prompt", sa.Text),
        sa.column("default_tools", sa.Text),
        sa.column("max_turns", sa.Integer),
        sa.column("qa_profile", sa.String),
        sa.column("min_plan_tier", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    for tool in CAMPAIGN_TOOLS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM tool_definitions WHERE id = :id"),
            {"id": tool["id"]},
        ).fetchone()
        if not exists:
            conn.execute(tool_table.insert().values(**tool, created_at=NOW))

    exists = conn.execute(
        sa.text("SELECT 1 FROM agent_definitions WHERE id = :id"),
        {"id": CAMPAIGN_AGENT["id"]},
    ).fetchone()
    if not exists:
        conn.execute(agent_table.insert().values(**CAMPAIGN_AGENT, created_at=NOW))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM agent_definitions WHERE id = 'campaign'"))
    conn.execute(
        sa.text(
            "DELETE FROM tool_definitions WHERE id IN ('campaign_composer', 'campaign_scheduler')"
        )
    )
