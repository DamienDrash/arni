"""Memory Platform API Router – unified REST API for all knowledge & memory operations.

This router provides the new API endpoints for the refactored Memory Platform,
replacing the legacy endpoints in admin.py. It maintains backward compatibility
while adding new capabilities:

    - Multi-format file upload (PDF, DOCX, XLSX, CSV, PPTX, HTML, etc.)
    - Unified hybrid search (vector + graph + keyword)
    - Notion connector management (OAuth, sync, webhooks)
    - Member memory with structured facts
    - Consent management (GDPR)
    - Document management with status tracking
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Body
from pydantic import BaseModel

logger = structlog.get_logger()

router = APIRouter(prefix="/memory-platform", tags=["Memory Platform"])


# ── Request/Response Models ──────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    search_type: str = "hybrid"  # hybrid, vector, graph, keyword
    member_id: str | None = None
    include_facts: bool = True
    include_knowledge: bool = True
    filters: dict[str, Any] | None = None


class IngestTextRequest(BaseModel):
    content: str
    title: str = ""
    reason: str | None = None


class NotionOAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class NotionSyncRequest(BaseModel):
    page_ids: list[str] | None = None
    incremental: bool = False


class ConsentRequest(BaseModel):
    member_id: str
    consent_type: str  # memory_storage, profiling, marketing
    action: str = "grant"  # grant, withdraw


class FactRequest(BaseModel):
    member_id: str
    fact_type: str = "attribute"
    subject: str
    predicate: str
    value: str
    confidence: float = 0.8


class CampaignSegmentRequest(BaseModel):
    fact_type: str | None = None
    predicate: str | None = None
    value: str | None = None


# ── Auth Dependency (reuse existing) ────────────────────────────────

def _get_auth():
    """Import auth dependency from existing gateway."""
    try:
        from app.gateway.auth import get_current_user
        return get_current_user
    except ImportError:
        # Fallback for testing
        async def mock_auth():
            class MockUser:
                tenant_id = 1
                role = "system_admin"
                user_id = "test"
            return MockUser()
        return mock_auth


# ── Knowledge Base Endpoints ─────────────────────────────────────────

@router.post("/knowledge/upload")
async def upload_knowledge_file(
    file: UploadFile = File(...),
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Upload a file to the knowledge base (supports PDF, DOCX, XLSX, CSV, PPTX, HTML, MD, TXT, JSON)."""
    from app.memory_platform.ingestion import get_ingestion_service

    service = get_ingestion_service()

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "")[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        doc = await service.ingest_file(
            tenant_id=user.tenant_id,
            file_path=tmp_path,
            original_filename=file.filename or "unknown",
            content_type=file.content_type or "",
        )

        return {
            "status": doc.status,
            "document_id": doc.document_id,
            "filename": doc.original_filename,
            "file_size": doc.file_size,
            "chunk_count": doc.chunk_count,
            "error": doc.error_message,
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/knowledge/text")
async def ingest_knowledge_text(
    body: IngestTextRequest,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Ingest text/markdown content into the knowledge base (legacy compatibility)."""
    from app.memory_platform.ingestion import get_ingestion_service

    service = get_ingestion_service()
    doc = await service.ingest_text(
        tenant_id=user.tenant_id,
        content=body.content,
        title=body.title,
    )

    return {
        "status": doc.status,
        "document_id": doc.document_id,
        "chunk_count": doc.chunk_count,
        "error": doc.error_message,
    }


@router.get("/knowledge/documents")
async def list_documents(
    status: str | None = Query(None),
    source_type: str | None = Query(None),
    user=Depends(_get_auth()),
) -> list[dict[str, Any]]:
    """List all documents in the knowledge base."""
    from app.memory_platform.ingestion import get_ingestion_service
    from app.memory_platform.models import DocumentSourceType

    service = get_ingestion_service()
    source = None
    if source_type:
        try:
            source = DocumentSourceType(source_type)
        except ValueError:
            pass

    docs = service.list_documents(
        tenant_id=user.tenant_id,
        source_type=source,
        status=status,
    )

    return [{
        "document_id": d.document_id,
        "filename": d.original_filename,
        "source_type": d.source_type.value if hasattr(d.source_type, 'value') else str(d.source_type),
        "content_type": d.content_type,
        "file_size": d.file_size,
        "chunk_count": d.chunk_count,
        "status": d.status,
        "created_at": d.created_at,
        "error": d.error_message,
    } for d in docs]


@router.delete("/knowledge/documents/{document_id}")
async def delete_document(
    document_id: str,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Delete a document from the knowledge base."""
    from app.memory_platform.ingestion import get_ingestion_service

    service = get_ingestion_service()
    success = await service.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    return {"status": "deleted", "document_id": document_id}


@router.get("/knowledge/supported-formats")
async def get_supported_formats(
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Get the list of supported file formats."""
    from app.memory_platform.ingestion import get_ingestion_service

    service = get_ingestion_service()
    return {
        "extensions": service.supported_extensions,
        "max_file_size_mb": 50,
    }


# ── Search Endpoints ─────────────────────────────────────────────────

@router.post("/search")
async def search(
    body: SearchRequest,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Unified hybrid search across knowledge base and member memory."""
    from app.memory_platform.retrieval import get_retrieval_service
    from app.memory_platform.models import SearchQuery

    service = get_retrieval_service()
    await service.initialise()

    query = SearchQuery(
        query=body.query,
        tenant_id=user.tenant_id,
        member_id=body.member_id,
        top_k=body.top_k,
        search_type=body.search_type,
        include_facts=body.include_facts,
        include_knowledge=body.include_knowledge,
        filters=body.filters,
    )

    response = await service.search(query)

    return {
        "query": response.query,
        "total_results": response.total_results,
        "search_time_ms": response.search_time_ms,
        "results": [{
            "content": r.content,
            "score": r.score,
            "result_type": r.result_type,
            "source": r.source,
            "metadata": r.metadata,
        } for r in response.results],
        "facts": [{
            "fact_type": f.fact_type.value,
            "subject": f.subject,
            "predicate": f.predicate,
            "value": f.value,
            "confidence": f.confidence,
        } for f in response.facts],
        "context_summary": response.context_summary,
    }


@router.get("/search/member/{member_id}")
async def get_member_context(
    member_id: str,
    query: str = "",
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Get the full knowledge context for a specific member."""
    from app.memory_platform.retrieval import get_retrieval_service

    service = get_retrieval_service()
    await service.initialise()

    response = await service.get_member_context(
        tenant_id=user.tenant_id,
        member_id=member_id,
        query=query,
    )

    return {
        "member_id": member_id,
        "total_results": response.total_results,
        "context_summary": response.context_summary,
        "facts": [{
            "fact_type": f.fact_type.value,
            "subject": f.subject,
            "predicate": f.predicate,
            "value": f.value,
            "confidence": f.confidence,
        } for f in response.facts],
    }


# ── Notion Connector Endpoints ───────────────────────────────────────

@router.get("/notion/oauth-url")
async def get_notion_oauth_url(
    redirect_uri: str = Query(...),
    user=Depends(_get_auth()),
) -> dict[str, str]:
    """Get the Notion OAuth authorization URL."""
    from app.memory_platform.connectors.notion import get_notion_connector

    connector = get_notion_connector()
    url = connector.get_oauth_url(redirect_uri)
    return {"oauth_url": url}


@router.post("/notion/oauth-callback")
async def notion_oauth_callback(
    body: NotionOAuthRequest,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Exchange the Notion OAuth code for an access token."""
    from app.memory_platform.connectors.notion import get_notion_connector

    connector = get_notion_connector()
    result = await connector.exchange_code(body.code, body.redirect_uri)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "status": "connected",
        "workspace_name": result.get("workspace_name"),
        "workspace_id": result.get("workspace_id"),
    }


@router.get("/notion/pages")
async def list_notion_pages(
    query: str = "",
    user=Depends(_get_auth()),
) -> list[dict[str, Any]]:
    """List available pages in the connected Notion workspace."""
    from app.memory_platform.connectors.notion import get_notion_connector

    connector = get_notion_connector()
    if not connector.is_connected:
        raise HTTPException(status_code=400, detail="Notion nicht verbunden")

    return await connector.list_pages(query=query)


@router.post("/notion/sync")
async def sync_notion(
    body: NotionSyncRequest,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Sync content from Notion to the knowledge base."""
    from app.memory_platform.connectors.notion import get_notion_connector

    connector = get_notion_connector()
    if not connector.is_connected:
        raise HTTPException(status_code=400, detail="Notion nicht verbunden")

    if body.incremental:
        return await connector.incremental_sync(user.tenant_id)
    else:
        return await connector.sync(user.tenant_id, page_ids=body.page_ids)


@router.post("/notion/webhook")
async def notion_webhook(
    payload: dict[str, Any] = Body(...),
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Handle incoming Notion webhook events."""
    from app.memory_platform.connectors.notion import get_notion_connector

    connector = get_notion_connector()
    return await connector.handle_webhook(user.tenant_id, payload)


@router.get("/notion/status")
async def get_notion_status(
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Get the current Notion connection status."""
    from app.memory_platform.connectors.notion import get_notion_connector

    connector = get_notion_connector()
    return connector.get_status()


# ── Consent Management Endpoints ─────────────────────────────────────

@router.post("/consent")
async def manage_consent(
    body: ConsentRequest,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Grant or withdraw consent for a member."""
    from app.memory_platform.consent import get_consent_service

    service = get_consent_service()

    if body.action == "grant":
        record = await service.grant_consent(
            tenant_id=user.tenant_id,
            member_id=body.member_id,
            consent_type=body.consent_type,
        )
    elif body.action == "withdraw":
        record = await service.withdraw_consent(
            tenant_id=user.tenant_id,
            member_id=body.member_id,
            consent_type=body.consent_type,
        )
    else:
        raise HTTPException(status_code=400, detail="Ungültige Aktion. Erlaubt: grant, withdraw")

    if not record:
        raise HTTPException(status_code=404, detail="Consent-Eintrag nicht gefunden")

    return {
        "consent_id": record.consent_id,
        "member_id": record.member_id,
        "consent_type": record.consent_type,
        "status": record.status.value,
    }


@router.get("/consent/{member_id}")
async def get_member_consents(
    member_id: str,
    user=Depends(_get_auth()),
) -> list[dict[str, Any]]:
    """Get all consent records for a member."""
    from app.memory_platform.consent import get_consent_service

    service = get_consent_service()
    records = await service.get_all_consents(user.tenant_id, member_id)

    return [{
        "consent_id": r.consent_id,
        "consent_type": r.consent_type,
        "status": r.status.value,
        "granted_at": r.granted_at.isoformat() if r.granted_at else None,
        "withdrawn_at": r.withdrawn_at.isoformat() if r.withdrawn_at else None,
    } for r in records]


@router.get("/consent/audit")
async def get_consent_audit(
    member_id: str | None = Query(None),
    limit: int = Query(100),
    user=Depends(_get_auth()),
) -> list[dict[str, Any]]:
    """Get consent audit log."""
    from app.memory_platform.consent import get_consent_service

    service = get_consent_service()
    return await service.get_audit_log(user.tenant_id, member_id, limit)


# ── Facts Management Endpoints ───────────────────────────────────────

@router.post("/facts")
async def add_fact(
    body: FactRequest,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Manually add a fact to the member's knowledge graph."""
    from app.memory_platform.writer import get_writer_service
    from app.memory_platform.models import ExtractedFact, FactType

    service = get_writer_service()
    await service.initialise()

    try:
        fact_type = FactType(body.fact_type)
    except ValueError:
        fact_type = FactType.ATTRIBUTE

    fact = ExtractedFact(
        fact_type=fact_type,
        subject=body.subject,
        predicate=body.predicate,
        value=body.value,
        confidence=body.confidence,
        member_id=body.member_id,
    )

    success = await service.write_fact(user.tenant_id, fact)
    if not success:
        raise HTTPException(status_code=500, detail="Fehler beim Speichern des Fakts")

    return {
        "status": "created",
        "fact_id": fact.fact_id,
        "fact_type": fact.fact_type.value,
    }


@router.get("/facts/{member_id}")
async def get_member_facts(
    member_id: str,
    fact_type: str | None = Query(None),
    user=Depends(_get_auth()),
) -> list[dict[str, Any]]:
    """Get all facts for a specific member."""
    from app.memory_platform.retrieval import get_retrieval_service
    from app.memory_platform.models import SearchQuery

    service = get_retrieval_service()
    await service.initialise()

    response = await service.get_member_context(
        tenant_id=user.tenant_id,
        member_id=member_id,
    )

    facts = response.facts
    if fact_type:
        facts = [f for f in facts if f.fact_type.value == fact_type]

    return [{
        "fact_id": f.fact_id,
        "fact_type": f.fact_type.value,
        "subject": f.subject,
        "predicate": f.predicate,
        "value": f.value,
        "confidence": f.confidence,
    } for f in facts]


# ── Campaign Integration Endpoints ───────────────────────────────────

@router.post("/campaigns/segments")
async def get_campaign_segments(
    body: CampaignSegmentRequest,
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Get member segments based on knowledge graph criteria for campaign targeting."""
    from app.memory_platform.retrieval import get_retrieval_service

    service = get_retrieval_service()
    await service.initialise()

    segments = await service.get_campaign_segments(
        tenant_id=user.tenant_id,
        criteria={
            "fact_type": body.fact_type,
            "predicate": body.predicate,
            "value": body.value,
        },
    )

    return {
        "total_members": len(segments),
        "segments": segments,
    }


# ── Platform Status ──────────────────────────────────────────────────

@router.get("/status")
async def get_platform_status(
    user=Depends(_get_auth()),
) -> dict[str, Any]:
    """Get the overall Memory Platform status."""
    from app.memory_platform.ingestion import get_ingestion_service
    from app.memory_platform.connectors.notion import get_notion_connector

    ingestion = get_ingestion_service()
    notion = get_notion_connector()

    docs = ingestion.list_documents(user.tenant_id)
    doc_stats = {
        "total": len(docs),
        "indexed": len([d for d in docs if d.status == "indexed"]),
        "processing": len([d for d in docs if d.status == "processing"]),
        "error": len([d for d in docs if d.status == "error"]),
    }

    return {
        "documents": doc_stats,
        "supported_formats": ingestion.supported_extensions,
        "notion": notion.get_status(),
    }
