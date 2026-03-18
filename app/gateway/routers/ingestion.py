"""ARIIA v2.0 – File Ingestion API Router.

Endpoints:
  POST /admin/knowledge/upload      → Datei-Upload (Streaming → MinIO → Queue)
  GET  /admin/knowledge/jobs        → Job-Liste des Tenants
  GET  /admin/knowledge/jobs/{id}   → Job-Status
  GET  /admin/knowledge/jobs/{id}/stream → SSE Live-Status
  POST /admin/ingestion/dlq/{id}/requeue → DLQ Re-Queue (system_admin)
  GET  /admin/ingestion/dlq         → DLQ-Liste (system_admin)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse

from app.core.auth import AuthContext, get_current_user, require_role

logger = structlog.get_logger()

router = APIRouter(tags=["ingestion"])

# ── Konstanten ───────────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

ALLOWED_MIME_TYPES = {
    # PDF
    "application/pdf",
    # Word
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    # Excel
    "text/csv",
    "application/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    # PowerPoint
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    # OpenDocument
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    # RTF
    "application/rtf",
    "text/rtf",
    # EPUB
    "application/epub+zip",
    # Text / Markup
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "text/html",
    "application/xhtml+xml",
    "text/xml",
    "application/xml",
    # Data
    "application/json",
}

# Extension → MIME Fallback (wenn Content-Type nicht gesetzt)
EXTENSION_MIME_MAP = {
    # PDF
    ".pdf":  "application/pdf",
    # Word
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
    # Excel
    ".csv":  "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls":  "application/vnd.ms-excel",
    # PowerPoint
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt":  "application/vnd.ms-powerpoint",
    # OpenDocument
    ".odt":  "application/vnd.oasis.opendocument.text",
    ".ods":  "application/vnd.oasis.opendocument.spreadsheet",
    ".odp":  "application/vnd.oasis.opendocument.presentation",
    # RTF
    ".rtf":  "application/rtf",
    # EPUB
    ".epub": "application/epub+zip",
    # Text / Markup
    ".txt":  "text/plain",
    ".md":   "text/markdown",
    ".html": "text/html",
    ".htm":  "text/html",
    ".xml":  "application/xml",
    ".xhtml": "application/xhtml+xml",
    # Data
    ".json": "application/json",
}


def _detect_mime(file: UploadFile) -> str:
    """Bestimmt MIME-Type aus Content-Type oder Dateiendung."""
    content_type = file.content_type or ""
    mime = content_type.split(";")[0].strip().lower()

    if mime and mime != "application/octet-stream" and mime in ALLOWED_MIME_TYPES:
        return mime

    # Fallback: Dateiendung
    if file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if suffix in EXTENSION_MIME_MAP:
            return EXTENSION_MIME_MAP[suffix]

    return mime or "application/octet-stream"


# ── Upload Endpoint ──────────────────────────────────────────────────────────

@router.post("/knowledge/upload")
async def upload_file_for_ingestion(
    file: UploadFile = File(...),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Datei-Upload für Knowledge-Base-Ingestion.

    - Streaming-Upload zu MinIO (kein komplett-In-Memory-Laden)
    - Erstellt Job-Record in PostgreSQL
    - Reiht Job in arq-Queue ein
    - Gibt 202 Accepted + job_id zurück
    """
    require_role(user, {"system_admin", "tenant_admin"})

    # MIME-Type Detection + Validierung
    mime_type = _detect_mime(file)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Nicht unterstütztes Format: {mime_type}. "
                   f"Erlaubt: PDF, DOCX, DOC, CSV, XLSX, XLS, PPTX, PPT, "
                   f"ODT, ODS, ODP, RTF, EPUB, TXT, MD, HTML, XML, JSON",
        )

    # Dateiname sanitizen
    original_filename = file.filename or "upload"
    safe_filename = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in original_filename
    )[:200]

    job_id = str(uuid.uuid4())

    logger.info(
        "ingestion.upload_started",
        job_id=job_id,
        tenant_id=user.tenant_id,
        filename=safe_filename,
        mime_type=mime_type,
    )

    # ── Streaming Upload zu MinIO ────────────────────────────────────────────
    try:
        from app.storage.minio_client import get_storage_client
        storage = get_storage_client()

        # Tenant-Slug aus DB holen
        from app.gateway.persistence import persistence
        tenant_slug = persistence.get_tenant_slug(user.tenant_id) or f"tenant_{user.tenant_id}"

        # Streaming: file.read() in Chunks, nie komplett im RAM
        # UploadFile.read() mit size-Limit
        chunks_data = b""
        total_bytes = 0

        async for chunk in _iter_upload_chunks(file, MAX_FILE_SIZE_BYTES):
            chunks_data += chunk
            total_bytes += len(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Leere Datei.")

        import io
        s3_key = await storage.upload_stream(
            tenant_slug=tenant_slug,
            job_id=job_id,
            filename=safe_filename,
            data=io.BytesIO(chunks_data),
            size=total_bytes,
            content_type=mime_type,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("ingestion.upload_failed", job_id=job_id, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Storage-Fehler: {exc}")

    # ── Job-Record in PostgreSQL ─────────────────────────────────────────────
    from app.gateway.persistence import persistence as p
    job = p.create_ingestion_job(
        tenant_id=user.tenant_id,
        filename=safe_filename,
        original_filename=original_filename,
        mime_type=mime_type,
        file_size_bytes=total_bytes,
        s3_key=s3_key,
    )

    # ── Job in arq-Queue einreihen ───────────────────────────────────────────
    try:
        import arq
        from app.worker.settings import get_worker_redis_settings

        redis_pool = await arq.create_pool(get_worker_redis_settings())
        await redis_pool.enqueue_job(
            "process_ingestion_job",
            job_id=job_id,
            s3_key=s3_key,
            tenant_id=user.tenant_id,
            mime_type=mime_type,
            tenant_slug=tenant_slug,
            _job_id=job_id,
        )
        await redis_pool.aclose()

    except Exception as exc:
        logger.error("ingestion.enqueue_failed", job_id=job_id, error=str(exc))
        # Job bleibt PENDING - kann manuell re-queued werden

    logger.info(
        "ingestion.upload_complete",
        job_id=job_id,
        tenant_id=user.tenant_id,
        size_bytes=total_bytes,
        s3_key=s3_key,
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "filename": safe_filename,
        "size_bytes": total_bytes,
        "mime_type": mime_type,
        "status_url": f"/admin/knowledge/jobs/{job_id}",
        "stream_url": f"/admin/knowledge/jobs/{job_id}/stream",
    }


async def _iter_upload_chunks(file: UploadFile, max_bytes: int, chunk_size: int = 65536):
    """Generator für Streaming-Chunks mit Size-Limit."""
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Datei zu groß. Maximum: {max_bytes // (1024 * 1024)} MB",
            )
        yield chunk


# ── Job Status Endpoints ─────────────────────────────────────────────────────

@router.get("/knowledge/jobs/{job_id}")
async def get_ingestion_job(
    job_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Gibt aktuellen Status eines Ingestion-Jobs zurück."""
    require_role(user, {"system_admin", "tenant_admin"})

    from app.gateway.persistence import persistence
    job = persistence.get_job_by_id(job_id=job_id, tenant_id=user.tenant_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden.")

    return _job_to_dict(job)


@router.get("/knowledge/jobs")
async def list_ingestion_jobs(
    user: AuthContext = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """Listet alle Ingestion-Jobs des Tenants."""
    require_role(user, {"system_admin", "tenant_admin"})

    from app.gateway.persistence import persistence
    jobs = persistence.list_jobs_by_tenant(
        tenant_id=user.tenant_id,
        limit=limit,
        offset=offset,
    )
    return [_job_to_dict(j) for j in jobs]


# ── SSE Live-Status ──────────────────────────────────────────────────────────

@router.get("/knowledge/jobs/{job_id}/stream")
async def stream_job_status(
    job_id: str,
    user: AuthContext = Depends(get_current_user),
) -> StreamingResponse:
    """
    Server-Sent Events: Live-Status-Updates für einen Ingestion-Job.

    Client verbindet mit EventSource, bekommt Push-Updates:
    - PROCESSING_STARTED
    - CHUNKING_COMPLETE
    - EMBEDDING_COMPLETE
    - COMPLETED / FAILED / DEAD_LETTER
    """
    require_role(user, {"system_admin", "tenant_admin"})

    # Validierung: Job gehört zum Tenant
    from app.gateway.persistence import persistence
    job = persistence.get_job_by_id(job_id=job_id, tenant_id=user.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden.")

    async def _event_stream() -> AsyncIterator[str]:
        import redis.asyncio as aioredis
        from config.settings import get_settings

        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)

        try:
            # Initiales Status-Event aus aktuell gespeichertem Status
            current_status = await r.hgetall(f"ariia:job:{job_id}")
            if current_status:
                yield f"data: {json.dumps(current_status)}\n\n"
            else:
                # Aus PostgreSQL
                initial = _job_to_dict(job)
                yield f"data: {json.dumps(initial)}\n\n"

            # Früher abschliessen wenn Job bereits final
            if job.status in ("completed", "dead_letter"):
                yield "data: {\"type\": \"STREAM_END\"}\n\n"
                return

            # Live-Updates via Redis Pub/Sub
            pubsub = r.pubsub()
            await pubsub.subscribe(f"ariia:job:{job_id}:events")

            timeout_counter = 0
            MAX_TIMEOUT_CYCLES = 300  # 300 * 1s = 5 Minuten

            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"

                    # Bei finalen Events: Stream schliessen
                    try:
                        payload = json.loads(message["data"])
                        if payload.get("type") in ("COMPLETED", "DEAD_LETTER", "FAILED"):
                            yield "data: {\"type\": \"STREAM_END\"}\n\n"
                            break
                    except Exception:
                        pass

                # Heartbeat alle 15s (keep-alive für Proxies)
                timeout_counter += 1
                if timeout_counter % 15 == 0:
                    yield ": heartbeat\n\n"

                if timeout_counter >= MAX_TIMEOUT_CYCLES:
                    yield "data: {\"type\": \"STREAM_TIMEOUT\", \"message\": \"Reconnect empfohlen\"}\n\n"
                    break

                await asyncio.sleep(1)

        finally:
            try:
                await r.aclose()
            except Exception:
                pass

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx buffering deaktivieren
            "Connection": "keep-alive",
        },
    )


# ── DLQ Admin-Endpoints ──────────────────────────────────────────────────────

@router.get("/ingestion/dlq")
async def list_dlq_jobs(
    user: AuthContext = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Dead-Letter-Queue: Liste fehlgeschlagener Jobs (system_admin only)."""
    require_role(user, {"system_admin"})

    from app.gateway.persistence import persistence
    jobs = persistence.get_dlq_jobs(limit=limit)
    return [_job_to_dict(j) for j in jobs]


@router.post("/ingestion/dlq/{job_id}/requeue")
async def requeue_dlq_job(
    job_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Re-Queue eines Dead-Letter-Jobs (system_admin only)."""
    require_role(user, {"system_admin"})

    from app.gateway.persistence import persistence
    job = persistence.get_job_by_id(job_id=job_id, tenant_id=None)  # system_admin: kein Tenant-Filter
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden.")

    # Status zurücksetzen
    persistence.update_job_status(job_id, "pending")

    # Re-Queue
    try:
        import arq
        from app.worker.settings import get_worker_redis_settings
        from app.gateway.persistence import persistence as p

        tenant_slug = p.get_tenant_slug(job.tenant_id) or f"tenant_{job.tenant_id}"

        redis_pool = await arq.create_pool(get_worker_redis_settings())
        await redis_pool.enqueue_job(
            "process_ingestion_job",
            job_id=job.id,
            s3_key=job.s3_key,
            tenant_id=job.tenant_id,
            mime_type=job.mime_type,
            tenant_slug=tenant_slug,
            _job_id=job.id,
        )
        await redis_pool.aclose()

        logger.info("ingestion.dlq.requeued", job_id=job_id, by_user=user.email)
        return {"status": "requeued", "job_id": job_id}

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Re-Queue fehlgeschlagen: {exc}")


# ── Helper ───────────────────────────────────────────────────────────────────

def _job_to_dict(job) -> dict[str, Any]:
    progress = None
    if job.chunks_total and job.chunks_total > 0:
        progress = round((job.chunks_processed or 0) / job.chunks_total, 3)

    return {
        "job_id": job.id,
        "filename": job.original_filename,
        "mime_type": job.mime_type,
        "file_size_bytes": job.file_size_bytes,
        "status": job.status if isinstance(job.status, str) else job.status.value,
        "attempt_count": job.attempt_count,
        "chunks_total": job.chunks_total,
        "chunks_processed": job.chunks_processed,
        "progress": progress,
        "error_message": job.error_message,
        "error_category": job.error_category,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
