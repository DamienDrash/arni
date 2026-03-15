"""ARIIA v1.4 – Swarm Router.

@BACKEND: Sprint 2, Task 2.2
GPT-4o-mini intent classifier → dispatches to correct sub-agent.
Fallback: keyword-based routing when LLM unavailable.
"""

import structlog

from app.gateway.schemas import InboundMessage
from app.swarm.agents.medic import AgentMedic
from app.swarm.agents.ops import AgentOps
from app.swarm.agents.persona import AgentPersona
from app.swarm.agents.sales import AgentSales
from app.swarm.agents.vision import AgentVision
from app.swarm.base import AgentResponse, BaseAgent
from app.swarm.master.orchestrator_v2 import MasterAgentV2
from app.swarm.llm import LLMClient
from app.swarm.router.intents import Intent
from app.core.feature_gates import FeatureGate
from fastapi import HTTPException

logger = structlog.get_logger()

class SwarmRouter:
    """Central router: classifies user intent → dispatches to sub-agent.

    Uses GPT-4o-mini for classification with keyword fallback.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        BaseAgent.set_llm(llm)  # Share LLM with all agents
        self._master = MasterAgentV2(llm)
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

        TITAN UPGRADE: 
        1. Check Feature Gate for channel availability.
        2. Emergency goes to Medic.
        3. EVERYTHING ELSE goes to Master.
        """
        # 0. PLATFORM CHECK (PR 4/5 - Feature Gating)
        gate = FeatureGate(message.tenant_id)
        try:
            gate.require_channel(message.platform)
        except HTTPException as exc:
            logger.warning(
                "router.channel_blocked",
                tenant_id=message.tenant_id,
                platform=message.platform,
                detail=exc.detail,
            )
            return AgentResponse(
                content=(
                    "Dieser Kommunikationskanal (z.B. Telegram/SMS) ist in deinem aktuellen ARIIA-Plan "
                    "nicht freigeschaltet. Bitte kontaktiere die Administration für ein Upgrade."
                )
            )

        content_lower = message.content.lower()

        # SAFETY: Emergency keywords always go to Medic (no LLM gamble)
        if any(kw in content_lower for kw in self.EMERGENCY_KEYWORDS):
            logger.critical(
                "router.emergency_hardroute",
                message_id=message.message_id,
            )
            return await self._agents[Intent.HEALTH].handle(message)

        # TITAN ORCHESTRATION: Arnold Prime takes over
        logger.info("router.titan_dispatch", agent="master", message_id=message.message_id)
        return await self._master.handle(message)

    @staticmethod
    def _keyword_classify(content: str) -> Intent:
        """Fallback keyword-based classification."""
        content = content.lower()

        keyword_map: dict[Intent, list[str]] = {
            Intent.BOOKING: [
                "buchen", "kurs", "reservieren", "termin", "check-in",
                "anmelden", "öffnungszeit", "wann", "book", "schedule",
                "trainer", "wer ist", "personal training",
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
                "profil", "ziele", "über mich", "erinnere",
                "weißt du noch", "weist du noch", "erinnerst du",
                "worauf muss ich achten", "meine pläne",
            ],
        }

        for intent, keywords in keyword_map.items():
            if any(kw in content for kw in keywords):
                return intent

        return Intent.UNKNOWN

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
