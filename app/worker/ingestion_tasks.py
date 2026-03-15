"""ARQ task functions for document ingestion.

These execute in the ariia-ingestion-worker process, fully isolated from the
API process. Status is communicated via .meta.json sidecar files on the shared
ariia_data volume — no shared in-memory state required.

Job lifecycle:
  1. API: register_pending() → writes status=processing to .meta.json + enqueues job
  2. Worker: ingest_file_task() → parses file, indexes to ChromaDB, updates .meta.json
  3. Frontend: polls GET /memory-platform/knowledge/documents → reads .meta.json status
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


# ── File Ingestion ─────────────────────────────────────────────────────────────

async def ingest_file_task(
    ctx: dict,
    *,
    tenant_id: int,
    staging_path: str,
    original_filename: str,
    content_type: str,
    doc_id: str,
    content_hash: str,
    tenant_slug: str,
) -> dict:
    """Parse a staged file and index it into ChromaDB.

    Called by the API after writing the file to staging_path.
    Writes final status (indexed / error) back to .meta.json on the shared volume.

    ARQ retries on exception up to the configured max_tries.
    """
    from app.memory_platform.ingestion import get_ingestion_service

    service = get_ingestion_service()
    try:
        doc = await service.ingest_file(
            tenant_id=tenant_id,
            file_path=staging_path,
            original_filename=original_filename,
            content_type=content_type,
            predefined_doc_id=doc_id,
            metadata={"content_hash": content_hash},
            tenant_slug=tenant_slug,
        )
        logger.info(
            "worker.ingest_file_task.done",
            doc_id=doc_id,
            status=doc.status,
            chunks=doc.chunk_count,
            tenant=tenant_slug,
        )
        return {"status": doc.status, "document_id": doc.document_id, "chunks": doc.chunk_count}

    except Exception as exc:
        logger.error("worker.ingest_file_task.failed", doc_id=doc_id, error=str(exc))
        _write_error_meta(doc_id, tenant_id, original_filename, content_type, str(exc))
        raise  # re-raise so ARQ records the failure and triggers retry

    finally:
        # Always delete the staging file — success or failure
        if os.path.exists(staging_path):
            try:
                os.unlink(staging_path)
            except OSError as e:
                logger.warning("worker.staging_cleanup_failed", path=staging_path, error=str(e))


# ── Text Ingestion ─────────────────────────────────────────────────────────────

async def ingest_text_task(
    ctx: dict,
    *,
    tenant_id: int,
    content: str,
    title: str,
    tenant_slug: str,
) -> dict:
    """Ingest raw text/markdown content into the knowledge base."""
    from app.memory_platform.ingestion import get_ingestion_service

    service = get_ingestion_service()
    try:
        doc = await service.ingest_text(
            tenant_id=tenant_id,
            content=content,
            title=title,
            tenant_slug=tenant_slug,
        )
        logger.info(
            "worker.ingest_text_task.done",
            doc_id=doc.document_id,
            status=doc.status,
            chunks=doc.chunk_count,
            tenant=tenant_slug,
        )
        return {"status": doc.status, "document_id": doc.document_id}

    except Exception as exc:
        logger.error("worker.ingest_text_task.failed", title=title, tenant=tenant_slug, error=str(exc))
        raise  # re-raise so ARQ records the failure and triggers retry


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_error_meta(
    doc_id: str,
    tenant_id: int,
    filename: str,
    content_type: str,
    error: str,
) -> None:
    """Write a minimal error .meta.json so the API can surface the failure.

    Called when the task itself raises before ingest_file() has a chance to
    write the error — e.g. a crash before parsing even starts.
    """
    from app.memory_platform.ingestion import UPLOAD_DIR

    path = os.path.join(UPLOAD_DIR, str(tenant_id), f"{doc_id}.meta.json")
    # Don't overwrite an existing .meta.json that already has a better status
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("status") in ("indexed", "error"):
                return
        except Exception:
            pass

    data = {
        "document_id": doc_id,
        "tenant_id": tenant_id,
        "filename": filename,
        "original_filename": filename,
        "source_type": "file_upload",
        "content_type": content_type,
        "file_size": 0,
        "chunk_count": 0,
        "status": "error",
        "error_message": f"Verarbeitungsfehler: {error[:500]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": "",
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
