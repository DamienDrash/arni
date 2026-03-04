"""ARIIA v2.0 – MasterAgent with Native Tool Calling.

@ARCH: Phase 1, Meilenstein 1.4 – Modernes Tool-Calling
Replaces the regex-based TOOL: worker_name("query") pattern
with native LLM function calling (OpenAI tools API).

Key differences from v1:
- No regex parsing of LLM output
- Tools defined as structured JSON schemas
- Tool calls returned as structured objects by the LLM
- Tool results fed back as proper tool messages
- Parallel tool calls supported natively
- TenantContext propagation through the entire pipeline
- Knowledge base and memory as first-class tools
"""

import asyncio
import json
import structlog
from typing import List, Optional

from app.gateway.schemas import InboundMessage
from app.gateway.persistence import persistence
from app.swarm.base import AgentResponse, BaseAgent
from app.swarm.llm import LLMClient, LLMResponse
from app.swarm.tool_calling import (
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    ToolExecutor,
    ToolRegistry,
    create_worker_tools,
    create_tool_registry_for_tenant,
)

# Specialized sub-agents (workers)
from app.swarm.agents.medic import AgentMedic
from app.swarm.agents.ops import AgentOps
from app.swarm.agents.sales import AgentSales
from app.swarm.agents.persona import AgentPersona
from app.swarm.agents.vision import AgentVision

logger = structlog.get_logger()


# ─── System Prompt (Tool-Calling Optimized) ──────────────────────────────────

MASTER_SYSTEM_PROMPT_V2 = """Du bist der Chef-Koordinator und zentrale Intelligenz von ARIIA.
Deine Aufgabe ist es, Nutzeranliegen exzellent zu lösen.

Du bist der EINZIGE Agent, der direkt mit dem Nutzer spricht.
Du hast ein Team von Spezialisten, die du über Tool-Calls aufrufst.

ABLAUF:
1. ANALYSIERE den User-Input sorgfältig.
2. Entscheide, welche Tools du brauchst. Du kannst mehrere gleichzeitig aufrufen.
3. Erhalte die Ergebnisse und erstelle eine finale, hilfreiche Antwort.

REGELN:
- Wenn ein Nutzer sich beschwert, deeskaliere ZUERST emotional, bevor du Tools aufrufst.
- Nutze das member_memory Tool, um den Nutzer persönlich anzusprechen.
- Nutze knowledge_base für Fakten über das Unternehmen.
- Deine Antwort muss sich anfühlen wie aus einem Guss – nicht wie zusammengestückelt.
- Antworte in der Sprache des Nutzers.

TONALITÄT:
- Verwende IMMER die Du-Form ("du", "dein", "dir") – NIEMALS die Sie-Form.
- Sei freundlich, empathisch und professionell.
- Halte Antworten kurz und prägnant (max. 3-4 Sätze), es sei denn der Nutzer fragt nach Details.
- Vermeide Fachjargon – erkläre einfach und verständlich.
- Wenn du Preise nennst, beziehe dich IMMER auf die offizielle Preisliste.
"""


