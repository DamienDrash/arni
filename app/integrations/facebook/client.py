"""ARIIA – Facebook Messenger Client.

Sends and receives Facebook Messenger messages via the Meta Send/Receive API.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class FacebookMessengerClient:
    """Client for Facebook Messenger via Meta Send API.

    Parameters
    ----------
    page_id : str
        The Facebook Page ID.
    page_access_token : str
        Long-lived Page Access Token with pages_messaging permission.
    app_secret : str, optional
        App Secret for webhook signature verification.
    """

    def __init__(
        self,
        page_id: str,
        page_access_token: str,
        app_secret: str = "",
    ) -> None:
        self.page_id = page_id
        self.page_access_token = page_access_token
        self.app_secret = app_secret

    async def send_message(self, recipient_id: str, text: str) -> dict[str, Any]:
        """Send a text message to a Facebook Messenger user.

        Parameters
        ----------
        recipient_id : str
            Page-scoped user ID (PSID).
        text : str
            Message text to send.

        Returns
        -------
        dict
            API response from Meta Graph API.
        """
        url = f"{GRAPH_API_BASE}/me/messages"
        payload = {
            "messaging_type": "RESPONSE",
            "recipient": {"id": recipient_id},
            "message": {"text": text},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                params={"access_token": self.page_access_token},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "facebook.message_sent",
                recipient=recipient_id,
                message_id=data.get("message_id", ""),
            )
            return data

    async def send_quick_replies(
        self,
        recipient_id: str,
        text: str,
        quick_replies: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send a message with quick reply buttons.

        Parameters
        ----------
        recipient_id : str
            Page-scoped user ID.
        text : str
            Message text.
        quick_replies : list
            List of quick reply dicts with 'title' and 'payload'.
        """
        url = f"{GRAPH_API_BASE}/me/messages"
        payload = {
            "messaging_type": "RESPONSE",
            "recipient": {"id": recipient_id},
            "message": {
                "text": text,
                "quick_replies": [
                    {
                        "content_type": "text",
                        "title": qr.get("title", ""),
                        "payload": qr.get("payload", qr.get("title", "")),
                    }
                    for qr in quick_replies
                ],
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                params={"access_token": self.page_access_token},
            )
            resp.raise_for_status()
            return resp.json()

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify the X-Hub-Signature-256 header from Meta."""
        if not self.app_secret:
            return True
        if not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            self.app_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """Fetch basic profile info for a Messenger user.

        Parameters
        ----------
        user_id : str
            Page-scoped user ID.

        Returns
        -------
        dict
            User profile data (first_name, last_name, profile_pic).
        """
        url = f"{GRAPH_API_BASE}/{user_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                params={
                    "fields": "first_name,last_name,profile_pic",
                    "access_token": self.page_access_token,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            return {}

    async def set_typing_on(self, recipient_id: str) -> None:
        """Send typing indicator to user."""
        url = f"{GRAPH_API_BASE}/me/messages"
        payload = {
            "recipient": {"id": recipient_id},
            "sender_action": "typing_on",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                url,
                json=payload,
                params={"access_token": self.page_access_token},
            )
