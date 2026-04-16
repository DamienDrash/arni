"""ARIIA Campaign Worker Tasks.

Start with:
    python -m app.worker.main --worker campaign
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import structlog
from app.domains.campaigns.models import Campaign, CampaignRecipient, CampaignVariant
from app.domains.support.models import ScheduledFollowUp
from app.shared.db import open_session

logger = structlog.get_logger()


# ── Send ────────────────────────────────────────────────────────────────────


async def send_campaign_batch(
    ctx: dict,
    campaign_id: int,
    tenant_id: int,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Dequeue and send a batch of campaign messages from campaign:send_queue."""
    from app.core.contact_models import Contact
    from app.campaign_engine.renderer import MessageRenderer

    redis = ctx["redis"]
    sent = 0
    failed = 0
    renderer = MessageRenderer()

    for _ in range(batch_size):
        raw = await redis.lpop("campaign:send_queue")
        if raw is None:
            break

        try:
            job = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("campaign.send.invalid_job", raw=str(raw)[:200], tenant_id=tenant_id)
            failed += 1
            continue

        job_campaign_id = job.get("campaign_id")
        job_tenant_id = job.get("tenant_id", tenant_id)
        recipient_id = job.get("recipient_id")
        contact_id = job.get("contact_id")

        db = open_session()
        try:
            # Load campaign, recipient, contact
            campaign = db.query(Campaign).filter(Campaign.id == job_campaign_id).first()
            recipient = (
                db.query(CampaignRecipient)
                .filter(CampaignRecipient.id == recipient_id)
                .first()
            ) if recipient_id else None
            contact = db.query(Contact).filter(
                Contact.id == contact_id,
                Contact.tenant_id == job_tenant_id,
            ).first() if contact_id else None

            if not campaign or not contact:
                logger.warning(
                    "campaign.send.missing_data",
                    campaign_id=job_campaign_id,
                    contact_id=contact_id,
                    tenant_id=job_tenant_id,
                    has_campaign=campaign is not None,
                    has_contact=contact is not None,
                )
                failed += 1
                if recipient:
                    recipient.status = "failed"
                    recipient.error_message = "Campaign or contact not found"
                    db.commit()
                continue

            # Tenant isolation check
            if campaign.tenant_id != job_tenant_id:
                logger.error(
                    "campaign.send.tenant_mismatch",
                    campaign_tenant=campaign.tenant_id,
                    job_tenant=job_tenant_id,
                )
                failed += 1
                continue

            # Render message
            rendered = await renderer.render(
                db, campaign, contact, recipient_id=recipient_id,
            )

            # Dispatch by channel
            if campaign.channel == "email":
                await _dispatch_email(db, campaign, contact, rendered, job_tenant_id)
            elif campaign.channel in ("whatsapp", "telegram", "sms"):
                await _dispatch_messaging(campaign, contact, rendered)
            else:
                logger.warning(
                    "campaign.send.unknown_channel",
                    channel=campaign.channel,
                    campaign_id=campaign.id,
                )

            # Mark as sent
            if recipient:
                recipient.status = "sent"
                recipient.sent_at = datetime.now(timezone.utc)
                db.commit()

            # Publish analytics event
            await redis.xadd("campaign:analytics_events", {
                "event_type": "sent",
                "campaign_id": str(job_campaign_id),
                "recipient_id": str(recipient_id or ""),
                "tenant_id": str(job_tenant_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            sent += 1

        except Exception as exc:
            db.rollback()
            failed += 1
            logger.error(
                "campaign.send.job_failed",
                campaign_id=job_campaign_id,
                recipient_id=recipient_id,
                tenant_id=job_tenant_id,
                error=str(exc),
            )
            if recipient_id:
                try:
                    recipient = (
                        db.query(CampaignRecipient)
                        .filter(CampaignRecipient.id == recipient_id)
                        .first()
                    )
                    if recipient:
                        recipient.status = "failed"
                        recipient.error_message = str(exc)[:500]
                        db.commit()
                except Exception:
                    db.rollback()
        finally:
            db.close()

    logger.info(
        "campaign.send.batch_complete",
        campaign_id=campaign_id,
        tenant_id=tenant_id,
        sent=sent,
        failed=failed,
    )
    return {"status": "ok", "campaign_id": campaign_id, "sent": sent, "failed": failed}


async def _dispatch_email(db, campaign, contact, rendered, tenant_id: int) -> None:
    """Send an email via tenant-configured SMTP. Falls back to stub mode if unconfigured."""
    from app.core.integration_models import get_integration_config
    from app.integrations.email import SMTPMailer

    config = get_integration_config(tenant_id, "smtp_email")
    if not config or not config.get("host"):
        logger.warning(
            "campaign.send.smtp_not_configured",
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            msg="Stub mode: marking as sent without actual delivery",
        )
        return

    mailer = SMTPMailer(
        host=config["host"],
        port=int(config.get("port", 587)),
        username=config.get("username", ""),
        password=config.get("password", ""),
        from_email=config.get("from_email") or config.get("username", ""),
        from_name=config.get("from_name", "ARIIA"),
        use_starttls=config.get("use_starttls", True),
    )

    if getattr(campaign, "attachment_url", None) and campaign.attachment_url:
        mailer.send_html_mail_with_attachment(
            to_email=contact.email,
            subject=rendered.subject,
            body_html=rendered.body_html,
            body_text=rendered.body_text,
            attachment_url=campaign.attachment_url,
            attachment_filename=getattr(campaign, "attachment_filename", None) or "attachment.pdf",
        )
    else:
        mailer.send_html_mail(
            to_email=contact.email,
            subject=rendered.subject,
            body_html=rendered.body_html,
            body_text=rendered.body_text,
        )


async def _dispatch_messaging(campaign, contact, rendered) -> None:
    """Send via WhatsApp/Telegram/SMS. Falls back to stub mode if unconfigured."""
    import os

    if campaign.channel == "whatsapp":
        from app.integrations.whatsapp import WhatsAppClient

        waha_url = os.environ.get("WAHA_API_URL")
        waha_key = os.environ.get("WAHA_API_KEY")
        wa_token = os.environ.get("WA_ACCESS_TOKEN", "")
        wa_phone_id = os.environ.get("WA_PHONE_NUMBER_ID", "")

        if not waha_url and not wa_token:
            logger.warning(
                "campaign.send.whatsapp_not_configured",
                campaign_id=campaign.id,
                msg="Stub mode: no WhatsApp credentials",
            )
            return

        client = WhatsAppClient(
            access_token=wa_token,
            phone_number_id=wa_phone_id,
            waha_api_url=waha_url,
            waha_api_key=waha_key,
        )

        if not contact.phone:
            raise ValueError(f"Contact {contact.id} has no phone number")

        await client.send_text(to=contact.phone, body=rendered.body_text)
    else:
        logger.warning(
            "campaign.send.channel_not_implemented",
            channel=campaign.channel,
            campaign_id=campaign.id,
        )


# ── Scheduler ───────────────────────────────────────────────────────────────


async def tick_campaign_scheduler(ctx: dict) -> dict[str, Any]:
    """Cron task: check for campaigns scheduled to run now, transition and enqueue."""
    db = open_session()
    enqueued = 0
    try:
        now = datetime.now(timezone.utc)
        due = (
            db.query(Campaign)
            .filter(Campaign.status == "scheduled", Campaign.scheduled_at <= now)
            .all()
        )

        for campaign in due:
            campaign.status = "sending"
            db.commit()

            logger.info(
                "campaign.scheduler.enqueued",
                campaign_id=campaign.id,
                tenant_id=campaign.tenant_id,
            )

            await ctx["redis"].enqueue_job(
                "send_campaign_batch",
                campaign_id=campaign.id,
                tenant_id=campaign.tenant_id,
            )
            enqueued += 1

    except Exception as exc:
        db.rollback()
        logger.error("campaign.scheduler.error", error=str(exc))
    finally:
        db.close()

    return {"status": "ok", "enqueued": enqueued}


# ── Analytics ───────────────────────────────────────────────────────────────


async def aggregate_analytics_events(ctx: dict) -> dict[str, Any]:
    """Cron task: consume campaign:analytics_events Redis stream, write to DB."""
    redis = ctx["redis"]
    cursor_key = "ariia:campaign:analytics:cursor"
    stream_key = "campaign:analytics_events"
    processed = 0

    try:
        last_id = await redis.get(cursor_key) or "0"
        if isinstance(last_id, bytes):
            last_id = last_id.decode()

        results = await redis.xread({stream_key: last_id}, count=100)
        if not results:
            return {"status": "ok", "processed": 0}

        db = open_session()
        try:
            for stream_name, messages in results:
                for msg_id, fields in messages:
                    if isinstance(msg_id, bytes):
                        msg_id = msg_id.decode()

                    # Decode bytes fields if needed
                    decoded = {}
                    for k, v in fields.items():
                        key = k.decode() if isinstance(k, bytes) else k
                        val = v.decode() if isinstance(v, bytes) else v
                        decoded[key] = val

                    event_type = decoded.get("event_type")
                    recipient_id = decoded.get("recipient_id")

                    if recipient_id and event_type:
                        try:
                            rid = int(recipient_id)
                        except (ValueError, TypeError):
                            rid = None

                        if rid:
                            recipient = (
                                db.query(CampaignRecipient)
                                .filter(CampaignRecipient.id == rid)
                                .first()
                            )
                            if recipient:
                                now = datetime.now(timezone.utc)
                                if event_type == "delivered" and not recipient.delivered_at:
                                    recipient.delivered_at = now
                                elif event_type == "opened" and not recipient.opened_at:
                                    recipient.opened_at = now
                                elif event_type == "clicked" and not recipient.clicked_at:
                                    recipient.clicked_at = now
                                elif event_type == "bounced":
                                    recipient.status = "bounced"

                    processed += 1
                    last_id = msg_id

            db.commit()
            await redis.set(cursor_key, last_id)

        except Exception as exc:
            db.rollback()
            logger.error("campaign.analytics.db_error", error=str(exc))
        finally:
            db.close()

    except Exception as exc:
        logger.error("campaign.analytics.stream_error", error=str(exc))

    return {"status": "ok", "processed": processed}


# ── A/B Testing ─────────────────────────────────────────────────────────────


async def evaluate_ab_tests(ctx: dict) -> dict[str, Any]:
    """Cron task: run Z-test on A/B variants with enough samples, declare winner."""
    db = open_session()
    evaluated = 0
    try:
        # Find A/B campaigns that are sending/sent with no winner yet
        ab_campaigns = (
            db.query(Campaign)
            .filter(
                Campaign.is_ab_test.is_(True),
                Campaign.ab_winner_variant.is_(None),
                Campaign.status.in_(["sending", "sent"]),
            )
            .all()
        )

        for campaign in ab_campaigns:
            variants = (
                db.query(CampaignVariant)
                .filter(
                    CampaignVariant.campaign_id == campaign.id,
                    CampaignVariant.is_winner.is_(False),
                )
                .all()
            )

            if len(variants) < 2:
                continue

            # Check minimum sample size
            if any(v.stats_sent < 100 for v in variants):
                continue

            # Run Z-test on open rates
            try:
                from scipy.stats import proportions_ztest
            except ImportError:
                logger.warning("campaign.ab_test.scipy_unavailable")
                break

            counts = [v.stats_opened for v in variants]
            nobs = [v.stats_sent for v in variants]

            try:
                _, p_value = proportions_ztest(counts, nobs)
            except Exception as exc:
                logger.warning(
                    "campaign.ab_test.ztest_failed",
                    campaign_id=campaign.id,
                    error=str(exc),
                )
                continue

            if p_value < 0.05:
                # Find best variant by open rate
                best = max(variants, key=lambda v: (v.stats_opened / v.stats_sent) if v.stats_sent > 0 else 0)
                best.is_winner = True
                best.winner_selected_at = datetime.now(timezone.utc)
                best.winner_metric = campaign.ab_test_metric or "open_rate"
                best.confidence_level = 1.0 - p_value

                campaign.ab_winner_variant = best.variant_name
                db.commit()

                logger.info(
                    "campaign.ab_test.winner_declared",
                    campaign_id=campaign.id,
                    tenant_id=campaign.tenant_id,
                    winner=best.variant_name,
                    p_value=round(p_value, 4),
                )
                evaluated += 1

    except Exception as exc:
        db.rollback()
        logger.error("campaign.ab_test.error", error=str(exc))
    finally:
        db.close()

    return {"status": "ok", "evaluated": evaluated}


# ── Follow-Ups ──────────────────────────────────────────────────────────────


async def process_follow_ups(ctx: dict) -> dict[str, Any]:
    """Cron task: dispatch scheduled follow-up messages that are due."""
    db = open_session()
    dispatched = 0
    try:
        now = datetime.now(timezone.utc)
        due = (
            db.query(ScheduledFollowUp)
            .filter(
                ScheduledFollowUp.follow_up_at <= now,
                ScheduledFollowUp.status == "pending",
            )
            .all()
        )

        for follow_up in due:
            try:
                from app.campaign_engine.send_queue import enqueue_send_job

                enqueue_send_job(
                    campaign_id=0,
                    recipient_id=follow_up.id,
                    contact_id=follow_up.member_id or 0,
                    tenant_id=follow_up.tenant_id,
                    channel=follow_up.channel or "whatsapp",
                )

                follow_up.status = "sent"
                follow_up.sent_at = datetime.now(timezone.utc)
                dispatched += 1

                logger.info(
                    "campaign.follow_up.dispatched",
                    follow_up_id=follow_up.id,
                    tenant_id=follow_up.tenant_id,
                )

            except Exception as exc:
                follow_up.status = "failed"
                follow_up.error_message = str(exc)[:500]
                logger.error(
                    "campaign.follow_up.failed",
                    follow_up_id=follow_up.id,
                    tenant_id=follow_up.tenant_id,
                    error=str(exc),
                )

        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error("campaign.follow_ups.error", error=str(exc))
    finally:
        db.close()

    return {"status": "ok", "dispatched": dispatched}


# ── arq WorkerSettings ──────────────────────────────────────────────────────


class CampaignWorkerSettings:
    """arq WorkerSettings for the campaign worker process."""

    try:
        from app.worker.settings import get_worker_redis_settings as _grs
        redis_settings = _grs()
        del _grs
    except Exception:
        from arq.connections import RedisSettings
        redis_settings = RedisSettings()

    functions = [
        send_campaign_batch,
        tick_campaign_scheduler,
        aggregate_analytics_events,
        evaluate_ab_tests,
        process_follow_ups,
    ]

    cron_jobs = None  # Set below after imports

    max_jobs = 50
    job_timeout = 300
    keep_result = 3600

    @classmethod
    def _build_cron_jobs(cls):
        from arq import cron
        return [
            cron(tick_campaign_scheduler, second={0}),             # every 60s
            cron(aggregate_analytics_events, second={0, 30}),      # every 30s
            cron(evaluate_ab_tests, second={0}, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),  # every 5min
            cron(process_follow_ups, second={0}),                  # every 60s
        ]


# Eagerly build cron_jobs so arq picks them up
try:
    CampaignWorkerSettings.cron_jobs = CampaignWorkerSettings._build_cron_jobs()
except Exception:
    logger.warning("campaign.worker.cron_init_deferred")
