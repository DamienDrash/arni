import structlog
import threading
import json
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.domains.identity.models import Tenant
from app.domains.knowledge.models import IngestionJob, IngestionJobStatus
from app.domains.platform.models import Setting
from app.domains.support.models import ChatMessage, ChatSession
from app.core.integration_models import TenantIntegration
from app.core.db import engine, Base
from app.gateway.schemas import Platform
from app.gateway.persistence_repository import persistence_repo
from app.core.crypto import encrypt_value, decrypt_value
from app.integrations.pii_filter import mask_pii
from app.shared.db import open_session, session_scope

logger = structlog.get_logger()

# ─── Platform-Level Governance (ONLY System Tenant) ───────────────────────────
GLOBAL_SYSTEM_SETTING_KEYS = {
    "system_name",
    "notification_email",
    "maintenance_mode",
    
    # AI Engine Infrastructure
    "platform_llm_providers_json", 
    "platform_llm_default_provider",
    "platform_llm_default_model",
    # Platform-wide API Keys (referenced by provider ID)
    "platform_llm_key_openai",
    "platform_llm_key_groq",
    "platform_llm_key_anthropic",
    
    # Platform Communication
    "platform_email_smtp_host",
    "platform_email_smtp_port",
    "platform_email_smtp_user",
    "platform_email_smtp_pass",
    "platform_email_from_name",
    "platform_email_from_addr",
    
    # Global Compliance & Privacy
    "platform_pii_masking_enabled",
    "platform_pii_rules_json",
    "platform_data_retention_days",
    "platform_audit_retention_days",
    
    # Global Observability
    "platform_langfuse_public_key",
    "platform_langfuse_secret_key",
    "platform_langfuse_host",
    
    # Language Governance
    "platform_available_languages", # JSON list: ["de", "en", "bg"]
    "platform_default_language",   # "en"
    
    # Gateway / Public URL
    "gateway_public_url",
    
    # Notion Integration
    "platform_notion_client_id",
    "platform_notion_client_secret",
    
    # Billing Governance
    "billing_default_provider",
    "billing_plans_json",
    "billing_stripe_enabled",
    "billing_stripe_publishable_key",
    "billing_stripe_secret_key",
    "billing_stripe_webhook_secret",
}

# ─── Sensitive Keys (Encrypted at Rest) ───────────────────────────────────────
SENSITIVE_SETTING_KEYS = {
    "openai_api_key",
    "elevenlabs_api_key",
    "magicline_api_key",
    "smtp_password",
    "billing_stripe_secret_key",
    "meta_access_token",
    "meta_app_secret",
    "telegram_bot_token",
    "telegram_webhook_secret",
    "platform_email_smtp_pass",
    "platform_langfuse_secret_key",
    "platform_llm_key_openai",
    "platform_llm_key_groq",
    "platform_llm_key_anthropic",
    "platform_notion_client_secret",
}

# Ensure tables exist
Base.metadata.create_all(bind=engine)

