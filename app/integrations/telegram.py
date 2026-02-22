"""ARIIA v1.4 – Telegram Bot Integration.

@BACKEND: Sprint 3, Task 3.3 + 3.4
Admin Bot for alerts, Ghost Mode control, and system monitoring.
"""

from typing import Any

import os
import httpx
import structlog

logger = structlog.get_logger()

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramBot:
    """Telegram Bot API client for admin operations.

    Features:
    - System health monitoring (/status)
    - Ghost Mode toggle (/ghost)
    - Emergency alerts from Medic agent
    - Staff notifications
    """

    def __init__(self, bot_token: str, admin_chat_id: str = "") -> None:
        self._bot_token = bot_token
        self._admin_chat_id = admin_chat_id
        self._base_url = f"{TELEGRAM_API_BASE}/bot{bot_token}"

    async def set_webhook(self, url: str) -> dict[str, Any]:
        """Register the webhook URL with Telegram."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/setWebhook",
                json={"url": url},
            )
            response.raise_for_status()
            logger.info("telegram.webhook_set", url=url)
            return response.json()

    async def delete_webhook(self, drop_pending_updates: bool = False) -> dict[str, Any]:
        """Remove the webhook integration.
        
        Args:
            drop_pending_updates: If True, all pending updates will be discarded.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {}
            if drop_pending_updates:
                params["drop_pending_updates"] = True
            response = await client.post(
                f"{self._base_url}/deleteWebhook",
                params=params
            )
            response.raise_for_status()
            return response.json()

    def normalize_update(self, update: dict[str, Any]) -> dict[str, Any] | None:
        """Extract relevant data from a Telegram update."""
        message = update.get("message", {})
        if not message:
            return None
        
        content = ""
        content_type = "text"
        metadata = {}

        if "text" in message:
            content = message["text"]
        elif "voice" in message:
            voice = message["voice"]
            content = voice["file_id"]
            content_type = "voice"
            metadata = {
                "mime_type": voice.get("mime_type"),
                "duration": voice.get("duration"),
                "file_size": voice.get("file_size"),
            }
        elif "contact" in message:
            contact = message["contact"]
            # Format: User shared contact
            content = f"[Contact] {contact.get('phone_number')}"
            content_type = "contact"
            metadata = {
                "phone_number": contact.get("phone_number"),
                "first_name": contact.get("first_name"),
                "user_id": str(contact.get("user_id")),
            }
        else:
            return None
        
        return {
            "message_id": str(message.get("message_id")),
            "user_id": str(message.get("from", {}).get("id")),
            "chat_id": str(message.get("chat", {}).get("id")),
            "content": content,
            "content_type": content_type,
            "metadata": metadata,
            "username": message.get("from", {}).get("username"),
            "first_name": message.get("from", {}).get("first_name"),
        }

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """Get file information (path) from Telegram."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._base_url}/getFile", 
                params={"file_id": file_id}
            )
            response.raise_for_status()
            return response.json().get("result", {})

    async def download_file(self, file_path: str) -> bytes:
        """Download file content from Telegram."""
        url = f"{TELEGRAM_API_BASE}/file/bot{self._bot_token}/{file_path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def get_updates(self, offset: int | None = None, timeout: int = 30) -> list[dict[str, Any]]:
        """Long polling for updates (alternative to webhook)."""
        params = {"timeout": timeout}
        if offset:
            params["offset"] = offset
            
        async with httpx.AsyncClient(timeout=timeout + 10.0) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/getUpdates",
                    params=params, 
                )
                response.raise_for_status()
                result = response.json()
                return result.get("result", [])
            except Exception as e:
                logger.error("telegram.polling_failed", error=str(e))
                return []

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a text message to a Telegram chat.

        Args:
            chat_id: Target chat/group ID.
            text: Message text (supports HTML formatting).
            parse_mode: 'HTML' or 'Markdown'.
            reply_markup: Optional JSON object for custom reply keyboard, inline keyboard, or reply force.

        Returns:
            API response dict.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "chat_id": chat_id,
                "text": text,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            response = await client.post(
                f"{self._base_url}/sendMessage",
                json=payload,
            )
            if response.status_code >= 400:
                body_preview = response.text[:500]
                logger.error(
                    "telegram.send_message_failed",
                    chat_id=chat_id,
                    status=response.status_code,
                    body_preview=body_preview,
                )
            response.raise_for_status()
            data = response.json()
            logger.info("telegram.message_sent", chat_id=chat_id)
            return data

    async def send_voice(
        self,
        chat_id: str,
        voice_path: str,
        caption: str = "",
    ) -> dict[str, Any]:
        """Send a voice note to a Telegram chat."""
        if not os.path.exists(voice_path):
            logger.error("telegram.voice_file_missing", path=voice_path)
            return {}

        url = f"{self._base_url}/sendVoice"
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(voice_path, "rb") as f:
                files = {"voice": f}
                data = {"chat_id": chat_id, "caption": caption}
                try:
                    response = await client.post(url, data=data, files=files)
                    response.raise_for_status()
                    logger.info("telegram.voice_sent", chat_id=chat_id)
                    return response.json()
                except Exception as e:
                    logger.error("telegram.send_voice_failed", error=str(e))
                    return {}

    async def send_alert(
        self,
        message: str,
        severity: str = "info",
        chat_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an alert to the admin chat.

        Args:
            message: Alert message text.
            severity: info|warning|error|critical.
            chat_id: Override chat ID (defaults to admin_chat_id).

        Returns:
            API response dict.
        """
        target = chat_id or self._admin_chat_id
        if not target:
            logger.warning("telegram.no_admin_chat", msg="Admin chat ID not configured")
            return {"ok": False, "error": "no_admin_chat_id"}

        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }
        emoji = emoji_map.get(severity, "📢")
        formatted = f"{emoji} <b>ARIIA Alert [{severity.upper()}]</b>\n\n{message}"
        return await self.send_message(target, formatted)

    async def send_emergency_alert(
        self,
        user_id: str,
        message_content: str,
    ) -> dict[str, Any]:
        """Send an emergency alert (Medic Rule – AGENTS.md §2).

        Triggered when emergency keywords are detected.
        Alerts staff immediately via Telegram.

        Args:
            user_id: User identifier (masked for PII).
            message_content: Original message (for context).
        """
        masked_user = f"{user_id[:5]}****" if len(user_id) > 5 else "****"
        alert_text = (
            f"🚨 <b>NOTFALL-ALARM</b> 🚨\n\n"
            f"👤 User: <code>{masked_user}</code>\n"
            f"💬 Nachricht enthält Notfall-Keywords\n\n"
            f"⚡ <b>Aktion:</b> Sofort prüfen!\n"
            f"📞 112 wurde dem User empfohlen."
        )
        logger.critical(
            "telegram.emergency_alert",
            user_masked=masked_user,
        )
        return await self.send_alert(alert_text, severity="critical")

    async def send_contact_request(self, chat_id: str, text: str) -> dict[str, Any]:
        """Send a message with a button to request contact sharing."""
        keyboard = {
            "keyboard": [[{
                "text": "📱 Nummer teilen / Share Contact", 
                "request_contact": True
            }]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
            "is_persistent": False,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "reply_markup": keyboard,
                },
            )
            response.raise_for_status()
            logger.info("telegram.contact_request_sent", chat_id=chat_id)
            return response.json()

    def parse_command(self, text: str) -> tuple[str, str]:
        """Parse a Telegram command message.

        Args:
            text: Message text (e.g. '/status', '/ghost on').

        Returns:
            Tuple of (command, args).
        """
        if not text or not text.startswith("/"):
            return ("", text or "")
        parts = text.split(maxsplit=1)
        command = parts[0].lower().split("@")[0]  # Remove @botname suffix
        args = parts[1] if len(parts) > 1 else ""
        return (command, args)

    async def handle_command(
        self,
        command: str,
        args: str,
        chat_id: str,
        health_data: dict[str, Any] | None = None,
    ) -> str:
        """Handle an admin bot command.

        Args:
            command: Command name (e.g. '/status').
            args: Command arguments.
            chat_id: Source chat ID.
            health_data: Optional system health data.

        Returns:
            Response text.
        """
        handlers: dict[str, str] = {
            "/status": self._cmd_status(health_data),
            "/ghost": self._cmd_ghost(args),
            "/help": self._cmd_help(),
        }
        response = handlers.get(command, f"❓ Unbekannter Befehl: {command}\n\nTippe /help für Hilfe.")
        await self.send_message(chat_id, response)
        return response

    def _cmd_status(self, health_data: dict[str, Any] | None = None) -> str:
        """Generate status response."""
        if health_data:
            status = health_data.get("status", "unknown")
            redis = health_data.get("redis", "unknown")
            version = health_data.get("version", "?")
            return (
                f"📊 <b>ARIIA System Status</b>\n\n"
                f"🟢 Status: <code>{status}</code>\n"
                f"🔗 Redis: <code>{redis}</code>\n"
                f"📦 Version: <code>{version}</code>"
            )
        return "📊 <b>ARIIA System Status</b>\n\n🟢 Gateway: <code>online</code>"

    def _cmd_ghost(self, args: str) -> str:
        """Generate ghost mode response."""
        if args.lower() in ("on", "an"):
            return "👻 <b>Ghost Mode: AKTIV</b>\n\nDu siehst jetzt alle Live-Konversationen."
        elif args.lower() in ("off", "aus"):
            return "👻 <b>Ghost Mode: DEAKTIVIERT</b>"
        return "👻 <b>Ghost Mode</b>\n\nNutze: <code>/ghost on</code> oder <code>/ghost off</code>"

    def _cmd_help(self) -> str:
        """Generate help response."""
        return (
            "🤖 <b>ARIIA Admin Bot</b>\n\n"
            "📊 /status – System-Status\n"
            "👻 /ghost on|off – Ghost Mode\n"
            "❓ /help – Diese Hilfe"
        )
