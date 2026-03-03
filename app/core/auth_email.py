"""
ARIIA Auth Email Service
========================
Central email service for all authentication-related communications.
Uses info@ariia.ai via Strato SMTP for transactional emails.

Templates follow the ARIIA dark-mode design language:
  - Background: #0a0b0f / Surface: #12131a
  - Accent/Primary: #6c5ce7
  - Text: #e8e9ed / Muted: #8b8d9a
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import os

import structlog

logger = structlog.get_logger()

# ─── SMTP Configuration (loaded from environment variables) ──────────────────
SMTP_HOST = os.getenv("AUTH_SMTP_HOST", "smtp.strato.de")
SMTP_PORT = int(os.getenv("AUTH_SMTP_PORT", "465"))  # SSL
SMTP_USER = os.getenv("AUTH_SMTP_USER", "")
SMTP_PASS = os.getenv("AUTH_SMTP_PASS", "")
FROM_EMAIL = os.getenv("AUTH_SMTP_FROM", "info@ariia.ai")
FROM_NAME = "ARIIA"


def _base_template(title: str, body_content: str, footer_extra: str = "") -> str:
    """Generate the base HTML email template in ARIIA design."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#0a0b0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0b0f;min-height:100vh;">
<tr><td align="center" style="padding:40px 20px;">

<!-- Main Card -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background-color:#12131a;border-radius:16px;border:1px solid #252630;overflow:hidden;">

<!-- Header with Logo -->
<tr><td style="padding:32px 40px 24px;text-align:center;border-bottom:1px solid #252630;">
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
  <tr>
    <td style="width:36px;height:36px;background:linear-gradient(135deg,#6c5ce7,#a855f7);border-radius:10px;text-align:center;vertical-align:middle;">
      <span style="color:#ffffff;font-size:18px;font-weight:800;line-height:36px;">A</span>
    </td>
    <td style="padding-left:12px;">
      <span style="color:#e8e9ed;font-size:22px;font-weight:700;letter-spacing:1.5px;">ARIIA</span>
    </td>
  </tr>
  </table>
</td></tr>

<!-- Body Content -->
<tr><td style="padding:32px 40px;">
{body_content}
</td></tr>

<!-- Footer -->
<tr><td style="padding:24px 40px 32px;border-top:1px solid #252630;text-align:center;">
  {footer_extra}
  <p style="margin:8px 0 0;color:#5a5c6b;font-size:12px;line-height:1.5;">
    &copy; 2026 ARIIA. All rights reserved.<br>
    Enterprise AI Agent Platform
  </p>
  <p style="margin:8px 0 0;">
    <a href="https://www.ariia.ai/privacy" style="color:#5a5c6b;font-size:11px;text-decoration:underline;">Privacy Policy</a>
    &nbsp;&middot;&nbsp;
    <a href="https://www.ariia.ai/terms" style="color:#5a5c6b;font-size:11px;text-decoration:underline;">Terms of Service</a>
    &nbsp;&middot;&nbsp;
    <a href="https://www.ariia.ai/imprint" style="color:#5a5c6b;font-size:11px;text-decoration:underline;">Imprint</a>
  </p>
</td></tr>

</table>
<!-- /Main Card -->

</td></tr>
</table>
</body>
</html>"""


def _heading(text: str) -> str:
    return f'<h1 style="margin:0 0 8px;color:#e8e9ed;font-size:22px;font-weight:700;line-height:1.3;">{text}</h1>'


def _paragraph(text: str) -> str:
    return f'<p style="margin:0 0 16px;color:#8b8d9a;font-size:14px;line-height:1.6;">{text}</p>'


def _button(label: str, url: str) -> str:
    return f"""\
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px auto;">
<tr><td style="background:linear-gradient(135deg,#6c5ce7,#a855f7);border-radius:10px;text-align:center;">
  <a href="{url}" target="_blank" style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;letter-spacing:0.3px;">{label}</a>
</td></tr>
</table>"""


def _code_box(code: str) -> str:
    return f"""\
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:20px 0;">
<tr><td style="background-color:#1a1b24;border:1px solid #252630;border-radius:12px;padding:20px;text-align:center;">
  <span style="font-family:'Courier New',monospace;font-size:32px;font-weight:700;letter-spacing:8px;color:#6c5ce7;">{code}</span>
