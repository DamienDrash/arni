"""ARIIA v1.4 – Swarm Router.

@BACKEND: Sprint 2, Task 2.2
GPT-4o-mini intent classifier → dispatches to correct sub-agent.
Fallback: keyword-based routing when LLM unavailable.
"""

import json
import re

import structlog

from app.gateway.persistence import persistence
from app.gateway.schemas import InboundMessage
from app.swarm.agents.medic import AgentMedic
from app.swarm.agents.ops import AgentOps
from app.swarm.agents.persona import AgentPersona
from app.swarm.agents.sales import AgentSales
from app.swarm.agents.vision import AgentVision
from app.swarm.base import AgentResponse, BaseAgent
from app.swarm.llm import LLMClient
from app.swarm.router.intents import Intent
from app.prompts.engine import get_engine
from app.prompts.context import build_tenant_context

logger = structlog.get_logger()

# Confidence threshold: below this, use UNKNOWN/fallback
CONFIDENCE_THRESHOLD = 0.6
AFFIRMATIVE_PATTERNS = {
    "ja",
    "ja bitte",
    "bitte",
    "gerne",
    "ok",
    "okay",
    "mach das",
    "passt",
    "einverstanden",
    "yes",
}


class SwarmRouter:
    """Central router: classifies user intent → dispatches to sub-agent.

    Uses GPT-4o-mini for classification with keyword fallback.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        BaseAgent.set_llm(llm)  # Share LLM with all agents
        self._agents: dict[Intent, BaseAgent] = {
            Intent.BOOKING: AgentOps(),
            Intent.SALES: AgentSales(),
            Intent.HEALTH: AgentMedic(),
            Intent.CROWD: AgentVision(),
            Intent.SMALLTALK: AgentPersona(),
        }

    # Emergency keywords: hard-route to Medic (AGENTS.md §2 – bypass LLM)
    EMERGENCY_KEYWORDS = [
        "herzinfarkt", "bewusstlos", "notarzt", "unfall",
        "heart attack", "unconscious", "emergency", "ohnmacht",
        "112", "notfall",
    ]
    BOOKING_ACTION_KEYWORDS = [
        "lösch", "loesch", "storn", "absag", "cancel", "entfern",
        "umbuch", "verschieb", "verschiebe",
    ]

    async def route(self, message: InboundMessage) -> AgentResponse:
        """Classify intent and dispatch to appropriate agent.

        Flow:
        0. Emergency keyword check → hard-route to Medic (safety first)
        1. Try LLM classification (GPT-4o-mini → Ollama fallback)
        2. If confidence < threshold → try keyword classification
        3. Dispatch to matched agent
        4. Return agent response

        Args:
            message: Normalized inbound message.

        Returns:
            AgentResponse from the dispatched agent.
        """
        content_lower = message.content.lower()

        # SAFETY: Emergency keywords always go to Medic (no LLM gamble)
        if any(kw in content_lower for kw in self.EMERGENCY_KEYWORDS):
            logger.critical(
                "router.emergency_hardroute",
                message_id=message.message_id,
            )
            return await self._agents[Intent.HEALTH].handle(message)

        # Deterministic override for booking actions (delete/reschedule etc.).
        if self._looks_like_booking_action(content_lower):
            intent, confidence = Intent.BOOKING, 0.99
            logger.info("router.context_override", intent=intent.value, reason="booking_action_keywords")
        else:
            # Context override: explicit dialog context has priority over keyword guessing.
            dialog_ctx = self._extract_dialog_context(message)
            pending_action = str(dialog_ctx.get("pending_action") or "").strip().lower()
            has_time_only = bool(re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", message.content or ""))
            if has_time_only and pending_action.startswith("book_appointment"):
                intent, confidence = Intent.BOOKING, 0.99
                logger.info("router.context_override", intent=intent.value, reason="dialog_context_time")
            elif self._is_affirmative(message.content) and pending_action.startswith("book_appointment"):
                intent, confidence = Intent.BOOKING, 0.99
                logger.info("router.context_override", intent=intent.value, reason="dialog_context")
            # Backward-compatible fallback: infer from recent assistant answers.
            elif self._is_affirmative(message.content) and self._has_recent_booking_context(message.user_id, message.tenant_id):
                intent, confidence = Intent.BOOKING, 0.99
                logger.info("router.context_override", intent=intent.value, reason="affirmative_followup")
            else:
                intent, confidence = await self._classify(
                    message.content,
                    user_id=message.user_id,
                    tenant_id=message.tenant_id,
                )

        # If LLM result is unreliable, try keywords
        if intent == Intent.UNKNOWN or confidence < CONFIDENCE_THRESHOLD:
            keyword_intent = self._keyword_classify(message.content)
            if keyword_intent != Intent.UNKNOWN:
                intent = keyword_intent
                confidence = 0.7
                logger.info("router.keyword_fallback", intent=intent.value)

        # Final fallback: persona (smalltalk)
        if intent == Intent.UNKNOWN:
            intent = Intent.SMALLTALK
            confidence = 0.4

        agent = self._agents[intent]
        logger.info(
            "router.dispatch",
            intent=intent.value,
            confidence=round(confidence, 2),
            agent=agent.name,
            message_id=message.message_id,
        )

        return await agent.handle(message)

    async def _classify(
        self,
        content: str,
        user_id: str | None = None,
        tenant_id: int | None = None,
    ) -> tuple[Intent, float]:
        """Classify intent using LLM.

        Expected LLM response format: "intent_name|confidence"
        Example: "booking|0.95"
        """
        try:
            context_lines = self._recent_context_for_router(user_id, limit=10, tenant_id=tenant_id)
            user_payload = content
            if context_lines:
                user_payload = (
                    "LETZTER VERLAUF (neueste unten):\n"
                    f"{context_lines}\n\n"
                    f"AKTUELLE NACHRICHT:\n{content}"
                )
            tid = tenant_id if tenant_id is not None else 0
            _tenant_slug = persistence.get_tenant_slug(tenant_id)
            _ctx = build_tenant_context(persistence, tid)
            router_prompt = get_engine().render_for_tenant("router/system.j2", _tenant_slug, **_ctx)

            # Resolve tenant-specific API key (BYOK)
            tenant_api_key = persistence.get_setting("openai_api_key", tenant_id=tenant_id)

            response = await self._llm.chat(
                messages=[
                    {"role": "system", "content": router_prompt},
                    {"role": "user", "content": user_payload},
                ],
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=20,
                api_key=tenant_api_key,
            )

            # Parse: "booking|0.95"
            parts = response.strip().lower().split("|")
            intent_str = parts[0].strip()
            confidence = float(parts[1]) if len(parts) > 1 else 0.5

            try:
                intent = Intent(intent_str)
            except ValueError:
                logger.warning("router.unknown_intent", raw=intent_str)
                return Intent.UNKNOWN, 0.0

            return intent, confidence

        except Exception as e:
            logger.error("router.classification_failed", error=str(e))
            return Intent.UNKNOWN, 0.0

    @staticmethod
    def _keyword_classify(content: str) -> Intent:
        """Fallback keyword-based classification."""
        content = content.lower()

        keyword_map: dict[Intent, list[str]] = {
            Intent.BOOKING: [
                "buchen", "kurs", "reservieren", "termin", "check-in",
                "anmelden", "öffnungszeit", "wann", "book", "schedule",
            ],
            Intent.SALES: [
                "kündigen", "vertrag", "preis", "kosten", "mitgliedschaft",
                "upgrade", "tarif", "cancel", "contract", "price",
            ],
            Intent.HEALTH: [
                "schmerz", "verletz", "training", "übung", "rücken",
                "knie", "schulter", "arzt", "gesund", "pain", "injury",
            ],
            Intent.CROWD: [
                "voll", "leer", "auslastung", "wie viele", "belegung",
                "crowded", "busy", "people", "besetzt",
            ],
            Intent.SMALLTALK: [
                "hey", "hallo", "hi", "danke", "servus", "moin",
                "wetter", "wie geht", "lust", "bock",
            ],
        }

        for intent, keywords in keyword_map.items():
            if any(kw in content for kw in keywords):
                return intent

        return Intent.UNKNOWN

    def get_agent(self, intent: Intent) -> BaseAgent | None:
        """Get agent by intent (for direct access)."""
        return self._agents.get(intent)

    @staticmethod
    def _is_affirmative(content: str) -> bool:
        cleaned = re.sub(r"[^\w\s]", " ", (content or "").lower())
        cleaned = " ".join(cleaned.split())
        return cleaned in AFFIRMATIVE_PATTERNS

    @staticmethod
    def _has_recent_booking_context(user_id: str, tenant_id: int | None = None) -> bool:
        history = persistence.get_chat_history(str(user_id), limit=10, tenant_id=tenant_id)
        if not history:
            return False
        timeline = [
            (getattr(m, "role", ""), (getattr(m, "content", "") or "").lower())
            for m in history
        ]
        i = len(timeline) - 1
        while i >= 0 and timeline[i][0] == "user" and SwarmRouter._is_affirmative(timeline[i][1]):
            i -= 1

        while i >= 0:
            role, text = timeline[i]
            if role == "assistant" and SwarmRouter._assistant_has_booking_prompt(text):
                return True
            if role == "user" and not SwarmRouter._is_affirmative(text):
                break
            i -= 1
        return False

    @staticmethod
    def _assistant_has_booking_prompt(text: str) -> bool:
        has_time = bool(re.search(r"\b([01]\d|2[0-3]):([0-5]\d)\b", text))
        has_booking_prompt = (
            "moechtest du" in text
            or "möchtest du" in text
            or "freie termine" in text
            or "verfügbare termine" in text
            or "buch" in text
        )
        return has_time and has_booking_prompt

    @classmethod
    def _looks_like_booking_action(cls, content: str) -> bool:
        if not any(k in content for k in cls.BOOKING_ACTION_KEYWORDS):
            return False
        # "Bitte loeschen" without further nouns should still stay in booking domain.
        if any(k in content for k in ("lösch", "loesch", "storn", "absag", "cancel")):
            return True
        booking_nouns = ("termin", "kurs", "buchung", "uhr", "heute", "morgen")
        has_time = bool(re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", content or ""))
        return has_time or any(n in content for n in booking_nouns)

    @staticmethod
    def _recent_context_for_router(user_id: str | None, limit: int = 10, tenant_id: int | None = None) -> str:
        if not user_id:
            return ""
        try:
            history = persistence.get_chat_history(
                str(user_id),
                limit=max(1, int(limit)),
                tenant_id=tenant_id,
            )
            lines: list[str] = []
            for item in history[-limit:]:
                role = str(getattr(item, "role", "") or "").lower()
                if role not in {"user", "assistant"}:
                    continue
                content = str(getattr(item, "content", "") or "").strip()
                if not content:
                    continue
                content = content.replace("\n", " ").strip()
                lines.append(f"{role}: {content[:220]}")
            return "\n".join(lines)
        except Exception:
            return ""

    @staticmethod
    def _extract_dialog_context(message: InboundMessage) -> dict:
        metadata = message.metadata or {}
        value = metadata.get("dialog_context")
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}
