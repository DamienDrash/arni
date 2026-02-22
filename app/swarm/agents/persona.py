"""ARNI v1.4 – Persona Handler (Smalltalk).

@BACKEND: Sprint 2 → Sprint 9 (LLM-powered)
Handles greetings, chitchat, and general questions using SOUL.md persona.
Arni = Arnold Schwarzenegger meets Berlin Fitness Coach.
"""

import structlog

from app.gateway.schemas import InboundMessage
from app.swarm.base import AgentResponse, BaseAgent

logger = structlog.get_logger()

from app.swarm.tools.knowledge_base import search_knowledge_base




class AgentPersona(BaseAgent):
    """Smalltalk and persona handler – LLM-powered with SOUL.md."""

    @property
    def name(self) -> str:
        return "persona"

    @property
    def description(self) -> str:
        return "Persona & Smalltalk Handler – Begrüßung, Chitchat, Arni-Style"

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
        """Handle smalltalk with Arni persona via GPT-4o-mini."""
        logger.info("agent.persona.handle", message_id=message.message_id)

        # Reload soul for live evolution
        self._soul_content = self._load_soul()

        # Build tenant-aware Jinja2 prompt (S2.5): per-tenant template with soul content
        from app.prompts.engine import get_engine
        from app.prompts.context import build_tenant_context
        from app.gateway.persistence import persistence as _ps
        _tenant_slug = _ps.get_tenant_slug(message.tenant_id)
        _ctx = build_tenant_context(_ps, message.tenant_id or 0)
        system_prompt = get_engine().render_for_tenant(
            "persona/system.j2", _tenant_slug, soul_content=self._soul_content, **_ctx
        )
        
        # 1. First Pass
        response_1 = await self._chat(
            system_prompt,
            message.content,
            user_id=message.user_id,
            tenant_id=message.tenant_id,
        )
        if not response_1:
             return AgentResponse(content="Sorry, bin kurz AFK. 🏋️‍♂️", confidence=0.5)

        # 2. Check for Tool Use
        tool_call = self._parse_tool_call(response_1)
        if tool_call:
            tool_name, tool_args = tool_call
            logger.info("agent.persona.tool_use", tool=tool_name, args=tool_args)
            
            if tool_name == "query_knowledge_base":
                # Remove quotes if present
                query = tool_args.strip('"\'')
                # Use tenant-scoped ChromaDB collection
                from app.knowledge.ingest import collection_name_for_slug
                kb_collection = collection_name_for_slug(_tenant_slug)
                context = search_knowledge_base(query, collection_name=kb_collection)
                
                # Second Pass with Context
                final_prompt = (
                    f"{system_prompt}\n\n"
                    f"CONTEXT FROM KNOWLEDGE BASE:\n{context}\n\n"
                    "WICHTIG: DU HAST DIE INFOS JETZT. NUTZE KEIN TOOL MEHR! "
                    "ANTWORTE DEM USER DIREKT UND FREUNDLICH BASIEREND AUF DEM KONTEXT."
                )
                response_2 = await self._chat(
                    final_prompt,
                    message.content,
                    user_id=message.user_id,
                    tenant_id=message.tenant_id,
                )
                if response_2:
                    return AgentResponse(content=response_2, confidence=0.95)

            elif tool_name == "request_handoff":
                try:
                    await self._trigger_handoff(message.user_id, tenant_id=message.tenant_id)
                except Exception:
                    import traceback
                    logger.error(
                        "agent.persona.handoff_unhandled",
                        traceback=traceback.format_exc(),
                    )
                return AgentResponse(content="Alles klar, ich hole einen Kollegen dazu. Moment! 👤", confidence=1.0)

        return AgentResponse(content=response_1, confidence=0.9)
