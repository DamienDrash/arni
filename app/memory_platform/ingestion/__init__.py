"""Ingestion Service – entry point for all content entering the Memory Platform.

Responsibilities:
    1. Accept content from multiple sources (file upload, API, Notion, conversations)
    2. Validate and store raw files
    3. Parse files into content chunks using the Parser Registry
    4. Publish IngestionEvents to the event bus for downstream processing

This service replaces the legacy ``app/knowledge/ingest.py`` module.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from typing import Any

import structlog

from app.memory_platform.config import get_config
from app.memory_platform.event_bus import get_event_bus
from app.memory_platform.ingestion.parsers import get_parser_registry
from app.memory_platform.models import (
    ContentChunk,
    DocumentSourceType,
    IngestionEvent,
    KnowledgeDocument,
)

logger = structlog.get_logger()

UPLOAD_DIR = os.path.join("data", "knowledge_uploads")
DOCS_INDEX_FILE = os.path.join(UPLOAD_DIR, "documents_index.json")


class IngestionService:
    """Handles all content ingestion into the Memory Platform."""

    def __init__(self) -> None:
        self._parser_registry = get_parser_registry()
        self._event_bus = get_event_bus()
        self._documents: dict[str, KnowledgeDocument] = {}
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        self._load_index()

    # ── Index Persistence ────────────────────────────────────────────

    def _load_index(self) -> None:
        """Load document index from disk, restoring records after restart.

        Also recovers orphaned files that exist in the upload directory but
        have no matching index record (e.g. from pre-persistence uploads).
        """
        if os.path.exists(DOCS_INDEX_FILE):
            try:
                with open(DOCS_INDEX_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    try:
                        doc = KnowledgeDocument.model_validate(item)
                        self._documents[doc.document_id] = doc
                    except Exception:
                        pass
                logger.info("ingestion.index_loaded", count=len(self._documents))
            except Exception as exc:
                logger.warning("ingestion.index_load_failed", error=str(exc))

        # Recover orphaned files: scan all tenant upload dirs
        self._recover_orphaned_files()

    def _recover_orphaned_files(self) -> None:
        """Create minimal index entries for uploaded files with no matching record."""
        if not os.path.exists(UPLOAD_DIR):
            return
        known_filenames = {doc.filename for doc in self._documents.values()}
        recovered = 0
        for entry in os.scandir(UPLOAD_DIR):
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            tenant_id = int(entry.name)
            for file_entry in os.scandir(entry.path):
                if not file_entry.is_file():
                    continue
                if file_entry.name in known_filenames:
                    continue
                # Build a minimal document record for the orphaned file
                ext = os.path.splitext(file_entry.name)[1].lower()
                doc = KnowledgeDocument(
                    tenant_id=tenant_id,
                    filename=file_entry.name,
                    original_filename=file_entry.name,
                    source_type=DocumentSourceType.FILE_UPLOAD,
                    file_size=file_entry.stat().st_size,
                    status="indexed",
                )
                self._documents[doc.document_id] = doc
                recovered += 1
        if recovered:
            logger.info("ingestion.orphaned_files_recovered", count=recovered)
            self._save_index()

    def _save_index(self) -> None:
        """Persist document index to disk."""
        try:
            data = [doc.model_dump(mode="json") for doc in self._documents.values()]
            with open(DOCS_INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str, ensure_ascii=False)
        except Exception as exc:
            logger.warning("ingestion.index_save_failed", error=str(exc))

    # ── File Upload ──────────────────────────────────────────────────

    async def ingest_file(
        self,
        tenant_id: int,
        file_path: str,
        original_filename: str,
        content_type: str = "",
        source_type: DocumentSourceType = DocumentSourceType.FILE_UPLOAD,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        """Ingest a file: validate, parse, and publish to event bus.

        Args:
            tenant_id: The tenant this document belongs to.
            file_path: Path to the uploaded file on disk.
            original_filename: The user-facing filename.
            content_type: MIME type of the file.
            source_type: Origin of the document.
            metadata: Additional metadata to attach.

        Returns:
            A KnowledgeDocument with processing status.
        """
        metadata = metadata or {}
        cfg = get_config().ingestion

        # Validate extension
        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in cfg.allowed_extensions:
            return KnowledgeDocument(
                tenant_id=tenant_id,
                filename=original_filename,
                original_filename=original_filename,
                source_type=source_type,
                status="error",
                error_message=f"Dateityp '{ext}' wird nicht unterstützt. "
                              f"Erlaubte Typen: {', '.join(cfg.allowed_extensions)}",
            )

        # Validate file size
        file_size = os.path.getsize(file_path)
        max_bytes = cfg.max_file_size_mb * 1024 * 1024
        if file_size > max_bytes:
            return KnowledgeDocument(
                tenant_id=tenant_id,
                filename=original_filename,
                original_filename=original_filename,
                source_type=source_type,
                status="error",
                error_message=f"Datei zu groß ({file_size // (1024*1024)} MB). "
                              f"Maximum: {cfg.max_file_size_mb} MB.",
            )

        # Create document record
        doc = KnowledgeDocument(
            tenant_id=tenant_id,
            filename=original_filename,
            original_filename=original_filename,
            source_type=source_type,
            content_type=content_type,
            file_size=file_size,
            status="processing",
            metadata=metadata,
        )

        # Copy file to permanent storage
        tenant_dir = os.path.join(UPLOAD_DIR, str(tenant_id))
        os.makedirs(tenant_dir, exist_ok=True)
        stored_filename = f"{doc.document_id}{ext}"
        stored_path = os.path.join(tenant_dir, stored_filename)
        shutil.copy2(file_path, stored_path)
        doc.filename = stored_filename

        # Parse the file
        try:
            chunks = await self._parser_registry.parse(
                file_path=stored_path,
                filename=original_filename,
                mimetype=content_type,
                metadata={
                    "document_id": doc.document_id,
                    "tenant_id": tenant_id,
                    "source_type": source_type.value,
                    **metadata,
                },
            )

            if not chunks:
                doc.status = "error"
                doc.error_message = "Keine Inhalte aus der Datei extrahiert."
                self._documents[doc.document_id] = doc
                return doc

            doc.chunk_count = len(chunks)
            doc.status = "indexed"

            # Publish ingestion event
            event = IngestionEvent(
                tenant_id=tenant_id,
                source_type=source_type,
                source_id=doc.document_id,
                filename=original_filename,
                content_type=content_type,
                chunks=chunks,
                metadata={
                    "document_id": doc.document_id,
                    **metadata,
                },
            )
            await self._event_bus.publish(event)

            logger.info(
                "ingestion.file_ingested",
                document_id=doc.document_id,
                filename=original_filename,
                chunks=len(chunks),
                tenant_id=tenant_id,
            )

        except Exception as exc:
            doc.status = "error"
            doc.error_message = f"Fehler bei der Verarbeitung: {str(exc)}"
            logger.error(
                "ingestion.file_error",
                document_id=doc.document_id,
                error=str(exc),
            )

        self._documents[doc.document_id] = doc
        self._save_index()
        return doc

    # ── Text / Markdown Ingestion ────────────────────────────────────

    async def ingest_text(
        self,
        tenant_id: int,
        content: str,
        title: str = "",
        source_type: DocumentSourceType = DocumentSourceType.MANUAL_EDITOR,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        """Ingest raw text/markdown content (legacy compatibility)."""
        metadata = metadata or {}

        doc = KnowledgeDocument(
            tenant_id=tenant_id,
            filename=f"{title or 'untitled'}.md",
            original_filename=f"{title or 'untitled'}.md",
            source_type=source_type,
            content_type="text/markdown",
            file_size=len(content.encode("utf-8")),
            status="processing",
            metadata=metadata,
        )

        # Write to temp file and parse
        tenant_dir = os.path.join(UPLOAD_DIR, str(tenant_id))
        os.makedirs(tenant_dir, exist_ok=True)
        temp_path = os.path.join(tenant_dir, f"{doc.document_id}.md")

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)

        try:
            chunks = await self._parser_registry.parse(
                file_path=temp_path,
                filename=doc.filename,
                mimetype="text/markdown",
                metadata={
                    "document_id": doc.document_id,
                    "tenant_id": tenant_id,
                    "title": title,
                    **metadata,
                },
            )

            doc.chunk_count = len(chunks)
            doc.status = "indexed"

            event = IngestionEvent(
                tenant_id=tenant_id,
                source_type=source_type,
                source_id=doc.document_id,
                filename=doc.filename,
                content_type="text/markdown",
                chunks=chunks,
                metadata={"document_id": doc.document_id, "title": title, **metadata},
            )
            await self._event_bus.publish(event)

            logger.info(
                "ingestion.text_ingested",
                document_id=doc.document_id,
                title=title,
                chunks=len(chunks),
            )

        except Exception as exc:
            doc.status = "error"
            doc.error_message = str(exc)
            logger.error("ingestion.text_error", error=str(exc))

        self._documents[doc.document_id] = doc
        self._save_index()
        return doc

    # ── Conversation Ingestion ───────────────────────────────────────

    async def ingest_conversation(
        self,
        tenant_id: int,
        conversation_id: str,
        messages: list[dict[str, str]],
        member_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Ingest a conversation for memory extraction.

        This is the entry point for the Orchestrator to feed conversation
        data into the memory pipeline.
        """
        metadata = metadata or {}
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted.append(f"[{role}]: {content}")

        full_text = "\n".join(formatted)

        chunks = [ContentChunk(
            content=full_text,
            content_type="conversation",
            metadata={
                "conversation_id": conversation_id,
                "member_id": member_id,
                "message_count": len(messages),
                **metadata,
            },
        )]

        event = IngestionEvent(
            tenant_id=tenant_id,
            source_type=DocumentSourceType.CONVERSATION,
            source_id=conversation_id,
            content_type="conversation",
            chunks=chunks,
            metadata={
                "conversation_id": conversation_id,
                "member_id": member_id,
                **metadata,
            },
        )
        await self._event_bus.publish(event)

        logger.info(
            "ingestion.conversation_ingested",
            conversation_id=conversation_id,
            messages=len(messages),
        )

    # ── Document Management ──────────────────────────────────────────

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        """Retrieve a document by ID."""
        return self._documents.get(document_id)

    def list_documents(
        self,
        tenant_id: int,
        source_type: DocumentSourceType | None = None,
        status: str | None = None,
    ) -> list[KnowledgeDocument]:
        """List all documents for a tenant with optional filters."""
        results = []
        for doc in self._documents.values():
            if doc.tenant_id != tenant_id:
                continue
            if source_type and doc.source_type != source_type:
                continue
            if status and doc.status != status:
                continue
            results.append(doc)
        return sorted(results, key=lambda d: d.created_at, reverse=True)

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and its stored file."""
        doc = self._documents.get(document_id)
        if not doc:
            return False

        # Remove stored file
        tenant_dir = os.path.join(UPLOAD_DIR, str(doc.tenant_id))
        stored_path = os.path.join(tenant_dir, doc.filename)
        if os.path.exists(stored_path):
            os.remove(stored_path)

        del self._documents[document_id]
        self._save_index()
        logger.info("ingestion.document_deleted", document_id=document_id)
        return True

    @property
    def supported_extensions(self) -> list[str]:
        """Return all supported file extensions."""
        return self._parser_registry.supported_extensions


# ── Singleton ────────────────────────────────────────────────────────

_service: IngestionService | None = None


def get_ingestion_service() -> IngestionService:
    """Return the singleton ingestion service."""
    global _service
    if _service is None:
        _service = IngestionService()
    return _service
