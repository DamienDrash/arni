"""Vector store abstraction – Qdrant with ChromaDB fallback.

Provides semantic search capabilities for the Memory Platform.
Falls back to the existing ChromaDB when Qdrant is not available,
ensuring backward compatibility during migration.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

import structlog

from app.memory_platform.config import get_config

logger = structlog.get_logger()

CHROMA_DB_PATH = os.path.join("data", "chroma_db")


class VectorStore:
    """Unified vector store with Qdrant primary and ChromaDB fallback."""

    def __init__(self) -> None:
        self._qdrant_client: Any = None
        self._chroma_client: Any = None
        self._embedding_fn: Any = None
        self._using_qdrant: bool = False
        self._initialised: bool = False

    async def initialise(self) -> None:
        """Connect to Qdrant or fall back to ChromaDB."""
        if self._initialised:
            return

        # Try Qdrant first
        cfg = get_config().qdrant
        try:
            from qdrant_client import QdrantClient  # type: ignore[import-untyped]

            self._qdrant_client = QdrantClient(
                host=cfg.host,
                port=cfg.port,
                api_key=cfg.api_key,
            )
            # Verify connectivity
            self._qdrant_client.get_collections()
            self._using_qdrant = True
            logger.info("vector_store.qdrant_connected", host=cfg.host)
        except Exception as exc:
            logger.warning(
                "vector_store.qdrant_unavailable_fallback_to_chroma",
                error=str(exc),
            )
            self._using_qdrant = False

        # Fall back to ChromaDB
        if not self._using_qdrant:
            try:
                import chromadb
                from chromadb.config import Settings

                db_path = os.path.abspath(CHROMA_DB_PATH)
                os.makedirs(db_path, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(
                    path=db_path,
                    settings=Settings(anonymized_telemetry=False, is_persistent=True),
                )
                logger.info("vector_store.chroma_connected", path=db_path)
            except Exception as exc:
                logger.error("vector_store.chroma_init_failed", error=str(exc))

        # Initialise embedding function
        self._init_embeddings()
        self._initialised = True

    def _init_embeddings(self) -> None:
        """Initialise the sentence-transformer embedding model."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
            self._embedding_fn = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("vector_store.embeddings_loaded", model="all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("vector_store.sentence_transformers_not_available")
            self._embedding_fn = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if self._embedding_fn is None:
            # Return zero vectors as fallback
            dim = get_config().qdrant.embedding_dim
            return [[0.0] * dim for _ in texts]
        return self._embedding_fn.encode(texts).tolist()

    def _collection_name(self, tenant_id: int, namespace: str = "knowledge") -> str:
        """Generate a tenant-scoped collection name."""
        prefix = get_config().qdrant.collection_prefix
        return f"{prefix}{namespace}_t{tenant_id}"

    # ── Collection Management ────────────────────────────────────────

    async def ensure_collection(self, tenant_id: int, namespace: str = "knowledge") -> str:
        """Ensure a collection exists for the given tenant and namespace."""
        name = self._collection_name(tenant_id, namespace)

        if self._using_qdrant:
            from qdrant_client.models import Distance, VectorParams  # type: ignore[import-untyped]
            try:
                self._qdrant_client.get_collection(name)
            except Exception:
                self._qdrant_client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=get_config().qdrant.embedding_dim,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("vector_store.collection_created", name=name)
        else:
            if self._chroma_client:
                self._chroma_client.get_or_create_collection(name=name)

        return name

    # ── Upsert ───────────────────────────────────────────────────────

    async def upsert(
        self,
        tenant_id: int,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        namespace: str = "knowledge",
    ) -> int:
        """Upsert documents into the vector store."""
        if not documents:
            return 0

        collection_name = await self.ensure_collection(tenant_id, namespace)
        metadatas = metadatas or [{} for _ in documents]
        embeddings = self._embed(documents)

        if self._using_qdrant:
            from qdrant_client.models import PointStruct  # type: ignore[import-untyped]
            points = []
            for doc_id, embedding, doc, meta in zip(ids, embeddings, documents, metadatas):
                # Qdrant requires numeric or UUID ids
                numeric_id = int(hashlib.md5(doc_id.encode()).hexdigest()[:16], 16)
                meta_with_content = {**meta, "content": doc, "original_id": doc_id}
                points.append(PointStruct(
                    id=numeric_id,
                    vector=embedding,
                    payload=meta_with_content,
                ))
            self._qdrant_client.upsert(
                collection_name=collection_name,
                points=points,
            )
        else:
            if self._chroma_client:
                collection = self._chroma_client.get_or_create_collection(name=collection_name)
                collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings,
                )

        logger.info(
            "vector_store.upserted",
            collection=collection_name,
            count=len(documents),
        )
        return len(documents)

    # ── Search ───────────────────────────────────────────────────────

    async def search(
        self,
        tenant_id: int,
        query: str,
        top_k: int = 10,
        namespace: str = "knowledge",
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search in the vector store."""
        collection_name = await self.ensure_collection(tenant_id, namespace)
        query_embedding = self._embed([query])[0]

        if self._using_qdrant:
            from qdrant_client.models import Filter, FieldCondition, MatchValue  # type: ignore[import-untyped]

            qdrant_filter = None
            if filters:
                conditions = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
                qdrant_filter = Filter(must=conditions)

            try:
                results = self._qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=query_embedding,
                    limit=top_k,
                    query_filter=qdrant_filter,
                )
                return [
                    {
                        "id": r.payload.get("original_id", str(r.id)),
                        "content": r.payload.get("content", ""),
                        "score": round(r.score, 4),
                        "metadata": {
                            k: v for k, v in r.payload.items()
                            if k not in ("content", "original_id")
                        },
                    }
                    for r in results
                ]
            except Exception as exc:
                logger.error("vector_store.qdrant_search_error", error=str(exc))
                return []
        else:
            if not self._chroma_client:
                return []
            try:
                collection = self._chroma_client.get_or_create_collection(name=collection_name)
                count = collection.count()
                if count == 0:
                    return []
                n = min(top_k, count)
                raw = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n,
                    where=filters if filters else None,
                )
                docs = (raw.get("documents") or [[]])[0]
                dists = (raw.get("distances") or [[]])[0]
                metas = (raw.get("metadatas") or [[]])[0]
                ids = (raw.get("ids") or [[]])[0]
                results = []
                for doc_id, doc, dist, meta in zip(ids, docs, dists, metas):
                    score = round(1.0 / (1.0 + dist), 4)
                    results.append({
                        "id": doc_id,
                        "content": doc,
                        "score": score,
                        "metadata": meta or {},
                    })
                return results
            except Exception as exc:
                logger.error("vector_store.chroma_search_error", error=str(exc))
                return []

    # ── Delete ───────────────────────────────────────────────────────

    async def delete(
        self,
        tenant_id: int,
        ids: list[str],
        namespace: str = "knowledge",
    ) -> int:
        """Delete documents by ID from the vector store."""
        if not ids:
            return 0

        collection_name = await self.ensure_collection(tenant_id, namespace)

        if self._using_qdrant:
            from qdrant_client.models import PointIdsList  # type: ignore[import-untyped]
            numeric_ids = [
                int(hashlib.md5(doc_id.encode()).hexdigest()[:16], 16)
                for doc_id in ids
            ]
            self._qdrant_client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=numeric_ids),
            )
        else:
            if self._chroma_client:
                collection = self._chroma_client.get_or_create_collection(name=collection_name)
                collection.delete(ids=ids)

        return len(ids)

    # ── Stats ────────────────────────────────────────────────────────

    async def get_stats(self, tenant_id: int, namespace: str = "knowledge") -> dict[str, Any]:
        """Return statistics for a tenant's collection."""
        collection_name = self._collection_name(tenant_id, namespace)

        if self._using_qdrant:
            try:
                info = self._qdrant_client.get_collection(collection_name)
                return {
                    "backend": "qdrant",
                    "collection": collection_name,
                    "points_count": info.points_count,
                    "vectors_count": info.vectors_count,
                }
            except Exception:
                return {"backend": "qdrant", "collection": collection_name, "points_count": 0}
        else:
            if self._chroma_client:
                try:
                    collection = self._chroma_client.get_or_create_collection(name=collection_name)
                    return {
                        "backend": "chromadb",
                        "collection": collection_name,
                        "points_count": collection.count(),
                    }
                except Exception:
                    return {"backend": "chromadb", "collection": collection_name, "points_count": 0}
            return {"backend": "none", "points_count": 0}


# ── Singleton ────────────────────────────────────────────────────────

_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the singleton vector store instance."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
