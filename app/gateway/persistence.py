import structlog
import threading
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.models import ChatSession, ChatMessage, Setting, Tenant
from app.core.db import SessionLocal, engine, Base
from app.gateway.schemas import Platform

logger = structlog.get_logger()
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

# Ensure tables exist + run column migrations
Base.metadata.create_all(bind=engine)

class PersistenceService:
    def __init__(self):
        self.db = SessionLocal()
        self._lock = threading.RLock()
        self._dialect = engine.dialect.name
        self._backfill_legacy_settings_tenant_ids()

    def __del__(self):
        self.db.close()

    def _backfill_legacy_settings_tenant_ids(self) -> None:
        try:
            self.db.rollback()
            system = self.db.query(Tenant).filter(Tenant.slug == "system").first()
            if not system:
                return
            self.db.execute(
                text("UPDATE settings SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
                {"tenant_id": system.id},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _resolve_tenant_id(self, tenant_id: int | None = None) -> int | None:
        if tenant_id is not None:
            return tenant_id
        tenant = self.db.query(Tenant).filter(Tenant.slug == "system").first()
        return tenant.id if tenant else None

    def get_default_tenant_id(self) -> int | None:
        with self._lock:
            return self._resolve_tenant_id(None)

    def get_tenant_slug(self, tenant_id: int | None) -> str:
        with self._lock:
            resolved = self._resolve_tenant_id(tenant_id)
            if resolved is None:
                return "system"
            row = self.db.query(Tenant).filter(Tenant.id == resolved).first()
            return (row.slug if row and row.slug else "system").strip().lower()

    def is_global_system_setting(self, key: str) -> bool:
        return (key or "").strip().lower() in GLOBAL_SYSTEM_SETTING_KEYS

    def _settings_tenant_id_for_key(self, key: str, tenant_id: int | None = None) -> int | None:
        if self.is_global_system_setting(key):
            return self._resolve_tenant_id(None)
        return self._resolve_tenant_id(tenant_id)

    def _storage_key_for_setting(self, key: str, tenant_id: int | None) -> str:
        if self._dialect != "sqlite":
            return key
        # SQLite legacy schema still has unique(settings.key). Use key namespacing
        # for tenant overrides while preserving plain keys as system defaults.
        system_tenant_id = self._resolve_tenant_id(None)
        if tenant_id is None or tenant_id == system_tenant_id or self.is_global_system_setting(key):
            return key
        return f"tenant:{tenant_id}:{key}"

    def get_or_create_session(
        self,
        user_id: str,
        platform: Platform,
        user_name: str = None,
        phone_number: str = None,
        member_id: str = None,
        tenant_id: int | None = None,
    ) -> ChatSession:
        with self._lock:
            # Keep the long-lived SQLAlchemy session in sync with external updates
            # (e.g. admin reset endpoints using separate transactions).
            self.db.expire_all()
            resolved_tenant_id = self._resolve_tenant_id(tenant_id)
            platform_str = platform.value if isinstance(platform, Platform) else str(platform)
            base_q = self.db.query(ChatSession).filter(ChatSession.user_id == user_id)

            session = None
            if resolved_tenant_id is not None:
                session = (
                    base_q
                    .filter(ChatSession.tenant_id == resolved_tenant_id)
                    .first()
                )
                if not session:
                    legacy = base_q.filter(ChatSession.tenant_id.is_(None)).first()
                    if legacy:
                        legacy.tenant_id = resolved_tenant_id
                        session = legacy
            else:
                session = base_q.first()

            if not session:
                # Legacy uniqueness: chat_sessions.user_id is globally unique.
                # Until composite uniqueness (tenant_id, user_id) is introduced,
                # reuse the existing row if the same external user_id already exists.
                existing_any = base_q.first()
                if existing_any:
                    session = existing_any
                    if session.tenant_id is None and resolved_tenant_id is not None:
                        session.tenant_id = resolved_tenant_id
                        self.db.commit()
                        self.db.refresh(session)

            if not session:
                session = ChatSession(
                    user_id=user_id,
                    tenant_id=resolved_tenant_id,
                    platform=platform_str,
                    user_name=user_name,
                    phone_number=phone_number,
                    member_id=member_id
                )
                self.db.add(session)
                self.db.commit()
                self.db.refresh(session)
                logger.info("db.session_created", user_id=user_id, tenant_id=resolved_tenant_id, platform=platform_str)
            else:
                # Update fields if provided and different
                updated = False
                if resolved_tenant_id is not None and session.tenant_id != resolved_tenant_id:
                    session.tenant_id = resolved_tenant_id
                    updated = True
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
                    logger.info(
                        "db.session_updated",
                        user_id=user_id,
                        tenant_id=session.tenant_id,
                        name=user_name,
                        phone=phone_number,
                        member_id=member_id,
                    )

            return session

    def get_session_by_user_id(self, user_id: str, tenant_id: int | None = None) -> ChatSession | None:
        """Get session by user_id (any platform)."""
        with self._lock:
            q = self.db.query(ChatSession).filter(ChatSession.user_id == user_id)
            resolved_tenant_id = self._resolve_tenant_id(tenant_id)
            if resolved_tenant_id is not None:
                q = q.filter(ChatSession.tenant_id == resolved_tenant_id)
            return q.first()

    def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        platform: Platform,
        metadata: dict = None,
        user_name: str = None,
        phone_number: str = None,
        member_id: str = None,
        tenant_id: int | None = None,
    ):
        with self._lock:
            try:
                session = self.get_or_create_session(
                    user_id,
                    platform,
                    user_name,
                    phone_number,
                    member_id,
                    tenant_id=tenant_id,
                )

                # Convert metadata to JSON string if needed
                import json
                meta_json = json.dumps(metadata) if metadata else None

                msg = ChatMessage(
                    session_id=user_id,
                    tenant_id=session.tenant_id,
                    role=role,
                    content=content,
                    metadata_json=meta_json
                )
                self.db.add(msg)

                # Update last activity
                from datetime import datetime, timezone
                session.last_message_at = datetime.now(timezone.utc)
                session.is_active = True

                self.db.commit()
                logger.info("db.message_saved", user_id=user_id, tenant_id=session.tenant_id, role=role)
            except Exception as e:
                logger.error("db.save_failed", error=str(e))
                self.db.rollback()

    # Admin Stats
    def get_stats(self, tenant_id: int | None = None):
        with self._lock:
            resolved_tenant_id = self._resolve_tenant_id(tenant_id)
            msg_q = self.db.query(ChatMessage)
            sess_q = self.db.query(ChatSession)
            if resolved_tenant_id is not None:
                msg_q = msg_q.filter(ChatMessage.tenant_id == resolved_tenant_id)
                sess_q = sess_q.filter(ChatSession.tenant_id == resolved_tenant_id)
            total_messages = msg_q.count()
            active_users = sess_q.count()
        
        # Count active handoff requests from Redis
        # We need to access Redis here. Ideally inject RedisBus or use a separate Redis client.
        # For simplicity in this monolithic service, let's assume we can get it via a helper or pass it in.
        # OR: faster, just check DB if we were storing handoffs there. 
        # But we store handoffs in Redis `session:*:human_mode`.
        # Let's count them using a direct redis connection for now or rely on the caller?
        # Better: caller (admin.py) has redis logic for handoffs. Let's move that logic here OR keep stats simple.
        
        # ACTUALLY: Let's store handoffs in DB? No, they are ephemeral.
        # Let's just return the two we have, and let admin.py enrich it or 
        # let's add a `get_handoffs_count` here if we move redis logic.
        
        return {
            "total_messages": total_messages,
            "active_users": active_users
        }
    
    def get_recent_sessions(self, limit=10, tenant_id: int | None = None, active_only: bool = False):
        with self._lock:
            q = self.db.query(ChatSession)
            resolved_tenant_id = self._resolve_tenant_id(tenant_id)
            if resolved_tenant_id is not None:
                q = q.filter(ChatSession.tenant_id == resolved_tenant_id)
            if active_only:
                q = q.filter(ChatSession.is_active.is_(True))
            return q.order_by(ChatSession.last_message_at.desc()).limit(limit).all()

    def get_chat_history(self, user_id: str, limit=50, tenant_id: int | None = None):
        with self._lock:
            # Return the newest messages capped by limit, but keep chronological order
            # for downstream consumers (router context + admin history rendering).
            q = self.db.query(ChatMessage).filter(ChatMessage.session_id == user_id)
            resolved_tenant_id = self._resolve_tenant_id(tenant_id)
            if resolved_tenant_id is not None:
                q = q.filter(ChatMessage.tenant_id == resolved_tenant_id)
            rows = q.order_by(ChatMessage.timestamp.desc()).limit(limit).all()
            rows.reverse()
            return rows

    def reset_chat(
        self,
        user_id: str,
        *,
        clear_verification: bool = True,
        clear_contact: bool = False,
        clear_history: bool = True,
        tenant_id: int | None = None,
    ) -> dict:
        """Reset chat state in the same shared session used by runtime flow."""
        with self._lock:
            deleted_messages = 0
            session_found = False
            try:
                self.db.expire_all()
                resolved_tenant_id = self._resolve_tenant_id(tenant_id)
                sess_q = self.db.query(ChatSession).filter(ChatSession.user_id == user_id)
                if resolved_tenant_id is not None:
                    sess_q = sess_q.filter(ChatSession.tenant_id == resolved_tenant_id)
                session = sess_q.first()
                session_found = session is not None

                if clear_history:
                    msg_q = self.db.query(ChatMessage).filter(ChatMessage.session_id == user_id)
                    if resolved_tenant_id is not None:
                        msg_q = msg_q.filter(ChatMessage.tenant_id == resolved_tenant_id)
                    deleted_messages = msg_q.delete(synchronize_session=False)

                if session is not None:
                    if clear_verification:
                        session.member_id = None
                    if clear_contact:
                        session.phone_number = None
                        session.email = None
                    session.is_active = False

                self.db.commit()
                self.db.expire_all()
                logger.info(
                    "db.chat_reset",
                    user_id=user_id,
                    deleted_messages=deleted_messages,
                    clear_verification=clear_verification,
                    clear_contact=clear_contact,
                    clear_history=clear_history,
                )
                return {"session_found": session_found, "deleted_messages": deleted_messages}
            except Exception as e:
                self.db.rollback()
                logger.error("db.chat_reset_failed", user_id=user_id, error=str(e))
                raise

    def get_settings(self, tenant_id: int | None = None):
        with self._lock:
            self._backfill_legacy_settings_tenant_ids()
            resolved_tenant_id = self._resolve_tenant_id(tenant_id)
            if resolved_tenant_id is None:
                return []
            if self._dialect == "sqlite":
                system_tenant_id = self._resolve_tenant_id(None)
                if resolved_tenant_id == system_tenant_id:
                    return (
                        self.db.query(Setting)
                        .filter(~Setting.key.like("tenant:%"))
                        .order_by(Setting.key.asc())
                        .all()
                    )
                prefix = f"tenant:{resolved_tenant_id}:"
                return (
                    self.db.query(Setting)
                    .filter(Setting.key.like(f"{prefix}%"))
                    .order_by(Setting.key.asc())
                    .all()
                )
            return (
                self.db.query(Setting)
                .filter(Setting.tenant_id == resolved_tenant_id)
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
        with self._lock:
            self._backfill_legacy_settings_tenant_ids()
            target_tenant_id = self._settings_tenant_id_for_key(key, tenant_id)
            if target_tenant_id is None:
                return default
            if self._dialect == "sqlite":
                storage_key = self._storage_key_for_setting(key, target_tenant_id)
                row = self.db.query(Setting).filter(Setting.key == storage_key).first()
                if row:
                    return row.value
                if fallback_to_system and not self.is_global_system_setting(key):
                    system_key = self._storage_key_for_setting(key, self._resolve_tenant_id(None))
                    system_row = self.db.query(Setting).filter(Setting.key == system_key).first()
                    if system_row:
                        return system_row.value
                return default
            row = (
                self.db.query(Setting)
                .filter(Setting.tenant_id == target_tenant_id, Setting.key == key)
                .first()
            )
            if row:
                return row.value
            if fallback_to_system and not self.is_global_system_setting(key):
                system_tenant_id = self._resolve_tenant_id(None)
                if system_tenant_id is not None and system_tenant_id != target_tenant_id:
                    system_row = (
                        self.db.query(Setting)
                        .filter(Setting.tenant_id == system_tenant_id, Setting.key == key)
                        .first()
                    )
                    if system_row:
                        return system_row.value
            return default

    def upsert_setting(
        self,
        key: str,
        value: str,
        description: str | None = None,
        tenant_id: int | None = None,
    ) -> None:
        with self._lock:
            self._backfill_legacy_settings_tenant_ids()
            target_tenant_id = self._settings_tenant_id_for_key(key, tenant_id)
            if target_tenant_id is None:
                raise ValueError(f"Unable to resolve tenant scope for setting: {key}")
            if self._dialect == "sqlite":
                storage_key = self._storage_key_for_setting(key, target_tenant_id)
                row = self.db.query(Setting).filter(Setting.key == storage_key).first()
                if row:
                    row.value = value
                    if description is not None:
                        row.description = description
                else:
                    self.db.add(
                        Setting(
                            tenant_id=target_tenant_id,
                            key=storage_key,
                            value=value,
                            description=description,
                        )
                    )
                self.db.commit()
                return
            row = (
                self.db.query(Setting)
                .filter(Setting.tenant_id == target_tenant_id, Setting.key == key)
                .first()
            )
            if row:
                row.value = value
                if description is not None:
                    row.description = description
            else:
                self.db.add(
                    Setting(
                        tenant_id=target_tenant_id,
                        key=key,
                        value=value,
                        description=description,
                    )
                )
            self.db.commit()

    def init_default_settings(self) -> None:
        """Seed default settings if they don't exist yet."""
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
            ("bridge_webhook_url", "http://arni-core:8000/webhook/whatsapp", "Webhook-Ziel fuer WhatsApp QR-Bridge."),
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
            ("smtp_from_name", "Arni", "Absendername für Verifizierung."),
            ("smtp_use_starttls", "true", "STARTTLS für SMTP aktivieren."),
            ("verification_email_subject", "Dein ARNI Verifizierungscode", "Betreff der Verifizierungs-E-Mail."),
            ("postmark_server_token", "", "Postmark Server Token für transaktionale E-Mails."),
            ("postmark_inbound_token", "", "Shared Secret für Postmark Inbound Webhook."),
            ("postmark_message_stream", "outbound", "Postmark Message Stream (z. B. outbound)."),
            ("email_channel_enabled", "false", "Aktiviert den E-Mail Kommunikationskanal."),
            ("email_outbound_from", "", "Absenderadresse für Channel-Antworten (z. B. support@tenant.arni.io)."),
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
            system_tenant_id = self._resolve_tenant_id(None)
            if system_tenant_id is None:
                return
            for key, value, description in defaults:
                storage_key = self._storage_key_for_setting(key, system_tenant_id)
                exists = (
                    self.db.query(Setting)
                    .filter(Setting.key == storage_key)
                    .first()
                )
                if not exists:
                    self.db.add(
                        Setting(
                            tenant_id=system_tenant_id,
                            key=storage_key,
                            value=value,
                            description=description,
                        )
                    )
            self.db.commit()


# Singleton Instance
persistence = PersistenceService()
persistence.init_default_settings()
