# app/orchestration/models.py
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
import sqlalchemy as sa
from app.core.db import Base, TenantScopedMixin

class OrchestratorDefinition(Base, TenantScopedMixin):
    __tablename__ = "orchestrator_definitions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(64), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=False)
    category = Column(String(16), nullable=False)  # SWARM/CAMPAIGN/AUTOMATION/SYNC
    scope = Column(String(16), nullable=False)      # SYSTEM/TENANT
    status = Column(String(16), nullable=False, default="ACTIVE") # ACTIVE | PAUSED | DISABLED
    config_schema = Column(JSON, nullable=True)
    config_current = Column(JSON, nullable=True)
    guardrails = Column(JSON, nullable=True)
    config_version = Column(Integer, nullable=False, default=1)
    created_at = Column(sa.DateTime(timezone=True), nullable=True)
    updated_at = Column(sa.DateTime(timezone=True), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    versions = relationship("OrchestratorVersion", back_populates="orchestrator", cascade="all, delete-orphan")
    tenant_overrides = relationship("OrchestratorTenantOverride", back_populates="orchestrator", cascade="all, delete-orphan")


class OrchestratorVersion(Base):
    __tablename__ = "orchestrator_versions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    orchestrator_id = Column(String(36), ForeignKey("orchestrator_definitions.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    config_snapshot = Column(JSON, nullable=True)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(sa.DateTime(timezone=True), nullable=True)
    rollback_safe = Column(Boolean, nullable=False, default=True)
    change_summary = Column(Text, nullable=True)
    orchestrator = relationship("OrchestratorDefinition", back_populates="versions")


class OrchestratorTenantOverride(Base):
    __tablename__ = "orchestrator_tenant_overrides"
    id = Column(Integer, primary_key=True, autoincrement=True)
    orchestrator_id = Column(String(36), ForeignKey("orchestrator_definitions.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    config_override = Column(JSON, nullable=True)
    created_at = Column(sa.DateTime(timezone=True), nullable=True)
    updated_at = Column(sa.DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("orchestrator_id", "tenant_id", name="uq_orch_tenant"),)
    orchestrator = relationship("OrchestratorDefinition", back_populates="tenant_overrides")
