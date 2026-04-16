"""ARIIA Swarm v3 — Escalation Router.

Routes QAJudge ESCALATE verdicts to the appropriate handler:
- human_handoff: activates human mode in Redis, publishes handoff event
- retry_with_different_agent: re-classifies intent with escalated=True flag
- dead_letter: logs structured error + audit_log entry

Handler is configurable via OrchestratorManager (quality-gate.escalation_handler).
"""

from __future__ import annotations

import json
import structlog
from enum import Enum

from app.shared.db import open_session

logger = structlog.get_logger()


class EscalationHandler(str, Enum):
    HUMAN_HANDOFF = "human_handoff"
    RETRY_WITH_DIFFERENT_AGENT = "retry_with_different_agent"
    DEAD_LETTER = "dead_letter"


def _get_configured_handler() -> str:
    """Read escalation_handler from OrchestratorManager quality-gate config."""
    try:
        from app.orchestration.manager import OrchestratorManager

        db = open_session()
        try:
            mgr = OrchestratorManager(db)
            config = mgr.get_config("quality-gate")
            return config.get("escalation_handler", EscalationHandler.HUMAN_HANDOFF)
        except Exception:
            return EscalationHandler.HUMAN_HANDOFF
        finally:
            db.close()
    except Exception:
        return EscalationHandler.HUMAN_HANDOFF


async def route_escalation(
    result,
    handler: str | None = None,
    tenant_id: int = 0,
    member_id: str | None = None,
    channel: str | None = None,
    redis=None,
):
    """Route an escalated result to the appropriate handler.

    If handler is None, reads the configured handler from OrchestratorManager
    (quality-gate orchestrator config → escalation_handler field).

    Args:
        result: The AgentResult that triggered escalation.
        handler: Override handler name. If None, reads from OrchestratorManager.
        tenant_id: Current tenant ID.
        member_id: Member ID for human handoff targeting.
        channel: Communication channel (whatsapp, telegram, etc.).
        redis: RedisBus instance for publishing events.

    Returns:
        The (potentially modified) AgentResult.
    """
    if handler is None:
        handler = _get_configured_handler()
    if handler == EscalationHandler.HUMAN_HANDOFF:
        return await _handle_human_handoff(result, tenant_id, member_id, channel, redis)
    if handler == EscalationHandler.RETRY_WITH_DIFFERENT_AGENT:
        return await _handle_retry_with_different_agent(result, tenant_id, member_id, channel, redis)
    if handler == EscalationHandler.DEAD_LETTER:
        return await _handle_dead_letter(result, tenant_id)
    logger.warning("escalation.unknown_handler", handler=handler)
    return await _handle_dead_letter(result, tenant_id)


async def _handle_retry_with_different_agent(result, tenant_id, member_id, channel, redis):
    """Re-classify intent with escalated=True, route to next best agent."""
    try:
        if redis:
            await redis.publish(
                "ariia:events",
                json.dumps({
                    "event": "escalation_retry_requested",
                    "tenant_id": tenant_id,
                    "member_id": member_id,
                    "channel": channel,
                    "escalated": True,
                    "reason": getattr(result, "metadata", {}).get("escalation_reason"),
                }),
            )
            logger.info(
                "escalation.retry_published",
                tenant_id=tenant_id,
                member_id=member_id,
            )
    except Exception as e:
        logger.error("escalation.retry_failed", error=str(e))
        # Fall back to human handoff
        return await _handle_human_handoff(result, tenant_id, member_id, channel, redis)
    return result


async def _handle_human_handoff(result, tenant_id, member_id, channel, redis):
    """Activate human mode for the member and publish a handoff event."""
    try:
        if redis and member_id:
            await redis.client.set(
                f"t{tenant_id}:human_mode:{member_id}", "1", ex=3600,
            )
            await redis.publish(
                "ariia:events",
                json.dumps({
                    "event": "human_handoff_requested",
                    "tenant_id": tenant_id,
                    "member_id": member_id,
                    "reason": "qa_escalation",
                    "channel": channel,
                }),
            )
            logger.info(
                "escalation.human_handoff_activated",
                tenant_id=tenant_id,
                member_id=member_id,
            )
    except Exception as e:
        logger.error("escalation.human_handoff_failed", error=str(e))
    return result


async def _handle_dead_letter(result, tenant_id):
    """Log the escalated result as a dead letter and create an audit log entry."""
    logger.error(
        "escalation.dead_letter",
        tenant_id=tenant_id,
        result_text=getattr(result, "content", str(result))[:500],
    )
    try:
        from app.domains.identity.models import AuditLog

        db = open_session()
        try:
            entry = AuditLog(
                tenant_id=tenant_id,
                action="qa_escalation_dead_letter",
                category="swarm",
                target_type="agent_result",
                target_id=str(getattr(result, "agent_id", "unknown")),
                details_json=json.dumps({
                    "reason": getattr(result, "metadata", {}).get("escalation_reason"),
                    "content_preview": getattr(result, "content", "")[:200],
                }),
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("escalation.dead_letter_audit_failed", error=str(e))
    return result