class MasterAgentV2(BaseAgent):
    """The central brain of ARIIA v2.0 with native tool calling.

    Uses the LLM's native function calling API instead of regex parsing.
    This is more reliable, supports parallel calls, and enables
    structured parameter passing.

    DYN-5/DYN-6: Now accepts an optional ``tenant_id`` to build a
    tenant-specific tool registry at instantiation time.  When no
    ``tenant_id`` is supplied the legacy behaviour (all tools) is used.
    """

    def __init__(self, llm: LLMClient, *, tenant_id: int | None = None):
        self._llm = llm
        self._tenant_id = tenant_id
        self._workers = {
            "ops_agent": AgentOps(),
            "sales_agent": AgentSales(),
            "medic_agent": AgentMedic(),
            "vision_agent": AgentVision(),
            "persona_agent": AgentPersona(),
        }

        # DYN-5: Dynamic tool registry per tenant
        if tenant_id is not None:
            self._tool_registry = create_tool_registry_for_tenant(tenant_id)
        else:
            self._tool_registry = create_worker_tools()

        self._tool_executor = ToolExecutor(self._tool_registry)

        # Register handlers for worker tools
        self._register_worker_handlers()

    def _register_worker_handlers(self):
        """Connect tool definitions to actual worker agent handlers."""
        for tool_name, worker in self._workers.items():
            tool_def = self._tool_registry.get(tool_name)
            if tool_def:
                # Create a closure to capture the worker reference
                async def make_handler(w):
                    async def handler(query: str, **kwargs):
                        msg = InboundMessage(
                            message_id="tool_call",
                            platform="internal",
                            user_id="system",
                            content=query,
                            content_type="text",
                            metadata=kwargs,
                            tenant_id=1,  # Will be overridden per request
                        )
                        result = await w.handle(msg)
                        return result.content
                    return handler

                # We'll set the handler dynamically per request
                # to inject the correct tenant_id
                pass

    @property
    def name(self) -> str:
        return "master_v2"

    @property
    def description(self) -> str:
        return "Master Orchestrator v2 – Native Tool Calling"

    async def handle(self, message: InboundMessage) -> AgentResponse:
        """The Orchestration Loop with native tool calling.

        Flow:
        1. Send user message + tools to LLM
        2. If LLM returns tool_calls → execute them
        3. Feed results back as tool messages
        4. Repeat until LLM returns a final text response
        """
        logger.info("master_v2.orchestration.started", message_id=message.message_id)

        # Build system prompt with tenant-specific context
        system_prompt = await self._build_system_prompt(message)

        # Build conversation history
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message.content},
        ]

        # Get tools in OpenAI format
        tools = self._tool_registry.get_openai_tools()

        max_turns = 5
        for turn in range(max_turns):
            # Call LLM with tools
            llm_response = await self._llm.chat_with_tools(
                messages=messages,
                tools=tools,
                tenant_id=message.tenant_id or 1,
                user_id=message.user_id,
                agent_name="master_v2",
                temperature=0.3,
                max_tokens=1500,
            )

            if not llm_response.success:
                logger.error(
                    "master_v2.llm_error",
                    error=llm_response.error,
                    turn=turn + 1,
                )
                return AgentResponse(
                    content="Es gab ein technisches Problem. Bitte versuche es gleich nochmal!",
                    confidence=0.3,
                )

            # Check if LLM wants to call tools
            if llm_response.has_tool_calls:
                logger.info(
                    "master_v2.tool_calls",
                    count=len(llm_response.tool_calls),
                    tools=[tc.get("function", {}).get("name") for tc in llm_response.tool_calls],
                    turn=turn + 1,
                )

                # Add assistant message with tool calls to history
                messages.append(llm_response.assistant_message)

                # Execute each tool call
                for tc_raw in llm_response.tool_calls:
                    tc = ToolCallRequest.from_openai(tc_raw)
                    result = await self._execute_tool_call(tc, message)

                    # Add tool result to conversation
                    messages.append(result.to_openai_message())

            else:
                # No tool calls → final response
                content = llm_response.content.strip()
                if not content:
                    content = "Ich bin gerade etwas verwirrt. Kannst du das nochmal anders formulieren?"

                logger.info(
                    "master_v2.orchestration.complete",
                    turns=turn + 1,
                    content_length=len(content),
                )

                return AgentResponse(content=content, confidence=1.0)

        # Max turns reached
        logger.warning("master_v2.max_turns_reached", max_turns=max_turns)
        return AgentResponse(
            content="Ich habe viele Infos gesammelt. Frag mich gerne nach den Details!",
            confidence=0.5,
        )

    async def _execute_tool_call(
        self, tc: ToolCallRequest, original_message: InboundMessage
    ) -> ToolCallResult:
        """Execute a single tool call by routing to the appropriate worker.

        Special tools (knowledge_base, member_memory) are handled directly.
        Worker tools are routed to the corresponding agent.
        """
        tool_name = tc.name
        query = tc.arguments.get("query", "")

        # Handle special tools
        if tool_name == "knowledge_base":
            return await self._handle_knowledge_base(tc, original_message)
        elif tool_name == "member_memory":
            return await self._handle_member_memory(tc, original_message)
        elif tool_name == "calendly_booking":
            return await self._handle_calendly_booking(tc, original_message)

        # Route to worker agent
        worker = self._workers.get(tool_name)
        if not worker:
            logger.warning("master_v2.unknown_worker", tool=tool_name)
            return ToolCallResult(
                tool_call_id=tc.id,
                name=tool_name,
                content=f"Worker '{tool_name}' nicht verfügbar.",
                success=False,
            )

        try:
            worker_msg = InboundMessage(
                message_id=f"tc_{tc.id}",
                platform=original_message.platform,
                user_id=original_message.user_id,
                content=query,
                content_type="text",
                metadata={
                    **original_message.metadata,
                    "tool_call_id": tc.id,
                    "tool_arguments": tc.arguments,
                },
                tenant_id=original_message.tenant_id,
            )
            worker_result = await worker.handle(worker_msg)

            return ToolCallResult(
                tool_call_id=tc.id,
                name=tool_name,
                content=worker_result.content,
                success=True,
            )
        except Exception as e:
            logger.error("master_v2.worker_error", tool=tool_name, error=str(e))
            return ToolCallResult(
                tool_call_id=tc.id,
                name=tool_name,
                content=f"Fehler bei {tool_name}: {str(e)}",
                success=False,
                error=str(e),
            )

    async def _handle_knowledge_base(
        self, tc: ToolCallRequest, message: InboundMessage
    ) -> ToolCallResult:
        """Search the tenant's knowledge base.

        Uses ChromaDB-backed KnowledgeStore (app.knowledge.store) for
        semantic vector search, with a fallback to per-member markdown
        knowledge files (app.memory.knowledge).
        """
        query = tc.arguments.get("query", "")
        top_k = tc.arguments.get("top_k", 3)

        try:
            from app.knowledge.store import KnowledgeStore
            from app.knowledge.ingest import collection_name_for_slug

            # Use the same collection naming as the ingest pipeline
            # so that ingested documents are actually found.
            tenant_slug = (message.metadata or {}).get('tenant_slug')
            if not tenant_slug and message.tenant_id:
                # KB-1 FIX: Use get_tenant_slug() instead of get_setting()
                # tenant_slug is a field on the Tenant model, not a setting.
                try:
                    tenant_slug = await asyncio.to_thread(
                        persistence.get_tenant_slug,
                        message.tenant_id,
                    )
                except Exception:
                    pass
            if tenant_slug:
                collection = collection_name_for_slug(tenant_slug)
            else:
                collection = f"tenant_{message.tenant_id or 1}"

            # KB-1 FIX: Fetch more results (top_k=5 min) to improve
            # recall with the default ChromaDB embedding model.
            effective_top_k = max(top_k, 5)
            store = KnowledgeStore(collection_name=collection)
            raw = store.query(query_text=query, n_results=effective_top_k)

            # ChromaDB returns {"documents": [[...]], "metadatas": [[...]], ...}
            docs = raw.get("documents", [[]])[0] if raw else []
            if docs:
                content = "\n\n".join(
                    [f"[{i+1}] {doc}" for i, doc in enumerate(docs) if doc]
                )
            else:
                content = ""

            # Fallback: check per-member knowledge files
            if not content:
                try:
                    from app.memory.knowledge import KnowledgeStore as MemberKnowledge
                    mk = MemberKnowledge()
                    member_facts = mk.get_facts(message.user_id)
                    if member_facts:
                        content = f"Bekannte Fakten über dieses Mitglied:\n{member_facts}"
                except Exception:
                    pass

            if not content:
                content = "Keine relevanten Informationen in der Wissensdatenbank gefunden."

            return ToolCallResult(
                tool_call_id=tc.id,
                name="knowledge_base",
                content=content,
                success=True,
            )
        except Exception as e:
            logger.error("master_v2.knowledge_base_error", error=str(e))
            return ToolCallResult(
                tool_call_id=tc.id,
                name="knowledge_base",
                content=f"Wissensdatenbank-Fehler: {str(e)}",
                success=False,
                error=str(e),
            )

    async def _handle_member_memory(
        self, tc: ToolCallRequest, message: InboundMessage
    ) -> ToolCallResult:
        """Retrieve or store member memory.

        Uses the per-member markdown knowledge files and the
        conversation context / librarian for recall.
        """
        query = tc.arguments.get("query", "")
        action = tc.arguments.get("action", "retrieve")

        try:
            from app.memory.knowledge import KnowledgeStore as MemberKnowledge

            store = MemberKnowledge()

            if action == "store":
                store.append_facts(user_id=message.user_id, facts=[query])
                return ToolCallResult(
                    tool_call_id=tc.id,
                    name="member_memory",
                    content="Information gespeichert.",
                    success=True,
                )
            else:
                facts = store.get_facts(message.user_id)
                if facts:
                    content = facts
                else:
                    content = "Keine gespeicherten Informationen über diesen Nutzer gefunden."

                return ToolCallResult(
                    tool_call_id=tc.id,
                    name="member_memory",
                    content=content,
                    success=True,
                )
        except Exception as e:
            logger.error("master_v2.memory_error", error=str(e))
            return ToolCallResult(
                tool_call_id=tc.id,
                name="member_memory",
                content=f"Memory-Fehler: {str(e)}",
                success=False,
                error=str(e),
            )

    async def _handle_calendly_booking(
        self, tc: ToolCallRequest, message: InboundMessage
    ) -> ToolCallResult:
        """Get a Calendly booking link for the given event type.

        P2-FIX: When no event_type_name is provided, proactively lists
        all available event types with booking links instead of asking
        the user to specify one first.
        """
        event_type_name = tc.arguments.get("event_type_name", "")
        try:
            from app.swarm.tools.calendly_tools import get_booking_link

            result = await get_booking_link(
                event_type_name=event_type_name,
                tenant_id=message.tenant_id or 1,
            )
            return ToolCallResult(
                tool_call_id=tc.id,
                name="calendly_booking",
                content=result,
                success=True,
            )
        except Exception as e:
            logger.error("master_v2.calendly_error", error=str(e))
            return ToolCallResult(
                tool_call_id=tc.id,
                name="calendly_booking",
                content=f"Calendly-Fehler: {str(e)}",
                success=False,
                error=str(e),
            )

    async def _build_system_prompt(self, message: InboundMessage) -> str:
        """Build the system prompt with tenant-specific customization.

        UX-3: Now also loads studio_name and studio_address from tenant settings
        to give the agent permanent business context.
        """
        base_prompt = MASTER_SYSTEM_PROMPT_V2

        # Load tenant-specific prompt customization
        try:
            custom_prompt = persistence.get_setting(
                "custom_system_prompt", "", tenant_id=message.tenant_id
            )
            if custom_prompt:
                base_prompt += f"\n\nTENANT-SPEZIFISCHE ANWEISUNGEN:\n{custom_prompt}"

            # Load persona name
            persona_name = persistence.get_setting(
                "persona_name", "ARIIA", tenant_id=message.tenant_id
            )
            if persona_name:
                base_prompt += f"\n\nDein Name ist: {persona_name}"

            # UX-3: Studio context (always available)
            studio_name = persistence.get_setting(
                "studio_name", "", tenant_id=message.tenant_id
            )
            studio_address = persistence.get_setting(
                "studio_address", "", tenant_id=message.tenant_id
            )
            if studio_name or studio_address:
                context_block = "\n\nUNTERNEHMENS-KONTEXT:"
                if studio_name:
                    context_block += f"\n- Unternehmensname: {studio_name}"
                if studio_address:
                    context_block += f"\n- Adresse: {studio_address}"
                base_prompt += context_block

            # P1-FIX: Single Source of Truth for pricing
            # Always inject sales_prices_text from DB settings into the
            # system prompt so the LLM uses authoritative pricing data
            # instead of potentially outdated Knowledge Base content.
            sales_prices = persistence.get_setting(
                "sales_prices_text", "", tenant_id=message.tenant_id
            )
            if sales_prices:
                base_prompt += (
                    "\n\nOFFIZIELLE PREISLISTE (verbindlich – diese Preise haben "
                    "IMMER Vorrang vor allen anderen Quellen, auch vor der "
                    "Knowledge Base):\n" + sales_prices
                )

            # DYN-3: Integration awareness in master prompt
            if self._tenant_id is not None:
                enabled = persistence.get_enabled_integrations(self._tenant_id)
                if enabled:
                    base_prompt += f"\n\nAKTIVE INTEGRATIONEN: {', '.join(enabled)}"
                    base_prompt += (
                        "\nNutze nur Tools, die zu den aktiven Integrationen passen. "
                        "Wenn eine Funktion nicht verf\u00fcgbar ist, erkl\u00e4re das freundlich."
                    )

        except Exception as e:
            logger.warning("master_v2.prompt_customization_failed", error=str(e))

        return base_prompt
