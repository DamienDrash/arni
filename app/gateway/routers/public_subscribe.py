"""app/gateway/routers/public_subscribe.py — Public subscription + unsubscribe endpoints (no auth).

Double opt-in flow:
  1. POST /public/subscribe/{token}   → store pending in Redis (24 h TTL), send confirmation email
  2. GET  /public/optin-confirm/{token} → validate, create contact+consent, send offer

No contact is created until the confirmation link is clicked (DSGVO-compliant).

Subscribe token format:        base64url("tenant_id:campaign_id:channel")
Unsubscribe token format:      base64url("tenant_id:contact_id:channel")
Optin-confirm token format:    base64url("tenant_id:pending_id:channel:offer_slug:hmac20")
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac as hmac_mod
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.domains.campaigns.models import CampaignRecipient
from app.domains.campaigns.queries import campaign_queries
from app.domains.identity.queries import identity_queries
from app.domains.support.models import ContactConsent

logger = structlog.get_logger()

router = APIRouter(prefix="/public", tags=["public-subscribe"])

# Pending opt-in TTL in seconds (24 hours)
OPTIN_PENDING_TTL = 86_400


# ── Redis helper ───────────────────────────────────────────────────────────────


def _get_redis():
    import redis as _redis
    from config.settings import get_settings
    return _redis.from_url(get_settings().redis_url, decode_responses=True)


# ── Subscribe token (3-part) ───────────────────────────────────────────────────


def _encode_token(a: int, b: int, channel: str) -> str:
    raw = f"{a}:{b}:{channel}"
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def _decode_token(token: str) -> tuple[int, int, str]:
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) != 3:
            raise ValueError("Expected 3 parts")
        a = int(parts[0])
        b = int(parts[1])
        channel = parts[2]
        if channel not in ("email", "whatsapp", "sms", "telegram"):
            raise ValueError(f"Invalid channel: {channel}")
        return a, b, channel
    except Exception as exc:
        logger.warning("public_token.invalid", token=token[:40], error=str(exc))
        raise HTTPException(status_code=400, detail="Ungültiger Link.") from exc


# ── Optin-confirm token (5-part, HMAC-signed) ─────────────────────────────────


def _optin_secret() -> str:
    from config.settings import get_settings
    return get_settings().auth_secret


def _make_optin_confirm_token(
    tenant_id: int, pending_id: str, channel: str, offer: str
) -> str:
    secret = _optin_secret()
    payload = f"{tenant_id}:{pending_id}:{channel}:{offer}"
    sig = hmac_mod.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def _decode_optin_confirm_token(token: str) -> tuple[int, str, str, str]:
    """Returns (tenant_id, pending_id, channel, offer_slug)."""
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        # Split on ":" — but UUIDs contain hyphens not colons, safe to split
        parts = decoded.split(":")
        if len(parts) != 5:
            raise ValueError(f"Expected 5 parts, got {len(parts)}")
        tenant_id_s, pending_id, channel, offer, sig = parts
        secret = _optin_secret()
        payload = f"{tenant_id_s}:{pending_id}:{channel}:{offer}"
        expected = hmac_mod.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:20]
        if not hmac_mod.compare_digest(sig, expected):
            raise ValueError("HMAC mismatch")
        return int(tenant_id_s), pending_id, channel, offer
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("optin_confirm_token.invalid", token=token[:40], error=str(exc))
        raise HTTPException(
            status_code=400, detail="Ungültiger oder abgelaufener Bestätigungslink."
        ) from exc


# ── Email senders ──────────────────────────────────────────────────────────────


def _build_smtp_mailer(tenant_id: int, tenant_name: str):
    """Return a configured SMTPMailer or None if not configured."""
    from app.core.integration_models import get_integration_config
    from app.integrations.email import SMTPMailer

    config = get_integration_config(tenant_id, "smtp_email")
    if not config or not config.get("host"):
        return None
    return SMTPMailer(
        host=config["host"],
        port=int(config.get("port", 587)),
        username=config.get("username", ""),
        password=config.get("password", ""),
        from_email=config.get("from_email", ""),
        from_name=config.get("from_name", tenant_name),
        use_starttls=config.get("use_starttls", "true").lower() != "false",
    )


def _send_optin_email_sync(
    tenant_id: int,
    to_email: str,
    first_name: str,
    tenant_name: str,
    confirm_url: str,
    offer_name: Optional[str],
) -> None:
    """Synchronously send the double-opt-in confirmation email (runs in background task)."""
    try:
        mailer = _build_smtp_mailer(tenant_id, tenant_name)
        if not mailer:
            logger.warning("double_optin.smtp_not_configured", tenant_id=tenant_id)
            return

        subject = f"Bitte bestätige deine Anmeldung bei {tenant_name}"
        offer_line_text = (
            f"\n\nNach der Bestätigung erhältst du: {offer_name}" if offer_name else ""
        )
        offer_line_html = (
            f"<p>Nach der Bestätigung erhältst du: <strong>{offer_name}</strong></p>"
            if offer_name
            else ""
        )

        body_text = (
            f"Hallo {first_name},\n\n"
            f"du hast dich für den Newsletter von {tenant_name} angemeldet.{offer_line_text}\n\n"
            f"Bitte bestätige deine Anmeldung durch Klick auf den folgenden Link:\n\n"
            f"{confirm_url}\n\n"
            f"Dieser Link ist 24 Stunden gültig. Wenn du dich nicht angemeldet hast, "
            f"kannst du diese E-Mail einfach ignorieren.\n\n"
            f"Viele Grüße,\n{tenant_name}"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;background:#f5f5f5;margin:0;padding:0;">
  <div style="max-width:520px;margin:40px auto;background:#fff;border-radius:12px;padding:40px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <h2 style="color:#1a1a1a;margin-top:0;">Anmeldung bestätigen</h2>
    <p style="color:#444;">Hallo {first_name},</p>
    <p style="color:#444;">du hast dich für den Newsletter von <strong>{tenant_name}</strong> angemeldet.</p>
    {offer_line_html}
    <p style="color:#444;">Bitte bestätige deine Anmeldung durch Klick auf den folgenden Button:</p>
    <a href="{confirm_url}"
       style="display:inline-block;margin:20px 0;padding:14px 28px;background:#6C5CE7;color:#fff;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;">
      Anmeldung bestätigen ✓
    </a>
    <p style="color:#888;font-size:12px;">Oder kopiere diesen Link in deinen Browser:<br>
    <a href="{confirm_url}" style="color:#6C5CE7;word-break:break-all;">{confirm_url}</a></p>
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
    <p style="color:#aaa;font-size:11px;">
      Dieser Link ist 24 Stunden gültig.<br>
      Wenn du dich nicht angemeldet hast, kannst du diese E-Mail ignorieren.
    </p>
  </div>
</body>
</html>"""

        mailer.send_html_mail(to_email, subject, body_html, body_text)
        logger.info("double_optin.email_sent", tenant_id=tenant_id, to=to_email)

    except Exception as e:
        logger.warning("double_optin.email_failed", tenant_id=tenant_id, error=str(e))


