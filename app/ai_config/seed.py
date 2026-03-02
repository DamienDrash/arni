"""ARIIA AI Config – Seed Data.

Seeds the initial LLM providers, agent definitions, and prompt templates
from the existing Jinja2 template files. Safe to call multiple times.
"""

from __future__ import annotations
import json
import structlog
from pathlib import Path
from sqlalchemy.orm import Session

from app.ai_config.models import (
    LLMProvider, AgentDefinition, PromptTemplate, PromptVersion, PromptDeployment,
)
from app.ai_config.encryption import encrypt_api_key

logger = structlog.get_logger()

# ── Default LLM Providers ────────────────────────────────────────────────────

DEFAULT_PROVIDERS = [
    {
        "slug": "openai",
        "name": "OpenAI",
        "provider_type": "openai_compatible",
        "api_base_url": "https://api.openai.com/v1",
        "supported_models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "o3-mini"],
        "default_model": "gpt-4o-mini",
        "priority": 10,
    },
    {
        "slug": "anthropic",
        "name": "Anthropic",
        "provider_type": "openai_compatible",
        "api_base_url": "https://api.anthropic.com/v1",
        "supported_models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
        "default_model": "claude-sonnet-4-20250514",
        "priority": 20,
    },
    {
        "slug": "gemini",
        "name": "Google Gemini",
        "provider_type": "gemini",
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "supported_models": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
        "default_model": "gemini-2.5-flash",
        "priority": 30,
    },
    {
        "slug": "groq",
        "name": "Groq",
        "provider_type": "openai_compatible",
        "api_base_url": "https://api.groq.com/openai/v1",
        "supported_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "default_model": "llama-3.3-70b-versatile",
        "priority": 40,
    },
    {
        "slug": "mistral",
        "name": "Mistral AI",
        "provider_type": "openai_compatible",
        "api_base_url": "https://api.mistral.ai/v1",
        "supported_models": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
        "default_model": "mistral-large-latest",
        "priority": 50,
    },
    {
        "slug": "xai",
        "name": "xAI (Grok)",
        "provider_type": "openai_compatible",
        "api_base_url": "https://api.x.ai/v1",
        "supported_models": ["grok-2", "grok-2-mini"],
        "default_model": "grok-2",
        "priority": 60,
    },
]

# ── Default Agent Definitions ─────────────────────────────────────────────────

DEFAULT_AGENTS = [
    {
        "slug": "persona",
        "name": "Persona & Smalltalk Agent",
        "description": "Handles greetings, chitchat, and general questions using SOUL.md persona.",
        "agent_class": "app.swarm.agents.persona.AgentPersona",
        "default_model": "gpt-4o-mini",
        "default_temperature": 0.7,
        "default_max_tokens": 500,
        "default_tools": ["knowledge_base", "member_memory"],
        "prompt_template_slug": "persona/system",
    },
    {
        "slug": "sales",
        "name": "Sales & Retention Agent",
        "description": "Handles cancellations, renewals, upgrades, pricing. Retention-focused.",
        "agent_class": "app.swarm.agents.sales.AgentSales",
        "default_model": "gpt-4o-mini",
        "default_temperature": 0.7,
        "default_max_tokens": 1000,
        "default_tools": ["knowledge_base", "magicline", "member_memory"],
        "prompt_template_slug": "sales/system",
    },
    {
        "slug": "ops",
        "name": "Operations & Scheduling Agent",
        "description": "Handles bookings, schedules, check-ins. One-Way-Door: Cancellations require confirmation.",
        "agent_class": "app.swarm.agents.ops.AgentOps",
        "default_model": "gpt-4o-mini",
        "default_temperature": 0.3,
        "default_max_tokens": 1000,
        "default_tools": ["knowledge_base", "magicline", "member_memory"],
        "prompt_template_slug": "ops/system",
    },
    {
        "slug": "medic",
        "name": "Health & Wellness Agent",
        "description": "Handles health, nutrition, and fitness questions with medical disclaimers.",
        "agent_class": "app.swarm.agents.medic.AgentMedic",
        "default_model": "gpt-4o-mini",
        "default_temperature": 0.5,
        "default_max_tokens": 800,
        "default_tools": ["knowledge_base", "member_memory"],
        "prompt_template_slug": "medic/system",
    },
    {
        "slug": "router",
        "name": "Intent Router",
        "description": "Classifies user intent and routes to the appropriate specialist agent.",
        "agent_class": "app.swarm.router.router.IntentRouter",
        "default_model": "gpt-4o-mini",
        "default_temperature": 0.1,
        "default_max_tokens": 200,
        "default_tools": [],
        "prompt_template_slug": "router/system",
    },
    {
        "slug": "vision",
        "name": "Vision & Crowd Counting Agent",
        "description": "Crowd counting via YOLOv8 on RTSP streams.",
        "agent_class": "app.swarm.agents.vision.AgentVision",
        "default_model": "gpt-4o-mini",
        "default_temperature": 0.3,
        "default_max_tokens": 500,
        "default_tools": [],
        "prompt_template_slug": None,
        "is_visible_to_tenants": False,
    },
]

