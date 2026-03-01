"""ARIIA v2.0 – Email Integration Adapter (SMTP + Postmark).

@ARCH: Sprint 1 (Integration Roadmap), Task S1.3
Concrete adapter for Email messaging. Wraps the existing SMTPMailer
and adds Postmark API support for transactional email delivery.

Supported Capabilities:
  - messaging.send.email           → Send a plain-text email via SMTP
  - messaging.send.html_email      → Send an HTML email via SMTP
  - messaging.send.postmark        → Send email via Postmark API
  - messaging.send.template_email  → Send a Postmark template email
  - messaging.receive.email        → Process inbound email (Postmark webhook)
  - messaging.track.opens          → Track email opens (Postmark)
  - messaging.track.bounces        → Process bounce notifications
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class EmailAdapter(BaseAdapter):
    """Adapter for Email messaging via SMTP and Postmark.

    Routes capability calls to the existing SMTPMailer and Postmark API,
    wrapping results in the standardized AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "email"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "messaging.send.email",
            "messaging.send.html_email",
            "messaging.send.postmark",
            "messaging.send.template_email",
            "messaging.receive.email",
            "messaging.track.opens",
            "messaging.track.bounces",
        ]

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability to the appropriate Email handler."""
        handlers = {
            "messaging.send.email": self._send_email,
            "messaging.send.html_email": self._send_html_email,
            "messaging.send.postmark": self._send_postmark,
            "messaging.send.template_email": self._send_template_email,
            "messaging.receive.email": self._receive_email,
            "messaging.track.opens": self._track_opens,
            "messaging.track.bounces": self._track_bounces,
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

    def _get_smtp_mailer(self, tenant_id: int, **kwargs: Any):
        """Resolve an SMTPMailer for the given tenant."""
        from app.integrations.email import SMTPMailer

        # Direct credential injection
        if kwargs.get("host") and kwargs.get("username"):
            return SMTPMailer(
                host=kwargs["host"],
                port=int(kwargs.get("port", 587)),
                username=kwargs["username"],
                password=kwargs.get("password", ""),
                from_email=kwargs.get("from_email", kwargs["username"]),
                from_name=kwargs.get("from_name", "ARIIA"),
                use_starttls=kwargs.get("use_starttls", True),
            )

        # Tenant-based credential resolution
        try:
            from app.core.integration_models import get_integration_config
            config = get_integration_config(tenant_id, "smtp_email")
            if config:
                return SMTPMailer(
                    host=config.get("host", ""),
                    port=int(config.get("port", 587)),
                    username=config.get("username", ""),
                    password=config.get("password", ""),
                    from_email=config.get("from_email", ""),
                    from_name=config.get("from_name", "ARIIA"),
                    use_starttls=config.get("use_starttls", True),
                )
        except Exception as e:
            logger.warning("email_adapter.smtp_config_failed", tenant_id=tenant_id, error=str(e))

        return None

    def _get_postmark_config(self, tenant_id: int, **kwargs: Any) -> dict | None:
        """Resolve Postmark configuration for the given tenant."""
        # Direct credential injection
        if kwargs.get("server_token"):
            return {
                "server_token": kwargs["server_token"],
                "from_email": kwargs.get("from_email", ""),
                "from_name": kwargs.get("from_name", "ARIIA"),
            }

        # Tenant-based credential resolution
        try:
            from app.core.integration_models import get_integration_config
            config = get_integration_config(tenant_id, "postmark")
            if config:
                return config
        except Exception as e:
            logger.warning("email_adapter.postmark_config_failed", tenant_id=tenant_id, error=str(e))

        return None

    # ─── SMTP Capabilities ───────────────────────────────────────────────

    async def _send_email(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a plain-text email via SMTP."""
        to_email = kwargs.get("to_email", "") or kwargs.get("to", "")
        subject = kwargs.get("subject", "")
        body = kwargs.get("body", "") or kwargs.get("content", "") or kwargs.get("text", "")

        if not to_email:
            return AdapterResult(
                success=False,
                error="Empfänger-E-Mail ('to_email') ist erforderlich.",
                error_code="MISSING_RECIPIENT",
            )
        if not subject:
            return AdapterResult(
                success=False,
                error="Betreff ('subject') ist erforderlich.",
                error_code="MISSING_SUBJECT",
            )
        if not body:
            return AdapterResult(
                success=False,
                error="Nachrichtentext ('body') ist erforderlich.",
                error_code="MISSING_BODY",
            )

        mailer = self._get_smtp_mailer(tenant_id, **kwargs)
        if not mailer:
            return AdapterResult(
                success=False,
                error="SMTP-E-Mail ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        try:
            # SMTPMailer.send_text_mail is synchronous, run in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, mailer.send_text_mail, to_email, subject, body)
            return AdapterResult(
                success=True,
                data={"to": to_email, "subject": subject, "status": "sent", "method": "smtp"},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SMTP_SEND_FAILED")

    async def _send_html_email(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send an HTML email via SMTP.

        Extends the basic SMTPMailer with HTML content support.
        """
        import smtplib
        from email.message import EmailMessage

        to_email = kwargs.get("to_email", "") or kwargs.get("to", "")
        subject = kwargs.get("subject", "")
        html_body = kwargs.get("html_body", "") or kwargs.get("html", "")
        text_body = kwargs.get("text_body", "") or kwargs.get("body", "")

        if not to_email or not subject or not html_body:
            return AdapterResult(
                success=False,
                error="'to_email', 'subject' und 'html_body' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        mailer = self._get_smtp_mailer(tenant_id, **kwargs)
        if not mailer:
            return AdapterResult(
                success=False,
                error="SMTP-E-Mail ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        def _send():
            msg = EmailMessage()
            msg["Subject"] = " ".join(subject.splitlines()).strip()
            msg["From"] = f"{mailer.from_name} <{mailer.from_email}>"
            msg["To"] = to_email

            if text_body:
                msg.set_content(text_body)
                msg.add_alternative(html_body, subtype="html")
            else:
                msg.set_content(html_body, subtype="html")

            smtp_conn = None
            try:
                if mailer.port == 465:
                    smtp_conn = smtplib.SMTP_SSL(mailer.host, mailer.port, timeout=30)
                    smtp_conn.login(mailer.username, mailer.password)
                    smtp_conn.send_message(msg)
                else:
                    smtp_conn = smtplib.SMTP(mailer.host, mailer.port, timeout=30)
                    smtp_conn.ehlo()
                    if mailer.use_starttls:
                        smtp_conn.starttls()
                        smtp_conn.ehlo()
                    smtp_conn.login(mailer.username, mailer.password)
                    smtp_conn.send_message(msg)
            finally:
                if smtp_conn:
                    try:
                        smtp_conn.quit()
                    except Exception:
                        pass

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _send)
            return AdapterResult(
                success=True,
                data={"to": to_email, "subject": subject, "status": "sent", "method": "smtp", "format": "html"},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HTML_SEND_FAILED")

    # ─── Postmark Capabilities ───────────────────────────────────────────

    async def _send_postmark(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send an email via Postmark API."""
        import httpx

        to_email = kwargs.get("to_email", "") or kwargs.get("to", "")
        subject = kwargs.get("subject", "")
        text_body = kwargs.get("body", "") or kwargs.get("text_body", "")
        html_body = kwargs.get("html_body", "")

        if not to_email or not subject:
            return AdapterResult(
                success=False,
                error="'to_email' und 'subject' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )
        if not text_body and not html_body:
            return AdapterResult(
                success=False,
                error="'body' oder 'html_body' ist erforderlich.",
                error_code="MISSING_BODY",
            )

        config = self._get_postmark_config(tenant_id, **kwargs)
        if not config:
            return AdapterResult(
                success=False,
                error="Postmark ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        from_email = config.get("from_email", "")
        from_name = config.get("from_name", "ARIIA")
        server_token = config.get("server_token", "")

        payload: dict[str, Any] = {
            "From": f"{from_name} <{from_email}>" if from_name else from_email,
            "To": to_email,
            "Subject": subject,
        }
        if text_body:
            payload["TextBody"] = text_body
        if html_body:
            payload["HtmlBody"] = html_body

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.postmarkapp.com/email",
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-Postmark-Server-Token": server_token,
                    },
                )
                response.raise_for_status()
                data = response.json()

            return AdapterResult(
                success=True,
                data={
                    "to": to_email,
                    "subject": subject,
                    "message_id": data.get("MessageID", ""),
                    "status": "sent",
                    "method": "postmark",
                },
                metadata={"raw_response": data},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="POSTMARK_SEND_FAILED")

    async def _send_template_email(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Send a Postmark template email."""
        import httpx

        to_email = kwargs.get("to_email", "") or kwargs.get("to", "")
        template_alias = kwargs.get("template_alias", "") or kwargs.get("template_id", "")
        template_model = kwargs.get("template_model", {})

        if not to_email or not template_alias:
            return AdapterResult(
                success=False,
                error="'to_email' und 'template_alias' sind erforderlich.",
                error_code="MISSING_PARAMS",
            )

        config = self._get_postmark_config(tenant_id, **kwargs)
        if not config:
            return AdapterResult(
                success=False,
                error="Postmark ist für diesen Tenant nicht konfiguriert.",
                error_code="NOT_CONFIGURED",
            )

        from_email = config.get("from_email", "")
        from_name = config.get("from_name", "ARIIA")
        server_token = config.get("server_token", "")

        payload = {
            "From": f"{from_name} <{from_email}>" if from_name else from_email,
            "To": to_email,
            "TemplateAlias": template_alias,
            "TemplateModel": template_model,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.postmarkapp.com/email/withTemplate",
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-Postmark-Server-Token": server_token,
                    },
                )
                response.raise_for_status()
                data = response.json()

            return AdapterResult(
                success=True,
                data={
                    "to": to_email,
                    "template": template_alias,
                    "message_id": data.get("MessageID", ""),
                    "status": "sent",
                    "method": "postmark_template",
                },
                metadata={"raw_response": data},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="TEMPLATE_SEND_FAILED")

    # ─── Receive / Tracking Capabilities ─────────────────────────────────

    async def _receive_email(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Process an inbound email from Postmark webhook.

        This normalizes the Postmark inbound payload into a structured format
        compatible with the MessageNormalizer.
        """
        payload = kwargs.get("payload", {})
        if not payload:
            return AdapterResult(
                success=False,
                error="'payload' (Postmark Inbound Webhook) ist erforderlich.",
                error_code="MISSING_PAYLOAD",
            )

        try:
            normalized = {
                "message_id": payload.get("MessageID", ""),
                "from": payload.get("From", ""),
                "from_name": payload.get("FromName", ""),
                "to": payload.get("To", ""),
                "subject": payload.get("Subject", ""),
                "text_body": payload.get("TextBody", ""),
                "html_body": payload.get("HtmlBody", ""),
                "date": payload.get("Date", ""),
                "attachments": [
                    {
                        "name": att.get("Name", ""),
                        "content_type": att.get("ContentType", ""),
                        "content_length": att.get("ContentLength", 0),
                    }
                    for att in payload.get("Attachments", [])
                ],
                "headers": {
                    h.get("Name", ""): h.get("Value", "")
                    for h in payload.get("Headers", [])
                },
            }
            return AdapterResult(
                success=True,
                data=normalized,
                metadata={"source": "postmark_inbound"},
            )
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="RECEIVE_FAILED")

    async def _track_opens(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Process an email open tracking event from Postmark."""
        payload = kwargs.get("payload", {})
        if not payload:
            return AdapterResult(
                success=False,
                error="'payload' (Postmark Open Webhook) ist erforderlich.",
                error_code="MISSING_PAYLOAD",
            )

        return AdapterResult(
            success=True,
            data={
                "message_id": payload.get("MessageID", ""),
                "recipient": payload.get("Recipient", ""),
                "first_open": payload.get("FirstOpen", False),
                "client": payload.get("Client", {}),
                "os": payload.get("OS", {}),
                "platform": payload.get("Platform", ""),
                "geo": payload.get("Geo", {}),
                "received_at": payload.get("ReceivedAt", ""),
            },
        )

    async def _track_bounces(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Process a bounce notification from Postmark."""
        payload = kwargs.get("payload", {})
        if not payload:
            return AdapterResult(
                success=False,
                error="'payload' (Postmark Bounce Webhook) ist erforderlich.",
                error_code="MISSING_PAYLOAD",
            )

        return AdapterResult(
            success=True,
            data={
                "bounce_id": payload.get("ID", ""),
                "type": payload.get("Type", ""),
                "type_code": payload.get("TypeCode", 0),
                "message_id": payload.get("MessageID", ""),
                "email": payload.get("Email", ""),
                "description": payload.get("Description", ""),
                "inactive": payload.get("Inactive", False),
                "can_activate": payload.get("CanActivate", False),
                "bounced_at": payload.get("BouncedAt", ""),
            },
        )

    # ─── Health Check ────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Email is configured for this tenant."""
        smtp = self._get_smtp_mailer(tenant_id)
        postmark = self._get_postmark_config(tenant_id)

        if smtp or postmark:
            providers = []
            if smtp:
                providers.append("smtp")
            if postmark:
                providers.append("postmark")
            return AdapterResult(
                success=True,
                data={"status": "ok", "adapter": "email", "providers": providers},
            )
        return AdapterResult(
            success=False,
            error="Email not configured (neither SMTP nor Postmark)",
            error_code="NOT_CONFIGURED",
        )
