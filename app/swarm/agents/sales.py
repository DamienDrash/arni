"""ARIIA v1.4 – Agent Sales (The Hunter).

@BACKEND: Sprint 2 → Sprint 9 (LLM-powered)
Handles cancellations, renewals, upgrades, pricing. Retention-focused.
Goal: Keep members. Offer alternatives before cancellation.
"""

import re
import csv

import structlog

from app.gateway.schemas import InboundMessage
from app.swarm.base import AgentResponse, BaseAgent
from app.swarm.tools import magicline

logger = structlog.get_logger()




class AgentSales(BaseAgent):
    """Retention and sales agent – LLM-powered with Magicline Tools."""

    @property
    def name(self) -> str:
        return "sales"

    @property
    def description(self) -> str:
        return "Sales & Retention Agent – Verträge, Kündigung, Preise, Upgrades"

    async def handle(self, message: InboundMessage) -> AgentResponse:
        """Process sales-related messages via GPT-4o-mini with Tool Loop."""
        content = message.content.lower()
        logger.info("agent.sales.handle", message_id=message.message_id)

        # One-Way-Door: Cancellation detection (always requires confirmation)
        cancel_keywords = ["kündigen", "kündigung", "aufhören", "cancel", "abbrechen"]
        if any(kw in content for kw in cancel_keywords):
            # Special case: Cancellation often implies needing context first.
            # We let the LLM decide if it needs to check status first.
            # But if it decides to cancel directly, we catch it here.
            
            # Use LLM first to see if it wants to check status
            pass # fall through to LLM loop

        # 1. First Pass: Ask LLM — build tenant-aware Jinja2 prompt (S2.5)
        from app.prompts.engine import get_engine
        from app.prompts.context import build_tenant_context
        from app.gateway.persistence import persistence
        _tenant_slug = persistence.get_tenant_slug(message.tenant_id)
        _ctx = build_tenant_context(persistence, message.tenant_id or 0)
        _prompt = get_engine().render_for_tenant("sales/system.j2", _tenant_slug, **_ctx)
        prompt_with_context = f"{_prompt}\n\nUSER_ID: {message.user_id}"

        response_1 = await self._chat(
            prompt_with_context,
            message.content,
            user_id=message.user_id,
            tenant_id=message.tenant_id,
        )
        if not response_1:
            return self._fallback_response()

        # 2. Check for TOOL usage
        tool_call = self._extract_tool_call(response_1)
        if tool_call:
            tool_name, args_str = tool_call
            logger.info("agent.sales.tool_use", tool=tool_name, args=args_str)

            # Execute tool
            tool_result = self._execute_tool(tool_name, args_str, message.user_id)
            
            # 3. Second Pass — reuse already-built tenant prompt
            final_prompt = (
                f"{prompt_with_context}\n\n"
                f"SYSTEM TOOL OUTPUT:\n{tool_result}\n\n"
                "Antworte dem User jetzt basierend auf diesen Daten. Antworte in normalem Text. Nutze KEIN Tool mehr. Beachte die Retention-Regeln!"
            )
            response_2 = await self._chat(
                final_prompt,
                message.content,
                user_id=message.user_id,
                tenant_id=message.tenant_id,
            )
            
            # If response is cancellation trigger, add metadata
            if any(kw in content for kw in cancel_keywords):
                 return AgentResponse(
                    content=response_2,
                    confidence=0.95,
                    requires_confirmation=True,
                    metadata={"action": "retention_flow"},
                )
            
            return AgentResponse(content=response_2 or "Datenfehler.", confidence=0.95)

        # Safety: never expose raw TOOL commands to users.
        if "TOOL:" in response_1:
            logger.warning("agent.sales.unparsed_tool_response", response=response_1)
            return AgentResponse(
                content="Ich brauche einen kurzen Retry für die Vertragsabfrage. Sag bitte noch einmal: 'Bin ich Premium?'",
                confidence=0.6,
            )

        # Check if cancellation fallback is needed if LLM was generic
        if any(kw in content for kw in cancel_keywords) and "TOOL" not in response_1:
             return AgentResponse(
                content=response_1, # Use LLM response if it handled it (e.g. asked "Warum?")
                confidence=0.9,
                requires_confirmation=True,
                metadata={"action": "retention_flow"},
            )

        return AgentResponse(content=response_1, confidence=0.85)

    def _parse_args(self, args_str: str) -> list[str]:
        if not args_str.strip():
            return []
        parsed = next(csv.reader([args_str], skipinitialspace=True), [])
        return [a.strip().strip("'").strip('"') for a in parsed]

    def _extract_tool_call(self, response: str) -> tuple[str, str] | None:
        cleaned = response.strip().strip("`")
        match = re.search(
            r"TOOL\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    def _execute_tool(self, name: str, args_str: str, user_id: str) -> str:
        try:
            args = self._parse_args(args_str)
            if name == "get_member_status":
                identifier = args[0] if args else user_id
                if identifier.upper() == "USER_ID":
                    identifier = user_id
                return magicline.get_member_status(identifier)
            elif name == "get_checkin_stats":
                # Parse days arg or default to 90
                days = 90
                if args and args[0].isdigit():
                    days = int(args[0])
                return magicline.get_checkin_stats(days=days, user_identifier=user_id)
                
            return f"Error: Tool '{name}' unknown."
        except Exception as e:
            return f"Error: {str(e)}"

    def _fallback_response(self) -> AgentResponse:
        return AgentResponse(
            content="Alles rund um deinen Vertrag – ich bin dein Mann! 💪 Preise, Upgrade, oder was anderes?",
            confidence=0.7,
        )
