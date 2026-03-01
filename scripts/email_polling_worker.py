"""
ARIIA Email Polling Worker
Polls IMAP servers for new emails and injects them into the ARIIA pipeline.
"""
import asyncio
import imaplib
import email
from email.header import decode_header
import structlog
from datetime import datetime, timezone
import time

from app.gateway.persistence import persistence
from app.gateway.dependencies import redis_bus
from app.gateway.redis_bus import RedisBus
from app.gateway.routers.webhooks import save_inbound_to_db, process_and_reply
from app.gateway.utils import broadcast_to_admins
from app.gateway.schemas import InboundMessage, Platform

logger = structlog.get_logger()

async def poll_tenant_emails(tenant_id: int, slug: str):
    """Poll emails for a specific tenant."""
    # Priority 1: Connector Hub settings (standardized prefix)
    cid = "smtp_email"
    imap_host = persistence.get_setting(f"integration_{cid}_{tenant_id}_imap_host", tenant_id=tenant_id)
    imap_port_raw = persistence.get_setting(f"integration_{cid}_{tenant_id}_imap_port", tenant_id=tenant_id)
    
    # Priority 2: Legacy / Derived from SMTP
    if not imap_host:
        smtp_host = persistence.get_setting("smtp_host", "imap.strato.de", tenant_id=tenant_id)
        if smtp_host and "smtp." in smtp_host:
            imap_host = smtp_host.replace("smtp.", "imap.")
        else:
            imap_host = smtp_host or "imap.strato.de"
            
    user = persistence.get_setting(f"integration_{cid}_{tenant_id}_username", tenant_id=tenant_id)
    if not user:
        user = persistence.get_setting("smtp_username", tenant_id=tenant_id)
        
    pw = persistence.get_setting(f"integration_{cid}_{tenant_id}_password", tenant_id=tenant_id)
    if not pw:
        pw = persistence.get_setting("smtp_password", tenant_id=tenant_id)
    
    if not all([imap_host, user, pw]):
        return

    port = int(imap_port_raw or "993")

    try:
        def _fetch_mails():
            new_messages = []
            try:
                mail = imaplib.IMAP4_SSL(imap_host, port)
                mail.login(user, pw)
                mail.select("INBOX")
                
                # Search for unread messages
                status, messages = mail.search(None, "UNSEEN")
                if status != "OK":
                    return []
                
                for msg_num in messages[0].split():
                    status, data = mail.fetch(msg_num, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Extract info
                    subject_raw = msg.get("Subject", "(Kein Betreff)")
                    subject, encoding = decode_header(subject_raw)[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8")
                    
                    from_ = msg.get("From", "unbekannt@sender.de")
                    msg_id = msg.get("Message-ID", f"imap-{time.time()}")
                    
                    # Get body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode()
                                    break
                                except Exception:
                                    continue
                    else:
                        body = msg.get_payload(decode=True).decode()
                    
                    if not body:
                        body = "(Leere E-Mail oder nur HTML)"

                    new_messages.append({
                        "from": from_,
                        "subject": subject,
                        "body": body,
                        "id": msg_id
                    })
                    
                    # Mark as seen
                    mail.store(msg_num, "+FLAGS", "\\Seen")
                
                mail.logout()
            except Exception as e:
                logger.error("email.poll_failed", error=str(e), tenant=slug)
            return new_messages

        new_mails = await asyncio.to_thread(_fetch_mails)
        
        for m in new_mails:
            logger.info("email.new_message_polled", sender=m["from"], subject=m["subject"], tenant=slug)
            
            clean_sender = m["from"]
            if "<" in clean_sender:
                clean_sender = clean_sender.split("<")[1].split(">")[0]

            inbound = InboundMessage(
                message_id=m["id"],
                platform=Platform.EMAIL,
                user_id=clean_sender,
                content=m["body"],
                content_type="text",
                metadata={"subject": m["subject"], "source": "imap_polling"},
                tenant_id=tenant_id,
            )

            # 1. Save to DB
            await save_inbound_to_db(inbound)
            
            # 2. Broadcast to UI
            await broadcast_to_admins({
                "type": "ghost.message_in",
                "user_id": clean_sender,
                "tenant_id": tenant_id,
                "platform": "email",
                "content": m["body"],
                "message_id": m["id"]
            }, tenant_id=tenant_id)
            
            # 3. Trigger AI
            asyncio.create_task(process_and_reply(inbound))

    except Exception as e:
        logger.error("email.poll_critical_error", error=str(e), tenant=slug)

async def main():
    logger.info("email_worker.started")
    while True:
        try:
            # Dynamically fetch all tenants that have email integration configured
            from app.core.db import SessionLocal
            from app.core.models import Tenant, Setting
            
            db = SessionLocal()
            try:
                # Find all tenants that have an IMAP host set in their connector config
                cid = "smtp_email"
                active_configs = db.query(Setting).filter(
                    Setting.key.like(f"integration_{cid}_%_imap_host")
                ).all()
                
                # Extract unique tenant IDs from keys like 'integration_smtp_email_2_imap_host'
                tenant_ids = set()
                for s in active_configs:
                    parts = s.key.split("_")
                    if len(parts) >= 4 and parts[3].isdigit():
                        tenant_ids.add(int(parts[3]))
                
                if not tenant_ids:
                    logger.debug("email_worker.no_active_configs")
                
                for tid in tenant_ids:
                    # Get slug for logging
                    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
                    if tenant:
                        await poll_tenant_emails(tid, tenant.slug)
            finally:
                db.close()
                
            await asyncio.sleep(30)
        except Exception as e:
            logger.error("email_worker.loop_error", error=str(e))
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
