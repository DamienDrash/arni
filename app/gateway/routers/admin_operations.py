from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_system_admin, require_tenant_admin_or_system
from app.gateway.services.admin_operations_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-operations"],
    dependencies=[Depends(get_current_user)],
)


class MembersSyncResponse(BaseModel):
    fetched: int
    upserted: int
    deleted: int


class ChatResetRequest(BaseModel):
    clear_verification: bool = True
    clear_contact: bool = True
    clear_history: bool = True
    clear_handoff: bool = True


class InterventionRequest(BaseModel):
    content: str
    platform: str | None = None


class TokenRequest(BaseModel):
    member_id: str
    user_id: str | None = None
    phone_number: str | None = None
    email: str | None = None


class LinkMemberRequest(BaseModel):
    member_id: str | None = None


@router.post("/members/sync", response_model=MembersSyncResponse)
async def sync_members(user: AuthContext = Depends(get_current_user)) -> dict[str, int]:
    require_tenant_admin_or_system(user)
    try:
        return await service.sync_members(user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Magicline Sync fehlgeschlagen: {str(exc)}")


@router.get("/members/stats")
async def get_members_stats(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_members_stats(user)


@router.get("/members")
async def list_members(
    limit: int = 200,
    search: str | None = None,
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.list_members(user, limit=limit, search=search)


@router.get("/members/enrichment-stats")
async def get_enrichment_stats(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_enrichment_stats(user)


@router.get("/members/{customer_id}")
async def get_member_detail(customer_id: int, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    try:
        return service.get_member_detail(user, customer_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/members/enrich-all")
async def enrich_all_members(force: bool = False, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.enqueue_enrich_all_members(user, force=force)


@router.post("/members/{customer_id}/enrich")
async def enrich_member_endpoint(
    customer_id: int,
    force: bool = False,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    result = await service.enrich_member(user, customer_id, force=force)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


@router.get("/handoffs")
async def list_active_handoffs(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return await service.list_active_handoffs(user)


@router.post("/handoffs/{user_id}/resolve")
async def resolve_handoff(user_id: str, user: AuthContext = Depends(get_current_user)) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    try:
        return await service.resolve_handoff(user, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/tokens")
async def generate_verification_token(
    req: TokenRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    try:
        return await service.generate_verification_token(
            user,
            member_id=req.member_id,
            user_id=req.user_id,
            phone_number=req.phone_number,
            email=req.email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/stats")
async def get_dashboard_stats(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_system_admin(user)
    return await service.get_dashboard_stats(user)


@router.get("/chats")
async def list_recent_chats(limit: int = 10, user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return await service.list_recent_chats(user, limit=limit)


@router.get("/chats/{user_id}/history")
async def get_chat_history(user_id: str, user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.get_chat_history(user, user_id)


@router.post("/chats/{user_id}/intervene")
async def send_intervention(
    user_id: str,
    body: InterventionRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="content is required")
    try:
        return await service.send_intervention(user, user_id=user_id, content=content, platform_value=body.platform)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/chats/{user_id}/link-member")
async def link_member_to_chat(
    user_id: str,
    body: LinkMemberRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    try:
        return service.link_member_to_chat(user, user_id, body.member_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/members/search-for-link")
async def search_members_for_link(
    q: str = "",
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.search_members_for_link(user, query_text=q)


@router.post("/chats/{user_id}/reset")
async def reset_chat(
    user_id: str,
    body: ChatResetRequest = Body(default=ChatResetRequest()),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return await service.reset_chat(
        user,
        user_id=user_id,
        clear_verification=body.clear_verification,
        clear_contact=body.clear_contact,
        clear_history=body.clear_history,
        clear_handoff=body.clear_handoff,
    )
