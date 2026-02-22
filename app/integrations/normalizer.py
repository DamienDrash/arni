"""ARIIA v1.4 – Message Normalizer.

@BACKEND: Sprint 3, Task 3.5
Multi-platform inbound normalization → unified InboundMessage schema.
"""

from typing import Any
from uuid import uuid4

import structlog

from app.gateway.schemas import InboundMessage, Platform

logger = structlog.get_logger()


class MessageNormalizer:
    """Normalizes messages from different platforms into InboundMessage.

    Ensures all channels produce identical schema for the Swarm Router.
    """

    def normalize_whatsapp(self, raw_payload: dict[str, Any]) -> list[InboundMessage]:
        """Normalize WhatsApp webhook payload to InboundMessages.

        Args:
            raw_payload: Raw Meta Cloud API webhook payload.

        Returns:
            List of normalized InboundMessages.
        """
        messages: list[InboundMessage] = []

        for entry in raw_payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    content = ""
                    content_type = msg.get("type", "text")
                    media_url = None

                    if content_type == "text":
                        content = msg.get("text", {}).get("body", "")
                    elif content_type == "image":
                        content = msg.get("image", {}).get("caption", "")
                        media_url = msg.get("image", {}).get("id", "")
                    elif content_type == "audio":
                        content = "[Sprachnachricht]"
                        media_url = msg.get("audio", {}).get("id", "")
                    elif content_type == "location":
                        loc = msg.get("location", {})
                        content = f"📍 {loc.get('latitude', 0)},{loc.get('longitude', 0)}"
                    elif content_type == "interactive":
                        interactive = msg.get("interactive", {})
                        reply = interactive.get("button_reply") or interactive.get("list_reply", {})
                        content = reply.get("title", reply.get("id", ""))
                    else:
                        content = f"[{content_type}]"

                    inbound = InboundMessage(
                        message_id=msg.get("id", str(uuid4())),
                        platform=Platform.WHATSAPP,
                        user_id=msg.get("from", "unknown"),
                        content=content,
                        content_type=content_type,
                        media_url=media_url,
                        metadata={
                            "raw_type": content_type,
                            "contacts": value.get("contacts", []),
                        },
                    )
                    messages.append(inbound)
                    logger.info(
                        "normalizer.whatsapp",
                        message_id=inbound.message_id,
                        content_type=content_type,
                    )

        return messages

    def normalize_telegram(self, update: dict[str, Any]) -> InboundMessage | None:
        """Normalize Telegram update to InboundMessage.

        Args:
            update: Telegram Bot API update object.

        Returns:
            Normalized InboundMessage or None if not a message update.
        """
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        chat = message.get("chat", {})
        user = message.get("from", {})

        content = ""
        content_type = "text"
        media_url = None

        if "text" in message:
            content = message["text"]
        elif "photo" in message:
            content = message.get("caption", "")
            content_type = "image"
            # Get largest photo (last in array)
            photos = message["photo"]
            if photos:
                media_url = photos[-1].get("file_id", "")
        elif "voice" in message:
            content = "[Sprachnachricht]"
            content_type = "voice"
            media_url = message["voice"].get("file_id", "")
        elif "audio" in message:
            content = message.get("caption", "[Audio]")
            content_type = "audio"
            media_url = message["audio"].get("file_id", "")
        elif "location" in message:
            loc = message["location"]
            content = f"📍 {loc.get('latitude', 0)},{loc.get('longitude', 0)}"
            content_type = "location"
        elif "sticker" in message:
            content = message["sticker"].get("emoji", "🎭")
            content_type = "sticker"

        inbound = InboundMessage(
            message_id=str(message.get("message_id", uuid4())),
            platform=Platform.TELEGRAM,
            user_id=str(user.get("id", chat.get("id", "unknown"))),
            content=content,
            content_type=content_type,
            media_url=media_url,
            metadata={
                "chat_id": str(chat.get("id", "")),
                "chat_type": chat.get("type", "private"),
                "username": user.get("username", ""),
                "first_name": user.get("first_name", ""),
            },
        )
        logger.info(
            "normalizer.telegram",
            message_id=inbound.message_id,
            content_type=content_type,
            chat_type=chat.get("type", "private"),
        )
        return inbound
