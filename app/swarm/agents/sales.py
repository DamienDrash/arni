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
from app.swarm.tools import magicline, member_memory
from app.swarm.tools.knowledge_base import search_knowledge_base
from app.knowledge.ingest import collection_name_for_slug

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

        # 1. Prepare Tenant Prompt (Gold Standard)
        from app.prompts.engine import get_engine
        from app.prompts.context import build_tenant_context
        from app.gateway.persistence import persistence
        
        _tenant_slug = persistence.get_tenant_slug(message.tenant_id)
        _ctx = build_tenant_context(persistence, message.tenant_id or 0)
        _prompt = get_engine().render_for_tenant("sales/system.j2", _tenant_slug, **_ctx)
        
        # One-Way-Door: Cancellation detection
        cancel_keywords = ["kündigen", "kündigung", "aufhören", "cancel", "abbrechen"]

        # 2. Start Tool Loop (ReAct Pattern)
        history_msgs = []
        try:
            raw_history = persistence.get_chat_history(str(message.user_id), limit=10, tenant_id=message.tenant_id)
            for item in raw_history:
                if item.role in {"user", "assistant"}:
                    history_msgs.append({"role": item.role, "content": item.content})
        except Exception:
            pass

        messages = [{"role": "system", "content": _prompt}]
        messages.extend(history_msgs)
        messages.append({"role": "user", "content": message.content})
        
        max_turns = 5
        previous_tool_calls = set()
        
        for turn in range(max_turns):
            response = await self._chat_with_messages(messages, tenant_id=message.tenant_id)
            
            if not response:
                return self._fallback_response()
                
            # Check for TOOL usage
            tool_call = self._extract_tool_call(response)
            if not tool_call:
                # Final answer reached
                # If response is cancellation trigger, add metadata
                if any(kw in content for kw in cancel_keywords):
                     return AgentResponse(
                        content=response,
                        confidence=0.95,
                        requires_confirmation=True,
                        metadata={"action": "retention_flow"},
                    )
                return AgentResponse(content=response, confidence=0.9)
            
            # Anti-Loop Protection
            tool_name, args_str = tool_call
            call_id = f"{tool_name}({args_str})"
            if call_id in previous_tool_calls:
                logger.warning("agent.sales.loop_detected", call=call_id)
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "OBSERVATION: Du wiederholst dich. Wenn ein Tool fehlerhaft ist oder keine Daten liefert, antworte dem User empathisch auf Basis der vorhandenen Infos oder entschuldige dich höflich."})
                continue

            previous_tool_calls.add(call_id)
            logger.info("agent.sales.tool_use", tool=tool_name, args=args_str, turn=turn+1)
            
            # Execute tool
            tool_result = self._execute_tool(tool_name, args_str, message.user_id, tenant_id=message.tenant_id)
            
            # Add to conversation
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"OBSERVATION: {tool_result}"})

        return AgentResponse(content="Ich konnte deine Vertragsdaten gerade nicht abrufen. Bitte versuche es später noch einmal.", confidence=0.5)

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

    def _execute_tool(self, name: str, args_str: str, user_id: str, tenant_id: int | None = None) -> str:
        try:
            args = self._parse_args(args_str)
            if name == "get_member_status":
                identifier = args[0] if args else user_id
                if identifier.upper() == "USER_ID":
                    identifier = user_id
                return magicline.get_member_status(identifier, tenant_id=tenant_id)
            elif name == "get_checkin_stats":
                # Parse days arg or default to 90
                days = 90
                if args and args[0].isdigit():
                    days = int(args[0])
                return magicline.get_checkin_stats(days=days, user_identifier=user_id, tenant_id=tenant_id)
            
            elif name == "search_member_memory":
                q = args[0] if args else ""
                return member_memory.search_member_memory(user_id, q, tenant_id=tenant_id)
            
            elif name == "search_knowledge_base":
                q = args[0] if args else ""
                from app.gateway.persistence import persistence
                slug = persistence.get_tenant_slug(tenant_id)
                coll = collection_name_for_slug(slug)
                return search_knowledge_base(q, collection_name=coll)
                
            return f"Error: Tool '{name}' unknown."
        except Exception as e:
            return f"Error: {str(e)}"

    def _fallback_response(self) -> AgentResponse:
        return AgentResponse(
            content="Alles rund um deinen Vertrag – ich bin dein Mann! 💪 Preise, Upgrade, oder was anderes?",
            confidence=0.7,
        )
