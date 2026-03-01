"""ARIIA v2.0 – Contact Management Pydantic Schemas.

@ARCH: Contacts Refactoring, Phase 2 – Request/Response Models (Extended)
Defines all Pydantic v2 models for the Contact Management API.
Strict validation, serialization, and documentation support.

Design Principles
-----------------
- Separate Create/Update/Response models (no model reuse for different operations)
- Explicit Optional fields for partial updates
- Consistent naming and documentation
- ISO 8601 date/time formats
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ─── Contact Schemas ──────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    """Schema for creating a new contact."""
    first_name: str = Field(..., min_length=1, max_length=255, description="Vorname")
    last_name: str = Field(..., min_length=1, max_length=255, description="Nachname")
    email: Optional[EmailStr] = Field(None, description="E-Mail-Adresse")
    phone: Optional[str] = Field(None, max_length=50, description="Telefonnummer")
    company: Optional[str] = Field(None, max_length=255, description="Unternehmen")
    job_title: Optional[str] = Field(None, max_length=255, description="Position/Titel")
    date_of_birth: Optional[date] = Field(None, description="Geburtsdatum (YYYY-MM-DD)")
    gender: Optional[str] = Field(None, max_length=20, description="Geschlecht")
    preferred_language: Optional[str] = Field("de", max_length=10, description="Bevorzugte Sprache")
    avatar_url: Optional[str] = Field(None, max_length=500, description="Avatar-URL")
    lifecycle_stage: Optional[str] = Field("subscriber", description="Lifecycle-Phase")
    source: Optional[str] = Field("manual", max_length=100, description="Quelle")
    source_id: Optional[str] = Field(None, max_length=255, description="Externe ID in Quellsystem")
    consent_email: Optional[bool] = Field(False, description="E-Mail-Einwilligung")
    consent_sms: Optional[bool] = Field(False, description="SMS-Einwilligung")
    consent_phone: Optional[bool] = Field(False, description="Telefon-Einwilligung")
    consent_whatsapp: Optional[bool] = Field(False, description="WhatsApp-Einwilligung")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tag-Namen")
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Benutzerdefinierte Felder")
    notes: Optional[str] = Field(None, description="Initiale Notiz")

    @field_validator("lifecycle_stage")
    @classmethod
    def validate_lifecycle(cls, v: str) -> str:
        allowed = ["subscriber", "lead", "opportunity", "customer", "churned", "other"]
        if v and v not in allowed:
            raise ValueError(f"Lifecycle-Phase muss einer der folgenden Werte sein: {', '.join(allowed)}")
        return v


class ContactUpdate(BaseModel):
    """Schema for updating an existing contact (partial update)."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    last_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    preferred_language: Optional[str] = Field(None, max_length=10)
    avatar_url: Optional[str] = Field(None, max_length=500)
    lifecycle_stage: Optional[str] = None
    consent_email: Optional[bool] = None
    consent_sms: Optional[bool] = None
    consent_phone: Optional[bool] = None
    consent_whatsapp: Optional[bool] = None
    score: Optional[int] = None

    @field_validator("lifecycle_stage")
    @classmethod
    def validate_lifecycle(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = ["subscriber", "lead", "opportunity", "customer", "churned", "other"]
        if v not in allowed:
            raise ValueError(f"Lifecycle-Phase muss einer der folgenden Werte sein: {', '.join(allowed)}")
        return v


class ContactResponse(BaseModel):
    """Full contact response with all fields."""
    id: int
    tenant_id: int
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    preferred_language: Optional[str] = None
    avatar_url: Optional[str] = None
    lifecycle_stage: str
    source: str
    source_id: Optional[str] = None
    consent_email: bool = False
    consent_sms: bool = False
    consent_phone: bool = False
    consent_whatsapp: bool = False
    gdpr_accepted_at: Optional[datetime] = None
    score: int = 0
    external_ids: Optional[Dict[str, str]] = None
    tags: List[TagResponse] = []
    custom_fields: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Paginated contact list response."""
    items: List[ContactResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ContactBulkDeleteRequest(BaseModel):
    """Request for bulk deleting contacts."""
    ids: List[int] = Field(..., min_length=1, description="Liste der zu löschenden Kontakt-IDs")
    permanent: bool = Field(False, description="Permanent löschen statt Soft-Delete")


class ContactBulkUpdateRequest(BaseModel):
    """Request for bulk updating contacts."""
    ids: List[int] = Field(..., min_length=1, description="Liste der zu aktualisierenden Kontakt-IDs")
    lifecycle_stage: Optional[str] = Field(None, description="Neue Lifecycle-Phase")
    add_tags: Optional[List[str]] = Field(None, description="Tags hinzufügen")
    remove_tags: Optional[List[str]] = Field(None, description="Tags entfernen")
    source: Optional[str] = Field(None, description="Neue Quelle")
    consent_email: Optional[bool] = Field(None, description="E-Mail-Einwilligung")
    consent_sms: Optional[bool] = Field(None, description="SMS-Einwilligung")
    consent_phone: Optional[bool] = Field(None, description="Telefon-Einwilligung")
    consent_whatsapp: Optional[bool] = Field(None, description="WhatsApp-Einwilligung")

    @field_validator("lifecycle_stage")
    @classmethod
    def validate_lifecycle(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = ["subscriber", "lead", "opportunity", "customer", "churned", "other"]
        if v not in allowed:
            raise ValueError(f"Lifecycle-Phase muss einer der folgenden Werte sein: {', '.join(allowed)}")
        return v


class ContactBulkUpdateResponse(BaseModel):
    """Response for bulk update operations."""
    updated: int = Field(..., description="Anzahl aktualisierter Kontakte")
    tags_added: int = Field(0, description="Anzahl hinzugefügter Tag-Zuordnungen")
    tags_removed: int = Field(0, description="Anzahl entfernter Tag-Zuordnungen")


class ContactMergeRequest(BaseModel):
    """Request for merging two contacts."""
    primary_id: int = Field(..., description="ID des primären Kontakts (wird beibehalten)")
    secondary_id: int = Field(..., description="ID des sekundären Kontakts (wird zusammengeführt)")
    fields_from_secondary: List[str] = Field(
        default_factory=list,
        description="Felder, die vom sekundären Kontakt übernommen werden sollen"
    )


# ─── Duplicate Schemas ───────────────────────────────────────────────────────

class DuplicateContactResponse(BaseModel):
    """A potential duplicate contact with match info."""
    contact: ContactResponse
    match_reason: str = Field(..., description="Grund für den Match (email_exact, phone_exact, name_exact, name_partial)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Konfidenz-Score (0.0 - 1.0)")


class DuplicateCheckResponse(BaseModel):
    """Response for duplicate check."""
    has_duplicates: bool
    duplicates: List[DuplicateContactResponse] = []


class DuplicateGroupResponse(BaseModel):
    """A group of potential duplicate contacts."""
    match_type: str
    match_value: str
    confidence: float
    contacts: List[ContactResponse]


class DuplicateGroupListResponse(BaseModel):
    """Paginated list of duplicate groups."""
    groups: List[DuplicateGroupResponse]
    total_groups: int
    page: int
    page_size: int


# ─── Tag Schemas ──────────────────────────────────────────────────────────────

class TagCreate(BaseModel):
    """Schema for creating a tag."""
    name: str = Field(..., min_length=1, max_length=100, description="Tag-Name")
    color: Optional[str] = Field("#6C5CE7", max_length=7, description="Hex-Farbcode")
    description: Optional[str] = Field(None, max_length=500, description="Beschreibung")


class TagUpdate(BaseModel):
    """Schema for updating a tag."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=7)
    description: Optional[str] = Field(None, max_length=500)


class TagResponse(BaseModel):
    """Tag response."""
    id: int
    name: str
    color: Optional[str] = "#6C5CE7"
    description: Optional[str] = None
    contact_count: int = 0

    class Config:
        from_attributes = True


class TagAssignRequest(BaseModel):
    """Request for assigning/removing a tag to/from a contact."""
    tag_name: str = Field(..., min_length=1, max_length=100, description="Tag-Name")
    color: Optional[str] = Field("#6C5CE7", max_length=7, description="Hex-Farbcode (nur bei Neuanlage)")


# ─── Note Schemas ─────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    """Schema for creating a contact note."""
    content: str = Field(..., min_length=1, description="Notiz-Inhalt")
    is_pinned: bool = Field(False, description="Notiz anpinnen")


class NoteUpdate(BaseModel):
    """Schema for updating a contact note."""
    content: Optional[str] = Field(None, min_length=1)
    is_pinned: Optional[bool] = None


class NoteResponse(BaseModel):
    """Note response."""
    id: int
    contact_id: int
    content: str
    is_pinned: bool = False
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Activity Schemas ─────────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    """Schema for manually creating a contact activity."""
    activity_type: str = Field(..., description="Aktivitätstyp")
    title: str = Field(..., min_length=1, max_length=500, description="Titel")
    description: Optional[str] = Field(None, description="Beschreibung")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Zusätzliche Metadaten")

    @field_validator("activity_type")
    @classmethod
    def validate_activity_type(cls, v: str) -> str:
        allowed = [
            "created", "updated", "note_added", "tag_added", "tag_removed",
            "email_sent", "email_received", "chat_message", "call", "meeting",
            "import", "merge", "lifecycle_change", "campaign_sent",
            "campaign_opened", "campaign_clicked", "custom",
        ]
        if v not in allowed:
            raise ValueError(f"Aktivitätstyp muss einer der folgenden Werte sein: {', '.join(allowed)}")
        return v


class ActivityResponse(BaseModel):
    """Activity timeline entry response."""
    id: int
    contact_id: int
    activity_type: str
    title: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    performed_by: Optional[int] = None
    performed_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    """Paginated activity list."""
    items: List[ActivityResponse]
    total: int
    page: int
    page_size: int


# ─── Custom Field Schemas ─────────────────────────────────────────────────────

class CustomFieldDefinitionCreate(BaseModel):
    """Schema for creating a custom field definition."""
    field_name: str = Field(..., min_length=1, max_length=100, description="Anzeigename")
    field_slug: str = Field(..., min_length=1, max_length=100, description="Technischer Slug")
    field_type: str = Field(..., description="Feldtyp: text, number, date, boolean, select, multi_select, url, email")
    is_required: bool = Field(False, description="Pflichtfeld")
    is_visible: bool = Field(True, description="In Tabelle sichtbar")
    options: Optional[List[str]] = Field(None, description="Optionen für Select-Felder")
    display_order: int = Field(0, description="Anzeigereihenfolge")
    description: Optional[str] = Field(None, max_length=500, description="Beschreibung")

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        allowed = ["text", "number", "date", "boolean", "select", "multi_select", "url", "email"]
        if v not in allowed:
            raise ValueError(f"Feldtyp muss einer der folgenden Werte sein: {', '.join(allowed)}")
        return v


class CustomFieldDefinitionResponse(BaseModel):
    """Custom field definition response."""
    id: int
    field_name: str
    field_slug: str
    field_type: str
    is_required: bool
    is_visible: bool
    options: Optional[List[str]] = None
    display_order: int
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Import/Export Schemas ────────────────────────────────────────────────────

class ImportLogResponse(BaseModel):
    """Import log response."""
    id: int
    source: str
    status: str
    filename: Optional[str] = None
    total_rows: int
    imported: int
    updated: int
    skipped: int
    errors: int
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Segment Schemas ──────────────────────────────────────────────────────────

class SegmentCreate(BaseModel):
    """Schema for creating a contact segment."""
    name: str = Field(..., min_length=1, max_length=255, description="Segment-Name")
    description: Optional[str] = Field(None, description="Beschreibung")
    filter_json: Optional[Dict[str, Any]] = Field(None, description="Filter-Kriterien als JSON")
    is_dynamic: bool = Field(True, description="Dynamisches Segment (wird bei Abfrage neu berechnet)")


class SegmentUpdate(BaseModel):
    """Schema for updating a contact segment."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    filter_json: Optional[Dict[str, Any]] = None
    is_dynamic: Optional[bool] = None
    is_active: Optional[bool] = None


class SegmentResponse(BaseModel):
    """Segment response."""
    id: int
    name: str
    description: Optional[str] = None
    filter_json: Optional[Dict[str, Any]] = None
    is_dynamic: bool
    contact_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SegmentListResponse(BaseModel):
    """List of segments."""
    items: List[SegmentResponse]
    total: int


# ─── Search / Filter Schemas ─────────────────────────────────────────────────

class ContactSearchParams(BaseModel):
    """Contact search and filter parameters."""
    search: Optional[str] = Field(None, description="Freitextsuche (Name, E-Mail, Telefon)")
    lifecycle_stage: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    has_email: Optional[bool] = None
    has_phone: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    score_min: Optional[int] = None
    score_max: Optional[int] = None
    company: Optional[str] = None
    gender: Optional[str] = None
    sort_by: str = Field("created_at", description="Sortierfeld")
    sort_order: str = Field("desc", description="Sortierrichtung: asc oder desc")
    page: int = Field(1, ge=1, description="Seitennummer")
    page_size: int = Field(50, ge=1, le=500, description="Einträge pro Seite")
