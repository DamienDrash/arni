"""ARIIA v1.4 – Persona Handler (Smalltalk).

@BACKEND: Sprint 2 → Sprint 9 (LLM-powered)
Handles greetings, chitchat, and general questions using SOUL.md persona.
Ariia = Arnold Schwarzenegger meets Berlin Fitness Coach.
"""

import structlog

from app.gateway.schemas import InboundMessage
from app.swarm.base import AgentResponse, BaseAgent

logger = structlog.get_logger()

from app.swarm.tools.knowledge_base import search_knowledge_base
from app.swarm.tools import member_memory


class AgentPersona(BaseAgent):
    """Smalltalk and persona handler – LLM-powered with SOUL.md."""

    @property
    def name(self) -> str:
        return "persona"

    @property
    def description(self) -> str:
        return "Persona & Smalltalk Handler – Begrüßung, Chitchat, Ariia-Style"

    def __init__(self) -> None:
        super().__init__()
        self._soul_content = self._load_soul()

    def _load_soul(self) -> str:
        """Load persona from SOUL.md."""
        try:
            with open("docs/personas/SOUL.md", "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            logger.warning("agent.persona.soul_missing")
            return ""

    async def _trigger_handoff(self, user_id: str, tenant_id: int | None = None) -> None:
        """Set human_mode flag in Redis (tenant-scoped key)."""
        import traceback
        from app.gateway.redis_bus import RedisBus
        from app.core.redis_keys import human_mode_key
        from config.settings import get_settings

        settings = get_settings()
        bus = RedisBus(settings.redis_url)
        connected = False
        try:
            await bus.connect()
            connected = True
            tid = tenant_id or 0
            key = human_mode_key(tid, user_id)
            # Set flag with 24h expiry
            await bus.client.setex(key, 86400, "true")
            logger.info("agent.persona.handoff_triggered", user_id=user_id)
        except Exception as e:
            logger.error(
                "agent.persona.handoff_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
        finally:
            if connected:
                try:
                    await bus.disconnect()
                except Exception as disc_err:
                    logger.warning(
                        "agent.persona.handoff_disconnect_failed",
                        error=str(disc_err),
                    )

    async def handle(self, message: InboundMessage) -> AgentResponse:
        """Handle smalltalk with Ariia persona via GPT-4o-mini with Tool Loop."""
        logger.info("agent.persona.handle", message_id=message.message_id)

        # 1. Prepare Tenant Prompt (Gold Standard)
        self._soul_content = self._load_soul()
        from app.prompts.engine import get_engine
        from app.prompts.context import build_tenant_context
        from app.gateway.persistence import persistence as _ps
        _tenant_slug = _ps.get_tenant_slug(message.tenant_id)
        _ctx = build_tenant_context(_ps, message.tenant_id or 0)
        system_prompt = get_engine().render_for_tenant(
            "persona/system.j2", _tenant_slug, soul_content=self._soul_content, **_ctx
        )
        
        # 2. Start Tool Loop (ReAct Pattern)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.content}
        ]
        
        max_turns = 3
        for turn in range(max_turns):
            response = await self._chat_with_messages(messages, tenant_id=message.tenant_id)
            if not response:
                return AgentResponse(content="Sorry, bin kurz AFK. 🏋️‍♂️", confidence=0.5)

            # Check for Tool Use
            tool_call = self._parse_tool_call(response)
            if not tool_call:
                return AgentResponse(content=response, confidence=0.9)
            
            tool_name, tool_args = tool_call
            logger.info("agent.persona.tool_use", tool=tool_name, args=tool_args, turn=turn+1)
            
            if tool_name == "query_knowledge_base":
                query = tool_args.strip('"\'')
                from app.knowledge.ingest import collection_name_for_slug
                kb_collection = collection_name_for_slug(_tenant_slug)
                tool_result = search_knowledge_base(query, collection_name=kb_collection)
                
            elif tool_name == "search_member_memory":
                tool_result = member_memory.search_member_memory(message.user_id, tool_args.strip('"\''), tenant_id=message.tenant_id)

            elif tool_name == "request_handoff":
                await self._trigger_handoff(message.user_id, tenant_id=message.tenant_id)
                return AgentResponse(content="Alles klar, ich hole einen Kollegen dazu. Moment! 👤", confidence=1.0)
            
            else:
                tool_result = f"Error: Tool '{tool_name}' unknown."

            # Add to conversation
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"OBSERVATION: {tool_result}"})

        return AgentResponse(content="Ich konnte die passende Info gerade nicht finden. Frag mich gerne nochmal anders.", confidence=0.5)
