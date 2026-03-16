"""ARIIA v2.0 – Retry-Strategie und Error-Kategorisierung."""
from __future__ import annotations
import enum
import structlog

logger = structlog.get_logger()


class IngestionErrorCategory(str, enum.Enum):
    # → Sofort DLQ (kein Retry sinnvoll)
    INVALID_FORMAT   = "invalid_format"    # Korrupte/unlesbare Datei
    QUOTA_EXCEEDED   = "quota_exceeded"    # Tenant-Limit erreicht
    CONTENT_POLICY   = "content_policy"    # OpenAI Moderation abgelehnt

    # → Retry mit exponential backoff
    EMBEDDING_TIMEOUT   = "embedding_timeout"
    CHROMA_UNAVAILABLE  = "chroma_unavailable"
    STORAGE_ERROR       = "storage_error"

    # → Sofort 1x retry
    PARSE_PARTIAL    = "parse_partial"


# Maximale Backoff-Zeit: 1 Stunde
MAX_BACKOFF_SECONDS = 3600

# Keine-Retry Kategorien
NO_RETRY_CATEGORIES = {
    IngestionErrorCategory.INVALID_FORMAT,
    IngestionErrorCategory.QUOTA_EXCEEDED,
    IngestionErrorCategory.CONTENT_POLICY,
}

# Sofort-Retry Kategorien (kein Backoff)
IMMEDIATE_RETRY_CATEGORIES = {
    IngestionErrorCategory.PARSE_PARTIAL,
}


def categorize_error(exc: Exception) -> IngestionErrorCategory:
    """Klassifiziert eine Exception in eine IngestionErrorCategory."""
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__

    if "quota" in exc_str or "limit exceeded" in exc_str:
        return IngestionErrorCategory.QUOTA_EXCEEDED

    if "content_policy" in exc_str or "content policy" in exc_str:
        return IngestionErrorCategory.CONTENT_POLICY

    if any(kw in exc_str for kw in ["timeout", "timed out", "time out"]):
        return IngestionErrorCategory.EMBEDDING_TIMEOUT

    if any(kw in exc_str for kw in ["chroma", "vectorstore", "collection"]):
        return IngestionErrorCategory.CHROMA_UNAVAILABLE

    if any(kw in exc_str for kw in ["minio", "s3", "storage", "bucket"]):
        return IngestionErrorCategory.STORAGE_ERROR

    if any(kw in exc_str for kw in ["parse", "extract", "pdf", "docx", "corrupt"]):
        return IngestionErrorCategory.PARSE_PARTIAL

    # Default: als STORAGE_ERROR behandeln (retry)
    return IngestionErrorCategory.STORAGE_ERROR


def should_retry(category: IngestionErrorCategory, attempt_count: int, max_attempts: int = 3) -> bool:
    if category in NO_RETRY_CATEGORIES:
        return False
    if category in IMMEDIATE_RETRY_CATEGORIES:
        return attempt_count < 2  # nur 1 sofortiger Retry
    return attempt_count < max_attempts


def get_backoff_seconds(attempt_count: int, category: IngestionErrorCategory) -> int:
    if category in IMMEDIATE_RETRY_CATEGORIES:
        return 0
    backoff = (2 ** attempt_count) * 30  # 30s, 60s, 120s
    return min(backoff, MAX_BACKOFF_SECONDS)
