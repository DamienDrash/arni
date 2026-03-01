"""ARIIA v2.0 – Knowledge Manager.

Implements a two-tier knowledge architecture:
1. Shared Knowledge: Platform-wide knowledge accessible to all tenants
   (e.g., general fitness knowledge, FAQ templates, best practices)
2. Tenant Knowledge: Tenant-specific knowledge base
   (e.g., studio-specific info, pricing, custom FAQs)

Both collections are searched in parallel and results are merged
with configurable weighting.

Architecture:
    Query → [Shared Collection, Tenant Collection] → Parallel Search → Merge & Rank
"""
from __future__ import annotations

import asyncio
import os
import re
import time
import structlog
from dataclasses import dataclass, field
from typing import Any, Optional

logger = structlog.get_logger()


# ─── Constants ────────────────────────────────────────────────────────────────

SHARED_COLLECTION = "ariia_shared_knowledge"
TENANT_COLLECTION_PREFIX = "ariia_kb_"
MEMBER_COLLECTION_PREFIX = "ariia_member_memory_"

DEFAULT_SHARED_WEIGHT = 0.3
DEFAULT_TENANT_WEIGHT = 0.7
DEFAULT_N_RESULTS = 5


@dataclass
class KnowledgeResult:
    """A single knowledge search result."""
    content: str
    source: str  # "shared" or "tenant" or "member"
    score: float  # Distance score (lower = more relevant)
    metadata: dict[str, Any] = field(default_factory=dict)
    collection: str = ""

    @property
    def weighted_score(self) -> float:
        """Score adjusted by source weight."""
        return self.score

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "source": self.source,
            "score": self.score,
            "collection": self.collection,
            "metadata": self.metadata,
        }


@dataclass
class KnowledgeSearchResult:
    """Combined results from multi-collection search."""
    query: str
    results: list[KnowledgeResult] = field(default_factory=list)
    shared_count: int = 0
    tenant_count: int = 0
    member_count: int = 0
    search_time_ms: float = 0
    collections_searched: list[str] = field(default_factory=list)

    @property
    def total_results(self) -> int:
        return len(self.results)

    @property
    def has_results(self) -> bool:
        return len(self.results) > 0

    @property
    def best_result(self) -> Optional[KnowledgeResult]:
        return self.results[0] if self.results else None

    def to_context_string(self, max_results: int = 5) -> str:
        """Format results as a context string for LLM injection."""
        if not self.results:
            return ""

        parts = []
        for i, r in enumerate(self.results[:max_results], 1):
            source_label = {
                "shared": "Allgemeines Wissen",
                "tenant": "Studio-Wissen",
                "member": "Mitglieder-Wissen",
            }.get(r.source, r.source)
            parts.append(f"[{source_label} #{i}]: {r.content}")

        return "\n\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "total_results": self.total_results,
            "shared_count": self.shared_count,
            "tenant_count": self.tenant_count,
            "member_count": self.member_count,
            "search_time_ms": self.search_time_ms,
            "collections_searched": self.collections_searched,
            "results": [r.to_dict() for r in self.results],
        }


# ─── Collection Name Helpers ──────────────────────────────────────────────────

def get_tenant_collection_name(tenant_slug: str) -> str:
    """Get the ChromaDB collection name for a tenant's knowledge base."""
    safe = re.sub(r"[^a-z0-9_-]", "_", (tenant_slug or "default").lower())
    return f"{TENANT_COLLECTION_PREFIX}{safe}"


def get_member_collection_name(tenant_slug: str) -> str:
    """Get the ChromaDB collection name for a tenant's member memories."""
    safe = re.sub(r"[^a-z0-9_-]", "_", (tenant_slug or "default").lower())
    return f"{MEMBER_COLLECTION_PREFIX}{safe}"


# ─── Knowledge Manager ────────────────────────────────────────────────────────

