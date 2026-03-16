"""ARIIA Swarm v3 — DynamicAgentLoader with Redis Cache Invalidation.

Loads agent configurations from the database, merges tenant overrides,
and instantiates GenericExpertAgent instances.  Uses a TTL-based cache
to avoid repeated DB hits and subscribes to a Redis Pub/Sub channel
for config change notifications.

Usage:
    loader = get_agent_loader()
    agent = loader.get_agent("ops", context)
"""

from __future__ import annotations

import json
import time
import structlog
from dataclasses import dataclass
from typing import Any

from app.swarm.contracts import TenantContext
from app.swarm.agents.generic_agent import GenericExpertAgent

logger = structlog.get_logger()

# Cache TTL in seconds
CACHE_TTL = 60

# Redis Pub/Sub channel for config updates
CONFIG_UPDATE_CHANNEL = "swarm:config:updated"


@dataclass
class CachedAgentDef:
    """Cached agent definition with expiry timestamp."""

    agent_id: str
    display_name: str
    system_prompt: str
    default_tools_json: str
    max_turns: int
    qa_profile: str
    loaded_at: float

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.loaded_at) > CACHE_TTL


class DynamicAgentLoader:
    """Loads and caches GenericExpertAgent instances from the database.

    Cache Strategy:
    - Agent definitions (AgentDefinition) are cached with a 60s TTL
    - Tenant configs (TenantAgentConfig) are NOT cached (per-request)
    - Cache is invalidated via Redis Pub/Sub or manual call
    """

    def __init__(self):
        self._cache: dict[str, CachedAgentDef] = {}

    def get_agent(
        self,
        agent_id: str,
        context: TenantContext | None = None,
    ) -> GenericExpertAgent | None:
        """Load and configure a GenericExpertAgent for the given agent + tenant.

        Steps:
        1. Load AgentDefinition (cached)
        2. Load TenantAgentConfig (per-request)
        3. Merge prompt override
        4. Merge tool overrides
        5. Resolve tools via TenantToolRegistry
        6. Instantiate GenericExpertAgent

        Args:
            agent_id: The agent definition ID (e.g. "ops", "sales").
            context: TenantContext for tenant-specific config. If None,
                     returns agent with defaults only.

        Returns:
            Configured GenericExpertAgent or None if agent not found.
        """
        # 1. Load agent definition (cached)
        agent_def = self._get_cached_or_load(agent_id)
        if not agent_def:
            logger.warning("agent_loader.not_found", agent_id=agent_id)
            return None

        # 2. Load tenant config (if context provided)
        tenant_cfg = None
        if context:
            tenant_cfg = self._load_tenant_agent_cfg(agent_id, context.tenant_id)

        # 3. Merge system prompt
        system_prompt = agent_def.system_prompt
        if tenant_cfg and tenant_cfg.get("system_prompt_override"):
            system_prompt = tenant_cfg["system_prompt_override"]

        # 4. Resolve tools
        tools = []
        if context:
            tool_overrides = None
            if tenant_cfg and tenant_cfg.get("tool_overrides"):
                raw = tenant_cfg["tool_overrides"]
                tool_overrides = json.loads(raw) if isinstance(raw, str) else raw

            try:
                from app.swarm.tools.registry import TenantToolRegistry
                registry = self._build_registry(context.tenant_id)
                tools = registry.get_tools_for_agent(
                    agent_id,
                    context,
                    tool_overrides=tool_overrides,
                )
            except Exception as e:
                logger.error(
                    "agent_loader.tool_resolution_failed",
                    agent_id=agent_id,
                    error=str(e),
                )

        # 5. Instantiate
        return GenericExpertAgent(
            agent_id=agent_def.agent_id,
            display_name=agent_def.display_name,
            system_prompt_template=system_prompt,
            tools=tools,
            max_turns=agent_def.max_turns,
            qa_profile=agent_def.qa_profile,
        )

    def invalidate_cache(self, agent_id: str | None = None) -> None:
        """Invalidate cached agent definitions.

        Args:
            agent_id: Specific agent to invalidate, or None for all.
        """
        if agent_id:
            self._cache.pop(agent_id, None)
            logger.info("agent_loader.cache_invalidated", agent_id=agent_id)
        else:
            self._cache.clear()
            logger.info("agent_loader.cache_cleared")

    def list_agents(self) -> list[dict[str, Any]]:
        """List all available agent definitions from the DB."""
        try:
            from app.core.db import SessionLocal
            from app.core.models import AgentDefinition

            db = SessionLocal()
            try:
                rows = db.query(AgentDefinition).all()
                return [
                    {
                        "id": r.id,
                        "display_name": r.display_name,
                        "description": r.description,
                        "is_system": r.is_system,
                    }
                    for r in rows
                ]
            finally:
                db.close()
        except Exception as e:
            logger.error("agent_loader.list_failed", error=str(e))
            return []

    # ── Internal Methods ─────────────────────────────────────────────────

    def _get_cached_or_load(self, agent_id: str) -> CachedAgentDef | None:
        """Get agent def from cache or load from DB."""
        cached = self._cache.get(agent_id)
        if cached and not cached.is_expired:
            return cached

        agent_def = self._load_agent_def(agent_id)
        if agent_def:
            self._cache[agent_id] = agent_def
        return agent_def

    @staticmethod
    def _load_agent_def(agent_id: str) -> CachedAgentDef | None:
        """Load an AgentDefinition from the database."""
        try:
            from app.core.db import SessionLocal
            from app.core.models import AgentDefinition

            db = SessionLocal()
            try:
                row = db.query(AgentDefinition).filter(
                    AgentDefinition.id == agent_id
                ).first()

                if not row:
                    return None

                return CachedAgentDef(
                    agent_id=row.id,
                    display_name=row.display_name,
                    system_prompt=row.system_prompt or "",
                    default_tools_json=row.default_tools or "[]",
                    max_turns=row.max_turns,
                    qa_profile=row.qa_profile or "standard",
                    loaded_at=time.time(),
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(
                "agent_loader.load_def_failed",
                agent_id=agent_id,
                error=str(e),
            )
            return None

    @staticmethod
    def _load_tenant_agent_cfg(
        agent_id: str, tenant_id: int
    ) -> dict[str, Any] | None:
        """Load TenantAgentConfig for this agent + tenant."""
        try:
            from app.core.db import SessionLocal
            from app.core.models import TenantAgentConfig

            db = SessionLocal()
            try:
                row = (
                    db.query(TenantAgentConfig)
                    .filter(
                        TenantAgentConfig.tenant_id == tenant_id,
                        TenantAgentConfig.agent_id == agent_id,
                    )
                    .first()
                )

                if not row:
                    return None

                return {
                    "is_enabled": row.is_enabled,
                    "system_prompt_override": row.system_prompt_override,
                    "tool_overrides": row.tool_overrides,
                    "extra_config": row.extra_config,
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(
                "agent_loader.load_cfg_failed",
                agent_id=agent_id,
                tenant_id=tenant_id,
                error=str(e),
            )
            return None

    @staticmethod
    def _build_registry(tenant_id: int):
        """Build a TenantToolRegistry from DB rows for this tenant."""
        from app.swarm.tools.registry import TenantToolRegistry

        try:
            from app.core.db import SessionLocal
            from app.core.models import TenantToolConfig

            db = SessionLocal()
            try:
                rows = (
                    db.query(TenantToolConfig)
                    .filter(TenantToolConfig.tenant_id == tenant_id)
                    .all()
                )
                return TenantToolRegistry.from_db_rows(rows)
            finally:
                db.close()
        except Exception:
            return TenantToolRegistry()


# ── Module-level Singleton ───────────────────────────────────────────────────

_loader_instance: DynamicAgentLoader | None = None


def get_agent_loader() -> DynamicAgentLoader:
    """Return the shared DynamicAgentLoader singleton."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = DynamicAgentLoader()
    return _loader_instance


# ── Redis Pub/Sub Listener ───────────────────────────────────────────────────


async def start_config_listener(redis_url: str) -> None:
    """Start a Redis Pub/Sub listener for config change notifications.

    Listens on the 'swarm:config:updated' channel and invalidates
    the agent cache when a message is received.

    Message format: {"agent_id": "ops"} or {"agent_id": null} for all.
    """
    try:
        import aioredis
        redis = aioredis.from_url(redis_url)
        pubsub = redis.pubsub()
        await pubsub.subscribe(CONFIG_UPDATE_CHANNEL)

        logger.info("agent_loader.config_listener_started", channel=CONFIG_UPDATE_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
                agent_id = data.get("agent_id")
                loader = get_agent_loader()
                loader.invalidate_cache(agent_id)
            except Exception as e:
                logger.warning(
                    "agent_loader.config_listener_error",
                    error=str(e),
                )
    except Exception as e:
        logger.error(
            "agent_loader.config_listener_failed",
            error=str(e),
        )