</td></tr>
</table>"""


def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #252630;margin:24px 0;">'


def _small_note(text: str) -> str:
    return f'<p style="margin:16px 0 0;color:#5a5c6b;font-size:12px;line-height:1.5;">{text}</p>'


# ─── Email Templates ────────────────────────────────────────────────────────

def render_verification_email(full_name: str, code: str, verify_url: str) -> tuple[str, str, str]:
    """Render email verification email. Returns (subject, html, plaintext)."""
    name = full_name or "there"
    subject = f"Verify your email – ARIIA"

    body = (
        _heading("Verify your email address")
        + _paragraph(f"Hi {name}, welcome to ARIIA! Please verify your email address to activate your account.")
        + _paragraph("Enter this verification code:")
        + _code_box(code)
        + _paragraph("Or click the button below:")
        + _button("Verify Email", verify_url)
        + _divider()
        + _small_note("This code expires in 30 minutes. If you didn't create an ARIIA account, you can safely ignore this email.")
    )
    html = _base_template("Verify your email – ARIIA", body)

    plaintext = (
        f"Hi {name},\n\n"
        f"Welcome to ARIIA! Please verify your email address.\n\n"
        f"Your verification code: {code}\n\n"
        f"Or visit: {verify_url}\n\n"
        f"This code expires in 30 minutes.\n\n"
        f"– ARIIA Team"
    )
    return subject, html, plaintext


def render_password_reset_email(full_name: str, code: str, reset_url: str) -> tuple[str, str, str]:
    """Render password reset email. Returns (subject, html, plaintext)."""
    name = full_name or "there"
    subject = "Reset your password – ARIIA"

    body = (
        _heading("Reset your password")
        + _paragraph(f"Hi {name}, we received a request to reset your ARIIA password.")
        + _paragraph("Enter this reset code:")
        + _code_box(code)
        + _paragraph("Or click the button below:")
        + _button("Reset Password", reset_url)
        + _divider()
        + _small_note("This code expires in 1 hour. If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.")
    )
    html = _base_template("Reset your password – ARIIA", body)

    plaintext = (
        f"Hi {name},\n\n"
        f"We received a request to reset your ARIIA password.\n\n"
        f"Your reset code: {code}\n\n"
        f"Or visit: {reset_url}\n\n"
        f"This code expires in 1 hour.\n\n"
        f"If you didn't request this, ignore this email.\n\n"
        f"– ARIIA Team"
    )
    return subject, html, plaintext


def render_welcome_email(full_name: str, tenant_name: str, login_url: str) -> tuple[str, str, str]:
    """Render welcome email after successful verification. Returns (subject, html, plaintext)."""
    name = full_name or "there"
    subject = f"Welcome to ARIIA, {name}!"

    body = (
        _heading(f"Welcome to ARIIA! 🎉")
        + _paragraph(f"Hi {name}, your account for <strong style='color:#e8e9ed;'>{tenant_name}</strong> is now fully set up and ready to go.")
        + _paragraph("Here's how to get started:")
        + f"""
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:16px 0;">
          <tr><td style="padding:12px 16px;background-color:#1a1b24;border:1px solid #252630;border-radius:10px;margin-bottom:8px;">
            <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="width:32px;vertical-align:top;">
                  <span style="display:inline-block;width:24px;height:24px;background:linear-gradient(135deg,#6c5ce7,#a855f7);border-radius:50%;text-align:center;line-height:24px;color:#fff;font-size:12px;font-weight:700;">1</span>
                </td>
                <td style="padding-left:8px;">
                  <span style="color:#e8e9ed;font-size:14px;font-weight:600;">Connect your first channel</span><br>
                  <span style="color:#8b8d9a;font-size:13px;">WhatsApp, Telegram, or Voice – set up in minutes.</span>
                </td>
              </tr>
            </table>
          </td></tr>
          <tr><td style="height:8px;"></td></tr>
          <tr><td style="padding:12px 16px;background-color:#1a1b24;border:1px solid #252630;border-radius:10px;margin-bottom:8px;">
            <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="width:32px;vertical-align:top;">
                  <span style="display:inline-block;width:24px;height:24px;background:linear-gradient(135deg,#6c5ce7,#a855f7);border-radius:50%;text-align:center;line-height:24px;color:#fff;font-size:12px;font-weight:700;">2</span>
                </td>
                <td style="padding-left:8px;">
                  <span style="color:#e8e9ed;font-size:14px;font-weight:600;">Configure your AI agent</span><br>
                  <span style="color:#8b8d9a;font-size:13px;">Customize prompts, personality, and knowledge base.</span>
                </td>
              </tr>
            </table>
          </td></tr>
          <tr><td style="height:8px;"></td></tr>
          <tr><td style="padding:12px 16px;background-color:#1a1b24;border:1px solid #252630;border-radius:10px;">
            <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="width:32px;vertical-align:top;">
                  <span style="display:inline-block;width:24px;height:24px;background:linear-gradient(135deg,#6c5ce7,#a855f7);border-radius:50%;text-align:center;line-height:24px;color:#fff;font-size:12px;font-weight:700;">3</span>
                </td>
                <td style="padding-left:8px;">
                  <span style="color:#e8e9ed;font-size:14px;font-weight:600;">Invite your team</span><br>
                  <span style="color:#8b8d9a;font-size:13px;">Add team members and assign roles for collaboration.</span>
                </td>
              </tr>
            </table>
          </td></tr>
        </table>
        """
        + _button("Go to Dashboard", login_url)
        + _divider()
        + _small_note("Your 14-day free trial has started. Need help? Reply to this email or contact us at hello@ariia.ai.")
    )
    html = _base_template(f"Welcome to ARIIA!", body)

    plaintext = (
        f"Hi {name},\n\n"
        f"Welcome to ARIIA! Your account for {tenant_name} is ready.\n\n"
        f"Get started:\n"
        f"1. Connect your first channel (WhatsApp, Telegram, or Voice)\n"
        f"2. Configure your AI agent\n"
        f"3. Invite your team\n\n"
        f"Go to Dashboard: {login_url}\n\n"
        f"Your 14-day free trial has started.\n\n"
        f"– ARIIA Team"
    )
    return subject, html, plaintext


def render_password_changed_email(full_name: str) -> tuple[str, str, str]:
    """Render password changed notification. Returns (subject, html, plaintext)."""
    name = full_name or "there"
    subject = "Password changed – ARIIA"

    body = (
        _heading("Your password was changed")
        + _paragraph(f"Hi {name}, your ARIIA password was successfully changed.")
        + _paragraph("If you made this change, no further action is needed.")
        + _paragraph("If you did <strong style='color:#ff6b6b;'>not</strong> make this change, please reset your password immediately or contact our support team.")
        + _button("Reset Password", "https://www.ariia.ai/forgot-password")
        + _divider()
        + _small_note("For security, all other sessions have been signed out.")
    )
    html = _base_template("Password changed – ARIIA", body)

    plaintext = (
        f"Hi {name},\n\n"
        f"Your ARIIA password was successfully changed.\n\n"
        f"If you did NOT make this change, reset your password immediately:\n"
        f"https://www.ariia.ai/forgot-password\n\n"
        f"All other sessions have been signed out.\n\n"
        f"– ARIIA Team"
    )
    return subject, html, plaintext


def render_team_invitation_email(
    inviter_name: str,
    tenant_name: str,
    role: str,
    invite_url: str,
) -> tuple[str, str, str]:
    """Render team invitation email. Returns (subject, html, plaintext)."""
    subject = f"You've been invited to {tenant_name} on ARIIA"

    role_display = {"tenant_admin": "Admin", "tenant_user": "Member"}.get(role, role)

    body = (
        _heading(f"You're invited!")
        + _paragraph(f"<strong style='color:#e8e9ed;'>{inviter_name}</strong> has invited you to join <strong style='color:#e8e9ed;'>{tenant_name}</strong> on ARIIA as <strong style='color:#6c5ce7;'>{role_display}</strong>.")
        + _paragraph("Click the button below to accept the invitation and create your account:")
        + _button("Accept Invitation", invite_url)
        + _divider()
        + _small_note("This invitation expires in 7 days. If you don't recognize this invitation, you can safely ignore this email.")
    )
    html = _base_template(f"Invitation to {tenant_name} – ARIIA", body)

    plaintext = (
        f"{inviter_name} has invited you to join {tenant_name} on ARIIA as {role_display}.\n\n"
        f"Accept the invitation: {invite_url}\n\n"
        f"This invitation expires in 7 days.\n\n"
        f"– ARIIA Team"
    )
    return subject, html, plaintext


def render_mfa_enabled_email(full_name: str) -> tuple[str, str, str]:
    """Render MFA enabled notification. Returns (subject, html, plaintext)."""
    name = full_name or "there"
    subject = "Two-factor authentication enabled – ARIIA"

    body = (
        _heading("2FA is now active")
        + _paragraph(f"Hi {name}, two-factor authentication has been successfully enabled for your ARIIA account.")
        + _paragraph("From now on, you'll need your authenticator app to sign in. Make sure to keep your backup codes in a safe place.")
        + _divider()
        + _small_note("If you didn't enable 2FA, please contact support immediately at hello@ariia.ai.")
    )
    html = _base_template("2FA enabled – ARIIA", body)

    plaintext = (
        f"Hi {name},\n\n"
        f"Two-factor authentication has been enabled for your ARIIA account.\n\n"
        f"If you didn't enable 2FA, contact support at hello@ariia.ai.\n\n"
        f"– ARIIA Team"
    )
    return subject, html, plaintext


# ─── Email Sending ──────────────────────────────────────────────────────────

def send_auth_email(
    to_email: str,
    subject: str,
    html_body: str,
    plaintext_body: str,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    smtp_user: Optional[str] = None,
    smtp_pass: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
) -> bool:
    """Send an HTML email via SMTP. Returns True on success."""
    host = smtp_host or SMTP_HOST
    port = smtp_port or SMTP_PORT
    user = smtp_user or SMTP_USER
    passwd = smtp_pass or SMTP_PASS
    sender = from_email or FROM_EMAIL
    sender_name = from_name or FROM_NAME

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender}>"
    msg["To"] = to_email
    msg["Reply-To"] = f"{sender_name} <{sender}>"

    # Attach plaintext first, then HTML (email clients prefer last)
    msg.attach(MIMEText(plaintext_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
                smtp.login(user, passwd)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(user, passwd)
                smtp.send_message(msg)

        logger.info("auth_email.sent", to=to_email, subject=subject)
        return True

    except Exception as exc:
        logger.error("auth_email.send_failed", to=to_email, subject=subject, error=str(exc))
        return False
