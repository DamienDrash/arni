"""app/gateway/routers/member_memory_admin.py — Member Memory Admin API.

Endpoints:
    GET  /admin/member-memory    → List member memory entries for the current tenant
"""
from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import get_db
from app.core.models import ChatSession, Tenant

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/member-memory", tags=["member-memory"])

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
LEGACY_MEMORY_DIR = os.path.join(BASE_DIR, "data", "knowledge", "members")
TENANT_MEMORY_ROOT = os.path.join(BASE_DIR, "data", "knowledge", "tenants")


def _memory_dir_for_tenant(tenant_slug: str | None) -> str:
    if not tenant_slug or tenant_slug == "system":
        return LEGACY_MEMORY_DIR
    safe = "".join(
        ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in tenant_slug
    ).strip("-_") or "system"
    return os.path.join(TENANT_MEMORY_ROOT, safe, "members")


@router.get("")
async def list_member_memory(
    limit: int = Query(50, ge=1, le=200),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Listet Member-Memory-Einträge für den aktuellen Tenant."""
    require_role(user, {"system_admin", "tenant_admin"})

    try:
        # Resolve tenant slug
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_slug = (tenant.slug if tenant and tenant.slug else None)

        memory_dir = _memory_dir_for_tenant(tenant_slug)

        entries = []
        if os.path.isdir(memory_dir):
            files = sorted(
                (f for f in os.listdir(memory_dir) if f.endswith(".md")),
                key=lambda f: os.path.getmtime(os.path.join(memory_dir, f)),
                reverse=True,
            )
            for filename in files[:limit]:
                member_id = filename[:-3]  # strip .md
                filepath = os.path.join(memory_dir, filename)
                stat = os.stat(filepath)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content_preview = fh.read(500)
                except Exception as e:
                    logger.warning("member_memory_admin.read_preview_failed", filename=filename, error=str(e))
                    content_preview = ""
                entries.append(
                    {
                        "member_id": member_id,
                        "filename": filename,
                        "last_updated": stat.st_mtime,
                        "size_bytes": stat.st_size,
                        "content_preview": content_preview,
                    }
                )

        # Also query active member IDs from DB for the tenant
        known_member_ids = set(
            row.member_id
            for row in db.query(ChatSession.member_id)
            .filter(
                ChatSession.tenant_id == user.tenant_id,
                ChatSession.member_id.isnot(None),
            )
            .distinct()
            .all()
            if row.member_id
        )

        return {
            "tenant_id": user.tenant_id,
            "tenant_slug": tenant_slug,
            "memory_dir": memory_dir,
            "entries": entries,
            "known_member_count": len(known_member_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("member_memory_admin.list_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Interner Serverfehler")
