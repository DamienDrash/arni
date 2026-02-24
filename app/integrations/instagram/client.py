"""ARIIA – Instagram DM Client.

Sends and receives Instagram Direct Messages via the Meta Graph API.
Uses the same underlying Graph API as WhatsApp Cloud API.
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


class InstagramClient:
    """Client for Instagram Messaging via Meta Graph API.

    Parameters
    ----------
    page_id : str
        The Instagram-connected Facebook Page ID.
    access_token : str
        Long-lived Page Access Token with instagram_manage_messages permission.
    app_secret : str, optional
        App Secret for webhook signature verification.
    """

    def __init__(
        self,
        page_id: str,
        access_token: str,
        app_secret: str = "",
    ) -> None:
        self.page_id = page_id
        self.access_token = access_token
        self.app_secret = app_secret

    async def send_message(self, recipient_id: str, text: str) -> dict[str, Any]:
        """Send a text message to an Instagram user.

        Parameters
        ----------
        recipient_id : str
            Instagram-scoped user ID (IGSID).
        text : str
            Message text to send.

        Returns
        -------
        dict
            API response from Meta Graph API.
        """
        url = f"{GRAPH_API_BASE}/{self.page_id}/messages"
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                params={"access_token": self.access_token},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "instagram.message_sent",
                recipient=recipient_id,
                message_id=data.get("message_id", ""),
            )
            return data

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify the X-Hub-Signature-256 header from Meta.

        Parameters
        ----------
        payload : bytes
            Raw request body.
        signature : str
            Value of X-Hub-Signature-256 header.

        Returns
        -------
        bool
            True if signature is valid.
        """
        if not self.app_secret:
            return True  # No verification configured
        if not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            self.app_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        """Fetch basic profile info for an Instagram user.

        Parameters
        ----------
        user_id : str
            Instagram-scoped user ID.

        Returns
        -------
        dict
            User profile data (name, profile_pic if available).
        """
        url = f"{GRAPH_API_BASE}/{user_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                params={
                    "fields": "name,profile_pic",
                    "access_token": self.access_token,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            return {}
