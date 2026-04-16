from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_tenant_admin_or_system
from app.gateway.services.admin_knowledge_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-knowledge"],
    dependencies=[Depends(get_current_user)],
)


class SaveFileRequest(BaseModel):
    content: str
    base_mtime: float | None = None
    reason: str | None = None


class MemberMemoryAnalyzeRequest(BaseModel):
    member_id: str | None = None


@router.get("/knowledge")
async def list_knowledge_files(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> list[str]:
    require_tenant_admin_or_system(user)
    return service.list_knowledge_files(user, tenant_slug)


@router.get("/knowledge/file/{filename}")
async def get_knowledge_file(
    filename: str,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_knowledge_file(user, filename, tenant_slug)


@router.post("/knowledge/file/{filename}")
async def save_knowledge_file(
    filename: str,
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.save_knowledge_file(
        user,
        filename,
        content=body.content,
        base_mtime=body.base_mtime,
        reason=body.reason,
        tenant_slug=tenant_slug,
    )


@router.delete("/knowledge/file/{filename}")
async def delete_knowledge_file(
    filename: str,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.delete_knowledge_file(user, filename, tenant_slug)


@router.get("/knowledge/status")
async def get_knowledge_status(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_knowledge_status(user, tenant_slug)


@router.post("/knowledge/reindex")
async def reindex_knowledge(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.reindex_knowledge(user, tenant_slug)


@router.get("/member-memory")
async def list_member_memory_files(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> list[str]:
    require_tenant_admin_or_system(user)
    return service.list_member_memory_files(user, tenant_slug)


@router.post("/member-memory/analyze-now")
async def run_member_memory_analyzer_now(
    body: MemberMemoryAnalyzeRequest = Body(default=MemberMemoryAnalyzeRequest()),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return await service.run_member_memory_analyzer_now(user, body.member_id)


@router.get("/member-memory/status")
async def get_member_memory_status(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_member_memory_status(user, tenant_slug)


@router.get("/member-memory/file/{filename}")
async def get_member_memory_file(
    filename: str,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_member_memory_file(user, filename, tenant_slug)


@router.post("/member-memory/file/{filename}")
async def save_member_memory_file(
    filename: str,
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.save_member_memory_file(
        user,
        filename,
        content=body.content,
        base_mtime=body.base_mtime,
        reason=body.reason,
        tenant_slug=tenant_slug,
    )
