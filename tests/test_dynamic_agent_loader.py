from __future__ import annotations

import time

from app.core.db import SessionLocal
from app.core.models import AgentDefinition, TenantAgentConfig
from app.swarm.registry.dynamic_loader import DynamicAgentLoader


def _cleanup_agent(agent_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(TenantAgentConfig).filter(TenantAgentConfig.agent_id == agent_id).delete()
        db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).delete()
        db.commit()
    finally:
        db.close()


def test_dynamic_loader_lists_agents_from_db() -> None:
    agent_id = f"loader-agent-{int(time.time() * 1000)}"
    db = SessionLocal()
    try:
        db.add(
            AgentDefinition(
                id=agent_id,
                display_name="Loader Agent",
                description="Dynamic loader test agent",
                min_plan_tier="starter",
                is_system=False,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        loader = DynamicAgentLoader()
        agents = loader.list_agents()
        created = next(item for item in agents if item["id"] == agent_id)
        assert created["display_name"] == "Loader Agent"
        assert created["is_system"] is False
    finally:
        _cleanup_agent(agent_id)


def test_dynamic_loader_reads_tenant_override_config() -> None:
    agent_id = f"loader-cfg-{int(time.time() * 1000)}"
    db = SessionLocal()
    try:
        db.add(
            AgentDefinition(
                id=agent_id,
                display_name="Override Agent",
                min_plan_tier="starter",
                is_system=False,
            )
        )
        db.add(
            TenantAgentConfig(
                tenant_id=1,
                agent_id=agent_id,
                is_enabled=True,
                system_prompt_override="Tenant prompt override",
                tool_overrides='["search"]',
                extra_config='{"mode":"strict"}',
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        config = DynamicAgentLoader._load_tenant_agent_cfg(agent_id, tenant_id=1)
        assert config is not None
        assert config["is_enabled"] is True
        assert config["system_prompt_override"] == "Tenant prompt override"
        assert config["tool_overrides"] == '["search"]'
        assert config["extra_config"] == '{"mode":"strict"}'
    finally:
        _cleanup_agent(agent_id)
