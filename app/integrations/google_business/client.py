"""ARIIA – Google Business Messages Client.

Sends and receives messages via the Google Business Messages API.
Uses the Business Communications API (businesscommunications.googleapis.com).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

API_BASE = "https://businessmessages.googleapis.com/v1"


class GoogleBusinessClient:
    """Client for Google Business Messages API.

    Parameters
    ----------
    service_account_json : str
        JSON string of the Google Cloud service account credentials.
    agent_id : str
        The Business Messages agent ID.
    """

    def __init__(
        self,
        service_account_json: str,
        agent_id: str,
    ) -> None:
        self.agent_id = agent_id
        self._credentials: dict[str, Any] = {}
        self._access_token: str = ""
        self._token_expiry: float = 0

        try:
            self._credentials = json.loads(service_account_json) if service_account_json else {}
        except (json.JSONDecodeError, TypeError):
            logger.warning("google_business.invalid_credentials_json")

    async def _get_access_token(self) -> str:
        """Obtain an OAuth2 access token using service account credentials.

        Uses the JWT Bearer flow for Google service accounts.

        Returns
        -------
        str
            Valid access token.
        """
        import time

        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        if not self._credentials:
            raise ValueError("No service account credentials configured")

        # Build JWT for token exchange
        import base64
        import hashlib
        import hmac as _hmac

        now = int(time.time())
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()

        claim_set = {
            "iss": self._credentials.get("client_email", ""),
            "scope": "https://www.googleapis.com/auth/businessmessages",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }
        payload = base64.urlsafe_b64encode(
            json.dumps(claim_set).encode()
        ).rstrip(b"=").decode()

        signing_input = f"{header}.{payload}"

        # Sign with RSA private key
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            private_key_pem = self._credentials.get("private_key", "")
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode(), password=None
            )
            signature = private_key.sign(
                signing_input.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        except ImportError:
            logger.error("google_business.cryptography_not_installed")
            raise RuntimeError(
                "cryptography package required for Google Business Messages. "
                "Install with: pip install cryptography"
            )

        jwt_token = f"{signing_input}.{sig_b64}"

        # Exchange JWT for access token
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": jwt_token,
                },
            )
            resp.raise_for_status()
            token_data = resp.json()
            self._access_token = token_data["access_token"]
            self._token_expiry = now + token_data.get("expires_in", 3600)
            return self._access_token

    async def send_message(
        self,
        conversation_id: str,
        text: str,
    ) -> dict[str, Any]:
        """Send a text message to a Google Business Messages conversation.

        Parameters
        ----------
        conversation_id : str
            The conversation ID from the inbound webhook.
        text : str
            Message text to send.

        Returns
        -------
        dict
            API response.
        """
        import uuid

        token = await self._get_access_token()
        url = f"{API_BASE}/conversations/{conversation_id}/messages"

        payload = {
            "messageId": str(uuid.uuid4()),
            "representative": {
                "representativeType": "BOT",
            },
            "text": text,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "google_business.message_sent",
                conversation_id=conversation_id,
                message_id=data.get("name", ""),
            )
            return data

    async def send_rich_card(
        self,
        conversation_id: str,
        title: str,
        description: str,
        suggestions: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Send a rich card with optional suggestion chips.

        Parameters
        ----------
        conversation_id : str
            The conversation ID.
        title : str
            Card title.
        description : str
            Card description.
        suggestions : list, optional
            List of suggestion dicts with 'text' and 'postback_data'.
        """
        import uuid

        token = await self._get_access_token()
        url = f"{API_BASE}/conversations/{conversation_id}/messages"

        payload: dict[str, Any] = {
            "messageId": str(uuid.uuid4()),
            "representative": {"representativeType": "BOT"},
            "richCard": {
                "standaloneCard": {
                    "cardContent": {
                        "title": title,
                        "description": description,
                    },
                },
            },
        }

        if suggestions:
            payload["suggestions"] = [
                {
                    "reply": {
                        "text": s.get("text", ""),
                        "postbackData": s.get("postback_data", s.get("text", "")),
                    }
                }
                for s in suggestions
            ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()
