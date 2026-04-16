from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_system_admin, require_tenant_admin_or_system
from app.gateway.services.admin_prompts_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-prompts"],
    dependencies=[Depends(get_current_user)],
)


class SaveFileRequest(BaseModel):
    content: str
    base_mtime: float | None = None
    reason: str | None = None


@router.get("/prompts/{agent}/system")
async def get_agent_system_prompt(agent: str, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_system_admin(user)
    return service.get_agent_system_prompt(user, agent)


@router.post("/prompts/{agent}/system")
async def save_agent_system_prompt(
    agent: str,
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_system_admin(user)
    return service.save_agent_system_prompt(user, agent, content=body.content, base_mtime=body.base_mtime, reason=body.reason)


@router.get("/prompts/member-memory-instructions")
async def get_member_memory_instructions(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_system_admin(user)
    return service.get_member_memory_instructions(user)


@router.post("/prompts/member-memory-instructions")
async def save_member_memory_instructions(
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_system_admin(user)
    return service.save_member_memory_instructions(user, content=body.content, base_mtime=body.base_mtime, reason=body.reason)


@router.get("/prompts/agent/{agent}")
async def get_agent_template(agent: str, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_agent_template(user, agent)


@router.post("/prompts/agent/{agent}")
async def save_agent_template(
    agent: str,
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.save_agent_template(user, agent, content=body.content, base_mtime=body.base_mtime, reason=body.reason)


@router.delete("/prompts/agent/{agent}")
async def reset_agent_template(agent: str, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.reset_agent_template(user, agent)
