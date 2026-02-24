"""ARIIA v1.4 – Agent Medic (The Coach).

@BACKEND: Sprint 2 → Sprint 9 (LLM-powered)
Handles health-related queries with MANDATORY disclaimer.
CONSTRAINT: ALWAYS includes „Ich bin kein Arzt" disclaimer (AGENTS.md §Medic Rule).
"""

import structlog

from app.gateway.schemas import InboundMessage
from app.swarm.base import AgentResponse, BaseAgent

from app.swarm.tools import member_memory

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

        # 1. Prepare Tenant Prompt (Gold Standard)
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

        # 2. Start Tool Loop (ReAct Pattern)
        messages = [
            {"role": "system", "content": medic_prompt},
            {"role": "user", "content": message.content}
        ]
        
        max_turns = 3
        for turn in range(max_turns):
            response = await self._chat_with_messages(messages, tenant_id=message.tenant_id)
            if not response:
                return self._fallback_response(medic_disclaimer)

            # Check for TOOL usage
            tool_call = self._parse_tool_call(response)
            if not tool_call:
                # Final answer reached
                return AgentResponse(
                    content=response + medic_disclaimer,
                    confidence=0.9
                )
            
            tool_name, tool_args = tool_call
            logger.info("agent.medic.tool_use", tool=tool_name, args=tool_args, turn=turn+1)
            
            # Execute tool
            if tool_name == "search_member_memory":
                tool_result = member_memory.search_member_memory(message.user_id, tool_args.strip('"\''), tenant_id=message.tenant_id)
            else:
                tool_result = f"Error: Tool '{tool_name}' not available for Medic."

            # Add to conversation
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"OBSERVATION: {tool_result}"})

        return AgentResponse(
            content="Ich kann dir gerade keine spezifischen Tipps geben. Frag am besten einen unserer Trainer vor Ort!" + medic_disclaimer,
            confidence=0.5
        )

    def _fallback_response(self, disclaimer: str) -> AgentResponse:
        return AgentResponse(
            content=(
                "Das ist ein Gesundheitsthema. 🩺 Ich kann dir allgemeine Fitness-Tipps geben, "
                "aber frag am besten unsere Trainer oder einen Arzt."
                + disclaimer
            ),
            confidence=0.7,
        )
