"""ARIIA v2.0 – Tenant Configuration Helper.

@ARCH: Phase 2, Meilenstein 2.4 – Integration & Skills
Provides a structured API for reading and writing tenant configuration,
including agent settings, integration preferences, and feature flags.

This module wraps the existing TenantConfig key-value store with
structured access patterns for the new Integration & Skills architecture.

Configuration Keys (Phase 2):
  - agent.persona.system_prompt    → Custom system prompt for the tenant's agent
  - agent.persona.name             → Agent display name
  - agent.persona.language         → Preferred language (de/en/bg)
  - agent.integrations.crm_provider → Active CRM integration ID (e.g., "magicline")
  - agent.integrations.messaging    → Active messaging channels (JSON list)
  - agent.features.*               → Feature flags per tenant
"""

from __future__ import annotations

import json
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import TenantConfig

logger = structlog.get_logger()


class TenantConfigHelper:
    """Structured access to tenant configuration.

    Wraps the TenantConfig key-value store with typed getters/setters
    for the Integration & Skills architecture.
    """

    def __init__(self, db: Session, tenant_id: int):
        self._db = db
        self._tenant_id = tenant_id

    # ─── Generic Access ──────────────────────────────────────────────────

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a config value by key."""
        config = self._db.execute(
            select(TenantConfig)
            .where(TenantConfig.tenant_id == self._tenant_id)
            .where(TenantConfig.key == key)
        ).scalar_one_or_none()
        return config.value if config else default

    def get_json(self, key: str, default: Any = None) -> Any:
        """Get a config value parsed as JSON."""
        raw = self.get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    def set(self, key: str, value: str) -> None:
        """Set a config value (upsert)."""
        config = self._db.execute(
            select(TenantConfig)
            .where(TenantConfig.tenant_id == self._tenant_id)
            .where(TenantConfig.key == key)
        ).scalar_one_or_none()
        if config:
            config.value = value
        else:
            config = TenantConfig(tenant_id=self._tenant_id, key=key, value=value)
            self._db.add(config)
        self._db.flush()

    def set_json(self, key: str, value: Any) -> None:
        """Set a config value as JSON."""
        self.set(key, json.dumps(value, ensure_ascii=False))

    def delete(self, key: str) -> bool:
        """Delete a config key. Returns True if it existed."""
        config = self._db.execute(
            select(TenantConfig)
            .where(TenantConfig.tenant_id == self._tenant_id)
            .where(TenantConfig.key == key)
        ).scalar_one_or_none()
        if config:
            self._db.delete(config)
            self._db.flush()
            return True
        return False

    def get_all(self, prefix: Optional[str] = None) -> dict[str, str]:
        """Get all config values, optionally filtered by key prefix."""
        query = select(TenantConfig).where(TenantConfig.tenant_id == self._tenant_id)
        if prefix:
            query = query.where(TenantConfig.key.startswith(prefix))
        configs = self._db.execute(query).scalars().all()
        return {c.key: c.value for c in configs}

    # ─── Agent Persona ───────────────────────────────────────────────────

    @property
    def agent_system_prompt(self) -> Optional[str]:
        """Get the custom system prompt for the tenant's agent."""
        return self.get("agent.persona.system_prompt")

    @agent_system_prompt.setter
    def agent_system_prompt(self, value: str) -> None:
        self.set("agent.persona.system_prompt", value)

    @property
    def agent_name(self) -> str:
        """Get the agent's display name."""
        return self.get("agent.persona.name", "ARIIA")

    @agent_name.setter
    def agent_name(self, value: str) -> None:
        self.set("agent.persona.name", value)

    @property
    def agent_language(self) -> str:
        """Get the preferred language for the agent."""
        return self.get("agent.persona.language", "de")

    @agent_language.setter
    def agent_language(self, value: str) -> None:
        self.set("agent.persona.language", value)

    # ─── Integration Preferences ─────────────────────────────────────────

    @property
    def crm_provider(self) -> Optional[str]:
        """Get the active CRM integration ID."""
        return self.get("agent.integrations.crm_provider")

    @crm_provider.setter
    def crm_provider(self, value: str) -> None:
        self.set("agent.integrations.crm_provider", value)

    @property
    def messaging_channels(self) -> list[str]:
        """Get the list of active messaging channels."""
        return self.get_json("agent.integrations.messaging", [])

    @messaging_channels.setter
    def messaging_channels(self, value: list[str]) -> None:
        self.set_json("agent.integrations.messaging", value)

    @property
    def active_integrations(self) -> list[str]:
        """Get all active integration IDs from config."""
        result = []
        crm = self.crm_provider
        if crm:
            result.append(crm)
        # Add any other integration types here
        return result

    # ─── Feature Flags ───────────────────────────────────────────────────

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature flag is enabled for this tenant."""
        value = self.get(f"agent.features.{feature}", "false")
        return value.lower() in ("true", "1", "yes", "enabled")

    def set_feature(self, feature: str, enabled: bool) -> None:
        """Set a feature flag for this tenant."""
        self.set(f"agent.features.{feature}", "true" if enabled else "false")

    # ─── Bulk Operations ─────────────────────────────────────────────────

    def get_agent_config(self) -> dict:
        """Get the complete agent configuration as a structured dict."""
        return {
            "persona": {
                "name": self.agent_name,
                "language": self.agent_language,
                "system_prompt": self.agent_system_prompt,
            },
            "integrations": {
                "crm_provider": self.crm_provider,
                "messaging_channels": self.messaging_channels,
            },
            "features": {
                k.replace("agent.features.", ""): v.lower() in ("true", "1", "yes", "enabled")
                for k, v in self.get_all("agent.features.").items()
            },
        }
