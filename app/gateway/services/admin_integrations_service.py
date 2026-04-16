from __future__ import annotations

import asyncio
import smtplib
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from fastapi import HTTPException

from app.core.auth import AuthContext
from app.gateway.admin_shared import (
    REDACTED_SECRET_VALUE,
    get_setting_with_env_fallback,
    is_sensitive_key,
    mask_if_sensitive,
    safe_tenant_slug,
    write_admin_audit,
)
from app.gateway.persistence import persistence
from app.gateway.connector_hub_repository import connector_hub_repository
from app.shared.db import open_session, transaction_scope
from app.integrations.connector_registry import CONNECTOR_DOCS, CONNECTOR_REGISTRY, get_connector_meta, list_connectors
from app.integrations.magicline.client import MagiclineClient

logger = structlog.get_logger()


class AdminIntegrationsService:
    @staticmethod
    def _get_config_key(tenant_id: int, connector_id: str, field_key: str) -> str:
        return f"integration_{connector_id}_{tenant_id}_{field_key}"

    @staticmethod
    def _persist_integration_key(setting_key: str, value: str | None, tenant_id: int | None = None) -> None:
        if value is None:
            return
        if is_sensitive_key(setting_key) and value == REDACTED_SECRET_VALUE:
            return
        persistence.upsert_setting(setting_key, value, tenant_id=tenant_id)

    @staticmethod
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

    @staticmethod
    def _upsert_tenant_integration_rows(body: Any, tenant_id: int) -> None:
        from app.core.integration_models import TenantIntegration

        mapping: list[str] = []
        if body.magicline and body.magicline.api_key:
            mapping.append("magicline")
        if body.telegram and body.telegram.bot_token:
            mapping.append("telegram")
        if body.smtp and body.smtp.host:
            mapping.append("smtp_email")
        if body.email_channel and body.email_channel.get("postmark_server_token"):
            mapping.append("postmark")
        if body.sms_channel and body.sms_channel.get("twilio_account_sid"):
            mapping.append("sms")
        if body.voice_channel and body.voice_channel.get("twilio_account_sid"):
            mapping.append("twilio_voice")

        if not mapping:
            return

        now = datetime.now(timezone.utc)
        try:
            with transaction_scope() as db:
                for integration_id in mapping:
                    existing = db.query(TenantIntegration).filter_by(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                    ).first()
                    if existing:
                        existing.status = "enabled"
                        existing.enabled = True
                        existing.updated_at = now
                    else:
                        db.add(TenantIntegration(
                            tenant_id=tenant_id,
                            integration_id=integration_id,
                            status="enabled",
                            enabled=True,
                            created_at=now,
                            updated_at=now,
                        ))
        except Exception as exc:
            logger.warning("admin.upsert_tenant_integration_rows_failed", error=str(exc))

    @staticmethod
    def _trigger_magicline_sync_if_configured(tenant_id: int) -> None:
        from app.integrations.magicline import _client_instances

        _client_instances.pop(tenant_id, None)
        ml_api_key = persistence.get_setting("magicline_api_key", None, tenant_id=tenant_id)
        ml_base_url = persistence.get_setting("magicline_base_url", None, tenant_id=tenant_id)
        if not (ml_api_key and ml_base_url):
            return

        from app.integrations.magicline.members_sync import sync_members_from_magicline
        from app.integrations.magicline.scheduler import _enrich_tenant_members

        def _bg_sync_on_config_save() -> None:
            try:
                from app.gateway.persistence import PersistenceService

                PersistenceService()
                result = sync_members_from_magicline(tenant_id=tenant_id)
                logger.info("admin.magicline_config_sync.completed", tenant_id=tenant_id, result=result)
                _enrich_tenant_members(tenant_id)
            except Exception as exc:
                logger.error("admin.magicline_config_sync.failed", tenant_id=tenant_id, error=str(exc))

        threading.Thread(
            target=_bg_sync_on_config_save,
            daemon=True,
            name=f"cfg-sync-t{tenant_id}",
        ).start()
        logger.info("admin.magicline_config_sync.started", tenant_id=tenant_id)

    def get_integrations_config(self, user: AuthContext) -> dict[str, Any]:
        return {
            "telegram": {
                "bot_token": mask_if_sensitive("telegram_bot_token", get_setting_with_env_fallback("telegram_bot_token", "telegram_bot_token", tenant_id=user.tenant_id)),
                "admin_chat_id": get_setting_with_env_fallback("telegram_admin_chat_id", "telegram_admin_chat_id", tenant_id=user.tenant_id),
                "webhook_secret": mask_if_sensitive("telegram_webhook_secret", get_setting_with_env_fallback("telegram_webhook_secret", "telegram_webhook_secret", tenant_id=user.tenant_id)),
            },
            "whatsapp": {
                "mode": get_setting_with_env_fallback("whatsapp_mode", None, "qr", tenant_id=user.tenant_id),
                "meta_verify_token": mask_if_sensitive("meta_verify_token", get_setting_with_env_fallback("meta_verify_token", "meta_verify_token", tenant_id=user.tenant_id)),
                "meta_access_token": mask_if_sensitive("meta_access_token", get_setting_with_env_fallback("meta_access_token", "meta_access_token", tenant_id=user.tenant_id)),
                "meta_app_secret": mask_if_sensitive("meta_app_secret", get_setting_with_env_fallback("meta_app_secret", "meta_app_secret", tenant_id=user.tenant_id)),
                "meta_phone_number_id": get_setting_with_env_fallback("meta_phone_number_id", "meta_phone_number_id", tenant_id=user.tenant_id),
                "bridge_auth_dir": f"/app/data/whatsapp/auth_info_{safe_tenant_slug(user)}",
            },
            "magicline": {
                "base_url": get_setting_with_env_fallback("magicline_base_url", "magicline_base_url", tenant_id=user.tenant_id),
                "api_key": mask_if_sensitive("magicline_api_key", get_setting_with_env_fallback("magicline_api_key", "magicline_api_key", tenant_id=user.tenant_id)),
                "tenant_id": get_setting_with_env_fallback("magicline_tenant_id", "magicline_tenant_id", tenant_id=user.tenant_id),
                "auto_sync_enabled": get_setting_with_env_fallback("magicline_auto_sync_enabled", None, "false", tenant_id=user.tenant_id),
                "auto_sync_cron": get_setting_with_env_fallback("magicline_auto_sync_cron", None, "0 */6 * * *", tenant_id=user.tenant_id),
                "last_sync_at": get_setting_with_env_fallback("magicline_last_sync_at", None, "", tenant_id=user.tenant_id),
                "last_sync_status": get_setting_with_env_fallback("magicline_last_sync_status", None, "never", tenant_id=user.tenant_id),
                "last_sync_error": get_setting_with_env_fallback("magicline_last_sync_error", None, "", tenant_id=user.tenant_id),
            },
            "smtp": {
                "host": get_setting_with_env_fallback("smtp_host", "smtp_host", tenant_id=user.tenant_id),
                "port": get_setting_with_env_fallback("smtp_port", "smtp_port", tenant_id=user.tenant_id),
                "username": mask_if_sensitive("smtp_username", get_setting_with_env_fallback("smtp_username", "smtp_username", tenant_id=user.tenant_id)),
                "password": mask_if_sensitive("smtp_password", get_setting_with_env_fallback("smtp_password", "smtp_password", tenant_id=user.tenant_id)),
                "from_email": get_setting_with_env_fallback("smtp_from_email", "smtp_from_email", tenant_id=user.tenant_id),
                "from_name": get_setting_with_env_fallback("smtp_from_name", "smtp_from_name", tenant_id=user.tenant_id),
                "use_starttls": get_setting_with_env_fallback("smtp_use_starttls", "smtp_use_starttls", "true", tenant_id=user.tenant_id),
                "verification_subject": get_setting_with_env_fallback("verification_email_subject", None, "Dein ARIIA Verifizierungscode", tenant_id=user.tenant_id),
            },
            "email_channel": {
                "enabled": get_setting_with_env_fallback("email_channel_enabled", None, "false", tenant_id=user.tenant_id),
                "postmark_server_token": mask_if_sensitive("postmark_server_token", get_setting_with_env_fallback("postmark_server_token", None, "", tenant_id=user.tenant_id)),
                "postmark_inbound_token": mask_if_sensitive("postmark_inbound_token", get_setting_with_env_fallback("postmark_inbound_token", None, "", tenant_id=user.tenant_id)),
                "message_stream": get_setting_with_env_fallback("postmark_message_stream", None, "outbound", tenant_id=user.tenant_id),
                "from_email": get_setting_with_env_fallback("email_outbound_from", None, "", tenant_id=user.tenant_id),
            },
            "sms_channel": {
                "enabled": get_setting_with_env_fallback("sms_channel_enabled", None, "false", tenant_id=user.tenant_id),
                "twilio_account_sid": get_setting_with_env_fallback("twilio_account_sid", None, "", tenant_id=user.tenant_id),
                "twilio_auth_token": mask_if_sensitive("twilio_auth_token", get_setting_with_env_fallback("twilio_auth_token", None, "", tenant_id=user.tenant_id)),
                "twilio_sms_number": get_setting_with_env_fallback("twilio_sms_number", None, "", tenant_id=user.tenant_id),
            },
            "voice_channel": {
                "enabled": get_setting_with_env_fallback("voice_channel_enabled", None, "false", tenant_id=user.tenant_id),
                "twilio_account_sid": get_setting_with_env_fallback("twilio_account_sid", None, "", tenant_id=user.tenant_id),
                "twilio_auth_token": mask_if_sensitive("twilio_auth_token", get_setting_with_env_fallback("twilio_auth_token", None, "", tenant_id=user.tenant_id)),
                "twilio_voice_number": get_setting_with_env_fallback("twilio_voice_number", None, "", tenant_id=user.tenant_id),
                "twilio_voice_stream_url": get_setting_with_env_fallback("twilio_voice_stream_url", None, "", tenant_id=user.tenant_id),
            },
        }

    def update_integrations_config(self, user: AuthContext, body: Any) -> dict[str, str]:
        if body.telegram:
            self._persist_integration_key("telegram_bot_token", body.telegram.bot_token, tenant_id=user.tenant_id)
            self._persist_integration_key("telegram_admin_chat_id", body.telegram.admin_chat_id, tenant_id=user.tenant_id)
            self._persist_integration_key("telegram_webhook_secret", body.telegram.webhook_secret, tenant_id=user.tenant_id)
        if body.whatsapp:
            self._persist_integration_key("whatsapp_mode", body.whatsapp.mode, tenant_id=user.tenant_id)
            self._persist_integration_key("meta_verify_token", body.whatsapp.meta_verify_token, tenant_id=user.tenant_id)
            self._persist_integration_key("meta_access_token", body.whatsapp.meta_access_token, tenant_id=user.tenant_id)
            self._persist_integration_key("meta_app_secret", body.whatsapp.meta_app_secret, tenant_id=user.tenant_id)
            self._persist_integration_key("meta_phone_number_id", body.whatsapp.meta_phone_number_id, tenant_id=user.tenant_id)
            self._persist_integration_key("bridge_auth_dir", body.whatsapp.bridge_auth_dir, tenant_id=user.tenant_id)
        if body.magicline:
            self._persist_integration_key("magicline_base_url", body.magicline.base_url, tenant_id=user.tenant_id)
            self._persist_integration_key("magicline_api_key", body.magicline.api_key, tenant_id=user.tenant_id)
            self._persist_integration_key("magicline_tenant_id", body.magicline.tenant_id, tenant_id=user.tenant_id)
            self._persist_integration_key("magicline_auto_sync_enabled", body.magicline.auto_sync_enabled, tenant_id=user.tenant_id)
            self._persist_integration_key("magicline_auto_sync_cron", body.magicline.auto_sync_cron, tenant_id=user.tenant_id)
            self._trigger_magicline_sync_if_configured(user.tenant_id)
        if body.smtp:
            self._persist_integration_key("smtp_host", body.smtp.host, tenant_id=user.tenant_id)
            self._persist_integration_key("smtp_port", body.smtp.port, tenant_id=user.tenant_id)
            self._persist_integration_key("smtp_username", body.smtp.username, tenant_id=user.tenant_id)
            self._persist_integration_key("smtp_password", body.smtp.password, tenant_id=user.tenant_id)
            self._persist_integration_key("smtp_from_email", body.smtp.from_email, tenant_id=user.tenant_id)
            self._persist_integration_key("smtp_from_name", body.smtp.from_name, tenant_id=user.tenant_id)
            self._persist_integration_key("smtp_use_starttls", body.smtp.use_starttls, tenant_id=user.tenant_id)
            self._persist_integration_key("verification_email_subject", body.smtp.verification_subject, tenant_id=user.tenant_id)
        if body.email_channel:
            self._persist_integration_key("email_channel_enabled", body.email_channel.get("enabled"), tenant_id=user.tenant_id)
            self._persist_integration_key("postmark_server_token", body.email_channel.get("postmark_server_token"), tenant_id=user.tenant_id)
            self._persist_integration_key("postmark_inbound_token", body.email_channel.get("postmark_inbound_token"), tenant_id=user.tenant_id)
            self._persist_integration_key("postmark_message_stream", body.email_channel.get("message_stream"), tenant_id=user.tenant_id)
            self._persist_integration_key("email_outbound_from", body.email_channel.get("from_email"), tenant_id=user.tenant_id)
        if body.sms_channel:
            self._persist_integration_key("sms_channel_enabled", body.sms_channel.get("enabled"), tenant_id=user.tenant_id)
            self._persist_integration_key("twilio_account_sid", body.sms_channel.get("twilio_account_sid"), tenant_id=user.tenant_id)
            self._persist_integration_key("twilio_auth_token", body.sms_channel.get("twilio_auth_token"), tenant_id=user.tenant_id)
            self._persist_integration_key("twilio_sms_number", body.sms_channel.get("twilio_sms_number"), tenant_id=user.tenant_id)
        if body.voice_channel:
            self._persist_integration_key("voice_channel_enabled", body.voice_channel.get("enabled"), tenant_id=user.tenant_id)
            self._persist_integration_key("twilio_account_sid", body.voice_channel.get("twilio_account_sid"), tenant_id=user.tenant_id)
            self._persist_integration_key("twilio_auth_token", body.voice_channel.get("twilio_auth_token"), tenant_id=user.tenant_id)
            self._persist_integration_key("twilio_voice_number", body.voice_channel.get("twilio_voice_number"), tenant_id=user.tenant_id)
            self._persist_integration_key("twilio_voice_stream_url", body.voice_channel.get("twilio_voice_stream_url"), tenant_id=user.tenant_id)

        self._upsert_tenant_integration_rows(body, user.tenant_id)
        logger.info("admin.integrations_config_updated")
        return {"status": "ok"}

    def delete_integration_config(self, user: AuthContext, provider: str) -> dict[str, Any]:
        normalized = (provider or "").strip().lower()
        prefix_map = {
            "telegram": "telegram_",
            "whatsapp": "meta_",
            "whatsapp_bridge": "whatsapp_",
            "magicline": "magicline_",
            "smtp": "smtp_",
            "email": "postmark_",
            "sms": "twilio_",
            "voice": "twilio_voice_",
        }

        prefix = prefix_map.get(normalized, f"{normalized}_")
        deleted_count = persistence.delete_settings_by_prefix(prefix, tenant_id=user.tenant_id)
        if normalized == "whatsapp":
            persistence.delete_setting("whatsapp_mode", tenant_id=user.tenant_id)
            deleted_count += 1

        write_admin_audit(
            actor=user,
            action="integration.delete",
            category="settings",
            target_type="integration",
            target_id=normalized,
            details={"deleted_keys_count": deleted_count, "prefix": prefix},
        )
        logger.info("admin.integration_deleted", provider=normalized, tenant_id=user.tenant_id, count=deleted_count)
        return {"status": "ok", "deleted_count": deleted_count}

    def _resolve_test_value(self, user: AuthContext, provider: str, config: dict[str, Any] | None, key: str, env_attr: str | None = None, default: str = "") -> str:
        if config:
            value = config.get(key)
            if value is None:
                shorthand = key.replace(f"{provider}_", "")
                if shorthand != key:
                    value = config.get(shorthand)
            if value is not None:
                final_value = str(value or "")
                if final_value != REDACTED_SECRET_VALUE and final_value.strip() != "":
                    return final_value
        return get_setting_with_env_fallback(key, env_attr, default, tenant_id=user.tenant_id)

    async def test_integration_connector(self, user: AuthContext, provider: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized = (provider or "").strip().lower()
        if normalized not in {"telegram", "whatsapp", "magicline", "smtp", "email", "sms", "voice"}:
            raise HTTPException(status_code=404, detail="Unknown integration provider")

        started = time.perf_counter()
        try:
            if normalized == "telegram":
                bot_token = self._resolve_test_value(user, normalized, config, "telegram_bot_token")
                if not bot_token:
                    raise HTTPException(status_code=422, detail="Telegram bot token is not configured")
                async with httpx.AsyncClient(timeout=12.0) as client:
                    response = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                if response.status_code in {401, 404}:
                    raise HTTPException(status_code=502, detail="Telegram Bot Token ungültig")
                if response.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"Telegram API nicht erreichbar ({response.status_code})")
                payload = response.json() if response.content else {}
                bot = payload.get("result", {}) if isinstance(payload, dict) else {}
                detail = f"Bot @{bot.get('username', 'unknown')} reachable"
            elif normalized == "whatsapp":
                mode = self._resolve_test_value(user, normalized, config, "whatsapp_mode", default="qr")
                if mode == "qr":
                    health_url = self._resolve_test_value(user, normalized, config, "bridge_health_url")
                    if health_url:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            response = await client.get(health_url)
                        if response.status_code >= 400:
                            raise HTTPException(status_code=502, detail=f"WhatsApp QR-Bridge nicht erreichbar ({response.status_code})")
                        detail = f"QR-Bridge health OK ({response.status_code})"
                    else:
                        detail = "QR-Bridge URL not configured, but mode is QR."
                else:
                    access_token = self._resolve_test_value(user, normalized, config, "meta_access_token")
                    if not access_token:
                        raise HTTPException(status_code=422, detail="WhatsApp Meta Access Token nicht konfiguriert")
                    async with httpx.AsyncClient(timeout=12.0) as client:
                        response = await client.get("https://graph.facebook.com/v21.0/me", params={"access_token": access_token})
                    if response.status_code in {401, 403}:
                        raise HTTPException(status_code=502, detail="WhatsApp Meta Token ungültig oder abgelaufen")
                    detail = "WhatsApp Meta Graph token valid"
            elif normalized == "magicline":
                base_url = self._resolve_test_value(user, normalized, config, "magicline_base_url")
                api_key = self._resolve_test_value(user, normalized, config, "magicline_api_key")
                if not base_url or not api_key:
                    raise HTTPException(status_code=422, detail="Magicline config incomplete")

                def _magicline_probe() -> dict[str, Any]:
                    client = MagiclineClient(base_url=base_url, api_key=api_key, timeout=15)
                    return client.studio_info()

                data = await asyncio.to_thread(_magicline_probe)
                studio = data.get("name") or data.get("studioName") or data.get("id") or "studio"
                detail = f"Magicline reachable ({studio})"
            elif normalized == "smtp":
                host = self._resolve_test_value(user, normalized, config, "smtp_host")
                port = int(self._resolve_test_value(user, normalized, config, "smtp_port") or "587")
                username = self._resolve_test_value(user, normalized, config, "smtp_username")
                password = self._resolve_test_value(user, normalized, config, "smtp_password")
                logger.info("admin.smtp_test.params", host=host, port=port, user=username, pw_len=len(password) if password else 0)
                if not host or not username or not password:
                    raise HTTPException(status_code=422, detail="SMTP config incomplete")

                def _smtp_probe() -> None:
                    if port == 465:
                        logger.info("admin.smtp_test.trying_ssl", host=host, port=port)
                        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
                            smtp.login(username, password)
                            smtp.noop()
                    else:
                        logger.info("admin.smtp_test.trying_starttls", host=host, port=port)
                        with smtplib.SMTP(host, port, timeout=20) as smtp:
                            smtp.ehlo()
                            smtp.starttls()
                            smtp.ehlo()
                            smtp.login(username, password)
                            smtp.noop()

                await asyncio.to_thread(_smtp_probe)
                detail = f"SMTP login OK ({host}:{port})"
            elif normalized == "email":
                token = self._resolve_test_value(user, normalized, config, "postmark_server_token")
                if not token:
                    raise HTTPException(status_code=422, detail="Postmark server token is not configured")
                async with httpx.AsyncClient(timeout=12.0) as client:
                    response = await client.get(
                        "https://api.postmarkapp.com/server",
                        headers={"X-Postmark-Server-Token": token, "Accept": "application/json"},
                    )
                if response.status_code in {401, 403}:
                    raise HTTPException(status_code=502, detail="Postmark Server Token ungültig")
                if response.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"Postmark API nicht erreichbar ({response.status_code})")
                data = response.json() if response.content else {}
                detail = f"Postmark reachable (server={data.get('Name', 'unknown')})"
            else:
                sid = self._resolve_test_value(user, normalized, config, "twilio_account_sid")
                token = self._resolve_test_value(user, normalized, config, "twilio_auth_token")
                if not sid or not token:
                    raise HTTPException(status_code=422, detail="Twilio account_sid/auth_token must be configured")
                async with httpx.AsyncClient(timeout=12.0, auth=(sid, token)) as client:
                    response = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
                if response.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"Twilio test failed ({response.status_code})")
                data = response.json() if response.content else {}
                detail = f"Twilio account reachable (status={data.get('status', 'unknown')})"

            latency_ms = int((time.perf_counter() - started) * 1000)
            self._store_integration_test_status(normalized, "ok", detail, tenant_id=user.tenant_id)
            return {
                "status": "ok",
                "provider": normalized,
                "latency_ms": latency_ms,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "detail": detail,
            }
        except HTTPException as exc:
            self._store_integration_test_status(normalized, "error", str(exc.detail), tenant_id=user.tenant_id)
            raise
        except Exception as exc:
            detail = f"{exc.__class__.__name__}: {exc}"
            self._store_integration_test_status(normalized, "error", detail, tenant_id=user.tenant_id)
            raise HTTPException(status_code=502, detail=f"{normalized} test failed: {detail}")

    async def integrations_health(self, user: AuthContext) -> dict[str, Any]:
        tenant_id = user.tenant_id
        result: dict[str, Any] = {}

        magicline_url = get_setting_with_env_fallback("magicline_base_url", "magicline_base_url", "", tenant_id)
        magicline_key = get_setting_with_env_fallback("magicline_api_key", "magicline_api_key", "", tenant_id)
        magicline_studio_id = get_setting_with_env_fallback("magicline_studio_id", "magicline_studio_id", "", tenant_id)
        if magicline_url and magicline_key:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"{magicline_url.rstrip('/')}/v1/customers?page=0&size=1",
                        headers={"X-API-KEY": magicline_key},
                    )
                result["magicline"] = {
                    "configured": True,
                    "studio_id": magicline_studio_id or "(not set)",
                    "reachable": response.status_code < 400,
                    "http_status": response.status_code,
                }
            except Exception as exc:
                result["magicline"] = {"configured": True, "reachable": False, "error": str(exc)}
        else:
            result["magicline"] = {"configured": False}

        whatsapp_phone_id = get_setting_with_env_fallback("wa_phone_number_id", "meta_phone_number_id", "", tenant_id)
        whatsapp_token = get_setting_with_env_fallback("wa_access_token", "meta_access_token", "", tenant_id)
        result["whatsapp"] = {
            "configured": bool(whatsapp_phone_id and whatsapp_token),
            "phone_number_id": whatsapp_phone_id or "(not set)",
            "webhook_url": f"/webhook/whatsapp/{get_setting_with_env_fallback('tenant_slug', None, '', tenant_id) or 'your-slug'}",
        }

        telegram_token = get_setting_with_env_fallback("telegram_bot_token", "telegram_bot_token", "", tenant_id)
        telegram_chat = get_setting_with_env_fallback("telegram_admin_chat_id", "telegram_admin_chat_id", "", tenant_id)
        result["telegram"] = {
            "configured": bool(telegram_token),
            "admin_chat_configured": bool(telegram_chat),
            "webhook_url": f"/webhook/telegram/{get_setting_with_env_fallback('tenant_slug', None, '', tenant_id) or 'your-slug'}",
        }

        smtp_host = get_setting_with_env_fallback("smtp_host", "smtp_host", "", tenant_id)
        smtp_user = get_setting_with_env_fallback("smtp_username", "smtp_username", "", tenant_id)
        if smtp_host and smtp_user:
            try:
                smtp_port = int(get_setting_with_env_fallback("smtp_port", "smtp_port", "587", tenant_id) or 587)
                smtp_pass = get_setting_with_env_fallback("smtp_password", "smtp_password", "", tenant_id)
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=5)
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.quit()
                result["smtp"] = {"configured": True, "reachable": True}
            except Exception as exc:
                result["smtp"] = {"configured": True, "reachable": False, "error": str(exc)}
        else:
            result["smtp"] = {"configured": False}

        return result

    def get_connector_catalog(self, user: AuthContext) -> list[dict[str, Any]]:
        catalog: list[dict[str, Any]] = []
        for meta in list_connectors():
            connector_id = meta["id"]
            enabled_key = self._get_config_key(user.tenant_id, connector_id, "enabled")
            is_enabled = (persistence.get_setting(enabled_key, "", tenant_id=user.tenant_id) or "").lower() == "true"
            status = "connected" if is_enabled else "disconnected"

            if connector_id == "whatsapp":
                wa_status = persistence.get_setting(f"wa_session_status_{user.tenant_slug}", tenant_id=user.tenant_id)
                if wa_status == "WORKING":
                    status = "connected"

            if connector_id == "telegram":
                token_key = self._get_config_key(user.tenant_id, "telegram", "bot_token")
                token = persistence.get_setting(token_key, "", tenant_id=user.tenant_id)
                if token and token.strip():
                    status = "connected"

            catalog.append({
                **meta,
                "status": status,
                "setup_progress": 100 if status == "connected" else 0,
            })
        return catalog

    def get_connector_config(self, user: AuthContext, connector_id: str) -> dict[str, Any]:
        meta = get_connector_meta(connector_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Connector not found")

        config: dict[str, Any] = {}
        for field in meta.get("fields", []):
            key = field["key"]
            db_key = self._get_config_key(user.tenant_id, connector_id, key)
            value = persistence.get_setting(db_key, "", tenant_id=user.tenant_id)
            if field.get("type") == "password" and value:
                value = REDACTED_SECRET_VALUE
            config[key] = value

        enabled_key = self._get_config_key(user.tenant_id, connector_id, "enabled")
        config["enabled"] = (persistence.get_setting(enabled_key, "false", tenant_id=user.tenant_id) or "").lower() == "true"
        return config

    def update_connector_config(self, user: AuthContext, connector_id: str, config: dict[str, Any]) -> dict[str, str]:
        meta = get_connector_meta(connector_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Connector not found")

        for field in meta.get("fields", []):
            key = field["key"]
            new_value = config.get(key)
            if new_value is None or new_value == REDACTED_SECRET_VALUE:
                continue
            persistence.upsert_setting(self._get_config_key(user.tenant_id, connector_id, key), str(new_value), tenant_id=user.tenant_id)

        if connector_id == "whatsapp":
            verify_token_key = self._get_config_key(user.tenant_id, "whatsapp", "verify_token")
            if not persistence.get_setting(verify_token_key, tenant_id=user.tenant_id):
                import secrets as _secrets
                persistence.upsert_setting(verify_token_key, _secrets.token_urlsafe(32), tenant_id=user.tenant_id)

        if "enabled" in config:
            enabled_key = self._get_config_key(user.tenant_id, connector_id, "enabled")
            persistence.upsert_setting(enabled_key, str(config["enabled"]).lower(), tenant_id=user.tenant_id)

        return {"status": "updated"}

    def reset_connector_config(self, user: AuthContext, connector_id: str) -> dict[str, str]:
        meta = get_connector_meta(connector_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Connector not found")

        for field in meta.get("fields", []):
            persistence.upsert_setting(self._get_config_key(user.tenant_id, connector_id, field["key"]), "", tenant_id=user.tenant_id)

        enabled_key = self._get_config_key(user.tenant_id, connector_id, "enabled")
        persistence.upsert_setting(enabled_key, "false", tenant_id=user.tenant_id)

        if connector_id == "whatsapp":
            slug = persistence.get_tenant_slug(user.tenant_id)
            if slug:
                persistence.delete_setting(f"wa_session_status_{slug}", tenant_id=user.tenant_id)

        return {"status": "reset"}

    def get_connector_docs(self, connector_id: str) -> dict[str, Any]:
        meta = get_connector_meta(connector_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Connector not found")

        return {
            "connector_id": connector_id,
            "name": meta.get("name", connector_id),
            "category": meta.get("category", ""),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", ""),
            "docs": CONNECTOR_DOCS.get(connector_id, {}),
        }

    def get_all_connector_docs(self) -> list[dict[str, Any]]:
        return [
            {
                "id": connector_id,
                "name": meta.get("name", connector_id),
                "category": meta.get("category", ""),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", ""),
                "has_docs": bool(CONNECTOR_DOCS.get(connector_id, {})),
                "overview": CONNECTOR_DOCS.get(connector_id, {}).get("overview", ""),
                "difficulty": CONNECTOR_DOCS.get(connector_id, {}).get("difficulty", "medium"),
                "estimated_time": CONNECTOR_DOCS.get(connector_id, {}).get("estimated_time", "5 min"),
            }
            for connector_id, meta in CONNECTOR_REGISTRY.items()
        ]

    def get_connector_webhook_info(self, user: AuthContext, connector_id: str) -> dict[str, Any]:
        tenant_slug = persistence.get_tenant_slug(user.tenant_id) or "unknown"
        base_url = "https://www.ariia.ai"
        result: dict[str, Any] = {"connector_id": connector_id, "tenant_slug": tenant_slug}

        if connector_id == "whatsapp":
            result["webhook_url"] = f"{base_url}/webhook/whatsapp/{tenant_slug}"
            verify_token_key = self._get_config_key(user.tenant_id, "whatsapp", "verify_token")
            verify_token = persistence.get_setting(verify_token_key, tenant_id=user.tenant_id)
            if not verify_token:
                import secrets as _secrets
                verify_token = _secrets.token_urlsafe(32)
                persistence.upsert_setting(verify_token_key, verify_token, tenant_id=user.tenant_id)
            result["verify_token"] = verify_token
            result["instructions"] = (
                "Trage diese Webhook-URL und den Verify Token in deiner Meta App unter "
                "WhatsApp > Configuration > Webhook ein. "
                "Abonniere die Felder: messages, messaging_postbacks."
            )
        elif connector_id == "telegram":
            result["webhook_url"] = f"{base_url}/webhook/telegram/{tenant_slug}"
            result["instructions"] = (
                "Der Telegram-Webhook wird automatisch konfiguriert. "
                "Alternativ kannst du diese URL manuell bei @BotFather setzen."
            )
        elif connector_id == "email":
            result["webhook_url"] = f"{base_url}/webhook/email/{tenant_slug}"
            result["instructions"] = "Konfiguriere dein E-Mail-System, um eingehende Nachrichten an diese URL weiterzuleiten."
        elif connector_id == "sms":
            result["webhook_url"] = f"{base_url}/webhook/sms/{tenant_slug}"
            result["instructions"] = "Trage diese URL als Messaging Webhook in deinem Twilio Dashboard ein."
        else:
            result["webhook_url"] = None
            result["instructions"] = "Dieser Connector benötigt keinen Webhook."
        return result

    def system_list_connectors(self, user: AuthContext) -> list[dict[str, Any]]:
        return [
            {
                "id": connector_id,
                **meta,
                "field_count": len(meta.get("fields", [])),
                "has_docs": connector_id in CONNECTOR_DOCS,
            }
            for connector_id, meta in CONNECTOR_REGISTRY.items()
        ]

    def system_create_connector(self, user: AuthContext, body: Any) -> dict[str, str]:
        if body.id in CONNECTOR_REGISTRY:
            raise HTTPException(status_code=409, detail=f"Connector '{body.id}' already exists")
        CONNECTOR_REGISTRY[body.id] = {
            "name": body.name,
            "category": body.category,
            "description": body.description,
            "icon": body.icon,
            "fields": body.fields,
            "setup_doc": body.setup_doc,
        }
        logger.info("connector_created", connector_id=body.id, admin=user.email)
        return {"status": "created", "connector_id": body.id}

    def system_update_connector(self, user: AuthContext, connector_id: str, body: Any) -> dict[str, str]:
        if connector_id not in CONNECTOR_REGISTRY:
            raise HTTPException(status_code=404, detail="Connector not found")
        existing = CONNECTOR_REGISTRY[connector_id]
        if body.name is not None:
            existing["name"] = body.name
        if body.category is not None:
            existing["category"] = body.category
        if body.description is not None:
            existing["description"] = body.description
        if body.icon is not None:
            existing["icon"] = body.icon
        if body.fields is not None:
            existing["fields"] = body.fields
        if body.setup_doc is not None:
            existing["setup_doc"] = body.setup_doc
        logger.info("connector_updated", connector_id=connector_id, admin=user.email)
        return {"status": "updated"}

    def system_delete_connector(self, user: AuthContext, connector_id: str) -> dict[str, str]:
        if connector_id not in CONNECTOR_REGISTRY:
            raise HTTPException(status_code=404, detail="Connector not found")
        del CONNECTOR_REGISTRY[connector_id]
        if connector_id in CONNECTOR_DOCS:
            del CONNECTOR_DOCS[connector_id]
        logger.info("connector_deleted", connector_id=connector_id, admin=user.email)
        return {"status": "deleted"}

    def system_usage_overview(self, user: AuthContext) -> dict[str, Any]:
        db = open_session()
        try:
            stats = {
                "total_connectors": len(CONNECTOR_REGISTRY),
                "total_tenants": len(connector_hub_repository.list_tenants(db)),
                "categories": {},
                "connector_usage": connector_hub_repository.count_enabled_connectors_by_type(db),
            }
            for connector_id, meta in CONNECTOR_REGISTRY.items():
                category = meta.get("category", "other")
                stats["categories"][category] = stats["categories"].get(category, 0) + 1
            return stats
        finally:
            db.close()


service = AdminIntegrationsService()
