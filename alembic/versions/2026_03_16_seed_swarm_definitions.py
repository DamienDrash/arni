"""feat(swarm-v3): seed system agent and tool definitions.

Revision ID: 2026_03_16_seed_swarm
Revises: 2026_03_16_swarm_v3
Create Date: 2026-03-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "2026_03_16_seed_swarm"
down_revision = "2026_03_16_swarm_v3"
branch_labels = None
depends_on = None

NOW = datetime.now(timezone.utc)


TOOL_DEFINITIONS = [
    {
        "id": "magicline_booking",
        "display_name": "Magicline Booking",
        "description": "Kursstunden und Termine über Magicline buchen, stornieren und abfragen.",
        "category": "crm",
        "required_integration": "magicline",
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "magicline_checkin",
        "display_name": "Magicline Check-in",
        "description": "Member Check-in Status und Anwesenheit über Magicline verwalten.",
        "category": "crm",
        "required_integration": "magicline",
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "magicline_member",
        "display_name": "Magicline Member",
        "description": "Mitgliederdaten aus Magicline abrufen und aktualisieren.",
        "category": "crm",
        "required_integration": "magicline",
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "knowledge_search",
        "display_name": "Knowledge Search",
        "description": "Semantic Search in der Wissensdatenbank des Tenants (ChromaDB).",
        "category": "knowledge",
        "required_integration": None,
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "member_memory",
        "display_name": "Member Memory",
        "description": "Langzeit-Gedächtnis für Mitglieder – Präferenzen und Gesprächshistorie.",
        "category": "memory",
        "required_integration": None,
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "calendly",
        "display_name": "Calendly Scheduling",
        "description": "Termine über Calendly planen und verwalten.",
        "category": "scheduling",
        "required_integration": "calendly",
        "min_plan_tier": "pro",
        "is_system": True,
    },
    {
        "id": "odoo",
        "display_name": "Odoo ERP",
        "description": "Odoo ERP-Integration: Kontakte, Aufgaben und Verkaufschancen.",
        "category": "erp",
        "required_integration": "odoo",
        "min_plan_tier": "enterprise",
        "is_system": True,
    },
    {
        "id": "social_media_composer",
        "display_name": "Social Media Composer",
        "description": "KI-gestützte Erstellung von Social-Media-Posts (Text + Bild-Prompt).",
        "category": "social_media",
        "required_integration": None,
        "min_plan_tier": "pro",
        "is_system": True,
    },
    {
        "id": "social_media_scheduler",
        "display_name": "Social Media Scheduler",
        "description": "Geplante Veröffentlichung von Social-Media-Posts mit Kalender-Integration.",
        "category": "social_media",
        "required_integration": None,
        "min_plan_tier": "pro",
        "is_system": True,
    },
    {
        "id": "social_media_publisher",
        "display_name": "Social Media Publisher",
        "description": "Direktes Veröffentlichen auf Instagram, Facebook und weiteren Kanälen.",
        "category": "social_media",
        "required_integration": "social_media",
        "min_plan_tier": "pro",
        "is_system": True,
    },
]

AGENT_DEFINITIONS = [
    {
        "id": "ops",
        "display_name": "Ops Agent",
        "description": "Buchungen, Kurspläne, Check-ins und operative Mitgliederfragen.",
        "system_prompt": None,
        "default_tools": '["magicline_booking", "magicline_checkin", "magicline_member"]',
        "max_turns": 5,
        "qa_profile": "standard",
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "sales",
        "display_name": "Sales Agent",
        "description": "Retention, Upselling, Vertragsangebote und Kündigungs-Gegenmaßnahmen.",
        "system_prompt": None,
        "default_tools": '["magicline_member", "member_memory"]',
        "max_turns": 6,
        "qa_profile": "strict",
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "medic",
        "display_name": "Medic Agent",
        "description": "Gesundheitsfragen, Notfälle, medizinische Disclamer (112-Fallback).",
        "system_prompt": None,
        "default_tools": '["member_memory", "knowledge_search"]',
        "max_turns": 4,
        "qa_profile": "strict",
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "vision",
        "display_name": "Vision Agent",
        "description": "Bildanalyse und visuelle Auswertung (YOLOv8 oder Stub-Modus).",
        "system_prompt": None,
        "default_tools": '["knowledge_search"]',
        "max_turns": 3,
        "qa_profile": "standard",
        "min_plan_tier": "pro",
        "is_system": True,
    },
    {
        "id": "persona",
        "display_name": "Persona Agent",
        "description": "Allgemeine Konversation, Small Talk und Markenpersönlichkeit.",
        "system_prompt": None,
        "default_tools": '["member_memory", "knowledge_search"]',
        "max_turns": 5,
        "qa_profile": "standard",
        "min_plan_tier": "starter",
        "is_system": True,
    },
    {
        "id": "social_media",
        "display_name": "Social Media Agent",
        "description": "Erstellt, plant und veröffentlicht Social-Media-Posts für Fitnessstudios.",
        "system_prompt": None,
        "default_tools": '["social_media_composer", "social_media_scheduler", "social_media_publisher"]',
        "max_turns": 6,
        "qa_profile": "standard",
        "min_plan_tier": "pro",
        "is_system": True,
    },
]


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

    # Upsert tools
    for tool in TOOL_DEFINITIONS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM tool_definitions WHERE id = :id"),
            {"id": tool["id"]},
        ).fetchone()
        if not exists:
            conn.execute(
                tool_table.insert().values(
                    id=tool["id"],
                    display_name=tool["display_name"],
                    description=tool["description"],
                    category=tool["category"],
                    required_integration=tool["required_integration"],
                    min_plan_tier=tool["min_plan_tier"],
                    is_system=tool["is_system"],
                    created_at=NOW,
                )
            )

    # Upsert agents
    for agent in AGENT_DEFINITIONS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM agent_definitions WHERE id = :id"),
            {"id": agent["id"]},
        ).fetchone()
        if not exists:
            conn.execute(
                agent_table.insert().values(
                    id=agent["id"],
                    display_name=agent["display_name"],
                    description=agent["description"],
                    system_prompt=agent["system_prompt"],
                    default_tools=agent["default_tools"],
                    max_turns=agent["max_turns"],
                    qa_profile=agent["qa_profile"],
                    min_plan_tier=agent["min_plan_tier"],
                    is_system=agent["is_system"],
                    created_at=NOW,
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    ids = [a["id"] for a in AGENT_DEFINITIONS]
    conn.execute(sa.text(f"DELETE FROM agent_definitions WHERE id IN ({','.join([repr(i) for i in ids])})"))
    ids = [t["id"] for t in TOOL_DEFINITIONS]
    conn.execute(sa.text(f"DELETE FROM tool_definitions WHERE id IN ({','.join([repr(i) for i in ids])})"))
