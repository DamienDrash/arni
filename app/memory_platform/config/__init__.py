"""Memory Platform configuration – centralised settings for all services."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class Neo4jConfig:
    """Neo4j Knowledge Graph connection settings."""

    uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user: str = os.getenv("NEO4J_USER", "neo4j")
    password: str = os.getenv("NEO4J_PASSWORD", "ariia_memory")
    database: str = os.getenv("NEO4J_DATABASE", "neo4j")
    max_connection_pool_size: int = int(os.getenv("NEO4J_POOL_SIZE", "50"))


@dataclass
class QdrantConfig:
    """Qdrant Vector DB connection settings."""

    host: str = os.getenv("QDRANT_HOST", "localhost")
    port: int = int(os.getenv("QDRANT_PORT", "6333"))
    grpc_port: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    api_key: str | None = os.getenv("QDRANT_API_KEY")
    collection_prefix: str = os.getenv("QDRANT_COLLECTION_PREFIX", "ariia_")
    embedding_dim: int = int(os.getenv("QDRANT_EMBEDDING_DIM", "384"))


@dataclass
class RedisConfig:
    """Redis cache connection settings."""

    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    password: str | None = os.getenv("REDIS_PASSWORD")
    db: int = int(os.getenv("REDIS_DB", "2"))
    context_ttl: int = int(os.getenv("REDIS_CONTEXT_TTL", "3600"))


@dataclass
class KafkaConfig:
    """Kafka / internal event bus settings."""

    bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    use_internal_bus: bool = os.getenv("MEMORY_USE_INTERNAL_BUS", "true").lower() == "true"
    topics: dict[str, str] = field(default_factory=lambda: {
        "ingestion_raw": "memory.ingestion.raw",
        "extracted": "memory.extracted",
        "enriched": "memory.enriched",
        "written": "memory.written",
        "session_started": "memory.session.started",
        "knowledge_updated": "memory.knowledge.updated",
    })


@dataclass
class IngestionConfig:
    """Ingestion service settings."""

    max_file_size_mb: int = int(os.getenv("INGESTION_MAX_FILE_SIZE_MB", "50"))
    allowed_extensions: list[str] = field(default_factory=lambda: [
        ".md", ".txt", ".pdf", ".docx", ".doc", ".xlsx", ".xls",
        ".csv", ".tsv", ".pptx", ".ppt", ".html", ".htm",
        ".eml", ".msg", ".rtf", ".epub", ".odt", ".xml", ".json",
    ])
    chunk_size: int = int(os.getenv("INGESTION_CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("INGESTION_CHUNK_OVERLAP", "200"))
    use_unstructured: bool = os.getenv("INGESTION_USE_UNSTRUCTURED", "true").lower() == "true"


@dataclass
class NotionConfig:
    """Notion connector settings."""

    client_id: str = os.getenv("NOTION_CLIENT_ID", "")
    client_secret: str = os.getenv("NOTION_CLIENT_SECRET", "")
    redirect_uri: str = os.getenv("NOTION_REDIRECT_URI", "")
    webhook_secret: str = os.getenv("NOTION_WEBHOOK_SECRET", "")
    sync_interval_minutes: int = int(os.getenv("NOTION_SYNC_INTERVAL", "5"))


@dataclass
class ExtractionConfig:
    """Extraction service settings."""

    model: str = os.getenv("EXTRACTION_MODEL", "gpt-4.1-mini")
    max_tokens: int = int(os.getenv("EXTRACTION_MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("EXTRACTION_TEMPERATURE", "0.1"))


@dataclass
class RetrievalConfig:
    """Retrieval service settings."""

    default_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "10"))
    rerank_top_k: int = int(os.getenv("RETRIEVAL_RERANK_TOP_K", "5"))
    vector_weight: float = float(os.getenv("RETRIEVAL_VECTOR_WEIGHT", "0.6"))
    graph_weight: float = float(os.getenv("RETRIEVAL_GRAPH_WEIGHT", "0.3"))
    keyword_weight: float = float(os.getenv("RETRIEVAL_KEYWORD_WEIGHT", "0.1"))
    enable_reranking: bool = os.getenv("RETRIEVAL_ENABLE_RERANKING", "true").lower() == "true"


@dataclass
class MemoryPlatformConfig:
    """Root configuration for the entire Memory Platform."""

    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    notion: NotionConfig = field(default_factory=NotionConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)


# ── Singleton ────────────────────────────────────────────────────────
_config: MemoryPlatformConfig | None = None


def get_config() -> MemoryPlatformConfig:
    """Return the singleton platform configuration."""
    global _config
    if _config is None:
        _config = MemoryPlatformConfig()
        logger.info("memory_platform.config.loaded")
    return _config
