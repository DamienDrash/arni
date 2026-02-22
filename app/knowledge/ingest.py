from __future__ import annotations

import glob
import hashlib
import os
import re

import structlog

from app.knowledge.store import KnowledgeStore

logger = structlog.get_logger()

KNOWLEDGE_DIR = "data/knowledge"
_SLUG_RE = re.compile(r"[^a-z0-9_-]")


def collection_name_for_slug(tenant_slug: str) -> str:
    """Return the ChromaDB collection name for a given tenant slug."""
    safe = _SLUG_RE.sub("_", (tenant_slug or "system").lower())
    return f"arni_knowledge_{safe}"


def ingest_knowledge(knowledge_dir: str = KNOWLEDGE_DIR, collection_name: str = "arni_knowledge_system") -> dict:
    """Scan knowledge directory, chunk markdown files, and upsert into ChromaDB.

    Uses upsert (not add) so re-ingesting after edits is always safe.
    """
    files = glob.glob(os.path.join(knowledge_dir, "*.md"))
    if not files:
        logger.info("knowledge.ingest.no_files", dir=knowledge_dir)
        return {"status": "empty", "knowledge_dir": knowledge_dir, "collection_name": collection_name, "files": 0, "chunks": 0}

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for file_path in sorted(files):
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            logger.warning("knowledge.ingest.read_failed", path=file_path, error=str(exc))
            continue

        filename = os.path.basename(file_path)
        # Split on markdown section headers (## or ###)
        raw_chunks = re.split(r"\n(?=#{1,3} )", content)

        for i, chunk in enumerate(raw_chunks):
            if not chunk.strip():
                continue
            # Deterministic ID includes filename + chunk index for stable upserts
            chunk_id = hashlib.md5(f"{collection_name}:{filename}:{i}".encode()).hexdigest()
            documents.append(chunk.strip())
            metadatas.append({"source": filename, "chunk_index": i})
            ids.append(chunk_id)

    if not documents:
        return {"status": "empty", "knowledge_dir": knowledge_dir, "collection_name": collection_name, "files": len(files), "chunks": 0}

    store = KnowledgeStore(collection_name=collection_name)
    store.upsert_documents(documents, metadatas, ids)

    logger.info("knowledge.ingest.done", collection=collection_name, files=len(files), chunks=len(documents))
    return {"status": "ok", "knowledge_dir": knowledge_dir, "collection_name": collection_name, "files": len(files), "chunks": len(documents)}


if __name__ == "__main__":
    ingest_knowledge()
