"""SQLAlchemy ORM models for multi-tenant Notion integration.

These models persist Notion connection credentials, synced page metadata,
and sync history per tenant – replacing the in-memory singleton approach.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)
from app.core.db import Base


class NotionConnectionDB(Base):
    """Stores one Notion workspace connection per tenant."""

    __tablename__ = "notion_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    workspace_id = Column(String(255), nullable=False, default="")
    workspace_name = Column(String(500), nullable=False, default="")
    workspace_icon = Column(String(500), nullable=True)
    access_token_enc = Column(Text, nullable=False, default="")
    bot_id = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="idle")
    connected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(50), nullable=True)
    last_sync_error = Column(Text, nullable=True)
    webhook_active = Column(Boolean, default=False)
    webhook_secret = Column(String(255), nullable=True)
    pages_synced = Column(Integer, default=0)
    databases_synced = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class NotionSyncedPageDB(Base):
    """Tracks individual Notion pages synced for a tenant."""

    __tablename__ = "notion_synced_pages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "notion_page_id", name="uq_tenant_notion_page"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    notion_page_id = Column(String(255), nullable=False)
    title = Column(String(1000), nullable=False, default="")
    page_type = Column(String(50), nullable=False, default="page")
    parent_type = Column(String(100), nullable=True)
    parent_name = Column(String(500), nullable=True)
    url = Column(String(2000), nullable=True)
    sync_enabled = Column(Boolean, default=True)
    sync_status = Column(String(50), default="pending")
    chunk_count = Column(Integer, default=0)
    last_edited_time = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class NotionSyncLogDB(Base):
    """Audit log for Notion sync operations."""

    __tablename__ = "notion_sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    sync_type = Column(String(50), nullable=False, default="full")
    status = Column(String(50), nullable=False, default="running")
    pages_processed = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
