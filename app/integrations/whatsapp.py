"""ARNI – WhatsApp Integration.

Supports two delivery modes:
  - Meta Cloud API   (bridge_url="")  – requires access_token + phone_number_id
  - WhatsApp Web/QR  (bridge_url set) – routes outbound through local Baileys bridge

Webhook signature verification (HMAC-SHA256) works independently of the
delivery mode and is always performed when app_secret is configured.
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


class WhatsAppClient:
    """WhatsApp client supporting Meta Cloud API and local Baileys bridge.

    Delivery mode is determined by the ``bridge_url`` parameter:
      - bridge_url=""  → Meta Cloud API (requires valid access_token / phone_number_id)
      - bridge_url set → WhatsApp Web bridge at that base URL (e.g. http://localhost:3000)

    Webhook signature verification is independent of the delivery mode.
    """

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        app_secret: str = "",
        bridge_url: str = "",
    ) -> None:
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._app_secret = app_secret
        self._bridge_url = bridge_url.rstrip("/") if bridge_url else ""
        self._meta_url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"

    # ──────────────────────────────────────────────────────────────
    # Public send methods
    # ──────────────────────────────────────────────────────────────

    async def send_text(self, to: str, body: str) -> dict[str, Any]:
        """Send a plain-text message.

        Args:
            to: Recipient phone number (E.164, e.g. ``491701234567``).
            body: Message text.

        Returns:
            Response dict containing ``messages[0].id``.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        return await self._send(payload)

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "de",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send an approved template message (no opt-in required).

        Args:
            to: Recipient phone number.
            template_name: Meta-approved template name.
            language_code: Template language code.
            components: Optional parameterized template components.

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
            interactive: Interactive payload (button/list definition).

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

    async def mark_as_read(self, message_id: str) -> None:
        """Mark a received message as read (blue ticks). Best-effort."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        try:
            await self._send(payload)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # Webhook verification
    # ──────────────────────────────────────────────────────────────

    def verify_webhook_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify the Meta HMAC-SHA256 webhook signature.

        Works for both Bridge-forwarded webhooks (the bridge wraps messages in
        Meta format) and direct Meta Cloud API webhooks.

        Args:
            payload_body: Raw request body bytes.
            signature_header: ``X-Hub-Signature-256`` header value.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self._app_secret:
            logger.warning("whatsapp.signature_skipped", reason="no_app_secret_configured")
            return False

        if not signature_header or not signature_header.startswith("sha256="):
            return False

        expected = hmac.new(
            self._app_secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()

        received = signature_header[7:]  # strip "sha256=" prefix
        return hmac.compare_digest(expected, received)

    # ──────────────────────────────────────────────────────────────
    # Internal routing
    # ──────────────────────────────────────────────────────────────

    async def _send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Route outbound message to Bridge or Meta Cloud API."""
        if self._bridge_url:
            return await self._send_via_bridge(payload)
        return await self._send_via_meta_api(payload)

    async def _send_via_bridge(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Deliver message through the local Baileys (WhatsApp Web) bridge."""
        to = payload.get("to", "")
        msg_type = payload.get("type", "")

        if msg_type == "text":
            text = payload.get("text", {}).get("body", "")
        elif msg_type == "template":
            tmpl_name = payload.get("template", {}).get("name", "unknown")
            text = f"[TEMPLATE: {tmpl_name}]"
        elif msg_type == "interactive":
            text = "[INTERACTIVE MENU]"
        else:
            text = str(payload)

        bridge_payload = {"to": to, "text": text}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    f"{self._bridge_url}/send",
                    json=bridge_payload,
                )
                response.raise_for_status()
                data = response.json()
                logger.info("whatsapp.bridge.sent", to=to, id=data.get("id"))
                return {"messages": [{"id": data.get("id")}]}
            except Exception as e:
                logger.error("whatsapp.bridge.failed", to=to, error=str(e))
                raise

    async def _send_via_meta_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Deliver message through the Meta Cloud API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    self._meta_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
                response.raise_for_status()
                data = response.json()
                msg_id = (data.get("messages") or [{}])[0].get("id")
                logger.info("whatsapp.cloud_api.sent", to=payload.get("to"), id=msg_id)
                return data
            except Exception as e:
                logger.error("whatsapp.cloud_api.failed", to=payload.get("to"), error=str(e))
                raise
