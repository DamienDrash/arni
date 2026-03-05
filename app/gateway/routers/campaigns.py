"""app/gateway/routers/campaigns.py — Gold Standard Campaign Management API.

Provides endpoints for:
- Campaign CRUD (create, list, update, delete)
- Template management
- AI content generation
- Preview & approval workflow
- Campaign scheduling & sending
- Segment management
- Follow-up scheduling
- Campaign analytics
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user
from app.core.models import (
    Campaign, CampaignTemplate, CampaignVariant, CampaignRecipient,
    MemberSegment, ScheduledFollowUp, ChatMessage, ChatSession,
    Tenant,
)
from app.core.contact_models import Contact, ContactTagAssociation, ContactTag

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/campaigns", tags=["campaigns"])


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = "broadcast"
    channel: str = "email"
    target_type: str = "all_members"
    target_filter_json: Optional[str] = None
    target_value: Optional[str] = None  # Convenience: auto-converts to target_filter_json
    template_id: Optional[int] = None
    content_subject: Optional[str] = None
    content_body: Optional[str] = None
    content_html: Optional[str] = None
    ai_prompt: Optional[str] = None
    scheduled_at: Optional[str] = None
    is_ab_test: bool = False


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    channel: Optional[str] = None
    target_type: Optional[str] = None
    target_filter_json: Optional[str] = None
    template_id: Optional[int] = None
    content_subject: Optional[str] = None
    content_body: Optional[str] = None
    content_html: Optional[str] = None
    ai_prompt: Optional[str] = None
    scheduled_at: Optional[str] = None
    status: Optional[str] = None


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = "email"
    header_html: Optional[str] = None
    footer_html: Optional[str] = None
    body_template: Optional[str] = None
    variables_json: Optional[str] = None
    primary_color: Optional[str] = "#6C5CE7"
    logo_url: Optional[str] = None


class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    filter_json: Optional[str] = None
    is_dynamic: bool = True


class FollowUpCreate(BaseModel):
    contact_id: Optional[int] = None
    member_id: Optional[int] = None  # Legacy alias for contact_id
    conversation_id: Optional[str] = None
    reason: Optional[str] = None
    follow_up_at: str
    message_template: Optional[str] = None
    channel: str = "whatsapp"


class AIGenerateRequest(BaseModel):
    campaign_id: int
    prompt: str
    use_knowledge: bool = True
    use_chat_history: bool = False
    tone: str = "professional"  # professional | casual | motivational | urgent


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN CRUD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("")
async def list_campaigns(
    status: Optional[str] = None,
    type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all campaigns for the tenant."""
    q = db.query(Campaign).filter(Campaign.tenant_id == user.tenant_id)
    if status:
        q = q.filter(Campaign.status == status)
    if type:
        q = q.filter(Campaign.type == type)

    total = q.count()
    campaigns = q.order_by(desc(Campaign.created_at)).offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [_campaign_to_dict(c) for c in campaigns],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


