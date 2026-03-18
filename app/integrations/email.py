from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage

import httpx
import structlog

logger = structlog.get_logger()


class SMTPMailer:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        from_name: str = "Ariia",
        use_starttls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.use_starttls = use_starttls

    def send_text_mail(self, to_email: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        self._build_headers(msg, to_email, subject)
        msg.set_content(body)
        self._send_message(msg)
        logger.info("email.sent", to_email=to_email, subject=" ".join(subject.splitlines()).strip())

    def _send_message(self, msg: EmailMessage) -> None:
        """Send an already-built EmailMessage via SMTP."""
        smtp = None
        try:
            if self.port == 465:
                smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=30)
                smtp.login(self.username, self.password)
                smtp.send_message(msg)
            else:
                smtp = smtplib.SMTP(self.host, self.port, timeout=30)
                smtp.ehlo()
                if self.use_starttls:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(self.username, self.password)
                smtp.send_message(msg)
        except smtplib.SMTPResponseException as e:
            if e.code == 250:
                pass
            else:
                raise e
        finally:
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    pass

    def _build_headers(self, msg: EmailMessage, to_email: str, subject: str) -> None:
        """Set common headers on an EmailMessage."""
        clean_subject = " ".join(subject.splitlines()).strip()
        clean_from_name = " ".join(self.from_name.splitlines()).strip()
        msg["Subject"] = clean_subject
        msg["From"] = f"{clean_from_name} <{self.from_email}>"
        msg["To"] = to_email

    def send_html_mail(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
    ) -> None:
        """Send a multipart/alternative email with plain text and HTML parts."""
        msg = EmailMessage()
        self._build_headers(msg, to_email, subject)
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")

        self._send_message(msg)
        logger.info("email.html_sent", to_email=to_email, subject=subject)

    def send_html_mail_with_attachment(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        attachment_url: str,
        attachment_filename: str,
    ) -> None:
        """Send a multipart/mixed email with HTML body and a file attachment.

        Downloads the attachment from attachment_url via HTTP GET.
        Max attachment size: 10 MB.
        """
        _MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

        # Download attachment
        try:
            resp = httpx.get(attachment_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except Exception as exc:
            logger.error(
                "email.attachment_download_failed",
                url=attachment_url,
                error=str(exc),
            )
            raise ValueError(f"Failed to download attachment from {attachment_url}: {exc}") from exc

        data = resp.content
        if len(data) > _MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"Attachment too large ({len(data)} bytes, max {_MAX_ATTACHMENT_BYTES})"
            )

        # Build message
        msg = EmailMessage()
        self._build_headers(msg, to_email, subject)
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")

        # Guess MIME type
        mime_type, _ = mimetypes.guess_type(attachment_filename)
        if mime_type is None:
            maintype, subtype = "application", "octet-stream"
        else:
            maintype, subtype = mime_type.split("/", 1)

        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=attachment_filename,
        )

        self._send_message(msg)
        logger.info(
            "email.html_with_attachment_sent",
            to_email=to_email,
            subject=subject,
            attachment=attachment_filename,
        )
