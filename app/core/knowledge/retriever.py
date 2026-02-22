from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()

KNOWLEDGE_DB_PATH = os.path.join("data", "chroma_db")
DEFAULT_COLLECTION = "arni_knowledge_system"


@dataclass
class SearchResult:
    id: str
    content: str
    score: float
    metadata: dict[str, Any]


class HybridRetriever:
    """ChromaDB-backed knowledge retriever (semantic search via default ONNX embeddings).

    One instance per request — instantiate with the correct tenant collection name.
    Falls back to empty results on any infrastructure error so agents never crash.
    """

    def __init__(self, collection_name: str = DEFAULT_COLLECTION) -> None:
        self.collection_name = collection_name or DEFAULT_COLLECTION
        self._collection = None
        try:
            import chromadb
            from chromadb.config import Settings

            db_path = os.path.abspath(KNOWLEDGE_DB_PATH)
            os.makedirs(db_path, exist_ok=True)
            client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(anonymized_telemetry=False, is_persistent=True),
            )
            self._collection = client.get_or_create_collection(name=self.collection_name)
            logger.debug("retriever.initialized", collection=self.collection_name)
        except Exception as exc:
            logger.error("retriever.init_failed", collection=self.collection_name, error=str(exc))

    def search(self, query: str, top_n: int = 3) -> list[SearchResult]:
        """Query the ChromaDB collection and return ranked results."""
        if not self._collection:
            logger.warning("retriever.no_collection", collection=self.collection_name)
            return []

        count = 0
        try:
            count = self._collection.count()
        except Exception:
            pass

        if count == 0:
            logger.info("retriever.empty_collection", collection=self.collection_name)
            return []

        n = min(top_n, count)
        try:
            raw = self._collection.query(query_texts=[query], n_results=n)
        except Exception as exc:
            logger.error("retriever.query_failed", error=str(exc))
            return []

        docs = (raw.get("documents") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        ids = (raw.get("ids") or [[]])[0]

        results: list[SearchResult] = []
        for doc_id, doc, dist, meta in zip(ids, docs, dists, metas):
            # ChromaDB returns L2 distance; convert to 0-1 similarity score
            score = round(1.0 / (1.0 + dist), 4)
            results.append(SearchResult(id=doc_id, content=doc, score=score, metadata=meta or {}))

        logger.info("retriever.search_ok", collection=self.collection_name, query=query[:60], hits=len(results))
        return results
