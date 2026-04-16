"""ARIIA v2.0 – Contact Management Data Models.

@ARCH: Contacts Refactoring, Phase 1 – Neues Datenmodell
Defines the normalized, extensible contact data model that replaces
the legacy StudioMember table. Designed for multi-tenant Enterprise CRM
with support for custom fields, activity tracking, tagging, notes,
lifecycle management, and identity resolution.

Design Principles
-----------------
- Generic, domain-agnostic contact model (no fitness-specific fields)
- Normalized structure with separate tables for activities, notes, tags
- Custom fields via EAV pattern (CustomFieldDefinition + CustomFieldValue)
- Strict tenant isolation via tenant_id on every table
- Soft-delete support via deleted_at column
- Full audit trail through ContactActivity
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.db import Base

# Ensure dependent models are registered with SQLAlchemy before defining FK references
import app.domains.identity.models  # noqa: F401 – registers Tenant, UserAccount, etc.
import app.domains.support.models  # noqa: F401 – registers StudioMember and related support tables


# ─── Enums ────────────────────────────────────────────────────────────────────

class LifecycleStage:
    """Contact lifecycle stages (stored as string for flexibility)."""
    SUBSCRIBER = "subscriber"
    LEAD = "lead"
    OPPORTUNITY = "opportunity"
    CUSTOMER = "customer"
    CHURNED = "churned"
    OTHER = "other"

    ALL = [SUBSCRIBER, LEAD, OPPORTUNITY, CUSTOMER, CHURNED, OTHER]


class ActivityType:
    """Types of contact activities for the timeline."""
    CREATED = "created"
    UPDATED = "updated"
    NOTE_ADDED = "note_added"
    TAG_ADDED = "tag_added"
    TAG_REMOVED = "tag_removed"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    CHAT_MESSAGE = "chat_message"
    CALL = "call"
    MEETING = "meeting"
    IMPORT = "import"
    MERGE = "merge"
    LIFECYCLE_CHANGE = "lifecycle_change"
    CAMPAIGN_SENT = "campaign_sent"
    CAMPAIGN_OPENED = "campaign_opened"
    CAMPAIGN_CLICKED = "campaign_clicked"
    CUSTOM = "custom"


class IdentifierType:
    """Types of contact identifiers for identity resolution."""
    EMAIL = "email"
    PHONE = "phone"
    EXTERNAL_ID = "external_id"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class CustomFieldType:
    """Supported custom field types."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    URL = "url"
    EMAIL = "email"


# ─── Contact (Core Entity) ───────────────────────────────────────────────────

