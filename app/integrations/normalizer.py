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

    def normalize_instagram(self, raw_payload: dict[str, Any]) -> list[InboundMessage]:
        """Normalize Instagram Messaging webhook payload.

        The Instagram Messaging API uses a similar structure to WhatsApp
        via the Meta Graph API.
        """
        messages: list[InboundMessage] = []

        for entry in raw_payload.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender_id = messaging.get("sender", {}).get("id", "unknown")
                msg = messaging.get("message", {})
                if not msg:
                    continue

                content = msg.get("text", "")
                content_type = "text"
                media_url = None

                attachments = msg.get("attachments", [])
                if attachments:
                    att = attachments[0]
                    att_type = att.get("type", "")
                    if att_type == "image":
                        content_type = "image"
                        media_url = att.get("payload", {}).get("url", "")
                        content = content or "[Bild]"
                    elif att_type == "audio":
                        content_type = "audio"
                        media_url = att.get("payload", {}).get("url", "")
                        content = "[Sprachnachricht]"
                    elif att_type == "video":
                        content_type = "video"
                        media_url = att.get("payload", {}).get("url", "")
                        content = "[Video]"
                    elif att_type == "story_mention":
                        content = "[Story-Erwähnung]"

                inbound = InboundMessage(
                    message_id=msg.get("mid", str(uuid4())),
                    platform=Platform.INSTAGRAM,
                    user_id=sender_id,
                    content=content,
                    content_type=content_type,
                    media_url=media_url,
                    metadata={
                        "recipient_id": messaging.get("recipient", {}).get("id", ""),
                        "timestamp": messaging.get("timestamp", ""),
                    },
                )
                messages.append(inbound)
                logger.info(
                    "normalizer.instagram",
                    message_id=inbound.message_id,
                    content_type=content_type,
                )

        return messages

    def normalize_facebook(self, raw_payload: dict[str, Any]) -> list[InboundMessage]:
        """Normalize Facebook Messenger webhook payload.

        Uses the Meta Send/Receive API format.
        """
        messages: list[InboundMessage] = []

        for entry in raw_payload.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender_id = messaging.get("sender", {}).get("id", "unknown")
                msg = messaging.get("message", {})

                # Handle postbacks (button clicks)
                postback = messaging.get("postback")
                if postback and not msg:
                    inbound = InboundMessage(
                        message_id=str(uuid4()),
                        platform=Platform.FACEBOOK,
                        user_id=sender_id,
                        content=postback.get("title", postback.get("payload", "")),
                        content_type="postback",
                        metadata={
                            "postback_payload": postback.get("payload", ""),
                            "recipient_id": messaging.get("recipient", {}).get("id", ""),
                        },
                    )
                    messages.append(inbound)
                    continue

                if not msg:
                    continue

                content = msg.get("text", "")
                content_type = "text"
                media_url = None

                attachments = msg.get("attachments", [])
                if attachments:
                    att = attachments[0]
                    att_type = att.get("type", "")
                    if att_type == "image":
                        content_type = "image"
                        media_url = att.get("payload", {}).get("url", "")
                        content = content or "[Bild]"
                    elif att_type == "audio":
                        content_type = "audio"
                        media_url = att.get("payload", {}).get("url", "")
                        content = "[Sprachnachricht]"
                    elif att_type == "video":
                        content_type = "video"
                        media_url = att.get("payload", {}).get("url", "")
                        content = "[Video]"
                    elif att_type == "location":
                        coords = att.get("payload", {}).get("coordinates", {})
                        content = f"📍 {coords.get('lat', 0)},{coords.get('long', 0)}"
                        content_type = "location"

                inbound = InboundMessage(
                    message_id=msg.get("mid", str(uuid4())),
                    platform=Platform.FACEBOOK,
                    user_id=sender_id,
                    content=content,
                    content_type=content_type,
                    media_url=media_url,
                    metadata={
                        "recipient_id": messaging.get("recipient", {}).get("id", ""),
                        "timestamp": messaging.get("timestamp", ""),
                    },
                )
                messages.append(inbound)
                logger.info(
                    "normalizer.facebook",
                    message_id=inbound.message_id,
                    content_type=content_type,
                )

        return messages

    def normalize_google_business(self, raw_payload: dict[str, Any]) -> InboundMessage | None:
        """Normalize Google Business Messages webhook payload."""
        message = raw_payload.get("message", {})
        if not message:
            return None

        conversation_id = raw_payload.get("conversationId", "")
        sender = message.get("sender", "")
        content = message.get("text", "")
        content_type = "text"
        media_url = None

        # Handle rich content
        if "image" in message:
            content_type = "image"
            media_url = message["image"].get("contentInfo", {}).get("fileUrl", "")
            content = content or "[Bild]"

        inbound = InboundMessage(
            message_id=message.get("messageId", str(uuid4())),
            platform=Platform.GOOGLE_BUSINESS,
            user_id=sender or conversation_id,
            content=content,
            content_type=content_type,
            media_url=media_url,
            metadata={
                "conversation_id": conversation_id,
                "agent_id": raw_payload.get("agent", ""),
            },
        )
        logger.info(
            "normalizer.google_business",
            message_id=inbound.message_id,
            content_type=content_type,
        )
        return inbound

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
