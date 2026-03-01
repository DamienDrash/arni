"""app/platform/ghost_mode_v2.py — Ghost Mode v2: Live-Monitoring & Intervention Engine.

Extends the existing Ghost Mode WebSocket with:
1. Structured event streaming (typed events, not just raw messages)
2. Intervention Engine: Admin can inject messages, pause/resume agent, take over
3. Conversation Scoring: Real-time quality scoring of active conversations
4. Knowledge Gap Analysis: Detects topics where the agent lacks knowledge
5. Session Recording: Full audit trail of ghost mode sessions
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════════════
# GHOST MODE EVENT TYPES
# ══════════════════════════════════════════════════════════════════════════════

class GhostEventType(str, Enum):
    """Types of events in Ghost Mode v2."""
    # Conversation events
    MESSAGE_IN = "ghost.message_in"
    MESSAGE_OUT = "ghost.message_out"
    CONVERSATION_START = "ghost.conversation_start"
    CONVERSATION_END = "ghost.conversation_end"

    # Agent events
    AGENT_THINKING = "ghost.agent_thinking"
    AGENT_TOOL_CALL = "ghost.agent_tool_call"
    AGENT_HANDOFF = "ghost.agent_handoff"
    AGENT_ERROR = "ghost.agent_error"

    # Intervention events
    ADMIN_TAKEOVER = "ghost.admin_takeover"
    ADMIN_RELEASE = "ghost.admin_release"
    ADMIN_INJECT = "ghost.admin_inject"
    ADMIN_PAUSE = "ghost.admin_pause"
    ADMIN_RESUME = "ghost.admin_resume"

    # Quality events
    QUALITY_ALERT = "ghost.quality_alert"
    KNOWLEDGE_GAP = "ghost.knowledge_gap"
    ESCALATION_DETECTED = "ghost.escalation_detected"
    SENTIMENT_SHIFT = "ghost.sentiment_shift"

    # System events
    SYSTEM_STATUS = "ghost.system_status"
    SESSION_RECORDING = "ghost.session_recording"


class InterventionType(str, Enum):
    """Types of admin interventions."""
    INJECT_MESSAGE = "inject_message"  # Send a message as the agent
    TAKEOVER = "takeover"  # Full conversation takeover
    RELEASE = "release"  # Release takeover back to agent
    PAUSE_AGENT = "pause_agent"  # Pause agent responses
    RESUME_AGENT = "resume_agent"  # Resume agent responses
    WHISPER = "whisper"  # Send a note only visible to admins
    SUGGEST = "suggest"  # Suggest a response to the agent
    FORCE_ESCALATE = "force_escalate"  # Force escalation to human


class ConversationStatus(str, Enum):
    """Status of a monitored conversation."""
    ACTIVE = "active"
    PAUSED = "paused"
    TAKEN_OVER = "taken_over"
    ESCALATED = "escalated"
    ENDED = "ended"


# ══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GhostEvent:
    """A structured event in Ghost Mode v2."""
    event_type: GhostEventType
    tenant_id: int
    conversation_id: str = ""
    user_id: str = ""
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "type": self.event_type.value,
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ConversationScore:
    """Real-time quality score for a conversation."""
    conversation_id: str
    tenant_id: int

    # Scores (0.0 - 1.0)
    relevance_score: float = 1.0  # How relevant are agent responses
    sentiment_score: float = 0.5  # User sentiment (0=negative, 1=positive)
    resolution_score: float = 0.5  # Likelihood of resolution
    coherence_score: float = 1.0  # Agent response coherence

    # Counters
    message_count: int = 0
    user_message_count: int = 0
    agent_message_count: int = 0
    tool_call_count: int = 0
    error_count: int = 0

    # Flags
    has_knowledge_gap: bool = False
    has_escalation_signal: bool = False
    needs_attention: bool = False

    # Timing
    avg_response_time_ms: float = 0.0
    _response_times: list[float] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Weighted overall quality score."""
        weights = {
            "relevance": 0.3,
            "sentiment": 0.25,
            "resolution": 0.25,
            "coherence": 0.2,
        }
        return (
            self.relevance_score * weights["relevance"]
            + self.sentiment_score * weights["sentiment"]
            + self.resolution_score * weights["resolution"]
            + self.coherence_score * weights["coherence"]
        )

    def add_response_time(self, ms: float):
        self._response_times.append(ms)
        self.avg_response_time_ms = sum(self._response_times) / len(self._response_times)

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "overall_score": round(self.overall_score, 3),
            "relevance": round(self.relevance_score, 3),
            "sentiment": round(self.sentiment_score, 3),
            "resolution": round(self.resolution_score, 3),
            "coherence": round(self.coherence_score, 3),
            "message_count": self.message_count,
            "tool_calls": self.tool_call_count,
            "errors": self.error_count,
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "flags": {
                "knowledge_gap": self.has_knowledge_gap,
                "escalation_signal": self.has_escalation_signal,
                "needs_attention": self.needs_attention,
            },
        }


