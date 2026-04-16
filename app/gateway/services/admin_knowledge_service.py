from __future__ import annotations

import asyncio
import glob
import os
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.domains.identity.models import Tenant
from app.gateway.admin_shared import safe_tenant_slug, write_admin_audit
from app.gateway.persistence import persistence
from app.knowledge.ingest import collection_name_for_slug, ingest_tenant_knowledge
from app.knowledge.store import KnowledgeStore
from app.shared.db import session_scope

logger = structlog.get_logger()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
KNOWLEDGE_ROOT_DIR = os.path.join(BASE_DIR, "data", "knowledge")
TENANT_KNOWLEDGE_ROOT_DIR = os.path.join(KNOWLEDGE_ROOT_DIR, "tenants")
LEGACY_MEMBER_MEMORY_DIR = os.path.join(KNOWLEDGE_ROOT_DIR, "members")


class AdminKnowledgeService:
    @staticmethod
    def effective_slug(user: AuthContext, tenant_slug_param: str | None) -> str:
        if user.role == "system_admin" and tenant_slug_param:
            raw = tenant_slug_param.strip().lower()
            cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in raw)
            cleaned = cleaned.strip("-_")
            return cleaned or "system"
        return safe_tenant_slug(user)

    def resolve_tenant_id_for_slug(self, user: AuthContext, tenant_slug_param: str | None) -> int | None:
        if user.role != "system_admin" or not tenant_slug_param:
            return user.tenant_id
        slug = self.effective_slug(user, tenant_slug_param)
        if slug == safe_tenant_slug(user):
            return user.tenant_id
        with session_scope() as db:
            tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
            return tenant.id if tenant else user.tenant_id

    @staticmethod
    def knowledge_dir_for_slug(slug: str) -> str:
        if slug == "system":
            return KNOWLEDGE_ROOT_DIR
        path = os.path.join(TENANT_KNOWLEDGE_ROOT_DIR, slug)
        try:
            os.makedirs(path, exist_ok=True)
        except PermissionError:
            return KNOWLEDGE_ROOT_DIR
        return path

    def member_memory_dir_for_slug(self, slug: str) -> str:
        if slug == "system":
            os.makedirs(LEGACY_MEMBER_MEMORY_DIR, exist_ok=True)
            return LEGACY_MEMBER_MEMORY_DIR
        path = os.path.join(self.knowledge_dir_for_slug(slug), "members")
        try:
            os.makedirs(path, exist_ok=True)
        except PermissionError:
            os.makedirs(LEGACY_MEMBER_MEMORY_DIR, exist_ok=True)
            return LEGACY_MEMBER_MEMORY_DIR
        return path

    @staticmethod
    def require_change_reason(reason: str | None) -> str:
        normalized = (reason or "").strip()
        if len(normalized) < 8:
            raise HTTPException(status_code=422, detail="Change reason is required (min. 8 chars)")
        return normalized

    @staticmethod
    def persist_knowledge_ingest_status(
        *,
        tenant_id: int | None,
        status: str,
        error: str = "",
        when: datetime | None = None,
    ) -> None:
        stamped = (when or datetime.now(timezone.utc)).isoformat()
        persistence.upsert_setting("knowledge_last_ingest_at", stamped, tenant_id=tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_status", status, tenant_id=tenant_id)
        persistence.upsert_setting("knowledge_last_ingest_error", error, tenant_id=tenant_id)

    def list_knowledge_files(self, user: AuthContext, tenant_slug: str | None) -> list[str]:
        slug = self.effective_slug(user, tenant_slug)
        knowledge_dir = self.knowledge_dir_for_slug(slug)
        files = [os.path.basename(path) for path in glob.glob(os.path.join(knowledge_dir, "*.md"))]
        if not files and slug == "system":
            files = [os.path.basename(path) for path in glob.glob(os.path.join(KNOWLEDGE_ROOT_DIR, "*.md"))]
        return sorted(set(files))

    def get_knowledge_file(self, user: AuthContext, filename: str, tenant_slug: str | None) -> dict[str, Any]:
        slug = self.effective_slug(user, tenant_slug)
        safe_name = os.path.basename(filename)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        path = os.path.join(self.knowledge_dir_for_slug(slug), safe_name)
        if not os.path.exists(path) and slug == "system":
            path = os.path.join(KNOWLEDGE_ROOT_DIR, safe_name)
        if not os.path.exists(path):
            return {"filename": safe_name, "content": "", "mtime": None, "new": True}
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        return {"filename": safe_name, "content": content, "mtime": os.path.getmtime(path), "new": False}

    def save_knowledge_file(
        self,
        user: AuthContext,
        filename: str,
        *,
        content: str,
        base_mtime: float | None,
        reason: str | None,
        tenant_slug: str | None,
    ) -> dict[str, Any]:
        slug = self.effective_slug(user, tenant_slug)
        normalized_reason = self.require_change_reason(reason)
        safe_name = os.path.basename(filename)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        path = os.path.join(self.knowledge_dir_for_slug(slug), safe_name)

        if os.path.exists(path) and base_mtime is not None:
            current_mtime = os.path.getmtime(path)
            if abs(current_mtime - base_mtime) > 1e-6:
                raise HTTPException(status_code=409, detail="Knowledge file changed since last load")

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        saved_mtime = os.path.getmtime(path)
        write_admin_audit(
            actor=user,
            action="knowledge.update",
            category="knowledge",
            target_type="knowledge_file",
            target_id=safe_name,
            details={
                "filename": safe_name,
                "reason": normalized_reason,
                "content_chars": len(content or ""),
                "mtime": saved_mtime,
                "tenant_slug": slug,
            },
        )

        try:
            result = ingest_tenant_knowledge(tenant_slug=slug)
            self.persist_knowledge_ingest_status(
                tenant_id=user.tenant_id,
                status=str(result.get("status", "ok")),
            )
            logger.info("admin.knowledge_updated", filename=safe_name, slug=slug)
            return {"status": "updated", "ingested": "true", "result": result, "mtime": saved_mtime}
        except Exception as exc:
            self.persist_knowledge_ingest_status(tenant_id=user.tenant_id, status="error", error=str(exc))
            logger.error("admin.ingest_failed", error=str(exc))
            return {"status": "saved_but_ingest_failed", "error": str(exc)}

    def delete_knowledge_file(self, user: AuthContext, filename: str, tenant_slug: str | None) -> dict[str, Any]:
        slug = self.effective_slug(user, tenant_slug)
        safe_name = os.path.basename(filename)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        path = os.path.join(self.knowledge_dir_for_slug(slug), safe_name)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="File not found")
        os.remove(path)
        write_admin_audit(
            actor=user,
            action="knowledge.delete",
            category="knowledge",
            target_type="knowledge_file",
            target_id=safe_name,
            details={"filename": safe_name, "tenant_slug": slug},
        )
        try:
            ingest_tenant_knowledge(tenant_slug=slug)
            self.persist_knowledge_ingest_status(tenant_id=user.tenant_id, status="ok")
        except Exception as exc:
            logger.error("admin.ingest_failed_after_delete", error=str(exc))
        logger.info("admin.knowledge_deleted", filename=safe_name, slug=slug)
        return {"status": "deleted", "filename": safe_name}

    def get_knowledge_status(self, user: AuthContext, tenant_slug: str | None) -> dict[str, Any]:
        slug = self.effective_slug(user, tenant_slug)
        knowledge_dir = self.knowledge_dir_for_slug(slug)
        collection_name = collection_name_for_slug(slug)
        files = glob.glob(os.path.join(knowledge_dir, "*.md"))
        vector_count = 0
        collection_error = ""
        try:
            vector_count = int(KnowledgeStore(collection_name=collection_name).count())
        except Exception as exc:
            collection_error = str(exc)

        return {
            "knowledge_dir": knowledge_dir,
            "collection_name": collection_name,
            "files_count": len(files),
            "vector_count": vector_count,
            "collection_error": collection_error,
            "last_ingest_at": persistence.get_setting("knowledge_last_ingest_at", "", tenant_id=user.tenant_id) or "",
            "last_ingest_status": persistence.get_setting("knowledge_last_ingest_status", "never", tenant_id=user.tenant_id) or "never",
            "last_ingest_error": persistence.get_setting("knowledge_last_ingest_error", "", tenant_id=user.tenant_id) or "",
        }

    def reindex_knowledge(self, user: AuthContext, tenant_slug: str | None) -> dict[str, Any]:
        slug = self.effective_slug(user, tenant_slug)
        started = datetime.now(timezone.utc)
        try:
            result = ingest_tenant_knowledge(tenant_slug=slug)
            status = str(result.get("status", "ok"))
            self.persist_knowledge_ingest_status(tenant_id=user.tenant_id, status=status, when=started)
            return {"status": status, "ran_at": started.isoformat(), "result": result}
        except Exception as exc:
            self.persist_knowledge_ingest_status(tenant_id=user.tenant_id, status="error", error=str(exc), when=started)
            raise HTTPException(status_code=500, detail=f"Knowledge reindex failed: {exc}")

    def list_member_memory_files(self, user: AuthContext, tenant_slug: str | None) -> list[str]:
        slug = self.effective_slug(user, tenant_slug)
        files = [os.path.basename(path) for path in glob.glob(os.path.join(self.member_memory_dir_for_slug(slug), "*.md"))]
        if not files and slug == "system":
            files = [os.path.basename(path) for path in glob.glob(os.path.join(LEGACY_MEMBER_MEMORY_DIR, "*.md"))]
        return sorted(set(files))

    async def run_member_memory_analyzer_now(self, user: AuthContext, member_id: str | None) -> dict[str, Any]:
        from app.memory.member_memory_analyzer import analyze_all_members, analyze_member

        started_at = datetime.now(timezone.utc)
        normalized_member_id = (member_id or "").strip()
        if normalized_member_id:
            tenant_id = None if user.role == "system_admin" else user.tenant_id
            await asyncio.to_thread(analyze_member, normalized_member_id, tenant_id)
            result = {"total": 1, "ok": 1, "err": 0}
        else:
            result = await asyncio.to_thread(analyze_all_members, user.tenant_id)

        status = "ok" if result.get("err", 0) == 0 else f"error:{result.get('err', 0)}"
        persistence.upsert_setting("member_memory_last_run_at", started_at.isoformat(), tenant_id=user.tenant_id)
        persistence.upsert_setting("member_memory_last_run_status", status, tenant_id=user.tenant_id)
        logger.info("admin.member_memory.analyze_now", member_id=normalized_member_id or None, **result, status=status)
        return {"status": status, "ran_at": started_at.isoformat(), "result": result}

    def get_member_memory_status(self, user: AuthContext, tenant_slug: str | None) -> dict[str, Any]:
        tenant_id = self.resolve_tenant_id_for_slug(user, tenant_slug)
        last_run_status = persistence.get_setting("member_memory_last_run_status", "never", tenant_id=tenant_id) or "never"
        return {
            "cron_enabled": (persistence.get_setting("member_memory_cron_enabled", "false", tenant_id=tenant_id) or "false").strip().lower() == "true",
            "cron_expr": persistence.get_setting("member_memory_cron", "0 2 * * *", tenant_id=tenant_id) or "0 2 * * *",
            "llm_enabled": (persistence.get_setting("member_memory_llm_enabled", "true", tenant_id=tenant_id) or "true").strip().lower() == "true",
            "llm_model": persistence.get_setting("member_memory_llm_model", "gpt-4o-mini", tenant_id=tenant_id) or "gpt-4o-mini",
            "last_run_at": persistence.get_setting("member_memory_last_run_at", "", tenant_id=tenant_id) or "",
            "last_run_status": last_run_status,
            "last_run_error": last_run_status.split(":", 1)[1].strip() if last_run_status.startswith("error:") else "",
        }

    def get_member_memory_file(self, user: AuthContext, filename: str, tenant_slug: str | None) -> dict[str, Any]:
        slug = self.effective_slug(user, tenant_slug)
        safe_name = os.path.basename(filename)
        path = os.path.join(self.member_memory_dir_for_slug(slug), safe_name)
        if not os.path.exists(path) and slug == "system":
            path = os.path.join(LEGACY_MEMBER_MEMORY_DIR, safe_name)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="File not found")
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        return {"filename": safe_name, "content": content, "mtime": os.path.getmtime(path)}

    def save_member_memory_file(
        self,
        user: AuthContext,
        filename: str,
        *,
        content: str,
        base_mtime: float | None,
        reason: str | None,
        tenant_slug: str | None,
    ) -> dict[str, Any]:
        slug = self.effective_slug(user, tenant_slug)
        normalized_reason = self.require_change_reason(reason)
        safe_name = os.path.basename(filename)
        path = os.path.join(self.member_memory_dir_for_slug(slug), safe_name)
        if os.path.exists(path) and base_mtime is not None:
            current_mtime = os.path.getmtime(path)
            if abs(current_mtime - base_mtime) > 1e-6:
                raise HTTPException(status_code=409, detail="Member memory file changed since last load")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        saved_mtime = os.path.getmtime(path)
        write_admin_audit(
            actor=user,
            action="member_memory.update",
            category="knowledge",
            target_type="member_memory_file",
            target_id=safe_name,
            details={
                "filename": safe_name,
                "reason": normalized_reason,
                "content_chars": len(content or ""),
                "mtime": saved_mtime,
            },
        )
        logger.info("admin.member_memory_updated", filename=safe_name)
        return {"status": "updated", "mtime": saved_mtime}


service = AdminKnowledgeService()
