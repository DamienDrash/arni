"""ARIIA v1.4 – WhatsApp Integration (Meta Cloud API).

@BACKEND: Sprint 3, Task 3.1 + 3.2
Outbound messaging + HMAC-SHA256 webhook signature validation.
"""

import hashlib
import hmac
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class WhatsAppClient:
    """Meta Cloud API client for WhatsApp Business messaging.
    Now supports WAHA (WhatsApp Web bridge) as a fallback/alternative.

    Handles outbound text/template messages and webhook verification.
    """

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        app_secret: str = "",
        waha_api_url: str | None = None,
        waha_api_key: str | None = None,
    ) -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._app_secret = app_secret
        self._base_url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
        self.waha_api_url = waha_api_url
        self.waha_api_key = waha_api_key

    async def send_text(self, to: str, body: str) -> dict[str, Any]:
        """Send a text message to a WhatsApp user."""
        if self.waha_api_url:
            return await self._send_waha(to, body)
            
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        return await self._send(payload)

    async def _send_waha(self, to: str, body: str) -> dict[str, Any]:
        """Send message via WAHA (WhatsApp Web bridge)."""
        # Ensure 'to' has @c.us for WAHA if it doesn't
        chat_id = to if "@" in to else f"{to}@c.us"
        
        payload = {
            "chatId": chat_id,
            "text": body,
            "session": "default"
        }
        
        headers = {"Content-Type": "application/json"}
        if self.waha_api_key:
            headers["X-Api-Key"] = self.waha_api_key

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.waha_api_url}/api/sendText",
                json=payload,
                headers=headers
            )
            if response.status_code >= 400:
                logger.error("whatsapp.waha_send_failed", status=response.status_code, body=response.text)
                return {"error": "WAHA_FAILED", "status": response.status_code}
            return response.json()

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "de",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a template message (for initiating conversations).

        Args:
            to: Recipient phone number.
            template_name: Approved template name.
            language_code: Template language code.
            components: Optional template components (header, body params).

        Returns:
            API response dict.
        """
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components
        return await self._send(payload)

    async def send_interactive(
        self,
        to: str,
        interactive: dict[str, Any],
    ) -> dict[str, Any]:
        """Send an interactive message (buttons, lists).

        Args:
            to: Recipient phone number.
            interactive: Interactive message payload (button/list_reply).

        Returns:
            API response dict.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._send(payload)

    async def _send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a message via local WhatsApp Bridge (Node.js)."""
        # Adapt payload for Bridge API
        # Expected: { "to": "...", "text": "..." }
        
        to = payload.get("to", "")
        text = ""
        
        # Extract text from various payload types (text, template)
        msg_type = payload.get("type")
        if msg_type == "text":
            text = payload.get("text", {}).get("body", "")
        elif msg_type == "template":
            # Simple fallback for templates (sending name for now)
            # Ideal: Bridge supports templates, or we render text here
            tmpl_name = payload.get("template", {}).get("name", "unknown")
            text = f"[TEMPLATE: {tmpl_name}] Please reply to continue."
        elif msg_type == "interactive":
             text = "[INTERACTIVE MENU] (Not supported in Bridge v1)"

        bridge_payload = {"to": to, "text": text}
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    "http://localhost:3000/send",
                    json=bridge_payload,
                )
                response.raise_for_status()
                data = response.json()
                logger.info("whatsapp.bridge.sent", to=to, id=data.get("id"))
                return {"messages": [{"id": data.get("id")}]}
            except Exception as e:
                logger.error("whatsapp.bridge.failed", error=str(e))
                raise

    def verify_webhook_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify Meta webhook HMAC-SHA256 signature.

        Args:
            payload_body: Raw request body bytes.
            signature_header: X-Hub-Signature-256 header value.

        Returns:
            True if signature is valid.
        """
        if not self._app_secret:
            logger.warning("whatsapp.signature_misconfigured", reason="no_app_secret_configured")
            return False

        if not signature_header or not signature_header.startswith("sha256="):
            return False

        expected_signature = hmac.new(
            self._app_secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()

        received_signature = signature_header[7:]  # Strip "sha256=" prefix
        return hmac.compare_digest(expected_signature, received_signature)

    async def mark_as_read(self, message_id: str) -> None:
        """Mark a received message as read (blue ticks)."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        try:
            await self._send(payload)
        except Exception:
            pass  # Non-critical, best effort
