"""ARIIA Orchestration – Dynamic Configuration Manager.

@ARCH: Phase 3 – Runtime Bridge & Pub/Sub
Provides a thread-safe, cached bridge between the database and the 
active LeadAgent orchestrator. Listens for Redis Pub/Sub invalidations.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import redis
import structlog
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import AgentTeam
from app.orchestration.models import OrchestratorDefinition, OrchestratorTenantOverride
from config.settings import get_settings

logger = structlog.get_logger()

# Constants
CACHE_TTL = 300  # 5 minutes
CONFIG_UPDATE_CHANNEL = "swarm:config:updated"
REDIS_CACHE_PREFIX = "orch:config"


@dataclass
class CachedConfig:
    """In-memory cached configuration object."""
    agent_team: dict[str, Any]
    orchestrator: dict[str, Any]
    loaded_at: float

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.loaded_at) > CACHE_TTL


class DynamicConfigManager:
    """Manages dynamic orchestrator and agent team configurations with caching.

    Uses a two-tier caching strategy:
    1. Thread-safe in-memory cache (L1)
    2. Redis-backed cache (L2) - Optional, implementation-dependent
    3. Database fallback (L3)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DynamicConfigManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        """Initialize the manager instance."""
        self._memory_cache: dict[int, CachedConfig] = {}
        self._cache_lock = threading.Lock()
        self._settings = get_settings()
        self._redis_client: Optional[redis.Redis] = None
        try:
            self._redis_client = redis.from_url(
                self._settings.redis_url, 
                decode_responses=True,
                socket_timeout=1.0
            )
        except Exception as e:
            logger.warning("config_manager.redis_init_failed", error=str(e))

    def get_tenant_config(self, tenant_id: int) -> dict[str, Any]:
        """Fetch the active AgentTeam and OrchestratorDefinition for a tenant.

        Args:
            tenant_id: Numeric ID of the tenant.

        Returns:
            Dictionary containing 'agent_team' and 'orchestrator' data.
        """
        # 1. Check in-memory cache
        with self._cache_lock:
            cached = self._memory_cache.get(tenant_id)
            if cached and not cached.is_expired:
                return {
                    "agent_team": cached.agent_team,
                    "orchestrator": cached.orchestrator
                }

        # 2. Load from Database
        config_data = self._load_from_db(tenant_id)
        
        # 3. Update in-memory cache
        if config_data:
            with self._cache_lock:
                self._memory_cache[tenant_id] = CachedConfig(
                    agent_team=config_data["agent_team"],
                    orchestrator=config_data["orchestrator"],
                    loaded_at=time.time()
                )
        
        return config_data or {"agent_team": None, "orchestrator": None}

    def invalidate_cache(self, tenant_id: Optional[int] = None, type: Optional[str] = None, id: Optional[str] = None) -> None:
        """Clear local and potentially Redis-backed caches.

        Args:
            tenant_id: Specific tenant to invalidate, or None for all.
            type: Not used currently, but kept for API compatibility.
            id: Not used currently, but kept for API compatibility.
        """
        with self._cache_lock:
            if tenant_id is not None:
                self._memory_cache.pop(tenant_id, None)
                logger.info("config_manager.cache_invalidated", tenant_id=tenant_id)
            else:
                self._memory_cache.clear()
                logger.info("config_manager.cache_cleared_all")

        # Note: We rely on the Pub/Sub listener to trigger this across instances.
        # If this instance is the one performing the update, it already cleared its cache.

    def _load_from_db(self, tenant_id: int) -> dict[str, Any]:
        """Internal helper to load config from the database."""
        db: Session = SessionLocal()
        try:
            # 1. Fetch Active AgentTeam for tenant
            # Assuming there's one primary team or we fetch the first active one
            team = db.query(AgentTeam).filter(
                AgentTeam.tenant_id == tenant_id,
                AgentTeam.status == "ACTIVE"
            ).first()

            if not team:
                logger.warning("config_manager.team_not_found", tenant_id=tenant_id)
                return {"agent_team": None, "orchestrator": None}

            team_data = {
                "id": team.id,
                "name": team.name,
                "display_name": team.display_name,
                "agent_ids": team.agent_ids,
                "orchestrator_name": team.orchestrator_name
            }

            # 2. Fetch OrchestratorDefinition
            orch_name = team.orchestrator_name or "swarm-orchestrator"
            orch = db.query(OrchestratorDefinition).filter(
                OrchestratorDefinition.name == orch_name
            ).first()

            if not orch:
                logger.warning("config_manager.orchestrator_not_found", name=orch_name)
                return {"agent_team": team_data, "orchestrator": None}

            # 3. Check for Tenant Overrides
            override = db.query(OrchestratorTenantOverride).filter(
                OrchestratorTenantOverride.orchestrator_id == orch.id,
                OrchestratorTenantOverride.tenant_id == tenant_id
            ).first()

            final_config = orch.config_current or {}
            if override and override.config_override:
                # Merge logic: override keys replace base keys
                final_config.update(override.config_override)

            orch_data = {
                "id": orch.id,
                "name": orch.name,
                "category": orch.category,
                "config": final_config,
                "guardrails": orch.guardrails
            }

            return {
                "agent_team": team_data,
                "orchestrator": orch_data
            }

        except Exception as e:
            logger.error("config_manager.db_load_failed", tenant_id=tenant_id, error=str(e))
            return {"agent_team": None, "orchestrator": None}
        finally:
            db.close()


# ── Redis Pub/Sub Listener ───────────────────────────────────────────────────

async def start_runtime_config_listener() -> None:
    """Background listener for configuration updates via Redis Pub/Sub."""
    settings = get_settings()
    manager = DynamicConfigManager()
    
    try:
        import aioredis
        redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis_conn.pubsub()
        await pubsub.subscribe(CONFIG_UPDATE_CHANNEL)

        logger.info("config_manager.listener_started", channel=CONFIG_UPDATE_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
                tenant_id = data.get("tenant_id")
                
                # Invalidate cache for specific tenant or all
                manager.invalidate_cache(tenant_id=tenant_id)
                
                logger.debug(
                    "config_manager.pubsub_invalidation", 
                    tenant_id=tenant_id,
                    data=data
                )
            except Exception as e:
                logger.warning("config_manager.pubsub_parse_error", error=str(e))

    except ImportError:
        logger.error("config_manager.aioredis_missing", detail="Please install aioredis")
    except Exception as e:
        logger.error("config_manager.listener_failed", error=str(e))
