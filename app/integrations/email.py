from __future__ import annotations

import smtplib
from email.message import EmailMessage

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
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg.set_content(body)

        # Support Port 465 (Direct SSL) vs Port 587 (STARTTLS)
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.ehlo()
                if self.use_starttls:
                    smtp.starttls()
                    smtp.ehlo()  # Required after starttls
                smtp.login(self.username, self.password)
                smtp.send_message(msg)
        logger.info("email.sent", to_email=to_email, subject=subject)
