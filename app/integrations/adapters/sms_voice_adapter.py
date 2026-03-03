"""ARIIA v2.0 – SMS & Voice Integration Adapter (Twilio).

@ARCH: Sprint 1 (Integration Roadmap), Task S1.4
Concrete adapter for Twilio SMS and Voice. Implements the full Twilio
REST API for sending/receiving SMS and managing voice calls.

Supported Capabilities:
  - messaging.send.sms         → Send an SMS message
  - messaging.receive.sms      → Process inbound SMS (Twilio webhook)
  - messaging.sms.status       → Process SMS status callback
  - voice.call.outbound        → Initiate an outbound voice call
  - voice.call.twiml           → Generate TwiML response for call handling
  - voice.call.status          → Process voice call status callback
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class SmsVoiceAdapter(BaseAdapter):
    """Adapter for Twilio SMS and Voice.

    Routes capability calls to the Twilio REST API,
    wrapping results in the standardized AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "sms_voice"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "messaging.send.sms",
            "messaging.receive.sms",
            "messaging.sms.status",
            "voice.call.outbound",
            "voice.call.twiml",
            "voice.call.status",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "SMS & Voice"

    @property
    def category(self) -> str:
        return "messaging"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "provider",
                    "label": "Provider",
                    "type": "select",
                    "required": True,
                    "help_text": "SMS/Voice Provider (z.B. Twilio, Vonage).",
                },
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "required": True,
                    "help_text": "Provider API Key.",
                },
                {
                    "key": "api_secret",
                    "label": "API Secret",
                    "type": "password",
                    "required": True,
                    "help_text": "Provider API Secret.",
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
            metadata={"note": "SMS & Voice does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="SMS & Voice-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability to the appropriate Twilio handler."""
        handlers = {
            "messaging.send.sms": self._send_sms,
            "messaging.receive.sms": self._receive_sms,
            "messaging.sms.status": self._sms_status,
            "voice.call.outbound": self._outbound_call,
            "voice.call.twiml": self._generate_twiml,
            "voice.call.status": self._call_status,
        }

        handler = handlers.get(capability_id)
        if not handler:
            return AdapterResult(
                success=False,
                error=f"No handler for capability '{capability_id}'",
                error_code="NO_HANDLER",
            )

        return await handler(tenant_id, **kwargs)

    # ─── Config Resolution ───────────────────────────────────────────────

    def _get_twilio_config(self, tenant_id: int, **kwargs: Any) -> dict | None:
        """Resolve Twilio configuration for the given tenant.

        Returns dict with account_sid, auth_token, phone_number.
        """
        # Direct credential injection
        if kwargs.get("account_sid") and kwargs.get("auth_token"):
            return {
                "account_sid": kwargs["account_sid"],
                "auth_token": kwargs["auth_token"],
                "phone_number": kwargs.get("phone_number", ""),
                "twiml_app_sid": kwargs.get("twiml_app_sid", ""),
            }

        # Tenant-based credential resolution (try SMS config first, then voice)
        try:
            from app.core.integration_models import get_integration_config

            config = get_integration_config(tenant_id, "sms")
            if config:
                return config

            config = get_integration_config(tenant_id, "twilio_voice")
            if config:
                return config
        except Exception as e:
            logger.warning("sms_voice_adapter.config_resolution_failed", tenant_id=tenant_id, error=str(e))

        return None

    # ─── SMS Capabilities ────────────────────────────────────────────────

    async def _send_sms(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send an SMS message via Twilio."""
        import httpx

        to = kwargs.get("to", "")
        body = kwargs.get("body", "") or kwargs.get("text", "") or kwargs.get("content", "")
        media_url = kwargs.get("media_url")  # For MMS

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

        config = self._get_twilio_config(tenant_id, **kwargs)
        if not config:
            return AdapterResult(
                success=False,
                error="Twilio SMS ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        account_sid = config["account_sid"]
        auth_token = config["auth_token"]
        from_number = config.get("phone_number", "")

        if not from_number:
            return AdapterResult(
                success=False,
                error="Twilio-Telefonnummer ist nicht konfiguriert.",
                error_code="MISSING_PHONE_NUMBER",
            )

        url = f"{TWILIO_API_BASE}/Accounts/{account_sid}/Messages.json"
        payload = {
            "To": to,
            "From": from_number,
            "Body": body,
        }
        if media_url:
            payload["MediaUrl"] = media_url

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    data=payload,
                    auth=(account_sid, auth_token),
                )
                response.raise_for_status()
                data = response.json()

            return AdapterResult(
                success=True,
                data={
                    "sid": data.get("sid", ""),
                    "to": to,
                    "from": from_number,
                    "status": data.get("status", "queued"),
                    "method": "twilio_sms",
                },
                metadata={"raw_response": data},
            )
        except httpx.HTTPStatusError as e:
            error_body = ""
            try:
                error_body = e.response.json().get("message", str(e))
            except Exception:
                error_body = str(e)
            return AdapterResult(success=False, error=error_body, error_code="TWILIO_SMS_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SMS_SEND_FAILED")

    async def _receive_sms(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Process an inbound SMS from Twilio webhook.

        Normalizes the Twilio webhook payload into a structured format.
        """
        payload = kwargs.get("payload", {})
        if not payload:
            return AdapterResult(
                success=False,
                error="'payload' (Twilio SMS Webhook) ist erforderlich.",
                error_code="MISSING_PAYLOAD",
            )

        normalized = {
            "message_sid": payload.get("MessageSid", "") or payload.get("SmsMessageSid", ""),
            "from": payload.get("From", ""),
            "to": payload.get("To", ""),
            "body": payload.get("Body", ""),
            "num_media": int(payload.get("NumMedia", "0")),
            "from_city": payload.get("FromCity", ""),
            "from_state": payload.get("FromState", ""),
            "from_country": payload.get("FromCountry", ""),
        }

        # Extract media URLs if present
        media = []
        for i in range(normalized["num_media"]):
            media_url = payload.get(f"MediaUrl{i}", "")
            media_type = payload.get(f"MediaContentType{i}", "")
            if media_url:
                media.append({"url": media_url, "content_type": media_type})
        if media:
            normalized["media"] = media

        return AdapterResult(
            success=True,
            data=normalized,
            metadata={"source": "twilio_sms_inbound"},
        )

    async def _sms_status(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Process an SMS status callback from Twilio."""
        payload = kwargs.get("payload", {})
        if not payload:
            return AdapterResult(
                success=False,
                error="'payload' (Twilio Status Callback) ist erforderlich.",
                error_code="MISSING_PAYLOAD",
            )

        return AdapterResult(
            success=True,
            data={
                "message_sid": payload.get("MessageSid", ""),
                "message_status": payload.get("MessageStatus", ""),
                "to": payload.get("To", ""),
                "error_code": payload.get("ErrorCode"),
                "error_message": payload.get("ErrorMessage"),
            },
        )

    # ─── Voice Capabilities ──────────────────────────────────────────────

    async def _outbound_call(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Initiate an outbound voice call via Twilio."""
        import httpx

        to = kwargs.get("to", "")
        twiml_url = kwargs.get("twiml_url", "")
        twiml = kwargs.get("twiml", "")
        status_callback = kwargs.get("status_callback", "")

        if not to:
            return AdapterResult(
                success=False,
                error="Empfänger-Nummer ('to') ist erforderlich.",
                error_code="MISSING_RECIPIENT",
            )
        if not twiml_url and not twiml:
            return AdapterResult(
                success=False,
                error="'twiml_url' oder 'twiml' ist erforderlich.",
                error_code="MISSING_TWIML",
            )

        config = self._get_twilio_config(tenant_id, **kwargs)
        if not config:
            return AdapterResult(
                success=False,
                error="Twilio Voice ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        account_sid = config["account_sid"]
        auth_token = config["auth_token"]
        from_number = config.get("phone_number", "")

        url = f"{TWILIO_API_BASE}/Accounts/{account_sid}/Calls.json"
        payload: dict[str, Any] = {
            "To": to,
            "From": from_number,
        }

        if twiml_url:
            payload["Url"] = twiml_url
        elif twiml:
            payload["Twiml"] = twiml

        if status_callback:
            payload["StatusCallback"] = status_callback
            payload["StatusCallbackEvent"] = ["initiated", "ringing", "answered", "completed"]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    data=payload,
                    auth=(account_sid, auth_token),
                )
                response.raise_for_status()
                data = response.json()

            return AdapterResult(
                success=True,
                data={
                    "call_sid": data.get("sid", ""),
                    "to": to,
                    "from": from_number,
                    "status": data.get("status", "queued"),
                    "method": "twilio_voice",
                },
                metadata={"raw_response": data},
            )
        except httpx.HTTPStatusError as e:
            error_body = ""
            try:
                error_body = e.response.json().get("message", str(e))
            except Exception:
                error_body = str(e)
            return AdapterResult(success=False, error=error_body, error_code="TWILIO_CALL_FAILED")
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="CALL_FAILED")

    async def _generate_twiml(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Generate TwiML response for call handling.

        Supports common TwiML verbs: Say, Play, Gather, Record, Dial.
        """
        action = kwargs.get("action", "say")  # say, play, gather, record, dial
        text = kwargs.get("text", "")
        language = kwargs.get("language", "de-DE")
        voice = kwargs.get("voice", "Polly.Vicki")
        audio_url = kwargs.get("audio_url", "")
        gather_action_url = kwargs.get("gather_action_url", "")
        dial_number = kwargs.get("dial_number", "")
        record_action_url = kwargs.get("record_action_url", "")

        twiml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<Response>"]

        if action == "say" and text:
            twiml_parts.append(f'  <Say language="{language}" voice="{voice}">{text}</Say>')

        elif action == "play" and audio_url:
            twiml_parts.append(f"  <Play>{audio_url}</Play>")

        elif action == "gather":
            gather_attrs = f'input="speech dtmf" language="{language}"'
            if gather_action_url:
                gather_attrs += f' action="{gather_action_url}"'
            twiml_parts.append(f"  <Gather {gather_attrs}>")
            if text:
                twiml_parts.append(f'    <Say language="{language}" voice="{voice}">{text}</Say>')
            twiml_parts.append("  </Gather>")

        elif action == "record":
            record_attrs = 'maxLength="120" playBeep="true"'
            if record_action_url:
                record_attrs += f' action="{record_action_url}"'
            twiml_parts.append(f"  <Record {record_attrs} />")

        elif action == "dial" and dial_number:
            twiml_parts.append(f"  <Dial>{dial_number}</Dial>")

        else:
            twiml_parts.append(f'  <Say language="{language}" voice="{voice}">Willkommen bei ARIIA.</Say>')

        twiml_parts.append("</Response>")
        twiml_xml = "\n".join(twiml_parts)

        return AdapterResult(
            success=True,
            data={"twiml": twiml_xml, "action": action},
        )

    async def _call_status(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Process a voice call status callback from Twilio."""
        payload = kwargs.get("payload", {})
        if not payload:
            return AdapterResult(
                success=False,
                error="'payload' (Twilio Call Status Callback) ist erforderlich.",
                error_code="MISSING_PAYLOAD",
            )

        return AdapterResult(
            success=True,
            data={
                "call_sid": payload.get("CallSid", ""),
                "call_status": payload.get("CallStatus", ""),
                "from": payload.get("From", ""),
                "to": payload.get("To", ""),
                "duration": payload.get("CallDuration", ""),
                "direction": payload.get("Direction", ""),
            },
        )

    # ─── Health Check ────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Twilio is configured for this tenant."""
        config = self._get_twilio_config(tenant_id)
        if config:
            return AdapterResult(
                success=True,
                data={"status": "ok", "adapter": "sms_voice"},
            )
        return AdapterResult(
            success=False,
            error="Twilio SMS/Voice not configured",
            error_code="NOT_CONFIGURED",
        )
