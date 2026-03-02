"""Shared data models for the Memory Platform.

These models define the canonical data structures that flow through the
event-driven pipeline – from ingestion to extraction to storage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────

class MemoryType(str, Enum):
    """The four pillars of intelligent memory."""
    WORKING = "working"
    PROCEDURAL = "procedural"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"


class FactType(str, Enum):
    """Classification of extracted facts."""
    PREFERENCE = "preference"
    ATTRIBUTE = "attribute"
    RELATIONSHIP = "relationship"
    EVENT = "event"
    OPINION = "opinion"
    GOAL = "goal"
    BEHAVIOUR = "behaviour"
    HEALTH = "health"
    CONTRACT = "contract"
    DEMOGRAPHIC = "demographic"


class DocumentSourceType(str, Enum):
    """Origin of a knowledge document."""
    FILE_UPLOAD = "file_upload"
    MANUAL_EDITOR = "manual_editor"
    NOTION_SYNC = "notion_sync"
    API_INGEST = "api_ingest"
    CONVERSATION = "conversation"
    MAGICLINE = "magicline"


class ConsentStatus(str, Enum):
    """GDPR consent status."""
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    NOT_REQUESTED = "not_requested"


class SyncStatus(str, Enum):
    """Status of an external connector sync."""
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR = "error"
    PAUSED = "paused"


# ── Core Events ──────────────────────────────────────────────────────

class MemoryEvent(BaseModel):
    """Base event flowing through the event bus."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    tenant_id: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionEvent(MemoryEvent):
    """Event published when raw content enters the pipeline."""
    event_type: str = "ingestion.raw"
    source_type: DocumentSourceType
    source_id: str = ""
    filename: str = ""
    content_type: str = ""
    chunks: list[ContentChunk] = Field(default_factory=list)


class ContentChunk(BaseModel):
    """A single chunk of parsed content."""
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    content_type: str = "text"  # text, table, image_description
    metadata: dict[str, Any] = Field(default_factory=dict)
    page_number: int | None = None
    section_title: str | None = None
    char_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        if not self.char_count:
            self.char_count = len(self.content)


class ExtractionResult(MemoryEvent):
    """Event published after entity/fact extraction."""
    event_type: str = "memory.extracted"
    source_event_id: str = ""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class ExtractedEntity(BaseModel):
    """An entity extracted from content."""
    entity_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    entity_type: str  # person, product, topic, organisation, location
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


class ExtractedFact(BaseModel):
    """A single atomic fact extracted from content."""
    fact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fact_type: FactType
    subject: str
    predicate: str
    value: str
    confidence: float = 0.0
    source_chunk_id: str = ""
    member_id: str | None = None


class ExtractedRelationship(BaseModel):
    """A relationship between two entities."""
    source_entity: str
    target_entity: str
    relationship_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


class EnrichmentResult(MemoryEvent):
    """Event published after data enrichment."""
    event_type: str = "memory.enriched"
    source_event_id: str = ""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    enrichment_sources: list[str] = Field(default_factory=list)


# ── Knowledge Document Model ────────────────────────────────────────

class KnowledgeDocument(BaseModel):
    """Represents a knowledge document in the system."""
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: int
    filename: str
    original_filename: str = ""
    source_type: DocumentSourceType
    content_type: str = ""
    file_size: int = 0
    chunk_count: int = 0
    status: str = "pending"  # pending, processing, indexed, error
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    notion_page_id: str | None = None
    notion_last_edited: datetime | None = None


# ── Notion Models ────────────────────────────────────────────────────

class NotionConnection(BaseModel):
    """Represents a Notion workspace connection."""
    connection_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: int
    workspace_id: str = ""
    workspace_name: str = ""
    access_token: str = ""
    bot_id: str = ""
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: SyncStatus = SyncStatus.IDLE
    last_sync_at: datetime | None = None
    synced_databases: list[NotionDatabaseConfig] = Field(default_factory=list)


class NotionDatabaseConfig(BaseModel):
    """Configuration for a synced Notion database."""
    database_id: str
    database_name: str = ""
    enabled: bool = True
    last_sync_at: datetime | None = None
    page_count: int = 0
    sync_status: SyncStatus = SyncStatus.IDLE
    error_message: str | None = None


# ── Retrieval Models ─────────────────────────────────────────────────

class SearchQuery(BaseModel):
    """A search query for the retrieval service."""
    query: str
    tenant_id: int
    member_id: str | None = None
    top_k: int = 10
    search_type: str = "hybrid"  # hybrid, vector, graph, keyword
    filters: dict[str, Any] = Field(default_factory=dict)
    include_facts: bool = True
    include_knowledge: bool = True
    include_episodic: bool = True


class SearchResult(BaseModel):
    """A single search result from the retrieval service."""
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    score: float = 0.0
    result_type: str = "knowledge"  # knowledge, fact, episodic, entity
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResponse(BaseModel):
    """Complete response from the retrieval service."""
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
    context_summary: str = ""
    total_results: int = 0
    search_time_ms: float = 0.0


# ── Consent Models ───────────────────────────────────────────────────

class ConsentRecord(BaseModel):
    """A GDPR consent record."""
    consent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: int
    member_id: str
    consent_type: str  # memory_storage, profiling, marketing
    status: ConsentStatus = ConsentStatus.NOT_REQUESTED
    granted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None


# Fix forward reference
IngestionEvent.model_rebuild()
