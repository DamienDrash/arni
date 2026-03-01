"""ARIIA v2.0 – HandoffAgent: Human Escalation Manager.

Manages the transition from AI agent to human support when:
- The agent's confidence is too low
- The user explicitly requests a human
- A critical operation requires human approval
- The conversation exceeds the agent's capabilities

Architecture:
    SupervisorAgent → detects escalation need → HandoffManager → creates ticket → notifies team
"""
from __future__ import annotations

import time
import uuid
import structlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = structlog.get_logger()


class HandoffPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class HandoffReason(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    USER_REQUEST = "user_request"
    CRITICAL_OPERATION = "critical_operation"
    REPEATED_FAILURE = "repeated_failure"
    COMPLAINT = "complaint"
    COMPLEX_QUERY = "complex_query"
    LEGAL_MATTER = "legal_matter"
    BILLING_DISPUTE = "billing_dispute"


class HandoffStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass
class HandoffTicket:
    """A handoff ticket representing an escalation to human support."""
    ticket_id: str
    tenant_id: int
    user_id: str
    reason: HandoffReason
    priority: HandoffPriority
    status: HandoffStatus = HandoffStatus.PENDING
    summary: str = ""
    context: str = ""
    conversation_history: list[dict] = field(default_factory=list)
    agent_notes: str = ""
    assigned_to: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "reason": self.reason.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "summary": self.summary,
            "context": self.context,
            "agent_notes": self.agent_notes,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
        }


# ─── Escalation Detection ───────────────────────────────────────────────────

HUMAN_REQUEST_PATTERNS = [
    "mensch", "mitarbeiter", "support", "agent", "person",
    "jemand echtes", "echter mensch", "human", "real person",
    "beschwerde", "complaint", "manager", "vorgesetzter",
    "ich möchte mit jemandem sprechen",
    "können sie mich verbinden",
    "ich brauche hilfe von einem menschen",
]

COMPLAINT_PATTERNS = [
    "beschwerde", "unzufrieden", "schlecht", "katastrophe",
    "frechheit", "unverschämt", "anwalt", "rechtsanwalt",
    "verbraucherschutz", "klage", "complaint",
]

LEGAL_PATTERNS = [
    "anwalt", "rechtsanwalt", "klage", "gericht",
    "datenschutz", "dsgvo", "gdpr", "schadensersatz",
    "abmahnung", "lawyer", "legal",
]


class EscalationDetector:
    """Detects when a conversation should be escalated to human support."""

    def detect(
        self,
        message: str,
        confidence: float = 1.0,
        failure_count: int = 0,
    ) -> Optional[tuple[HandoffReason, HandoffPriority]]:
        """Analyze a message and context to determine if escalation is needed.

        Returns:
            Tuple of (reason, priority) if escalation needed, None otherwise.
        """
        message_lower = message.lower()

        # Check for legal matters (highest priority)
        if any(pattern in message_lower for pattern in LEGAL_PATTERNS):
            return (HandoffReason.LEGAL_MATTER, HandoffPriority.URGENT)

        # Check for complaints (before general human request)
        if any(pattern in message_lower for pattern in COMPLAINT_PATTERNS):
            return (HandoffReason.COMPLAINT, HandoffPriority.HIGH)

        # Check for explicit human request
        if any(pattern in message_lower for pattern in HUMAN_REQUEST_PATTERNS):
            return (HandoffReason.USER_REQUEST, HandoffPriority.HIGH)

        # Check confidence
        if confidence < 0.3:
            return (HandoffReason.LOW_CONFIDENCE, HandoffPriority.NORMAL)

        # Check repeated failures
        if failure_count >= 3:
            return (HandoffReason.REPEATED_FAILURE, HandoffPriority.HIGH)

        return None