def _send_whatsapp_optin_request_sync(phone: str, first_name: str, tenant_name: str) -> None:
    """Send a WhatsApp message asking the user to reply JA to confirm (background task)."""
    try:
        from app.integrations.whatsapp import WhatsAppClient

        msg = (
            f"Hallo {first_name},\n\n"
            f"du hast dich für den Newsletter von {tenant_name} angemeldet.\n\n"
            f"Bitte antworte mit *JA* um deine Anmeldung zu bestätigen.\n"
            f"Antworte mit *NEIN* um die Anmeldung abzulehnen."
        )
        client = WhatsAppClient()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(client.send_text(phone, msg))
        loop.close()
    except Exception as e:
        logger.warning("double_optin.whatsapp_failed", error=str(e))


async def _deliver_offer_email(tenant_id: int, contact, offer, tenant_name: str) -> None:
    """Send the offer content via email after confirmed double opt-in."""
    try:
        mailer = _build_smtp_mailer(tenant_id, tenant_name)
        if not mailer:
            return

        subject = f"Dein {offer.name} von {tenant_name}"
        body_text = (
            f"Hallo {contact.first_name},\n\n"
            f"{offer.confirmation_message}\n\n"
            f"Viele Grüße,\n{tenant_name}"
        )
        body_html = (
            f"<p>Hallo {contact.first_name},</p>"
            f"<p>{offer.confirmation_message}</p>"
            f"<p>Viele Grüße,<br>{tenant_name}</p>"
        )

        loop = asyncio.get_running_loop()
        if offer.attachment_url and offer.attachment_filename:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: mailer.send_html_mail_with_attachment(
                        contact.email,
                        subject,
                        body_html,
                        body_text,
                        offer.attachment_url,
                        offer.attachment_filename,
                    ),
                )
            except Exception as attach_err:
                logger.warning(
                    "offer_email.attachment_failed_fallback",
                    error=str(attach_err),
                    offer_slug=offer.slug,
                )
                # Fallback: send without attachment
                await loop.run_in_executor(
                    None,
                    lambda: mailer.send_html_mail(contact.email, subject, body_html, body_text),
                )
        else:
            await loop.run_in_executor(
                None,
                lambda: mailer.send_html_mail(contact.email, subject, body_html, body_text),
            )

        logger.info("offer_email.sent", tenant_id=tenant_id, offer_slug=offer.slug, to=contact.email)
    except Exception as e:
        logger.warning("offer_email.failed", error=str(e))


