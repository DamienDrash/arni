"""ARIIA Swarm v3 — System Seed Data.

Idempotent upsert of the 8 built-in agents and their tools.
Called from run_migrations() in app/core/db.py.
"""

from __future__ import annotations

import json
import structlog
from sqlalchemy.orm import Session

from app.core.models import AgentDefinition, ToolDefinition

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Tool definitions (system built-ins)
# ---------------------------------------------------------------------------
SYSTEM_TOOLS: list[dict] = [
    {
        "id": "magicline_booking",
        "display_name": "Magicline Booking",
        "description": "Manage bookings: class schedules, appointment slots, book/cancel/reschedule.",
        "category": "booking",
        "required_integration": "magicline",
        "min_plan_tier": "starter",
    },
    {
        "id": "magicline_member",
        "display_name": "Magicline Member",
        "description": "Member info: status, bookings list, check-in statistics.",
        "category": "crm",
        "required_integration": "magicline",
        "min_plan_tier": "starter",
    },
    {
        "id": "magicline_checkin",
        "display_name": "Magicline Check-in",
        "description": "Retrieve check-in history for gym members.",
        "category": "crm",
        "required_integration": "magicline",
        "min_plan_tier": "starter",
    },
    {
        "id": "calendly",
        "display_name": "Calendly",
        "description": "Schedule and manage Calendly appointments.",
        "category": "booking",
        "required_integration": "calendly",
        "min_plan_tier": "pro",
    },
    {
        "id": "knowledge_search",
        "display_name": "Knowledge Base Search",
        "description": "Search tenant knowledge base (ChromaDB) for contextual answers.",
        "category": "knowledge",
        "required_integration": None,
        "min_plan_tier": "starter",
    },
    {
        "id": "member_memory",
        "display_name": "Member Memory",
        "description": "Store and retrieve per-member conversation memory and preferences.",
        "category": "memory",
        "required_integration": None,
        "min_plan_tier": "starter",
    },
]

# ---------------------------------------------------------------------------
# Agent definitions (system built-ins)
# ---------------------------------------------------------------------------
SYSTEM_AGENTS: list[dict] = [
    {
        "id": "ops",
        "display_name": "Operations Agent",
        "description": "Handles bookings, scheduling, cancellations, and reschedules via Magicline.",
        "default_tools": json.dumps(["magicline_booking", "magicline_member", "calendly"]),
        "max_turns": 5,
        "qa_profile": "standard",
        "min_plan_tier": "starter",
    },
    {
        "id": "sales",
        "display_name": "Sales & Retention Agent",
        "description": "Retention flows, churn prevention, upselling, and member engagement.",
        "default_tools": json.dumps(["magicline_member", "magicline_checkin", "member_memory"]),
        "max_turns": 5,
        "qa_profile": "standard",
        "min_plan_tier": "starter",
    },
    {
        "id": "medic",
        "display_name": "Health & Safety Agent",
        "description": "Health advice with mandatory legal disclaimer. Emergency keywords bypass classification.",
        "default_tools": json.dumps(["knowledge_search", "member_memory"]),
        "max_turns": 3,
        "qa_profile": "strict",
        "min_plan_tier": "starter",
    },
    {
        "id": "vision",
        "display_name": "Vision Agent",
        "description": "Image analysis for exercise form checking and equipment identification.",
        "default_tools": json.dumps(["knowledge_search"]),
        "max_turns": 3,
        "qa_profile": "standard",
        "min_plan_tier": "pro",
    },
    {
        "id": "persona",
        "display_name": "Persona Agent",
        "description": "Free-form conversational agent with studio personality and knowledge base.",
        "default_tools": json.dumps(["knowledge_search", "member_memory"]),
        "max_turns": 5,
        "qa_profile": "standard",
        "min_plan_tier": "starter",
    },
    {
        "id": "knowledge",
        "display_name": "Knowledge Agent",
        "description": "Answers questions from tenant knowledge base (opening hours, pricing, FAQs).",
        "default_tools": json.dumps(["knowledge_search"]),
        "max_turns": 3,
        "qa_profile": "standard",
        "min_plan_tier": "starter",
    },
    {
        "id": "campaign",
        "display_name": "Campaign Agent",
        "description": "Marketing campaign creation and management (design, copy, QA).",
        "default_tools": json.dumps(["knowledge_search"]),
        "max_turns": 8,
        "qa_profile": "standard",
        "min_plan_tier": "pro",
    },
    {
        "id": "media",
        "display_name": "Media Agent",
        "description": "Social media content generation, analysis, and publishing.",
        "default_tools": json.dumps(["knowledge_search"]),
        "max_turns": 8,
        "qa_profile": "standard",
        "min_plan_tier": "pro",
    },
]


def seed_system_agents_and_tools(db: Session) -> None:
    """Idempotent upsert of all system agents and tools.

    Existing rows are updated in-place; missing rows are inserted.
    """
    # -- Tools --
    for tool_data in SYSTEM_TOOLS:
        existing = db.query(ToolDefinition).filter_by(id=tool_data["id"]).first()
        if existing:
            for key, value in tool_data.items():
                if key != "id":
                    setattr(existing, key, value)
            existing.is_system = True
        else:
            db.add(ToolDefinition(**tool_data, is_system=True))

    # -- Agents --
    for agent_data in SYSTEM_AGENTS:
        existing = db.query(AgentDefinition).filter_by(id=agent_data["id"]).first()
        if existing:
            for key, value in agent_data.items():
                if key != "id":
                    setattr(existing, key, value)
            existing.is_system = True
        else:
            db.add(AgentDefinition(**agent_data, is_system=True))

    db.commit()
    logger.info("swarm.seed.completed", tools=len(SYSTEM_TOOLS), agents=len(SYSTEM_AGENTS))
