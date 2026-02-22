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

logger = structlog.get_logger()

# Global system settings that belong to the 'system' tenant
GLOBAL_SYSTEM_SETTING_KEYS = {
    "billing_default_provider",
    "billing_plans_json",
    "billing_providers_json",
    "billing_stripe_enabled",
    "billing_stripe_mode",
    "billing_stripe_publishable_key",
    "billing_stripe_secret_key",
    "billing_stripe_webhook_secret",
}

# Settings that should be encrypted at rest (BYOK)
SENSITIVE_SETTING_KEYS = {
    "openai_api_key",
    "elevenlabs_api_key",
    "twilio_auth_token",
    "magicline_api_key",
    "smtp_password",
    "postmark_server_token",
    "billing_stripe_secret_key",
}

# Ensure tables exist (PostgreSQL bootstrap)
Base.metadata.create_all(bind=engine)

class PersistenceService:
    """Core persistence layer for ARIIA. Exclusively PostgreSQL."""

    def __init__(self):
        self.db = SessionLocal()
        self._lock = threading.RLock()
        self._backfill_legacy_settings_tenant_ids()

    def __del__(self):
        self.db.close()

    def _backfill_legacy_settings_tenant_ids(self) -> None:
        """Maintenance: Ensure all settings have a tenant_id."""
        try:
            self.db.rollback()
            system_id = self.get_system_tenant_id()
            self.db.execute(
                text("UPDATE settings SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
                {"tenant_id": system_id},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _resolve_tenant_id(self, tenant_id: int | None) -> int:
        """Resolve tenant_id. Raises ValueError if None is provided to enforce isolation."""
        if tenant_id is not None:
            return int(tenant_id)
        
        # In a strict SaaS, we no longer allow implicit fallbacks to 'system'.
        # Callers must explicitly resolve the tenant (e.g. from slug or auth context).
        raise ValueError("Strict Multi-Tenancy Violation: tenant_id is required.")

    def get_system_tenant_id(self) -> int:
        """Explicitly get the 'system' tenant ID for global operations."""
        with self._lock:
            tenant = self.db.query(Tenant).filter(Tenant.slug == "system").first()
            if not tenant:
                # Emergency auto-create if missing during bootstrap
                tenant = Tenant(slug="system", name="System")
                self.db.add(tenant)
                self.db.commit()
                self.db.refresh(tenant)
            return int(tenant.id)

    def get_tenant_slug(self, tenant_id: int) -> str:
        """Get the slug for a given tenant ID."""
        with self._lock:
            resolved = self._resolve_tenant_id(tenant_id)
            row = self.db.query(Tenant).filter(Tenant.id == resolved).first()
            return (row.slug if row and row.slug else "unknown").strip().lower()

    def is_global_system_setting(self, key: str) -> bool:
        """Check if a setting key is global."""
        return (key or "").strip().lower() in GLOBAL_SYSTEM_SETTING_KEYS

    def _is_sensitive_setting(self, key: str) -> bool:
        """Check if a setting key should be encrypted."""
        return (key or "").strip().lower() in SENSITIVE_SETTING_KEYS

    def _settings_tenant_id_for_key(self, key: str, tenant_id: int | None = None) -> int:
        """Determine which tenant scope a setting belongs to."""
        if self.is_global_system_setting(key):
            return self.get_system_tenant_id()
        return self._resolve_tenant_id(tenant_id)

    def get_or_create_session(
        self,
        user_id: str,
        platform: Platform,
        tenant_id: int,
        user_name: str = None,
        phone_number: str = None,
        member_id: str = None,
    ) -> ChatSession:
        """Get or create a chat session scoped to a tenant."""
        with self._lock:
            self.db.expire_all()
            resolved_tid = self._resolve_tenant_id(tenant_id)
            platform_str = platform.value if isinstance(platform, Platform) else str(platform)
            
            session = (
                self.db.query(ChatSession)
                .filter(ChatSession.user_id == user_id, ChatSession.tenant_id == resolved_tid)
                .first()
            )

            if not session:
                session = ChatSession(
                    user_id=user_id,
                    tenant_id=resolved_tid,
                    platform=platform_str,
                    user_name=user_name,
                    phone_number=phone_number,
                    member_id=member_id
                )
                self.db.add(session)
                self.db.commit()
                self.db.refresh(session)
                logger.info("db.session_created", user_id=user_id, tenant_id=resolved_tid, platform=platform_str)
            else:
                # Update identifying fields if provided
                updated = False
                if user_name and session.user_name != user_name:
                    session.user_name = user_name
                    updated = True
                if phone_number and session.phone_number != phone_number:
                    session.phone_number = phone_number
                    updated = True
                if member_id and session.member_id != member_id:
                    session.member_id = member_id
                    updated = True

                if updated:
                    self.db.commit()
                    self.db.refresh(session)
                    logger.info("db.session_updated", user_id=user_id, tenant_id=resolved_tid)

            return session

    def get_session_by_user_id(self, user_id: str, tenant_id: int) -> ChatSession | None:
        """Get session by user_id scoped to tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            return self.db.query(ChatSession).filter(
                ChatSession.user_id == user_id, 
                ChatSession.tenant_id == resolved_tid
            ).first()

    def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        platform: Platform,
        tenant_id: int,
        metadata: dict = None,
        user_name: str = None,
        phone_number: str = None,
        member_id: str = None,
    ):
        """Save a message to the database, automatically managing the session context."""
        with self._lock:
            try:
                session = self.get_or_create_session(
                    user_id=user_id,
                    platform=platform,
                    tenant_id=tenant_id,
                    user_name=user_name,
                    phone_number=phone_number,
                    member_id=member_id,
                )

                meta_json = json.dumps(metadata) if metadata else None

                msg = ChatMessage(
                    session_id=user_id,
                    tenant_id=session.tenant_id,
                    role=role,
                    content=content,
                    metadata_json=meta_json
                )
                self.db.add(msg)

                session.last_message_at = datetime.now(timezone.utc)
                session.is_active = True

                self.db.commit()
                logger.info("db.message_saved", user_id=user_id, tenant_id=session.tenant_id, role=role)
            except Exception as e:
                logger.error("db.save_failed", error=str(e))
                self.db.rollback()

    def get_stats(self, tenant_id: int) -> dict:
        """Get usage statistics for a specific tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            msg_count = self.db.query(ChatMessage).filter(ChatMessage.tenant_id == resolved_tid).count()
            sess_count = self.db.query(ChatSession).filter(ChatSession.tenant_id == resolved_tid).count()
            
            return {
                "total_messages": msg_count,
                "active_users": sess_count
            }
    
    def get_recent_sessions(self, tenant_id: int, limit: int = 10, active_only: bool = False):
        """List recent chat sessions for a tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            q = self.db.query(ChatSession).filter(ChatSession.tenant_id == resolved_tid)
            if active_only:
                q = q.filter(ChatSession.is_active.is_(True))
            return q.order_by(ChatSession.last_message_at.desc()).limit(limit).all()

    def get_chat_history(self, user_id: str, tenant_id: int, limit: int = 50):
        """Retrieve chronological chat history scoped to tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            q = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == user_id,
                ChatMessage.tenant_id == resolved_tid
            )
            rows = q.order_by(ChatMessage.timestamp.desc()).limit(limit).all()
            rows.reverse()
            return rows

    def reset_chat(
        self,
        user_id: str,
        tenant_id: int,
        *,
        clear_verification: bool = True,
        clear_contact: bool = False,
        clear_history: bool = True,
    ) -> dict:
        """Reset conversation state for a user within a tenant's scope."""
        with self._lock:
            deleted_messages = 0
            try:
                self.db.expire_all()
                resolved_tid = self._resolve_tenant_id(tenant_id)
                session = self.db.query(ChatSession).filter(
                    ChatSession.user_id == user_id,
                    ChatSession.tenant_id == resolved_tid
                ).first()

                if clear_history:
                    deleted_messages = self.db.query(ChatMessage).filter(
                        ChatMessage.session_id == user_id,
                        ChatMessage.tenant_id == resolved_tid
                    ).delete(synchronize_session=False)

                if session:
                    if clear_verification:
                        session.member_id = None
                    if clear_contact:
                        session.phone_number = None
                        session.email = None
                    session.is_active = False

                self.db.commit()
                logger.info("db.chat_reset", user_id=user_id, tenant_id=resolved_tid)
                return {"session_found": session is not None, "deleted_messages": deleted_messages}
            except Exception as e:
                self.db.rollback()
                logger.error("db.chat_reset_failed", user_id=user_id, error=str(e))
                raise

    def get_settings(self, tenant_id: int) -> list[Setting]:
        """List all settings for a tenant."""
        with self._lock:
            resolved_tid = self._resolve_tenant_id(tenant_id)
            return (
                self.db.query(Setting)
                .filter(Setting.tenant_id == resolved_tid)
                .order_by(Setting.key.asc())
                .all()
            )

    def get_setting(
        self,
        key: str,
        default: str | None = None,
        tenant_id: int | None = None,
        fallback_to_system: bool = True,
    ) -> str | None:
        """Get a setting value, optionally falling back to global system defaults."""
        with self._lock:
            self._backfill_legacy_settings_tenant_ids()
            target_tid = self._settings_tenant_id_for_key(key, tenant_id)
            
            row = (
                self.db.query(Setting)
                .filter(Setting.tenant_id == target_tid, Setting.key == key)
                .first()
            )
            if row:
                val = row.value
                return decrypt_value(val) if self._is_sensitive_setting(key) else val
            
            if fallback_to_system and not self.is_global_system_setting(key):
                sys_tid = self.get_system_tenant_id()
                if sys_tid != target_tid:
                    sys_row = (
                        self.db.query(Setting)
                        .filter(Setting.tenant_id == sys_tid, Setting.key == key)
                        .first()
                    )
                    if sys_row:
                        val = sys_row.value
                        return decrypt_value(val) if self._is_sensitive_setting(key) else val
            return default

    def upsert_setting(
        self,
        key: str,
        value: str,
        description: str | None = None,
        tenant_id: int | None = None,
    ) -> None:
        """Create or update a setting, with automatic encryption for sensitive keys."""
        with self._lock:
            self._backfill_legacy_settings_tenant_ids()
            
            storage_val = encrypt_value(value) if self._is_sensitive_setting(key) else value
            target_tid = self._settings_tenant_id_for_key(key, tenant_id)
            
            row = (
                self.db.query(Setting)
                .filter(Setting.tenant_id == target_tid, Setting.key == key)
                .first()
            )
            if row:
                row.value = storage_val
                if description is not None:
                    row.description = description
            else:
                self.db.add(
                    Setting(
                        tenant_id=target_tid,
                        key=key,
                        value=storage_val,
                        description=description,
                    )
                )
            self.db.commit()

    def init_default_settings(self) -> None:
        """Seed initial system settings."""
        defaults = [
            ("checkin_enabled", "true",
             "Magicline Check-in System aktiv. Wenn deaktiviert, werden Besuchs-Statistiken aus Buchungsdaten berechnet."),
            ("member_memory_cron_enabled", "true",
             "Aktiviert den täglichen Member-Memory Analyzer per Cron-Zeitplan."),
            ("member_memory_cron", "0 2 * * *",
             "Cron-Zeitplan (UTC) für die tägliche Member-Memory Analyse, Format: m h dom mon dow."),
            ("member_memory_last_run_at", "",
             "Zeitpunkt des letzten Member-Memory Cron-Runs (ISO-UTC)."),
            ("member_memory_last_run_status", "never",
             "Status des letzten Member-Memory Cron-Runs (never|ok|error:<details>)."),
            ("member_memory_llm_enabled", "true",
             "Aktiviert LLM-basierte Extraktion für Member Memory (Fallback auf Heuristik bei Fehlern)."),
            ("member_memory_llm_model", "gpt-4o-mini",
             "LLM-Modell für die tägliche Member-Memory Extraktion."),
            ("whatsapp_mode", "qr", "WhatsApp Betriebsmodus (qr|business_api)."),
            ("bridge_webhook_url", "http://ariia-core:8000/webhook/whatsapp", "Webhook-Ziel fuer WhatsApp QR-Bridge."),
            ("bridge_port", "3000", "Port der WhatsApp QR-Bridge."),
            ("bridge_auth_dir", "/app/data/whatsapp/auth_info_baileys", "Auth-Verzeichnis der WhatsApp QR-Bridge."),
            ("bridge_qr_url", "http://localhost:3000/qr", "URL zur QR-Code-Seite der WhatsApp Bridge."),
            ("bridge_health_url", "http://localhost:3000/health", "Health-Endpoint der WhatsApp Bridge."),
            ("telegram_bot_token", "", "Telegram Bot Token. Hinweis: Telegram Poller-Neustart erforderlich nach Aenderung."),
            ("telegram_admin_chat_id", "", "Telegram Admin Chat ID fuer Alerts."),
            ("telegram_webhook_secret", "", "Shared Secret für Telegram Webhook Authentifizierung."),
            ("magicline_base_url", "", "Magicline API Base URL (z. B. https://api.magicline.com)."),
            ("magicline_api_key", "", "Magicline API Key."),
            ("magicline_studio_id", "", "Magicline Studio ID."),
            ("magicline_tenant_id", "", "Magicline Tenant ID."),
            ("magicline_auto_sync_enabled", "false", "Aktiviert den automatischen Magicline Sync per Cron."),
            ("magicline_auto_sync_cron", "0 */6 * * *", "Cron-Zeitplan (UTC) für Magicline Auto Sync."),
            ("magicline_last_sync_at", "", "Zeitpunkt des letzten Magicline Sync-Runs (ISO-UTC)."),
            ("magicline_last_sync_status", "never", "Status des letzten Magicline Sync-Runs (never|ok|error:<details>)."),
            ("magicline_last_sync_error", "", "Letzte Fehlermeldung des Magicline Sync-Runs."),
            ("tenant_display_name", "", "Mandantenanzeige-Name im UI."),
            ("tenant_timezone", "Europe/Berlin", "Standard-Zeitzone des Tenants (IANA)."),
            ("tenant_locale", "de-DE", "Standard-Lokalisierung des Tenants."),
            ("tenant_notify_email", "", "Tenant-Benachrichtigungsadresse (Ops/Eskalationen)."),
            ("tenant_notify_telegram", "", "Tenant-Notifications via Telegram Chat-ID."),
            ("tenant_escalation_sla_minutes", "15", "SLA-Zielzeit in Minuten für Eskalationen."),
            ("tenant_live_refresh_seconds", "5", "Auto-Refresh Intervall (Sek.) für Live Monitor."),
            ("smtp_host", "", "SMTP Host für Verifizierungs-E-Mails."),
            ("smtp_port", "587", "SMTP Port (z. B. 587 für STARTTLS)."),
            ("smtp_username", "", "SMTP Benutzername."),
            ("smtp_password", "", "SMTP Passwort / App-Passwort."),
            ("smtp_from_email", "", "Absender-E-Mail für Verifizierung."),
            ("smtp_from_name", "Ariia", "Absendername für Verifizierung."),
            ("smtp_use_starttls", "true", "STARTTLS für SMTP aktivieren."),
            ("verification_email_subject", "Dein ARIIA Verifizierungscode", "Betreff der Verifizierungs-E-Mails."),
            ("postmark_server_token", "", "Postmark Server Token für transaktionale E-Mails."),
            ("postmark_inbound_token", "", "Shared Secret für Postmark Inbound Webhook."),
            ("postmark_message_stream", "outbound", "Postmark Message Stream (z. B. outbound)."),
            ("email_channel_enabled", "false", "Aktiviert den E-Mail Kommunikationskanal."),
            ("email_outbound_from", "", "Absenderadresse für Channel-Antworten (z. B. support@tenant.ariia.io)."),
            ("twilio_account_sid", "", "Twilio Account SID für SMS/Voice."),
            ("twilio_auth_token", "", "Twilio Auth Token für Webhook-Signatur und API."),
            ("twilio_sms_number", "", "Twilio Telefonnummer für SMS Outbound."),
            ("twilio_voice_number", "", "Twilio Telefonnummer für Voice Inbound/Outbound."),
            ("twilio_voice_stream_url", "", "WSS Endpoint für Voice Media Streams."),
            ("sms_channel_enabled", "false", "Aktiviert den SMS Kommunikationskanal."),
            ("voice_channel_enabled", "false", "Aktiviert den Voice Kommunikationskanal."),
            ("billing_default_provider", "stripe",
             "Globaler Default Payment Provider (systemweit, tenant-übergreifend)."),
            ("billing_plans_json",
             '[{\"id\":\"starter\",\"name\":\"Starter\",\"priceMonthly\":149,\"membersIncluded\":500,\"messagesIncluded\":10000,\"aiAgents\":2,\"support\":\"Email\"},'
             '{\"id\":\"growth\",\"name\":\"Growth\",\"priceMonthly\":349,\"membersIncluded\":2500,\"messagesIncluded\":50000,\"aiAgents\":5,\"support\":\"Priority\",\"highlight\":true},'
             '{\"id\":\"enterprise\",\"name\":\"Enterprise\",\"priceMonthly\":999,\"membersIncluded\":10000,\"messagesIncluded\":250000,\"aiAgents\":10,\"support\":\"Dedicated CSM\"}]',
             "Globaler Plan-Katalog als JSON (systemweit, tenant-übergreifend)."),
            ("billing_providers_json",
             '[{\"id\":\"stripe\",\"name\":\"Stripe\",\"enabled\":true,\"mode\":\"mock\",\"note\":\"Default Provider\"},'
             '{\"id\":\"paypal\",\"name\":\"PayPal\",\"enabled\":false,\"mode\":\"mock\",\"note\":\"Planned\"},'
             '{\"id\":\"klarna\",\"name\":\"Klarna\",\"enabled\":false,\"mode\":\"mock\",\"note\":\"Planned\"}]',
             "Globale Payment-Provider-Konfiguration als JSON (systemweit, tenant-übergreifend)."),
            ("billing_stripe_enabled", "false", "Stripe Connector global aktiv/inaktiv."),
            ("billing_stripe_mode", "test", "Stripe Connector Modus (test|live)."),
            ("billing_stripe_publishable_key", "", "Stripe Publishable Key (pk_*)."),
            ("billing_stripe_secret_key", "", "Stripe Secret Key (sk_*)."),
            ("billing_stripe_webhook_secret", "", "Stripe Webhook Secret (whsec_*)."),
        ]
        with self._lock:
            self._backfill_legacy_settings_tenant_ids()
            sys_tid = self.get_system_tenant_id()
            for key, value, description in defaults:
                exists = (
                    self.db.query(Setting)
                    .filter(Setting.tenant_id == sys_tid, Setting.key == key)
                    .first()
                )
                if not exists:
                    self.db.add(
                        Setting(
                            tenant_id=sys_tid,
                            key=key,
                            value=value,
                            description=description,
                        )
                    )
            self.db.commit()

# Singleton Instance
persistence = PersistenceService()
persistence.init_default_settings()
