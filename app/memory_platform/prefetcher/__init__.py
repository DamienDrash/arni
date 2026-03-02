"""Context Pre-fetcher – proactive context surfacing for conversations.

Instead of waiting for the LLM to make tool calls (reactive approach),
the Pre-fetcher proactively loads relevant context BEFORE the conversation
turn is processed. This reduces latency and ensures the AI always has
the most relevant information available.

The Pre-fetcher runs as a middleware in the message processing pipeline:
1. Receives the incoming message
2. Identifies the member (if known)
3. Pre-fetches relevant knowledge and member facts
4. Injects the context into the message metadata
5. The Orchestrator uses this pre-fetched context in the system prompt

This implements the "Proactive Context Surfacing" pattern from the
Gold-Standard analysis.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger()


class ContextPrefetcher:
    """Proactively fetches and assembles context for conversations."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}  # member_id -> cached context
        self._cache_ttl: int = 300  # 5 minutes
        self._initialised: bool = False

    async def initialise(self) -> None:
        """Initialise the pre-fetcher."""
        if self._initialised:
            return
        self._initialised = True
        logger.info("prefetcher.initialised")

    async def prefetch_context(
        self,
        tenant_id: int,
        member_id: str | None,
        query: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Pre-fetch all relevant context for a conversation turn.

        Returns a context dict that can be injected into the message
        metadata for use by the Orchestrator.
        """
        start = time.time()
        context: dict[str, Any] = {
            "knowledge_context": "",
            "member_facts": [],
            "member_summary": "",
            "recent_interactions": [],
            "prefetch_time_ms": 0,
        }

        # Check cache first
        if member_id:
            cached = self._get_cached(member_id)
            if cached:
                context.update(cached)
                context["prefetch_time_ms"] = round((time.time() - start) * 1000, 1)
                context["cache_hit"] = True
                return context

        try:
            from app.memory_platform.retrieval import get_retrieval_service
            service = get_retrieval_service()
            await service.initialise()

            # 1. Get member-specific context
            if member_id:
                response = await service.get_member_context(
                    tenant_id=tenant_id,
                    member_id=member_id,
                    query=query,
                )

                # Build member summary
                if response.facts:
                    fact_lines = []
                    for f in response.facts[:20]:
                        fact_lines.append({
                            "type": f.fact_type.value,
                            "subject": f.subject,
                            "predicate": f.predicate,
                            "value": f.value,
                            "confidence": f.confidence,
                        })
                    context["member_facts"] = fact_lines

                if response.context_summary:
                    context["member_summary"] = response.context_summary

                # Get knowledge results
                knowledge = [r for r in response.results if r.result_type == "knowledge"]
                if knowledge:
                    context["knowledge_context"] = "\n\n".join(
                        [r.content[:300] for r in knowledge[:5]]
                    )

            # 2. Get general knowledge context
            elif query:
                results = await service.search_knowledge(
                    tenant_id=tenant_id,
                    query=query,
                    top_k=5,
                )
                if results:
                    context["knowledge_context"] = "\n\n".join(
                        [r.content[:300] for r in results[:5]]
                    )

        except Exception as exc:
            logger.warning("prefetcher.error", error=str(exc))

        elapsed = round((time.time() - start) * 1000, 1)
        context["prefetch_time_ms"] = elapsed
        context["cache_hit"] = False

        # Cache the result
        if member_id:
            self._set_cached(member_id, context)

        logger.info(
            "prefetcher.completed",
            member_id=member_id,
            facts=len(context.get("member_facts", [])),
            has_knowledge=bool(context.get("knowledge_context")),
            time_ms=elapsed,
        )

        return context

    def build_context_prompt(self, context: dict[str, Any]) -> str:
        """Convert pre-fetched context into a prompt-ready string.

        This is injected into the system prompt before the conversation.
        """
        parts: list[str] = []

        # Member facts
        member_facts = context.get("member_facts", [])
        if member_facts:
            parts.append("## Bekannte Informationen über den Kunden")
            for fact in member_facts:
                confidence = fact.get("confidence", 0)
                if confidence >= 0.5:
                    parts.append(
                        f"- **{fact['subject']}** {fact['predicate']}: {fact['value']}"
                    )

        # Knowledge context
        knowledge = context.get("knowledge_context", "")
        if knowledge:
            parts.append("\n## Relevantes Wissen aus der Wissensbasis")
            parts.append(knowledge)

        return "\n".join(parts) if parts else ""

    # ── Cache Management ─────────────────────────────────────────────

    def _get_cached(self, member_id: str) -> dict[str, Any] | None:
        """Get cached context for a member."""
        entry = self._cache.get(member_id)
        if not entry:
            return None
        if time.time() - entry.get("_cached_at", 0) > self._cache_ttl:
            del self._cache[member_id]
            return None
        return entry

    def _set_cached(self, member_id: str, context: dict[str, Any]) -> None:
        """Cache context for a member."""
        context["_cached_at"] = time.time()
        self._cache[member_id] = context

        # Evict old entries if cache is too large
        if len(self._cache) > 1000:
            oldest = sorted(
                self._cache.items(),
                key=lambda x: x[1].get("_cached_at", 0),
            )
            for key, _ in oldest[:100]:
                del self._cache[key]

    def invalidate_cache(self, member_id: str | None = None) -> None:
        """Invalidate cached context."""
        if member_id:
            self._cache.pop(member_id, None)
        else:
            self._cache.clear()


# ── Singleton ────────────────────────────────────────────────────────

_prefetcher: ContextPrefetcher | None = None


def get_context_prefetcher() -> ContextPrefetcher:
    """Return the singleton context pre-fetcher."""
    global _prefetcher
    if _prefetcher is None:
        _prefetcher = ContextPrefetcher()
    return _prefetcher
