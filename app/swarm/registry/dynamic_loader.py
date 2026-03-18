"""ARIIA Swarm v3 — DynamicAgentLoader with Redis Cache Invalidation.

Loads agent configurations from the database, merges tenant overrides,
and instantiates GenericExpertAgent instances.  Uses a Redis-backed
TTL cache to avoid repeated DB hits and subscribes to a Redis Pub/Sub
channel for config change notifications.

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

# Redis key prefix for agent definition cache
AGENT_DEF_CACHE_PREFIX = "agent:def"


def _get_redis():
    """Lazy Redis client for caching."""
    try:
        import redis as redis_lib
        from config.settings import get_settings
        s = get_settings()
        return redis_lib.from_url(s.redis_url or "redis://localhost:6379/1", decode_responses=True, socket_timeout=1)
    except Exception:
        return None


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

    def to_json(self) -> str:
        return json.dumps({
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "system_prompt": self.system_prompt,
            "default_tools_json": self.default_tools_json,
            "max_turns": self.max_turns,
            "qa_profile": self.qa_profile,
        })

    @classmethod
    def from_json(cls, raw: str) -> CachedAgentDef:
        d = json.loads(raw)
        return cls(loaded_at=time.time(), **d)


class DynamicAgentLoader:
    """Loads and caches GenericExpertAgent instances from the database.

    Cache Strategy:
    - Agent definitions (AgentDefinition) are cached in Redis with a 60s TTL
      Key pattern: agent:def:{tenant_id}:{agent_id}
    - Falls back to in-memory cache if Redis is unavailable
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
        agent_def = self._get_cached_or_load(agent_id, tenant_id=context.tenant_id if context else None)
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

    def invalidate_cache(self, agent_id: str | None = None, tenant_id: int | None = None) -> None:
        """Invalidate cached agent definitions in both memory and Redis.

        Args:
            agent_id: Specific agent to invalidate, or None for all.
            tenant_id: Specific tenant to invalidate, or None for all.
        """
        if agent_id:
            self._cache.pop(agent_id, None)
        else:
            self._cache.clear()

        # Invalidate Redis cache
        r = _get_redis()
        if r:
            try:
                if agent_id and tenant_id:
                    r.delete(f"{AGENT_DEF_CACHE_PREFIX}:{tenant_id}:{agent_id}")
                else:
                    # Scan and delete matching keys
                    pattern = f"{AGENT_DEF_CACHE_PREFIX}:*"
                    if agent_id:
                        pattern = f"{AGENT_DEF_CACHE_PREFIX}:*:{agent_id}"
                    cursor = 0
                    while True:
                        cursor, keys = r.scan(cursor, match=pattern, count=100)
                        if keys:
                            r.delete(*keys)
                        if cursor == 0:
                            break
            except Exception as e:
                logger.warning("agent_loader.redis_invalidation_failed", error=str(e))

        logger.info("agent_loader.cache_invalidated", agent_id=agent_id, tenant_id=tenant_id)

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

    def _get_cached_or_load(self, agent_id: str, tenant_id: int | None = None) -> CachedAgentDef | None:
        """Get agent def from memory cache → Redis cache → DB."""
        # 1. In-memory cache
        cached = self._cache.get(agent_id)
        if cached and not cached.is_expired:
            return cached

        # 2. Redis cache
        redis_key = f"{AGENT_DEF_CACHE_PREFIX}:{tenant_id or 'global'}:{agent_id}"
        r = _get_redis()
        if r:
            try:
                raw = r.get(redis_key)
                if raw:
                    agent_def = CachedAgentDef.from_json(raw)
                    self._cache[agent_id] = agent_def
                    return agent_def
            except Exception as e:
                logger.warning("agent_loader.redis_cache_read_failed", error=str(e))

        # 3. Load from DB
        agent_def = self._load_agent_def(agent_id)
        if agent_def:
            self._cache[agent_id] = agent_def
            # Store in Redis
            if r:
                try:
                    r.setex(redis_key, CACHE_TTL, agent_def.to_json())
                except Exception as e:
                    logger.warning("agent_loader.redis_cache_write_failed", error=str(e))
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
        """Build a TenantToolRegistry from DB rows, with Redis cache (60s TTL)."""
        from app.swarm.tools.registry import TenantToolRegistry

        cache_key = f"tool:registry:{tenant_id}"

        # Try Redis cache first
        r = _get_redis()
        if r:
            try:
                raw = r.get(cache_key)
                if raw:
                    configs = json.loads(raw)
                    return TenantToolRegistry(tenant_tool_configs=configs)
            except Exception as e:
                logger.warning("tool_registry.redis_cache_read_failed", error=str(e))

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
                registry = TenantToolRegistry.from_db_rows(rows)

                # Cache in Redis
                if r:
                    try:
                        configs = registry._tool_configs
                        r.setex(cache_key, CACHE_TTL, json.dumps(configs))
                    except Exception as e:
                        logger.warning("tool_registry.redis_cache_write_failed", error=str(e))

                return registry
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
    both agent definition cache and tool registry cache.

    Message format: {"orchestrator_name": "swarm-orchestrator", "tenant_id": null}
                 or {"agent_id": "ops"}
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
                tenant_id = data.get("tenant_id")
                loader = get_agent_loader()

                # Invalidate agent definition cache
                loader.invalidate_cache(agent_id, tenant_id=tenant_id)

                # Invalidate tool registry cache
                r = _get_redis()
                if r:
                    if tenant_id:
                        r.delete(f"tool:registry:{tenant_id}")
                    else:
                        cursor = 0
                        while True:
                            cursor, keys = r.scan(cursor, match="tool:registry:*", count=100)
                            if keys:
                                r.delete(*keys)
                            if cursor == 0:
                                break

                logger.info("config_listener.caches_invalidated", agent_id=agent_id, tenant_id=tenant_id)
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
