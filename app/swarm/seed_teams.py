"""app/swarm/seed_teams.py — Seed Agent Teams and Tool Definitions.

Seeds:
- AgentToolDefinition: core tools (knowledge_base, magicline, etc.)
- AgentTeamConfig + AgentTeamStep: campaign-generation, media-generation
- Exports initial YAML snapshots
"""

from __future__ import annotations

import json

import structlog
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# Bump this version whenever the system team definitions or builtin tools change.
# Tenants already seeded at this version are skipped on startup, keeping O(1)
# startup time regardless of how many tenants exist.
_SEED_VERSION = 1


def _is_seeded(db: Session, tenant_id: int) -> bool:
    """Return True if this tenant has already been seeded at the current _SEED_VERSION."""
    try:
        from app.core.models import Setting
        key = f"agent_teams_seed_v{_SEED_VERSION}"
        row = db.query(Setting).filter(
            Setting.tenant_id == tenant_id,
            Setting.key == key,
        ).first()
        return row is not None and row.value == "1"
    except Exception:
        return False


def _mark_seeded(db: Session, tenant_id: int) -> None:
    """Record that this tenant has been seeded at the current _SEED_VERSION."""
    try:
        from app.core.models import Setting
        key = f"agent_teams_seed_v{_SEED_VERSION}"
        existing = db.query(Setting).filter(
            Setting.tenant_id == tenant_id,
            Setting.key == key,
        ).first()
        if existing is None:
            db.add(Setting(tenant_id=tenant_id, key=key, value="1"))
            db.flush()
    except Exception as exc:
        logger.warning("seed_teams.mark_seeded_failed", tenant_id=tenant_id, error=str(exc))


def seed_teams(db: Session, tenant_id: int | None = None) -> None:
    """Idempotent seed of tools and system teams.

    If tenant_id is None (default), seeds system teams for ALL active tenants.
    Pass an explicit tenant_id to seed a single tenant (e.g. during onboarding).

    Uses a per-tenant seed version flag (stored in Settings) to skip tenants that
    have already been seeded, keeping startup time O(1) regardless of tenant count.
    """
    _seed_tools(db)

    if tenant_id is not None:
        if not _is_seeded(db, tenant_id):
            _seed_system_teams(db, tenant_id)
            _mark_seeded(db, tenant_id)
    else:
        # Seed for every active tenant that hasn't been seeded yet
        try:
            from app.core.models import Tenant
            tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
            seeded_count = 0
            for t in tenants:
                if not _is_seeded(db, t.id):
                    _seed_system_teams(db, t.id)
                    _mark_seeded(db, t.id)
                    seeded_count += 1
            if seeded_count:
                logger.info("seed_teams.tenants_seeded", count=seeded_count)
        except Exception as exc:
            logger.warning("seed_teams.tenant_scan_failed", error=str(exc))

    db.commit()
    logger.info("seed_teams.done", seed_version=_SEED_VERSION)


# ─── Tool Definitions ─────────────────────────────────────────────────────────

_BUILTIN_TOOLS = [
    {
        "slug": "knowledge_base",
        "name": "Knowledge Base Search",
        "description": "Searches the tenant's ChromaDB knowledge base for relevant documents.",
        "tool_class": "app.swarm.tools.knowledge_base.KnowledgeBaseTool",
    },
    {
        "slug": "magicline",
        "name": "Magicline API",
        "description": "Access Magicline fitness studio data: members, bookings, courses.",
        "tool_class": "app.swarm.tools.magicline.MagiclineTool",
    },
    {
        "slug": "member_memory",
        "name": "Member Memory",
        "description": "Read and update long-term memory for individual members.",
        "tool_class": "app.swarm.tools.member_memory.MemberMemoryTool",
    },
    {
        "slug": "calendly_booking",
        "name": "Calendly Booking",
        "description": "Create and manage Calendly booking links and appointments.",
        "tool_class": "app.swarm.tools.calendly_tools.CalendlyTool",
    },
    {
        "slug": "media_library",
        "name": "Media Library",
        "description": "Access and manage the tenant media library (images, videos).",
        "tool_class": "app.swarm.tools.media_library.MediaLibraryTool",
    },
    {
        "slug": "chat_history",
        "name": "Chat History",
        "description": "Retrieve recent conversation history for context-aware responses.",
        "tool_class": "app.swarm.tools.chat_history.ChatHistoryTool",
    },
    {
        "slug": "integration_context",
        "name": "Integration Context",
        "description": "Fetch live integration status and connection metadata.",
        "tool_class": "app.swarm.tools.integration_context.IntegrationContextTool",
    },
]