@router.post("")
async def create_campaign(
    body: CampaignCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new campaign."""
    # Auto-convert target_value convenience field to target_filter_json
    filter_json = body.target_filter_json
    if not filter_json and body.target_value:
        if body.target_type in ("tag", "tags"):
            filter_json = json.dumps({"tags": [body.target_value]})
        elif body.target_type == "lifecycle":
            filter_json = json.dumps({"lifecycle_stage": body.target_value})
        elif body.target_type == "segment":
            filter_json = json.dumps({"segment_id": body.target_value})
        elif body.target_type == "selected":
            # Comma-separated IDs
            filter_json = json.dumps({"contact_ids": [int(x.strip()) for x in body.target_value.split(",") if x.strip()]})

    campaign = Campaign(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        type=body.type,
        channel=body.channel,
        target_type=body.target_type,
        target_filter_json=filter_json,
        template_id=body.template_id,
        content_subject=body.content_subject,
        content_body=body.content_body,
        content_html=body.content_html,
        ai_prompt=body.ai_prompt,
        is_ab_test=body.is_ab_test,
        status="draft",
        preview_token=str(uuid.uuid4()),
        preview_expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        created_by=user.user_id,
    )
    if body.scheduled_at:
        try:
            campaign.scheduled_at = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
            campaign.status = "scheduled"
        except ValueError:
            pass

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    logger.info("campaign.created", campaign_id=campaign.id, tenant_id=user.tenant_id)
    return _campaign_to_dict(campaign)


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get campaign details."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result = _campaign_to_dict(campaign)

    # Include recipients count
    result["recipients_count"] = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == campaign_id
    ).count()

    # Include variants if A/B test
    if campaign.is_ab_test:
        variants = db.query(CampaignVariant).filter(
            CampaignVariant.campaign_id == campaign_id
        ).all()
        result["variants"] = [
            {
                "id": v.id,
                "variant_name": v.variant_name,
                "content_subject": v.content_subject,
                "content_body": v.content_body,
                "percentage": v.percentage,
                "stats_sent": v.stats_sent,
                "stats_opened": v.stats_opened,
                "stats_clicked": v.stats_clicked,
            }
            for v in variants
        ]

    return result


@router.put("/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    body: CampaignUpdate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a campaign."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status in ("sending", "sent"):
        raise HTTPException(status_code=400, detail="Cannot edit a campaign that is sending or already sent")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "scheduled_at" and value:
            try:
                setattr(campaign, field, datetime.fromisoformat(value.replace("Z", "+00:00")))
            except ValueError:
                pass
        else:
            setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return _campaign_to_dict(campaign)


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a campaign."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status in ("sending",):
        raise HTTPException(status_code=400, detail="Cannot delete a campaign that is currently sending")

    # Delete recipients and variants
    db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id).delete()
    db.query(CampaignVariant).filter(CampaignVariant.campaign_id == campaign_id).delete()
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# AI CONTENT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/ai-generate")
async def ai_generate_content(
    body: AIGenerateRequest,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate campaign content using AI agent."""
    campaign = db.query(Campaign).filter(
        Campaign.id == body.campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Build context for AI
    context_parts = [f"Campaign: {campaign.name}", f"Channel: {campaign.channel}"]

    # Get member context if targeting specific members
    if campaign.target_type != "all_members" and campaign.target_filter_json:
        try:
            filters = json.loads(campaign.target_filter_json)
            member_count = db.query(Contact).filter(
                Contact.tenant_id == user.tenant_id,
                Contact.deleted_at.is_(None),
            ).count()
            context_parts.append(f"Target audience: {member_count} members")
        except (json.JSONDecodeError, TypeError):
            pass

    # Get knowledge base context via semantic search in ChromaDB
    knowledge_context = ""
    if body.use_knowledge:
        try:
            from app.knowledge.knowledge_manager import KnowledgeManager
            km = KnowledgeManager()
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_slug = tenant.slug if tenant else "default"
            search_results = await km.search(
                query=body.prompt,
                tenant_slug=tenant_slug,
                n_results=5,
                include_shared=True,
            )
            if search_results.has_results:
                knowledge_context = search_results.to_context_string(max_results=5)
                context_parts.append(f"Relevante Informationen aus der Wissensbasis:\n{knowledge_context}")
        except Exception as e:
            logger.warning("campaign.knowledge_search_failed", error=str(e))

    # Get chat history context if requested
    chat_context = ""
    if body.use_chat_history:
        recent_messages = db.query(ChatMessage).filter(
            ChatMessage.tenant_id == user.tenant_id,
            ChatMessage.role == "user",
        ).order_by(desc(ChatMessage.created_at)).limit(20).all()
        if recent_messages:
            topics = set()
            for msg in recent_messages:
                if msg.content and len(msg.content) > 10:
                    topics.add(msg.content[:100])
            if topics:
                chat_context = "Recent member topics: " + "; ".join(list(topics)[:5])
                context_parts.append(chat_context)

    # Build AI prompt
    tone_map = {
        "professional": "professionell und seriös",
        "casual": "locker und freundlich",
        "motivational": "motivierend und energiegeladen",
        "urgent": "dringend und handlungsorientiert",
    }
    tone_desc = tone_map.get(body.tone, "professionell")

    channel_format = {
        "email": "Erstelle eine E-Mail mit Betreff und Inhalt. Verwende HTML-Formatierung für den Body.",
        "whatsapp": "Erstelle eine kurze WhatsApp-Nachricht (max 1000 Zeichen). Verwende Emojis sparsam.",
        "telegram": "Erstelle eine Telegram-Nachricht. Markdown-Formatierung ist erlaubt.",
        "sms": "Erstelle eine SMS (max 160 Zeichen). Kurz und prägnant.",
    }
    format_instruction = channel_format.get(campaign.channel, channel_format["email"])

    system_prompt = f"""Du bist ein erfahrener Marketing-Experte und Content Creator.
Dein Ton ist {tone_desc}.
{format_instruction}

KONTEXT DES UNTERNEHMENS:
{chr(10).join(context_parts)}

WICHTIGE REGELN:
1. Nutze die Informationen aus der Wissensbasis als primäre Quelle für Fakten, Preise, Angebote und Details.
2. Erfinde KEINE Fakten, Preise oder Angebote, die nicht in der Wissensbasis stehen.
3. Verwende Platzhalter wie {{{{contact.first_name}}}}, {{{{contact.company}}}} für Personalisierung.
4. Der Inhalt muss zum Kanal passen ({campaign.channel}).
5. Antworte im JSON-Format: {{"subject": "...", "body": "...", "html": "..."}}
6. Für WhatsApp/SMS/Telegram: "html" kann leer sein.
7. Schreibe den Inhalt auf Deutsch, es sei denn, der Prompt verlangt eine andere Sprache.
"""

    try:
        from app.swarm.llm import LLMClient
        from config.settings import get_settings
        settings = get_settings()
        llm = LLMClient(openai_api_key=settings.openai_api_key)

        response = await llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": body.prompt},
            ],
            tenant_id=user.tenant_id,
            temperature=0.7,
            max_tokens=2000,
        )

        # Try to parse JSON response
        try:
            # Find JSON in response
            import re
            json_match = re.search(r'\{[^{}]*"subject"[^{}]*\}', response, re.DOTALL)
            if json_match:
                generated = json.loads(json_match.group())
            else:
                generated = {"subject": "", "body": response, "html": ""}
        except (json.JSONDecodeError, TypeError):
            generated = {"subject": "", "body": response, "html": ""}

        # Update campaign
        campaign.ai_generated_content = json.dumps(generated, ensure_ascii=False)
        campaign.content_subject = generated.get("subject", campaign.content_subject)
        campaign.content_body = generated.get("body", campaign.content_body)
        campaign.content_html = generated.get("html", campaign.content_html)
        campaign.status = "pending_review"
        campaign.preview_token = str(uuid.uuid4())
        campaign.preview_expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
        db.commit()

        return {
            "status": "generated",
            "content": generated,
            "preview_url": f"/campaigns/preview/{campaign.preview_token}",
            "preview_expires_at": campaign.preview_expires_at.isoformat(),
        }

    except Exception as e:
        logger.error("campaign.ai_generate_failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
        }


