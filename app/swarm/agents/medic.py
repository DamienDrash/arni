"""ARIIA v1.4 – Agent Medic (The Coach).

@BACKEND: Sprint 2 → Sprint 9 (LLM-powered)
Handles health-related queries with MANDATORY disclaimer.
CONSTRAINT: ALWAYS includes „Ich bin kein Arzt" disclaimer (AGENTS.md §Medic Rule).
"""

import structlog

from app.gateway.schemas import InboundMessage
from app.swarm.base import AgentResponse, BaseAgent

logger = structlog.get_logger()




class AgentMedic(BaseAgent):
    """Health and coaching agent – LLM-powered with mandatory disclaimer."""

    @property
    def name(self) -> str:
        return "medic"

    @property
    def description(self) -> str:
        return "Health & Coaching Agent – Training bei Beschwerden, Übungen, Disclaimer-Pflicht"

    async def handle(self, message: InboundMessage) -> AgentResponse:
        """Process health-related messages. ALWAYS includes disclaimer."""
        content = message.content.lower()
        logger.info("agent.medic.handle", message_id=message.message_id)

        # Build tenant-aware Jinja2 prompt and disclaimer at runtime (S2.5)
        from app.prompts.engine import get_engine
        from app.prompts.context import build_tenant_context
        from app.gateway.persistence import persistence
        _tenant_slug = persistence.get_tenant_slug(message.tenant_id)
        _ctx = build_tenant_context(persistence, message.tenant_id or 0)
        medic_prompt = get_engine().render_for_tenant("medic/system.j2", _tenant_slug, **_ctx)
        medic_disclaimer = "\n\n" + str(_ctx.get("medic_disclaimer_text", ""))
        emergency_number = str(_ctx.get("studio_emergency_number", "112"))

        # Emergency detection → immediate alert (no LLM needed)
        emergency_keywords = [
            "herzinfarkt", "bewusstlos", "notarzt", "unfall",
            "heart attack", "unconscious", "emergency", "ohnmacht",
            "112", "notfall",
        ]
        if any(kw in content for kw in emergency_keywords):
            return AgentResponse(
                content=(
                    "🚨 **NOTFALL ERKANNT!**\n\n"
                    f"Bitte sofort **{emergency_number}** anrufen!\n"
                    "Ich informiere unser Team JETZT.\n\n"
                    "Bleib ruhig und warte auf Hilfe."
                    + medic_disclaimer
                ),
                confidence=1.0,
                metadata={"action": "emergency_alert", "severity": "critical"},
            )

        # LLM response + mandatory disclaimer
        llm_response = await self._chat(
            medic_prompt,
            message.content,
            user_id=message.user_id,
            tenant_id=message.tenant_id,
        )
        if llm_response:
            return AgentResponse(
                content=llm_response + medic_disclaimer,
                confidence=0.85,
            )

        # Keyword fallback
        return AgentResponse(
            content=(
                "Das ist ein Gesundheitsthema. 🩺 Ich kann dir allgemeine Fitness-Tipps geben, "
                "aber frag am besten unsere Trainer oder einen Arzt."
                + medic_disclaimer
            ),
            confidence=0.7,
        )
