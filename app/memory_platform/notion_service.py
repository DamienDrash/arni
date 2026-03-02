"""Multi-tenant Notion Service – DB-backed, per-tenant Notion integration.

Replaces the in-memory singleton NotionConnector with a service that
persists credentials, sync state, and history in PostgreSQL.

OAuth Client ID / Secret are stored as **platform-level settings** in the
``settings`` table (tenant = system tenant), NOT as environment variables.
Each tenant gets their own access_token via the shared OAuth client.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.ai_config.encryption import encrypt_api_key, decrypt_api_key
from app.core.db import SessionLocal
from app.memory_platform.notion_models import (
    NotionConnectionDB,
    NotionSyncedPageDB,
    NotionSyncLogDB,
)
from app.memory_platform.connectors.notion import (
    NOTION_API_VERSION,
    NOTION_AUTH_URL,
    NOTION_TOKEN_URL,
    NOTION_API_BASE,
    NotionConnector,
)

logger = structlog.get_logger()


# ── Platform-level credential helpers ─────────────────────────────────

def _get_platform_notion_credentials() -> tuple[str, str]:
    """Read Notion OAuth Client-ID and Client-Secret from the platform
    settings table (system tenant).  Falls back to env-vars for backwards
    compatibility during migration.

    Returns (client_id, client_secret).
    """
    client_id = ""
    client_secret = ""

    try:
        from app.gateway.persistence import get_store
        store = get_store()
        sys_tid = store.get_system_tenant_id()
        client_id = store.get_setting("platform_notion_client_id", tenant_id=sys_tid) or ""
        # persistence.get_setting already decrypts sensitive keys automatically
        client_secret = store.get_setting("platform_notion_client_secret", tenant_id=sys_tid) or ""
    except Exception as exc:
        logger.warning("notion.platform_creds_from_db_failed", error=str(exc))

    # Fallback to ENV vars (backwards compat)
    if not client_id:
        client_id = os.getenv("NOTION_CLIENT_ID", "")
    if not client_secret:
        client_secret = os.getenv("NOTION_CLIENT_SECRET", "")

    return client_id, client_secret




class NotionService:
    """Stateless, DB-backed Notion service for multi-tenant environments."""

    # ── Platform Config (Admin) ────────────────────────────────────────

    def get_platform_config(self) -> dict[str, Any]:
        """Return the current platform-level Notion configuration (for admin UI)."""
        client_id, client_secret = _get_platform_notion_credentials()
        return {
            "configured": bool(client_id and client_secret),
            "client_id": client_id,
            "has_secret": bool(client_secret),
        }

    def save_platform_config(self, client_id: str, client_secret: str) -> dict[str, Any]:
        """Save platform-level Notion OAuth credentials (admin only)."""
        if not client_id:
            return {"error": "Client ID ist erforderlich"}
        
        from app.gateway.persistence import get_store
        store = get_store()
        sys_tid = store.get_system_tenant_id()
        
        # Always save client_id
        store.upsert_setting("platform_notion_client_id", client_id,
                            description="Notion OAuth Client ID", tenant_id=sys_tid)
        
        # Only update secret if a new one is provided (not KEEP_EXISTING)
        if client_secret and client_secret != "KEEP_EXISTING":
            # Note: persistence._is_sensitive_setting handles encryption automatically
            # for keys in SENSITIVE_SETTING_KEYS, so we do NOT encrypt manually here
            store.upsert_setting("platform_notion_client_secret", client_secret,
                                description="Notion OAuth Client Secret (encrypted)", tenant_id=sys_tid)
        
        logger.info("notion.platform_credentials_saved")
        return {"status": "saved", "client_id": client_id}

    # ── Connection Management ───────────────────────────────────────

    def get_connection(self, tenant_id: int, db: Session | None = None) -> NotionConnectionDB | None:
        """Get the Notion connection for a tenant."""
        close = False
        if db is None:
            db = SessionLocal()
            close = True
        try:
            return db.query(NotionConnectionDB).filter(
                NotionConnectionDB.tenant_id == tenant_id
            ).first()
        finally:
            if close:
                db.close()

    def get_status(self, tenant_id: int) -> dict[str, Any]:
        """Get the Notion connection status for a tenant."""
        # First check if platform credentials are configured
        client_id, client_secret = _get_platform_notion_credentials()
        platform_configured = bool(client_id and client_secret)

        conn = self.get_connection(tenant_id)
        if not conn:
            return {
                "connected": False,
                "platform_configured": platform_configured,
                "workspace_name": None,
                "workspace_icon": None,
                "connected_at": None,
                "last_sync_at": None,
                "last_sync_status": None,
                "webhook_active": False,
                "pages_synced": 0,
                "databases_synced": 0,
            }
        return {
            "connected": True,
            "platform_configured": platform_configured,
            "workspace_name": conn.workspace_name,
            "workspace_icon": conn.workspace_icon,
            "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
            "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
            "last_sync_status": conn.last_sync_status,
            "webhook_active": conn.webhook_active,
            "pages_synced": conn.pages_synced,
            "databases_synced": conn.databases_synced,
        }

    def get_oauth_url(self, tenant_id: int, redirect_uri: str) -> dict[str, str]:
        """Generate the Notion OAuth authorization URL.

        The Notion OAuth Client ID/Secret are platform-level settings,
        stored in the DB settings table (system tenant).
        The resulting access_token is tenant-specific and stored per-tenant.
        """
        client_id, _ = _get_platform_notion_credentials()
        if not client_id:
            return {"error": "Notion-Integration ist nicht konfiguriert. Bitte den Platform-Admin bitten, die Notion OAuth-Credentials in den Einstellungen zu hinterlegen."}

        from urllib.parse import urlencode
        params = {
            "client_id": client_id,
            "response_type": "code",
            "owner": "user",
            "redirect_uri": redirect_uri,
            "state": str(tenant_id),
        }
        return {"auth_url": f"{NOTION_AUTH_URL}?{urlencode(params)}"}

    async def exchange_code(
        self,
        tenant_id: int,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange OAuth code for access token and store in DB."""
        import httpx

        client_id, client_secret = _get_platform_notion_credentials()

        if not client_id or not client_secret:
            return {"error": "Notion OAuth-Credentials nicht konfiguriert. Bitte den Platform-Admin kontaktieren."}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                NOTION_TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(client_id, client_secret),
                headers={"Notion-Version": NOTION_API_VERSION},
            )

            if response.status_code != 200:
                logger.error("notion.oauth_exchange_failed", status=response.status_code, body=response.text)
                return {"error": f"OAuth-Austausch fehlgeschlagen: {response.status_code}"}

            data = response.json()
            access_token = data.get("access_token", "")
            workspace_id = data.get("workspace_id", "")
            workspace_name = data.get("workspace_name", "")
            bot_id = data.get("bot_id", "")

            # Store encrypted token in DB
            db = SessionLocal()
            try:
                conn = db.query(NotionConnectionDB).filter(
                    NotionConnectionDB.tenant_id == tenant_id
                ).first()

                encrypted_token = encrypt_api_key(access_token)

                if conn:
                    conn.workspace_id = workspace_id
                    conn.workspace_name = workspace_name
                    conn.access_token_enc = encrypted_token
                    conn.bot_id = bot_id
                    conn.status = "connected"
                    conn.connected_at = datetime.now(timezone.utc)
                    conn.updated_at = datetime.now(timezone.utc)
                else:
                    conn = NotionConnectionDB(
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        workspace_name=workspace_name,
                        access_token_enc=encrypted_token,
                        bot_id=bot_id,
                        status="connected",
                    )
                    db.add(conn)

                db.commit()
                logger.info("notion.connected", tenant_id=tenant_id, workspace=workspace_name)

                return {
                    "status": "connected",
                    "workspace_name": workspace_name,
                    "workspace_id": workspace_id,
                }
            finally:
                db.close()

    def disconnect(self, tenant_id: int) -> dict[str, Any]:
        """Disconnect Notion for a tenant (delete connection and synced pages)."""
        db = SessionLocal()
        try:
            db.query(NotionSyncedPageDB).filter(NotionSyncedPageDB.tenant_id == tenant_id).delete()
            db.query(NotionSyncLogDB).filter(NotionSyncLogDB.tenant_id == tenant_id).delete()
            db.query(NotionConnectionDB).filter(NotionConnectionDB.tenant_id == tenant_id).delete()
            db.commit()
            logger.info("notion.disconnected", tenant_id=tenant_id)
            return {"status": "disconnected"}
        finally:
            db.close()

    # ── Page Discovery ──────────────────────────────────────────────

    async def list_pages(self, tenant_id: int, query: str = "") -> list[dict[str, Any]]:
        """List available pages from the connected Notion workspace."""
        conn = self.get_connection(tenant_id)
        if not conn or not conn.access_token_enc:
            return []

        access_token = decrypt_api_key(conn.access_token_enc)

        # Use the existing NotionConnector for API calls
        connector = NotionConnector()
        connector._access_token = access_token
        connector._connected = True

        pages = await connector.list_pages(query=query, page_size=50)

        # Enrich with sync status from DB
        db = SessionLocal()
        try:
            synced = {
                sp.notion_page_id: sp
                for sp in db.query(NotionSyncedPageDB).filter(
                    NotionSyncedPageDB.tenant_id == tenant_id
                ).all()
            }

            result = []
            for page in pages:
                page_id = page.get("id", "")
                sp = synced.get(page_id)
                result.append({
                    "page_id": page_id,
                    "title": page.get("title", "Untitled"),
                    "type": page.get("type", "page"),
                    "url": page.get("url", ""),
                    "last_edited": page.get("last_edited_time", ""),
                    "synced": sp.sync_enabled if sp else False,
                    "sync_status": sp.sync_status if sp else "not_synced",
                    "chunk_count": sp.chunk_count if sp else 0,
                    "parent_type": "",
                    "parent_name": "",
                })
            return result
        finally:
            db.close()

    def get_synced_pages(self, tenant_id: int) -> list[dict[str, Any]]:
        """Get all synced pages for a tenant from DB."""
        db = SessionLocal()
        try:
            pages = db.query(NotionSyncedPageDB).filter(
                NotionSyncedPageDB.tenant_id == tenant_id,
                NotionSyncedPageDB.sync_enabled == True,
            ).all()
            return [
                {
                    "page_id": p.notion_page_id,
                    "title": p.title,
                    "type": p.page_type,
                    "url": p.url,
                    "sync_status": p.sync_status,
                    "chunk_count": p.chunk_count,
                    "last_edited": p.last_edited_time.isoformat() if p.last_edited_time else None,
                    "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
                    "parent_type": p.parent_type,
                    "parent_name": p.parent_name,
                    "synced": True,
                }
                for p in pages
            ]
        finally:
            db.close()

    # ── Sync Operations ─────────────────────────────────────────────

    async def sync_page(self, tenant_id: int, page_id: str, enable: bool) -> dict[str, Any]:
        """Enable or disable sync for a specific page."""
        conn = self.get_connection(tenant_id)
        if not conn:
            return {"error": "Nicht verbunden"}

        db = SessionLocal()
        try:
            sp = db.query(NotionSyncedPageDB).filter(
                NotionSyncedPageDB.tenant_id == tenant_id,
                NotionSyncedPageDB.notion_page_id == page_id,
            ).first()

            if enable:
                if not sp:
                    # Fetch page info from Notion
                    access_token = decrypt_api_key(conn.access_token_enc)
                    connector = NotionConnector()
                    connector._access_token = access_token
                    connector._connected = True

                    pages = await connector.list_pages(page_size=100)
                    page_info = next((p for p in pages if p.get("id") == page_id), {})

                    sp = NotionSyncedPageDB(
                        tenant_id=tenant_id,
                        notion_page_id=page_id,
                        title=page_info.get("title", f"Page {page_id[:8]}"),
                        page_type=page_info.get("type", "page"),
                        url=page_info.get("url", ""),
                        sync_enabled=True,
                        sync_status="pending",
                    )
                    db.add(sp)
                else:
                    sp.sync_enabled = True
                    sp.sync_status = "pending"

                db.commit()

                # Trigger immediate sync for this page
                await self._sync_single_page(tenant_id, page_id, db)

                return {"status": "enabled", "page_id": page_id}
            else:
                if sp:
                    sp.sync_enabled = False
                    sp.sync_status = "disabled"
                    db.commit()
                return {"status": "disabled", "page_id": page_id}
        finally:
            db.close()

    async def trigger_full_sync(self, tenant_id: int) -> dict[str, Any]:
        """Trigger a full sync of all enabled pages."""
        conn = self.get_connection(tenant_id)
        if not conn:
            return {"error": "Nicht verbunden"}

        db = SessionLocal()
        try:
            # Create sync log
            log = NotionSyncLogDB(
                tenant_id=tenant_id,
                sync_type="full",
                status="running",
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            log_id = log.id

            # Get all enabled pages
            enabled_pages = db.query(NotionSyncedPageDB).filter(
                NotionSyncedPageDB.tenant_id == tenant_id,
                NotionSyncedPageDB.sync_enabled == True,
            ).all()

            access_token = decrypt_api_key(conn.access_token_enc)
            connector = NotionConnector()
            connector._access_token = access_token
            connector._connected = True

            synced = 0
            total_chunks = 0
            errors = []

            for sp in enabled_pages:
                try:
                    chunks = await connector._fetch_page_content(sp.notion_page_id)
                    if chunks:
                        # Ingest into knowledge base
                        try:
                            from app.memory_platform.ingestion import get_ingestion_service
                            service = get_ingestion_service()
                            from app.memory_platform.models import DocumentSourceType
                            content = "\n\n".join([c.content for c in chunks])
                            await service.ingest_text(
                                tenant_id=tenant_id,
                                content=content,
                                title=f"[Notion] {sp.title}",
                                source_type=DocumentSourceType.NOTION_SYNC,
                                metadata={
                                    "notion_page_id": sp.notion_page_id,
                                    "notion_url": sp.url or "",
                                },
                            )
                        except Exception as ingest_err:
                            logger.warning("notion.ingest_fallback", error=str(ingest_err))

                        sp.sync_status = "synced"
                        sp.chunk_count = len(chunks)
                        sp.last_synced_at = datetime.now(timezone.utc)
                        sp.error_message = None
                        synced += 1
                        total_chunks += len(chunks)
                    else:
                        sp.sync_status = "synced"
                        sp.chunk_count = 0
                        sp.last_synced_at = datetime.now(timezone.utc)
                except Exception as exc:
                    sp.sync_status = "error"
                    sp.error_message = str(exc)[:500]
                    errors.append(f"{sp.title}: {str(exc)[:200]}")
                    logger.error("notion.sync_page_error", page_id=sp.notion_page_id, error=str(exc))

            # Update connection stats
            conn.last_sync_at = datetime.now(timezone.utc)
            conn.last_sync_status = "completed" if not errors else "partial"
            conn.last_sync_error = "; ".join(errors) if errors else None
            conn.pages_synced = synced

            # Update sync log
            sync_log = db.query(NotionSyncLogDB).filter(NotionSyncLogDB.id == log_id).first()
            if sync_log:
                sync_log.status = "completed" if not errors else "partial"
                sync_log.pages_processed = synced
                sync_log.chunks_created = total_chunks
                sync_log.completed_at = datetime.now(timezone.utc)
                sync_log.error = "; ".join(errors) if errors else None

            db.commit()

            return {
                "synced_pages": synced,
                "total_chunks": total_chunks,
                "errors": errors,
            }
        finally:
            db.close()

    async def _sync_single_page(self, tenant_id: int, page_id: str, db: Session) -> None:
        """Sync a single page (helper)."""
        conn = self.get_connection(tenant_id, db)
        if not conn:
            return

        access_token = decrypt_api_key(conn.access_token_enc)
        connector = NotionConnector()
        connector._access_token = access_token
        connector._connected = True

        sp = db.query(NotionSyncedPageDB).filter(
            NotionSyncedPageDB.tenant_id == tenant_id,
            NotionSyncedPageDB.notion_page_id == page_id,
        ).first()

        if not sp:
            return

        try:
            chunks = await connector._fetch_page_content(page_id)
            if chunks:
                try:
                    from app.memory_platform.ingestion import get_ingestion_service
                    service = get_ingestion_service()
                    from app.memory_platform.models import DocumentSourceType
                    content = "\n\n".join([c.content for c in chunks])
                    await service.ingest_text(
                        tenant_id=tenant_id,
                        content=content,
                        title=f"[Notion] {sp.title}",
                        source_type=DocumentSourceType.NOTION_SYNC,
                        metadata={"notion_page_id": page_id, "notion_url": sp.url or ""},
                    )
                except Exception as ingest_err:
                    logger.warning("notion.ingest_fallback", error=str(ingest_err))

                sp.sync_status = "synced"
                sp.chunk_count = len(chunks)
                sp.last_synced_at = datetime.now(timezone.utc)
                sp.error_message = None
            else:
                sp.sync_status = "synced"
                sp.chunk_count = 0
                sp.last_synced_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            sp.sync_status = "error"
            sp.error_message = str(exc)[:500]
            db.commit()

    # ── Sync Logs ───────────────────────────────────────────────────

    def get_sync_logs(self, tenant_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Get sync history for a tenant."""
        db = SessionLocal()
        try:
            logs = db.query(NotionSyncLogDB).filter(
                NotionSyncLogDB.tenant_id == tenant_id
            ).order_by(NotionSyncLogDB.started_at.desc()).limit(limit).all()

            return [
                {
                    "id": str(log.id),
                    "type": log.sync_type,
                    "status": log.status,
                    "pages_processed": log.pages_processed,
                    "chunks_created": log.chunks_created,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "error": log.error,
                }
                for log in logs
            ]
        finally:
            db.close()


# ── Singleton ────────────────────────────────────────────────────────

_service: NotionService | None = None


def get_notion_service() -> NotionService:
    """Return the singleton NotionService."""
    global _service
    if _service is None:
        _service = NotionService()
    return _service
