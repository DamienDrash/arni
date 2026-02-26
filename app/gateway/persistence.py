import structlog
import threading
import json
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.models import ChatSession, ChatMessage, Setting, Tenant
from app.core.db import SessionLocal, engine, Base
from app.gateway.schemas import Platform
from app.core.crypto import encrypt_value, decrypt_value
from app.integrations.pii_filter import mask_pii

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
    
    # Billing Governance
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
}

# Ensure tables exist
Base.metadata.create_all(bind=engine)

class PersistenceService:
    def __init__(self):
        self.db = SessionLocal()
        self._lock = threading.RLock()

    def __del__(self):
        self.db.close()

    def _resolve_tenant_id(self, tenant_id: int | None) -> int:
        if tenant_id is not None:
            return int(tenant_id)
        # Fallback: Check if we are in a request context (FastAPI)
        # In a background script, we MUST provide tenant_id explicitly.
        raise ValueError("Strict Multi-Tenancy Violation: tenant_id is required.")

    def get_system_tenant_id(self) -> int:
        with self._lock:
            tenant = self.db.query(Tenant).filter(Tenant.slug == "system").first()
            if not tenant:
                tenant = Tenant(slug="system", name="ARIIA System")
                self.db.add(tenant)
                self.db.commit()
                self.db.refresh(tenant)
            return int(tenant.id)

    def is_global_system_setting(self, key: str) -> bool:
        return (key or "").strip().lower() in GLOBAL_SYSTEM_SETTING_KEYS

    def _is_sensitive_setting(self, key: str) -> bool:
        return (key or "").strip().lower() in SENSITIVE_SETTING_KEYS

    def _settings_tenant_id_for_key(self, key: str, tenant_id: int | None = None) -> int:
        if self.is_global_system_setting(key):
            return self.get_system_tenant_id()
        return self._resolve_tenant_id(tenant_id)

    def get_settings(self, tenant_id: int) -> list[Setting]:
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            return self.db.query(Setting).filter(Setting.tenant_id == resolved_tid).all()

    def get_setting(self, key: str, default: str | None = None, tenant_id: int | None = None, fallback_to_system: bool = True) -> str | None:
        with self._lock:
            target_tid = self._settings_tenant_id_for_key(key, tenant_id)
            row = self.db.query(Setting).filter(Setting.tenant_id == target_tid, Setting.key == key).first()
            if row:
                val = row.value
                return decrypt_value(val) if self._is_sensitive_setting(key) else val
            
            if fallback_to_system and not self.is_global_system_setting(key):
                sys_tid = self.get_system_tenant_id()
                if sys_tid != target_tid:
                    sys_row = self.db.query(Setting).filter(Setting.tenant_id == sys_tid, Setting.key == key).first()
                    if sys_row:
                        val = sys_row.value
                        return decrypt_value(val) if self._is_sensitive_setting(key) else val
            return default

    def upsert_setting(self, key: str, value: str, description: str | None = None, tenant_id: int | None = None) -> None:
        with self._lock:
            storage_val = encrypt_value(value) if self._is_sensitive_setting(key) else value
            target_tid = self._settings_tenant_id_for_key(key, tenant_id)
            row = self.db.query(Setting).filter(Setting.tenant_id == target_tid, Setting.key == key).first()
            if row:
                row.value = storage_val
                if description is not None: row.description = description
            else:
                self.db.add(Setting(tenant_id=target_tid, key=key, value=storage_val, description=description))
            self.db.commit()

    def delete_setting(self, key: str, tenant_id: int | None = None) -> bool:
        """Remove a specific setting for a tenant."""
        with self._lock:
            target_tid = self._settings_tenant_id_for_key(key, tenant_id)
            cursor = self.db.query(Setting).filter(Setting.tenant_id == target_tid, Setting.key == key)
            if cursor.first():
                cursor.delete()
                self.db.commit()
                return True
            return False

    def delete_settings_by_prefix(self, prefix: str, tenant_id: int | None = None) -> int:
        """Remove all settings starting with a specific prefix (e.g. 'whatsapp_')."""
        with self._lock:
            # We don't use _settings_tenant_id_for_key here because we want to be explicit about the tenant
            tid = tenant_id if tenant_id is not None else self.get_system_tenant_id()
            cursor = self.db.query(Setting).filter(Setting.tenant_id == tid, Setting.key.like(f"{prefix}%"))
            count = cursor.count()
            if count > 0:
                cursor.delete(synchronize_session=False)
                self.db.commit()
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
            for key, value, desc in platform_defaults:
                exists = self.db.query(Setting).filter(Setting.tenant_id == sys_tid, Setting.key == key).first()
                if not exists:
                    self.db.add(Setting(tenant_id=sys_tid, key=key, value=value, description=desc))
            self.db.commit()

    # --- Session & Message Management ---
    def get_stats(self, tenant_id: int) -> dict:
        """Get usage statistics for a specific tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            msg_count = self.db.query(ChatMessage).filter(ChatMessage.tenant_id == resolved_tid).count()
            sess_count = self.db.query(ChatSession).filter(ChatSession.tenant_id == resolved_tid).count()
            return {"total_messages": msg_count, "active_users": sess_count}

    def get_recent_sessions(self, tenant_id: int, limit: int = 10, active_only: bool = False):
        """List recent chat sessions for a tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            q = self.db.query(ChatSession).filter(ChatSession.tenant_id == resolved_tid)
            if active_only:
                q = q.filter(ChatSession.is_active.is_(True))
            return q.order_by(ChatSession.last_message_at.desc()).limit(limit).all()

    def get_session_by_user_id(self, user_id: str, tenant_id: int) -> ChatSession | None:
        """Get session by user_id scoped to tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            return self.db.query(ChatSession).filter(
                ChatSession.user_id == user_id, 
                ChatSession.tenant_id == resolved_tid
            ).first()

    def get_session_global(self, user_id: str) -> ChatSession | None:
        """Find a session across all tenants (internal routing only)."""
        with self._lock:
            return self.db.query(ChatSession).filter(ChatSession.user_id == user_id).first()

    def get_tenant_slug(self, tenant_id: int) -> str | None:
        """Get the slug for a given tenant_id."""
        with self._lock:
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            return tenant.slug if tenant else None

    def get_or_create_session(self, user_id: str, platform: Platform, tenant_id: int, user_name: str = None, phone_number: str = None, member_id: str = None) -> ChatSession:
        with self._lock:
            self.db.expire_all()
            resolved_tid = self._resolve_tenant_id(tenant_id)
            platform_str = platform.value if isinstance(platform, Platform) else str(platform)
            session = self.db.query(ChatSession).filter(ChatSession.user_id == user_id, ChatSession.tenant_id == resolved_tid).first()
            if not session:
                session = ChatSession(user_id=user_id, tenant_id=resolved_tid, platform=platform_str, user_name=user_name, phone_number=phone_number, member_id=member_id)
                self.db.add(session)
                self.db.commit()
                self.db.refresh(session)
            else:
                updated = False
                if user_name and session.user_name != user_name: session.user_name = user_name; updated = True
                if phone_number and session.phone_number != phone_number: session.phone_number = phone_number; updated = True
                if member_id and session.member_id != member_id: session.member_id = member_id; updated = True
                if updated: self.db.commit(); self.db.refresh(session)
            return session

    def save_message(self, user_id: str, role: str, content: str, platform: Platform, tenant_id: int, metadata: dict = None, user_name: str = None, phone_number: str = None, member_id: str = None):
        with self._lock:
            try:
                # 1. Mask PII before storage (Gold Standard Compliance)
                is_enabled = self.get_setting("platform_pii_masking_enabled", "true") == "true"
                safe_content = mask_pii(content) if is_enabled else content
                
                session = self.get_or_create_session(user_id=user_id, platform=platform, tenant_id=tenant_id, user_name=user_name, phone_number=phone_number, member_id=member_id)
                msg = ChatMessage(session_id=user_id, tenant_id=session.tenant_id, role=role, content=safe_content, metadata_json=json.dumps(metadata) if metadata else None)
                self.db.add(msg)
                session.last_message_at = datetime.now(timezone.utc)
                session.is_active = True
                self.db.commit()
            except Exception as e:
                logger.error("db.save_failed", error=str(e))
                self.db.rollback()

    def get_chat_history(self, user_id: str, tenant_id: int, limit: int = 50):
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            rows = self.db.query(ChatMessage).filter(ChatMessage.session_id == user_id, ChatMessage.tenant_id == resolved_tid).order_by(ChatMessage.timestamp.desc()).limit(limit).all()
            rows.reverse(); return rows

    def reset_chat(self, user_id: str, tenant_id: int, *, clear_verification: bool = True, clear_contact: bool = False, clear_history: bool = True) -> dict:
        with self._lock:
            try:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                if clear_history: self.db.query(ChatMessage).filter(ChatMessage.session_id == user_id, ChatMessage.tenant_id == resolved_tid).delete(synchronize_session=False)
                session = self.db.query(ChatSession).filter(ChatSession.user_id == user_id, ChatSession.tenant_id == resolved_tid).first()
                if session:
                    if clear_verification: session.member_id = None
                    if clear_contact: session.phone_number = None; session.email = None
                    session.is_active = False
                self.db.commit()
                return {"session_found": session is not None}
            except Exception: self.db.rollback(); raise

    def link_session_to_member(self, user_id: str, tenant_id: int, member_id: str | None) -> bool:
        """Manually link (or unlink) a chat session to a member_id."""
        with self._lock:
            try:
                resolved_tid = self._resolve_tenant_id(tenant_id)
                session = self.db.query(ChatSession).filter(
                    ChatSession.user_id == user_id,
                    ChatSession.tenant_id == resolved_tid,
                ).first()
                if not session:
                    return False
                session.member_id = member_id
                self.db.commit()
                return True
            except Exception:
                self.db.rollback()
                raise

# Singleton Instance
persistence = PersistenceService()
persistence.init_default_settings()
