from __future__ import annotations

import glob
import hashlib
import os
import re

import structlog

from app.knowledge.store import KnowledgeStore

logger = structlog.get_logger()

KNOWLEDGE_DIR = "data/knowledge"
TENANT_KNOWLEDGE_DIR = "data/knowledge/tenants"
_SLUG_RE = re.compile(r"[^a-z0-9_-]")


def collection_name_for_slug(tenant_slug: str) -> str:
    """Return the ChromaDB collection name for a given tenant slug."""
    safe = _SLUG_RE.sub("_", (tenant_slug or "system").lower())
    return f"ariia_knowledge_{safe}"


def ingest_tenant_knowledge(tenant_id: int | None = None, tenant_slug: str | None = None) -> dict:
    """Ingest global knowledge AND tenant-specific knowledge for a studio."""
    from app.core.db import SessionLocal
    from app.core.models import Tenant
    
    # 1. Resolve slug and ID
    if tenant_id and not tenant_slug:
        db = SessionLocal()
        t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        tenant_slug = t.slug if t else "system"
        db.close()
    
    slug = tenant_slug or "system"
    collection_name = collection_name_for_slug(slug)
    
    # 2. Gather files: System defaults + Tenant overrides
    file_list = []
    
    # Global files
    global_files = glob.glob(os.path.join(KNOWLEDGE_DIR, "*.md"))
    file_list.extend(global_files)
    
    # Tenant files (these override system defaults if name matches, or add new context)
    if slug != "system":
        t_path = os.path.join(TENANT_KNOWLEDGE_DIR, slug)
        if os.path.exists(t_path):
            # Recursively find all markdown files in tenant knowledge
            for root, _, files in os.walk(t_path):
                for f in files:
                    if f.endswith(".md"):
                        file_list.append(os.path.join(root, f))

    if not file_list:
        return {"status": "empty", "collection": collection_name}

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for file_path in sorted(file_list):
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue

        filename = os.path.basename(file_path)
        source_type = "tenant" if TENANT_KNOWLEDGE_DIR in file_path else "system"
        
        # SMARTER CHUNKING: Split by headers but keep headers in chunks
        # We look for #, ##, ### at the start of a line
        raw_chunks = re.split(r"(?=\n#{1,3} )", "\n" + content)

        for i, chunk in enumerate(raw_chunks):
            chunk = chunk.strip()
            if not chunk:
                continue
            
            # Deterministic ID includes filename + chunk content hash for stable upserts
            content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
            chunk_id = hashlib.md5(f"{collection_name}:{filename}:{i}:{content_hash}".encode()).hexdigest()
            
            documents.append(chunk)
            metadatas.append({
                "source": filename,
                "type": source_type,
                "tenant_slug": slug,
                "path": file_path
            })
            ids.append(chunk_id)

    if not documents:
        return {"status": "empty", "collection": collection_name}

    store = KnowledgeStore(collection_name=collection_name)
    store.upsert_documents(documents, metadatas, ids)

    logger.info("knowledge.ingest.success", collection=collection_name, chunks=len(documents))
    return {"status": "ok", "collection": collection_name, "chunks": len(documents)}


def ingest_all_tenants() -> dict:
    """Automated sync for all active studios in the system."""
    from app.core.db import SessionLocal
    from app.core.models import Tenant
    
    db = SessionLocal()
    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
    results = {}
    
    # System first
    results["system"] = ingest_tenant_knowledge(tenant_slug="system")
    
    for t in tenants:
        results[t.slug] = ingest_tenant_knowledge(tenant_id=t.id, tenant_slug=t.slug)
    
    db.close()
    return results


if __name__ == "__main__":
    ingest_all_tenants()
