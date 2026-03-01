"""ARIIA v2.0 – Knowledge Base Adapter.

@ARCH: Sprint 2 (Integration Roadmap), Task S2.1
Concrete adapter for the ARIIA Knowledge Base (ChromaDB-backed).
Wraps the existing HybridRetriever and KnowledgeStore into the BaseAdapter
interface, providing standardized capability routing for the DynamicToolResolver.

Supported Capabilities:
  - knowledge.search            → Semantic search in tenant knowledge base
  - knowledge.ingest            → Ingest/re-ingest tenant knowledge files
  - knowledge.list_collections  → List available ChromaDB collections
  - knowledge.document.add      → Add a single document to the knowledge base
  - knowledge.document.delete   → Delete documents by ID or metadata filter
  - knowledge.stats             → Get collection statistics (document count, etc.)
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class KnowledgeAdapter(BaseAdapter):
    """Adapter for the ARIIA Knowledge Base (ChromaDB vector store).

    Routes capability calls to the existing HybridRetriever and KnowledgeStore,
    wrapping results in the standardized AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "knowledge"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "knowledge.search",
            "knowledge.ingest",
            "knowledge.list_collections",
            "knowledge.document.add",
            "knowledge.document.delete",
            "knowledge.stats",
        ]

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate knowledge base method."""
        handlers = {
            "knowledge.search": self._search,
            "knowledge.ingest": self._ingest,
            "knowledge.list_collections": self._list_collections,
            "knowledge.document.add": self._add_document,
            "knowledge.document.delete": self._delete_document,
            "knowledge.stats": self._stats,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── knowledge.search ─────────────────────────────────────────────

    async def _search(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Semantic search in the tenant's knowledge base.

        Required kwargs:
            query (str): The search query or question.
        Optional kwargs:
            collection_name (str): Override the default collection.
            top_n (int): Number of results to return (default: 3).
        """
        query = kwargs.get("query")
        if not query:
            return AdapterResult(
                success=False,
                error="Parameter 'query' is required for knowledge.search",
                error_code="MISSING_PARAM",
            )

        collection_name = kwargs.get("collection_name") or self._resolve_collection(tenant_id)
        top_n = kwargs.get("top_n", 3)

        try:
            from app.core.knowledge.retriever import HybridRetriever

            retriever = HybridRetriever(collection_name=collection_name)
            results = retriever.search(query, top_n=top_n)

            if not results:
                return AdapterResult(
                    success=True,
                    data="Keine passenden Informationen in der Wissensbasis gefunden.",
                    metadata={"collection": collection_name, "hits": 0},
                )

            output = []
            for res in results:
                source = res.metadata.get("source", "Wissensbasis")
                output.append({
                    "id": res.id,
                    "content": res.content,
                    "score": res.score,
                    "source": source,
                })

            return AdapterResult(
                success=True,
                data=output,
                metadata={"collection": collection_name, "hits": len(output)},
            )
        except Exception as exc:
            logger.error("knowledge_adapter.search_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Knowledge search failed: {exc}")

    # ── knowledge.ingest ─────────────────────────────────────────────

    async def _ingest(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Ingest or re-ingest tenant knowledge files into ChromaDB.

        Optional kwargs:
            tenant_slug (str): Override tenant slug for collection naming.
        """
        tenant_slug = kwargs.get("tenant_slug")

        try:
            from app.knowledge.ingest import ingest_tenant_knowledge

            result = ingest_tenant_knowledge(tenant_id=tenant_id, tenant_slug=tenant_slug)

            return AdapterResult(
                success=True,
                data=result,
                metadata={"tenant_id": tenant_id},
            )
        except Exception as exc:
            logger.error("knowledge_adapter.ingest_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Knowledge ingest failed: {exc}")

    # ── knowledge.list_collections ───────────────────────────────────

    async def _list_collections(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List all available ChromaDB collections.

        Returns a list of collection names and their document counts.
        """
        try:
            import chromadb
            from chromadb.config import Settings
            import os

            db_path = os.path.abspath(os.path.join("data", "chroma_db"))
            if not os.path.exists(db_path):
                return AdapterResult(
                    success=True,
                    data=[],
                    metadata={"message": "No ChromaDB database found"},
                )

            client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(anonymized_telemetry=False, is_persistent=True),
            )
            collections = client.list_collections()

            collection_info = []
            for coll in collections:
                try:
                    count = coll.count()
                except Exception:
                    count = -1
                collection_info.append({
                    "name": coll.name,
                    "document_count": count,
                })

            return AdapterResult(
                success=True,
                data=collection_info,
                metadata={"total_collections": len(collection_info)},
            )
        except Exception as exc:
            logger.error("knowledge_adapter.list_collections_failed", error=str(exc))
            return AdapterResult(success=False, error=f"List collections failed: {exc}")

    # ── knowledge.document.add ───────────────────────────────────────

    async def _add_document(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Add a single document to the knowledge base.

        Required kwargs:
            content (str): The document text content.
        Optional kwargs:
            doc_id (str): Custom document ID (auto-generated if not provided).
            source (str): Source label for the document.
            collection_name (str): Override the default collection.
            metadata (dict): Additional metadata to attach.
        """
        content = kwargs.get("content")
        if not content:
            return AdapterResult(
                success=False,
                error="Parameter 'content' is required for knowledge.document.add",
                error_code="MISSING_PARAM",
            )

        collection_name = kwargs.get("collection_name") or self._resolve_collection(tenant_id)
        source = kwargs.get("source", "manual")
        doc_id = kwargs.get("doc_id")
        extra_metadata = kwargs.get("metadata", {})

        if not doc_id:
            import hashlib
            doc_id = f"doc_{hashlib.md5(content[:200].encode()).hexdigest()[:12]}"

        try:
            from app.knowledge.store import KnowledgeStore

            store = KnowledgeStore(collection_name=collection_name)
            metadata = {"source": source, "tenant_id": tenant_id, **extra_metadata}
            store.upsert_documents(
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id],
            )

            return AdapterResult(
                success=True,
                data={"doc_id": doc_id, "collection": collection_name, "action": "upserted"},
                metadata={"collection": collection_name},
            )
        except Exception as exc:
            logger.error("knowledge_adapter.add_document_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Add document failed: {exc}")

    # ── knowledge.document.delete ────────────────────────────────────

    async def _delete_document(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Delete documents from the knowledge base.

        Optional kwargs (at least one required):
            doc_ids (list[str]): List of document IDs to delete.
            where_filter (dict): Metadata filter for bulk deletion.
            collection_name (str): Override the default collection.
        """
        doc_ids = kwargs.get("doc_ids")
        where_filter = kwargs.get("where_filter")
        collection_name = kwargs.get("collection_name") or self._resolve_collection(tenant_id)

        if not doc_ids and not where_filter:
            return AdapterResult(
                success=False,
                error="Either 'doc_ids' or 'where_filter' is required for knowledge.document.delete",
                error_code="MISSING_PARAM",
            )

        try:
            from app.knowledge.store import KnowledgeStore

            store = KnowledgeStore(collection_name=collection_name)

            if doc_ids:
                store.delete_documents(ids=doc_ids)
                return AdapterResult(
                    success=True,
                    data={"deleted_ids": doc_ids, "collection": collection_name},
                )
            elif where_filter:
                store.delete_by_metadata(where_filter=where_filter)
                return AdapterResult(
                    success=True,
                    data={"filter": where_filter, "collection": collection_name, "action": "deleted_by_filter"},
                )

            return AdapterResult(success=False, error="No deletion criteria provided")
        except Exception as exc:
            logger.error("knowledge_adapter.delete_document_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Delete document failed: {exc}")

    # ── knowledge.stats ──────────────────────────────────────────────

    async def _stats(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get statistics for a knowledge base collection.

        Optional kwargs:
            collection_name (str): Override the default collection.
        """
        collection_name = kwargs.get("collection_name") or self._resolve_collection(tenant_id)

        try:
            from app.knowledge.store import KnowledgeStore

            store = KnowledgeStore(collection_name=collection_name)
            count = store.count()

            return AdapterResult(
                success=True,
                data={
                    "collection": collection_name,
                    "document_count": count,
                    "status": "active" if count > 0 else "empty",
                },
            )
        except Exception as exc:
            logger.error("knowledge_adapter.stats_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Stats retrieval failed: {exc}")

    # ── Health Check ─────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if the ChromaDB knowledge base is accessible."""
        try:
            import chromadb
            from chromadb.config import Settings
            import os

            db_path = os.path.abspath(os.path.join("data", "chroma_db"))
            if not os.path.exists(db_path):
                return AdapterResult(
                    success=True,
                    data={"status": "NOT_CONFIGURED", "reason": "ChromaDB path does not exist"},
                )

            client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(anonymized_telemetry=False, is_persistent=True),
            )
            collections = client.list_collections()

            return AdapterResult(
                success=True,
                data={
                    "status": "HEALTHY",
                    "adapter": self.integration_id,
                    "collections": len(collections),
                },
            )
        except Exception as exc:
            logger.warning(
                "knowledge_adapter.health_check_failed",
                error=str(exc),
                tenant_id=tenant_id,
            )
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": str(exc)},
            )

    # ── Helpers ───────────────────────────────────────────────────────

    def _resolve_collection(self, tenant_id: int) -> str:
        """Resolve the ChromaDB collection name for a tenant.

        Falls back to the system default collection if tenant lookup fails.
        """
        try:
            from app.core.db import SessionLocal
            from app.core.models import Tenant
            from app.knowledge.ingest import collection_name_for_slug

            db = SessionLocal()
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            slug = tenant.slug if tenant else "system"
            db.close()
            return collection_name_for_slug(slug)
        except Exception:
            from app.core.knowledge.retriever import DEFAULT_COLLECTION
            return DEFAULT_COLLECTION
