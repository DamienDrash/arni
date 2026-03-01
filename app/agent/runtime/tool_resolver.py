"""ARIIA v2.0 – Dynamic Tool Resolver.

@ARCH: Phase 2, Meilenstein 2.2 – Integration & Skills
Resolves the available tools/capabilities for a tenant at runtime by:
  1. Loading the tenant's activated integrations from the DB
  2. Loading the associated CapabilityDefinition schemas from the Registry
  3. Loading the corresponding *.SKILL.md files from the filesystem
  4. Combining everything into a format injectable into the agent's system prompt

This is the bridge between the Integration Registry (static catalog) and
the Agent Runtime (dynamic execution). It ensures that each tenant's agent
only sees the tools/capabilities that are actually activated and configured.

Design Principles:
  - Results are cached per tenant with a short TTL to avoid DB hits on every message
  - Skill files are loaded lazily and cached
  - The resolver is integration-agnostic; it works with any adapter
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.integration_models import (
    CapabilityDefinition,
    IntegrationCapability,
    IntegrationDefinition,
    IntegrationStatus,
    TenantIntegration,
)
from app.core.tenant_context import TenantContext

logger = structlog.get_logger()

# Base directory for skill files
SKILLS_BASE_DIR = os.environ.get(
    "ARIIA_SKILLS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "skills"),
)


@dataclass
class ResolvedCapability:
    """A single resolved capability ready for agent consumption."""
    capability_id: str
    name: str
    description: str
    input_schema: dict
    output_schema: Optional[dict]
    is_destructive: bool
    integration_id: str
    adapter_class: str

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.capability_id.replace(".", "_"),
                "description": self.description,
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


@dataclass
class ResolvedIntegration:
    """A fully resolved integration with its capabilities and skill content."""
    integration_id: str
    name: str
    category: str
    adapter_class: str
    skill_content: Optional[str]
    capabilities: list[ResolvedCapability] = field(default_factory=list)


@dataclass
class TenantToolSet:
    """The complete set of tools available to a tenant's agent."""
    tenant_id: int
    integrations: list[ResolvedIntegration] = field(default_factory=list)
    resolved_at: float = field(default_factory=time.monotonic)

    @property
    def all_capabilities(self) -> list[ResolvedCapability]:
        """Flat list of all capabilities across all integrations."""
        return [cap for integ in self.integrations for cap in integ.capabilities]

    @property
    def openai_tools(self) -> list[dict]:
        """All capabilities as OpenAI function-calling tool schemas."""
        return [cap.to_openai_tool() for cap in self.all_capabilities]

    @property
    def skill_prompt_section(self) -> str:
        """Combined skill content for injection into the system prompt."""
        sections = []
        for integ in self.integrations:
            if integ.skill_content:
                sections.append(integ.skill_content)
        return "\n\n---\n\n".join(sections) if sections else ""

    @property
    def capability_map(self) -> dict[str, ResolvedCapability]:
        """Map of capability_id → ResolvedCapability for quick lookup."""
        return {cap.capability_id: cap for cap in self.all_capabilities}


# ─── Skill File Cache ────────────────────────────────────────────────────────

_skill_cache: dict[str, tuple[str, float]] = {}
_SKILL_CACHE_TTL = 300.0  # 5 minutes


def _load_skill_file(skill_path: Optional[str]) -> Optional[str]:
    """Load a skill file from disk with caching."""
    if not skill_path:
        return None

    now = time.monotonic()
    if skill_path in _skill_cache:
        content, cached_at = _skill_cache[skill_path]
        if now - cached_at < _SKILL_CACHE_TTL:
            return content

    # Try absolute path first, then relative to SKILLS_BASE_DIR
    full_path = skill_path if os.path.isabs(skill_path) else os.path.join(SKILLS_BASE_DIR, skill_path)

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        _skill_cache[skill_path] = (content, now)
        logger.debug("skill_file.loaded", path=full_path, size=len(content))
        return content
    except FileNotFoundError:
        logger.warning("skill_file.not_found", path=full_path)
        return None
    except Exception as e:
        logger.error("skill_file.load_error", path=full_path, error=str(e))
        return None


# ─── Resolver Cache ──────────────────────────────────────────────────────────

_resolver_cache: dict[int, TenantToolSet] = {}
_RESOLVER_CACHE_TTL = 120.0  # 2 minutes