class PersistenceService:
    def __init__(self):
        self._lock = threading.RLock()

    @property
    def db(self) -> Session:
        """Return a dedicated sync session for legacy explicit call sites."""
        return open_session()

    def _resolve_tenant_id(self, tenant_id: int | None) -> int:
        if tenant_id is not None:
            return int(tenant_id)
        # Legacy global settings calls still exist in tests and compatibility paths.
        # Treat missing tenant context as an explicit system-scope access.
        return self.get_system_tenant_id()

    def get_system_tenant_id(self) -> int:
        with self._lock:
            with session_scope() as db:
                tenant = persistence_repo.get_tenant_by_slug(db, "system")
                if not tenant:
                    tenant = Tenant(slug="system", name="ARIIA System")
                    db.add(tenant)
                    db.commit()
                    db.refresh(tenant)
                return int(tenant.id)

    def is_global_system_setting(self, key: str) -> bool:
        return (key or "").strip().lower() in GLOBAL_SYSTEM_SETTING_KEYS

    def _storage_key(self, key: str, tenant_id: int) -> str:
        normalized = (key or "").strip()
        if self.is_global_system_setting(normalized):
            return normalized
        return f"tenant:{tenant_id}:{normalized}"

    def _display_key(self, storage_key: str, tenant_id: int) -> str:
        prefix = f"tenant:{tenant_id}:"
        if storage_key.startswith(prefix):
            return storage_key[len(prefix):]
        return storage_key

    def _is_sensitive_setting(self, key: str) -> bool:
        k = (key or "").strip().lower()
        if k in SENSITIVE_SETTING_KEYS:
            return True
        # Dynamic check for integration tokens/secrets
        return any(word in k for word in ["token", "secret", "password", "key"])

    def _settings_tenant_id_for_key(self, key: str, tenant_id: int | None = None) -> int:
        if self.is_global_system_setting(key):
            return self.get_system_tenant_id()
        return self._resolve_tenant_id(tenant_id)

    def get_settings(self, tenant_id: int) -> list[Setting]:
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            with session_scope() as db:
                rows = persistence_repo.list_settings_by_tenant(db, resolved_tid)
                for row in rows:
                    row.key = self._display_key(row.key, resolved_tid)
                return rows

    def get_setting(self, key: str, default: str | None = None, tenant_id: int | None = None, fallback_to_system: bool = True) -> str | None:
        with self._lock:
            with session_scope() as db:
                target_tid = self._settings_tenant_id_for_key(key, tenant_id)
                storage_key = self._storage_key(key, target_tid)
                row = persistence_repo.get_setting_row(db, storage_key)
                if not row and storage_key != key:
                    row = persistence_repo.get_legacy_setting_row(db, target_tid, key)
                if row:
                    val = row.value
                    return decrypt_value(val) if self._is_sensitive_setting(key) else val

                if fallback_to_system and not self.is_global_system_setting(key):
                    sys_tid = self.get_system_tenant_id()
                    if sys_tid != target_tid:
                        sys_storage_key = self._storage_key(key, sys_tid)
                        sys_row = persistence_repo.get_setting_row(db, sys_storage_key)
                        if not sys_row and sys_storage_key != key:
                            sys_row = persistence_repo.get_legacy_setting_row(db, sys_tid, key)
                        if sys_row:
                            val = sys_row.value
                            return decrypt_value(val) if self._is_sensitive_setting(key) else val
                return default

    def upsert_setting(self, key: str, value: str, description: str | None = None, tenant_id: int | None = None) -> None:
        with self._lock:
            with session_scope() as db:
                storage_val = encrypt_value(value) if self._is_sensitive_setting(key) else value
                target_tid = self._settings_tenant_id_for_key(key, tenant_id)
                storage_key = self._storage_key(key, target_tid)
                row = persistence_repo.get_setting_row(db, storage_key)
                if not row and storage_key != key:
                    row = persistence_repo.get_legacy_setting_row(db, target_tid, key)
                if row and row.key != storage_key:
                    row.key = storage_key
                persistence_repo.upsert_setting_row(
                    db,
                    tenant_id=target_tid,
                    key=storage_key,
                    value=storage_val,
                    description=description,
                )
                db.commit()

    def set_setting(self, key: str, value: str, description: str | None = None, tenant_id: int | None = None) -> None:
        """Legacy compatibility alias for older callers."""
        self.upsert_setting(key, value, description=description, tenant_id=tenant_id)

    def delete_setting(self, key: str, tenant_id: int | None = None) -> bool:
        """Remove a specific setting for a tenant."""
        with self._lock:
            with session_scope() as db:
                target_tid = self._settings_tenant_id_for_key(key, tenant_id)
                storage_key = self._storage_key(key, target_tid)
                deleted = persistence_repo.delete_setting_row(db, storage_key)
                if not deleted and storage_key != key:
                    legacy_row = persistence_repo.get_legacy_setting_row(db, target_tid, key)
                    if legacy_row:
                        db.delete(legacy_row)
                        deleted = True
                if deleted:
                    db.commit()
                    return True
                return False

    def delete_settings_by_prefix(self, prefix: str, tenant_id: int | None = None) -> int:
        """Remove all settings starting with a specific prefix (e.g. 'whatsapp_')."""
        with self._lock:
            with session_scope() as db:
                # We don't use _settings_tenant_id_for_key here because we want to be explicit about the tenant
                tid = tenant_id if tenant_id is not None else self.get_system_tenant_id()
                storage_prefix = prefix if self.is_global_system_setting(prefix.rstrip("_")) else f"tenant:{tid}:{prefix}"
                count = persistence_repo.delete_settings_by_prefix(db, tid, storage_prefix)
                if count > 0:
                    db.commit()
                return count

    def init_default_settings(self) -> None:
        sys_tid = self.get_system_tenant_id()
        platform_defaults = [
            ("system_name", "ARIIA Platform Control", "Main branding for the SaaS dashboard."),
            ("notification_email", "admin@ariia.io", "Platform-wide alerts."),
            ("maintenance_mode", "false", "Global maintenance switch."),
            ("platform_llm_providers_json", json.dumps([]), "Inventory of AI providers."),
            ("platform_pii_masking_enabled", "true", "Global PII masking."),
            ("platform_data_retention_days", "90", "Message retention in days."),
            ("platform_available_languages", json.dumps(["de", "en", "bg"]), "List of supported UI languages."),
            ("platform_default_language", "en", "System fallback language."),
        ]
        with self._lock:
            with session_scope() as db:
                for key, value, desc in platform_defaults:
                    storage_key = self._storage_key(key, sys_tid)
                    row = persistence_repo.get_setting_row(db, storage_key)
                    if row:
                        row.tenant_id = sys_tid
                        if not row.value:
                            row.value = value
                        if not row.description:
                            row.description = desc
                    else:
                        persistence_repo.upsert_setting_row(
                            db,
                            tenant_id=sys_tid,
                            key=storage_key,
                            value=value,
                            description=desc,
                        )
                db.commit()

    # --- Session & Message Management ---
    def get_stats(self, tenant_id: int) -> dict:
        """Get usage statistics for a specific tenant."""
        with self._lock:
            with session_scope() as db:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                msg_count = persistence_repo.count_messages_for_tenant(db, resolved_tid)
                sess_count = persistence_repo.count_sessions_for_tenant(db, resolved_tid)
                return {"total_messages": msg_count, "active_users": sess_count}

    def get_recent_sessions(self, tenant_id: int, limit: int = 10, active_only: bool = False):
        """List recent chat sessions for a tenant."""
        with self._lock:
            with session_scope() as db:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                return persistence_repo.list_recent_sessions(
                    db,
                    resolved_tid,
                    limit=limit,
                    active_only=active_only,
                )

    def get_session_by_user_id(self, user_id: str, tenant_id: int) -> ChatSession | None:
        """Get session by user_id scoped to tenant."""
        with self._lock:
            with session_scope() as db:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                return persistence_repo.get_session_by_user_id(db, resolved_tid, user_id)

    def get_session_global(self, user_id: str) -> ChatSession | None:
        """Find a session across all tenants (internal routing only)."""
        with self._lock:
            with session_scope() as db:
                return persistence_repo.get_session_global(db, user_id)

    def get_tenant_slug(self, tenant_id: int) -> str | None:
        """Get the slug for a given tenant_id."""
        with self._lock:
            with session_scope() as db:
                tenant = persistence_repo.get_tenant_by_id(db, tenant_id)
                return tenant.slug if tenant else None

    def get_or_create_session(self, user_id: str, platform: Platform, tenant_id: int, user_name: str = None, phone_number: str = None, member_id: str = None) -> ChatSession:
        with self._lock:
            with session_scope() as db:
                db.expire_all()
                resolved_tid = self._resolve_tenant_id(tenant_id)
                session = persistence_repo.get_session_by_user_id(db, resolved_tid, user_id)
                if not session:
                    session = persistence_repo.create_session(
                        db,
                        tenant_id=resolved_tid,
                        user_id=user_id,
                        platform=platform,
                        user_name=user_name,
                        phone_number=phone_number,
                        member_id=member_id,
                    )
                    db.commit()
                    db.refresh(session)
                else:
                    updated = persistence_repo.update_session_identity(
                        session,
                        user_name=user_name,
                        phone_number=phone_number,
                        member_id=member_id,
                    )
                    if updated:
                        db.commit()
                        db.refresh(session)
                return session

    def save_message(self, user_id: str, role: str, content: str, platform: Platform, tenant_id: int, metadata: dict = None, user_name: str = None, phone_number: str = None, member_id: str = None):
        with self._lock:
            with session_scope() as db:
                try:
                    # 1. Mask PII before storage (Gold Standard Compliance)
                    is_enabled = self.get_setting("platform_pii_masking_enabled", "true") == "true"
                    safe_content = mask_pii(content) if is_enabled else content

                    resolved_tid = self._resolve_tenant_id(tenant_id)
                    session = persistence_repo.get_session_by_user_id(db, resolved_tid, user_id)
                    if not session:
                        session = persistence_repo.create_session(
                            db,
                            tenant_id=resolved_tid,
                            user_id=user_id,
                            platform=platform,
                            user_name=user_name,
                            phone_number=phone_number,
                            member_id=member_id,
                        )
                    else:
                        persistence_repo.update_session_identity(
                            session,
                            user_name=user_name,
                            phone_number=phone_number,
                            member_id=member_id,
                        )

                    persistence_repo.add_message(
                        db,
                        tenant_id=session.tenant_id,
                        user_id=user_id,
                        role=role,
                        content=safe_content,
                        metadata_json=json.dumps(metadata) if metadata else None,
                    )
                    persistence_repo.touch_session_activity(session)
                    db.commit()
                except Exception as e:
                    logger.error("db.save_failed", error=str(e))
                    db.rollback()

    def get_chat_history(self, user_id: str, tenant_id: int, limit: int = 50):
        with self._lock:
            with session_scope() as db:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                return persistence_repo.list_chat_history(
                    db,
                    tenant_id=resolved_tid,
                    user_id=user_id,
                    limit=limit,
                )

    def reset_chat(self, user_id: str, tenant_id: int, *, clear_verification: bool = True, clear_contact: bool = False, clear_history: bool = True) -> dict:
        with self._lock:
            with session_scope() as db:
                try:
                    resolved_tid = self._resolve_tenant_id(tenant_id)
                    if clear_history:
                        persistence_repo.delete_chat_history(db, tenant_id=resolved_tid, user_id=user_id)
                    session = persistence_repo.get_session_by_user_id(db, resolved_tid, user_id)
                    if session:
                        if clear_verification:
                            session.member_id = None
                        if clear_contact:
                            session.phone_number = None
                            session.email = None
                        session.is_active = False
                    db.commit()
                    return {"session_found": session is not None}
                except Exception:
                    db.rollback()
                    raise

    def link_session_to_member(self, user_id: str, tenant_id: int, member_id: str | None) -> bool:
        """Manually link (or unlink) a chat session to a member_id."""
        with self._lock:
            with session_scope() as db:
                try:
                    resolved_tid = self._resolve_tenant_id(tenant_id)
                    updated = persistence_repo.set_session_link(
                        db,
                        tenant_id=resolved_tid,
                        user_id=user_id,
                        member_id=member_id,
                    )
                    if not updated:
                        return False
                    db.commit()
                    return True
                except Exception:
                    db.rollback()
                    raise

    # ─── Integration Management ────────────────────────────────────────────

    def get_enabled_integrations(self, tenant_id: int) -> list[str]:
        """Return a list of integration IDs that are enabled for a tenant.

        Primary: Reads the ``tenant_integrations`` table.
        Fallback: Scans settings keys matching ``integration_{name}_{tid}_enabled``.

        Args:
            tenant_id: The tenant whose active integrations should be returned.

        Returns:
            A sorted list of integration ID strings, e.g. ``['calendly', 'magicline']``.
        """
        # ── Primary: tenant_integrations table ──
        with self._lock:
            try:
                with session_scope() as db:
                    resolved_tid = self._resolve_tenant_id(tenant_id)
                    rows = (
                        db.query(TenantIntegration.integration_id)
                        .filter(
                            TenantIntegration.tenant_id == resolved_tid,
                            TenantIntegration.enabled.is_(True),
                            TenantIntegration.status == "enabled",
                        )
                        .all()
                    )
                    result = sorted([row[0] for row in rows])
                    if result:
                        return result
            except Exception as exc:
                logger.debug(
                    "persistence.get_enabled_integrations_table_fallback",
                    tenant_id=tenant_id,
                    error=str(exc),
                )

        # ── Fallback: settings-based detection ──
        # Scans for keys like integration_calendly_2_enabled = true
        try:
            import re
            settings = self.get_settings(tenant_id)
            enabled = set()
            pattern = re.compile(r"^integration_([a-z_]+?)_\d+_enabled$")
            for s in settings:
                m = pattern.match(s.key)
                if m and str(s.value).strip().lower() == "true":
                    enabled.add(m.group(1))
            if enabled:
                logger.debug(
                    "persistence.get_enabled_integrations_from_settings",
                    tenant_id=tenant_id,
                    integrations=sorted(enabled),
                )
            return sorted(enabled)
        except Exception as exc:
            logger.error(
                "persistence.get_enabled_integrations_failed",
                tenant_id=tenant_id,
                error=str(exc),
            )
            return []

    def is_integration_enabled(self, tenant_id: int, integration_id: str) -> bool:
        """Check whether a specific integration is enabled for a tenant."""
        return integration_id in self.get_enabled_integrations(tenant_id)

    # ─── Ingestion Jobs ────────────────────────────────────────────────────────

    def create_ingestion_job(
        self,
        tenant_id: int,
        filename: str,
        original_filename: str,
        mime_type: str,
        file_size_bytes: int | None = None,
        s3_key: str | None = None,
    ) -> IngestionJob:
        """Create a new ingestion job record with PENDING status."""
        with self._lock:
            with session_scope() as db:
                try:
                    resolved_tid = self._resolve_tenant_id(tenant_id)
                    job = IngestionJob(
                        tenant_id=resolved_tid,
                        filename=filename,
                        original_filename=original_filename,
                        mime_type=mime_type,
                        file_size_bytes=file_size_bytes,
                        s3_key=s3_key,
                        status=IngestionJobStatus.PENDING,
                    )
                    db.add(job)
                    db.commit()
                    db.refresh(job)
                    return job
                except Exception:
                    db.rollback()
                    raise

    def update_job_status(
        self,
        job_id: str,
        status: IngestionJobStatus,
        error_message: str | None = None,
        error_category: str | None = None,
    ) -> IngestionJob | None:
        """Update the status of an ingestion job. Returns the updated job or None."""
        from datetime import datetime, timezone as _tz
        with self._lock:
            with session_scope() as db:
                try:
                    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                    if not job:
                        return None
                    job.status = status
                    if error_message is not None:
                        job.error_message = error_message
                    if error_category is not None:
                        job.error_category = error_category
                    if status == IngestionJobStatus.PROCESSING and job.started_at is None:
                        job.started_at = datetime.now(_tz.utc)
                        job.attempt_count = (job.attempt_count or 0) + 1
                    if status in (IngestionJobStatus.COMPLETED, IngestionJobStatus.FAILED, IngestionJobStatus.DEAD_LETTER):
                        job.completed_at = datetime.now(_tz.utc)
                    db.commit()
                    db.refresh(job)
                    return job
                except Exception:
                    db.rollback()
                    raise

    def update_job_progress(
        self,
        job_id: str,
        chunks_total: int,
        chunks_processed: int,
    ) -> None:
        """Update chunk-level progress counters for an ingestion job."""
        with self._lock:
            with session_scope() as db:
                try:
                    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
                    if job:
                        job.chunks_total = chunks_total
                        job.chunks_processed = chunks_processed
                        db.commit()
                except Exception:
                    db.rollback()
                    raise

    def get_job_by_id(self, job_id: str, tenant_id: int) -> IngestionJob | None:
        """Fetch a single ingestion job scoped to a tenant (multi-tenant isolation)."""
        with self._lock:
            with session_scope() as db:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                return (
                    db.query(IngestionJob)
                    .filter(IngestionJob.id == job_id, IngestionJob.tenant_id == resolved_tid)
                    .first()
                )

    def list_jobs_by_tenant(
        self,
        tenant_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IngestionJob]:
        """List ingestion jobs for a tenant, ordered by created_at descending."""
        with self._lock:
            with session_scope() as db:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                return (
                    db.query(IngestionJob)
                    .filter(IngestionJob.tenant_id == resolved_tid)
                    .order_by(IngestionJob.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                    .all()
                )

    def get_dlq_jobs(self, limit: int = 50) -> list[IngestionJob]:
        """Return dead-letter jobs across all tenants (system_admin only)."""
        with self._lock:
            with session_scope() as db:
                return (
                    db.query(IngestionJob)
                    .filter(IngestionJob.status == IngestionJobStatus.DEAD_LETTER)
                    .order_by(IngestionJob.created_at.desc())
                    .limit(limit)
                    .all()
                )


# Singleton Instance
persistence = PersistenceService()
persistence.init_default_settings()