# ── Prompt Template Base Path ─────────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "prompts" / "templates"


def seed_ai_config(db: Session) -> None:
    """Seed all AI configuration tables. Safe to call multiple times."""
    _seed_providers(db)
    _seed_agents(db)
    _seed_prompts(db)
    db.commit()
    logger.info("ai_config.seed.complete")


def _seed_providers(db: Session) -> None:
    """Seed default LLM providers."""
    for pdata in DEFAULT_PROVIDERS:
        existing = db.query(LLMProvider).filter(LLMProvider.slug == pdata["slug"]).first()
        if existing:
            continue

        provider = LLMProvider(
            slug=pdata["slug"],
            name=pdata["name"],
            provider_type=pdata["provider_type"],
            api_base_url=pdata["api_base_url"],
            supported_models_json=json.dumps(pdata["supported_models"]),
            default_model=pdata["default_model"],
            priority=pdata["priority"],
            is_active=True,
        )
        db.add(provider)
        logger.info("ai_config.seed.provider", slug=pdata["slug"])

    db.flush()


def _seed_agents(db: Session) -> None:
    """Seed default agent definitions."""
    for adata in DEFAULT_AGENTS:
        existing = db.query(AgentDefinition).filter(AgentDefinition.slug == adata["slug"]).first()
        if existing:
            continue

        agent = AgentDefinition(
            slug=adata["slug"],
            name=adata["name"],
            description=adata.get("description"),
            agent_class=adata["agent_class"],
            default_model=adata.get("default_model", "gpt-4o-mini"),
            default_temperature=adata.get("default_temperature", 0.7),
            default_max_tokens=adata.get("default_max_tokens", 1000),
            default_tools_json=json.dumps(adata.get("default_tools", [])),
            prompt_template_slug=adata.get("prompt_template_slug"),
            is_active=True,
            is_visible_to_tenants=adata.get("is_visible_to_tenants", True),
        )
        db.add(agent)
        logger.info("ai_config.seed.agent", slug=adata["slug"])

    db.flush()


def _seed_prompts(db: Session) -> None:
    """Seed prompt templates from existing Jinja2 files."""
    template_files = {
        "persona/system": ("Persona System Prompt", "persona"),
        "sales/system": ("Sales Agent System Prompt", "sales"),
        "ops/system": ("Operations Agent System Prompt", "ops"),
        "medic/system": ("Health Agent System Prompt", "medic"),
        "router/system": ("Intent Router System Prompt", "router"),
    }

    for slug, (name, agent_type) in template_files.items():
        existing = db.query(PromptTemplate).filter(PromptTemplate.slug == slug).first()
        if existing:
            continue

        # Read the Jinja2 template file
        j2_path = _TEMPLATE_DIR / f"{agent_type}" / "system.j2"
        content = ""
        if j2_path.exists():
            try:
                content = j2_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("ai_config.seed.prompt_read_failed", path=str(j2_path), error=str(e))
                content = f"# {name}\n\nTemplate content not available."

        # Create template
        template = PromptTemplate(
            slug=slug,
            name=name,
            category="agent",
            agent_type=agent_type,
            is_active=True,
        )
        db.add(template)
        db.flush()

        # Create initial version (v1.0.0)
        version = PromptVersion(
            template_id=template.id,
            version="1.0.0",
            content=content,
            change_notes="Initial version migrated from Jinja2 template files.",
            created_by="system",
            status="published",
        )
        db.add(version)
        db.flush()

        # Auto-deploy to production
        deployment = PromptDeployment(
            version_id=version.id,
            environment="production",
            tenant_id=None,  # Platform default
            is_active=True,
            deployed_by="system",
        )
        db.add(deployment)

        logger.info("ai_config.seed.prompt", slug=slug, version="1.0.0")

    db.flush()
