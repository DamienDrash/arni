"""ARIIA v2.0 – Telegram Integration Adapter.

@ARCH: Sprint 1 (Integration Roadmap), Task S1.2
Concrete adapter for Telegram Bot API. Wraps the existing TelegramBot
into the BaseAdapter interface, providing standardized capability routing
for the DynamicToolResolver.

Supported Capabilities:
  - messaging.send.text             → Send a text message
  - messaging.send.voice            → Send a voice note
  - messaging.send.alert            → Send an admin alert
  - messaging.send.emergency        → Send an emergency alert (Medic Rule)
  - messaging.send.contact_request  → Request contact sharing
  - messaging.receive.normalize     → Normalize a Telegram update
  - messaging.receive.get_file      → Get file info from Telegram
  - messaging.receive.download_file → Download a file from Telegram
  - admin.command.handle            → Handle a bot command
  - admin.command.parse             → Parse a command string
  - admin.webhook.set               → Set webhook URL
  - admin.webhook.delete            → Delete webhook
  - admin.polling.get_updates       → Long polling for updates
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class TelegramAdapter(BaseAdapter):
    """Adapter for Telegram Bot API.

    Routes capability calls to the existing TelegramBot class,
    wrapping results in the standardized AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "telegram"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "messaging.send.text",
            "messaging.send.voice",
            "messaging.send.alert",
            "messaging.send.emergency",
            "messaging.send.contact_request",
            "messaging.receive.normalize",
            "messaging.receive.get_file",
            "messaging.receive.download_file",
            "admin.command.handle",
            "admin.command.parse",
            "admin.webhook.set",
            "admin.webhook.delete",
            "admin.polling.get_updates",
        ]

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability to the appropriate Telegram handler."""
        handlers = {
            "messaging.send.text": self._send_text,
            "messaging.send.voice": self._send_voice,
            "messaging.send.alert": self._send_alert,
            "messaging.send.emergency": self._send_emergency,
            "messaging.send.contact_request": self._send_contact_request,
            "messaging.receive.normalize": self._normalize_update,
            "messaging.receive.get_file": self._get_file,
            "messaging.receive.download_file": self._download_file,
            "admin.command.handle": self._handle_command,
            "admin.command.parse": self._parse_command,
            "admin.webhook.set": self._set_webhook,
            "admin.webhook.delete": self._delete_webhook,
            "admin.polling.get_updates": self._get_updates,
        }

        handler = handlers.get(capability_id)
        if not handler:
            return AdapterResult(
                success=False,
                error=f"No handler for capability '{capability_id}'",
                error_code="NO_HANDLER",
            )

        return await handler(tenant_id, **kwargs)

    # ─── Bot Resolution ──────────────────────────────────────────────────

    def _get_bot(self, tenant_id: int, **kwargs: Any):
        """Resolve a TelegramBot for the given tenant."""
        from app.integrations.telegram import TelegramBot

        # Direct credential injection
        if kwargs.get("bot_token"):
            return TelegramBot(
                bot_token=kwargs["bot_token"],
                admin_chat_id=kwargs.get("admin_chat_id", ""),
            )

        # Tenant-based credential resolution
        try:
            from app.core.integration_models import get_integration_config
            config = get_integration_config(tenant_id, "telegram")
            if config:
                return TelegramBot(
                    bot_token=config.get("bot_token", ""),
                    admin_chat_id=config.get("admin_chat_id", ""),
                )
        except Exception as e:
            logger.warning("telegram_adapter.config_resolution_failed", tenant_id=tenant_id, error=str(e))

        return None

    # ─── Messaging Capabilities ──────────────────────────────────────────

    async def _send_text(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a text message to a Telegram chat."""
        chat_id = kwargs.get("chat_id", "") or kwargs.get("to", "")
        text = kwargs.get("text", "") or kwargs.get("body", "") or kwargs.get("content", "")
        parse_mode = kwargs.get("parse_mode")
        reply_markup = kwargs.get("reply_markup")

        if not chat_id:
            return AdapterResult(
                success=False,
                error="'chat_id' ist erforderlich.",
                error_code="MISSING_CHAT_ID",
            )
        if not text:
            return AdapterResult(
                success=False,
                error="Nachrichtentext ('text') ist erforderlich.",
                error_code="MISSING_TEXT",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
            message_id = ""
            if isinstance(result, dict) and result.get("result"):
                message_id = str(result["result"].get("message_id", ""))
            return AdapterResult(
                success=True,
                data={"message_id": message_id, "chat_id": chat_id, "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SEND_FAILED")

    async def _send_voice(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a voice note to a Telegram chat."""
        chat_id = kwargs.get("chat_id", "") or kwargs.get("to", "")
        voice_path = kwargs.get("voice_path", "")
        caption = kwargs.get("caption", "")

        if not chat_id or not voice_path:
            return AdapterResult(
                success=False,
                error="'chat_id' und 'voice_path' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.send_voice(chat_id, voice_path, caption)
            return AdapterResult(
                success=True,
                data={"chat_id": chat_id, "type": "voice", "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="VOICE_SEND_FAILED")

    async def _send_alert(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send an alert to the admin chat."""
        message = kwargs.get("message", "")
        severity = kwargs.get("severity", "info")
        chat_id = kwargs.get("chat_id")

        if not message:
            return AdapterResult(
                success=False,
                error="'message' ist erforderlich.",
                error_code="MISSING_MESSAGE",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.send_alert(message, severity=severity, chat_id=chat_id)
            return AdapterResult(
                success=True,
                data={"severity": severity, "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="ALERT_SEND_FAILED")

    async def _send_emergency(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send an emergency alert (Medic Rule – AGENTS.md §2)."""
        user_id = kwargs.get("user_id", "")
        message_content = kwargs.get("message_content", "")

        if not user_id:
            return AdapterResult(
                success=False,
                error="'user_id' ist erforderlich.",
                error_code="MISSING_USER_ID",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.send_emergency_alert(user_id, message_content)
            return AdapterResult(
                success=True,
                data={"user_id_masked": f"{user_id[:5]}****" if len(user_id) > 5 else "****", "status": "emergency_sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="EMERGENCY_SEND_FAILED")

    async def _send_contact_request(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a message with a contact-sharing button."""
        chat_id = kwargs.get("chat_id", "") or kwargs.get("to", "")
        text = kwargs.get("text", "Bitte teile deine Kontaktdaten:")

        if not chat_id:
            return AdapterResult(
                success=False,
                error="'chat_id' ist erforderlich.",
                error_code="MISSING_CHAT_ID",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.send_contact_request(chat_id, text)
            return AdapterResult(
                success=True,
                data={"chat_id": chat_id, "type": "contact_request", "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CONTACT_REQUEST_FAILED")

    # ─── Receive / Normalize Capabilities ────────────────────────────────

    async def _normalize_update(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Normalize a raw Telegram update into structured data."""
        update = kwargs.get("update", {})
        if not update:
            return AdapterResult(
                success=False,
                error="'update' Payload ist erforderlich.",
                error_code="MISSING_UPDATE",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            # Normalization doesn't strictly need a bot token, but we create one for consistency
            from app.integrations.telegram import TelegramBot
            bot = TelegramBot(bot_token="dummy", admin_chat_id="")

        normalized = bot.normalize_update(update)
        if normalized:
            return AdapterResult(success=True, data=normalized)
        return AdapterResult(
            success=False,
            error="Update konnte nicht normalisiert werden (kein Message-Objekt).",
            error_code="NORMALIZATION_FAILED",
        )

    async def _get_file(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get file information from Telegram."""
        file_id = kwargs.get("file_id", "")
        if not file_id:
            return AdapterResult(
                success=False,
                error="'file_id' ist erforderlich.",
                error_code="MISSING_FILE_ID",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.get_file(file_id)
            return AdapterResult(success=True, data=result)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="GET_FILE_FAILED")

    async def _download_file(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Download file content from Telegram."""
        file_path = kwargs.get("file_path", "")
        if not file_path:
            return AdapterResult(
                success=False,
                error="'file_path' ist erforderlich.",
                error_code="MISSING_FILE_PATH",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            content = await bot.download_file(file_path)
            return AdapterResult(
                success=True,
                data={"file_path": file_path, "size_bytes": len(content)},
                metadata={"file_content": content},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="DOWNLOAD_FAILED")

    # ─── Admin / Command Capabilities ────────────────────────────────────

    async def _handle_command(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Handle an admin bot command."""
        command = kwargs.get("command", "")
        args = kwargs.get("args", "")
        chat_id = kwargs.get("chat_id", "")
        health_data = kwargs.get("health_data")

        if not command or not chat_id:
            return AdapterResult(
                success=False,
                error="'command' und 'chat_id' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            response = await bot.handle_command(command, args, chat_id, health_data)
            return AdapterResult(
                success=True,
                data={"command": command, "response": response, "chat_id": chat_id},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="COMMAND_FAILED")

    async def _parse_command(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Parse a Telegram command string."""
        text = kwargs.get("text", "")

        # Parse doesn't need a real bot, but we use the class method
        from app.integrations.telegram import TelegramBot
        bot = TelegramBot(bot_token="dummy")
        command, args = bot.parse_command(text)

        return AdapterResult(
            success=True,
            data={"command": command, "args": args, "is_command": bool(command)},
        )

    # ─── Webhook / Polling Capabilities ──────────────────────────────────

    async def _set_webhook(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Register a webhook URL with Telegram."""
        url = kwargs.get("url", "")
        if not url:
            return AdapterResult(
                success=False,
                error="'url' ist erforderlich.",
                error_code="MISSING_URL",
            )

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.set_webhook(url)
            return AdapterResult(
                success=True,
                data={"url": url, "status": "webhook_set"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="WEBHOOK_SET_FAILED")

    async def _delete_webhook(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Delete the webhook integration."""
        drop_pending = kwargs.get("drop_pending_updates", False)

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await bot.delete_webhook(drop_pending_updates=drop_pending)
            return AdapterResult(
                success=True,
                data={"status": "webhook_deleted", "drop_pending": drop_pending},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="WEBHOOK_DELETE_FAILED")

    async def _get_updates(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Long polling for updates (alternative to webhook)."""
        offset = kwargs.get("offset")
        timeout = kwargs.get("timeout", 30)

        bot = self._get_bot(tenant_id, **kwargs)
        if not bot:
            return AdapterResult(
                success=False,
                error="Telegram ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            updates = await bot.get_updates(offset=offset, timeout=timeout)
            return AdapterResult(
                success=True,
                data={"updates": updates, "count": len(updates)},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="POLLING_FAILED")

    # ─── Health Check ────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Telegram is configured for this tenant."""
        bot = self._get_bot(tenant_id)
        if bot:
            return AdapterResult(
                success=True,
                data={"status": "ok", "adapter": "telegram"},
            )
        return AdapterResult(
            success=False,
            error="Telegram bot not configured",
            error_code="NOT_CONFIGURED",
        )