@dataclass
class KnowledgeGap:
    """Detected knowledge gap in a conversation."""
    gap_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    tenant_id: int = 0
    conversation_id: str = ""
    topic: str = ""
    user_query: str = ""
    agent_response: str = ""
    confidence: float = 0.0  # How confident we are this is a gap
    category: str = "unknown"
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "gap_id": self.gap_id,
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "topic": self.topic,
            "user_query": self.user_query,
            "confidence": round(self.confidence, 3),
            "category": self.category,
            "detected_at": self.detected_at.isoformat(),
            "resolved": self.resolved,
        }


@dataclass
class InterventionRecord:
    """Record of an admin intervention."""
    intervention_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tenant_id: int = 0
    conversation_id: str = ""
    admin_user_id: int = 0
    admin_email: str = ""
    intervention_type: InterventionType = InterventionType.INJECT_MESSAGE
    content: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "intervention_id": self.intervention_id,
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "admin_email": self.admin_email,
            "type": self.intervention_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GAP DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

class KnowledgeGapDetector:
    """Detects knowledge gaps from conversation patterns.

    Identifies situations where:
    - Agent gives vague/generic responses to specific questions
    - Agent explicitly says it doesn't know
    - User repeats the same question (agent didn't answer satisfactorily)
    - Agent falls back to general responses for domain-specific queries
    """

    # Patterns indicating the agent doesn't know
    UNCERTAINTY_PATTERNS = [
        "ich bin mir nicht sicher",
        "das kann ich leider nicht",
        "dazu habe ich keine informationen",
        "das weiß ich leider nicht",
        "ich habe dazu keine daten",
        "i'm not sure",
        "i don't have information",
        "i cannot answer that",
        "let me check",
        "ich muss nachfragen",
        "das übersteigt meine",
        "dafür bin ich nicht zuständig",
        "keine angaben",
        "nicht verfügbar",
    ]

    # Patterns indicating user frustration (question repetition)
    FRUSTRATION_PATTERNS = [
        "ich habe schon gefragt",
        "nochmal:",
        "wie ich bereits sagte",
        "ich wiederhole",
        "das beantwortet nicht meine frage",
        "das hilft mir nicht",
        "i already asked",
        "as i said",
        "that doesn't answer",
        "that's not helpful",
    ]

    # Domain-specific topic categories
    TOPIC_CATEGORIES = {
        "pricing": ["preis", "kosten", "tarif", "price", "cost", "plan", "abo", "subscription"],
        "scheduling": ["termin", "buchen", "stornieren", "appointment", "book", "cancel", "kurs"],
        "membership": ["mitglied", "vertrag", "kündigung", "member", "contract", "cancel"],
        "technical": ["fehler", "problem", "funktioniert nicht", "error", "bug", "broken"],
        "product": ["produkt", "angebot", "service", "leistung", "product", "offering"],
        "policy": ["regel", "richtlinie", "policy", "agb", "terms", "bedingung"],
        "location": ["adresse", "öffnungszeiten", "standort", "address", "hours", "location"],
    }

    def __init__(self):
        self._gaps: dict[int, list[KnowledgeGap]] = defaultdict(list)  # tenant_id -> gaps
        self._conversation_queries: dict[str, list[str]] = defaultdict(list)  # conv_id -> queries

    def analyze_exchange(
        self,
        tenant_id: int,
        conversation_id: str,
        user_message: str,
        agent_response: str,
    ) -> Optional[KnowledgeGap]:
        """Analyze a user-agent exchange for knowledge gaps.

        Returns a KnowledgeGap if one is detected, None otherwise.
        """
        user_lower = user_message.lower()
        agent_lower = agent_response.lower()

        confidence = 0.0
        topic = ""
        category = "unknown"

        # Check for uncertainty patterns in agent response
        for pattern in self.UNCERTAINTY_PATTERNS:
            if pattern in agent_lower:
                confidence += 0.4
                break

        # Check for user frustration
        for pattern in self.FRUSTRATION_PATTERNS:
            if pattern in user_lower:
                confidence += 0.3
                break

        # Check for repeated questions
        prev_queries = self._conversation_queries.get(conversation_id, [])
        for prev_q in prev_queries:
            if self._similarity(user_lower, prev_q) > 0.7:
                confidence += 0.3
                break
        self._conversation_queries[conversation_id].append(user_lower)

        # Detect topic category
        for cat, keywords in self.TOPIC_CATEGORIES.items():
            if any(kw in user_lower for kw in keywords):
                category = cat
                topic = cat
                break

        # Extract topic from user message (first noun phrase approximation)
        if not topic:
            words = user_message.split()
            topic = " ".join(words[:5]) if len(words) > 5 else user_message

        # Short agent responses to specific questions suggest a gap
        if len(user_message) > 30 and len(agent_response) < 50:
            confidence += 0.2

        # Only report if confidence is above threshold
        if confidence >= 0.4:
            gap = KnowledgeGap(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                topic=topic,
                user_query=user_message[:500],
                agent_response=agent_response[:500],
                confidence=min(confidence, 1.0),
                category=category,
            )
            self._gaps[tenant_id].append(gap)

            logger.info("knowledge_gap.detected",
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        topic=topic,
                        category=category,
                        confidence=round(confidence, 2))

            return gap

        return None

    def get_gaps(
        self,
        tenant_id: int,
        category: str = "",
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[KnowledgeGap]:
        """Get detected knowledge gaps for a tenant."""
        gaps = self._gaps.get(tenant_id, [])
        if category:
            gaps = [g for g in gaps if g.category == category]
        if min_confidence > 0:
            gaps = [g for g in gaps if g.confidence >= min_confidence]
        # Sort by confidence descending
        gaps.sort(key=lambda g: g.confidence, reverse=True)
        return gaps[:limit]

    def get_gap_summary(self, tenant_id: int) -> dict:
        """Get a summary of knowledge gaps by category."""
        gaps = self._gaps.get(tenant_id, [])
        summary = defaultdict(lambda: {"count": 0, "avg_confidence": 0.0, "topics": []})

        for gap in gaps:
            cat = gap.category
            summary[cat]["count"] += 1
            summary[cat]["avg_confidence"] += gap.confidence
            if gap.topic not in summary[cat]["topics"]:
                summary[cat]["topics"].append(gap.topic)

        # Calculate averages
        for cat in summary:
            if summary[cat]["count"] > 0:
                summary[cat]["avg_confidence"] /= summary[cat]["count"]
                summary[cat]["avg_confidence"] = round(summary[cat]["avg_confidence"], 3)
            summary[cat]["topics"] = summary[cat]["topics"][:10]

        return {
            "tenant_id": tenant_id,
            "total_gaps": len(gaps),
            "unresolved": len([g for g in gaps if not g.resolved]),
            "categories": dict(summary),
        }

    def resolve_gap(self, tenant_id: int, gap_id: str) -> bool:
        """Mark a knowledge gap as resolved."""
        for gap in self._gaps.get(tenant_id, []):
            if gap.gap_id == gap_id:
                gap.resolved = True
                return True
        return False

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Simple Jaccard similarity between two strings."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)


# ══════════════════════════════════════════════════════════════════════════════
# INTERVENTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class InterventionEngine:
    """Manages admin interventions in live conversations.

    Supports:
    - Message injection (send as agent)
    - Full takeover (agent paused, admin responds)
    - Pause/resume agent
    - Whisper (admin-only notes)
    - Forced escalation
    """

    def __init__(self):
        self._conversation_states: dict[str, ConversationStatus] = {}
        self._takeover_admins: dict[str, dict] = {}  # conv_id -> admin info
        self._intervention_history: dict[int, list[InterventionRecord]] = defaultdict(list)
        self._paused_conversations: set[str] = set()

    def inject_message(
        self,
        tenant_id: int,
        conversation_id: str,
        admin_user_id: int,
        admin_email: str,
        content: str,
    ) -> InterventionRecord:
        """Inject a message into a conversation as the agent."""
        record = InterventionRecord(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            intervention_type=InterventionType.INJECT_MESSAGE,
            content=content,
        )
        self._intervention_history[tenant_id].append(record)

        logger.info("intervention.inject",
                     tenant_id=tenant_id,
                     conversation_id=conversation_id,
                     admin=admin_email)

        return record

    def takeover(
        self,
        tenant_id: int,
        conversation_id: str,
        admin_user_id: int,
        admin_email: str,
    ) -> InterventionRecord:
        """Take over a conversation (pause agent, admin responds)."""
        self._conversation_states[conversation_id] = ConversationStatus.TAKEN_OVER
        self._takeover_admins[conversation_id] = {
            "admin_user_id": admin_user_id,
            "admin_email": admin_email,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self._paused_conversations.add(conversation_id)

        record = InterventionRecord(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            intervention_type=InterventionType.TAKEOVER,
        )
        self._intervention_history[tenant_id].append(record)

        logger.info("intervention.takeover",
                     tenant_id=tenant_id,
                     conversation_id=conversation_id,
                     admin=admin_email)

        return record

    def release(
        self,
        tenant_id: int,
        conversation_id: str,
        admin_user_id: int,
        admin_email: str,
    ) -> InterventionRecord:
        """Release a taken-over conversation back to the agent."""
        self._conversation_states[conversation_id] = ConversationStatus.ACTIVE
        self._takeover_admins.pop(conversation_id, None)
        self._paused_conversations.discard(conversation_id)

        record = InterventionRecord(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            intervention_type=InterventionType.RELEASE,
        )
        self._intervention_history[tenant_id].append(record)

        logger.info("intervention.release",
                     tenant_id=tenant_id,
                     conversation_id=conversation_id,
                     admin=admin_email)

        return record

    def pause_agent(self, tenant_id: int, conversation_id: str, admin_email: str) -> InterventionRecord:
        """Pause agent responses for a conversation."""
        self._paused_conversations.add(conversation_id)
        self._conversation_states[conversation_id] = ConversationStatus.PAUSED

        record = InterventionRecord(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            admin_email=admin_email,
            intervention_type=InterventionType.PAUSE_AGENT,
        )
        self._intervention_history[tenant_id].append(record)
        return record

    def resume_agent(self, tenant_id: int, conversation_id: str, admin_email: str) -> InterventionRecord:
        """Resume agent responses for a conversation."""
        self._paused_conversations.discard(conversation_id)
        self._conversation_states[conversation_id] = ConversationStatus.ACTIVE

        record = InterventionRecord(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            admin_email=admin_email,
            intervention_type=InterventionType.RESUME_AGENT,
        )
        self._intervention_history[tenant_id].append(record)
        return record

    def force_escalate(
        self,
        tenant_id: int,
        conversation_id: str,
        admin_email: str,
        reason: str = "",
    ) -> InterventionRecord:
        """Force escalation of a conversation to human support."""
        self._conversation_states[conversation_id] = ConversationStatus.ESCALATED

        record = InterventionRecord(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            admin_email=admin_email,
            intervention_type=InterventionType.FORCE_ESCALATE,
            content=reason,
        )
        self._intervention_history[tenant_id].append(record)

        logger.info("intervention.force_escalate",
                     tenant_id=tenant_id,
                     conversation_id=conversation_id,
                     reason=reason)

        return record

    def is_paused(self, conversation_id: str) -> bool:
        """Check if a conversation's agent is paused."""
        return conversation_id in self._paused_conversations

    def is_taken_over(self, conversation_id: str) -> bool:
        """Check if a conversation is taken over by an admin."""
        return self._conversation_states.get(conversation_id) == ConversationStatus.TAKEN_OVER

    def get_conversation_status(self, conversation_id: str) -> ConversationStatus:
        """Get the current status of a conversation."""
        return self._conversation_states.get(conversation_id, ConversationStatus.ACTIVE)

    def get_takeover_admin(self, conversation_id: str) -> Optional[dict]:
        """Get info about the admin who took over a conversation."""
        return self._takeover_admins.get(conversation_id)

    def get_intervention_history(
        self,
        tenant_id: int,
        conversation_id: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """Get intervention history for a tenant."""
        records = self._intervention_history.get(tenant_id, [])
        if conversation_id:
            records = [r for r in records if r.conversation_id == conversation_id]
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return [r.to_dict() for r in records[:limit]]


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATION MONITOR
# ══════════════════════════════════════════════════════════════════════════════

class ConversationMonitor:
    """Monitors active conversations and computes real-time quality scores."""

    # Negative sentiment indicators
    NEGATIVE_INDICATORS = [
        "schlecht", "enttäuscht", "ärgerlich", "frustriert", "unzufrieden",
        "problem", "fehler", "falsch", "bad", "disappointed", "frustrated",
        "angry", "wrong", "terrible", "awful", "worst",
    ]

    # Positive sentiment indicators
    POSITIVE_INDICATORS = [
        "danke", "super", "toll", "perfekt", "hilfreich", "zufrieden",
        "great", "thanks", "perfect", "helpful", "excellent", "awesome",
        "wonderful", "satisfied",
    ]

    def __init__(self):
        self._scores: dict[str, ConversationScore] = {}
        self._last_user_message_time: dict[str, float] = {}

    def get_or_create_score(self, conversation_id: str, tenant_id: int) -> ConversationScore:
        """Get or create a conversation score tracker."""
        if conversation_id not in self._scores:
            self._scores[conversation_id] = ConversationScore(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
            )
        return self._scores[conversation_id]

    def record_user_message(self, conversation_id: str, tenant_id: int, message: str):
        """Record a user message and update scores."""
        score = self.get_or_create_score(conversation_id, tenant_id)
        score.message_count += 1
        score.user_message_count += 1
        self._last_user_message_time[conversation_id] = time.time()

        # Update sentiment
        msg_lower = message.lower()
        neg_count = sum(1 for w in self.NEGATIVE_INDICATORS if w in msg_lower)
        pos_count = sum(1 for w in self.POSITIVE_INDICATORS if w in msg_lower)

        if neg_count > 0 or pos_count > 0:
            sentiment_delta = (pos_count - neg_count) * 0.1
            score.sentiment_score = max(0.0, min(1.0, score.sentiment_score + sentiment_delta))

        # Check if needs attention (many user messages without resolution)
        if score.user_message_count > 5 and score.sentiment_score < 0.3:
            score.needs_attention = True

    def record_agent_response(self, conversation_id: str, tenant_id: int, response: str):
        """Record an agent response and update scores."""
        score = self.get_or_create_score(conversation_id, tenant_id)
        score.message_count += 1
        score.agent_message_count += 1

        # Calculate response time
        if conversation_id in self._last_user_message_time:
            response_time_ms = (time.time() - self._last_user_message_time[conversation_id]) * 1000
            score.add_response_time(response_time_ms)

        # Update coherence based on response length
        if len(response) < 10:
            score.coherence_score = max(0.0, score.coherence_score - 0.1)

    def record_tool_call(self, conversation_id: str, tenant_id: int):
        """Record a tool call in the conversation."""
        score = self.get_or_create_score(conversation_id, tenant_id)
        score.tool_call_count += 1
        # Tool calls generally indicate the agent is working on the problem
        score.resolution_score = min(1.0, score.resolution_score + 0.05)

    def record_error(self, conversation_id: str, tenant_id: int):
        """Record an error in the conversation."""
        score = self.get_or_create_score(conversation_id, tenant_id)
        score.error_count += 1
        score.relevance_score = max(0.0, score.relevance_score - 0.15)
        score.needs_attention = True

    def record_knowledge_gap(self, conversation_id: str, tenant_id: int):
        """Record a knowledge gap detection."""
        score = self.get_or_create_score(conversation_id, tenant_id)
        score.has_knowledge_gap = True
        score.relevance_score = max(0.0, score.relevance_score - 0.1)

    def record_escalation_signal(self, conversation_id: str, tenant_id: int):
        """Record an escalation signal."""
        score = self.get_or_create_score(conversation_id, tenant_id)
        score.has_escalation_signal = True
        score.needs_attention = True

    def get_score(self, conversation_id: str) -> Optional[ConversationScore]:
        """Get the current score for a conversation."""
        return self._scores.get(conversation_id)

    def get_active_scores(self, tenant_id: int) -> list[dict]:
        """Get all active conversation scores for a tenant."""
        scores = [
            s.to_dict() for s in self._scores.values()
            if s.tenant_id == tenant_id
        ]
        # Sort by needs_attention first, then by overall_score ascending
        scores.sort(key=lambda s: (not s["flags"]["needs_attention"], s["overall_score"]))
        return scores

    def get_attention_needed(self, tenant_id: int) -> list[dict]:
        """Get conversations that need admin attention."""
        return [
            s.to_dict() for s in self._scores.values()
            if s.tenant_id == tenant_id and s.needs_attention
        ]

    def end_conversation(self, conversation_id: str) -> Optional[dict]:
        """End monitoring for a conversation and return final score."""
        score = self._scores.pop(conversation_id, None)
        self._last_user_message_time.pop(conversation_id, None)
        return score.to_dict() if score else None


# ══════════════════════════════════════════════════════════════════════════════
# GHOST MODE V2 MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class GhostModeV2:
    """Central manager for Ghost Mode v2 functionality.

    Coordinates:
    - ConversationMonitor (quality scoring)
    - InterventionEngine (admin actions)
    - KnowledgeGapDetector (gap analysis)
    - Event streaming (to WebSocket)
    """

    def __init__(self):
        self.monitor = ConversationMonitor()
        self.intervention = InterventionEngine()
        self.gap_detector = KnowledgeGapDetector()
        self._event_listeners: dict[int, list] = defaultdict(list)  # tenant_id -> callbacks

    def register_listener(self, tenant_id: int, callback):
        """Register an event listener for a tenant (e.g., WebSocket broadcast)."""
        self._event_listeners[tenant_id].append(callback)

    def unregister_listener(self, tenant_id: int, callback):
        """Unregister an event listener."""
        if tenant_id in self._event_listeners:
            self._event_listeners[tenant_id] = [
                cb for cb in self._event_listeners[tenant_id] if cb != callback
            ]

    async def emit_event(self, event: GhostEvent):
        """Emit an event to all listeners for the tenant."""
        listeners = self._event_listeners.get(event.tenant_id, [])
        for listener in listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event.to_dict())
                else:
                    listener(event.to_dict())
            except Exception as e:
                logger.error("ghost.emit_failed", error=str(e))

    async def on_user_message(
        self,
        tenant_id: int,
        conversation_id: str,
        user_id: str,
        message: str,
        platform: str = "whatsapp",
    ):
        """Process an incoming user message."""
        # Update monitor
        self.monitor.record_user_message(conversation_id, tenant_id, message)

        # Emit event
        await self.emit_event(GhostEvent(
            event_type=GhostEventType.MESSAGE_IN,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            user_id=user_id,
            data={
                "message": message,
                "platform": platform,
                "score": self.monitor.get_score(conversation_id).to_dict()
                if self.monitor.get_score(conversation_id) else {},
            },
        ))

    async def on_agent_response(
        self,
        tenant_id: int,
        conversation_id: str,
        user_id: str,
        response: str,
        user_message: str = "",
    ):
        """Process an agent response."""
        # Update monitor
        self.monitor.record_agent_response(conversation_id, tenant_id, response)

        # Check for knowledge gaps
        if user_message:
            gap = self.gap_detector.analyze_exchange(
                tenant_id, conversation_id, user_message, response
            )
            if gap:
                self.monitor.record_knowledge_gap(conversation_id, tenant_id)
                await self.emit_event(GhostEvent(
                    event_type=GhostEventType.KNOWLEDGE_GAP,
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    data=gap.to_dict(),
                ))

        # Emit response event
        score = self.monitor.get_score(conversation_id)
        await self.emit_event(GhostEvent(
            event_type=GhostEventType.MESSAGE_OUT,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            user_id=user_id,
            data={
                "response": response,
                "score": score.to_dict() if score else {},
            },
        ))

        # Check if attention needed
        if score and score.needs_attention:
            await self.emit_event(GhostEvent(
                event_type=GhostEventType.QUALITY_ALERT,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                user_id=user_id,
                data={
                    "reason": "low_quality_score",
                    "overall_score": score.overall_score,
                    "details": score.to_dict(),
                },
            ))

    async def on_tool_call(
        self,
        tenant_id: int,
        conversation_id: str,
        tool_name: str,
        tool_args: dict,
    ):
        """Process a tool call by the agent."""
        self.monitor.record_tool_call(conversation_id, tenant_id)

        await self.emit_event(GhostEvent(
            event_type=GhostEventType.AGENT_TOOL_CALL,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            data={"tool": tool_name, "args": tool_args},
        ))

    async def on_error(
        self,
        tenant_id: int,
        conversation_id: str,
        error: str,
    ):
        """Process an agent error."""
        self.monitor.record_error(conversation_id, tenant_id)

        await self.emit_event(GhostEvent(
            event_type=GhostEventType.AGENT_ERROR,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            data={"error": error},
        ))

    def should_agent_respond(self, conversation_id: str) -> bool:
        """Check if the agent should respond (not paused/taken over)."""
        return (
            not self.intervention.is_paused(conversation_id)
            and not self.intervention.is_taken_over(conversation_id)
        )

    def get_dashboard_state(self, tenant_id: int) -> dict:
        """Get the full dashboard state for Ghost Mode v2."""
        return {
            "active_conversations": self.monitor.get_active_scores(tenant_id),
            "attention_needed": self.monitor.get_attention_needed(tenant_id),
            "knowledge_gaps": self.gap_detector.get_gap_summary(tenant_id),
            "recent_interventions": self.intervention.get_intervention_history(tenant_id, limit=20),
        }


# ══════════════════════════════════════════════════════════════════════════════
# GHOST MODE V2 API ROUTER
# ══════════════════════════════════════════════════════════════════════════════

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class InterventionRequest(BaseModel):
    conversation_id: str
    admin_email: str = "admin@ariia.io"
    admin_user_id: int = 0
    content: str = ""
    reason: str = ""


# Global instance
_ghost_mode_v2: Optional[GhostModeV2] = None


def get_ghost_mode_v2() -> GhostModeV2:
    global _ghost_mode_v2
    if _ghost_mode_v2 is None:
        _ghost_mode_v2 = GhostModeV2()
    return _ghost_mode_v2


def create_ghost_mode_v2_router() -> APIRouter:
    """Create the Ghost Mode v2 API router."""
    router = APIRouter(prefix="/api/v1/ghost", tags=["ghost-mode-v2"])

    @router.get("/dashboard/{tenant_id}")
    async def get_dashboard(tenant_id: int):
        """Get the full Ghost Mode v2 dashboard state."""
        gm = get_ghost_mode_v2()
        return gm.get_dashboard_state(tenant_id)

    @router.get("/conversations/{tenant_id}")
    async def get_active_conversations(tenant_id: int):
        """Get all active conversations with quality scores."""
        gm = get_ghost_mode_v2()
        return {"conversations": gm.monitor.get_active_scores(tenant_id)}

    @router.get("/attention/{tenant_id}")
    async def get_attention_needed(tenant_id: int):
        """Get conversations that need admin attention."""
        gm = get_ghost_mode_v2()
        return {"conversations": gm.monitor.get_attention_needed(tenant_id)}

    @router.post("/intervene/inject/{tenant_id}")
    async def inject_message(tenant_id: int, req: InterventionRequest):
        """Inject a message into a conversation as the agent."""
        gm = get_ghost_mode_v2()
        record = gm.intervention.inject_message(
            tenant_id, req.conversation_id,
            req.admin_user_id, req.admin_email, req.content
        )
        return record.to_dict()

    @router.post("/intervene/takeover/{tenant_id}")
    async def takeover_conversation(tenant_id: int, req: InterventionRequest):
        """Take over a conversation."""
        gm = get_ghost_mode_v2()
        record = gm.intervention.takeover(
            tenant_id, req.conversation_id,
            req.admin_user_id, req.admin_email
        )
        return record.to_dict()

    @router.post("/intervene/release/{tenant_id}")
    async def release_conversation(tenant_id: int, req: InterventionRequest):
        """Release a taken-over conversation."""
        gm = get_ghost_mode_v2()
        record = gm.intervention.release(
            tenant_id, req.conversation_id,
            req.admin_user_id, req.admin_email
        )
        return record.to_dict()

    @router.post("/intervene/pause/{tenant_id}")
    async def pause_agent(tenant_id: int, req: InterventionRequest):
        """Pause agent responses for a conversation."""
        gm = get_ghost_mode_v2()
        record = gm.intervention.pause_agent(
            tenant_id, req.conversation_id, req.admin_email
        )
        return record.to_dict()

    @router.post("/intervene/resume/{tenant_id}")
    async def resume_agent(tenant_id: int, req: InterventionRequest):
        """Resume agent responses for a conversation."""
        gm = get_ghost_mode_v2()
        record = gm.intervention.resume_agent(
            tenant_id, req.conversation_id, req.admin_email
        )
        return record.to_dict()

    @router.post("/intervene/escalate/{tenant_id}")
    async def force_escalate(tenant_id: int, req: InterventionRequest):
        """Force escalation of a conversation."""
        gm = get_ghost_mode_v2()
        record = gm.intervention.force_escalate(
            tenant_id, req.conversation_id, req.admin_email, req.reason
        )
        return record.to_dict()

    @router.get("/interventions/{tenant_id}")
    async def get_interventions(tenant_id: int, conversation_id: str = "", limit: int = 50):
        """Get intervention history."""
        gm = get_ghost_mode_v2()
        return {
            "interventions": gm.intervention.get_intervention_history(
                tenant_id, conversation_id, limit
            )
        }

    @router.get("/knowledge-gaps/{tenant_id}")
    async def get_knowledge_gaps(
        tenant_id: int,
        category: str = "",
        min_confidence: float = 0.0,
        limit: int = 50,
    ):
        """Get detected knowledge gaps."""
        gm = get_ghost_mode_v2()
        gaps = gm.gap_detector.get_gaps(tenant_id, category, min_confidence, limit)
        return {"gaps": [g.to_dict() for g in gaps]}

    @router.get("/knowledge-gaps/{tenant_id}/summary")
    async def get_knowledge_gap_summary(tenant_id: int):
        """Get knowledge gap summary by category."""
        gm = get_ghost_mode_v2()
        return gm.gap_detector.get_gap_summary(tenant_id)

    @router.post("/knowledge-gaps/{tenant_id}/resolve/{gap_id}")
    async def resolve_knowledge_gap(tenant_id: int, gap_id: str):
        """Mark a knowledge gap as resolved."""
        gm = get_ghost_mode_v2()
        if not gm.gap_detector.resolve_gap(tenant_id, gap_id):
            raise HTTPException(404, "Knowledge gap not found")
        return {"status": "resolved", "gap_id": gap_id}

    @router.get("/conversation/{conversation_id}/status")
    async def get_conversation_status(conversation_id: str):
        """Get the status of a specific conversation."""
        gm = get_ghost_mode_v2()
        status = gm.intervention.get_conversation_status(conversation_id)
        score = gm.monitor.get_score(conversation_id)
        takeover_admin = gm.intervention.get_takeover_admin(conversation_id)
        return {
            "conversation_id": conversation_id,
            "status": status.value,
            "score": score.to_dict() if score else None,
            "takeover_admin": takeover_admin,
        }

    return router