def invalidate_tenant_cache(tenant_id: int) -> None:
    """Invalidate the resolver cache for a specific tenant.

    Call this when a tenant's integrations are changed (activated/deactivated).
    """
    _resolver_cache.pop(tenant_id, None)
    logger.debug("tool_resolver.cache_invalidated", tenant_id=tenant_id)


def invalidate_all_caches() -> None:
    """Invalidate all resolver caches (e.g., after a global registry update)."""
    _resolver_cache.clear()
    _skill_cache.clear()
    logger.info("tool_resolver.all_caches_invalidated")


# ─── Dynamic Tool Resolver ───────────────────────────────────────────────────


class DynamicToolResolver:
    """Resolves the available tools for a tenant at runtime.

    Usage:
        resolver = DynamicToolResolver(db_session)
        tool_set = resolver.resolve(tenant_context)

        # Inject into agent
        system_prompt += tool_set.skill_prompt_section
        tools = tool_set.openai_tools
    """

    def __init__(self, db: Session):
        self._db = db

    def resolve(self, tenant_context: TenantContext) -> TenantToolSet:
        """Resolve all active integrations and capabilities for a tenant.

        Args:
            tenant_context: The current tenant context.

        Returns:
            TenantToolSet with all resolved integrations, capabilities, and skills.
        """
        tenant_id = tenant_context.tenant_id
        now = time.monotonic()

        # Check cache
        if tenant_id in _resolver_cache:
            cached = _resolver_cache[tenant_id]
            if now - cached.resolved_at < _RESOLVER_CACHE_TTL:
                logger.debug("tool_resolver.cache_hit", tenant_id=tenant_id)
                return cached

        # Load active integrations for this tenant
        active_integrations = self._db.execute(
            select(TenantIntegration)
            .where(TenantIntegration.tenant_id == tenant_id)
            .where(TenantIntegration.enabled == True)
            .where(TenantIntegration.status.in_([
                IntegrationStatus.ACTIVE.value,
                IntegrationStatus.PENDING_SETUP.value,
            ]))
        ).scalars().all()

        if not active_integrations:
            logger.debug("tool_resolver.no_active_integrations", tenant_id=tenant_id)
            tool_set = TenantToolSet(tenant_id=tenant_id)
            _resolver_cache[tenant_id] = tool_set
            return tool_set

        resolved_integrations = []

        for ti in active_integrations:
            # Load integration definition
            integ_def = self._db.get(IntegrationDefinition, ti.integration_id)
            if not integ_def or not integ_def.is_active:
                continue

            # Load capabilities for this integration
            cap_links = self._db.execute(
                select(IntegrationCapability)
                .where(IntegrationCapability.integration_id == ti.integration_id)
            ).scalars().all()

            resolved_caps = []
            for link in cap_links:
                cap_def = self._db.get(CapabilityDefinition, link.capability_id)
                if not cap_def:
                    continue

                resolved_caps.append(ResolvedCapability(
                    capability_id=cap_def.id,
                    name=cap_def.name,
                    description=cap_def.description or cap_def.name,
                    input_schema=cap_def.input_schema or {"type": "object", "properties": {}},
                    output_schema=cap_def.output_schema,
                    is_destructive=cap_def.is_destructive,
                    integration_id=ti.integration_id,
                    adapter_class=integ_def.adapter_class or "",
                ))

            # Load skill file
            skill_content = _load_skill_file(integ_def.skill_file)

            resolved_integrations.append(ResolvedIntegration(
                integration_id=ti.integration_id,
                name=integ_def.name,
                category=integ_def.category,
                adapter_class=integ_def.adapter_class or "",
                skill_content=skill_content,
                capabilities=resolved_caps,
            ))

        tool_set = TenantToolSet(
            tenant_id=tenant_id,
            integrations=resolved_integrations,
        )

        # Cache result
        _resolver_cache[tenant_id] = tool_set

        logger.info(
            "tool_resolver.resolved",
            tenant_id=tenant_id,
            integrations=len(resolved_integrations),
            capabilities=len(tool_set.all_capabilities),
        )

        return tool_set

    def resolve_capability_adapter(
        self,
        capability_id: str,
        tool_set: TenantToolSet,
    ) -> tuple[Optional[str], Optional[str]]:
        """Find the adapter class and integration_id for a given capability.

        Args:
            capability_id: The capability to look up (e.g., "crm.customer.search").
            tool_set: The resolved tool set for the tenant.

        Returns:
            Tuple of (adapter_class, integration_id) or (None, None) if not found.
        """
        cap = tool_set.capability_map.get(capability_id)
        if cap:
            return cap.adapter_class, cap.integration_id
        return None, None
