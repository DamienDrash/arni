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
    MemberSegment, ScheduledFollowUp, StudioMember, ChatMessage, ChatSession,
)

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
    member_id: Optional[int] = None
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
    campaign = Campaign(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        type=body.type,
        channel=body.channel,
        target_type=body.target_type,
        target_filter_json=body.target_filter_json,
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
            member_count = db.query(StudioMember).filter(
                StudioMember.tenant_id == user.tenant_id
            ).count()
            context_parts.append(f"Target audience: {member_count} members")
        except (json.JSONDecodeError, TypeError):
            pass

    # Get knowledge base context if requested
    knowledge_context = ""
    if body.use_knowledge:
        try:
            from app.gateway.persistence import persistence
            knowledge_context = persistence.get_setting("knowledge_base_summary", "", tenant_id=user.tenant_id)
            if knowledge_context:
                context_parts.append(f"Knowledge base context: {knowledge_context[:500]}")
        except Exception:
            pass

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

    system_prompt = f"""Du bist ein Marketing-Experte und Content Creator für ein Fitness-Studio / Unternehmen.
Dein Ton ist {tone_desc}.
{format_instruction}

Kontext:
{chr(10).join(context_parts)}

WICHTIG:
- Verwende Platzhalter wie {{{{first_name}}}}, {{{{studio_name}}}} für Personalisierung
- Der Inhalt muss zum Kanal passen ({campaign.channel})
- Antworte im JSON-Format: {{"subject": "...", "body": "...", "html": "..."}}
- Für WhatsApp/SMS/Telegram: "html" kann leer sein
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

    if campaign.preview_expires_at and campaign.preview_expires_at < datetime.now(timezone.utc):
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
# CAMPAIGN SENDING (Simulation)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{campaign_id}/send")
async def send_campaign(
    campaign_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a campaign immediately."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.tenant_id == user.tenant_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status not in ("approved", "scheduled", "draft"):
        raise HTTPException(status_code=400, detail=f"Campaign cannot be sent from status '{campaign.status}'")

    # Resolve target members
    members = _resolve_target_members(db, user.tenant_id, campaign.target_type, campaign.target_filter_json)

    if not members:
        raise HTTPException(status_code=400, detail="No recipients found for this campaign")

    # Create recipient records
    campaign.status = "sending"
    campaign.stats_total = len(members)
    db.commit()

    sent_count = 0
    for member in members:
        recipient = CampaignRecipient(
            campaign_id=campaign_id,
            member_id=member.id,
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )
        db.add(recipient)
        sent_count += 1

    campaign.status = "sent"
    campaign.stats_sent = sent_count
    campaign.sent_at = datetime.now(timezone.utc)
    db.commit()

    logger.info("campaign.sent", campaign_id=campaign_id, recipients=sent_count)
    return {
        "status": "sent",
        "recipients": sent_count,
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
        member = db.query(StudioMember).filter(StudioMember.id == fu.member_id).first() if fu.member_id else None
        result.append({
            "id": fu.id,
            "member_id": fu.member_id,
            "member_name": f"{member.first_name} {member.last_name}" if member else "Unknown",
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
        member_id=body.member_id,
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
    """Resolve target members based on campaign targeting."""
    q = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id)

    if target_type == "all_members":
        return q.all()

    if target_type == "selected" and filter_json:
        try:
            filters = json.loads(filter_json)
            member_ids = filters.get("member_ids", [])
            if member_ids:
                return q.filter(StudioMember.id.in_(member_ids)).all()
        except (json.JSONDecodeError, TypeError):
            pass

    if target_type == "tags" and filter_json:
        try:
            filters = json.loads(filter_json)
            tags = filters.get("tags", [])
            if tags:
                # Filter by tags in the tags column
                members = q.all()
                return [m for m in members if any(t in (m.tags or "") for t in tags)]
        except (json.JSONDecodeError, TypeError):
            pass

    if target_type == "segment" and filter_json:
        try:
            filters = json.loads(filter_json)
            segment_id = filters.get("segment_id")
            if segment_id:
                segment = db.query(MemberSegment).filter(MemberSegment.id == segment_id).first()
                if segment and segment.filter_json:
                    return _apply_segment_filter(db, tenant_id, segment.filter_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return q.all()


def _apply_segment_filter(db: Session, tenant_id: int, filter_json: str) -> list:
    """Apply segment filter to get matching members."""
    q = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id)
    try:
        filters = json.loads(filter_json)
        if "status" in filters:
            q = q.filter(StudioMember.status == filters["status"])
        if "source" in filters:
            q = q.filter(StudioMember.source == filters["source"])
    except (json.JSONDecodeError, TypeError):
        pass
    return q.all()


def _count_segment_members(db: Session, tenant_id: int, filter_json: str | None) -> int:
    """Count members matching a segment filter."""
    if not filter_json:
        return db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id).count()
    return len(_apply_segment_filter(db, tenant_id, filter_json))
