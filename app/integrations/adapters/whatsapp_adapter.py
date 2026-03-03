"""ARIIA v2.0 – WhatsApp Integration Adapter.

@ARCH: Sprint 1 (Integration Roadmap), Task S1.1
Concrete adapter for WhatsApp Business messaging. Wraps the existing
WhatsAppClient and wa_flows into the BaseAdapter interface, providing
standardized capability routing for the DynamicToolResolver.

Supported Capabilities:
  - messaging.send.text           → Send a text message
  - messaging.send.template       → Send a template message
  - messaging.send.interactive    → Send interactive buttons/lists
  - messaging.send.media          → Send media message (image, document, etc.)
  - messaging.mark_read           → Mark a message as read
  - messaging.verify_webhook      → Verify Meta webhook signature
  - messaging.flow.booking        → Booking confirmation flow
  - messaging.flow.time_slots     → Time slot selection flow
  - messaging.flow.cancellation   → Cancellation confirmation flow
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class WhatsAppAdapter(BaseAdapter):
    """Adapter for WhatsApp Business messaging via Meta Cloud API / WAHA.

    Routes capability calls to the existing WhatsAppClient and wa_flows
    module, wrapping results in the standardized AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "whatsapp"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "messaging.send.text",
            "messaging.send.template",
            "messaging.send.interactive",
            "messaging.send.media",
            "messaging.mark_read",
            "messaging.verify_webhook",
            "messaging.flow.booking",
            "messaging.flow.time_slots",
            "messaging.flow.cancellation",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "WhatsApp"

    @property
    def category(self) -> str:
        return "messaging"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "api_url",
                    "label": "API URL",
                    "type": "text",
                    "required": True,
                    "help_text": "WhatsApp Business API URL oder WAHA Instanz-URL.",
                },
                {
                    "key": "api_token",
                    "label": "API Token",
                    "type": "password",
                    "required": True,
                    "help_text": "API Access Token.",
                },
                {
                    "key": "phone_number_id",
                    "label": "Phone Number ID",
                    "type": "text",
                    "required": False,
                    "help_text": "Meta Cloud API Phone Number ID.",
                },
            ],
        }

    async def get_contacts(
        self,
        tenant_id: int,
        config: dict,
        last_sync_at=None,
        sync_mode=None,
    ) -> "SyncResult":
        from app.integrations.adapters.base import SyncResult
        return SyncResult(
            success=True,
            records_fetched=0,
            contacts=[],
            metadata={"note": "WhatsApp does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="WhatsApp-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability to the appropriate WhatsApp handler."""
        handlers = {
            "messaging.send.text": self._send_text,
            "messaging.send.template": self._send_template,
            "messaging.send.interactive": self._send_interactive,
            "messaging.send.media": self._send_media,
            "messaging.mark_read": self._mark_read,
            "messaging.verify_webhook": self._verify_webhook,
            "messaging.flow.booking": self._flow_booking,
            "messaging.flow.time_slots": self._flow_time_slots,
            "messaging.flow.cancellation": self._flow_cancellation,
        }

        handler = handlers.get(capability_id)
        if not handler:
            return AdapterResult(
                success=False,
                error=f"No handler for capability '{capability_id}'",
                error_code="NO_HANDLER",
            )

        return await handler(tenant_id, **kwargs)

    # ─── Client Resolution ───────────────────────────────────────────────

    def _get_client(self, tenant_id: int, **kwargs: Any):
        """Resolve a WhatsAppClient for the given tenant.

        Attempts to load credentials from kwargs (for direct use) or
        from the tenant's integration configuration.
        """
        from app.integrations.whatsapp import WhatsAppClient

        # Direct credential injection (e.g., from tests or manual calls)
        if kwargs.get("access_token") and kwargs.get("phone_number_id"):
            return WhatsAppClient(
                access_token=kwargs["access_token"],
                phone_number_id=kwargs["phone_number_id"],
                app_secret=kwargs.get("app_secret", ""),
                waha_api_url=kwargs.get("waha_api_url"),
                waha_api_key=kwargs.get("waha_api_key"),
                session_name=kwargs.get("session_name", "default"),
            )

        # Tenant-based credential resolution
        try:
            from app.core.integration_models import get_integration_config
            config = get_integration_config(tenant_id, "whatsapp")
            if config:
                return WhatsAppClient(
                    access_token=config.get("access_token", ""),
                    phone_number_id=config.get("phone_number_id", ""),
                    app_secret=config.get("app_secret", ""),
                    waha_api_url=config.get("waha_api_url"),
                    waha_api_key=config.get("waha_api_key"),
                    session_name=config.get("session_name", "default"),
                )
        except Exception as e:
            logger.warning("whatsapp_adapter.config_resolution_failed", tenant_id=tenant_id, error=str(e))

        return None

    # ─── Messaging Capabilities ──────────────────────────────────────────

    async def _send_text(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a text message to a WhatsApp user."""
        to = kwargs.get("to", "")
        body = kwargs.get("body", "") or kwargs.get("text", "") or kwargs.get("content", "")

        if not to:
            return AdapterResult(
                success=False,
                error="Empfänger-Nummer ('to') ist erforderlich.",
                error_code="MISSING_RECIPIENT",
            )
        if not body:
            return AdapterResult(
                success=False,
                error="Nachrichtentext ('body') ist erforderlich.",
                error_code="MISSING_BODY",
            )

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await client.send_text(to, body)
            message_id = ""
            if isinstance(result, dict):
                messages = result.get("messages", [])
                if messages:
                    message_id = messages[0].get("id", "")
            return AdapterResult(
                success=True,
                data={"message_id": message_id, "to": to, "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SEND_FAILED")

    async def _send_template(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a template message (for initiating conversations)."""
        to = kwargs.get("to", "")
        template_name = kwargs.get("template_name", "")
        language_code = kwargs.get("language_code", "de")
        components = kwargs.get("components")

        if not to or not template_name:
            return AdapterResult(
                success=False,
                error="'to' und 'template_name' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await client.send_template(to, template_name, language_code, components)
            message_id = ""
            if isinstance(result, dict):
                messages = result.get("messages", [])
                if messages:
                    message_id = messages[0].get("id", "")
            return AdapterResult(
                success=True,
                data={"message_id": message_id, "to": to, "template": template_name, "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="TEMPLATE_SEND_FAILED")

    async def _send_interactive(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send an interactive message (buttons, lists)."""
        to = kwargs.get("to", "")
        interactive = kwargs.get("interactive", {})

        if not to or not interactive:
            return AdapterResult(
                success=False,
                error="'to' und 'interactive' Payload sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await client.send_interactive(to, interactive)
            message_id = ""
            if isinstance(result, dict):
                messages = result.get("messages", [])
                if messages:
                    message_id = messages[0].get("id", "")
            return AdapterResult(
                success=True,
                data={"message_id": message_id, "to": to, "type": "interactive", "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="INTERACTIVE_SEND_FAILED")

    async def _send_media(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a media message (image, document, audio, video).

        This capability extends the WhatsApp client with media support
        by constructing the appropriate payload for the Cloud API.
        """
        to = kwargs.get("to", "")
        media_type = kwargs.get("media_type", "image")  # image, document, audio, video
        media_url = kwargs.get("media_url", "") or kwargs.get("url", "")
        media_id = kwargs.get("media_id", "")
        caption = kwargs.get("caption", "")

        if not to:
            return AdapterResult(
                success=False,
                error="Empfänger-Nummer ('to') ist erforderlich.",
                error_code="MISSING_RECIPIENT",
            )
        if not media_url and not media_id:
            return AdapterResult(
                success=False,
                error="'media_url' oder 'media_id' ist erforderlich.",
                error_code="MISSING_MEDIA",
            )

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        # Build media payload
        media_object: dict[str, Any] = {}
        if media_id:
            media_object["id"] = media_id
        elif media_url:
            media_object["link"] = media_url
        if caption and media_type in ("image", "video", "document"):
            media_object["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: media_object,
        }

        try:
            result = await client._send(payload)
            message_id = ""
            if isinstance(result, dict):
                messages = result.get("messages", [])
                if messages:
                    message_id = messages[0].get("id", "")
            return AdapterResult(
                success=True,
                data={"message_id": message_id, "to": to, "media_type": media_type, "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="MEDIA_SEND_FAILED")

    async def _mark_read(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Mark a received message as read (blue ticks)."""
        message_id = kwargs.get("message_id", "")
        if not message_id:
            return AdapterResult(
                success=False,
                error="'message_id' ist erforderlich.",
                error_code="MISSING_MESSAGE_ID",
            )

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            await client.mark_as_read(message_id)
            return AdapterResult(
                success=True,
                data={"message_id": message_id, "status": "read"},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="MARK_READ_FAILED")

    async def _verify_webhook(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Verify a Meta webhook HMAC-SHA256 signature."""
        payload_body = kwargs.get("payload_body", b"")
        signature_header = kwargs.get("signature_header", "")

        if not payload_body or not signature_header:
            return AdapterResult(
                success=False,
                error="'payload_body' und 'signature_header' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        is_valid = client.verify_webhook_signature(payload_body, signature_header)
        return AdapterResult(
            success=True,
            data={"valid": is_valid},
        )

    # ─── WhatsApp Flow Capabilities ──────────────────────────────────────

    async def _flow_booking(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Generate and send a booking confirmation flow."""
        from app.integrations.wa_flows import booking_confirmation_buttons

        to = kwargs.get("to", "")
        course_name = kwargs.get("course_name", "")
        time_slot = kwargs.get("time_slot", "")
        date = kwargs.get("date", "")
        studio_name = kwargs.get("studio_name", "ARIIA")

        if not to or not course_name or not time_slot or not date:
            return AdapterResult(
                success=False,
                error="'to', 'course_name', 'time_slot' und 'date' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        interactive = booking_confirmation_buttons(course_name, time_slot, date, studio_name)

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await client.send_interactive(to, interactive)
            return AdapterResult(
                success=True,
                data={"to": to, "flow": "booking_confirmation", "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="FLOW_BOOKING_FAILED")

    async def _flow_time_slots(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Generate and send a time slot selection flow."""
        from app.integrations.wa_flows import time_slot_list

        to = kwargs.get("to", "")
        available_slots = kwargs.get("available_slots", [])
        course_name = kwargs.get("course_name", "")
        studio_name = kwargs.get("studio_name", "ARIIA")

        if not to or not available_slots or not course_name:
            return AdapterResult(
                success=False,
                error="'to', 'available_slots' und 'course_name' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        interactive = time_slot_list(available_slots, course_name, studio_name)

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await client.send_interactive(to, interactive)
            return AdapterResult(
                success=True,
                data={"to": to, "flow": "time_slot_selection", "slots_count": len(available_slots), "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="FLOW_TIME_SLOTS_FAILED")

    async def _flow_cancellation(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Generate and send a cancellation confirmation flow."""
        from app.integrations.wa_flows import cancellation_confirmation

        to = kwargs.get("to", "")
        if not to:
            return AdapterResult(
                success=False,
                error="Empfänger-Nummer ('to') ist erforderlich.",
                error_code="MISSING_RECIPIENT",
            )

        interactive = cancellation_confirmation()

        client = self._get_client(tenant_id, **kwargs)
        if not client:
            return AdapterResult(
                success=False,
                error="WhatsApp ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            result = await client.send_interactive(to, interactive)
            return AdapterResult(
                success=True,
                data={"to": to, "flow": "cancellation_confirmation", "status": "sent"},
                metadata={"raw_response": result},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="FLOW_CANCELLATION_FAILED")

    # ─── Health Check ────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if WhatsApp is configured for this tenant."""
        client = self._get_client(tenant_id)
        if client:
            return AdapterResult(
                success=True,
                data={"status": "ok", "adapter": "whatsapp"},
            )
        return AdapterResult(
            success=False,
            error="WhatsApp client not configured",
            error_code="NOT_CONFIGURED",
        )
