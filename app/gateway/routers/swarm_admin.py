"""Swarm v3 Admin API – Agent & Tool Definition CRUD + Tenant Config.

System-admin-only routes for managing the agent/tool catalog and
per-tenant swarm configuration. After every mutation a Redis pub/sub
event ``swarm:config:updated`` is published so that the
DynamicAgentLoader can invalidate its cache.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, AuthContext, require_role
from app.core.db import SessionLocal
from app.core.models import (
    AgentDefinition,
    AuditLog,
    ToolDefinition,
    TenantAgentConfig,
    TenantToolConfig,
)
from app.gateway.dependencies import redis_bus

logger = structlog.get_logger()

router = APIRouter(
    prefix="/admin/swarm",
    tags=["swarm-admin"],
    dependencies=[Depends(get_current_user)],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_system_admin(user: AuthContext) -> None:
    require_role(user, {"system_admin"})


def _audit(
    *,
    actor: AuthContext,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db = SessionLocal()
    try:
        actor_uid = actor.impersonator_user_id if actor.is_impersonating else actor.user_id
        actor_email = actor.impersonator_email if actor.is_impersonating else actor.email
        actor_tid = actor.impersonator_tenant_id if actor.is_impersonating else actor.tenant_id
        db.add(
            AuditLog(
                actor_user_id=actor_uid,
                actor_email=actor_email,
                tenant_id=actor_tid,
                action=action,
                category="swarm",
                target_type=target_type,
                target_id=str(target_id) if target_id else None,
                details_json=json.dumps(details or {}, ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()


async def _notify_config_change(detail: str = "") -> None:
    """Publish a cache-invalidation event on the ``swarm:config:updated`` channel."""
    try:
        payload = json.dumps({"event": "swarm:config:updated", "detail": detail, "ts": datetime.now(timezone.utc).isoformat()})
        await redis_bus.publish("swarm:config:updated", payload)
    except Exception as exc:
        logger.warning("swarm_admin.redis_notify_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

# -- Agent --

class AgentCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=64, description="Unique slug, e.g. 'ops', 'social_media'")
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    default_tools: Optional[list[str]] = None
    max_turns: int = Field(5, ge=1, le=50)
    qa_profile: Optional[str] = None
    min_plan_tier: str = Field("starter", pattern=r"^(starter|pro|enterprise)$")
    is_system: bool = False


class AgentUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    default_tools: Optional[list[str]] = None
    max_turns: Optional[int] = Field(None, ge=1, le=50)
    qa_profile: Optional[str] = None
    min_plan_tier: Optional[str] = Field(None, pattern=r"^(starter|pro|enterprise)$")


class AgentOut(BaseModel):
    id: str
    display_name: str
    description: Optional[str]
    system_prompt: Optional[str]
    default_tools: Optional[list[str]]
    max_turns: int
    qa_profile: Optional[str]
    min_plan_tier: str
    is_system: bool
    created_at: Optional[str]


# -- Tool --

class ToolCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    required_integration: Optional[str] = None
    min_plan_tier: str = Field("starter", pattern=r"^(starter|pro|enterprise)$")
    config_schema: Optional[dict] = None
    is_system: bool = False


class ToolUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    required_integration: Optional[str] = None
    min_plan_tier: Optional[str] = Field(None, pattern=r"^(starter|pro|enterprise)$")
    config_schema: Optional[dict] = None


class ToolOut(BaseModel):
    id: str
    display_name: str
    description: Optional[str]
    category: Optional[str]
    required_integration: Optional[str]
    min_plan_tier: str
    config_schema: Optional[dict]
    is_system: bool
    created_at: Optional[str]


# -- Tenant Config --

class TenantAgentConfigBody(BaseModel):
    is_enabled: Optional[bool] = None
    system_prompt_override: Optional[str] = None
    tool_overrides: Optional[list[str]] = None
    extra_config: Optional[dict] = None


class TenantToolConfigBody(BaseModel):
    is_enabled: Optional[bool] = None
    config: Optional[dict] = None


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _agent_to_dict(a: AgentDefinition) -> dict:
    tools = None
    if a.default_tools:
        try:
            tools = json.loads(a.default_tools)
        except (json.JSONDecodeError, TypeError):
            tools = []
    return AgentOut(
        id=a.id,
        display_name=a.display_name,
        description=a.description,
        system_prompt=a.system_prompt,
        default_tools=tools,
        max_turns=a.max_turns,
        qa_profile=a.qa_profile,
        min_plan_tier=a.min_plan_tier,
        is_system=a.is_system,
        created_at=a.created_at.isoformat() if a.created_at else None,
    ).model_dump()


def _tool_to_dict(t: ToolDefinition) -> dict:
    schema = None
    if t.config_schema:
        try:
            schema = json.loads(t.config_schema)
        except (json.JSONDecodeError, TypeError):
            schema = None
    return ToolOut(
        id=t.id,
        display_name=t.display_name,
        description=t.description,
        category=t.category,
        required_integration=t.required_integration,
        min_plan_tier=t.min_plan_tier,
        config_schema=schema,
        is_system=t.is_system,
        created_at=t.created_at.isoformat() if t.created_at else None,
    ).model_dump()


# ---------------------------------------------------------------------------
# Agent CRUD
# ---------------------------------------------------------------------------

@router.get("/agents")
async def list_agents(user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        agents = db.query(AgentDefinition).order_by(AgentDefinition.display_name).all()
        return [_agent_to_dict(a) for a in agents]
    finally:
        db.close()


@router.post("/agents", status_code=201)
async def create_agent(body: AgentCreate, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        if db.query(AgentDefinition).filter(AgentDefinition.id == body.id).first():
            raise HTTPException(409, f"Agent '{body.id}' already exists")
        agent = AgentDefinition(
            id=body.id,
            display_name=body.display_name,
            description=body.description,
            system_prompt=body.system_prompt,
            default_tools=json.dumps(body.default_tools) if body.default_tools else None,
            max_turns=body.max_turns,
            qa_profile=body.qa_profile,
            min_plan_tier=body.min_plan_tier,
            is_system=body.is_system,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        _audit(actor=user, action="created", target_type="agent_definition", target_id=agent.id, details={"display_name": body.display_name})
        await _notify_config_change(f"agent_created:{agent.id}")
        return _agent_to_dict(agent)
    finally:
        db.close()


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
        if not agent:
            raise HTTPException(404, "Agent not found")
        return _agent_to_dict(agent)
    finally:
        db.close()


@router.patch("/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
        if not agent:
            raise HTTPException(404, "Agent not found")
        updates = body.model_dump(exclude_unset=True)
        if "default_tools" in updates:
            updates["default_tools"] = json.dumps(updates["default_tools"]) if updates["default_tools"] is not None else None
        for k, v in updates.items():
            setattr(agent, k, v)
        db.commit()
        db.refresh(agent)
        _audit(actor=user, action="updated", target_type="agent_definition", target_id=agent_id, details=updates)
        await _notify_config_change(f"agent_updated:{agent_id}")
        return _agent_to_dict(agent)
    finally:
        db.close()


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
        if not agent:
            raise HTTPException(404, "Agent not found")
        if agent.is_system:
            raise HTTPException(403, "Cannot delete system agents")
        # Clean up tenant configs referencing this agent
        db.query(TenantAgentConfig).filter(TenantAgentConfig.agent_id == agent_id).delete()
        db.delete(agent)
        db.commit()
        _audit(actor=user, action="deleted", target_type="agent_definition", target_id=agent_id)
        await _notify_config_change(f"agent_deleted:{agent_id}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool CRUD
# ---------------------------------------------------------------------------

@router.get("/tools")
async def list_tools(user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        tools = db.query(ToolDefinition).order_by(ToolDefinition.display_name).all()
        return [_tool_to_dict(t) for t in tools]
    finally:
        db.close()


@router.post("/tools", status_code=201)
async def create_tool(body: ToolCreate, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        if db.query(ToolDefinition).filter(ToolDefinition.id == body.id).first():
            raise HTTPException(409, f"Tool '{body.id}' already exists")
        tool = ToolDefinition(
            id=body.id,
            display_name=body.display_name,
            description=body.description,
            category=body.category,
            required_integration=body.required_integration,
            min_plan_tier=body.min_plan_tier,
            config_schema=json.dumps(body.config_schema) if body.config_schema else None,
            is_system=body.is_system,
        )
        db.add(tool)
        db.commit()
        db.refresh(tool)
        _audit(actor=user, action="created", target_type="tool_definition", target_id=tool.id, details={"display_name": body.display_name})
        await _notify_config_change(f"tool_created:{tool.id}")
        return _tool_to_dict(tool)
    finally:
        db.close()


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        tool = db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).first()
        if not tool:
            raise HTTPException(404, "Tool not found")
        return _tool_to_dict(tool)
    finally:
        db.close()


@router.patch("/tools/{tool_id}")
async def update_tool(tool_id: str, body: ToolUpdate, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        tool = db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).first()
        if not tool:
            raise HTTPException(404, "Tool not found")
        updates = body.model_dump(exclude_unset=True)
        if "config_schema" in updates:
            updates["config_schema"] = json.dumps(updates["config_schema"]) if updates["config_schema"] is not None else None
        for k, v in updates.items():
            setattr(tool, k, v)
        db.commit()
        db.refresh(tool)
        _audit(actor=user, action="updated", target_type="tool_definition", target_id=tool_id, details=updates)
        await _notify_config_change(f"tool_updated:{tool_id}")
        return _tool_to_dict(tool)
    finally:
        db.close()


@router.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(tool_id: str, user: AuthContext = Depends(get_current_user)):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        tool = db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).first()
        if not tool:
            raise HTTPException(404, "Tool not found")
        if tool.is_system:
            raise HTTPException(403, "Cannot delete system tools")
        db.query(TenantToolConfig).filter(TenantToolConfig.tool_id == tool_id).delete()
        db.delete(tool)
        db.commit()
        _audit(actor=user, action="deleted", target_type="tool_definition", target_id=tool_id)
        await _notify_config_change(f"tool_deleted:{tool_id}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tenant Agent Config
# ---------------------------------------------------------------------------

@router.post("/tenants/{tenant_id}/agents/{agent_id}/configure")
async def configure_tenant_agent(
    tenant_id: int,
    agent_id: str,
    body: TenantAgentConfigBody,
    user: AuthContext = Depends(get_current_user),
):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        # Verify agent exists
        if not db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first():
            raise HTTPException(404, "Agent not found")
        cfg = (
            db.query(TenantAgentConfig)
            .filter(TenantAgentConfig.tenant_id == tenant_id, TenantAgentConfig.agent_id == agent_id)
            .first()
        )
        updates = body.model_dump(exclude_unset=True)
        if "tool_overrides" in updates:
            updates["tool_overrides"] = json.dumps(updates["tool_overrides"]) if updates["tool_overrides"] is not None else None
        if "extra_config" in updates:
            updates["extra_config"] = json.dumps(updates["extra_config"]) if updates["extra_config"] is not None else None
        if cfg:
            for k, v in updates.items():
                setattr(cfg, k, v)
        else:
            cfg = TenantAgentConfig(
                tenant_id=tenant_id,
                agent_id=agent_id,
                is_enabled=updates.get("is_enabled", True),
                system_prompt_override=updates.get("system_prompt_override"),
                tool_overrides=updates.get("tool_overrides"),
                extra_config=updates.get("extra_config"),
            )
            db.add(cfg)
        db.commit()
        db.refresh(cfg)
        _audit(actor=user, action="configured", target_type="tenant_agent_config", target_id=f"{tenant_id}/{agent_id}", details=updates)
        await _notify_config_change(f"tenant_agent_configured:{tenant_id}:{agent_id}")
        return {"status": "ok", "tenant_id": tenant_id, "agent_id": agent_id, "is_enabled": cfg.is_enabled}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tenant Tool Config
# ---------------------------------------------------------------------------

@router.post("/tenants/{tenant_id}/tools/{tool_id}/configure")
async def configure_tenant_tool(
    tenant_id: int,
    tool_id: str,
    body: TenantToolConfigBody,
    user: AuthContext = Depends(get_current_user),
):
    _require_system_admin(user)
    db = SessionLocal()
    try:
        if not db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).first():
            raise HTTPException(404, "Tool not found")
        cfg = (
            db.query(TenantToolConfig)
            .filter(TenantToolConfig.tenant_id == tenant_id, TenantToolConfig.tool_id == tool_id)
            .first()
        )
        updates = body.model_dump(exclude_unset=True)
        if "config" in updates:
            updates["config"] = json.dumps(updates["config"]) if updates["config"] is not None else None
        if cfg:
            for k, v in updates.items():
                setattr(cfg, k, v)
        else:
            cfg = TenantToolConfig(
                tenant_id=tenant_id,
                tool_id=tool_id,
                is_enabled=updates.get("is_enabled", True),
                config=updates.get("config"),
            )
            db.add(cfg)
        db.commit()
        db.refresh(cfg)
        _audit(actor=user, action="configured", target_type="tenant_tool_config", target_id=f"{tenant_id}/{tool_id}", details=updates)
        await _notify_config_change(f"tenant_tool_configured:{tenant_id}:{tool_id}")
        return {"status": "ok", "tenant_id": tenant_id, "tool_id": tool_id, "is_enabled": cfg.is_enabled}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tenant Config listing (for frontend)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tenant_id}/agents")
async def list_tenant_agent_configs(tenant_id: int, user: AuthContext = Depends(get_current_user)):
    """List all agents with their tenant-specific config (enabled state, overrides)."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        agents = db.query(AgentDefinition).order_by(AgentDefinition.display_name).all()
        configs = {
            c.agent_id: c
            for c in db.query(TenantAgentConfig).filter(TenantAgentConfig.tenant_id == tenant_id).all()
        }
        result = []
        for a in agents:
            cfg = configs.get(a.id)
            entry = _agent_to_dict(a)
            entry["tenant_config"] = None
            if cfg:
                tool_ov = None
                if cfg.tool_overrides:
                    try:
                        tool_ov = json.loads(cfg.tool_overrides)
                    except (json.JSONDecodeError, TypeError):
                        tool_ov = None
                extra = None
                if cfg.extra_config:
                    try:
                        extra = json.loads(cfg.extra_config)
                    except (json.JSONDecodeError, TypeError):
                        extra = None
                entry["tenant_config"] = {
                    "is_enabled": cfg.is_enabled,
                    "system_prompt_override": cfg.system_prompt_override,
                    "tool_overrides": tool_ov,
                    "extra_config": extra,
                }
            result.append(entry)
        return result
    finally:
        db.close()


@router.get("/tenants/{tenant_id}/tools")
async def list_tenant_tool_configs(tenant_id: int, user: AuthContext = Depends(get_current_user)):
    """List all tools with their tenant-specific config (enabled state, settings)."""
    _require_system_admin(user)
    db = SessionLocal()
    try:
        tools = db.query(ToolDefinition).order_by(ToolDefinition.display_name).all()
        configs = {
            c.tool_id: c
            for c in db.query(TenantToolConfig).filter(TenantToolConfig.tenant_id == tenant_id).all()
        }
        result = []
        for t in tools:
            cfg = configs.get(t.id)
            entry = _tool_to_dict(t)
            entry["tenant_config"] = None
            if cfg:
                tcfg = None
                if cfg.config:
                    try:
                        tcfg = json.loads(cfg.config)
                    except (json.JSONDecodeError, TypeError):
                        tcfg = None
                entry["tenant_config"] = {
                    "is_enabled": cfg.is_enabled,
                    "config": tcfg,
                }
            result.append(entry)
        return result
    finally:
        db.close()
