"""ARNI v1.4 – Outbound Message Dispatcher.

@BACKEND: Sprint 3, Task 3.6
Routes OutboundMessages to the correct platform channel.
"""

from typing import Any

import structlog

from app.gateway.schemas import OutboundMessage, Platform

logger = structlog.get_logger()


class OutboundDispatcher:
    """Routes outbound messages to platform-specific delivery channels.

    Flow: OutboundMessage → check platform → send via correct client
    """

    def __init__(
        self,
        whatsapp_client: Any | None = None,
        telegram_bot: Any | None = None,
        websocket_broadcast: Any | None = None,
    ) -> None:
        self._whatsapp = whatsapp_client
        self._telegram = telegram_bot
        self._ws_broadcast = websocket_broadcast

    async def dispatch(self, message: OutboundMessage) -> bool:
        """Dispatch an outbound message to the correct platform.

        Args:
            message: OutboundMessage with target platform.

        Returns:
            True if message was sent successfully.
        """
        try:
            if message.platform == Platform.WHATSAPP:
                return await self._dispatch_whatsapp(message)
            elif message.platform == Platform.TELEGRAM:
                return await self._dispatch_telegram(message)
            elif message.platform == Platform.DASHBOARD:
                return await self._dispatch_dashboard(message)
            else:
                logger.warning(
                    "dispatcher.unknown_platform",
                    platform=message.platform,
                    message_id=message.message_id,
                )
                return False
        except Exception as e:
            logger.error(
                "dispatcher.send_failed",
                platform=message.platform,
                message_id=message.message_id,
                error=str(e),
            )
            return False

    async def _dispatch_whatsapp(self, message: OutboundMessage) -> bool:
        """Send message via WhatsApp."""
        if not self._whatsapp:
            logger.warning("dispatcher.whatsapp_not_configured")
            return False
        await self._whatsapp.send_text(message.user_id, message.content)
        logger.info(
            "dispatcher.whatsapp_sent",
            message_id=message.message_id,
        )
        return True

    async def _dispatch_telegram(self, message: OutboundMessage) -> bool:
        """Send message via Telegram."""
        if not self._telegram:
            logger.warning("dispatcher.telegram_not_configured")
            return False
        chat_id = message.user_id
        await self._telegram.send_message(chat_id, message.content, parse_mode="")
        logger.info(
            "dispatcher.telegram_sent",
            message_id=message.message_id,
        )
        return True

    async def _dispatch_dashboard(self, message: OutboundMessage) -> bool:
        """Send message via WebSocket to admin dashboard."""
        if not self._ws_broadcast:
            logger.warning("dispatcher.dashboard_not_configured")
            return False
        await self._ws_broadcast({
            "type": "outbound",
            "message_id": message.message_id,
            "content": message.content,
            "user_id": message.user_id,
        })
        logger.info(
            "dispatcher.dashboard_sent",
            message_id=message.message_id,
        )
        return True