# ── Schemas ────────────────────────────────────────────────────────────────────


class SubscribeIn(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# SUBSCRIBE  (step 1 — stores pending, sends confirmation)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/subscribe/{token}")
async def subscribe_info(
    token: str, offer: Optional[str] = None, db: Session = Depends(get_db)
):
    """Return public context for the subscribe landing page."""
    tenant_id, campaign_id, channel = _decode_token(token)

    tenant = identity_queries.get_active_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    campaign_name: str | None = None
    description: str | None = None
    if campaign_id:
        campaign = campaign_queries.get_campaign_for_tenant(
            db,
            tenant_id=tenant_id,
            campaign_id=campaign_id,
        )
        if campaign:
            campaign_name = campaign.name
            description = campaign.description

    offer_name: str | None = None
    if offer:
        db_offer = campaign_queries.get_active_offer_for_tenant(
            db,
            tenant_id=tenant_id,
            slug=offer.lower(),
        )
        if db_offer:
            offer_name = db_offer.name

    return {
        "tenant_name": tenant.name,
        "campaign_name": campaign_name,
        "channel": channel,
        "description": description,
        "offer_name": offer_name,
    }


@router.post("/subscribe/{token}")
async def subscribe(
    token: str,
    body: SubscribeIn,
    request: Request,
    background_tasks: BackgroundTasks,
    offer: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Store pending subscription in Redis and send a double opt-in confirmation.

    No contact is created here. The contact is created only after the
    confirmation link is clicked (DSGVO-compliant double opt-in).
    """
    tenant_id, campaign_id, channel = _decode_token(token)

    tenant = identity_queries.get_active_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    offer_slug = offer.lower() if offer else ""

    # Resolve offer name for email copy
    offer_name: str | None = None
    if offer_slug:
        db_offer = campaign_queries.get_active_offer_for_tenant(
            db,
            tenant_id=tenant_id,
            slug=offer_slug,
        )
        if db_offer:
            offer_name = db_offer.name

    # Check for existing contact with same email
    if body.email:
        from app.core.contact_models import Contact
        existing = db.query(Contact).filter(
            Contact.tenant_id == tenant_id,
            Contact.email == str(body.email),
            Contact.deleted_at.is_(None),
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Diese E-Mail-Adresse ist bereits registriert.",
            )

    # Store pending subscription data in Redis (24 h TTL)
    pending_id = str(uuid.uuid4())
    redis_key = f"optin:pending:{tenant_id}:{pending_id}"
    pending_data = {
        "first_name": body.first_name,
        "last_name": body.last_name,
        "email": str(body.email) if body.email else None,
        "phone": body.phone,
        "tenant_id": tenant_id,
        "campaign_id": campaign_id,
        "channel": channel,
        "offer_slug": offer_slug,
        "ip_address": request.client.host if request.client else None,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        r = _get_redis()
        r.setex(redis_key, OPTIN_PENDING_TTL, json.dumps(pending_data))
        # Immediately verify the key was stored
        verify = r.get(redis_key)
        logger.info(
            "public_subscribe.redis_verify",
            key=redis_key,
            stored=verify is not None,
            ttl=r.ttl(redis_key),
        )
    except Exception as e:
        logger.error("public_subscribe.redis_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Temporärer Fehler, bitte erneut versuchen.")

    # Build confirmation URL
    confirm_token = _make_optin_confirm_token(tenant_id, pending_id, channel, offer_slug)
    origin = request.headers.get("origin", "")
    if not origin:
        referer = request.headers.get("referer", "")
        origin = "/".join(referer.split("/")[:3]) if referer else ""
    confirm_url = f"{origin}/optin-confirm/{confirm_token}"

    # Send confirmation
    if body.email:
        background_tasks.add_task(
            _send_optin_email_sync,
            tenant_id=tenant_id,
            to_email=str(body.email),
            first_name=body.first_name,
            tenant_name=tenant.name,
            confirm_url=confirm_url,
            offer_name=offer_name,
        )
        confirmation_method = "email"
    elif body.phone and channel in ("whatsapp", "sms"):
        background_tasks.add_task(
            _send_whatsapp_optin_request_sync,
            phone=body.phone,
            first_name=body.first_name,
            tenant_name=tenant.name,
        )
        confirmation_method = "whatsapp"
    else:
        confirmation_method = "none"

    logger.info(
        "public_subscribe.pending_stored",
        tenant_id=tenant_id,
        pending_id=pending_id,
        offer=offer_slug,
        method=confirmation_method,
    )
    return {
        "status": "pending",
        "message": (
            "Bitte bestätige deine Anmeldung über den Link in deiner E-Mail."
            if body.email
            else "Bitte bestätige deine Anmeldung."
        ),
        "confirmation_sent": confirmation_method != "none",
    }


# ══════════════════════════════════════════════════════════════════════════════
# OPTIN CONFIRM  (step 2 — create contact, confirm consent, deliver offer)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/optin-confirm/{token}")
async def optin_confirm(token: str, db: Session = Depends(get_db)):
    """Confirm double opt-in when user clicks the email link.

    - Reads pending data from Redis
    - Creates the contact
    - Records confirmed consent (double_optin)
    - Delivers the offer (email with attachment or WhatsApp)
    - Deletes the pending Redis key (one-time use)
    """
    tenant_id, pending_id, channel, offer_slug = _decode_optin_confirm_token(token)

    tenant = identity_queries.get_active_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    # Load pending data from Redis
    redis_key = f"optin:pending:{tenant_id}:{pending_id}"
    try:
        r = _get_redis()
        raw = r.get(redis_key)
        all_keys = r.keys("optin:pending:*")
        logger.info(
            "optin_confirm.redis_lookup",
            key=redis_key,
            found=raw is not None,
            all_pending_keys=all_keys,
        )
    except Exception as e:
        logger.error("optin_confirm.redis_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Temporärer Fehler.")

    if not raw:
        raise HTTPException(
            status_code=410,
            detail="Dieser Bestätigungslink ist abgelaufen oder wurde bereits verwendet.",
        )

    try:
        pending = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige Daten.")

    # NOTE: Redis key is deleted AFTER successful DB commit below (not here)
    # so that a failed DB write doesn't permanently invalidate the link.

    from app.core.contact_models import Contact

    # Create or update contact
    existing_contact = db.query(Contact).filter(
        Contact.tenant_id == tenant_id,
        Contact.email == pending.get("email"),
        Contact.deleted_at.is_(None),
    ).first() if pending.get("email") else None

    if existing_contact:
        existing_contact.first_name = pending["first_name"]
        existing_contact.last_name = pending["last_name"]
        if pending.get("phone"):
            existing_contact.phone = pending["phone"]
        contact = existing_contact
    else:
        contact = Contact(
            tenant_id=tenant_id,
            first_name=pending["first_name"],
            last_name=pending["last_name"],
            email=pending.get("email"),
            phone=pending.get("phone"),
            source="subscribe_form",
            lifecycle_stage="subscriber",
        )
        db.add(contact)
        db.flush()

    # Record confirmed DSGVO consent
    now = datetime.now(timezone.utc)
    existing_consent = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == tenant_id,
        ContactConsent.contact_id == contact.id,
        ContactConsent.channel == channel,
    ).first()

    if existing_consent:
        existing_consent.consent_given = True
        existing_consent.given_at = now
        existing_consent.revoked_at = None
        existing_consent.consent_source = "double_optin"
        existing_consent.ip_address = pending.get("ip_address")
    else:
        db.add(ContactConsent(
            tenant_id=tenant_id,
            contact_id=contact.id,
            channel=channel,
            consent_given=True,
            given_at=now,
            consent_source="double_optin",
            ip_address=pending.get("ip_address"),
        ))

    # Create CampaignRecipient if campaign was specified
    campaign_id = pending.get("campaign_id", 0)
    if campaign_id:
        try:
            campaign = campaign_queries.get_campaign_for_tenant(
                db,
                tenant_id=tenant_id,
                campaign_id=campaign_id,
            )
            if campaign:
                recipient = CampaignRecipient(
                    campaign_id=campaign.id,
                    tenant_id=tenant_id,
                    contact_id=contact.id,
                    channel=channel,
                    status="confirmed",
                    offer_slug=offer_slug or None,
                )
                db.add(recipient)
        except Exception as exc:
            logger.warning("optin_confirm.campaign_recipient_failed", error=str(exc))

    db.commit()
    db.refresh(contact)

    # Delete Redis key only after successful commit (allows retry on DB failure)
    try:
        r.delete(redis_key)
    except Exception:
        pass

    # Deliver offer content
    offer_name: str | None = None
    if offer_slug:
        db_offer = campaign_queries.get_active_offer_for_tenant(
            db,
            tenant_id=tenant_id,
            slug=offer_slug,
        )
        if db_offer:
            offer_name = db_offer.name
            if contact.email:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    _deliver_offer_email(
                        tenant_id=tenant_id,
                        contact=contact,
                        offer=db_offer,
                        tenant_name=tenant.name,
                    )
                )
            elif contact.phone and channel in ("whatsapp", "sms"):
                from app.campaign_engine.reply_handler import _send_offer_confirmation
                try:
                    await _send_offer_confirmation(
                        db=db,
                        tenant_id=tenant_id,
                        contact_id=contact.id,
                        channel=channel,
                        offer_slug=offer_slug,
                    )
                except Exception as e:
                    logger.warning("optin_confirm.offer_dispatch_failed", error=str(e))

    logger.info(
        "optin_confirm.success",
        tenant_id=tenant_id,
        contact_id=contact.id,
        channel=channel,
        offer=offer_slug,
    )
    return {
        "status": "confirmed",
        "tenant_name": tenant.name,
        "first_name": contact.first_name,
        "offer_name": offer_name,
    }


# ══════════════════════════════════════════════════════════════════════════════
# UNSUBSCRIBE
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/unsubscribe/{token}")
async def unsubscribe_info(token: str, db: Session = Depends(get_db)):
    """Return context for the unsubscribe landing page."""
    tenant_id, contact_id, channel = _decode_token(token)

    tenant = identity_queries.get_active_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    return {
        "tenant_name": tenant.name,
        "channel": channel,
    }


@router.post("/unsubscribe/{token}")
async def unsubscribe(token: str, db: Session = Depends(get_db)):
    """Revoke consent for a contact via a tokenized unsubscribe link."""
    tenant_id, contact_id, channel = _decode_token(token)

    tenant = identity_queries.get_active_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Unbekannter Anbieter.")

    now = datetime.now(timezone.utc)
    consents = db.query(ContactConsent).filter(
        ContactConsent.tenant_id == tenant_id,
        ContactConsent.contact_id == contact_id,
        ContactConsent.channel == channel,
        ContactConsent.consent_given.is_(True),
    ).all()

    for c in consents:
        c.consent_given = False
        c.revoked_at = now

    db.commit()

    logger.info(
        "public_unsubscribe.success",
        tenant_id=tenant_id,
        contact_id=contact_id,
        channel=channel,
    )
    return {"status": "ok", "message": "Erfolgreich abgemeldet."}


# ── Helper: generate an unsubscribe token for a contact ───────────────────────

def make_unsubscribe_token(tenant_id: int, contact_id: int, channel: str) -> str:
    return _encode_token(tenant_id, contact_id, channel)