class Contact(Base):
    """Core contact entity – the central record for every customer/lead.

    Replaces the legacy StudioMember table with a generic, extensible model.
    All domain-specific data is stored via custom fields or related tables.
    """
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # ── Core Identity ─────────────────────────────────────────────────────
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(320), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    company = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)

    # ── Demographics ──────────────────────────────────────────────────────
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    preferred_language = Column(String(10), nullable=True, default="de")
    avatar_url = Column(String(500), nullable=True)

    # ── Lifecycle & Status ────────────────────────────────────────────────
    lifecycle_stage = Column(String(50), nullable=False, default=LifecycleStage.SUBSCRIBER)
    source = Column(String(100), nullable=False, default="manual")
    source_id = Column(String(255), nullable=True)

    # ── Consent & Compliance ──────────────────────────────────────────────
    consent_email = Column(Boolean, nullable=False, default=False)
    consent_sms = Column(Boolean, nullable=False, default=False)
    consent_phone = Column(Boolean, nullable=False, default=False)
    consent_whatsapp = Column(Boolean, nullable=False, default=False)
    gdpr_accepted_at = Column(DateTime, nullable=True)

    # ── Scoring ───────────────────────────────────────────────────────────
    score = Column(Integer, nullable=False, default=0)

    # ── AI Optimization ──────────────────────────────────────────────────
    preferred_channel = Column(String(20), nullable=True)          # AI-determined preferred channel
    optimal_send_hour_utc = Column(Integer, nullable=True)         # AI-determined optimal send hour (0-23)
    channel_affinity_json = Column(Text, nullable=True)            # JSON: {"email": 0.7, "whatsapp": 0.9, "sms": 0.3}

    # ── External Mapping ──────────────────────────────────────────────────
    external_ids = Column(Text, nullable=True)  # JSON: {"magicline": "123", "hubspot": "456"}

    # ── Legacy Migration ──────────────────────────────────────────────────
    legacy_member_id = Column(Integer, nullable=True, index=True)  # Link to old StudioMember.id

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # ── Relationships ─────────────────────────────────────────────────────
    activities = relationship("ContactActivity", back_populates="contact", lazy="dynamic",
                              cascade="all, delete-orphan")
    notes = relationship("ContactNote", back_populates="contact", lazy="dynamic",
                         cascade="all, delete-orphan")
    identifiers = relationship("ContactIdentifier", back_populates="contact", lazy="selectin",
                               cascade="all, delete-orphan")
    tag_associations = relationship("ContactTagAssociation", back_populates="contact",
                                    lazy="selectin", cascade="all, delete-orphan")
    custom_field_values = relationship("ContactCustomFieldValue", back_populates="contact",
                                       lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_contacts_tenant_email", "tenant_id", "email"),
        Index("ix_contacts_tenant_phone", "tenant_id", "phone"),
        Index("ix_contacts_tenant_lifecycle", "tenant_id", "lifecycle_stage"),
        Index("ix_contacts_tenant_source", "tenant_id", "source"),
        Index("ix_contacts_tenant_deleted", "tenant_id", "deleted_at"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


# ─── Contact Identifier (Identity Resolution) ────────────────────────────────

class ContactIdentifier(Base):
    """Multiple identifiers per contact for identity resolution and dedup.

    Allows storing multiple emails, phone numbers, and external IDs
    per contact, enabling sophisticated duplicate detection and merging.
    """
    __tablename__ = "contact_identifiers"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    identifier_type = Column(String(50), nullable=False)  # email, phone, external_id, whatsapp, telegram
    identifier_value = Column(String(500), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    verified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    contact = relationship("Contact", back_populates="identifiers")

    __table_args__ = (
        Index("ix_ci_tenant_type_value", "tenant_id", "identifier_type", "identifier_value"),
        UniqueConstraint("tenant_id", "identifier_type", "identifier_value",
                         name="uq_contact_identifier"),
    )


# ─── Contact Activity (Timeline / Audit) ─────────────────────────────────────

class ContactActivity(Base):
    """Chronological activity log for the contact timeline.

    Records all interactions and changes related to a contact,
    serving as both an activity timeline and an audit trail.
    """
    __tablename__ = "contact_activities"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    activity_type = Column(String(50), nullable=False)  # See ActivityType
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON: additional structured data

    performed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = system
    performed_by_name = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    contact = relationship("Contact", back_populates="activities")

    __table_args__ = (
        Index("ix_ca_contact_created", "contact_id", "created_at"),
        Index("ix_ca_tenant_type", "tenant_id", "activity_type"),
    )


# ─── Contact Note ─────────────────────────────────────────────────────────────

class ContactNote(Base):
    """Rich-text notes attached to a contact.

    Supports internal notes, call summaries, meeting notes, etc.
    """
    __tablename__ = "contact_notes"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    is_pinned = Column(Boolean, nullable=False, default=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_name = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    contact = relationship("Contact", back_populates="notes")


# ─── Tag System ───────────────────────────────────────────────────────────────

class ContactTag(Base):
    """Tag definition – reusable labels for categorizing contacts.

    Tags are tenant-scoped and can have a color for visual distinction.
    """
    __tablename__ = "contact_tags"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=True, default="#6C5CE7")  # Hex color
    description = Column(String(500), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    contact_associations = relationship("ContactTagAssociation", back_populates="tag",
                                        cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_contact_tag_name"),
    )


class ContactTagAssociation(Base):
    """Many-to-many association between contacts and tags."""
    __tablename__ = "contact_tag_associations"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("contact_tags.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    contact = relationship("Contact", back_populates="tag_associations")
    tag = relationship("ContactTag", back_populates="contact_associations")

    __table_args__ = (
        UniqueConstraint("contact_id", "tag_id", name="uq_contact_tag_assoc"),
    )


# ─── Custom Fields (EAV Pattern) ─────────────────────────────────────────────

class ContactCustomFieldDefinition(Base):
    """Custom field definition – tenant-specific field schema.

    Allows each tenant to extend the contact model with their own fields
    without altering the database schema.
    """
    __tablename__ = "contact_custom_field_definitions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    field_name = Column(String(100), nullable=False)
    field_slug = Column(String(100), nullable=False)
    field_type = Column(String(50), nullable=False)  # See CustomFieldType
    is_required = Column(Boolean, nullable=False, default=False)
    is_visible = Column(Boolean, nullable=False, default=True)
    options_json = Column(Text, nullable=True)  # JSON: for select/multi_select types
    display_order = Column(Integer, nullable=False, default=0)
    description = Column(String(500), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    values = relationship("ContactCustomFieldValue", back_populates="field_definition",
                          cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "field_slug", name="uq_custom_field_slug"),
    )


class ContactCustomFieldValue(Base):
    """Custom field value – stores the actual data for a contact's custom field."""
    __tablename__ = "contact_custom_field_values"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    field_definition_id = Column(Integer, ForeignKey("contact_custom_field_definitions.id", ondelete="CASCADE"),
                                  nullable=False, index=True)

    value = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ─────────────────────────────────────────────────────
    contact = relationship("Contact", back_populates="custom_field_values")
    field_definition = relationship("ContactCustomFieldDefinition", back_populates="values")

    __table_args__ = (
        UniqueConstraint("contact_id", "field_definition_id", name="uq_custom_field_value"),
    )


# ─── Contact Segment ─────────────────────────────────────────────────────────

class ContactSegment(Base):
    """Reusable contact segments for targeting and filtering.

    Replaces the legacy MemberSegment with enhanced filter capabilities.
    """
    __tablename__ = "contact_segments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    filter_json = Column(Text, nullable=True)  # JSON: legacy flat filter rules
    filter_groups_json = Column(Text, nullable=True)  # JSON: Phase 3 rule groups
    group_connector = Column(String(10), nullable=False, default="and")
    is_dynamic = Column(Boolean, nullable=False, default=True)
    contact_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ─── Contact Import Log ──────────────────────────────────────────────────────

class ContactLifecycleConfig(Base):
    """Tenant-specific lifecycle stage configuration."""
    __tablename__ = "contact_lifecycle_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    stages_json = Column(Text, nullable=False)
    default_stage = Column(String(100), nullable=False, default="subscriber")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ContactImportLog(Base):
    """Log of bulk import operations for contacts."""
    __tablename__ = "contact_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    source = Column(String(100), nullable=False)  # csv, api, magicline, shopify, etc.
    status = Column(String(50), nullable=False, default="running")  # running, completed, failed
    filename = Column(String(500), nullable=True)

    total_rows = Column(Integer, nullable=False, default=0)
    imported = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    error_log = Column(Text, nullable=True)  # JSON details

    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
