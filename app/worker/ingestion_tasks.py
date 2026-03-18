"""ARIIA v2.0 – Ingestion Worker Tasks.

Vollständiger Pipeline: MinIO Download → Parse → Chunk → Embed → ChromaDB Upsert.

Legacy tasks (ingest_file_task, ingest_text_task) handle the existing
memory-platform knowledge-base flow via .meta.json sidecar files.

Job lifecycle (Sprint 2/3):
  1. API: create_ingestion_job() → status=PENDING, enqueues process_ingestion_job
  2. Worker: process_ingestion_job() → PROCESSING → COMPLETED / FAILED / DEAD_LETTER
  3. Frontend: polls GET /ingestion/jobs/{id} → reads status from DB

Legacy lifecycle (unchanged):
  1. API: register_pending() → writes status=processing to .meta.json + enqueues job
  2. Worker: ingest_file_task() → parses file, indexes to ChromaDB, updates .meta.json
  3. Frontend: polls GET /memory-platform/knowledge/documents → reads .meta.json status
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()


# ── Sprint 2/3: Full MinIO-backed Ingestion Pipeline ──────────────────────────

async def _publish_job_event(redis, job_id: str, event_type: str, data: dict) -> None:
    """Publiziert SSE-Event für Job-Status-Updates."""
    try:
        payload = json.dumps({"type": event_type, "job_id": job_id, **data})
        await redis.publish(f"ariia:job:{job_id}:events", payload)
        # Auch als Redis-Hash für Polling
        await redis.hset(f"ariia:job:{job_id}", mapping={
            "status": event_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **{k: str(v) for k, v in data.items()},
        })
        await redis.expire(f"ariia:job:{job_id}", 3600)
    except Exception as e:
        logger.warning("worker.publish_event_failed", job_id=job_id, error=str(e))


async def process_ingestion_job(
    ctx: dict,
    job_id: str,
    s3_key: str,
    tenant_id: int,
    mime_type: str,
    tenant_slug: str,
) -> dict[str, Any]:
    """
    Haupt-Ingestion-Task.

    Ablauf:
    1. Job → PROCESSING
    2. MinIO Stream-Download → TempFile
    3. Format-Detection + Streaming Parse
    4. Semantic Chunking
    5. Batched Embedding (mit Rate-Limiting)
    6. ChromaDB Upsert (idempotent)
    7. Cleanup + COMPLETED

    Args:
        ctx: arq worker context (contains ``redis`` connection).
        job_id: UUID of the IngestionJob DB record.
        s3_key: MinIO object key for the uploaded file.
        tenant_id: Owning tenant's database ID.
        mime_type: MIME type of the file to process.
        tenant_slug: Tenant slug used for ChromaDB collection naming.

    Returns:
        Status dict with ``status``, ``job_id``, ``chunks``, and ``collection`` keys.
    """
    redis = ctx["redis"]

    # Lazy imports (nur im Worker, nicht im API-Prozess)
    from app.core.db import SessionLocal
    from app.core.models import IngestionJobStatus, Subscription
    from app.gateway.persistence import persistence
    from app.ingestion.parsers.base import ParserRegistry
    # Trigger Parser-Registrierungen
    import app.ingestion.parsers.pdf_parser       # noqa: F401
    import app.ingestion.parsers.docx_parser      # noqa: F401
    import app.ingestion.parsers.csv_parser       # noqa: F401
    import app.ingestion.parsers.pptx_parser          # noqa: F401
    import app.ingestion.parsers.rtf_parser           # noqa: F401
    import app.ingestion.parsers.odt_parser           # noqa: F401
    import app.ingestion.parsers.text_parser      # noqa: F401
    import app.ingestion.parsers.unstructured_parser  # noqa: F401
    from app.ingestion.chunker import SemanticChunker
    from app.ingestion.embedding import get_embedding_service
    from config.settings import get_settings

    get_settings()  # ensure settings are loaded

    logger.info("ingestion.job.started", job_id=job_id, tenant_id=tenant_id, mime_type=mime_type)

    # ── Step 1: Status → PROCESSING ──────────────────────────────────────────
    persistence.update_job_status(job_id, IngestionJobStatus.PROCESSING)
    await _publish_job_event(redis, job_id, "PROCESSING_STARTED", {
        "tenant_id": tenant_id,
        "mime_type": mime_type,
    })

    tmp_path = None

    try:
        # ── Step 2: MinIO Download → TempFile ────────────────────────────────
        from app.storage.minio_client import get_storage_client
        storage = get_storage_client()

        logger.debug("ingestion.downloading", job_id=job_id, s3_key=s3_key)
        tmp_path = await storage.download_to_tempfile(s3_key)

        file_size_mb = tmp_path.stat().st_size / (1024 * 1024)
        logger.info("ingestion.downloaded", job_id=job_id, size_mb=round(file_size_mb, 2))

        # ── Step 3: Streaming Parse ───────────────────────────────────────────
        parser = ParserRegistry.get_parser(mime_type)
        logger.debug("ingestion.parsing", job_id=job_id, parser=type(parser).__name__)

        raw_chunks = []
        async for text_chunk in parser.parse(tmp_path):
            raw_chunks.append(text_chunk)

        logger.info("ingestion.parsed", job_id=job_id, raw_chunks=len(raw_chunks))

        if not raw_chunks:
            logger.warning("ingestion.no_content", job_id=job_id)
            persistence.update_job_status(job_id, IngestionJobStatus.COMPLETED)
            await _publish_job_event(redis, job_id, "COMPLETED", {
                "chunks_total": 0,
                "message": "Keine extrahierbaren Textinhalte gefunden.",
            })
            return {"status": "completed", "chunks": 0}

        # ── Step 4: Semantic Chunking ─────────────────────────────────────────
        chunker = SemanticChunker()
        semantic_chunks = list(chunker.chunk_text_chunks(raw_chunks))

        chunks_total = len(semantic_chunks)
        persistence.update_job_progress(job_id, chunks_total=chunks_total, chunks_processed=0)

        await _publish_job_event(redis, job_id, "CHUNKING_COMPLETE", {
            "chunks_total": chunks_total,
            "progress": 0.0,
        })

        logger.info("ingestion.chunked", job_id=job_id, chunks=chunks_total)

        # ── Step 5: Tenant-Plan laden ─────────────────────────────────────────
        db = SessionLocal()
        plan_slug = "starter"  # default
        try:
            sub = db.query(Subscription).filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
            ).first()
            if sub and sub.plan:
                plan_slug = sub.plan.slug
        except Exception:
            pass
        finally:
            db.close()

        # ── Step 6: Batched Embedding ─────────────────────────────────────────
        async with get_embedding_service() as emb_svc:
            embedded_chunks = await emb_svc.embed_chunks(
                chunks=semantic_chunks,
                tenant_id=tenant_id,
                plan_slug=plan_slug,
                job_id=job_id,
            )

        chunks_embedded = len(embedded_chunks)
        await _publish_job_event(redis, job_id, "EMBEDDING_COMPLETE", {
            "chunks_embedded": chunks_embedded,
            "progress": 0.8,
        })

        # ── Step 7: ChromaDB Upsert (idempotent) ─────────────────────────────
        collection_name = f"ariia_knowledge_{tenant_slug}"

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for ec in embedded_chunks:
            # Idempotency-Key: sha256 des Inhalts
            chunk_id = hashlib.sha256(
                f"{tenant_id}:{s3_key}:{ec.char_offset}:{ec.chunk_index}".encode()
            ).hexdigest()[:32]

            ids.append(chunk_id)
            embeddings.append(ec.embedding)
            documents.append(ec.text)
            metadatas.append({
                "source_s3_key": s3_key,
                "job_id": job_id,
                "tenant_id": str(tenant_id),
                "page_num": str(ec.page_num) if ec.page_num else "",
                "section": ec.section or "",
                "chunk_index": str(ec.chunk_index),
                "token_count": str(ec.token_count),
                "model": ec.model_used,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                **{k: str(v) for k, v in ec.source_metadata.items()},
            })

        # ChromaDB-Zugriff (sync in executor)
        import chromadb
        chroma_host = os.getenv("CHROMADB_HOST", "localhost")
        chroma_port = int(os.getenv("CHROMADB_PORT", "8001"))

        def _chroma_upsert():
            client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"tenant_id": str(tenant_id)},
            )
            # Batch-Upsert in 500er-Blöcken
            batch_size = 500
            for i in range(0, len(ids), batch_size):
                collection.upsert(
                    ids=ids[i:i + batch_size],
                    embeddings=embeddings[i:i + batch_size],
                    documents=documents[i:i + batch_size],
                    metadatas=metadatas[i:i + batch_size],
                )

        await asyncio.get_event_loop().run_in_executor(None, _chroma_upsert)

        logger.info(
            "ingestion.chroma_upserted",
            job_id=job_id,
            tenant_id=tenant_id,
            collection=collection_name,
            vectors=len(ids),
        )

        # ── Step 8: Cleanup ───────────────────────────────────────────────────
        # MinIO: raw → processed
        try:
            await storage.move_to_processed(s3_key)
        except Exception as e:
            logger.warning("ingestion.move_failed", job_id=job_id, error=str(e))

        # Job abschliessen
        persistence.update_job_status(job_id, IngestionJobStatus.COMPLETED)
        persistence.update_job_progress(job_id, chunks_total=chunks_total, chunks_processed=chunks_embedded)

        await _publish_job_event(redis, job_id, "COMPLETED", {
            "chunks_total": chunks_total,
            "chunks_processed": chunks_embedded,
            "progress": 1.0,
            "collection": collection_name,
        })

        logger.info(
            "ingestion.job.completed",
            job_id=job_id,
            tenant_id=tenant_id,
            chunks=chunks_embedded,
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "chunks": chunks_embedded,
            "collection": collection_name,
        }

    except Exception as exc:
        # ── Error Handling ────────────────────────────────────────────────────
        from app.core.models import IngestionJobStatus as _IJS
        from app.worker.retry import (
            categorize_error,
            should_retry,
            get_backoff_seconds,
        )

        category = categorize_error(exc)

        # attempt_count aus arq ctx
        attempt = ctx.get("job_try", 1)

        logger.error(
            "ingestion.job.failed",
            job_id=job_id,
            tenant_id=tenant_id,
            error=str(exc),
            category=category,
            attempt=attempt,
            exc_info=True,
        )

        if not should_retry(category, attempt):
            # → Dead Letter Queue
            persistence.update_job_status(
                job_id,
                _IJS.DEAD_LETTER,
                error_message=str(exc)[:2000],
                error_category=category.value,
            )
            await _publish_job_event(redis, job_id, "DEAD_LETTER", {
                "error": str(exc)[:500],
                "category": category.value,
                "message": "Job endgültig fehlgeschlagen. Manuelle Prüfung erforderlich.",
            })
            # DLQ: nicht re-raisen verhindert arq-Retry
            return {"status": "dead_letter", "error": str(exc)[:500]}
        else:
            # → Retry
            backoff = get_backoff_seconds(attempt, category)
            persistence.update_job_status(
                job_id,
                _IJS.FAILED,
                error_message=str(exc)[:2000],
                error_category=category.value,
            )
            await _publish_job_event(redis, job_id, "FAILED_RETRY", {
                "error": str(exc)[:500],
                "attempt": attempt,
                "retry_in_seconds": backoff,
            })
            if backoff > 0:
                await asyncio.sleep(backoff)
            raise  # arq handled den Retry

    finally:
        # TempFile immer löschen
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
                logger.debug("ingestion.tempfile_deleted", job_id=job_id)
            except Exception:
                pass


# ── arq WorkerSettings for this module ────────────────────────────────────────

class WorkerSettings:
    """arq WorkerSettings — includes both legacy and Sprint 2/3 pipeline tasks."""

    @staticmethod
    def _get_redis_settings():
        try:
            from app.worker.settings import get_worker_redis_settings
            return get_worker_redis_settings()
        except Exception:
            from arq.connections import RedisSettings
            return RedisSettings()

    redis_settings = property(lambda self: WorkerSettings._get_redis_settings())
    functions = [process_ingestion_job]
    max_jobs = 20
    job_timeout = 600
    keep_result = 3600
    retry_jobs = True
    max_tries = 3


# ── Legacy File Ingestion ──────────────────────────────────────────────────────

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