class KnowledgeManager:
    """Manages multi-tier knowledge retrieval with parallel search.

    Tier 1: Shared knowledge (platform-wide)
    Tier 2: Tenant-specific knowledge
    Tier 3: Member-specific memory (optional)
    """

    def __init__(
        self,
        shared_weight: float = DEFAULT_SHARED_WEIGHT,
        tenant_weight: float = DEFAULT_TENANT_WEIGHT,
        chroma_db_path: str = "data/chroma_db",
    ):
        self._shared_weight = shared_weight
        self._tenant_weight = tenant_weight
        self._chroma_db_path = chroma_db_path
        self._stores: dict[str, Any] = {}  # Lazy-loaded stores

    def _get_store(self, collection_name: str):
        """Lazy-load a KnowledgeStore for a collection."""
        if collection_name not in self._stores:
            from app.knowledge.store import KnowledgeStore
            try:
                store = KnowledgeStore(
                    collection_name=collection_name,
                    db_path=self._chroma_db_path,
                )
                self._stores[collection_name] = store
            except Exception as e:
                logger.error(
                    "knowledge.store_init_failed",
                    collection=collection_name,
                    error=str(e),
                )
                return None
        return self._stores.get(collection_name)

    # ─── Search ───────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        tenant_slug: str,
        n_results: int = DEFAULT_N_RESULTS,
        include_shared: bool = True,
        include_member: bool = False,
        member_id: Optional[str] = None,
    ) -> KnowledgeSearchResult:
        """Search across multiple knowledge collections in parallel.

        Args:
            query: The search query.
            tenant_slug: Tenant identifier for collection lookup.
            n_results: Max results per collection.
            include_shared: Whether to search shared knowledge.
            include_member: Whether to search member memory.
            member_id: Required if include_member is True.

        Returns:
            Merged and ranked search results.
        """
        start_time = time.time()
        search_result = KnowledgeSearchResult(query=query)

        # Build search tasks
        tasks = []
        collections = []

        # Tenant-specific knowledge (always included)
        tenant_collection = get_tenant_collection_name(tenant_slug)
        tasks.append(self._search_collection(
            tenant_collection, query, n_results, "tenant",
        ))
        collections.append(tenant_collection)

        # Shared knowledge
        if include_shared:
            tasks.append(self._search_collection(
                SHARED_COLLECTION, query, n_results, "shared",
            ))
            collections.append(SHARED_COLLECTION)

        # Member memory
        if include_member and member_id:
            member_collection = get_member_collection_name(tenant_slug)
            tasks.append(self._search_collection(
                member_collection, query, n_results, "member",
            ))
            collections.append(member_collection)

        # Execute searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results
        all_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("knowledge.search_error", error=str(result))
                continue
            if isinstance(result, list):
                all_results.extend(result)

        # Apply source weighting
        for r in all_results:
            if r.source == "shared":
                r.score = r.score * (1 + (1 - self._shared_weight))
                search_result.shared_count += 1
            elif r.source == "tenant":
                r.score = r.score * (1 + (1 - self._tenant_weight))
                search_result.tenant_count += 1
            elif r.source == "member":
                search_result.member_count += 1

        # Sort by weighted score (lower = better for distance metrics)
        all_results.sort(key=lambda r: r.score)

        # Limit total results
        search_result.results = all_results[:n_results * 2]
        search_result.collections_searched = collections
        search_result.search_time_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(
            "knowledge.search_complete",
            query_length=len(query),
            total_results=search_result.total_results,
            shared=search_result.shared_count,
            tenant=search_result.tenant_count,
            member=search_result.member_count,
            time_ms=search_result.search_time_ms,
        )

        return search_result

    async def _search_collection(
        self,
        collection_name: str,
        query: str,
        n_results: int,
        source: str,
    ) -> list[KnowledgeResult]:
        """Search a single collection and return typed results."""
        store = self._get_store(collection_name)
        if not store:
            return []

        try:
            # Run synchronous ChromaDB query in thread pool
            loop = asyncio.get_event_loop()
            raw_results = await loop.run_in_executor(
                None, store.query, query, n_results,
            )

            if not raw_results or not raw_results.get("documents"):
                return []

            results = []
            documents = raw_results.get("documents", [[]])[0]
            distances = raw_results.get("distances", [[]])[0]
            metadatas = raw_results.get("metadatas", [[]])[0]

            for i, doc in enumerate(documents):
                score = distances[i] if i < len(distances) else 1.0
                meta = metadatas[i] if i < len(metadatas) else {}

                results.append(KnowledgeResult(
                    content=doc,
                    source=source,
                    score=score,
                    metadata=meta,
                    collection=collection_name,
                ))

            return results

        except Exception as e:
            logger.error(
                "knowledge.collection_search_failed",
                collection=collection_name,
                error=str(e),
            )
            return []

    # ─── Shared Knowledge Management ──────────────────────────────────

    async def add_shared_knowledge(
        self,
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
        ids: Optional[list[str]] = None,
    ) -> int:
        """Add documents to the shared knowledge collection.

        Args:
            documents: List of text documents.
            metadatas: Optional metadata for each document.
            ids: Optional document IDs.

        Returns:
            Number of documents added.
        """
        store = self._get_store(SHARED_COLLECTION)
        if not store:
            return 0

        if not ids:
            import uuid
            ids = [f"shared-{uuid.uuid4().hex[:12]}" for _ in documents]

        if not metadatas:
            metadatas = [{"source": "shared", "type": "knowledge"} for _ in documents]

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, store.upsert_documents, documents, metadatas, ids,
            )
            logger.info("knowledge.shared_added", count=len(documents))
            return len(documents)
        except Exception as e:
            logger.error("knowledge.shared_add_failed", error=str(e))
            return 0

    async def add_tenant_knowledge(
        self,
        tenant_slug: str,
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
        ids: Optional[list[str]] = None,
    ) -> int:
        """Add documents to a tenant's knowledge collection."""
        collection = get_tenant_collection_name(tenant_slug)
        store = self._get_store(collection)
        if not store:
            return 0

        if not ids:
            import uuid
            ids = [f"tenant-{uuid.uuid4().hex[:12]}" for _ in documents]

        if not metadatas:
            metadatas = [
                {"source": "tenant", "tenant_slug": tenant_slug}
                for _ in documents
            ]

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, store.upsert_documents, documents, metadatas, ids,
            )
            logger.info(
                "knowledge.tenant_added",
                tenant=tenant_slug,
                count=len(documents),
            )
            return len(documents)
        except Exception as e:
            logger.error(
                "knowledge.tenant_add_failed",
                tenant=tenant_slug,
                error=str(e),
            )
            return 0

    # ─── Statistics ───────────────────────────────────────────────────

    async def get_stats(self, tenant_slug: Optional[str] = None) -> dict:
        """Get knowledge base statistics."""
        stats = {"shared_count": 0, "tenant_count": 0}

        shared_store = self._get_store(SHARED_COLLECTION)
        if shared_store:
            try:
                stats["shared_count"] = shared_store.count()
            except Exception:
                pass

        if tenant_slug:
            tenant_collection = get_tenant_collection_name(tenant_slug)
            tenant_store = self._get_store(tenant_collection)
            if tenant_store:
                try:
                    stats["tenant_count"] = tenant_store.count()
                    stats["tenant_collection"] = tenant_collection
                except Exception:
                    pass

        return stats