class HandoffManager:
    """Manages the creation and lifecycle of handoff tickets.

    In a full production system, this would:
    - Store tickets in the database
    - Send notifications via email/Slack/Teams
    - Track SLA compliance
    - Route to the right support team

    Current implementation: In-memory + Redis-based for MVP.
    """

    def __init__(self):
        self._detector = EscalationDetector()
        self._tickets: dict[str, HandoffTicket] = {}

    def check_escalation(
        self,
        message: str,
        confidence: float = 1.0,
        failure_count: int = 0,
    ) -> Optional[tuple[HandoffReason, HandoffPriority]]:
        """Check if a message should trigger escalation."""
        return self._detector.detect(message, confidence, failure_count)

    async def create_handoff(
        self,
        tenant_id: int,
        user_id: str,
        reason: str | HandoffReason,
        context: str = "",
        priority: str | HandoffPriority = HandoffPriority.NORMAL,
        conversation_history: Optional[list[dict]] = None,
        agent_notes: str = "",
    ) -> dict:
        """Create a new handoff ticket.

        Args:
            tenant_id: The tenant ID
            user_id: The user requesting handoff
            reason: Why the handoff is needed
            context: Additional context about the conversation
            priority: Ticket priority level
            conversation_history: Recent chat messages
            agent_notes: Notes from the AI agent about what was attempted

        Returns:
            Dict with ticket details
        """
        # Normalize enums
        if isinstance(reason, str):
            try:
                reason = HandoffReason(reason)
            except ValueError:
                reason = HandoffReason.COMPLEX_QUERY

        if isinstance(priority, str):
            try:
                priority = HandoffPriority(priority)
            except ValueError:
                priority = HandoffPriority.NORMAL

        ticket_id = f"HO-{uuid.uuid4().hex[:8].upper()}"

        ticket = HandoffTicket(
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            user_id=user_id,
            reason=reason,
            priority=priority,
            summary=self._generate_summary(reason, context),
            context=context,
            conversation_history=conversation_history or [],
            agent_notes=agent_notes,
        )

        self._tickets[ticket_id] = ticket

        # Notify support team
        await self._notify_support_team(ticket)

        # Store in Redis for persistence
        await self._store_ticket(ticket)

        logger.info(
            "handoff.ticket_created",
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            user_id=user_id,
            reason=reason.value,
            priority=priority.value,
        )

        return ticket.to_dict()

    def get_user_message(
        self,
        reason: HandoffReason,
        priority: HandoffPriority,
        ticket_id: str = "",
    ) -> str:
        """Generate a user-facing message for the handoff.

        Returns a friendly message explaining the escalation.
        """
        messages = {
            HandoffReason.USER_REQUEST: (
                "Ich verbinde Sie gerne mit einem Mitarbeiter. "
                f"Ihr Ticket ({ticket_id}) wurde erstellt und ein Teammitglied "
                "wird sich in Kürze bei Ihnen melden."
            ),
            HandoffReason.LOW_CONFIDENCE: (
                "Ich bin mir bei dieser Anfrage nicht sicher genug, um Ihnen "
                "eine verlässliche Antwort zu geben. Ich habe daher ein Ticket "
                f"({ticket_id}) für unser Support-Team erstellt. "
                "Ein Mitarbeiter wird sich zeitnah bei Ihnen melden."
            ),
            HandoffReason.COMPLAINT: (
                "Ich verstehe, dass Sie unzufrieden sind, und das tut mir leid. "
                f"Ich habe Ihr Anliegen als Ticket ({ticket_id}) an unser Team "
                "weitergeleitet. Ein Mitarbeiter wird sich persönlich um Ihr "
                "Anliegen kümmern."
            ),
            HandoffReason.LEGAL_MATTER: (
                "Bei rechtlichen Angelegenheiten möchte ich Sie an unser "
                f"Fachteam weiterleiten. Ihr Ticket ({ticket_id}) wurde mit "
                "hoher Priorität erstellt."
            ),
            HandoffReason.CRITICAL_OPERATION: (
                "Diese Aktion erfordert eine manuelle Prüfung durch unser Team. "
                f"Ticket ({ticket_id}) wurde erstellt."
            ),
            HandoffReason.REPEATED_FAILURE: (
                "Es scheint, als könnte ich Ihnen bei diesem Anliegen nicht "
                f"optimal weiterhelfen. Ich habe ein Ticket ({ticket_id}) "
                "für unser Support-Team erstellt."
            ),
            HandoffReason.BILLING_DISPUTE: (
                "Abrechnungsfragen werden von unserem Finanzteam bearbeitet. "
                f"Ihr Ticket ({ticket_id}) wurde erstellt und wird prioritär "
                "behandelt."
            ),
        }

        return messages.get(
            reason,
            f"Ihr Anliegen wurde an unser Team weitergeleitet. "
            f"Ticket-ID: {ticket_id}",
        )

    def _generate_summary(self, reason: HandoffReason, context: str) -> str:
        """Generate a brief summary for the support team."""
        reason_labels = {
            HandoffReason.LOW_CONFIDENCE: "AI-Agent unsicher",
            HandoffReason.USER_REQUEST: "Nutzer wünscht menschlichen Kontakt",
            HandoffReason.CRITICAL_OPERATION: "Kritische Operation – manuelle Prüfung",
            HandoffReason.REPEATED_FAILURE: "Wiederholte Fehler im AI-Agent",
            HandoffReason.COMPLAINT: "Beschwerde",
            HandoffReason.COMPLEX_QUERY: "Komplexe Anfrage",
            HandoffReason.LEGAL_MATTER: "Rechtliche Angelegenheit",
            HandoffReason.BILLING_DISPUTE: "Abrechnungsstreit",
        }
        label = reason_labels.get(reason, "Eskalation")
        summary = f"[{label}]"
        if context:
            summary += f" {context[:200]}"
        return summary

    async def _notify_support_team(self, ticket: HandoffTicket) -> None:
        """Notify the support team about a new handoff ticket.

        In production, this would:
        - Send a Slack/Teams notification
        - Send an email to the support queue
        - Push to a ticketing system (Zendesk, Freshdesk, etc.)

        Current: Redis pub/sub notification.
        """
        try:
            from app.core.redis_keys import RedisKeyBuilder
            import redis.asyncio as aioredis
            import json

            # Publish to support notification channel
            key_builder = RedisKeyBuilder(ticket.tenant_id)
            channel = f"ariia:tenant:{ticket.tenant_id}:support:notifications"

            notification = {
                "type": "handoff_ticket",
                "ticket": ticket.to_dict(),
                "timestamp": time.time(),
            }

            # Try to publish – non-critical if Redis unavailable
            try:
                from config.settings import get_settings
                settings = get_settings()
                r = aioredis.from_url(settings.REDIS_URL)
                await r.publish(channel, json.dumps(notification))
                await r.close()
            except Exception:
                pass  # Redis notification is best-effort

        except Exception as e:
            logger.warning("handoff.notification_failed", error=str(e))

    async def _store_ticket(self, ticket: HandoffTicket) -> None:
        """Store the ticket in Redis for persistence.

        In production, this would also store in the database.
        """
        try:
            import redis.asyncio as aioredis
            import json

            from config.settings import get_settings
            settings = get_settings()
            r = aioredis.from_url(settings.REDIS_URL)

            key = f"ariia:tenant:{ticket.tenant_id}:handoff:{ticket.ticket_id}"
            await r.setex(
                key,
                86400 * 7,  # 7 days TTL
                json.dumps(ticket.to_dict()),
            )
            await r.close()

        except Exception as e:
            logger.warning("handoff.store_failed", error=str(e))

    # ─── Ticket Management ────────────────────────────────────────────────

    def get_ticket(self, ticket_id: str) -> Optional[HandoffTicket]:
        """Get a ticket by ID from in-memory store."""
        return self._tickets.get(ticket_id)

    def get_pending_tickets(self, tenant_id: Optional[int] = None) -> list[HandoffTicket]:
        """Get all pending tickets, optionally filtered by tenant."""
        tickets = [
            t for t in self._tickets.values()
            if t.status == HandoffStatus.PENDING
        ]
        if tenant_id is not None:
            tickets = [t for t in tickets if t.tenant_id == tenant_id]
        return sorted(tickets, key=lambda t: t.created_at, reverse=True)

    async def resolve_ticket(
        self,
        ticket_id: str,
        resolution: str = "",
        resolved_by: str = "",
    ) -> Optional[HandoffTicket]:
        """Mark a ticket as resolved."""
        ticket = self._tickets.get(ticket_id)
        if ticket:
            ticket.status = HandoffStatus.RESOLVED
            ticket.resolved_at = time.time()
            ticket.updated_at = time.time()
            ticket.metadata["resolution"] = resolution
            ticket.metadata["resolved_by"] = resolved_by

            logger.info(
                "handoff.ticket_resolved",
                ticket_id=ticket_id,
                resolved_by=resolved_by,
            )

            return ticket
        return None

    async def close_ticket(self, ticket_id: str) -> Optional[HandoffTicket]:
        """Close a ticket."""
        ticket = self._tickets.get(ticket_id)
        if ticket:
            ticket.status = HandoffStatus.CLOSED
            ticket.updated_at = time.time()
            return ticket
        return None
