"""Swarm v3 — TenantToolRegistry with 3-Gate Permission System.

Resolves which tools an agent may use for a given tenant by checking:
  Gate 1: Plan tier — tool.min_plan_tier <= tenant plan tier
  Gate 2: Integration — required_integration available in tenant context
  Gate 3: Tenant config — TenantToolConfig.is_enabled (DB override)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Type

from app.swarm.contracts import TenantContext
from app.swarm.tools.base import SkillTool

logger = logging.getLogger(__name__)

# ── Plan tier hierarchy (higher value = more features) ───────────────────────

PLAN_TIER: dict[str, int] = {
    "starter": 0,
    "pro": 1,
    "enterprise": 2,
}

# ── Default tool assignments per agent ───────────────────────────────────────

AGENT_TOOL_MAP: dict[str, list[str]] = {
    "ops": [
        "magicline_booking", "magicline_member", "magicline_checkin",
        "magicline_employee", "magicline_contract", "calendly_schedule",
    ],
    "sales": ["magicline_contract", "magicline_member", "magicline_booking", "member_memory"],
    "medic": ["member_memory", "knowledge_search"],
    "vision": ["knowledge_search"],
    "persona": ["member_memory", "knowledge_search"],
    "knowledge": ["knowledge_search"],
    "campaign": ["member_memory", "knowledge_search"],
    "media": ["knowledge_search"],
}

# ── Tool catalogue: maps tool_id → SkillTool class ──────────────────────────
# Populated at import time via register_tool() or by seed scripts.

TOOL_CATALOGUE: dict[str, Type[SkillTool]] = {}


def register_tool(tool_cls: Type[SkillTool]) -> Type[SkillTool]:
    """Decorator / helper to register a SkillTool class in the catalogue."""
    TOOL_CATALOGUE[tool_cls.name] = tool_cls
    return tool_cls


# ── Registry ─────────────────────────────────────────────────────────────────

class TenantToolRegistry:
    """Resolves permitted tools for an agent within a tenant context.

    Uses a 3-gate permission check:
      1. Plan tier gate
      2. Integration availability gate
      3. Tenant-level enable/disable gate (from DB)
    """

    def __init__(self, tenant_tool_configs: dict[str, dict[str, Any]] | None = None):
        """
        Args:
            tenant_tool_configs: Pre-loaded mapping of tool_id → config dict
                from TenantToolConfig rows. Expected shape:
                {"tool_id": {"is_enabled": bool, "config": dict}}
                Pass None to skip Gate 3 (all tools allowed by default).
        """
        self._tool_configs = tenant_tool_configs or {}

    # ── Public API ───────────────────────────────────────────────────────

    def get_tools_for_agent(
        self,
        agent_id: str,
        context: TenantContext,
        tool_overrides: list[str] | None = None,
    ) -> list[SkillTool]:
        """Return instantiated SkillTool list for the given agent + tenant.

        Args:
            agent_id: The agent requesting tools (e.g. "ops").
            context: Immutable tenant context with plan_slug and integrations.
            tool_overrides: If provided, replaces the default tool list for the agent.

        Returns:
            List of SkillTool instances that passed all three gates.
        """
        tool_ids = tool_overrides if tool_overrides is not None else AGENT_TOOL_MAP.get(agent_id, [])
        tenant_tier = PLAN_TIER.get(context.plan_slug, 0)

        tools: list[SkillTool] = []
        for tool_id in tool_ids:
            tool_cls = TOOL_CATALOGUE.get(tool_id)
            if tool_cls is None:
                logger.debug("tool_not_in_catalogue", tool_id=tool_id)
                continue

            # Gate 1: Plan tier
            tool_tier = PLAN_TIER.get(getattr(tool_cls, "min_plan_tier", "starter"), 0)
            if tenant_tier < tool_tier:
                logger.debug("tool_blocked_plan_tier", tool_id=tool_id, required=tool_tier, tenant=tenant_tier)
                continue

            # Gate 2: Required integration
            required = getattr(tool_cls, "required_integrations", frozenset())
            if required and not required.issubset(context.active_integrations):
                missing = required - context.active_integrations
                logger.debug("tool_blocked_integration", tool_id=tool_id, missing=missing)
                continue

            # Gate 3: Tenant config
            cfg = self._tool_configs.get(tool_id)
            if cfg is not None and not cfg.get("is_enabled", True):
                logger.debug("tool_disabled_by_tenant", tool_id=tool_id)
                continue

            # Instantiate with tenant config if available
            tool_instance = tool_cls()
            tools.append(tool_instance)

        return tools

    def get_openai_schemas(
        self,
        agent_id: str,
        context: TenantContext,
        tool_overrides: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return OpenAI function-calling schemas for permitted tools."""
        return [t.to_openai_schema() for t in self.get_tools_for_agent(agent_id, context, tool_overrides)]

    @classmethod
    def from_db_rows(cls, rows: list[Any]) -> TenantToolRegistry:
        """Build registry from TenantToolConfig ORM rows.

        Args:
            rows: List of TenantToolConfig objects with tool_id, is_enabled, config attrs.
        """
        configs: dict[str, dict[str, Any]] = {}
        for row in rows:
            tool_config = {}
            if hasattr(row, "config") and row.config:
                try:
                    tool_config = json.loads(row.config) if isinstance(row.config, str) else row.config
                except (json.JSONDecodeError, TypeError):
                    tool_config = {}
            configs[row.tool_id] = {
                "is_enabled": row.is_enabled,
                "config": tool_config,
            }
        return cls(tenant_tool_configs=configs)


# ── Auto-register all built-in SkillTool classes ─────────────────────────────

def _register_builtin_tools() -> None:
    """Import and register all built-in SkillTool classes."""
    from app.swarm.tools.magicline_booking import MagiclineBookingTool
    from app.swarm.tools.magicline_member import MagiclineMemberTool
    from app.swarm.tools.magicline_checkin import MagiclineCheckinTool
    from app.swarm.tools.magicline_employee import MagiclineEmployeeTool
    from app.swarm.tools.calendly_tool import CalendlyTool
    from app.swarm.tools.knowledge_search_tool import KnowledgeSearchTool
    from app.swarm.tools.member_memory_tool import MemberMemoryTool
    from app.swarm.tools.odoo import OdooTool
    from app.swarm.tools.social_media_composer import SocialMediaComposerTool
    from app.swarm.tools.social_media_scheduler import SocialMediaSchedulerTool
    from app.swarm.tools.social_media_publisher import SocialMediaPublisherTool

    for cls in [
        MagiclineBookingTool,
        MagiclineMemberTool,
        MagiclineCheckinTool,
        MagiclineEmployeeTool,
        CalendlyTool,
        KnowledgeSearchTool,
        MemberMemoryTool,
        OdooTool,
        SocialMediaComposerTool,
        SocialMediaSchedulerTool,
        SocialMediaPublisherTool,
    ]:
        register_tool(cls)


try:
    _register_builtin_tools()
except Exception:
    # Deferred registration — tools will be available when their deps are loaded
    pass
