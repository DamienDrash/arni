"""Retrieval Service – unified hybrid search API.

Provides a single entry point for all read operations against the
Memory Platform.  Implements hybrid search combining:
    1. Vector search (semantic similarity)
    2. Graph search (structured queries via Cypher)
    3. Keyword search (full-text matching)
    4. Reranking (cross-encoder for precision)

This service replaces the retrieval logic in ``app/core/knowledge/retriever.py``
and the query methods in ``app/memory/librarian_v2.py``.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.memory_platform.config import get_config
from app.memory_platform.models import (
    ExtractedFact,
    RetrievalResponse,
    SearchQuery,
    SearchResult,
)
from app.memory_platform.models.graph_store import get_graph_store
from app.memory_platform.models.vector_store import get_vector_store

logger = structlog.get_logger()


class RetrievalService:
    """Unified retrieval service with hybrid search capabilities."""

    def __init__(self) -> None:
        self._graph = get_graph_store()
        self._vector = get_vector_store()
        self._reranker: Any = None
        self._initialised: bool = False
        self._query_count: int = 0

    async def initialise(self) -> None:
        """Initialise stores and optional reranker."""
        if self._initialised:
            return

        await self._graph.initialise()
        await self._vector.initialise()

        # Try to load reranker model
        cfg = get_config().retrieval
        if cfg.enable_reranking:
            try:
                from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
                self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("retrieval.reranker_loaded")
            except ImportError:
                logger.info("retrieval.reranker_not_available")

        self._initialised = True
        logger.info("retrieval.service_initialised")

    # ── Main Search API ──────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> RetrievalResponse:
        """Execute a hybrid search and return ranked results.

        The search combines results from multiple sources:
        1. Vector search for semantic similarity
        2. Graph search for structured facts
        3. Full-text search for keyword matching
        Results are merged, deduplicated, and optionally reranked.
        """
        start_time = time.time()
        self._query_count += 1

        cfg = get_config().retrieval
        all_results: list[SearchResult] = []

        # 1. Vector Search
        if query.search_type in ("hybrid", "vector"):
            vector_results = await self._vector_search(query)
            for r in vector_results:
                r.score *= cfg.vector_weight
            all_results.extend(vector_results)

        # 2. Graph Search (facts for specific member)
        if query.search_type in ("hybrid", "graph") and query.include_facts:
            graph_results = await self._graph_search(query)
            for r in graph_results:
                r.score *= cfg.graph_weight
            all_results.extend(graph_results)

        # 3. Keyword Search (full-text on graph)
        if query.search_type in ("hybrid", "keyword"):
            keyword_results = await self._keyword_search(query)
            for r in keyword_results:
                r.score *= cfg.keyword_weight
            all_results.extend(keyword_results)

        # 4. Deduplicate by content similarity
        deduped = self._deduplicate(all_results)

        # 5. Sort by score
        deduped.sort(key=lambda r: r.score, reverse=True)

        # 6. Rerank top results
        if self._reranker and cfg.enable_reranking and deduped:
            deduped = self._rerank(query.query, deduped, cfg.rerank_top_k)

        # 7. Limit results
        final_results = deduped[:query.top_k]

        # 8. Get member-specific facts
        facts: list[ExtractedFact] = []
        if query.member_id and query.include_facts:
            facts = await self._get_member_facts(query)

        # 9. Build context summary
        context_summary = self._build_context_summary(final_results, facts)

        elapsed = (time.time() - start_time) * 1000

        logger.info(
            "retrieval.search_completed",
            query=query.query[:50],
            results=len(final_results),
            facts=len(facts),
            time_ms=round(elapsed, 1),
        )

        return RetrievalResponse(
            query=query.query,
            results=final_results,
            facts=facts,
            context_summary=context_summary,
            total_results=len(final_results),
            search_time_ms=round(elapsed, 1),
        )

    # ── Search Strategies ────────────────────────────────────────────

    async def _vector_search(self, query: SearchQuery) -> list[SearchResult]:
        """Semantic vector search across knowledge and facts."""
        results: list[SearchResult] = []

        # Search knowledge chunks
        if query.include_knowledge:
            knowledge_hits = await self._vector.search(
                tenant_id=query.tenant_id,
                query=query.query,
                top_k=query.top_k,
                namespace="knowledge",
                filters=query.filters if query.filters else None,
            )
            for hit in knowledge_hits:
                results.append(SearchResult(
                    content=hit.get("content", ""),
                    score=hit.get("score", 0.0),
                    result_type="knowledge",
                    source=hit.get("metadata", {}).get("document_id", ""),
                    metadata=hit.get("metadata", {}),
                ))

        # Search facts
        if query.include_facts:
            fact_hits = await self._vector.search(
                tenant_id=query.tenant_id,
                query=query.query,
                top_k=query.top_k,
                namespace="facts",
                filters={"member_id": query.member_id} if query.member_id else None,
            )
            for hit in fact_hits:
                results.append(SearchResult(
                    content=hit.get("content", ""),
                    score=hit.get("score", 0.0),
                    result_type="fact",
                    source="vector_search",
                    metadata=hit.get("metadata", {}),
                ))

        return results

    async def _graph_search(self, query: SearchQuery) -> list[SearchResult]:
        """Structured search in the knowledge graph."""
        results: list[SearchResult] = []

        if query.member_id:
            # Get facts for specific member
            facts = await self._graph.get_member_facts(
                tenant_id=query.tenant_id,
                member_id=query.member_id,
                limit=query.top_k,
            )
            for fact in facts:
                content = f"{fact.get('subject', '')} {fact.get('predicate', '')} {fact.get('value', '')}"
                results.append(SearchResult(
                    content=content,
                    score=float(fact.get("confidence", 0.5)),
                    result_type="fact",
                    source="graph",
                    metadata={
                        "fact_id": fact.get("fact_id", ""),
                        "fact_type": fact.get("fact_type", ""),
                        "member_id": query.member_id,
                    },
                ))
        else:
            # General entity search
            entities = await self._graph.query_nodes(
                label="Entity",
                filters={"tenant_id": query.tenant_id},
                limit=query.top_k,
            )
            query_lower = query.query.lower()
            for entity in entities:
                name = entity.get("name", "")
                if query_lower in name.lower():
                    results.append(SearchResult(
                        content=f"Entity: {name} (Type: {entity.get('entity_type', '')})",
                        score=0.7,
                        result_type="entity",
                        source="graph",
                        metadata=entity,
                    ))

        return results

    async def _keyword_search(self, query: SearchQuery) -> list[SearchResult]:
        """Full-text keyword search in the graph."""
        results: list[SearchResult] = []

        hits = await self._graph.fulltext_search(
            tenant_id=query.tenant_id,
            query_text=query.query,
            limit=query.top_k,
        )
        for hit in hits:
            content = f"{hit.get('subject', '')} {hit.get('predicate', '')} {hit.get('value', '')}"
            results.append(SearchResult(
                content=content,
                score=float(hit.get("_score", 0.5)),
                result_type="fact",
                source="fulltext",
                metadata={
                    "fact_id": hit.get("fact_id", ""),
                    "fact_type": hit.get("fact_type", ""),
                },
            ))

        return results

    async def _get_member_facts(self, query: SearchQuery) -> list[ExtractedFact]:
        """Get all structured facts for a member."""
        if not query.member_id:
            return []

        from app.memory_platform.models import FactType

        raw_facts = await self._graph.get_member_facts(
            tenant_id=query.tenant_id,
            member_id=query.member_id,
            limit=50,
        )

        facts: list[ExtractedFact] = []
        for f in raw_facts:
            try:
                fact_type_str = f.get("fact_type", "attribute")
                try:
                    fact_type = FactType(fact_type_str)
                except ValueError:
                    fact_type = FactType.ATTRIBUTE

                facts.append(ExtractedFact(
                    fact_id=f.get("fact_id", ""),
                    fact_type=fact_type,
                    subject=f.get("subject", ""),
                    predicate=f.get("predicate", ""),
                    value=f.get("value", ""),
                    confidence=float(f.get("confidence", 0.0)),
                    member_id=query.member_id,
                ))
            except Exception:
                continue

        return facts

    # ── Deduplication & Reranking ────────────────────────────────────

    def _deduplicate(self, results: list[SearchResult]) -> list[SearchResult]:
        """Remove duplicate results based on content similarity."""
        seen: dict[str, SearchResult] = {}
        for result in results:
            # Use first 100 chars as dedup key
            key = result.content[:100].strip().lower()
            if key in seen:
                # Keep the one with higher score
                if result.score > seen[key].score:
                    seen[key] = result
            else:
                seen[key] = result
        return list(seen.values())

    def _rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Rerank results using a cross-encoder model."""
        if not self._reranker or not results:
            return results

        try:
            pairs = [(query, r.content) for r in results[:top_k * 2]]
            scores = self._reranker.predict(pairs)

            for i, score in enumerate(scores):
                if i < len(results):
                    results[i].score = float(score)

            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]
        except Exception as exc:
            logger.warning("retrieval.rerank_error", error=str(exc))
            return results

    # ── Context Building ─────────────────────────────────────────────

    def _build_context_summary(
        self,
        results: list[SearchResult],
        facts: list[ExtractedFact],
    ) -> str:
        """Build a human-readable context summary for the orchestrator."""
        parts: list[str] = []

        if facts:
            parts.append("## Bekannte Fakten über das Mitglied")
            for fact in facts[:20]:
                parts.append(f"- **{fact.subject}** {fact.predicate}: {fact.value} "
                           f"(Konfidenz: {fact.confidence:.0%})")

        if results:
            knowledge_results = [r for r in results if r.result_type == "knowledge"]
            if knowledge_results:
                parts.append("\n## Relevantes Wissen aus der Wissensbasis")
                for r in knowledge_results[:5]:
                    parts.append(f"- {r.content[:200]}...")

        return "\n".join(parts) if parts else ""

    # ── Convenience Methods ──────────────────────────────────────────

    async def get_member_context(
        self,
        tenant_id: int,
        member_id: str,
        query: str = "",
    ) -> RetrievalResponse:
        """Get the full context for a member (used by orchestrator)."""
        search_query = SearchQuery(
            query=query or f"Mitglied {member_id}",
            tenant_id=tenant_id,
            member_id=member_id,
            top_k=20,
            search_type="hybrid",
            include_facts=True,
            include_knowledge=True,
            include_episodic=True,
        )
        return await self.search(search_query)

    async def search_knowledge(
        self,
        tenant_id: int,
        query: str,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Search only the knowledge base (used by knowledge API)."""
        search_query = SearchQuery(
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
            search_type="vector",
            include_facts=False,
            include_knowledge=True,
            include_episodic=False,
        )
        response = await self.search(search_query)
        return response.results

    async def get_campaign_segments(
        self,
        tenant_id: int,
        criteria: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Get member segments for campaign targeting.

        This enables the Campaign Engine to use the knowledge graph
        for advanced segmentation queries.
        """
        results: list[dict[str, Any]] = []

        # Build graph query from criteria
        fact_type = criteria.get("fact_type")
        predicate = criteria.get("predicate")
        value = criteria.get("value")

        if fact_type or predicate:
            filters: dict[str, Any] = {"tenant_id": tenant_id}
            if fact_type:
                filters["fact_type"] = fact_type
            if predicate:
                filters["predicate"] = predicate

            facts = await self._graph.query_nodes(
                label="Fact",
                filters=filters,
                limit=1000,
            )

            # Group by member_id
            member_facts: dict[str, list[dict]] = {}
            for fact in facts:
                mid = fact.get("member_id", "")
                if not mid:
                    continue
                if value and value.lower() not in str(fact.get("value", "")).lower():
                    continue
                member_facts.setdefault(mid, []).append(fact)

            for mid, mfacts in member_facts.items():
                results.append({
                    "member_id": mid,
                    "matching_facts": len(mfacts),
                    "facts": mfacts[:5],
                })

        return results

    @property
    def query_count(self) -> int:
        return self._query_count


# ── Singleton ────────────────────────────────────────────────────────

_service: RetrievalService | None = None


def get_retrieval_service() -> RetrievalService:
    """Return the singleton retrieval service."""
    global _service
    if _service is None:
        _service = RetrievalService()
    return _service
