"""app/platform/api/tenant_portal.py — Tenant Self-Service Portal API.

Provides tenant admins with full control over their agent configuration,
personas, system prompts, integration status, and operational overview.

Endpoints (prefix /api/v1/tenant/portal):
    GET  /overview           → Tenant dashboard overview (stats, health, usage)
    GET  /agent/config       → Current agent configuration
    PUT  /agent/config       → Update agent configuration
    GET  /agent/persona      → Current agent persona
    PUT  /agent/persona      → Update agent persona
    GET  /agent/prompts      → System prompts (all)
    PUT  /agent/prompts      → Update system prompts
    POST /agent/prompts/test → Test a prompt with sample input
    GET  /channels           → Active messaging channels + status
    PUT  /channels/{channel} → Enable/disable a channel
    GET  /status             → System health from tenant perspective
    GET  /usage              → Usage metrics for current billing period
    GET  /audit-log          → Recent audit log entries
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.models import (
    Tenant, TenantConfig, Subscription, Plan, AuditLog,
    UsageRecord, ChatSession, ChatMessage,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/tenant/portal", tags=["tenant-portal"])


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _require_tenant_admin(user: AuthContext) -> AuthContext:
    """Ensure the user has tenant_admin or system_admin role."""
    require_role(user, {"system_admin", "tenant_admin"})
    return user


def _get_config(db, tenant_id: int, key: str, default: str = "") -> str:
    """Read a single tenant config value."""
    row = db.query(TenantConfig).filter(
        TenantConfig.tenant_id == tenant_id,
        TenantConfig.key == key,
    ).first()
    return row.value if row and row.value else default


def _set_config(db, tenant_id: int, key: str, value: str) -> None:
    """Upsert a tenant config value."""
    row = db.query(TenantConfig).filter(
        TenantConfig.tenant_id == tenant_id,
        TenantConfig.key == key,
    ).first()
    if row:
        row.value = value
    else:
        db.add(TenantConfig(tenant_id=tenant_id, key=key, value=value))


def _get_json_config(db, tenant_id: int, key: str, default: Any = None) -> Any:
    """Read a JSON tenant config value."""
    raw = _get_config(db, tenant_id, key, "")
    if not raw:
        return default if default is not None else {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def _set_json_config(db, tenant_id: int, key: str, value: Any) -> None:
    """Write a JSON tenant config value."""
    _set_config(db, tenant_id, key, json.dumps(value, ensure_ascii=False))


def _audit(db, tenant_id: int, user_id: int, action: str, details: dict) -> None:
    """Write an audit log entry."""
    try:
        db.add(AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            details=json.dumps(details, ensure_ascii=False, default=str),
            created_at=datetime.now(timezone.utc),
        ))
    except Exception:
        logger.warning("audit_log.write_failed", action=action)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class AgentConfigUpdate(BaseModel):
    """Schema for updating agent configuration."""
    agent_name: Optional[str] = Field(None, max_length=100, description="Display name of the agent")
    language: Optional[str] = Field(None, max_length=10, description="Primary language (e.g. 'de', 'en')")
    tone: Optional[str] = Field(None, description="Communication tone: formal, friendly, casual")
    max_response_length: Optional[int] = Field(None, ge=50, le=4000, description="Max response length in chars")
    greeting_message: Optional[str] = Field(None, max_length=1000, description="Initial greeting message")
    fallback_message: Optional[str] = Field(None, max_length=1000, description="Fallback when agent can't help")
    escalation_message: Optional[str] = Field(None, max_length=1000, description="Message when escalating to human")
    auto_escalate_after: Optional[int] = Field(None, ge=0, le=20, description="Auto-escalate after N failed attempts")
    business_hours: Optional[dict] = Field(None, description="Business hours config")
    enabled_features: Optional[list[str]] = Field(None, description="List of enabled feature keys")


class PersonaUpdate(BaseModel):
    """Schema for updating agent persona."""
    name: Optional[str] = Field(None, max_length=100, description="Persona display name")
    role: Optional[str] = Field(None, max_length=200, description="Role description")
    personality: Optional[str] = Field(None, max_length=2000, description="Personality traits and behavior")
    expertise: Optional[list[str]] = Field(None, description="Areas of expertise")
    restrictions: Optional[list[str]] = Field(None, description="Things the agent should NOT do")
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar image URL")


class SystemPromptsUpdate(BaseModel):
    """Schema for updating system prompts."""
    main_system_prompt: Optional[str] = Field(None, max_length=10000, description="Main system prompt")
    greeting_prompt: Optional[str] = Field(None, max_length=2000, description="Greeting generation prompt")
    escalation_prompt: Optional[str] = Field(None, max_length=2000, description="Escalation handling prompt")
    knowledge_prompt: Optional[str] = Field(None, max_length=2000, description="Knowledge retrieval prompt")
    custom_instructions: Optional[str] = Field(None, max_length=5000, description="Additional custom instructions")


class PromptTestRequest(BaseModel):
    """Schema for testing a prompt."""
    prompt: str = Field(..., max_length=10000, description="The prompt to test")
    sample_input: str = Field(..., max_length=2000, description="Sample user message")
    model: Optional[str] = Field("gpt-4o-mini", description="Model to use for testing")


class ChannelUpdate(BaseModel):
    """Schema for updating a channel."""
    enabled: bool = Field(..., description="Whether the channel is enabled")
    config: Optional[dict] = Field(None, description="Channel-specific configuration")


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS: OVERVIEW & STATUS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/overview")
async def get_tenant_overview(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Tenant dashboard overview with key metrics and health status."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Subscription info
        sub = db.query(Subscription).filter(
            Subscription.tenant_id == user.tenant_id
        ).first()

        plan = None
        if sub and sub.plan_id:
            plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()

        # Usage stats for current period
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        conversation_count = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= period_start,
        ).count()

        # Recent audit entries
        recent_audits = db.query(AuditLog).filter(
            AuditLog.tenant_id == user.tenant_id,
        ).order_by(AuditLog.created_at.desc()).limit(5).all()

        # Agent config summary
        agent_name = _get_config(db, user.tenant_id, "agent_name", "ARIIA Agent")
        agent_language = _get_config(db, user.tenant_id, "agent_language", "de")

        # Active channels
        channels_config = _get_json_config(db, user.tenant_id, "channels_config", {})
        active_channels = [ch for ch, cfg in channels_config.items()
                          if isinstance(cfg, dict) and cfg.get("enabled")]

        return {
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "created_at": str(tenant.created_at) if hasattr(tenant, "created_at") else None,
            },
            "subscription": {
                "plan_name": plan.name if plan else "Free",
                "plan_slug": plan.slug if plan else "free",
                "status": sub.status if sub else "inactive",
                "current_period_end": str(sub.current_period_end) if sub and sub.current_period_end else None,
            } if sub else {"plan_name": "Free", "status": "inactive"},
            "usage": {
                "conversations_this_period": conversation_count,
                "max_conversations": plan.max_monthly_messages if plan and hasattr(plan, "max_monthly_messages") else None,
                "period_start": str(period_start),
            },
            "agent": {
                "name": agent_name,
                "language": agent_language,
                "active_channels": active_channels,
            },
            "recent_activity": [
                {
                    "action": a.action,
                    "created_at": str(a.created_at),
                    "details": a.details[:200] if a.details else None,
                }
                for a in recent_audits
            ],
        }
    finally:
        db.close()


@router.get("/status")
async def get_system_status(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """System health status from the tenant's perspective."""
    _require_tenant_admin(user)

    # Check component health
    components = {}

    # Redis
    try:
        import redis
        from config.settings import get_settings
        settings = get_settings()
        r = redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        components["redis"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        components["redis"] = {"status": "degraded", "error": str(e)[:100]}

    # Database
    try:
        db = SessionLocal()
        from sqlalchemy import text
        start = time.time()
        db.execute(text("SELECT 1"))
        latency = round((time.time() - start) * 1000, 1)
        components["database"] = {"status": "healthy", "latency_ms": latency}
        db.close()
    except Exception as e:
        components["database"] = {"status": "degraded", "error": str(e)[:100]}

    # Overall status
    all_healthy = all(c["status"] == "healthy" for c in components.values())

    return {
        "overall": "healthy" if all_healthy else "degraded",
        "components": components,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/usage")
async def get_usage_metrics(
    user: AuthContext = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
) -> dict[str, Any]:
    """Usage metrics for the current billing period."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)

        # Conversation count
        conversations = db.query(ChatSession).filter(
            ChatSession.tenant_id == user.tenant_id,
            ChatSession.created_at >= since,
        ).count()

        # Usage records (token usage)
        usage_records = db.query(UsageRecord).filter(
            UsageRecord.tenant_id == user.tenant_id,
            UsageRecord.created_at >= since,
        ).all()

        total_tokens = sum(r.tokens_used for r in usage_records if hasattr(r, "tokens_used") and r.tokens_used)
        total_cost_cents = sum(r.cost_cents for r in usage_records if hasattr(r, "cost_cents") and r.cost_cents)

        # Subscription limits
        sub = db.query(Subscription).filter(
            Subscription.tenant_id == user.tenant_id
        ).first()
        plan = None
        if sub and sub.plan_id:
            plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()

        max_messages = plan.max_monthly_messages if plan and hasattr(plan, "max_monthly_messages") else None

        return {
            "period": {"days": days, "since": since.isoformat(), "until": now.isoformat()},
            "conversations": conversations,
            "tokens_used": total_tokens,
            "cost_cents": total_cost_cents,
            "limits": {
                "max_monthly_messages": max_messages,
                "usage_percent": round(conversations / max_messages * 100, 1) if max_messages else None,
            },
        }
    finally:
        db.close()


@router.get("/audit-log")
async def get_audit_log(
    user: AuthContext = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action_filter: Optional[str] = Query(None, description="Filter by action type"),
) -> dict[str, Any]:
    """Recent audit log entries for the tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        query = db.query(AuditLog).filter(AuditLog.tenant_id == user.tenant_id)

        if action_filter:
            query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))

        total = query.count()
        entries = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "entries": [
                {
                    "id": e.id,
                    "action": e.action,
                    "user_id": e.user_id,
                    "details": e.details,
                    "created_at": str(e.created_at),
                }
                for e in entries
            ],
        }
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS: AGENT CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/agent/config")
async def get_agent_config(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current agent configuration for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        config = {
            "agent_name": _get_config(db, user.tenant_id, "agent_name", "ARIIA Agent"),
            "language": _get_config(db, user.tenant_id, "agent_language", "de"),
            "tone": _get_config(db, user.tenant_id, "agent_tone", "friendly"),
            "max_response_length": int(_get_config(db, user.tenant_id, "agent_max_response_length", "1000")),
            "greeting_message": _get_config(db, user.tenant_id, "agent_greeting", ""),
            "fallback_message": _get_config(db, user.tenant_id, "agent_fallback_message", ""),
            "escalation_message": _get_config(db, user.tenant_id, "agent_escalation_message", ""),
            "auto_escalate_after": int(_get_config(db, user.tenant_id, "agent_auto_escalate_after", "3")),
            "business_hours": _get_json_config(db, user.tenant_id, "business_hours", {}),
            "enabled_features": _get_json_config(db, user.tenant_id, "enabled_features", []),
        }
        return {"config": config, "tenant_id": user.tenant_id}
    finally:
        db.close()


@router.put("/agent/config")
async def update_agent_config(
    body: AgentConfigUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update agent configuration for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        updates = body.model_dump(exclude_none=True)
        field_map = {
            "agent_name": "agent_name",
            "language": "agent_language",
            "tone": "agent_tone",
            "max_response_length": "agent_max_response_length",
            "greeting_message": "agent_greeting",
            "fallback_message": "agent_fallback_message",
            "escalation_message": "agent_escalation_message",
            "auto_escalate_after": "agent_auto_escalate_after",
        }

        for field, config_key in field_map.items():
            if field in updates:
                _set_config(db, user.tenant_id, config_key, str(updates[field]))

        if "business_hours" in updates:
            _set_json_config(db, user.tenant_id, "business_hours", updates["business_hours"])

        if "enabled_features" in updates:
            _set_json_config(db, user.tenant_id, "enabled_features", updates["enabled_features"])

        _audit(db, user.tenant_id, user.user_id, "agent_config.updated", {
            "fields": list(updates.keys()),
        })

        db.commit()
        logger.info("tenant_portal.agent_config_updated",
                     tenant_id=user.tenant_id, fields=list(updates.keys()))

        return {"status": "updated", "fields": list(updates.keys())}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
    finally:
        db.close()


@router.get("/agent/persona")
async def get_agent_persona(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current agent persona for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        persona = _get_json_config(db, user.tenant_id, "agent_persona", {
            "name": "ARIIA",
            "role": "Kundenservice-Assistent",
            "personality": "Freundlich, hilfsbereit und professionell.",
            "expertise": ["Kundenservice", "Terminbuchung", "Allgemeine Fragen"],
            "restrictions": ["Keine medizinischen Ratschläge", "Keine Finanzberatung"],
            "avatar_url": "",
        })
        return {"persona": persona, "tenant_id": user.tenant_id}
    finally:
        db.close()


@router.put("/agent/persona")
async def update_agent_persona(
    body: PersonaUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update agent persona for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        current = _get_json_config(db, user.tenant_id, "agent_persona", {})
        updates = body.model_dump(exclude_none=True)
        current.update(updates)

        _set_json_config(db, user.tenant_id, "agent_persona", current)
        _audit(db, user.tenant_id, user.user_id, "agent_persona.updated", {
            "fields": list(updates.keys()),
        })

        db.commit()
        logger.info("tenant_portal.persona_updated",
                     tenant_id=user.tenant_id, fields=list(updates.keys()))

        return {"status": "updated", "persona": current}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
    finally:
        db.close()


@router.get("/agent/prompts")
async def get_system_prompts(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Get all system prompts for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        prompts = {
            "main_system_prompt": _get_config(db, user.tenant_id, "system_prompt", ""),
            "greeting_prompt": _get_config(db, user.tenant_id, "greeting_prompt", ""),
            "escalation_prompt": _get_config(db, user.tenant_id, "escalation_prompt", ""),
            "knowledge_prompt": _get_config(db, user.tenant_id, "knowledge_prompt", ""),
            "custom_instructions": _get_config(db, user.tenant_id, "custom_instructions", ""),
        }
        return {"prompts": prompts, "tenant_id": user.tenant_id}
    finally:
        db.close()


@router.put("/agent/prompts")
async def update_system_prompts(
    body: SystemPromptsUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Update system prompts for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        updates = body.model_dump(exclude_none=True)
        prompt_map = {
            "main_system_prompt": "system_prompt",
            "greeting_prompt": "greeting_prompt",
            "escalation_prompt": "escalation_prompt",
            "knowledge_prompt": "knowledge_prompt",
            "custom_instructions": "custom_instructions",
        }

        for field, config_key in prompt_map.items():
            if field in updates:
                _set_config(db, user.tenant_id, config_key, updates[field])

        _audit(db, user.tenant_id, user.user_id, "system_prompts.updated", {
            "fields": list(updates.keys()),
        })

        db.commit()
        logger.info("tenant_portal.prompts_updated",
                     tenant_id=user.tenant_id, fields=list(updates.keys()))

        return {"status": "updated", "fields": list(updates.keys())}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
    finally:
        db.close()


@router.post("/agent/prompts/test")
async def test_prompt(
    body: PromptTestRequest,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Test a system prompt with a sample input using the configured LLM."""
    _require_tenant_admin(user)

    try:
        from app.swarm.llm import LLMClient
        client = LLMClient()
        messages = [
            {"role": "system", "content": body.prompt},
            {"role": "user", "content": body.sample_input},
        ]
        response = client.chat(messages, model=body.model)
        return {
            "response": response,
            "model": body.model,
            "prompt_length": len(body.prompt),
            "input_length": len(body.sample_input),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt test failed: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS: CHANNELS
# ══════════════════════════════════════════════════════════════════════════════

SUPPORTED_CHANNELS = {
    "whatsapp": {"name": "WhatsApp", "description": "WhatsApp Business API"},
    "telegram": {"name": "Telegram", "description": "Telegram Bot API"},
    "email": {"name": "E-Mail", "description": "SMTP/IMAP E-Mail-Integration"},
    "webchat": {"name": "Webchat", "description": "Eingebetteter Website-Chat"},
    "instagram": {"name": "Instagram", "description": "Instagram Direct Messages"},
    "facebook": {"name": "Facebook", "description": "Facebook Messenger"},
}


@router.get("/channels")
async def get_channels(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Get all messaging channels with their status for this tenant."""
    _require_tenant_admin(user)
    db = SessionLocal()
    try:
        channels_config = _get_json_config(db, user.tenant_id, "channels_config", {})

        channels = []
        for ch_id, ch_meta in SUPPORTED_CHANNELS.items():
            ch_cfg = channels_config.get(ch_id, {})
            channels.append({
                "id": ch_id,
                "name": ch_meta["name"],
                "description": ch_meta["description"],
                "enabled": ch_cfg.get("enabled", False) if isinstance(ch_cfg, dict) else False,
                "configured": bool(ch_cfg.get("config")) if isinstance(ch_cfg, dict) else False,
                "config": {k: "***" if "secret" in k.lower() or "token" in k.lower() or "key" in k.lower()
                          else v for k, v in ch_cfg.get("config", {}).items()}
                if isinstance(ch_cfg, dict) and ch_cfg.get("config") else {},
            })

        return {"channels": channels, "tenant_id": user.tenant_id}
    finally:
        db.close()


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Enable/disable a messaging channel or update its configuration."""
    _require_tenant_admin(user)

    if channel_id not in SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"Unknown channel: {channel_id}")

    db = SessionLocal()
    try:
        channels_config = _get_json_config(db, user.tenant_id, "channels_config", {})

        current = channels_config.get(channel_id, {})
        if not isinstance(current, dict):
            current = {}

        current["enabled"] = body.enabled
        if body.config is not None:
            current["config"] = body.config

        channels_config[channel_id] = current
        _set_json_config(db, user.tenant_id, "channels_config", channels_config)

        _audit(db, user.tenant_id, user.user_id, "channel.updated", {
            "channel": channel_id,
            "enabled": body.enabled,
        })

        db.commit()
        logger.info("tenant_portal.channel_updated",
                     tenant_id=user.tenant_id, channel=channel_id, enabled=body.enabled)

        return {"status": "updated", "channel": channel_id, "enabled": body.enabled}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
    finally:
        db.close()
