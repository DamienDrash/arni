"""Integration Bridge – connects the Memory Platform to ARIIA's existing systems.

This module provides the bridge between the new Memory Platform and the
existing ARIIA components:
    - Orchestrator (MasterAgentV2): tool handlers for knowledge_base and member_memory
    - Campaign Engine: knowledge-enhanced campaign generation
    - Prompt Builder: context injection for agent prompts
    - Event Publishing: conversation memory extraction

The bridge maintains backward compatibility with the legacy API while
routing all operations through the new Memory Platform services.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class MemoryPlatformBridge:
    """Bridge between ARIIA's existing systems and the new Memory Platform.

    This class provides drop-in replacements for the legacy knowledge
    and memory operations used by the Orchestrator, Campaign Engine,
    and Prompt Builder.
    """

    def __init__(self) -> None:
        self._initialised: bool = False

    async def initialise(self) -> None:
        """Initialise all Memory Platform services."""
        if self._initialised:
            return

        from app.memory_platform.extraction import get_extraction_service
        from app.memory_platform.enrichment import get_enrichment_service
        from app.memory_platform.writer import get_writer_service
        from app.memory_platform.retrieval import get_retrieval_service

        # Initialise services in order
        extraction = get_extraction_service()
        await extraction.initialise()

        enrichment = get_enrichment_service()
        await enrichment.initialise()

        writer = get_writer_service()
        await writer.initialise()

        retrieval = get_retrieval_service()
        await retrieval.initialise()

        self._initialised = True
        logger.info("memory_platform.bridge_initialised")

    # ── Orchestrator Tool Handlers ───────────────────────────────────

    async def handle_knowledge_base_tool(
        self,
        tenant_id: int,
        query: str,
        top_k: int = 5,
    ) -> str:
        """Handle the knowledge_base tool call from the Orchestrator.

        Replaces the legacy ``_handle_knowledge_base`` method in
        ``MasterAgentV2``. Uses the new hybrid search.
        """
        await self.initialise()

        from app.memory_platform.retrieval import get_retrieval_service

        service = get_retrieval_service()
        results = await service.search_knowledge(
            tenant_id=tenant_id,
            query=query,
            top_k=top_k,
        )

        if not results:
            return "Keine relevanten Informationen in der Wissensdatenbank gefunden."

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] {r.content}")

        return "\n\n".join(parts)

    async def handle_member_memory_tool(
        self,
        tenant_id: int,
        user_id: str,
        query: str,
        action: str = "retrieve",
        member_id: str | None = None,
    ) -> str:
        """Handle the member_memory tool call from the Orchestrator.

        Replaces the legacy ``_handle_member_memory`` method in
        ``MasterAgentV2``. Uses the new retrieval service with
        structured facts.
        """
        await self.initialise()

        effective_member_id = member_id or user_id

        if action == "store":
            # Ingest the content as a conversation memory
            from app.memory_platform.ingestion import get_ingestion_service
            service = get_ingestion_service()
            await service.ingest_conversation(
                tenant_id=tenant_id,
                conversation_id=f"manual_{effective_member_id}",
                messages=[{"role": "user", "content": query}],
                member_id=effective_member_id,
            )
            return "Information gespeichert."

        else:
            # Retrieve member context
            from app.memory_platform.retrieval import get_retrieval_service
            service = get_retrieval_service()
            response = await service.get_member_context(
                tenant_id=tenant_id,
                member_id=effective_member_id,
                query=query,
            )

            if response.context_summary:
                return response.context_summary

            if response.facts:
                parts = []
                for f in response.facts[:10]:
                    parts.append(f"- {f.subject} {f.predicate}: {f.value}")
                return "\n".join(parts)

            return "Keine gespeicherten Informationen über diesen Nutzer gefunden."

    # ── Campaign Engine Integration ──────────────────────────────────

    async def get_campaign_knowledge_context(
        self,
        tenant_id: int,
        prompt: str,
        max_results: int = 5,
    ) -> str:
        """Get knowledge context for campaign content generation.

        Replaces the legacy knowledge search in the campaigns router.
        """
        await self.initialise()

        from app.memory_platform.retrieval import get_retrieval_service

        service = get_retrieval_service()
        results = await service.search_knowledge(
            tenant_id=tenant_id,
            query=prompt,
            top_k=max_results,
        )

        if not results:
            return ""

        parts = ["Relevante Informationen aus der Wissensbasis:"]
        for r in results:
            parts.append(f"- {r.content[:300]}")

        return "\n".join(parts)

    async def get_campaign_segments(
        self,
        tenant_id: int,
        criteria: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Get member segments for campaign targeting.

        Enables the Campaign Engine to use the knowledge graph
        for advanced segmentation based on member facts.
        """
        await self.initialise()

        from app.memory_platform.retrieval import get_retrieval_service

        service = get_retrieval_service()
        return await service.get_campaign_segments(tenant_id, criteria)

    # ── Prompt Context Injection ─────────────────────────────────────

    async def build_agent_context(
        self,
        tenant_id: int,
        member_id: str | None = None,
        query: str = "",
    ) -> str:
        """Build context for agent prompts.

        This is the new "proactive context surfacing" that replaces
        the reactive tool-call-based approach. The orchestrator calls
        this BEFORE generating a response to pre-load relevant context.
        """
        await self.initialise()

        parts: list[str] = []

        # 1. Get member context if available
        if member_id:
            from app.memory_platform.retrieval import get_retrieval_service
            service = get_retrieval_service()
            response = await service.get_member_context(
                tenant_id=tenant_id,
                member_id=member_id,
                query=query,
            )

            if response.facts:
                parts.append("## Kundengedächtnis")
                for f in response.facts[:15]:
                    parts.append(f"- **{f.subject}** {f.predicate}: {f.value}")

            if response.results:
                knowledge = [r for r in response.results if r.result_type == "knowledge"]
                if knowledge:
                    parts.append("\n## Relevantes Wissen")
                    for r in knowledge[:3]:
                        parts.append(f"- {r.content[:200]}")

        # 2. Get general knowledge context for the query
        elif query:
            from app.memory_platform.retrieval import get_retrieval_service
            service = get_retrieval_service()
            results = await service.search_knowledge(
                tenant_id=tenant_id,
                query=query,
                top_k=5,
            )
            if results:
                parts.append("## Relevantes Wissen")
                for r in results[:5]:
                    parts.append(f"- {r.content[:200]}")

        return "\n".join(parts) if parts else ""

    # ── Conversation Memory Pipeline ─────────────────────────────────

    async def process_conversation(
        self,
        tenant_id: int,
        conversation_id: str,
        messages: list[dict[str, str]],
        member_id: str | None = None,
    ) -> None:
        """Process a conversation through the memory extraction pipeline.

        Called by the Orchestrator after each conversation turn to
        extract and store relevant information.
        """
        await self.initialise()

        from app.memory_platform.ingestion import get_ingestion_service
        service = get_ingestion_service()
        await service.ingest_conversation(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            messages=messages,
            member_id=member_id,
        )


# ── Singleton ────────────────────────────────────────────────────────

_bridge: MemoryPlatformBridge | None = None


def get_memory_platform_bridge() -> MemoryPlatformBridge:
    """Return the singleton bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = MemoryPlatformBridge()
    return _bridge