def _seed_tools(db: Session) -> None:
    from app.swarm.team_models import AgentToolDefinition

    for tool_data in _BUILTIN_TOOLS:
        # Global builtins have tenant_id=NULL — check by slug with no tenant filter
        existing = db.query(AgentToolDefinition).filter(
            AgentToolDefinition.tenant_id == None,
            AgentToolDefinition.slug == tool_data["slug"],
        ).first()
        if existing:
            continue
        tool = AgentToolDefinition(
            tenant_id=None,   # NULL = global builtin visible to all tenants
            slug=tool_data["slug"],
            name=tool_data["name"],
            description=tool_data["description"],
            tool_class=tool_data.get("tool_class"),
            is_builtin=True,
            is_active=True,
        )
        db.add(tool)

    db.flush()
    logger.info("seed_tools.done", count=len(_BUILTIN_TOOLS))


# ─── System Team Definitions ──────────────────────────────────────────────────

_SYSTEM_TEAMS = [
    {
        "slug": "campaign-generation",
        "name": "Campaign Generation",
        "description": "Generates marketing campaign content via MarketingAgent → DesignerAgent → QAAgent pipeline.",
        "execution_mode": "orchestrator",
        "lead_agent_slug": "marketing_agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_name": {"type": "string"},
                "channel": {"type": "string", "enum": ["email", "whatsapp", "sms"]},
                "tone": {"type": "string", "enum": ["professional", "friendly", "urgent"]},
                "prompt": {"type": "string"},
            },
            "required": ["campaign_name", "channel", "prompt"],
        },
        "steps": [
            {"step_order": 0, "agent_slug": "marketing_agent", "display_name": "Marketing Agent",
             "tools_json": json.dumps(["knowledge_base", "chat_history"])},
            {"step_order": 1, "agent_slug": "designer_agent", "display_name": "Designer Agent",
             "tools_json": json.dumps(["media_library"])},
            {"step_order": 2, "agent_slug": "qa_agent", "display_name": "QA Agent",
             "tools_json": json.dumps([])},
        ],
    },
    {
        "slug": "media-generation",
        "name": "Media Generation",
        "description": "Generates images and media assets via AnalysisAgent → PromptAgent → GenerationAgent → QAAgent.",
        "execution_mode": "orchestrator",
        "lead_agent_slug": "generation_agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "style": {"type": "string"},
                "aspect_ratio": {"type": "string"},
            },
            "required": ["prompt"],
        },
        "steps": [
            {"step_order": 0, "agent_slug": "analysis_agent", "display_name": "Analysis Agent",
             "tools_json": json.dumps([])},
            {"step_order": 1, "agent_slug": "prompt_agent", "display_name": "Prompt Agent",
             "tools_json": json.dumps(["knowledge_base"])},
            {"step_order": 2, "agent_slug": "generation_agent", "display_name": "Generation Agent",
             "tools_json": json.dumps(["media_library"])},
            {"step_order": 3, "agent_slug": "qa_agent", "display_name": "QA Agent",
             "tools_json": json.dumps([])},
        ],
    },
]


def _seed_system_teams(db: Session, tenant_id: int) -> None:
    from app.swarm.team_models import AgentTeamConfig, AgentTeamStep
    from app.swarm.team_yaml import export_team_yaml

    for team_data in _SYSTEM_TEAMS:
        existing = db.query(AgentTeamConfig).filter(
            AgentTeamConfig.tenant_id == tenant_id,
            AgentTeamConfig.slug == team_data["slug"],
        ).first()

        if existing:
            # Idempotent step update: refresh steps if count differs
            existing_steps = db.query(AgentTeamStep).filter(
                AgentTeamStep.team_id == existing.id
            ).all()
            expected_count = len(team_data.get("steps", []))
            if len(existing_steps) != expected_count:
                for old_step in existing_steps:
                    db.delete(old_step)
                db.flush()
                for s in team_data.get("steps", []):
                    step = AgentTeamStep(
                        team_id=existing.id,
                        step_order=s["step_order"],
                        agent_slug=s["agent_slug"],
                        display_name=s.get("display_name"),
                        tools_json=s.get("tools_json"),
                    )
                    db.add(step)
                db.flush()
                logger.info("seed_teams.steps_refreshed", slug=existing.slug)
            continue

        team = AgentTeamConfig(
            tenant_id=tenant_id,
            slug=team_data["slug"],
            name=team_data["name"],
            description=team_data.get("description"),
            execution_mode=team_data["execution_mode"],
            lead_agent_slug=team_data.get("lead_agent_slug"),
            input_schema_json=json.dumps(team_data["input_schema"]) if team_data.get("input_schema") else None,
            yaml_version=1,
            is_active=True,
            is_system=True,
        )
        db.add(team)
        db.flush()  # get team.id

        steps = []
        for s in team_data.get("steps", []):
            step = AgentTeamStep(
                team_id=team.id,
                step_order=s["step_order"],
                agent_slug=s["agent_slug"],
                display_name=s.get("display_name"),
                tools_json=s.get("tools_json"),
            )
            db.add(step)
            steps.append(step)

        db.flush()
        try:
            export_team_yaml(team, steps)
        except Exception as exc:
            logger.warning("seed_teams.yaml_export_failed", slug=team.slug, error=str(exc))

    logger.info("seed_system_teams.done")