# ══════════════════════════════════════════════════════════════════════════════
# PREVIEW & APPROVAL
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/preview/{token}")
async def get_campaign_preview(
    token: str,
    db: Session = Depends(get_db),
):
    """Public preview endpoint - no auth required, token-based access."""
    campaign = db.query(Campaign).filter(Campaign.preview_token == token).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Preview not found or expired")

    if campaign.preview_expires_at:
        expires_at = campaign.preview_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Preview has expired")

    # Get template if linked
    template = None
    if campaign.template_id:
        template = db.query(CampaignTemplate).filter(
            CampaignTemplate.id == campaign.template_id
        ).first()

    return {
        "campaign_name": campaign.name,
        "channel": campaign.channel,
        "status": campaign.status,
        "content_subject": campaign.content_subject,
        "content_body": campaign.content_body,
        "content_html": campaign.content_html,
        "ai_prompt": campaign.ai_prompt,
        "template": {
            "name": template.name,
            "header_html": template.header_html,
            "footer_html": template.footer_html,
            "primary_color": template.primary_color,
            "logo_url": template.logo_url,
        } if template else None,
        "scheduled_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
        "target_type": campaign.target_type,
    }


@router.post("/{campaign_id}/approve")
async def approve_campaign(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a campaign for sending."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status not in ("pending_review", "draft"):
        raise HTTPException(status_code=400, detail=f"Campaign cannot be approved from status '{campaign.status}'")

    campaign.status = "approved" if not campaign.scheduled_at else "scheduled"
    db.commit()

    return {"status": campaign.status, "message": "Campaign approved"}


@router.post("/{campaign_id}/reject")
async def reject_campaign(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject AI-generated content, return to draft."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = "draft"
    campaign.ai_generated_content = None
    db.commit()
    return {"status": "draft", "message": "Campaign returned to draft"}


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN SENDING
# ══════════════════════════════════════════════════════════════════════════════

def _render_campaign_email(campaign, template, contact, recipient_id: int = 0, base_url: str = "") -> tuple[str, str]:
    """Render the full HTML email for a campaign recipient.

    Returns (subject, html_body).
    Resolves all template variables including {{first_name}}, {{content}},
    {{unsubscribe_url}} etc. in both the template AND the campaign body.
    """
    first_name = (contact.first_name or contact.name or "").split()[0] if (contact.first_name or contact.name) else ""
    last_name = (contact.last_name or "") if hasattr(contact, "last_name") else ""
    full_name = f"{first_name} {last_name}".strip() or contact.name or ""

    subject = campaign.content_subject or campaign.name
    # Also resolve variables in the subject line
    subject = subject.replace("{{first_name}}", first_name)
    subject = subject.replace("{{name}}", full_name)

    # Build unsubscribe URL
    unsubscribe_url = f"{base_url}/unsubscribe/{recipient_id}" if recipient_id and base_url else "#"

    # Build body HTML – resolve variables in content_body first
    body_content = campaign.content_body or campaign.content_html or ""
    body_content = body_content.replace("{{first_name}}", first_name)
    body_content = body_content.replace("{{name}}", full_name)
    body_content = body_content.replace("{{unsubscribe_url}}", unsubscribe_url)

    if template and template.body_template:
        # Substitute variables in the body template
        body_html = template.body_template
        body_html = body_html.replace("{{first_name}}", first_name)
        body_html = body_html.replace("{{name}}", full_name)
        body_html = body_html.replace("{{content}}", body_content)
        body_html = body_html.replace("{{cta_url}}", "https://calendly.com/dfrigewski/kostenloses-erstgesprach")
        body_html = body_html.replace("{{cta_text}}", "Jetzt Termin buchen")
        body_html = body_html.replace("{{closing}}", "Ich freue mich auf dich!")
        body_html = body_html.replace("{{unsubscribe_url}}", unsubscribe_url)
    else:
        body_html = body_content

    # Wrap with header + footer (also resolve unsubscribe in footer)
    header = (template.header_html or "") if template else ""
    footer = (template.footer_html or "") if template else ""
    footer = footer.replace("{{unsubscribe_url}}", unsubscribe_url)
    footer = footer.replace("{{first_name}}", first_name)

    full_html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#000000;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#000000;">
    <tr><td align="center">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px; width:100%;">
        <tr><td>{header}</td></tr>
        <tr><td>{body_html}</td></tr>
        <tr><td>{footer}</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return subject, full_html


@router.post("/{campaign_id}/send")
async def send_campaign(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a campaign immediately via the configured email channel.

    Uses the centralized MessageRenderer for consistent rendering,
    tracking pixel injection, and link rewriting.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status not in ("approved", "scheduled", "draft"):
        raise HTTPException(status_code=400, detail=f"Campaign cannot be sent from status '{campaign.status}'")

    # Resolve target contacts
    members = _resolve_target_members(db, user.tenant_id, campaign.target_type, campaign.target_filter_json)

    if not members:
        raise HTTPException(status_code=400, detail="No recipients found for this campaign")

    # Resolve SMTP config for this tenant via connector_hub persistence keys
    from app.gateway.persistence import persistence
    from app.integrations.email import SMTPMailer
    from app.campaign_engine.renderer import MessageRenderer
    import smtplib as _smtplib
    from email.message import EmailMessage as _EmailMessage
    import asyncio
    import os

    def _cfg(field: str, default: str = "") -> str:
        key = f"integration_smtp_email_{user.tenant_id}_{field}"
        return persistence.get_setting(key, default, tenant_id=user.tenant_id) or default

    smtp_host = _cfg("host")
    smtp_user = _cfg("username")

    if not smtp_host and campaign.channel == "email":
        raise HTTPException(status_code=400, detail="SMTP-E-Mail ist für diesen Tenant nicht konfiguriert.")

    mailer = None
    if smtp_host:
        mailer = SMTPMailer(
            host=smtp_host,
            port=int(_cfg("port", "587")),
            username=smtp_user,
            password=_cfg("password"),
            from_email=_cfg("from_email") or smtp_user,
            from_name=_cfg("from_name", "ARIIA"),
            use_starttls=True,
        )

    # Validate SMTP config for email campaigns
    if not smtp_host and campaign.channel == "email":
        # Store SMTP config for the sending worker to use later
        pass  # SMTP config is resolved per-tenant by the sending worker

    # Create recipient records and enqueue into send queue
    from app.campaign_engine.send_queue import enqueue_campaign_batch

    campaign.status = "sending"
    campaign.stats_total = len(members)
    db.commit()

    batch_recipients = []
    skipped_count = 0

    for contact in members:
        # Only send to contacts with a valid email and consent
        if campaign.channel == "email" and not contact.email:
            logger.warning("campaign.skip_no_email", contact_id=contact.id)
            skipped_count += 1
            continue

        if hasattr(contact, 'consent_email') and contact.consent_email is False:
            logger.info("campaign.skip_no_consent", contact_id=contact.id)
            skipped_count += 1
            continue

        # Create recipient record (needed for tracking)
        recipient = CampaignRecipient(
            campaign_id=campaign_id,
            contact_id=contact.id,
            tenant_id=user.tenant_id,
            channel=campaign.channel,
            status="queued",
        )
        db.add(recipient)
        db.flush()  # Get the recipient.id

        batch_recipients.append({
            "recipient_id": recipient.id,
            "contact_id": contact.id,
        })

    db.commit()

    # Enqueue all recipients into the send queue for async dispatch
    enqueued = 0
    if batch_recipients:
        enqueued = enqueue_campaign_batch(
            campaign_id=campaign_id,
            tenant_id=user.tenant_id,
            channel=campaign.channel,
            recipients=batch_recipients,
        )

    # Update campaign status
    campaign.stats_total = len(batch_recipients)
    campaign.status = "queued" if enqueued > 0 else "failed"
    campaign.sent_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "campaign.enqueued",
        campaign_id=campaign_id,
        enqueued=enqueued,
        skipped=skipped_count,
        total_contacts=len(members),
    )
    return {
        "status": campaign.status,
        "recipients": enqueued,
        "skipped": skipped_count,
        "sent_at": campaign.sent_at.isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/templates")
async def list_templates(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all templates for the tenant."""
    templates = db.query(CampaignTemplate).filter(
        CampaignTemplate.tenant_id == user.tenant_id,
        CampaignTemplate.is_active.is_(True),
    ).order_by(desc(CampaignTemplate.created_at)).all()

    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "type": t.type,
            "header_html": t.header_html,
            "footer_html": t.footer_html,
            "body_template": t.body_template,
            "variables_json": t.variables_json,
            "primary_color": t.primary_color,
            "logo_url": t.logo_url,
            "is_default": t.is_default,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in templates
    ]


@router.post("/templates")
async def create_template(
    body: TemplateCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new campaign template."""
    template = CampaignTemplate(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        type=body.type,
        header_html=body.header_html,
        footer_html=body.footer_html,
        body_template=body.body_template,
        variables_json=body.variables_json,
        primary_color=body.primary_color,
        logo_url=body.logo_url,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": template.id, "name": template.name, "status": "created"}


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    body: TemplateCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a template."""
    template = db.query(CampaignTemplate).filter(
        CampaignTemplate.id == template_id,
        CampaignTemplate.tenant_id == user.tenant_id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    return {"id": template.id, "status": "updated"}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a template."""
    template = db.query(CampaignTemplate).filter(
        CampaignTemplate.id == template_id,
        CampaignTemplate.tenant_id == user.tenant_id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_active = False
    db.commit()
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# SEGMENTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/segments")
async def list_segments(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all segments for the tenant."""
    segments = db.query(MemberSegment).filter(
        MemberSegment.tenant_id == user.tenant_id,
        MemberSegment.is_active.is_(True),
    ).order_by(desc(MemberSegment.created_at)).all()

    result = []
    for s in segments:
        member_count = s.member_count
        if s.is_dynamic:
            member_count = _count_segment_members(db, user.tenant_id, s.filter_json)
            if member_count != s.member_count:
                s.member_count = member_count
                db.commit()

        result.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "filter_json": s.filter_json,
            "is_dynamic": s.is_dynamic,
            "member_count": member_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return result


@router.post("/segments")
async def create_segment(
    body: SegmentCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new member segment."""
    member_count = _count_segment_members(db, user.tenant_id, body.filter_json)

    segment = MemberSegment(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        filter_json=body.filter_json,
        is_dynamic=body.is_dynamic,
        member_count=member_count,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return {"id": segment.id, "name": segment.name, "member_count": member_count}


@router.delete("/segments/{segment_id}")
async def delete_segment(
    segment_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a segment."""
    segment = db.query(MemberSegment).filter(
        MemberSegment.id == segment_id,
        MemberSegment.tenant_id == user.tenant_id,
    ).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    segment.is_active = False
    db.commit()
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# FOLLOW-UPS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/follow-ups")
async def list_follow_ups(
    status: Optional[str] = None,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all scheduled follow-ups for the tenant."""
    q = db.query(ScheduledFollowUp).filter(ScheduledFollowUp.tenant_id == user.tenant_id)
    if status:
        q = q.filter(ScheduledFollowUp.status == status)

    follow_ups = q.order_by(ScheduledFollowUp.follow_up_at).all()

    result = []
    for fu in follow_ups:
        _contact_id = fu.member_id  # Legacy: ScheduledFollowUp still uses member_id column
        contact = db.query(Contact).filter(Contact.id == _contact_id).first() if _contact_id else None
        result.append({
            "id": fu.id,
            "contact_id": _contact_id,
            "member_id": _contact_id,  # Legacy compatibility
            "contact_name": contact.full_name if contact else "Unknown",
            "conversation_id": fu.conversation_id,
            "reason": fu.reason,
            "follow_up_at": fu.follow_up_at.isoformat() if fu.follow_up_at else None,
            "message_template": fu.message_template,
            "channel": fu.channel,
            "status": fu.status,
            "created_at": fu.created_at.isoformat() if fu.created_at else None,
        })

    return result


@router.post("/follow-ups")
async def create_follow_up(
    body: FollowUpCreate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a scheduled follow-up."""
    follow_up_at = datetime.fromisoformat(body.follow_up_at.replace("Z", "+00:00"))

    # Get chat context if conversation_id provided
    ai_context = None
    if body.conversation_id:
        recent = db.query(ChatMessage).filter(
            ChatMessage.session_id == body.conversation_id,
            ChatMessage.tenant_id == user.tenant_id,
        ).order_by(desc(ChatMessage.created_at)).limit(10).all()
        if recent:
            ai_context = json.dumps([
                {"role": m.role, "content": m.content[:200]} for m in reversed(recent)
            ], ensure_ascii=False)

    fu = ScheduledFollowUp(
        tenant_id=user.tenant_id,
        member_id=body.contact_id or body.member_id,  # Prefer contact_id, fallback to legacy
        conversation_id=body.conversation_id,
        reason=body.reason,
        follow_up_at=follow_up_at,
        message_template=body.message_template,
        channel=body.channel,
        ai_context_json=ai_context,
        created_by=user.user_id,
    )
    db.add(fu)
    db.commit()
    db.refresh(fu)

    return {"id": fu.id, "status": "pending", "follow_up_at": fu.follow_up_at.isoformat()}


@router.delete("/follow-ups/{follow_up_id}")
async def cancel_follow_up(
    follow_up_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a scheduled follow-up."""
    fu = db.query(ScheduledFollowUp).filter(
        ScheduledFollowUp.id == follow_up_id,
        ScheduledFollowUp.tenant_id == user.tenant_id,
    ).first()
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    fu.status = "cancelled"
    db.commit()
    return {"status": "cancelled"}


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGN ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/analytics")
async def campaign_analytics(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get campaign analytics overview."""
    tenant_id = user.tenant_id

    total_campaigns = db.query(Campaign).filter(Campaign.tenant_id == tenant_id).count()
    sent_campaigns = db.query(Campaign).filter(
        Campaign.tenant_id == tenant_id,
        Campaign.status == "sent",
    ).count()

    # Aggregate stats
    stats = db.query(
        func.sum(Campaign.stats_sent),
        func.sum(Campaign.stats_delivered),
        func.sum(Campaign.stats_opened),
        func.sum(Campaign.stats_clicked),
        func.sum(Campaign.stats_failed),
    ).filter(
        Campaign.tenant_id == tenant_id,
        Campaign.status == "sent",
    ).first()

    total_sent = stats[0] or 0
    total_delivered = stats[1] or 0
    total_opened = stats[2] or 0
    total_clicked = stats[3] or 0
    total_failed = stats[4] or 0

    # Recent campaigns
    recent = db.query(Campaign).filter(
        Campaign.tenant_id == tenant_id,
        Campaign.status == "sent",
    ).order_by(desc(Campaign.sent_at)).limit(5).all()

    # Follow-up stats
    pending_follow_ups = db.query(ScheduledFollowUp).filter(
        ScheduledFollowUp.tenant_id == tenant_id,
        ScheduledFollowUp.status == "pending",
    ).count()

    return {
        "total_campaigns": total_campaigns,
        "sent_campaigns": sent_campaigns,
        "total_recipients": total_sent,
        "delivery_rate": round(total_delivered / total_sent * 100, 1) if total_sent > 0 else 0,
        "open_rate": round(total_opened / total_delivered * 100, 1) if total_delivered > 0 else 0,
        "click_rate": round(total_clicked / total_opened * 100, 1) if total_opened > 0 else 0,
        "bounce_rate": round(total_failed / total_sent * 100, 1) if total_sent > 0 else 0,
        "pending_follow_ups": pending_follow_ups,
        "recent_campaigns": [_campaign_to_dict(c) for c in recent],
    }


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _campaign_to_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "type": c.type,
        "status": c.status,
        "channel": c.channel,
        "target_type": c.target_type,
        "target_filter_json": c.target_filter_json,
        "template_id": c.template_id,
        "content_subject": c.content_subject,
        "content_body": c.content_body,
        "content_html": c.content_html,
        "ai_prompt": c.ai_prompt,
        "ai_generated_content": c.ai_generated_content,
        "preview_token": c.preview_token,
        "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
        "is_ab_test": c.is_ab_test,
        "stats_total": c.stats_total,
        "stats_sent": c.stats_sent,
        "stats_delivered": c.stats_delivered,
        "stats_opened": c.stats_opened,
        "stats_clicked": c.stats_clicked,
        "stats_failed": c.stats_failed,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _resolve_target_members(db: Session, tenant_id: int, target_type: str, filter_json: str | None) -> list:
    """Resolve target contacts based on campaign targeting.

    Uses the Contact v2 model for all targeting.
    Returns a list of Contact objects.
    """
    q = db.query(Contact).filter(
        Contact.tenant_id == tenant_id,
        Contact.deleted_at.is_(None),
    )

    if target_type in ("all_members", "all_contacts"):
        return q.all()

    if target_type == "selected" and filter_json:
        try:
            filters = json.loads(filter_json)
            contact_ids = filters.get("contact_ids", filters.get("member_ids", []))
            if contact_ids:
                return q.filter(Contact.id.in_(contact_ids)).all()
        except (json.JSONDecodeError, TypeError):
            pass

    if target_type in ("tag", "tags") and filter_json:
        try:
            filters = json.loads(filter_json)
            tags = filters.get("tags", [])
            if tags:
                # Filter contacts by tags via the ContactTagAssociation join
                return (
                    q.join(ContactTagAssociation, ContactTagAssociation.contact_id == Contact.id)
                    .join(ContactTag, ContactTag.id == ContactTagAssociation.tag_id)
                    .filter(ContactTag.name.in_(tags))
                    .distinct()
                    .all()
                )
        except (json.JSONDecodeError, TypeError):
            pass

    if target_type == "lifecycle" and filter_json:
        try:
            filters = json.loads(filter_json)
            stage = filters.get("lifecycle_stage")
            if stage:
                return q.filter(Contact.lifecycle_stage == stage).all()
        except (json.JSONDecodeError, TypeError):
            pass

    if target_type == "segment" and filter_json:
        try:
            from app.core.contact_models import ContactSegment
            from app.contacts.repository import ContactRepository
            filters = json.loads(filter_json)
            segment_id = filters.get("segment_id")
            if segment_id:
                # Try new ContactSegment model first
                segment = db.query(ContactSegment).filter(
                    ContactSegment.id == segment_id,
                    ContactSegment.tenant_id == tenant_id,
                ).first()
                if segment and segment.filter_groups_json:
                    repo = ContactRepository()
                    filter_groups = json.loads(segment.filter_groups_json)
                    group_connector = segment.group_connector or "and"
                    contacts, _total = repo.evaluate_segment_v2(
                        db, tenant_id, filter_groups, group_connector,
                        page=1, page_size=100000,
                    )
                    return contacts
                elif segment and segment.filter_json:
                    return _apply_segment_filter(db, tenant_id, segment.filter_json)
                # Fallback to legacy MemberSegment
                legacy_segment = db.query(MemberSegment).filter(MemberSegment.id == segment_id).first()
                if legacy_segment and legacy_segment.filter_json:
                    return _apply_segment_filter(db, tenant_id, legacy_segment.filter_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return q.all()


def _apply_segment_filter(db: Session, tenant_id: int, filter_json: str) -> list:
    """Apply segment filter to get matching contacts."""
    q = db.query(Contact).filter(
        Contact.tenant_id == tenant_id,
        Contact.deleted_at.is_(None),
    )
    try:
        filters = json.loads(filter_json)
        if "lifecycle_stage" in filters:
            q = q.filter(Contact.lifecycle_stage == filters["lifecycle_stage"])
        # Legacy support
        if "status" in filters:
            q = q.filter(Contact.lifecycle_stage == filters["status"])
        if "source" in filters:
            q = q.filter(Contact.source == filters["source"])
    except (json.JSONDecodeError, TypeError):
        pass
    return q.all()


def _count_segment_members(db: Session, tenant_id: int, filter_json: str | None) -> int:
    """Count contacts matching a segment filter."""
    if not filter_json:
        return db.query(Contact).filter(
            Contact.tenant_id == tenant_id,
            Contact.deleted_at.is_(None),
        ).count()
    return len(_apply_segment_filter(db, tenant_id, filter_json))


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATION STEPS CRUD
# ═══════════════════════════════════════════════════════════════════════════

class OrchStepSchema(BaseModel):
    step_order: int
    channel: str
    template_id: int | None = None
    content_override_json: str | None = None
    wait_hours: int = 0
    condition_type: str = "always"

class OrchStepsBulk(BaseModel):
    steps: list[OrchStepSchema]

@router.get("/{campaign_id}/orchestration-steps")
async def get_orchestration_steps(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all orchestration steps for a campaign."""
    from app.core.analytics_models import CampaignOrchestrationStep
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    steps = (
        db.query(CampaignOrchestrationStep)
        .filter(CampaignOrchestrationStep.campaign_id == campaign_id)
        .order_by(CampaignOrchestrationStep.step_order)
        .all()
    )
    return [
        {
            "id": s.id,
            "campaign_id": s.campaign_id,
            "step_order": s.step_order,
            "channel": s.channel,
            "template_id": s.template_id,
            "content_override_json": s.content_override_json,
            "wait_hours": s.wait_hours,
            "condition_type": s.condition_type,
        }
        for s in steps
    ]


@router.post("/{campaign_id}/orchestration-steps")
async def save_orchestration_steps(
    campaign_id: int,
    payload: OrchStepsBulk,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace all orchestration steps for a campaign (bulk upsert)."""
    from app.core.analytics_models import CampaignOrchestrationStep
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Delete existing steps
    db.query(CampaignOrchestrationStep).filter(
        CampaignOrchestrationStep.campaign_id == campaign_id
    ).delete()

    # Insert new steps
    for s in payload.steps:
        db.add(CampaignOrchestrationStep(
            campaign_id=campaign_id,
            step_order=s.step_order,
            channel=s.channel,
            template_id=s.template_id,
            content_override_json=s.content_override_json,
            wait_hours=s.wait_hours,
            condition_type=s.condition_type,
        ))

    db.commit()
    return {"status": "ok", "count": len(payload.steps)}


# ══════════════════════════════════════════════════════════════════════════════
# QUEUE STATS (v2 endpoint)
# ══════════════════════════════════════════════════════════════════════════════

v2_campaigns_router = APIRouter(prefix="/v2/admin/campaigns", tags=["campaigns-v2"])


@v2_campaigns_router.get("/queue-stats")
async def get_queue_stats(
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current send queue statistics for the campaign dashboard."""
    from app.core.models import CampaignRecipient
    
    # Calculate tenant-specific queue and failed lengths directly from the DB
    send_queue_len = db.query(CampaignRecipient).filter(
        CampaignRecipient.tenant_id == user.tenant_id,
        CampaignRecipient.status == "queued"
    ).count()

    dlq_len = db.query(CampaignRecipient).filter(
        CampaignRecipient.tenant_id == user.tenant_id,
        CampaignRecipient.status == "failed"
    ).count()

    # We do not track tenant-level isolated analytics queue events yet,
    # so we return 0 for analytics queue length.
    analytics_queue_len = 0
    workers_active = True

    return {
        "send_queue_length": send_queue_len,
        "dead_letter_queue_length": dlq_len,
        "analytics_queue_length": analytics_queue_len,
        "workers_active": workers_active,
        "last_processed_at": None,
        "throughput_per_minute": 0,
    }
