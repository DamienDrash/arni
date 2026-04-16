import enum as _enum_module
import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Enum as SQLEnum, Index, Integer, String, Text

from app.core.db import Base, TenantScopedMixin


class IngestionJobStatus(str, _enum_module.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class IngestionJob(Base, TenantScopedMixin):
    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=True)
    s3_key = Column(String(1000), nullable=True)
    status = Column(SQLEnum(IngestionJobStatus), nullable=False, default=IngestionJobStatus.PENDING, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    error_category = Column(String(100), nullable=True)
    chunks_total = Column(Integer, nullable=True)
    chunks_processed = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ingestion_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_ingestion_jobs_tenant_created", "tenant_id", "created_at"),
    )


__all__ = ["IngestionJob", "IngestionJobStatus"]
