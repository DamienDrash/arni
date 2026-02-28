from typing import Any, Optional
import os
import glob
import json as _json
import asyncio
import time
import smtplib
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body, Depends, Query
from pydantic import BaseModel, Field
import structlog
from sqlalchemy import or_, func

from app.gateway.redis_bus import RedisBus
from config.settings import get_settings
from app.knowledge.ingest import ingest_tenant_knowledge, collection_name_for_slug
from app.knowledge.store import KnowledgeStore
from app.core.db import SessionLocal
from app.core.models import StudioMember, ChatSession, ChatMessage, AuditLog, Plan
from app.integrations.magicline.members_sync import sync_members_from_magicline
from app.integrations.magicline.member_enrichment import enrich_member, get_member_profile
from app.integrations.magicline.client import MagiclineClient
from app.core.auth import get_current_user, AuthContext, require_role
from app.gateway.schemas import Platform

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_user)],
)
logger = structlog.get_logger()
settings = get_settings()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KNOWLEDGE_ROOT_DIR = os.path.join(BASE_DIR, "data", "knowledge")
TENANT_KNOWLEDGE_ROOT_DIR = os.path.join(KNOWLEDGE_ROOT_DIR, "tenants")
LEGACY_MEMBER_MEMORY_DIR = os.path.join(KNOWLEDGE_ROOT_DIR, "members")
OPS_SYSTEM_PROMPT_PATH = os.path.join(BASE_DIR, "app", "prompts", "templates", "ops", "system.j2")
MEMORY_INSTRUCTIONS_PATH = os.path.join(KNOWLEDGE_ROOT_DIR, "member-memory-instructions.md")
REDACTED_SECRET_VALUE = "__REDACTED__"
SENSITIVE_SETTING_KEYS = {
    "auth_secret",
    "acp_secret",
    "telegram_bot_token",
    "telegram_webhook_secret",
    "meta_access_token",
    "meta_app_secret",
    "magicline_api_key",
    "smtp_username",
    "smtp_password",
    "postmark_server_token",
    "postmark_inbound_token",
    "twilio_auth_token",
    "credentials_encryption_key",
    "openai_api_key",
    "bridge_auth_dir",
    "billing_stripe_secret_key",
    "billing_stripe_webhook_secret",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = (key or "").strip().lower()
    if normalized in SENSITIVE_SETTING_KEYS:
        return True
    return any(token in normalized for token in ("password", "secret", "token", "api_key", "apikey"))


def _mask_if_sensitive(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if _is_sensitive_key(key) and value != "":
        return REDACTED_SECRET_VALUE
    return value


def _get_setting_with_env_fallback(
    key: str,
    env_attr: str | None = None,
    default: str = "",
    tenant_id: int | None = None,
) -> str:
    value = persistence.get_setting(key, None, tenant_id=tenant_id)
    if value is not None:
        return value
    if env_attr:
        return str(getattr(settings, env_attr, default) or default)
    return default


def _require_system_admin(user: AuthContext) -> None:
    require_role(user, {"system_admin"})


def _require_tenant_admin_or_system(user: AuthContext) -> None:
    require_role(user, {"system_admin", "tenant_admin"})


def _write_admin_audit(
    *,
    actor: AuthContext | None,
    action: str,
    category: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db = SessionLocal()
    try:
        actor_user_id = actor.user_id if actor else None
        actor_email = actor.email if actor else None
        actor_tenant_id = actor.tenant_id if actor else None
        if actor and getattr(actor, "is_impersonating", False):
            actor_user_id = getattr(actor, "impersonator_user_id", actor_user_id)
            actor_email = getattr(actor, "impersonator_email", actor_email)
            actor_tenant_id = getattr(actor, "impersonator_tenant_id", actor_tenant_id)
        db.add(
            AuditLog(
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                tenant_id=actor_tenant_id,
                action=action,
                category=category,
                target_type=target_type,
                target_id=target_id,
                details_json=_json.dumps(details or {}, ensure_ascii=False),
            )
        )
        db.commit()
    except Exception as e:
        logger.error("admin.audit_write_failed", action=action, error=str(e))
        db.rollback()
    finally:
        db.close()


def _safe_tenant_slug(user: AuthContext) -> str:
    raw = (user.tenant_slug or "system").strip().lower()
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in raw)
    cleaned = cleaned.strip("-_")
    return cleaned or "system"


def _effective_slug(user: AuthContext, tenant_slug_param: str | None) -> str:
    """Resolve the tenant slug for a request.

    system_admin: uses tenant_slug_param if provided (cross-tenant access), else own slug.
    tenant_admin/tenant_user: always own slug — param is ignored.
    """
    if user.role == "system_admin" and tenant_slug_param:
        raw = tenant_slug_param.strip().lower()
        safe = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in raw)
        safe = safe.strip("-_")
        return safe or "system"
    return _safe_tenant_slug(user)


def _resolve_tenant_id_for_slug(user: AuthContext, tenant_slug_param: str | None) -> int | None:
    """Return the tenant_id corresponding to the effective slug.

    For own tenant or non-system_admin: returns user.tenant_id directly (no DB hit).
    For system_admin viewing another tenant: looks up that tenant's id.
    """
    if user.role != "system_admin" or not tenant_slug_param:
        return user.tenant_id
    slug = _effective_slug(user, tenant_slug_param)
    if slug == _safe_tenant_slug(user):
        return user.tenant_id
    from app.core.models import Tenant as _TenantModel
    db = SessionLocal()
    try:
        t = db.query(_TenantModel).filter(_TenantModel.slug == slug).first()
        return t.id if t else user.tenant_id
    finally:
        db.close()


def _knowledge_dir_for_slug(slug: str) -> str:
    if slug == "system":
        return KNOWLEDGE_ROOT_DIR
    path = os.path.join(TENANT_KNOWLEDGE_ROOT_DIR, slug)
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        return KNOWLEDGE_ROOT_DIR
    return path


def _member_memory_dir_for_slug(slug: str) -> str:
    if slug == "system":
        os.makedirs(LEGACY_MEMBER_MEMORY_DIR, exist_ok=True)
        return LEGACY_MEMBER_MEMORY_DIR
    path = os.path.join(_knowledge_dir_for_slug(slug), "members")
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        os.makedirs(LEGACY_MEMBER_MEMORY_DIR, exist_ok=True)
        return LEGACY_MEMBER_MEMORY_DIR
    return path


def _tenant_knowledge_dir(user: AuthContext) -> str:
    if _safe_tenant_slug(user) == "system":
        return KNOWLEDGE_ROOT_DIR
    path = os.path.join(TENANT_KNOWLEDGE_ROOT_DIR, _safe_tenant_slug(user))
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        # Fallback for restrictive mount permissions.
        return KNOWLEDGE_ROOT_DIR
    return path


def _tenant_member_memory_dir(user: AuthContext) -> str:
    if _safe_tenant_slug(user) == "system":
        os.makedirs(LEGACY_MEMBER_MEMORY_DIR, exist_ok=True)
        return LEGACY_MEMBER_MEMORY_DIR
    path = os.path.join(_tenant_knowledge_dir(user), "members")
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        os.makedirs(LEGACY_MEMBER_MEMORY_DIR, exist_ok=True)
        return LEGACY_MEMBER_MEMORY_DIR
    return path


def _tenant_prompt_path(user: AuthContext, agent: str) -> str:
    default_path = os.path.join(BASE_DIR, "app", "prompts", "templates", agent, "system.j2")
    if _safe_tenant_slug(user) == "system":
        return default_path
    prompt_dir = os.path.join(_tenant_knowledge_dir(user), "prompts", agent)
    try:
        os.makedirs(prompt_dir, exist_ok=True)
    except PermissionError:
        return default_path
    return os.path.join(prompt_dir, "system.j2")


def _tenant_memory_instructions_path(user: AuthContext) -> str:
    if _safe_tenant_slug(user) == "system":
        return MEMORY_INSTRUCTIONS_PATH
    prompt_dir = os.path.join(_tenant_knowledge_dir(user), "prompts")
    try:
        os.makedirs(prompt_dir, exist_ok=True)
    except PermissionError:
        return MEMORY_INSTRUCTIONS_PATH
    return os.path.join(prompt_dir, "member-memory-instructions.md")


def _knowledge_collection_name(user: AuthContext) -> str:
    return collection_name_for_slug(_safe_tenant_slug(user))


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


@router.post("/members/sync", response_model=MembersSyncResponse)
async def sync_members(user: AuthContext = Depends(get_current_user)) -> dict[str, int]:
    """Trigger a full MEMBER sync from Magicline into local DB."""
    import threading as _threading
    _require_tenant_admin_or_system(user)
    
    try:
        started_at = datetime.now(timezone.utc).isoformat()
        result = sync_members_from_magicline(tenant_id=user.tenant_id)
        
        # Update sync status settings so UI reflects the success
        persistence.upsert_setting("magicline_last_sync_at", started_at, tenant_id=user.tenant_id)
        persistence.upsert_setting("magicline_last_sync_status", "ok", tenant_id=user.tenant_id)
        persistence.upsert_setting("magicline_last_sync_error", "", tenant_id=user.tenant_id)

        # Kick off enrichment in background
        from app.integrations.magicline.scheduler import _enrich_tenant_members
        _threading.Thread(
            target=_enrich_tenant_members,
            args=(user.tenant_id,),
            daemon=True,
            name=f"manual-enrich-t{user.tenant_id}",
        ).start()
        return result
    except ValueError as e:
        logger.warning("admin.sync_members.config_error", tenant_id=user.tenant_id, error=str(e))
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("admin.sync_members.failed", tenant_id=user.tenant_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Magicline Sync fehlgeschlagen: {str(e)}")


@router.get("/members/stats")
async def get_members_stats(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Real-time stats about synced members."""
    _require_tenant_admin_or_system(user)
    from sqlalchemy import func, and_
    from datetime import date

    db = SessionLocal()
    try:
        base_q = db.query(StudioMember).filter(StudioMember.tenant_id == user.tenant_id)
        total = base_q.count()
        today = date.today()
        new_today = base_q.filter(
            func.date(StudioMember.created_at) == today
        ).count()
        with_email = base_q.filter(
            StudioMember.email.isnot(None)
        ).count()
        with_phone = base_q.filter(
            StudioMember.phone_number.isnot(None)
        ).count()
        with_both = base_q.filter(
            and_(
                StudioMember.email.isnot(None),
                StudioMember.phone_number.isnot(None),
            )
        ).count()
        return {
            "total_members": total,
            "new_today": new_today,
            "with_email": with_email,
            "with_phone": with_phone,
            "with_both": with_both,
        }
    finally:
        db.close()


@router.get("/members")
async def list_members(
    limit: int = 200,
    search: str | None = None,
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List synced members for admin UI."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        session_rows = (
            db.query(
                ChatSession.member_id,
                func.count(ChatSession.id).label("sessions"),
                func.max(ChatSession.last_message_at).label("last_chat_at"),
            )
            .filter(ChatSession.tenant_id == user.tenant_id)
            .filter(ChatSession.member_id.isnot(None))
            .group_by(ChatSession.member_id)
            .all()
        )
        session_by_member: dict[str, dict[str, Any]] = {}
        for member_id, sessions_count, last_chat_at in session_rows:
            if not member_id:
                continue
            session_by_member[str(member_id).strip()] = {
                "chat_sessions": int(sessions_count or 0),
                "last_chat_at": last_chat_at.isoformat() if last_chat_at else None,
            }

        q = db.query(StudioMember).filter(StudioMember.tenant_id == user.tenant_id)
        if search:
            token = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    StudioMember.first_name.ilike(token),
                    StudioMember.last_name.ilike(token),
                    StudioMember.member_number.ilike(token),
                    StudioMember.email.ilike(token),
                    StudioMember.phone_number.ilike(token),
                )
            )

        rows = (
            q.order_by(StudioMember.last_name.asc(), StudioMember.first_name.asc())
            .limit(max(1, min(limit, 2000)))
            .all()
        )
        return [
            {
                "customer_id": row.customer_id,
                "member_number": row.member_number,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
                "phone_number": row.phone_number,
                "email": row.email,
                "gender": row.gender,
                "preferred_language": row.preferred_language,
                "member_since": row.member_since.isoformat() if row.member_since else None,
                "is_paused": row.is_paused,
                "pause_info": _json.loads(row.pause_info) if row.pause_info else None,
                "contract_info": _json.loads(row.contract_info) if row.contract_info else None,
                "enriched_at": row.enriched_at.isoformat() if row.enriched_at else None,
                "additional_info": _json.loads(row.additional_info) if row.additional_info else None,
                "checkin_stats": _json.loads(row.checkin_stats) if row.checkin_stats else None,
                "recent_bookings": _json.loads(row.recent_bookings) if row.recent_bookings else None,
                "verified": (
                    ((session_by_member.get((row.member_number or "").strip()) or {}).get("chat_sessions") or 0)
                    + ((session_by_member.get(str(row.customer_id)) or {}).get("chat_sessions") or 0)
                ) > 0,
                "chat_sessions": (
                    ((session_by_member.get((row.member_number or "").strip()) or {}).get("chat_sessions") or 0)
                    + ((session_by_member.get(str(row.customer_id)) or {}).get("chat_sessions") or 0)
                ),
                "last_chat_at": (
                    (session_by_member.get((row.member_number or "").strip()) or {}).get("last_chat_at")
                    or (session_by_member.get(str(row.customer_id)) or {}).get("last_chat_at")
                ),
            }
            for row in rows
        ]
    finally:
        db.close()


@router.get("/members/enrichment-stats")
async def get_enrichment_stats(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Aggregate enrichment stats: language distribution, paused count, enrichment coverage."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        base_q = db.query(StudioMember).filter(StudioMember.tenant_id == user.tenant_id)
        total = base_q.count()
        enriched = base_q.filter(StudioMember.enriched_at.isnot(None)).count()
        paused = base_q.filter(StudioMember.is_paused == True).count()
        lang_rows = (
            base_q.with_entities(StudioMember.preferred_language, func.count(StudioMember.customer_id))
            .group_by(StudioMember.preferred_language)
            .all()
        )
        languages = {(row[0] or "unknown"): row[1] for row in lang_rows}
        return {
            "total": total,
            "enriched": enriched,
            "paused": paused,
            "languages": languages,
        }
    finally:
        db.close()


@router.get("/members/{customer_id}")
async def get_member_detail(customer_id: int, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return full member profile including enrichment data."""
    _require_tenant_admin_or_system(user)
    profile = get_member_profile(customer_id, tenant_id=user.tenant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Member not found")
    return profile


@router.post("/members/enrich-all")
async def enrich_all_members(force: bool = False, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Trigger background enrichment for all members (non-blocking).

    Enqueues the members into Redis for the bulk_enrich_worker to process slowly.
    """
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        ids = [row.customer_id for row in db.query(StudioMember).filter(StudioMember.tenant_id == user.tenant_id).all()]
    finally:
        db.close()

    if not ids:
        return {"enqueued": 0, "estimated_minutes": 0}

    import redis as _redis
    from config.settings import get_settings
    r = _redis.from_url(get_settings().redis_url, decode_responses=True)
    
    queue_key = f"tenant:{user.tenant_id}:enrich_queue"
    if force:
        r.delete(queue_key)
        
    # push to list in chunks to avoid single massive command if tenant is huge
    chunk_size = 500
    for i in range(0, len(ids), chunk_size):
        r.sadd(queue_key, *ids[i:i+chunk_size])
        
    enqueued = r.scard(queue_key)
    minutes = (enqueued * 6) // 60
    
    logger.info("admin.enrich_all.enqueued", total=enqueued, minutes=minutes)
    return {"enqueued": enqueued, "estimated_minutes": minutes}


@router.post("/members/{customer_id}/enrich")
async def enrich_member_endpoint(
    customer_id: int,
    force: bool = False,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger lazy enrichment (check-in stats + recent bookings) for a member.

    Skips if cached data is fresh unless force=true.
    """
    _require_tenant_admin_or_system(user)
    import asyncio
    result = await asyncio.to_thread(enrich_member, customer_id, force, user.tenant_id)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


# We need a Redis instance. Ideally passed via dependency injection or global.
# For MVP, we'll instantiate or use the global one if possible. 
# But `admin.py` shouldn't depend on `main.py`.
# Let's verify if we can access the redis_bus from main or create a new transient connection?
# Better: Create a dependency. But for now, let's just make a helper since it's admin/low traffic.
async def get_redis():
    bus = RedisBus(redis_url=settings.redis_url)
    await bus.connect()
    return bus

# --- Knowledge Base API (US-13.3) ---

@router.get("/knowledge")
async def list_knowledge_files(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> list[str]:
    """List all markdown files in data/knowledge."""
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    knowledge_dir = _knowledge_dir_for_slug(slug)
    tenant_files = glob.glob(os.path.join(knowledge_dir, "*.md"))
    files = [os.path.basename(f) for f in tenant_files]
    # Legacy fallback for pre-tenantized global knowledge files.
    if not files and slug == "system":
        legacy_files = glob.glob(os.path.join(KNOWLEDGE_ROOT_DIR, "*.md"))
        files = [os.path.basename(f) for f in legacy_files]
    return sorted(set(files))

@router.get("/knowledge/file/{filename}")
async def get_knowledge_file(
    filename: str,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    """Read content of a knowledge file."""
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    safe_name = os.path.basename(filename)  # Path traversal protection
    path = os.path.join(_knowledge_dir_for_slug(slug), safe_name)
    if not os.path.exists(path) and slug == "system":
        # Legacy fallback
        path = os.path.join(KNOWLEDGE_ROOT_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"filename": safe_name, "content": content, "mtime": os.path.getmtime(path)}

class SaveFileRequest(BaseModel):
    content: str
    base_mtime: float | None = None
    reason: str | None = None


class MemberMemoryAnalyzeRequest(BaseModel):
    member_id: str | None = None


def _require_change_reason(reason: str | None) -> str:
    normalized = (reason or "").strip()
    if len(normalized) < 8:
        raise HTTPException(status_code=422, detail="Change reason is required (min. 8 chars)")
    return normalized


@router.post("/knowledge/file/{filename}")
async def save_knowledge_file(
    filename: str,
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    """Update file and trigger ingestion."""
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    reason = _require_change_reason(body.reason)
    safe_name = os.path.basename(filename)
    path = os.path.join(_knowledge_dir_for_slug(slug), safe_name)

    if os.path.exists(path) and body.base_mtime is not None:
        current_mtime = os.path.getmtime(path)
        if abs(current_mtime - body.base_mtime) > 1e-6:
            raise HTTPException(status_code=409, detail="Knowledge file changed since last load")

    with open(path, "w", encoding="utf-8") as f:
        f.write(body.content)
    saved_mtime = os.path.getmtime(path)
    _write_admin_audit(
        actor=user,
        action="knowledge.update",
        category="knowledge",
        target_type="knowledge_file",
        target_id=safe_name,
        details={
            "filename": safe_name,
            "reason": reason,
            "content_chars": len(body.content or ""),
            "mtime": saved_mtime,
            "tenant_slug": slug,
        },
    )

    try:
        result = ingest_tenant_knowledge(
            knowledge_dir=_knowledge_dir_for_slug(slug),
            collection_name=collection_name_for_slug(slug),
        )
        persistence.upsert_setting("knowledge_last_ingest_at", datetime.now(timezone.utc).isoformat(), tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_status", str(result.get("status", "ok")), tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_error", "", tenant_id=user.tenant_id)
        logger.info("admin.knowledge_updated", filename=safe_name, slug=slug)
        return {"status": "updated", "ingested": "true", "result": result, "mtime": saved_mtime}
    except Exception as e:
        persistence.upsert_setting("knowledge_last_ingest_at", datetime.now(timezone.utc).isoformat(), tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_status", "error", tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_error", str(e), tenant_id=user.tenant_id)
        logger.error("admin.ingest_failed", error=str(e))
        return {"status": "saved_but_ingest_failed", "error": str(e)}


@router.get("/knowledge/status")
async def get_knowledge_status(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    knowledge_dir = _knowledge_dir_for_slug(slug)
    collection_name = collection_name_for_slug(slug)
    files = glob.glob(os.path.join(knowledge_dir, "*.md"))
    vector_count = 0
    collection_error = ""
    try:
        vector_count = int(KnowledgeStore(collection_name=collection_name).count())
    except Exception as e:
        collection_error = str(e)

    last_ingest_at = persistence.get_setting("knowledge_last_ingest_at", "", tenant_id=user.tenant_id) or ""
    last_ingest_status = persistence.get_setting("knowledge_last_ingest_status", "never", tenant_id=user.tenant_id) or "never"
    last_ingest_error = persistence.get_setting("knowledge_last_ingest_error", "", tenant_id=user.tenant_id) or ""
    return {
        "knowledge_dir": knowledge_dir,
        "collection_name": collection_name,
        "files_count": len(files),
        "vector_count": vector_count,
        "collection_error": collection_error,
        "last_ingest_at": last_ingest_at,
        "last_ingest_status": last_ingest_status,
        "last_ingest_error": last_ingest_error,
    }


@router.post("/knowledge/reindex")
async def reindex_knowledge(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    started = datetime.now(timezone.utc)
    try:
        result = ingest_tenant_knowledge(
            knowledge_dir=_knowledge_dir_for_slug(slug),
            collection_name=collection_name_for_slug(slug),
        )
        status = str(result.get("status", "ok"))
        persistence.upsert_setting("knowledge_last_ingest_at", started.isoformat(), tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_status", status, tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_error", "", tenant_id=user.tenant_id)
        return {"status": status, "ran_at": started.isoformat(), "result": result}
    except Exception as e:
        persistence.upsert_setting("knowledge_last_ingest_at", started.isoformat(), tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_status", "error", tenant_id=user.tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_error", str(e), tenant_id=user.tenant_id)
        raise HTTPException(status_code=500, detail=f"Knowledge reindex failed: {e}")


@router.get("/member-memory")
async def list_member_memory_files(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> list[str]:
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    memory_dir = _member_memory_dir_for_slug(slug)
    files = glob.glob(os.path.join(memory_dir, "*.md"))
    names = [os.path.basename(f) for f in files]
    if not names and slug == "system":
        legacy = glob.glob(os.path.join(LEGACY_MEMBER_MEMORY_DIR, "*.md"))
        names = [os.path.basename(f) for f in legacy]
    return sorted(set(names))


@router.post("/member-memory/analyze-now")
async def run_member_memory_analyzer_now(
    body: MemberMemoryAnalyzeRequest = Body(default=MemberMemoryAnalyzeRequest()),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    _require_tenant_admin_or_system(user)
    from datetime import datetime, timezone
    import asyncio
    from app.memory.member_memory_analyzer import analyze_all_members, analyze_member

    started_at = datetime.now(timezone.utc)
    member_id = (body.member_id or "").strip()
    if member_id:
        # system_admin may run cross-tenant analysis; tenant_admin is scoped to their tenant
        tid = None if user.role == "system_admin" else user.tenant_id
        await asyncio.to_thread(analyze_member, member_id, tid)
        result = {"total": 1, "ok": 1, "err": 0}
    else:
        result = await asyncio.to_thread(analyze_all_members, user.tenant_id)

    status = "ok" if result.get("err", 0) == 0 else f"error:{result.get('err', 0)}"
    persistence.upsert_setting("member_memory_last_run_at", started_at.isoformat(), tenant_id=user.tenant_id)
    persistence.upsert_setting("member_memory_last_run_status", status, tenant_id=user.tenant_id)
    logger.info("admin.member_memory.analyze_now", member_id=member_id or None, **result, status=status)
    return {
        "status": status,
        "ran_at": started_at.isoformat(),
        "result": result,
    }


@router.get("/member-memory/status")
async def get_member_memory_status(
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    _require_tenant_admin_or_system(user)
    tid = _resolve_tenant_id_for_slug(user, tenant_slug)
    cron_enabled = (persistence.get_setting("member_memory_cron_enabled", "false", tenant_id=tid) or "false").strip().lower()
    cron_expr = persistence.get_setting("member_memory_cron", "0 2 * * *", tenant_id=tid) or "0 2 * * *"
    llm_enabled = (persistence.get_setting("member_memory_llm_enabled", "true", tenant_id=tid) or "true").strip().lower()
    llm_model = persistence.get_setting("member_memory_llm_model", "gpt-4o-mini", tenant_id=tid) or "gpt-4o-mini"
    last_run_at = persistence.get_setting("member_memory_last_run_at", "", tenant_id=tid) or ""
    last_run_status = persistence.get_setting("member_memory_last_run_status", "never", tenant_id=tid) or "never"
    last_run_error = ""
    if last_run_status.startswith("error:"):
        last_run_error = last_run_status.split(":", 1)[1].strip()

    return {
        "cron_enabled": cron_enabled == "true",
        "cron_expr": cron_expr,
        "llm_enabled": llm_enabled == "true",
        "llm_model": llm_model,
        "last_run_at": last_run_at,
        "last_run_status": last_run_status,
        "last_run_error": last_run_error,
    }


@router.get("/member-memory/file/{filename}")
async def get_member_memory_file(
    filename: str,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    safe_name = os.path.basename(filename)
    path = os.path.join(_member_memory_dir_for_slug(slug), safe_name)
    if not os.path.exists(path) and slug == "system":
        path = os.path.join(LEGACY_MEMBER_MEMORY_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"filename": safe_name, "content": content, "mtime": os.path.getmtime(path)}


@router.post("/member-memory/file/{filename}")
async def save_member_memory_file(
    filename: str,
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
    tenant_slug: str | None = Query(None),
) -> dict[str, Any]:
    _require_tenant_admin_or_system(user)
    slug = _effective_slug(user, tenant_slug)
    reason = _require_change_reason(body.reason)
    safe_name = os.path.basename(filename)
    path = os.path.join(_member_memory_dir_for_slug(slug), safe_name)
    if os.path.exists(path) and body.base_mtime is not None:
        current_mtime = os.path.getmtime(path)
        if abs(current_mtime - body.base_mtime) > 1e-6:
            raise HTTPException(status_code=409, detail="Member memory file changed since last load")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body.content)
    saved_mtime = os.path.getmtime(path)
    _write_admin_audit(
        actor=user,
        action="member_memory.update",
        category="knowledge",
        target_type="member_memory_file",
        target_id=safe_name,
        details={
            "filename": safe_name,
            "reason": reason,
            "content_chars": len(body.content or ""),
            "mtime": saved_mtime,
        },
    )
    logger.info("admin.member_memory_updated", filename=safe_name)
    return {"status": "updated", "mtime": saved_mtime}


@router.get("/prompts/{agent}/system")
async def get_agent_system_prompt(agent: str, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    _require_system_admin(user)
    if agent not in ["ops", "sales", "medic", "persona", "router"]:
        raise HTTPException(status_code=400, detail="Invalid agent")
    tenant_prompt_path = _tenant_prompt_path(user, agent)
    default_path = os.path.join(BASE_DIR, "app", "prompts", "templates", agent, "system.j2")
    prompt_path = tenant_prompt_path if os.path.exists(tenant_prompt_path) else default_path
    if not os.path.exists(prompt_path):
        raise HTTPException(status_code=404, detail="Prompt not found")
    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"filename": f"{agent}/system.j2", "content": content, "mtime": os.path.getmtime(prompt_path)}


@router.post("/prompts/{agent}/system")
async def save_agent_system_prompt(agent: str, body: SaveFileRequest, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    _require_system_admin(user)
    if agent not in ["ops", "sales", "medic", "persona", "router"]:
        raise HTTPException(status_code=400, detail="Invalid agent")
    reason = _require_change_reason(body.reason)
    path = _tenant_prompt_path(user, agent)
    if os.path.exists(path) and body.base_mtime is not None:
        current_mtime = os.path.getmtime(path)
        if abs(current_mtime - body.base_mtime) > 1e-6:
            raise HTTPException(status_code=409, detail="Prompt changed since last load")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body.content)
    saved_mtime = os.path.getmtime(path)
    _write_admin_audit(
        actor=user,
        action=f"prompt.{agent}.update",
        category="prompts",
        target_type="prompt_file",
        target_id=f"{agent}/system.j2",
        details={
            "reason": reason,
            "content_chars": len(body.content or ""),
            "mtime": saved_mtime,
        },
    )
    logger.info("admin.agent_system_prompt_updated", agent=agent)
    return {"status": "updated", "mtime": saved_mtime}


@router.get("/prompts/member-memory-instructions")
async def get_member_memory_instructions(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    _require_system_admin(user)
    path = _tenant_memory_instructions_path(user)
    if not os.path.exists(path):
        from app.memory.member_memory_analyzer import DEFAULT_INSTRUCTIONS
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_INSTRUCTIONS)
        except PermissionError:
            with open(MEMORY_INSTRUCTIONS_PATH, "w", encoding="utf-8") as f:
                f.write(DEFAULT_INSTRUCTIONS)
            path = MEMORY_INSTRUCTIONS_PATH
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"filename": os.path.basename(path), "content": content, "mtime": os.path.getmtime(path)}


@router.post("/prompts/member-memory-instructions")
async def save_member_memory_instructions(body: SaveFileRequest, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    _require_system_admin(user)
    reason = _require_change_reason(body.reason)
    path = _tenant_memory_instructions_path(user)
    if os.path.exists(path) and body.base_mtime is not None:
        current_mtime = os.path.getmtime(path)
        if abs(current_mtime - body.base_mtime) > 1e-6:
            raise HTTPException(status_code=409, detail="Prompt changed since last load")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body.content)
    except PermissionError:
        with open(MEMORY_INSTRUCTIONS_PATH, "w", encoding="utf-8") as f:
            f.write(body.content)
        path = MEMORY_INSTRUCTIONS_PATH
    saved_mtime = os.path.getmtime(path)
    _write_admin_audit(
        actor=user,
        action="prompt.member_memory.update",
        category="prompts",
        target_type="prompt_file",
        target_id="member-memory-instructions.md",
        details={
            "reason": reason,
            "content_chars": len(body.content or ""),
            "mtime": saved_mtime,
        },
    )
    logger.info("admin.member_memory_instructions_updated")
    return {"status": "updated", "mtime": saved_mtime}

# --- Handoff API (US-13.4) ---

@router.get("/handoffs")
async def list_active_handoffs(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """List active human_mode sessions with details."""
    _require_tenant_admin_or_system(user)
    import json
    import random

    bus = await get_redis()
    try:
        if user.role == "system_admin":
            # Legacy + tenant-scoped keys for full system visibility.
            keys = await bus.client.keys("session:*:human_mode")
            keys += await bus.client.keys("t*:human_mode:*")
        else:
            tid = user.tenant_id or 0
            keys = await bus.client.keys(f"t{tid}:human_mode:*")
            keys += await bus.client.keys("session:*:human_mode")
        results = []
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            
            # Extract user_id
            # session:{user_id}:human_mode
            parts = key.split(":")
            user_id = None
            if key.startswith("session:") and len(parts) >= 3:
                user_id = parts[1]
            elif key.startswith("t") and len(parts) >= 3:
                user_id = parts[-1]
            if user_id:
                
                # Fetch Session Details (Sprint 13)
                # We need platform to get session properly, but for now we can try to guess or just get by user_id if persistence supports it.
                # Actually persistence.get_or_create_session needs platform.
                # Let's try to peek at the session from DB by user_id only?
                # Persistence doesn't have a "get_by_user_id" without platform easily exposed unless we add it.
                # Workaround: Iterate all sessions? No, too slow.
                # Let's just try to get it. Most likely Telegram or WhatsApp.
                # Actually, `list_recent_chats` gets sessions.
                # Let's just assume we can get it or return minimal info.
                
                # Better: Let's assume Telegram for now or try both if critical.
                # Or just rely on the UI to show ID if name missing.
                # Wait, I can use `persistence.db.query(ChatSession).filter...` if I import SessionLocal.
                # But let's stick to persistence methods.
                # `get_chat_history` only needs user_id.
                # `get_recent_sessions` returns sessions.
                
                # Let's accept that we might not have name/member_id efficiently here without a join,
                # UNLESS we store that in Redis too.
                # BUT: `list_recent_chats` is fast enough. 
                # Let's just return what we have in Redis, and maybe fetch DB info if needed?
                # Actually, the user wants to see "Member ID" to know if verification is needed.
                # I'll add a quick lookup helper.
                
                session = persistence.get_session_by_user_id(user_id, tenant_id=user.tenant_id)
                if user.role != "system_admin" and not session:
                    # Never expose foreign-tenant handoffs to tenant admins.
                    continue
                token_value = await bus.client.get(f"user_token:{user_id}")
                active_token = token_value.decode("utf-8") if isinstance(token_value, bytes) else token_value

                if session and session.member_id:
                    # Verified users do not need verification tokens in escalation UI.
                    if active_token:
                        await bus.client.delete(f"user_token:{user_id}")
                        await bus.client.delete(f"token:{active_token}")
                    active_token = None
                elif not active_token:
                    # Auto-generate if missing (Sprint 13 Fix)
                    import random
                    import json
                    active_token = f"{random.randint(0, 999999):06d}"
                    token_data = {
                        "member_id": session.member_id if session else None,
                        "user_id": user_id,
                        "phone_number": session.phone_number if session else None,
                        "email": session.email if session else None,
                    }
                    await bus.client.setex(f"token:{active_token}", 86400, json.dumps(token_data))
                    await bus.client.setex(f"user_token:{user_id}", 86400, active_token)
                    logger.info("admin.token_autogen_handoff", user_id=user_id, token=active_token)
                
                results.append({
                    "user_id": user_id, 
                    "key": key,
                    "member_id": session.member_id if session else None,
                    "user_name": session.user_name if session else None,
                    "platform": session.platform if session else "unknown",
                    "active_token": active_token,
                })
                logger.info("admin.handoff_item", user_id=user_id, has_token=bool(active_token), token=active_token)
        return results
    finally:
        await bus.disconnect()

@router.post("/handoffs/{user_id}/resolve")
async def resolve_handoff(user_id: str, user: AuthContext = Depends(get_current_user)) -> dict[str, str]:
    """Remove human_mode flag for a user."""
    _require_tenant_admin_or_system(user)
    session = persistence.get_session_by_user_id(user_id, tenant_id=user.tenant_id)
    if user.role != "system_admin" and not session:
        raise HTTPException(status_code=404, detail="Handoff not found")
    bus = await get_redis()
    try:
        legacy_key = f"session:{user_id}:human_mode"
        tenant_key = f"t{user.tenant_id}:human_mode:{user_id}"
        await bus.client.delete(legacy_key)
        await bus.client.delete(tenant_key)
        token_value = await bus.client.get(f"user_token:{user_id}")
        if token_value:
            token_str = token_value.decode("utf-8") if isinstance(token_value, bytes) else str(token_value)
            await bus.client.delete(f"user_token:{user_id}")
            await bus.client.delete(f"token:{token_str}")
        logger.info("admin.handoff_resolved", user_id=user_id)
        return {"status": "resolved"}
    finally:
        await bus.disconnect()

# --- Token Verification API (Sprint 13 Polish) ---

class TokenRequest(BaseModel):
    member_id: str
    user_id: str | None = None
    phone_number: str | None = None
    email: str | None = None

@router.post("/tokens")
async def generate_verification_token(req: TokenRequest, user: AuthContext = Depends(get_current_user)) -> dict[str, str]:
    """Generate a 6-digit verification token."""
    _require_tenant_admin_or_system(user)
    if user.role != "system_admin" and req.user_id:
        session = persistence.get_session_by_user_id(req.user_id, tenant_id=user.tenant_id)
        if not session:
            raise HTTPException(status_code=404, detail="User session not found")
    import random
    import json
    
    token = f"{random.randint(0, 999999):06d}"
    
    bus = await get_redis()
    try:
        # Store token with 24h expiration
        key = f"token:{token}"
        data = {
            "member_id": req.member_id,
            "user_id": req.user_id,
            "phone_number": req.phone_number,
            "email": req.email
        }
        await bus.client.setex(key, 86400, json.dumps(data))
        if req.user_id:
            await bus.client.setex(f"user_token:{req.user_id}", 86400, token)
        logger.info("admin.token_generated", token=token, member_id=req.member_id)
        return {"token": token}
    finally:
        await bus.disconnect()

# --- Handoff API (US-13.4) ---

from app.gateway.persistence import persistence # Import from source, not main

@router.get("/stats")
async def get_dashboard_stats(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Get real-time stats from DB and Redis."""
    _require_tenant_admin_or_system(user)
    # 1. DB Stats
    db_stats = persistence.get_stats(tenant_id=user.tenant_id)
    
    # 2. Redis Stats (Active Handoffs)
    bus = await get_redis()
    active_handoffs = 0
    try:
        if user.role == "system_admin":
            keys = await bus.client.keys("session:*:human_mode")
            keys += await bus.client.keys("t*:human_mode:*")
            active_handoffs = len(keys)
        else:
            keys = await bus.client.keys(f"t{user.tenant_id}:human_mode:*")
            active_handoffs = len(keys)
    except Exception as e:
        logger.error("admin.stats_redis_failed", error=str(e))
    finally:
        await bus.disconnect()
        
    return {
        **db_stats,
        "active_handoffs": active_handoffs
    }

@router.get("/chats")
async def list_recent_chats(limit: int = 10, user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """List recent chat sessions."""
    _require_tenant_admin_or_system(user)
    sessions = persistence.get_recent_sessions(tenant_id=user.tenant_id, limit=limit)
    
    # Sprint 13.x Fix: Hydrate with active tokens from Redis
    bus = await get_redis()
    try:
        results = []
        for s in sessions:
            # Check for active token in Redis
            token_val = await bus.client.get(f"user_token:{s.user_id}")
            active_token = None
            if token_val:
                active_token = token_val.decode("utf-8") if isinstance(token_val, bytes) else token_val

            if s.member_id:
                # Verified sessions should never expose lingering verification tokens.
                if active_token:
                    await bus.client.delete(f"user_token:{s.user_id}")
                    await bus.client.delete(f"token:{active_token}")
                active_token = None
            
            # Auto-generate if missing (Sprint 13 Fix for Handoffs)
            # Only for unverified users who need it.
            if not active_token and not s.member_id:
                import random
                import json
                active_token = f"{random.randint(0, 999999):06d}"
                token_data = {
                    "member_id": None,
                    "user_id": s.user_id,
                    "phone_number": s.phone_number,
                    "email": s.email,
                }
                # Save to Redis (24h)
                await bus.client.setex(f"token:{active_token}", 86400, json.dumps(token_data))
                await bus.client.setex(f"user_token:{s.user_id}", 86400, active_token)
                logger.info("admin.token_autogen", user_id=s.user_id, token=active_token)

            results.append({
                "user_id": s.user_id,
                "platform": s.platform,
                "last_active": s.last_message_at.isoformat(),
                "is_active": s.is_active,
                # Enhanced User Data (Sprint 13)
                "user_name": s.user_name,
                "phone_number": s.phone_number,
                "email": s.email,
                "member_id": s.member_id,
                "active_token": active_token # <--- Added
            })
        return results
    finally:
        await bus.disconnect()

@router.get("/chats/{user_id}/history")
async def get_chat_history(user_id: str, user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Get message history for a user."""
    _require_tenant_admin_or_system(user)
    history = persistence.get_chat_history(user_id, tenant_id=user.tenant_id)
    return [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "metadata": msg.metadata_json
        }
        for msg in history
    ]


async def _send_admin_intervention(user_id: str, platform: Platform, content: str, tenant_id: int | None = None) -> None:
    from app.gateway.utils import send_to_user

    await send_to_user(
        user_id=user_id,
        platform=platform,
        content=content,
        metadata={"chat_id": user_id},
        tenant_id=tenant_id
    )


@router.post("/chats/{user_id}/intervene")
async def send_intervention(
    user_id: str,
    body: InterventionRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    _require_tenant_admin_or_system(user)
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="content is required")

    session = persistence.get_session_by_user_id(user_id, tenant_id=user.tenant_id)
    platform_value = (body.platform or (session.platform if session else "") or "telegram").strip().lower()
    try:
        platform = Platform(platform_value)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid platform: {platform_value}") from exc

    await _send_admin_intervention(user_id, platform, content, tenant_id=user.tenant_id)

    asyncio.create_task(asyncio.to_thread(
        persistence.save_message,
        user_id=user_id,
        role="assistant",
        content=content,
        platform=platform,
        metadata={"source": "admin", "type": "intervention"},
        tenant_id=user.tenant_id,
    ))
    logger.info("admin.intervention.sent", user_id=user_id, platform=platform.value)
    return {"status": "ok"}


class LinkMemberRequest(BaseModel):
    member_id: str | None = None  # None = unlink

@router.post("/chats/{user_id}/link-member")
async def link_member_to_chat(
    user_id: str,
    body: LinkMemberRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually link or unlink a member to a chat session."""
    _require_tenant_admin_or_system(user)
    ok = persistence.link_session_to_member(
        user_id=user_id,
        tenant_id=user.tenant_id,
        member_id=body.member_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info("admin.link_member", user_id=user_id, member_id=body.member_id)
    return {"status": "ok", "user_id": user_id, "member_id": body.member_id}


@router.get("/members/search-for-link")
async def search_members_for_link(
    q: str = "",
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Search members by name, email, phone or member_number for manual linking."""
    _require_tenant_admin_or_system(user)
    from app.core.db import SessionLocal
    from app.core.models import StudioMember
    db = SessionLocal()
    try:
        query = db.query(StudioMember).filter(StudioMember.tenant_id == user.tenant_id)
        if q.strip():
            term = f"%{q.strip()}%"
            query = query.filter(
                (StudioMember.first_name.ilike(term)) |
                (StudioMember.last_name.ilike(term)) |
                (StudioMember.email.ilike(term)) |
                (StudioMember.phone_number.ilike(term)) |
                (StudioMember.member_number.ilike(term))
            )
        members = query.limit(20).all()
        return [
            {
                "id": m.id,
                "customer_id": m.customer_id,
                "member_number": m.member_number,
                "first_name": m.first_name,
                "last_name": m.last_name,
                "email": m.email,
                "phone_number": m.phone_number,
            }
            for m in members
        ]
    finally:
        db.close()


@router.post("/chats/{user_id}/reset")
async def reset_chat(
    user_id: str,
    body: ChatResetRequest = Body(default=ChatResetRequest()),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Reset chat state/history and optionally verification/contact data."""
    _require_tenant_admin_or_system(user)
    reset_result = persistence.reset_chat(
        user_id,
        clear_verification=body.clear_verification,
        clear_contact=body.clear_contact,
        clear_history=body.clear_history,
        tenant_id=user.tenant_id,
    )

    handoff_cleared = False
    if body.clear_handoff:
        bus = await get_redis()
        try:
            key = f"session:{user_id}:human_mode"
            handoff_cleared = (await bus.client.delete(key)) > 0
        finally:
            await bus.disconnect()

    logger.info(
        "admin.chat_reset",
        user_id=user_id,
        deleted_messages=reset_result["deleted_messages"],
        clear_verification=body.clear_verification,
        clear_contact=body.clear_contact,
        clear_handoff=body.clear_handoff,
    )
    return {
        "status": "ok",
        "user_id": user_id,
        "session_found": reset_result["session_found"],
        "deleted_messages": reset_result["deleted_messages"],
        "verification_cleared": body.clear_verification,
        "contact_cleared": body.clear_contact,
        "handoff_cleared": handoff_cleared if body.clear_handoff else False,
    }

class SettingUpdate(BaseModel):
    value: str
    description: str | None = None


DEFAULT_BILLING_PLANS = [
    {"id": "starter", "name": "Starter", "priceMonthly": 149, "membersIncluded": 500, "messagesIncluded": 10000, "aiAgents": 2, "support": "Email"},
    {"id": "growth", "name": "Growth", "priceMonthly": 349, "membersIncluded": 2500, "messagesIncluded": 50000, "aiAgents": 5, "support": "Priority", "highlight": True},
    {"id": "enterprise", "name": "Enterprise", "priceMonthly": 999, "membersIncluded": 10000, "messagesIncluded": 250000, "aiAgents": 10, "support": "Dedicated CSM"},
]
DEFAULT_BILLING_PROVIDERS = [
    {"id": "stripe", "name": "Stripe", "enabled": True, "mode": "mock", "note": "Default Provider"},
    {"id": "paypal", "name": "PayPal", "enabled": False, "mode": "mock", "note": "Planned"},
    {"id": "klarna", "name": "Klarna", "enabled": False, "mode": "mock", "note": "Planned"},
]


def _parse_json_setting(key: str, default: Any, tenant_id: int | None = None) -> Any:
    raw = persistence.get_setting(key, None, tenant_id=tenant_id)
    if not raw:
        return default
    try:
        return _json.loads(raw)
    except Exception:
        logger.warning("admin.settings.json_parse_failed", key=key)
        return default


class PlansConfigUpdate(BaseModel):
    plans: list[dict[str, Any]]
    providers: list[dict[str, Any]]
    default_provider: str = "stripe"


@router.get("/plans/config")
async def get_plans_config(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Global plans/billing config (system-wide, not tenant scoped)."""
    _require_system_admin(user)
    
    # Fetch real plans from DB
    db = SessionLocal()
    plans_list = []
    try:
        plans = db.query(Plan).order_by(Plan.price_monthly_cents.asc()).all()
        plans_list = [
            {
                "id": p.slug,
                "name": p.name,
                "priceMonthly": round(p.price_monthly_cents / 100),
                "membersIncluded": p.max_members if p.max_members is not None else 999999, # Frontend expects number
                "messagesIncluded": p.max_monthly_messages if p.max_monthly_messages is not None else 999999,
                "aiAgents": 5, # Mock for now or map from features
                "support": "Email", # Mock
                "highlight": p.slug == "pro" or p.slug == "professional",
                "stripe_price_id": p.stripe_price_id
            }
            for p in plans
        ]
    finally:
        db.close()

    providers = _parse_json_setting("billing_providers_json", DEFAULT_BILLING_PROVIDERS, tenant_id=user.tenant_id)
    default_provider = persistence.get_setting("billing_default_provider", "stripe", tenant_id=user.tenant_id) or "stripe"
    return {
        "scope": "global_system",
        "plans": plans_list,
        "providers": providers,
        "default_provider": default_provider,
    }

@router.put("/plans/config")
async def update_plans_config(
    body: PlansConfigUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update global billing provider config (system-wide). Plans are read-only here."""
    _require_system_admin(user)
    
    # We only update providers and default_provider here now
    # Plans should be updated via separate endpoints if we build a Plan Editor
    providers = body.providers or []
    provider_ids = {str(p.get("id") or "").strip().lower() for p in providers}
    default_provider = (body.default_provider or "stripe").strip().lower()
    if default_provider and default_provider not in provider_ids:
        raise HTTPException(status_code=422, detail="default_provider must exist in providers")
    if not default_provider:
        default_provider = "stripe"

    persistence.upsert_setting("billing_providers_json", _json.dumps(providers, ensure_ascii=False), tenant_id=user.tenant_id)
    persistence.upsert_setting("billing_default_provider", default_provider, tenant_id=user.tenant_id)
    
    logger.info("admin.plans_config_updated", providers=len(providers), default_provider=default_provider)
    return {"status": "ok", "scope": "global_system"}


class StripeConnectorConfig(BaseModel):
    enabled: bool = False
    mode: str = "test"
    publishable_key: str | None = None
    secret_key: str | None = None
    webhook_secret: str | None = None


class BillingConnectorsUpdate(BaseModel):
    stripe: StripeConnectorConfig


@router.get("/billing/connectors")
async def get_billing_connectors(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Global billing connector config (system-wide)."""
    _require_system_admin(user)
    return {
        "scope": "global_system",
        "stripe": {
            "enabled": (persistence.get_setting("billing_stripe_enabled", "false", tenant_id=user.tenant_id) == "true"),
            "mode": persistence.get_setting("billing_stripe_mode", "test", tenant_id=user.tenant_id) or "test",
            "publishable_key": persistence.get_setting("billing_stripe_publishable_key", "", tenant_id=user.tenant_id) or "",
            "secret_key": _mask_if_sensitive("billing_stripe_secret_key", persistence.get_setting("billing_stripe_secret_key", "", tenant_id=user.tenant_id) or ""),
            "webhook_secret": _mask_if_sensitive("billing_stripe_webhook_secret", persistence.get_setting("billing_stripe_webhook_secret", "", tenant_id=user.tenant_id) or ""),
        },
    }


@router.put("/billing/connectors")
async def update_billing_connectors(
    body: BillingConnectorsUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update global billing connector config (system-wide)."""
    _require_system_admin(user)
    stripe = body.stripe
    mode = (stripe.mode or "test").strip().lower()
    if mode not in {"test", "live"}:
        raise HTTPException(status_code=422, detail="Stripe mode must be test or live")
    persistence.upsert_setting("billing_stripe_enabled", "true" if stripe.enabled else "false", tenant_id=user.tenant_id)
    persistence.upsert_setting("billing_stripe_mode", mode, tenant_id=user.tenant_id)
    if stripe.publishable_key is not None:
        persistence.upsert_setting("billing_stripe_publishable_key", stripe.publishable_key, tenant_id=user.tenant_id)
    if stripe.secret_key is not None and stripe.secret_key != REDACTED_SECRET_VALUE:
        persistence.upsert_setting("billing_stripe_secret_key", stripe.secret_key, tenant_id=user.tenant_id)
    if stripe.webhook_secret is not None and stripe.webhook_secret != REDACTED_SECRET_VALUE:
        persistence.upsert_setting("billing_stripe_webhook_secret", stripe.webhook_secret, tenant_id=user.tenant_id)
    logger.info("admin.billing_connectors_updated", provider="stripe", mode=mode, enabled=stripe.enabled)
    return {"status": "ok", "scope": "global_system"}


@router.post("/billing/connectors/stripe/test")
async def test_stripe_connector(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Live health-check against Stripe API using configured secret key."""
    _require_system_admin(user)
    secret_key = persistence.get_setting("billing_stripe_secret_key", "", tenant_id=user.tenant_id) or ""
    mode = persistence.get_setting("billing_stripe_mode", "test", tenant_id=user.tenant_id) or "test"
    if not secret_key:
        raise HTTPException(status_code=422, detail="Stripe secret key is not configured")
    if mode == "test" and not secret_key.startswith("sk_test_"):
        raise HTTPException(status_code=422, detail="Stripe mode is test but secret key is not sk_test_*")
    if mode == "live" and not secret_key.startswith("sk_live_"):
        raise HTTPException(status_code=422, detail="Stripe mode is live but secret key is not sk_live_*")

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                "https://api.stripe.com/v1/account",
                auth=(secret_key, ""),
            )
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                detail = payload.get("error", {}).get("message", "") if isinstance(payload, dict) else ""
            except Exception:
                detail = response.text[:180]
            raise HTTPException(status_code=502, detail=f"Stripe test failed ({response.status_code}): {detail or 'unknown error'}")
        data = response.json() if response.content else {}
        return {
            "status": "ok",
            "provider": "stripe",
            "mode": mode,
            "account_id": data.get("id"),
            "charges_enabled": data.get("charges_enabled"),
            "payouts_enabled": data.get("payouts_enabled"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe test failed: {e}")


@router.get("/settings")
async def get_all_settings(user: AuthContext = Depends(get_current_user)) -> list[dict]:
    """Get all settings for the current tenant (or all tenants for system_admin)."""
    _require_tenant_admin_or_system(user)
    settings = persistence.get_settings(tenant_id=user.tenant_id)
    return [
        {
            "key": s.key,
            "value": _mask_if_sensitive(s.key, s.value),
            "description": s.description,
            "tenant_id": s.tenant_id,
        }
        for s in settings
    ]


@router.put("/settings")
async def update_settings_batch(
    body: list[dict[str, Any]],
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Update multiple settings at once."""
    _require_system_admin(user)
    updated_keys = []
    for entry in body:
        key = entry.get("key")
        value = entry.get("value")
        desc = entry.get("description")
        if key:
            persistence.upsert_setting(key, str(value), desc, tenant_id=user.tenant_id)
            updated_keys.append(key)
    
    # Gold Standard: Audit Log for batch operations
    if updated_keys:
        _write_admin_audit(
            actor=user,
            action="settings.batch_update",
            category="settings",
            target_type="system_config",
            target_id="batch",
            details={
                "keys_count": len(updated_keys),
                "keys": updated_keys,
                "msg": "AI Engine or Platform settings updated via infrastructure manager."
            }
        )
        
    return {"status": "ok", "count": str(len(body))}

@router.put("/settings/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Update a setting value."""
    _require_system_admin(user)
    current_value = persistence.get_setting(key, "", tenant_id=user.tenant_id)
    next_value = body.value
    if _is_sensitive_key(key) and body.value == REDACTED_SECRET_VALUE:
        existing = persistence.get_setting(key, None, tenant_id=user.tenant_id)
        if existing is not None:
            next_value = existing

    persistence.upsert_setting(key, next_value, body.description, tenant_id=user.tenant_id)
    _write_admin_audit(
        actor=user,
        action="setting.update",
        category="settings",
        target_type="setting",
        target_id=key,
        details={
            "key": key,
            "reason": (body.description or "").strip(),
            "sensitive": _is_sensitive_key(key),
            "previous_value": REDACTED_SECRET_VALUE if _is_sensitive_key(key) and current_value else current_value,
            "next_value": REDACTED_SECRET_VALUE if _is_sensitive_key(key) and next_value else next_value,
        },
    )
    logger.info("admin.setting_updated", key=key, redacted=_is_sensitive_key(key))
    return {"status": "ok", "key": key, "value": _mask_if_sensitive(key, next_value) or ""}


@router.get("/integrations/config")
async def get_integrations_config(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return integration credentials/config; secrets are always masked."""
    _require_tenant_admin_or_system(user)
    return {
        "telegram": {
            "bot_token": _mask_if_sensitive("telegram_bot_token", _get_setting_with_env_fallback("telegram_bot_token", "telegram_bot_token", tenant_id=user.tenant_id)),
            "admin_chat_id": _get_setting_with_env_fallback("telegram_admin_chat_id", "telegram_admin_chat_id", tenant_id=user.tenant_id),
            "webhook_secret": _mask_if_sensitive("telegram_webhook_secret", _get_setting_with_env_fallback("telegram_webhook_secret", "telegram_webhook_secret", tenant_id=user.tenant_id)),
        },
        "whatsapp": {
            "mode": _get_setting_with_env_fallback("whatsapp_mode", None, "qr", tenant_id=user.tenant_id),
            "meta_verify_token": _mask_if_sensitive("meta_verify_token", _get_setting_with_env_fallback("meta_verify_token", "meta_verify_token", tenant_id=user.tenant_id)),
            "meta_access_token": _mask_if_sensitive("meta_access_token", _get_setting_with_env_fallback("meta_access_token", "meta_access_token", tenant_id=user.tenant_id)),
            "meta_app_secret": _mask_if_sensitive("meta_app_secret", _get_setting_with_env_fallback("meta_app_secret", "meta_app_secret", tenant_id=user.tenant_id)),
            "meta_phone_number_id": _get_setting_with_env_fallback("meta_phone_number_id", "meta_phone_number_id", tenant_id=user.tenant_id),
            # Automated path — no longer user-configurable
            "bridge_auth_dir": f"/app/data/whatsapp/auth_info_{_safe_tenant_slug(user)}",
        },
        "magicline": {
            "base_url": _get_setting_with_env_fallback("magicline_base_url", "magicline_base_url", tenant_id=user.tenant_id),
            "api_key": _mask_if_sensitive("magicline_api_key", _get_setting_with_env_fallback("magicline_api_key", "magicline_api_key", tenant_id=user.tenant_id)),
            "tenant_id": _get_setting_with_env_fallback("magicline_tenant_id", "magicline_tenant_id", tenant_id=user.tenant_id),
            "auto_sync_enabled": _get_setting_with_env_fallback("magicline_auto_sync_enabled", None, "false", tenant_id=user.tenant_id),
            "auto_sync_cron": _get_setting_with_env_fallback("magicline_auto_sync_cron", None, "0 */6 * * *", tenant_id=user.tenant_id),
            "last_sync_at": _get_setting_with_env_fallback("magicline_last_sync_at", None, "", tenant_id=user.tenant_id),
            "last_sync_status": _get_setting_with_env_fallback("magicline_last_sync_status", None, "never", tenant_id=user.tenant_id),
            "last_sync_error": _get_setting_with_env_fallback("magicline_last_sync_error", None, "", tenant_id=user.tenant_id),
        },
        "smtp": {
            "host": _get_setting_with_env_fallback("smtp_host", "smtp_host", tenant_id=user.tenant_id),
            "port": _get_setting_with_env_fallback("smtp_port", "smtp_port", tenant_id=user.tenant_id),
            "username": _mask_if_sensitive("smtp_username", _get_setting_with_env_fallback("smtp_username", "smtp_username", tenant_id=user.tenant_id)),
            "password": _mask_if_sensitive("smtp_password", _get_setting_with_env_fallback("smtp_password", "smtp_password", tenant_id=user.tenant_id)),
            "from_email": _get_setting_with_env_fallback("smtp_from_email", "smtp_from_email", tenant_id=user.tenant_id),
            "from_name": _get_setting_with_env_fallback("smtp_from_name", "smtp_from_name", tenant_id=user.tenant_id),
            "use_starttls": _get_setting_with_env_fallback("smtp_use_starttls", "smtp_use_starttls", "true", tenant_id=user.tenant_id),
            "verification_subject": _get_setting_with_env_fallback("verification_email_subject", None, "Dein ARIIA Verifizierungscode", tenant_id=user.tenant_id),
        },
        "email_channel": {
            "enabled": _get_setting_with_env_fallback("email_channel_enabled", None, "false", tenant_id=user.tenant_id),
            "postmark_server_token": _mask_if_sensitive("postmark_server_token", _get_setting_with_env_fallback("postmark_server_token", None, "", tenant_id=user.tenant_id)),
            "postmark_inbound_token": _mask_if_sensitive("postmark_inbound_token", _get_setting_with_env_fallback("postmark_inbound_token", None, "", tenant_id=user.tenant_id)),
            "message_stream": _get_setting_with_env_fallback("postmark_message_stream", None, "outbound", tenant_id=user.tenant_id),
            "from_email": _get_setting_with_env_fallback("email_outbound_from", None, "", tenant_id=user.tenant_id),
        },
        "sms_channel": {
            "enabled": _get_setting_with_env_fallback("sms_channel_enabled", None, "false", tenant_id=user.tenant_id),
            "twilio_account_sid": _get_setting_with_env_fallback("twilio_account_sid", None, "", tenant_id=user.tenant_id),
            "twilio_auth_token": _mask_if_sensitive("twilio_auth_token", _get_setting_with_env_fallback("twilio_auth_token", None, "", tenant_id=user.tenant_id)),
            "twilio_sms_number": _get_setting_with_env_fallback("twilio_sms_number", None, "", tenant_id=user.tenant_id),
        },
        "voice_channel": {
            "enabled": _get_setting_with_env_fallback("voice_channel_enabled", None, "false", tenant_id=user.tenant_id),
            "twilio_account_sid": _get_setting_with_env_fallback("twilio_account_sid", None, "", tenant_id=user.tenant_id),
            "twilio_auth_token": _mask_if_sensitive("twilio_auth_token", _get_setting_with_env_fallback("twilio_auth_token", None, "", tenant_id=user.tenant_id)),
            "twilio_voice_number": _get_setting_with_env_fallback("twilio_voice_number", None, "", tenant_id=user.tenant_id),
            "twilio_voice_stream_url": _get_setting_with_env_fallback("twilio_voice_stream_url", None, "", tenant_id=user.tenant_id),
        },
    }


class TelegramConfigUpdate(BaseModel):
    bot_token: str | None = None
    admin_chat_id: str | None = None
    webhook_secret: str | None = None


class WhatsAppConfigUpdate(BaseModel):
    mode: str | None = None
    meta_verify_token: str | None = None
    meta_access_token: str | None = None
    meta_app_secret: str | None = None
    meta_phone_number_id: str | None = None
    bridge_auth_dir: str | None = None


class MagiclineConfigUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    tenant_id: str | None = None
    auto_sync_enabled: str | None = None
    auto_sync_cron: str | None = None


class SmtpConfigUpdate(BaseModel):
    host: str | None = None
    port: str | None = None
    username: str | None = None
    password: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    use_starttls: str | None = None
    verification_subject: str | None = None


class IntegrationsConfigUpdate(BaseModel):
    telegram: TelegramConfigUpdate | None = None
    whatsapp: WhatsAppConfigUpdate | None = None
    magicline: MagiclineConfigUpdate | None = None
    smtp: SmtpConfigUpdate | None = None
    email_channel: dict[str, str | None] | None = None
    sms_channel: dict[str, str | None] | None = None
    voice_channel: dict[str, str | None] | None = None


class TenantPreferencesUpdate(BaseModel):
    tenant_display_name: str | None = None
    tenant_timezone: str | None = None
    tenant_locale: str | None = None
    tenant_notify_email: str | None = None
    tenant_notify_telegram: str | None = None
    tenant_escalation_sla_minutes: str | None = None
    tenant_live_refresh_seconds: str | None = None
    # White-label branding (S6)
    tenant_logo_url: str | None = None
    tenant_primary_color: str | None = None
    tenant_app_title: str | None = None
    tenant_support_email: str | None = None


def _persist_integration_key(setting_key: str, value: str | None, tenant_id: int | None = None) -> None:
    if value is None:
        return
    if _is_sensitive_key(setting_key) and value == REDACTED_SECRET_VALUE:
        return
    persistence.upsert_setting(setting_key, value, tenant_id=tenant_id)


def _store_integration_test_status(
    provider: str,
    status: str,
    detail: str = "",
    tenant_id: int | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    persistence.upsert_setting(f"integration_{provider}_last_test_at", now, tenant_id=tenant_id)
    persistence.upsert_setting(f"integration_{provider}_last_status", status, tenant_id=tenant_id)
    persistence.upsert_setting(
        f"integration_{provider}_last_detail",
        detail[:1200] if detail else "",
        tenant_id=tenant_id,
    )


def _bool_setting(
    key: str,
    env_attr: str | None = None,
    default: bool = False,
    tenant_id: int | None = None,
) -> bool:
    raw = _get_setting_with_env_fallback(
        key,
        env_attr,
        "true" if default else "false",
        tenant_id=tenant_id,
    ).strip().lower()
    return raw in {"1", "true", "yes", "on"}


@router.put("/integrations/config")
async def update_integrations_config(
    body: IntegrationsConfigUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    _require_tenant_admin_or_system(user)
    if body.telegram:
        _persist_integration_key("telegram_bot_token", body.telegram.bot_token, tenant_id=user.tenant_id)
        _persist_integration_key("telegram_admin_chat_id", body.telegram.admin_chat_id, tenant_id=user.tenant_id)
        _persist_integration_key("telegram_webhook_secret", body.telegram.webhook_secret, tenant_id=user.tenant_id)
    if body.whatsapp:
        _persist_integration_key("whatsapp_mode", body.whatsapp.mode, tenant_id=user.tenant_id)
        _persist_integration_key("meta_verify_token", body.whatsapp.meta_verify_token, tenant_id=user.tenant_id)
        _persist_integration_key("meta_access_token", body.whatsapp.meta_access_token, tenant_id=user.tenant_id)
        _persist_integration_key("meta_app_secret", body.whatsapp.meta_app_secret, tenant_id=user.tenant_id)
        _persist_integration_key("meta_phone_number_id", body.whatsapp.meta_phone_number_id, tenant_id=user.tenant_id)
        _persist_integration_key("bridge_auth_dir", body.whatsapp.bridge_auth_dir, tenant_id=user.tenant_id)
    if body.magicline:
        _persist_integration_key("magicline_base_url", body.magicline.base_url, tenant_id=user.tenant_id)
        _persist_integration_key("magicline_api_key", body.magicline.api_key, tenant_id=user.tenant_id)
        _persist_integration_key("magicline_tenant_id", body.magicline.tenant_id, tenant_id=user.tenant_id)
        _persist_integration_key("magicline_auto_sync_enabled", body.magicline.auto_sync_enabled, tenant_id=user.tenant_id)
        _persist_integration_key("magicline_auto_sync_cron", body.magicline.auto_sync_cron, tenant_id=user.tenant_id)
        # Invalidate cached client so new credentials take effect immediately
        from app.integrations.magicline import _client_instances
        _client_instances.pop(user.tenant_id, None)
        # Trigger immediate background sync + enrichment if credentials are configured
        _ml_api_key = persistence.get_setting("magicline_api_key", None, tenant_id=user.tenant_id)
        _ml_base_url = persistence.get_setting("magicline_base_url", None, tenant_id=user.tenant_id)
        if _ml_api_key and _ml_base_url:
            import threading as _threading
            from app.integrations.magicline.members_sync import sync_members_from_magicline as _ml_sync
            from app.integrations.magicline.scheduler import _enrich_tenant_members as _enrich
            _tid = user.tenant_id

            def _bg_sync_on_config_save() -> None:
                try:
                    # Refresh persistence to ensure latest DB commit is visible
                    from app.gateway.persistence import PersistenceService
                    _local_p = PersistenceService()
                    result = _ml_sync(tenant_id=_tid)
                    logger.info("admin.magicline_config_sync.completed", tenant_id=_tid, result=result)
                    _enrich(_tid)
                except Exception as _e:
                    logger.error("admin.magicline_config_sync.failed", tenant_id=_tid, error=str(_e))

            _threading.Thread(
                target=_bg_sync_on_config_save,
                daemon=True,
                name=f"cfg-sync-t{user.tenant_id}",
            ).start()
            logger.info("admin.magicline_config_sync.started", tenant_id=user.tenant_id)
    if body.smtp:
        _persist_integration_key("smtp_host", body.smtp.host, tenant_id=user.tenant_id)
        _persist_integration_key("smtp_port", body.smtp.port, tenant_id=user.tenant_id)
        _persist_integration_key("smtp_username", body.smtp.username, tenant_id=user.tenant_id)
        _persist_integration_key("smtp_password", body.smtp.password, tenant_id=user.tenant_id)
        _persist_integration_key("smtp_from_email", body.smtp.from_email, tenant_id=user.tenant_id)
        _persist_integration_key("smtp_from_name", body.smtp.from_name, tenant_id=user.tenant_id)
        _persist_integration_key("smtp_use_starttls", body.smtp.use_starttls, tenant_id=user.tenant_id)
        _persist_integration_key("verification_email_subject", body.smtp.verification_subject, tenant_id=user.tenant_id)
    if body.email_channel:
        _persist_integration_key("email_channel_enabled", body.email_channel.get("enabled"), tenant_id=user.tenant_id)
        _persist_integration_key("postmark_server_token", body.email_channel.get("postmark_server_token"), tenant_id=user.tenant_id)
        _persist_integration_key("postmark_inbound_token", body.email_channel.get("postmark_inbound_token"), tenant_id=user.tenant_id)
        _persist_integration_key("postmark_message_stream", body.email_channel.get("message_stream"), tenant_id=user.tenant_id)
        _persist_integration_key("email_outbound_from", body.email_channel.get("from_email"), tenant_id=user.tenant_id)
    if body.sms_channel:
        _persist_integration_key("sms_channel_enabled", body.sms_channel.get("enabled"), tenant_id=user.tenant_id)
        _persist_integration_key("twilio_account_sid", body.sms_channel.get("twilio_account_sid"), tenant_id=user.tenant_id)
        _persist_integration_key("twilio_auth_token", body.sms_channel.get("twilio_auth_token"), tenant_id=user.tenant_id)
        _persist_integration_key("twilio_sms_number", body.sms_channel.get("twilio_sms_number"), tenant_id=user.tenant_id)
    if body.voice_channel:
        _persist_integration_key("voice_channel_enabled", body.voice_channel.get("enabled"), tenant_id=user.tenant_id)
        _persist_integration_key("twilio_account_sid", body.voice_channel.get("twilio_account_sid"), tenant_id=user.tenant_id)
        _persist_integration_key("twilio_auth_token", body.voice_channel.get("twilio_auth_token"), tenant_id=user.tenant_id)
        _persist_integration_key("twilio_voice_number", body.voice_channel.get("twilio_voice_number"), tenant_id=user.tenant_id)
        _persist_integration_key("twilio_voice_stream_url", body.voice_channel.get("twilio_voice_stream_url"), tenant_id=user.tenant_id)

    logger.info("admin.integrations_config_updated")
    return {"status": "ok"}


@router.delete("/integrations/{provider}")
async def delete_integration_config(
    provider: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Completely wipe an integration's settings for the current tenant."""
    _require_tenant_admin_or_system(user)
    normalized = (provider or "").strip().lower()
    
    # Map friendly provider names to setting prefixes
    prefix_map = {
        "telegram": "telegram_",
        "whatsapp": "meta_", # Meta Cloud API uses meta_ prefix
        "whatsapp_bridge": "whatsapp_", # QR Bridge uses whatsapp_ prefix
        "magicline": "magicline_",
        "smtp": "smtp_",
        "email": "postmark_", # Email channel uses postmark_
        "sms": "twilio_", # Twilio used for SMS
        "voice": "twilio_voice_",
    }
    
    prefix = prefix_map.get(normalized)
    if not prefix:
        # Fallback: if no map, try using the provider name directly as prefix
        prefix = f"{normalized}_"
        
    deleted_count = persistence.delete_settings_by_prefix(prefix, tenant_id=user.tenant_id)
    
    # Specialized cleanup for hybrid keys
    if normalized == "whatsapp":
        # Also clean up the mode switch
        persistence.delete_setting("whatsapp_mode", tenant_id=user.tenant_id)
        deleted_count += 1

    _write_admin_audit(
        actor=user,
        action="integration.delete",
        category="settings",
        target_type="integration",
        target_id=normalized,
        details={"deleted_keys_count": deleted_count, "prefix": prefix},
    )
    
    logger.info("admin.integration_deleted", provider=normalized, tenant_id=user.tenant_id, count=deleted_count)
    return {"status": "ok", "deleted_count": deleted_count}


@router.get("/tenant-preferences")
async def get_tenant_preferences(user: AuthContext = Depends(get_current_user)) -> dict[str, str]:
    _require_tenant_admin_or_system(user)
    # Fall back to Tenant.name when display_name setting not yet stored
    display_name = _get_setting_with_env_fallback("tenant_display_name", None, "", tenant_id=user.tenant_id)
    if not display_name:
        from app.core.models import Tenant as TenantModel
        _db = SessionLocal()
        try:
            _t = _db.query(TenantModel).filter(TenantModel.id == user.tenant_id).first()
            if _t:
                display_name = _t.name
        finally:
            _db.close()
    return {
        "tenant_display_name": display_name,
        "tenant_timezone": _get_setting_with_env_fallback("tenant_timezone", None, "Europe/Berlin", tenant_id=user.tenant_id),
        "tenant_locale": _get_setting_with_env_fallback("tenant_locale", None, "de-DE", tenant_id=user.tenant_id),
        "tenant_notify_email": _get_setting_with_env_fallback("tenant_notify_email", None, "", tenant_id=user.tenant_id),
        "tenant_notify_telegram": _get_setting_with_env_fallback("tenant_notify_telegram", None, "", tenant_id=user.tenant_id),
        "tenant_escalation_sla_minutes": _get_setting_with_env_fallback("tenant_escalation_sla_minutes", None, "15", tenant_id=user.tenant_id),
        "tenant_live_refresh_seconds": _get_setting_with_env_fallback("tenant_live_refresh_seconds", None, "5", tenant_id=user.tenant_id),
        # White-label branding (S6)
        "tenant_logo_url": _get_setting_with_env_fallback("tenant_logo_url", None, "", tenant_id=user.tenant_id),
        "tenant_primary_color": _get_setting_with_env_fallback("tenant_primary_color", None, "#3B82F6", tenant_id=user.tenant_id),
        "tenant_app_title": _get_setting_with_env_fallback("tenant_app_title", None, "ARIIA", tenant_id=user.tenant_id),
        "tenant_support_email": _get_setting_with_env_fallback("tenant_support_email", None, "", tenant_id=user.tenant_id),
    }


@router.put("/tenant-preferences")
async def update_tenant_preferences(
    body: TenantPreferencesUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    _require_tenant_admin_or_system(user)
    payload = body.model_dump(exclude_none=True)
    for key, value in payload.items():
        persistence.upsert_setting(key, str(value), tenant_id=user.tenant_id)
    _write_admin_audit(
        actor=user,
        action="tenant.preferences.update",
        category="settings",
        target_type="tenant",
        target_id=str(user.tenant_id),
        details={"changed_keys": sorted(payload.keys())},
    )
    return {"status": "ok"}


class IntegrationTestRequest(BaseModel):
    config: dict[str, Any] | None = None

@router.post("/integrations/test/{provider}")
async def test_integration_connector(
    provider: str, 
    body: IntegrationTestRequest = Body(default=IntegrationTestRequest()),
    user: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    _require_tenant_admin_or_system(user)
    normalized = (provider or "").strip().lower()
    if normalized not in {"telegram", "whatsapp", "magicline", "smtp", "email", "sms", "voice"}:
        raise HTTPException(status_code=404, detail="Unknown integration provider")

    # Helper to get value from body (live) or DB (persisted)
    def _val(key: str, env_attr: str | None = None, default: str = "") -> str:
        if body.config:
            # Try exact key (prefixed) or shorthand (without prefix)
            val = body.config.get(key)
            if val is None:
                # e.g. look for 'bot_token' if key is 'telegram_bot_token'
                shorthand = key.replace(f"{normalized}_", "")
                val = body.config.get(shorthand)
            
            if val is not None:
                final_val = str(val or "")
                if final_val != REDACTED_SECRET_VALUE:
                    return final_val
        
        return _get_setting_with_env_fallback(key, env_attr, default, tenant_id=user.tenant_id)

    started = time.perf_counter()
    try:
        if normalized == "telegram":
            bot_token = _val("telegram_bot_token")
            if not bot_token:
                raise HTTPException(status_code=422, detail="Telegram bot token is not configured")
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            if resp.status_code == 404 or resp.status_code == 401:
                raise HTTPException(status_code=502, detail="Telegram Bot Token ungültig")
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Telegram API nicht erreichbar ({resp.status_code})")
            payload = resp.json() if resp.content else {}
            bot = payload.get("result", {}) if isinstance(payload, dict) else {}
            detail = f"Bot @{bot.get('username', 'unknown')} reachable"

        elif normalized == "whatsapp":
            mode = _val("whatsapp_mode", default="qr")
            if mode == "qr":
                health_url = _val("bridge_health_url")
                if health_url:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(health_url)
                    if resp.status_code >= 400:
                        raise HTTPException(status_code=502, detail=f"WhatsApp QR-Bridge nicht erreichbar ({resp.status_code})")
                    detail = f"QR-Bridge health OK ({resp.status_code})"
                else:
                    detail = "QR-Bridge URL not configured, but mode is QR."
            else:
                access_token = _val("meta_access_token")
                if not access_token:
                    raise HTTPException(status_code=422, detail="WhatsApp Meta Access Token nicht konfiguriert")
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.get("https://graph.facebook.com/v21.0/me", params={"access_token": access_token})
                if resp.status_code in (401, 403):
                    raise HTTPException(status_code=502, detail="WhatsApp Meta Token ungültig oder abgelaufen")
                detail = "WhatsApp Meta Graph token valid"

        elif normalized == "magicline":
            base_url = _val("magicline_base_url")
            api_key = _val("magicline_api_key")
            if not base_url or not api_key:
                raise HTTPException(status_code=422, detail="Magicline config incomplete")

            def _magicline_probe() -> dict[str, Any]:
                client = MagiclineClient(base_url=base_url, api_key=api_key, timeout=15)
                return client.studio_info()

            data = await asyncio.to_thread(_magicline_probe)
            studio = data.get("name") or data.get("studioName") or data.get("id") or "studio"
            detail = f"Magicline reachable ({studio})"

        elif normalized == "smtp":
            host = _val("smtp_host")
            port = int(_val("smtp_port") or "587")
            username = _val("smtp_username")
            password = _val("smtp_password")
            if not host or not username or not password:
                raise HTTPException(status_code=422, detail="SMTP config incomplete")

            def _smtp_probe() -> None:
                with smtplib.SMTP(host, port, timeout=20) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.login(username, password)
                    smtp.noop()

            await asyncio.to_thread(_smtp_probe)
            detail = f"SMTP login OK ({host}:{port})"
        elif normalized == "email":
            token = _val("postmark_server_token")
            if not token:
                raise HTTPException(status_code=422, detail="Postmark server token is not configured")
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://api.postmarkapp.com/server",
                    headers={"X-Postmark-Server-Token": token, "Accept": "application/json"},
                )
            if resp.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="Postmark Server Token ungültig")
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Postmark API nicht erreichbar ({resp.status_code})")
            data = resp.json() if resp.content else {}
            detail = f"Postmark reachable (server={data.get('Name', 'unknown')})"
        else:  # sms|voice
            sid = _val("twilio_account_sid")
            token = _val("twilio_auth_token")
            if not sid or not token:
                raise HTTPException(status_code=422, detail="Twilio account_sid/auth_token must be configured")
            async with httpx.AsyncClient(timeout=12.0, auth=(sid, token)) as client:
                resp = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Twilio test failed ({resp.status_code})")
            data = resp.json() if resp.content else {}
            status = data.get("status", "unknown")
            detail = f"Twilio account reachable (status={status})"
            data = resp.json() if resp.content else {}
            status = data.get("status", "unknown")
            detail = f"Twilio account reachable (status={status})"

        latency_ms = int((time.perf_counter() - started) * 1000)
        _store_integration_test_status(normalized, "ok", detail, tenant_id=user.tenant_id)
        return {
            "status": "ok",
            "provider": normalized,
            "latency_ms": latency_ms,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "detail": detail,
        }
    except HTTPException as exc:
        _store_integration_test_status(normalized, "error", str(exc.detail), tenant_id=user.tenant_id)
        raise
    except Exception as e:
        detail = f"{e.__class__.__name__}: {e}"
        _store_integration_test_status(normalized, "error", detail, tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"{normalized} test failed: {detail}")


# ─────────────────────────────────────────────────────────
# Integration Health-Check (S3.3)
# ─────────────────────────────────────────────────────────

@router.get("/integrations/health")
async def integrations_health(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return connectivity status for all configured integrations of the current tenant."""
    _require_tenant_admin_or_system(user)
    tid = user.tenant_id
    result: dict[str, Any] = {}

    # Magicline
    ml_url = _get_setting_with_env_fallback("magicline_base_url", "magicline_base_url", "", tid)
    ml_key = _get_setting_with_env_fallback("magicline_api_key", "magicline_api_key", "", tid)
    ml_studio_id = _get_setting_with_env_fallback("magicline_studio_id", "magicline_studio_id", "", tid)
    if ml_url and ml_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{ml_url.rstrip('/')}/v1/customers?page=0&size=1", headers={"X-API-KEY": ml_key})
            result["magicline"] = {
                "configured": True,
                "studio_id": ml_studio_id or "(not set)",
                "reachable": r.status_code < 400,
                "http_status": r.status_code,
            }
        except Exception as e:
            result["magicline"] = {"configured": True, "reachable": False, "error": str(e)}
    else:
        result["magicline"] = {"configured": False}

    # WhatsApp
    wa_phone_id = _get_setting_with_env_fallback("wa_phone_number_id", "meta_phone_number_id", "", tid)
    wa_token = _get_setting_with_env_fallback("wa_access_token", "meta_access_token", "", tid)
    result["whatsapp"] = {
        "configured": bool(wa_phone_id and wa_token),
        "phone_number_id": wa_phone_id or "(not set)",
        "webhook_url": f"/webhook/whatsapp/{_get_setting_with_env_fallback('tenant_slug', None, '', tid) or 'your-slug'}",
    }

    # Telegram
    tg_token = _get_setting_with_env_fallback("telegram_bot_token", "telegram_bot_token", "", tid)
    tg_chat = _get_setting_with_env_fallback("telegram_admin_chat_id", "telegram_admin_chat_id", "", tid)
    result["telegram"] = {
        "configured": bool(tg_token),
        "admin_chat_configured": bool(tg_chat),
        "webhook_url": f"/webhook/telegram/{_get_setting_with_env_fallback('tenant_slug', None, '', tid) or 'your-slug'}",
    }

    # SMTP
    smtp_host = _get_setting_with_env_fallback("smtp_host", "smtp_host", "", tid)
    smtp_user = _get_setting_with_env_fallback("smtp_username", "smtp_username", "", tid)
    if smtp_host and smtp_user:
        try:
            import smtplib
            smtp_port = int(_get_setting_with_env_fallback("smtp_port", "smtp_port", "587", tid) or 587)
            smtp_pass = _get_setting_with_env_fallback("smtp_password", "smtp_password", "", tid)
            srv = smtplib.SMTP(smtp_host, smtp_port, timeout=5)
            srv.starttls()
            srv.login(smtp_user, smtp_pass)
            srv.quit()
            result["smtp"] = {"configured": True, "reachable": True}
        except Exception as e:
            result["smtp"] = {"configured": True, "reachable": False, "error": str(e)}
    else:
        result["smtp"] = {"configured": False}

    return result


# ─────────────────────────────────────────────────────────
# Prompt Config API (S2.1)
# ─────────────────────────────────────────────────────────

class PromptConfigUpdate(BaseModel):
    studio_name: str | None = None
    studio_short_name: str | None = None
    agent_display_name: str | None = None
    studio_locale: str | None = None
    studio_timezone: str | None = None
    studio_emergency_number: str | None = None
    studio_address: str | None = None
    sales_prices_text: str | None = None
    sales_retention_rules: str | None = None
    medic_disclaimer_text: str | None = None
    persona_bio_text: str | None = None


@router.get("/prompt-config")
async def get_prompt_config(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return all prompt configuration values for the current tenant."""
    _require_tenant_admin_or_system(user)
    from app.core.prompt_builder import PROMPT_SETTINGS_KEYS, PROMPT_SETTINGS_DEFAULTS
    result: dict[str, Any] = {}
    for key in PROMPT_SETTINGS_KEYS:
        value = persistence.get_setting(key, None, tenant_id=user.tenant_id)
        result[key] = value if value is not None else PROMPT_SETTINGS_DEFAULTS.get(key, "")
    return result


@router.put("/prompt-config")
async def update_prompt_config(
    body: PromptConfigUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Update prompt configuration values for the current tenant."""
    _require_tenant_admin_or_system(user)
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    from app.core.prompt_builder import PROMPT_SETTINGS_KEYS
    for key, value in payload.items():
        if key in PROMPT_SETTINGS_KEYS:
            persistence.upsert_setting(key, str(value), tenant_id=user.tenant_id)
    _write_admin_audit(
        actor=user,
        action="prompt_config.update",
        category="settings",
        target_type="tenant",
        target_id=str(user.tenant_id),
        details={"changed_keys": sorted(payload.keys())},
    )
    return {"status": "ok", "updated": str(len(payload))}


# ─────────────────────────────────────────────────────────
# Agent Jinja2 Template API (S2.5)
# Tenant admins can customise per-agent system prompts as Jinja2 files.
# ─────────────────────────────────────────────────────────

_ALLOWED_AGENT_TEMPLATES = {"sales", "medic", "persona", "router", "ops"}


def _agent_template_path(user: AuthContext, agent: str) -> str:
    """Return the per-tenant override path for an agent template."""
    slug = _safe_tenant_slug(user)
    prompt_dir = os.path.join(TENANT_KNOWLEDGE_ROOT_DIR, slug, "prompts", agent)
    try:
        os.makedirs(prompt_dir, exist_ok=True)
    except PermissionError:
        pass
    return os.path.join(prompt_dir, "system.j2")


def _agent_default_template_path(agent: str) -> str:
    """Return the system default template path for an agent."""
    return os.path.join(BASE_DIR, "app", "prompts", "templates", agent, "system.j2")


@router.get("/prompts/agent/{agent}")
async def get_agent_template(agent: str, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Get the Jinja2 system prompt template for a specific agent.

    Returns the tenant-specific override if it exists, otherwise the system default.
    """
    _require_tenant_admin_or_system(user)
    if agent not in _ALLOWED_AGENT_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'. Allowed: {sorted(_ALLOWED_AGENT_TEMPLATES)}")

    tenant_path = _agent_template_path(user, agent)
    default_path = _agent_default_template_path(agent)
    is_custom = os.path.exists(tenant_path)
    active_path = tenant_path if is_custom else default_path

    if not os.path.exists(active_path):
        raise HTTPException(status_code=404, detail=f"No template found for agent '{agent}'")

    with open(active_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "agent": agent,
        "is_custom": is_custom,
        "filename": f"{agent}/system.j2",
        "content": content,
        "mtime": os.path.getmtime(active_path),
    }


@router.post("/prompts/agent/{agent}")
async def save_agent_template(
    agent: str,
    body: SaveFileRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Save a per-tenant Jinja2 system prompt template for a specific agent."""
    _require_tenant_admin_or_system(user)
    if agent not in _ALLOWED_AGENT_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'. Allowed: {sorted(_ALLOWED_AGENT_TEMPLATES)}")

    reason = _require_change_reason(body.reason)
    path = _agent_template_path(user, agent)

    if os.path.exists(path) and body.base_mtime is not None:
        current_mtime = os.path.getmtime(path)
        if abs(current_mtime - body.base_mtime) > 1e-6:
            raise HTTPException(status_code=409, detail="Template changed since last load")

    with open(path, "w", encoding="utf-8") as f:
        f.write(body.content)
    saved_mtime = os.path.getmtime(path)

    _write_admin_audit(
        actor=user,
        action=f"prompt.agent.{agent}.update",
        category="prompts",
        target_type="agent_template",
        target_id=f"{agent}/system.j2",
        details={"reason": reason, "content_chars": len(body.content or ""), "mtime": saved_mtime},
    )
    logger.info("admin.agent_template_saved", agent=agent, tenant_id=user.tenant_id)
    return {"status": "updated", "agent": agent, "mtime": saved_mtime}


@router.delete("/prompts/agent/{agent}")
async def reset_agent_template(agent: str, user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Delete the per-tenant Jinja2 override — falls back to system default."""
    _require_tenant_admin_or_system(user)
    if agent not in _ALLOWED_AGENT_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'.")

    path = _agent_template_path(user, agent)
    if os.path.exists(path):
        os.remove(path)
        _write_admin_audit(
            actor=user,
            action=f"prompt.agent.{agent}.reset",
            category="prompts",
            target_type="agent_template",
            target_id=f"{agent}/system.j2",
            details={"reset_to_default": True},
        )
        return {"status": "reset", "agent": agent}
    return {"status": "already_default", "agent": agent}


# ─────────────────────────────────────────────────────────
# Billing Subscription & Usage API (S4.3)
# ─────────────────────────────────────────────────────────

@router.get("/billing/subscription")
async def get_billing_subscription(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return the tenant's current subscription, plan details, and feature flags."""
    _require_tenant_admin_or_system(user)
    from app.core.models import Plan, Subscription
    db = SessionLocal()
    try:
        sub = (
            db.query(Subscription)
            .filter(Subscription.tenant_id == user.tenant_id)
            .first()
        )
        if not sub:
            # Return starter defaults when no subscription exists
            return {
                "has_subscription": False,
                "status": "free",
                "plan": {
                    "name": "Starter",
                    "slug": "starter",
                    "price_monthly_cents": 0,
                    "max_members": 500,
                    "max_monthly_messages": 1000,
                    "max_channels": 1,
                    "whatsapp_enabled": True,
                    "telegram_enabled": False,
                    "sms_enabled": False,
                    "email_channel_enabled": False,
                    "voice_enabled": False,
                    "memory_analyzer_enabled": False,
                    "custom_prompts_enabled": False,
                },
            }

        plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
        plan_data: dict[str, Any] = {}
        if plan:
            plan_data = {
                "name": plan.name,
                "slug": plan.slug,
                "price_monthly_cents": plan.price_monthly_cents,
                "max_members": plan.max_members,
                "max_monthly_messages": plan.max_monthly_messages,
                "max_channels": plan.max_channels,
                "whatsapp_enabled": plan.whatsapp_enabled,
                "telegram_enabled": plan.telegram_enabled,
                "sms_enabled": plan.sms_enabled,
                "email_channel_enabled": plan.email_channel_enabled,
                "voice_enabled": plan.voice_enabled,
                "memory_analyzer_enabled": plan.memory_analyzer_enabled,
                "custom_prompts_enabled": plan.custom_prompts_enabled,
            }

        return {
            "has_subscription": True,
            "status": sub.status,
            "stripe_subscription_id": sub.stripe_subscription_id,
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
            "plan": plan_data,
        }
    finally:
        db.close()


# ── Analytics ─────────────────────────────────────────────────────────────────

_INTENT_LABELS: dict[str, str] = {
    "preise_premium": "Preise & Mitgliedschaft",
    "preise_flex_vs_premium": "Preisvergleich Tarife",
    "oeffnungszeiten_allgemein": "Öffnungszeiten",
    "oeffnungszeiten_feiertag": "Öffnungszeiten Feiertag",
    "kurs_buchen_yoga": "Kurs buchen – Yoga",
    "kurs_buchen_spinning": "Kurs buchen – Spinning",
    "kurs_buchen_functional": "Kurs buchen – Functional",
    "abo_pausieren_urlaub": "Abo pausieren (Urlaub)",
    "abo_pausieren_verletzung": "Abo pausieren (Verletzung)",
    "kuendigung_retention": "Kündigung (Retention)",
    "kuendigung_eskaliert": "Kündigung (Eskaliert)",
    "app_login_problem": "App Login Problem",
    "trainingsberatung": "Trainingsberatung",
    "trainingsberatung_gewicht": "Trainingsberatung (Gewicht)",
    "sauna_frage": "Sauna & Wellness",
    "handtuch_schliessfach": "Handtuch & Schließfach",
    "personal_training": "Personal Training",
    "neues_mitglied_info": "Neues Mitglied Info",
    "checkin_problem": "Check-in Problem",
    "studentenrabatt": "Studentenrabatt",
    "feedback_positiv": "Positives Feedback",
    "getraenke_nutrition": "Getränke & Nutrition",
    "price_inquiry_en": "Price Inquiry (EN)",
    "class_booking_en": "Class Booking (EN)",
    "pause_membership_en": "Pause Membership (EN)",
}

_CHANNEL_NAMES: dict[str, str] = {
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "email": "E-Mail",
    "sms": "SMS",
    "phone": "Telefon",
}


def _parse_msg_meta(meta_str: str | None) -> dict[str, Any]:
    if not meta_str:
        return {}
    try:
        return _json.loads(meta_str)  # type: ignore[return-value]
    except Exception:
        return {}


def _time_ago(ts: datetime) -> str:
    """Human-readable 'vor X Min/Std' label."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - ts
    total_seconds = int(diff.total_seconds())
    if total_seconds < 60:
        return f"vor {total_seconds}s"
    if total_seconds < 3600:
        return f"vor {total_seconds // 60} Min"
    if total_seconds < 86400:
        return f"vor {total_seconds // 3600} Std"
    return f"vor {total_seconds // 86400} Tagen"


def _initials(name: str | None) -> str:
    if not name:
        return "??"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()





@router.get("/analytics/channels")
async def analytics_channels(
    days: int = 30,
    tenant_slug: str | None = Query(None),
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Per-channel ticket count and AI-resolution rate."""
    _require_tenant_admin_or_system(user)
    effective_tid = _resolve_tenant_id_for_slug(user, tenant_slug)
    days = min(max(days, 1), 90)

    from datetime import timedelta
    from collections import defaultdict
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).replace(tzinfo=None)

    db = SessionLocal()
    try:
        msgs = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.tenant_id == effective_tid,
                ChatMessage.role == "assistant",
                ChatMessage.timestamp >= since,
            )
            .all()
        )

        ch_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "resolved": 0})
        for msg in msgs:
            meta = _parse_msg_meta(msg.metadata_json)
            ch = meta.get("channel", "unknown")
            ch_stats[ch]["count"] += 1
            if not meta.get("escalated"):
                ch_stats[ch]["resolved"] += 1

        _CH_ORDER = ["whatsapp", "telegram", "email", "sms", "phone"]
        result = []
        for ch in _CH_ORDER:
            if ch not in ch_stats:
                continue
            v = ch_stats[ch]
            total = v["count"]
            resolved = v["resolved"]
            esc = total - resolved
            ai_rate = round(resolved / max(total, 1) * 100)
            result.append({
                "ch": ch,
                "name": _CHANNEL_NAMES.get(ch, ch.capitalize()),
                "tickets": total,
                "aiRate": ai_rate,
                "esc": f"{100 - ai_rate}%",
            })
        # Add any unexpected channels
        for ch, v in ch_stats.items():
            if ch not in _CH_ORDER:
                total = v["count"]
                ai_rate = round(v["resolved"] / max(total, 1) * 100)
                result.append({
                    "ch": ch,
                    "name": _CHANNEL_NAMES.get(ch, ch.capitalize()),
                    "tickets": total,
                    "aiRate": ai_rate,
                    "esc": f"{100 - ai_rate}%",
                })
        return result
    finally:
        db.close()


@router.get("/analytics/sessions/recent")
async def analytics_recent_sessions(
    limit: int = 10,
    tenant_slug: str | None = Query(None),
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Recent chat sessions with last-message snippet for the dashboard table."""
    _require_tenant_admin_or_system(user)
    effective_tid = _resolve_tenant_id_for_slug(user, tenant_slug)
    limit = min(max(limit, 1), 50)

    db = SessionLocal()
    try:
        sessions = (
            db.query(ChatSession)
            .filter(ChatSession.tenant_id == effective_tid)
            .order_by(ChatSession.last_message_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for i, s in enumerate(sessions):
            # Get last assistant message for this session
            last_msg = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.session_id == s.user_id,
                    ChatMessage.tenant_id == effective_tid,
                    ChatMessage.role == "assistant",
                )
                .order_by(ChatMessage.timestamp.desc())
                .first()
            )
            # Get last user message for the issue/question text
            last_user_msg = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.session_id == s.user_id,
                    ChatMessage.tenant_id == effective_tid,
                    ChatMessage.role == "user",
                )
                .order_by(ChatMessage.timestamp.desc())
                .first()
            )
            # Count messages
            msg_count = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.session_id == s.user_id,
                    ChatMessage.tenant_id == effective_tid,
                )
                .count()
            )

            meta = _parse_msg_meta(last_msg.metadata_json if last_msg else None)
            channel = meta.get("channel") or (s.platform or "unknown").lower()
            confidence_raw = meta.get("confidence")
            confidence = round(float(confidence_raw) * 100) if confidence_raw is not None else 0
            escalated = meta.get("escalated", False)
            status = "escalated" if escalated else "resolved"

            issue_text = ""
            if last_user_msg:
                issue_text = (last_user_msg.content or "")[:120]

            last_active = s.last_message_at
            if last_active and last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)

            member_name = s.user_name or s.email or s.phone_number or f"User {s.user_id[-6:]}"
            result.append({
                "id": f"T-{s.id:04d}",
                "channel": channel,
                "member": member_name,
                "avatar": _initials(member_name),
                "issue": issue_text,
                "confidence": confidence,
                "status": status,
                "time": _time_ago(last_active) if last_active else "–",
                "messages": msg_count,
            })
        return result
    finally:
        db.close()


@router.get("/billing/usage")
async def get_billing_usage(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Return the tenant's current-month usage counters."""
    _require_tenant_admin_or_system(user)
    from datetime import datetime, timezone
    from app.core.feature_gates import FeatureGate
    now = datetime.now(timezone.utc)
    gate = FeatureGate(tenant_id=user.tenant_id)
    usage = gate._get_current_usage()
    plan_data = gate._plan_data
    max_msgs = plan_data.get("max_monthly_messages")
    total_msgs = usage.get("messages_inbound", 0) + usage.get("messages_outbound", 0)
    return {
        "period": {"year": now.year, "month": now.month},
        "messages_inbound": usage.get("messages_inbound", 0),
        "messages_outbound": usage.get("messages_outbound", 0),
        "messages_total": total_msgs,
        "messages_limit": max_msgs,
        "messages_pct": round(total_msgs / int(max_msgs) * 100, 1) if max_msgs and int(max_msgs) > 0 else None,
        "active_members": usage.get("active_members", 0),
        "llm_tokens_used": usage.get("llm_tokens_used", 0),
    }


# ─── Analytics Aggregation Endpoints (K1) ────────────────────────────────────
# Server-side replacements for the N+1 client pattern in chat-analytics.ts.
# All aggregation runs in the DB; tenant_id-scoped for full isolation.

def _parse_msg_meta_safe(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return _json.loads(raw)
    except Exception:
        return {}


@router.get("/analytics/overview")
async def get_analytics_overview(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """KPI overview: tickets 24h/30d, AI resolution rate, confidence, channels.

    Replaces the N+1 pattern (up to 220 HTTP calls) in chat-analytics.ts with a
    single DB query pass per time window.
    """
    _require_tenant_admin_or_system(user)
    from datetime import timedelta
    from sqlalchemy import text as _text

    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).replace(tzinfo=None)
    cutoff_30d = (now - timedelta(days=30)).replace(tzinfo=None)
    cutoff_60d = (now - timedelta(days=60)).replace(tzinfo=None)

    db = SessionLocal()
    try:
        def _fetch_window(since: datetime) -> list[dict]:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.tenant_id == user.tenant_id,
                    ChatMessage.role == "assistant",
                    ChatMessage.timestamp >= since,
                )
                .all()
            )
            result = []
            for r in rows:
                meta = _parse_msg_meta_safe(r.metadata_json)
                conf_raw = meta.get("confidence")
                conf: float | None = None
                if isinstance(conf_raw, (int, float)):
                    conf = float(conf_raw)
                elif isinstance(conf_raw, str):
                    try:
                        conf = float(conf_raw)
                    except ValueError:
                        pass
                result.append({
                    "escalated": meta.get("escalated") is True or meta.get("escalated") == "true",
                    "confidence": conf,
                    "channel": str(meta.get("channel") or "unknown").lower(),
                    "ts": r.timestamp,
                })
            return result

        msgs_24h = _fetch_window(cutoff_24h)
        msgs_30d = _fetch_window(cutoff_30d)
        msgs_60d = _fetch_window(cutoff_60d)

        # Only keep 60d that are OUTSIDE 30d window for comparison
        msgs_prev_30d = [m for m in msgs_60d if m["ts"] < cutoff_30d]

        escal_24h = sum(1 for m in msgs_24h if m["escalated"])
        total_24h = len(msgs_24h)
        confs = [m["confidence"] for m in msgs_24h if m["confidence"] is not None]
        conf_avg = round((sum(confs) / len(confs)) * 100, 1) if confs else 0.0
        channels_24h: dict[str, int] = {}
        for m in msgs_24h:
            channels_24h[m["channel"]] = channels_24h.get(m["channel"], 0) + 1

        conf_dist = [
            {"range": "90–100%", "count": sum(1 for c in confs if c >= 0.9)},
            {"range": "75–89%",  "count": sum(1 for c in confs if 0.75 <= c < 0.9)},
            {"range": "50–74%",  "count": sum(1 for c in confs if 0.5 <= c < 0.75)},
            {"range": "<50%",    "count": sum(1 for c in confs if c < 0.5)},
        ]
        conf_total = len(confs)
        tickets_30d = len(msgs_30d)
        tickets_prev = len(msgs_prev_30d)
        ai_rate = round(((total_24h - escal_24h) / max(1, total_24h)) * 100, 1)
        month_trend = round(((tickets_30d - tickets_prev) / max(1, tickets_prev)) * 100, 1)
        return {
            "tickets_24h": total_24h,
            "resolved_24h": total_24h - escal_24h,
            "escalated_24h": escal_24h,
            "ai_resolution_rate": ai_rate,
            "escalation_rate": round((escal_24h / max(1, total_24h)) * 100, 1),
            "confidence_avg": conf_avg,
            "confidence_high_pct": round(sum(1 for c in confs if c >= 0.9) / max(1, conf_total) * 100),
            "confidence_low_pct": round(sum(1 for c in confs if c < 0.5) / max(1, conf_total) * 100),
            "confidence_distribution": conf_dist,
            "channels_24h": channels_24h,
            "tickets_30d": tickets_30d,
            "tickets_prev_30d": tickets_prev,
            "month_trend_pct": month_trend,
        }
    finally:
        db.close()


@router.get("/analytics/satisfaction")
async def analytics_satisfaction(
    tenant_slug: str | None = Query(None),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate member feedback (average rating and count)."""
    _require_tenant_admin_or_system(user)
    effective_tid = _resolve_tenant_id_for_slug(user, tenant_slug)

    from app.core.models import MemberFeedback
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        result = db.query(
            func.avg(MemberFeedback.rating).label("avg_rating"),
            func.count(MemberFeedback.id).label("total_feedback")
        ).filter(MemberFeedback.tenant_id == effective_tid).first()
        
        avg_raw = result.avg_rating if result and result.avg_rating else 0.0
        total = result.total_feedback if result and result.total_feedback else 0
        
        return {
            "average": round(float(avg_raw), 1),
            "total": total
        }
    finally:
        db.close()


@router.get("/analytics/hourly")
async def get_analytics_hourly(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Stündlicher Verlauf der letzten 24h: KI-gelöst vs. eskaliert."""
    _require_tenant_admin_or_system(user)
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).replace(tzinfo=None)
    db = SessionLocal()
    try:
        rows = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.tenant_id == user.tenant_id,
                ChatMessage.role == "assistant",
                ChatMessage.timestamp >= cutoff,
            )
            .all()
        )
        hourly: dict[int, dict[str, int]] = {h: {"aiResolved": 0, "escalated": 0} for h in range(24)}
        for r in rows:
            ts = r.timestamp
            if ts and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            h = ts.hour if ts else 0
            meta = _parse_msg_meta_safe(r.metadata_json)
            if meta.get("escalated") is True or meta.get("escalated") == "true":
                hourly[h]["escalated"] += 1
            else:
                hourly[h]["aiResolved"] += 1
        return [
            {"hour": f"{h:02d}:00", "aiResolved": hourly[h]["aiResolved"], "escalated": hourly[h]["escalated"]}
            for h in range(24)
        ]
    finally:
        db.close()


@router.get("/analytics/weekly")
async def get_analytics_weekly(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Täglicher Verlauf der letzten 7 Tage."""
    _require_tenant_admin_or_system(user)
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    db = SessionLocal()
    try:
        rows = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.tenant_id == user.tenant_id,
                ChatMessage.role == "assistant",
                ChatMessage.timestamp >= cutoff,
            )
            .all()
        )
        DAY_DE = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"]
        daily: dict[str, dict[str, int]] = {}
        for r in rows:
            ts = r.timestamp
            if ts and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            day_key = ts.strftime("%Y-%m-%d") if ts else ""
            if not day_key:
                continue
            if day_key not in daily:
                daily[day_key] = {"tickets": 0, "escalated": 0}
            daily[day_key]["tickets"] += 1
            meta = _parse_msg_meta_safe(r.metadata_json)
            if meta.get("escalated") is True or meta.get("escalated") == "true":
                daily[day_key]["escalated"] += 1

        result = []
        for i in range(7):
            d = now - timedelta(days=6 - i)
            key = d.strftime("%Y-%m-%d")
            rec = daily.get(key, {"tickets": 0, "escalated": 0})
            result.append({
                "day": DAY_DE[d.weekday() % 7],
                "date": key,
                "tickets": rec["tickets"],
                "resolved": rec["tickets"] - rec["escalated"],
                "escalated": rec["escalated"],
            })
        return result
    finally:
        db.close()


@router.get("/analytics/intents")
async def get_analytics_intents(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Top-8 Support-Intents der letzten 30 Tage mit AI-Lösungsrate."""
    _require_tenant_admin_or_system(user)
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    db = SessionLocal()
    try:
        rows = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.tenant_id == user.tenant_id,
                ChatMessage.role == "assistant",
                ChatMessage.timestamp >= cutoff,
            )
            .all()
        )
        intent_stats: dict[str, dict[str, int]] = {}
        for r in rows:
            meta = _parse_msg_meta_safe(r.metadata_json)
            intent = str(meta.get("intent") or "unknown").strip() or "unknown"
            if intent not in intent_stats:
                intent_stats[intent] = {"count": 0, "resolved": 0}
            intent_stats[intent]["count"] += 1
            if not (meta.get("escalated") is True or meta.get("escalated") == "true"):
                intent_stats[intent]["resolved"] += 1

        sorted_intents = sorted(intent_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:8]
        return [
            {
                "intent": intent,
                "label": intent.replace("_", " ").title(),
                "count": s["count"],
                "aiRate": round((s["resolved"] / max(1, s["count"])) * 100),
            }
            for intent, s in sorted_intents
        ]
    finally:
        db.close()

@router.get("/audit")
async def get_audit_logs(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    user: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Fetch audit logs for the current tenant (SaaS compliance)."""
    _require_tenant_admin_or_system(user)
    db = SessionLocal()
    try:
        q = db.query(AuditLog).filter(AuditLog.tenant_id == user.tenant_id)
        total = q.count()
        rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "items": [
                {
                    "id": r.id,
                    "actor_user_id": r.actor_user_id,
                    "actor_email": r.actor_email,
                    "action": r.action,
                    "category": r.category,
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "details": _json.loads(r.details_json) if r.details_json else {},
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        }
    finally:
        db.close()


# ─── Platform LLM Health & Governance (SaaS level) ───────────────────────────

PREDEFINED_PROVIDERS = [
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_models": ["gpt-4o", "gpt-4o-mini", "o1-preview", "o1-mini"]
    },
    {
        "id": "groq",
        "name": "Groq Cloud",
        "base_url": "https://api.groq.com/openai/v1",
        "default_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    },
    {
        "id": "anthropic",
        "name": "Anthropic (via Proxy/Shim)",
        "base_url": "https://api.anthropic.com/v1",
        "default_models": ["claude-3-5-sonnet-20240620", "claude-3-haiku-20240307"]
    },
    {
        "id": "custom",
        "name": "Custom OpenAI-Compatible",
        "base_url": "",
        "default_models": []
    }
]

@router.get("/platform/llm/predefined")
async def get_predefined_providers(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    _require_system_admin(user)
    return PREDEFINED_PROVIDERS

class LlmProviderConfig(BaseModel):
    id: str
    name: str
    base_url: str
    models: list[str]
    api_key: Optional[str] = None # Only used for transport in PUT/POST

@router.get("/platform/llm/providers")
async def get_platform_llm_providers(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    _require_system_admin(user)
    providers_json = persistence.get_setting("platform_llm_providers_json", tenant_id=user.tenant_id) or "[]"
    providers = _json.loads(providers_json)
    
    # Enrich with health status (cached or fresh)
    # For simplicity in this step, we just return the list. 
    # Health checks are triggered explicitly via /test or /status.
    return providers

@router.post("/platform/llm/providers")
async def save_platform_llm_provider(
    body: LlmProviderConfig,
    user: AuthContext = Depends(get_current_user)
) -> dict[str, str]:
    _require_system_admin(user)
    providers_json = persistence.get_setting("platform_llm_providers_json", tenant_id=user.tenant_id) or "[]"
    providers = _json.loads(providers_json)
    
    # Update or Add
    existing = next((p for p in providers if p["id"] == body.id), None)
    new_provider = {
        "id": body.id,
        "name": body.name,
        "base_url": body.base_url,
        "models": body.models
    }
    
    if existing:
        providers = [p if p["id"] != body.id else new_provider for p in providers]
    else:
        providers.append(new_provider)
        
    persistence.upsert_setting("platform_llm_providers_json", _json.dumps(providers), tenant_id=user.tenant_id)
    
    # Save Key separately if provided
    if body.api_key and body.api_key != REDACTED_SECRET_VALUE:
        persistence.upsert_setting(f"platform_llm_key_{body.id}", body.api_key, tenant_id=user.tenant_id)
        
    return {"status": "ok"}

@router.delete("/platform/llm/providers/{provider_id}")
async def delete_platform_llm_provider(
    provider_id: str,
    user: AuthContext = Depends(get_current_user)
) -> dict[str, str]:
    _require_system_admin(user)
    providers_json = persistence.get_setting("platform_llm_providers_json", tenant_id=user.tenant_id) or "[]"
    providers = _json.loads(providers_json)
    
    providers = [p for p in providers if p["id"] != provider_id]
    persistence.upsert_setting("platform_llm_providers_json", _json.dumps(providers), tenant_id=user.tenant_id)
    
    # Optional: Delete the key too
    # persistence.delete_setting(f"platform_llm_key_{provider_id}") # Need to implement delete in persistence
    
    return {"status": "ok"}

@router.post("/platform/llm/test-config")
async def test_llm_config(
    body: LlmProviderConfig,
    user: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Test a provider configuration without saving it."""
    _require_system_admin(user)
    from app.swarm.llm import LLMClient
    
    api_key = body.api_key
    if api_key == REDACTED_SECRET_VALUE:
        # Load existing key if testing an edit
        api_key = persistence.get_setting(f"platform_llm_key_{body.id}", tenant_id=user.tenant_id)
        
    if not api_key:
        return {"status": "error", "error": "No API key provided"}
        
    client = LLMClient()
    model = body.models[0] if body.models else "gpt-4o-mini"
    return await client.check_health(body.base_url, api_key, model)

@router.get("/platform/llm/status")
async def get_platform_llm_status(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Health check for all platform-configured LLM providers."""
    _require_system_admin(user)
    from app.gateway.persistence import persistence
    from app.swarm.llm import LLMClient
    
    providers_json = persistence.get_setting("platform_llm_providers_json", tenant_id=user.tenant_id) or "[]"
    providers = _json.loads(providers_json)
    
    client = LLMClient()
    results = []
    
    for p in providers:
        p_id = p.get("id")
        key_setting = f"platform_llm_key_{p_id}"
        api_key = persistence.get_setting(key_setting, tenant_id=user.tenant_id)
        
        if not api_key:
            results.append({**p, "health": "error", "error": "No platform key configured"})
            continue
            
        # Test the first model in the list
        model = p.get("models", ["gpt-4o-mini"])[0]
        health = await client.check_health(p.get("base_url"), api_key, model)
        results.append({
            **p,
            "health": health["status"],
            "latency": health.get("latency", 0),
            "error": health.get("error")
        })
        
    return results


@router.put("/platform/llm/key/{provider_id}")
async def update_platform_llm_key(
    provider_id: str,
    key: str = Body(..., embed=True),
    user: AuthContext = Depends(get_current_user)
) -> dict[str, str]:
    """Securely store a platform-wide API key for an LLM provider."""
    _require_system_admin(user)
    from app.gateway.persistence import persistence
    
    setting_key = f"platform_llm_key_{provider_id.lower()}"
    persistence.upsert_setting(setting_key, key, tenant_id=user.tenant_id)
    
    _write_admin_audit(
        actor=user,
        action="platform.llm_key.update",
        category="security",
        target_type="llm_provider",
        target_id=provider_id,
        details={"provider": provider_id}
    )
    return {"status": "ok"}


# ─── Platform Email Test (SaaS level) ────────────────────────────────────────

class SmtpTestRequest(BaseModel):
    host: str
    port: int
    user: str
    pass_: str = Field(..., alias="pass")
    from_name: str
    from_addr: str
    recipient: str

@router.post("/platform/email/test")
async def test_platform_email(
    body: SmtpTestRequest,
    user: AuthContext = Depends(get_current_user)
) -> dict[str, Any]:
    """Test SMTP configuration by sending a real email."""
    _require_system_admin(user)
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    # Handle redaction
    effective_pass = body.pass_
    if effective_pass == REDACTED_SECRET_VALUE:
        effective_pass = persistence.get_setting("platform_email_smtp_pass", tenant_id=user.tenant_id)
    
    if not effective_pass:
        return {"status": "error", "error": "No SMTP password provided"}

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{body.from_name} <{body.from_addr}>"
        msg['To'] = body.recipient
        msg['Subject'] = "ARIIA Platform SMTP Test"
        
        content = f"Dies ist ein Test der ARIIA SaaS Plattform SMTP-Konfiguration.\n\nZeitstempel: {datetime.now(timezone.utc).isoformat()}\nHost: {body.host}\nUser: {body.user}"
        msg.attach(MIMEText(content, 'plain'))

        def _send():
            with smtplib.SMTP(body.host, body.port, timeout=15) as server:
                server.starttls()
                server.login(body.user, effective_pass)
                server.send_message(msg)
        
        await asyncio.to_thread(_send)
        return {"status": "ok", "message": f"Test-Mail erfolgreich an {body.recipient} gesendet."}
    except Exception as e:
        logger.error("admin.smtp_test_failed", error=str(e))
        return {"status": "error", "error": str(e)}


# ─── WhatsApp QR Proxy (SaaS level) ──────────────────────────────────────────

@router.get("/platform/whatsapp/qr")
async def get_whatsapp_qr(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    """Retrieve the live QR code from the WhatsApp bridge for the current tenant."""
    _require_tenant_admin_or_system(user)
    
    # In a multi-tenant bridge, we would pass the tenant identifier.
    # For now, we use the global bridge URL from settings or a default.
    bridge_url = persistence.get_setting("bridge_qr_url") or "http://localhost:3000/qr"
    
    return {
        "status": "ok",
        "qr_url": bridge_url,
        "tenant_slug": _safe_tenant_slug(user)
    }

@router.get("/platform/whatsapp/qr-image")
async def get_whatsapp_qr_image(user: AuthContext = Depends(get_current_user)):
    """Get QR code image from WAHA bridge for WhatsApp pairing."""
    _require_tenant_admin_or_system(user)
    from fastapi.responses import Response
    
    slug = _safe_tenant_slug(user)
    waha_url = persistence.get_setting("waha_api_url", tenant_id=user.tenant_id) or "http://ariia-whatsapp-bridge:3000"
    waha_key = persistence.get_setting("waha_api_key", tenant_id=user.tenant_id) or "ariia-waha-secret"
    # WAHA Core only supports 'default' session name. Multi-tenancy requires WAHA PLUS.
    session_name = "default"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Ensure session exists
            sessions_resp = await client.get(
                f"{waha_url}/api/sessions",
                headers={"X-Api-Key": waha_key}
            )
            if sessions_resp.status_code == 200:
                sessions = sessions_resp.json()
                session_names = [s["name"] for s in sessions]
                if session_name not in session_names:
                    # Create session with dynamic webhook for this tenant
                    # Use internal docker networking (ariia-core:8000)
                    webhook_url = f"http://ariia-core:8000/webhook/waha/{slug}"
                    await client.post(
                        f"{waha_url}/api/sessions/start",
                        headers={"X-Api-Key": waha_key, "Content-Type": "application/json"},
                        json={
                            "name": session_name,
                            "config": {
                                "webhooks": [
                                    {
                                        "url": webhook_url,
                                        "events": ["message"],
                                        "hmac": waha_key
                                    }
                                ]
                            }
                        }
                    )
                    import asyncio
                    await asyncio.sleep(5)
                else:
                    # Check if already connected
                    for s in sessions:
                        if s["name"] == session_name and s.get("status") == "WORKING":
                            raise HTTPException(status_code=404, detail="CONNECTED")
            
            # 2. Get QR code as PNG (with retry)
            qr_resp = None
            for _ in range(2):
                qr_resp = await client.get(
                    f"{waha_url}/api/{session_name}/auth/qr",
                    headers={"X-Api-Key": waha_key, "Accept": "image/png"}
                )
                if qr_resp.status_code == 200 and qr_resp.headers.get("content-type", "").startswith("image/"):
                    break
                import asyncio
                await asyncio.sleep(2)
            
            if qr_resp and qr_resp.status_code == 200 and qr_resp.headers.get("content-type", "").startswith("image/"):
                return Response(content=qr_resp.content, media_type="image/png")
            elif qr_resp and (qr_resp.status_code == 404 or b"QR code" not in qr_resp.content):
                raise HTTPException(status_code=404, detail="NO_QR_FOUND")
            else:
                raise HTTPException(status_code=502, detail="QR-Code konnte nicht geladen werden")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin.qr_proxy_failed", error=str(e))
        raise HTTPException(status_code=502, detail="WhatsApp Bridge Fehler")

@router.post("/platform/whatsapp/reset")
async def reset_whatsapp_session(user: AuthContext = Depends(get_current_user)):
    """Force-reset the WhatsApp session by terminating it in WAHA bridge."""
    _require_tenant_admin_or_system(user)
    
    waha_url = persistence.get_setting("waha_api_url", tenant_id=user.tenant_id) or "http://ariia-whatsapp-bridge:3000"
    waha_key = persistence.get_setting("waha_api_key", tenant_id=user.tenant_id) or "ariia-waha-secret"
    session_name = "default"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Delete the session
            await client.post(
                f"{waha_url}/api/sessions/stop",
                headers={"X-Api-Key": waha_key, "Content-Type": "application/json"},
                json={"name": session_name, "logout": True}
            )
            # Give it a moment to cleanup
            import asyncio
            await asyncio.sleep(2)
            
        return {"status": "ok", "message": "WhatsApp Sitzung zurückgesetzt. Bitte QR-Code neu laden."}
    except Exception as e:
        logger.error("admin.whatsapp.reset_failed", error=str(e))
        return {"status": "ok", "message": "Reset-Anfrage an Bridge gesendet."}
