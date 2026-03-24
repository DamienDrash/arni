"""ARIIA v2.0 – Contact Management API Router (v2).

@ARCH: Contacts Refactoring, Phase 2 – REST API (Extended)
Full v2 API endpoints for the Contact Management module.
Replaces the legacy /admin/members/ endpoints with a clean,
RESTful API following Enterprise CRM best practices.

Endpoints
---------
# Contact CRUD
GET    /v2/contacts                    – List contacts (paginated, filterable)
POST   /v2/contacts                    – Create a new contact
GET    /v2/contacts/stats              – Contact statistics
GET    /v2/contacts/{id}               – Get a single contact
PUT    /v2/contacts/{id}               – Update a contact
DELETE /v2/contacts/{id}               – Soft-delete a contact
POST   /v2/contacts/bulk-delete        – Bulk delete contacts
POST   /v2/contacts/bulk-update        – Bulk update contacts

# Duplicate Detection & Merge
POST   /v2/contacts/check-duplicates   – Check for duplicates
GET    /v2/contacts/duplicates         – List all duplicate groups
POST   /v2/contacts/merge              – Merge two contacts

# Notes
GET    /v2/contacts/{id}/notes         – List notes
POST   /v2/contacts/{id}/notes         – Add a note
PUT    /v2/contacts/{id}/notes/{nid}   – Update a note
DELETE /v2/contacts/{id}/notes/{nid}   – Delete a note

# Activities
GET    /v2/contacts/{id}/activities    – Activity timeline
POST   /v2/contacts/{id}/activities    – Add an activity

# Tags (tenant-level)
GET    /v2/contacts/tags               – List all tags
POST   /v2/contacts/tags               – Create a tag
PUT    /v2/contacts/tags/{id}          – Update a tag
DELETE /v2/contacts/tags/{id}          – Delete a tag

# Tags (contact-level)
POST   /v2/contacts/{id}/tags         – Add a tag to contact
DELETE /v2/contacts/{id}/tags/{name}   – Remove a tag from contact

# Segments
GET    /v2/contacts/segments           – List segments
POST   /v2/contacts/segments           – Create a segment
GET    /v2/contacts/segments/{id}      – Get a segment
PUT    /v2/contacts/segments/{id}      – Update a segment
DELETE /v2/contacts/segments/{id}      – Delete a segment
GET    /v2/contacts/segments/{id}/eval – Evaluate a segment

# Custom Fields
GET    /v2/contacts/custom-fields      – List custom field definitions
POST   /v2/contacts/custom-fields      – Create a custom field definition

# Import/Export
POST   /v2/contacts/import/csv         – CSV import
GET    /v2/contacts/export/csv         – CSV export
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.contacts.schemas import (
    ActivityCreate,
    ActivityListResponse,
    ContactBulkDeleteRequest,
    ContactBulkUpdateRequest,
    ContactBulkUpdateResponse,
    ContactCreate,
    ContactListResponse,
    ContactMergeRequest,
    ContactResponse,
    ContactSearchParams,
    ContactUpdate,
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionResponse,
    CustomFieldDefinitionUpdate,
    CustomFieldValueResponse,
    CustomFieldValueSet,
    DuplicateCheckResponse,
    DuplicateGroupListResponse,
    ExportRequest,
    ImportColumnMapping,
    ImportLogResponse,
    ImportPreviewResponse,
    ImportV2Request,
    LifecycleConfigResponse,
    LifecycleConfigUpdate,
    LifecycleTransitionRequest,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
    SegmentCreate,
    SegmentFilterGroup,
    SegmentListResponse,
    SegmentPreviewRequest,
    SegmentPreviewResponse,
    SegmentResponse,
    SegmentUpdate,
    TagAssignRequest,
    TagCreate,
    TagResponse,
    TagUpdate,
)
from app.contacts.service import contact_service
from app.core.auth import AuthContext, get_current_user, require_role
from app.core.db import SessionLocal
from app.core.contact_models import Contact, ContactImportLog

logger = structlog.get_logger()

router = APIRouter(prefix="/v2/contacts", tags=["contacts-v2"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(user: AuthContext):
    """Require admin role for write operations."""
    require_role(user, {"system_admin", "tenant_admin"})


# ── Contact CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=ContactListResponse)
@router.get("/", response_model=ContactListResponse)
def list_contacts(
    search: Optional[str] = Query(None, description="Freitextsuche"),
    lifecycle_stage: Optional[str] = Query(None, description="Lifecycle-Phase"),
    source: Optional[str] = Query(None, description="Quelle"),
    tags: Optional[List[str]] = Query(None, description="Tags"),
    has_email: Optional[bool] = Query(None, description="Hat E-Mail"),
    has_phone: Optional[bool] = Query(None, description="Hat Telefon"),
    company: Optional[str] = Query(None, description="Firma"),
    gender: Optional[str] = Query(None, description="Geschlecht"),
    score_min: Optional[int] = Query(None, description="Minimaler Score"),
    score_max: Optional[int] = Query(None, description="Maximaler Score"),
    created_after: Optional[str] = Query(None, description="Erstellt ab (YYYY-MM-DD)"),
    created_before: Optional[str] = Query(None, description="Erstellt bis (YYYY-MM-DD)"),
    sort_by: str = Query("created_at", description="Sortierfeld"),
    sort_order: str = Query("desc", description="Sortierrichtung"),
    page: int = Query(1, ge=1, description="Seite"),
    page_size: int = Query(50, ge=1, le=2000, description="Einträge pro Seite"),
    user: AuthContext = Depends(get_current_user),
):
    """List contacts with filtering, search, and pagination."""
    tag_list: Optional[List[str]] = None
    if tags:
        expanded_tags: List[str] = []
        for tag in tags:
            expanded_tags.extend([item.strip() for item in str(tag).split(",") if item.strip()])
        tag_list = expanded_tags or None
    created_after_dt = None
    created_before_dt = None
    try:
        if created_after:
            created_after_dt = datetime.combine(datetime.fromisoformat(created_after).date(), time.min, tzinfo=timezone.utc)
        if created_before:
            created_before_dt = datetime.combine(datetime.fromisoformat(created_before).date(), time.max, tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Ungültiges Datumsformat: {exc}") from exc

    return contact_service.list_contacts(
        tenant_id=user.tenant_id,
        search=search,
        lifecycle_stage=lifecycle_stage,
        source=source,
        tags=tag_list,
        has_email=has_email,
        has_phone=has_phone,
        company=company,
        gender=gender,
        score_min=score_min,
        score_max=score_max,
        created_after=created_after_dt,
        created_before=created_before_dt,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ContactResponse, status_code=201)
@router.post("/", response_model=ContactResponse, status_code=201)
def create_contact(
    data: ContactCreate,
    user: AuthContext = Depends(get_current_user),
):
    """Create a new contact."""
    _require_admin(user)
    try:
        return contact_service.create_contact(
            tenant_id=user.tenant_id,
            data=data,
            performed_by=user.user_id,
            performed_by_name=user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/stats", response_model=Dict[str, Any])
def get_contact_stats(user: AuthContext = Depends(get_current_user)):
    """Get contact statistics for the tenant."""
    return contact_service.get_statistics(user.tenant_id)


# ── Bulk Operations ──────────────────────────────────────────────────────────

@router.post("/bulk-delete", response_model=Dict[str, Any])
@router.post("/bulk-delete/", response_model=Dict[str, Any])
def bulk_delete_contacts(
    data: ContactBulkDeleteRequest,
    user: AuthContext = Depends(get_current_user),
):
    """Bulk delete contacts (soft or hard delete)."""
    _require_admin(user)
    count = contact_service.delete_contacts(
        tenant_id=user.tenant_id,
        contact_ids=data.ids,
        permanent=data.permanent,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    return {"deleted": count, "permanent": data.permanent}


@router.post("/bulk-update", response_model=ContactBulkUpdateResponse)
@router.post("/bulk-update/", response_model=ContactBulkUpdateResponse)
def bulk_update_contacts(
    data: ContactBulkUpdateRequest,
    user: AuthContext = Depends(get_current_user),
):
    """Bulk update multiple contacts (lifecycle, tags, consent)."""
    _require_admin(user)
    return contact_service.bulk_update_contacts(
        tenant_id=user.tenant_id,
        data=data,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )


# ── Duplicate Detection & Merge ──────────────────────────────────────────────

@router.post("/check-duplicates", response_model=DuplicateCheckResponse)
@router.post("/check-duplicates/", response_model=DuplicateCheckResponse)
def check_duplicates(
    email: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    first_name: Optional[str] = Query(None),
    last_name: Optional[str] = Query(None),
    exclude_id: Optional[int] = Query(None),
    user: AuthContext = Depends(get_current_user),
):
    """Check for potential duplicates before creating/updating a contact."""
    return contact_service.check_duplicates(
        tenant_id=user.tenant_id,
        email=email,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        exclude_id=exclude_id,
    )


@router.get("/duplicates", response_model=DuplicateGroupListResponse)
@router.get("/duplicates/", response_model=DuplicateGroupListResponse)
def list_duplicate_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
):
    """List all groups of potential duplicate contacts."""
    return contact_service.list_duplicate_groups(
        tenant_id=user.tenant_id,
        page=page,
        page_size=page_size,
    )


@router.post("/merge", response_model=ContactResponse)
@router.post("/merge/", response_model=ContactResponse)
def merge_contacts(
    data: ContactMergeRequest,
    user: AuthContext = Depends(get_current_user),
):
    """Merge two contacts into one."""
    _require_admin(user)
    result = contact_service.merge_contacts(
        tenant_id=user.tenant_id,
        primary_id=data.primary_id,
        secondary_id=data.secondary_id,
        fields_from_secondary=data.fields_from_secondary,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Einer oder beide Kontakte nicht gefunden")
    return result


# ── Tags (Tenant-level) ─────────────────────────────────────────────────────

@router.get("/tags", response_model=List[TagResponse])
def list_tags(user: AuthContext = Depends(get_current_user)):
    """List all tags for the tenant."""
    return contact_service.list_tags(user.tenant_id)


@router.post("/tags", response_model=TagResponse, status_code=201)
@router.post("/tags/", response_model=TagResponse, status_code=201)
def create_tag(
    data: TagCreate,
    user: AuthContext = Depends(get_current_user),
):
    """Create a new tag."""
    _require_admin(user)
    return contact_service.create_tag(
        tenant_id=user.tenant_id,
        name=data.name,
        color=data.color,
        description=data.description,
    )


@router.put("/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: int,
    data: TagUpdate,
    user: AuthContext = Depends(get_current_user),
):
    """Update a tag."""
    _require_admin(user)
    result = contact_service.update_tag(
        tenant_id=user.tenant_id,
        tag_id=tag_id,
        name=data.name,
        color=data.color,
        description=data.description,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")
    return result


@router.delete("/tags/{tag_id}", response_model=Dict[str, Any])
def delete_tag(
    tag_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Delete a tag and all its associations."""
    _require_admin(user)
    result = contact_service.delete_tag(user.tenant_id, tag_id)
    if not result:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")
    return {"deleted": True}


# ── Segments ─────────────────────────────────────────────────────────────────

@router.get("/segments", response_model=SegmentListResponse)
@router.get("/segments/", response_model=SegmentListResponse)
def list_segments(user: AuthContext = Depends(get_current_user)):
    """List all contact segments."""
    return contact_service.list_segments(user.tenant_id)


@router.post("/segments", response_model=SegmentResponse, status_code=201)
@router.post("/segments/", response_model=SegmentResponse, status_code=201)
def create_segment(
    data: SegmentCreate,
    user: AuthContext = Depends(get_current_user),
):
    """Create a new contact segment."""
    _require_admin(user)
    return contact_service.create_segment(
        tenant_id=user.tenant_id,
        data=data,
    )


@router.get("/segments/{segment_id}", response_model=SegmentResponse)
def get_segment(
    segment_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Get a segment by ID."""
    segment = contact_service.get_segment(user.tenant_id, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment nicht gefunden")
    return segment


@router.put("/segments/{segment_id}", response_model=SegmentResponse)
def update_segment(
    segment_id: int,
    data: SegmentUpdate,
    user: AuthContext = Depends(get_current_user),
):
    """Update a segment."""
    _require_admin(user)
    result = contact_service.update_segment(
        tenant_id=user.tenant_id,
        segment_id=segment_id,
        data=data,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Segment nicht gefunden")
    return result


@router.delete("/segments/{segment_id}", response_model=Dict[str, Any])
def delete_segment(
    segment_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Delete a segment."""
    _require_admin(user)
    result = contact_service.delete_segment(user.tenant_id, segment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Segment nicht gefunden")
    return {"deleted": True}


@router.get("/segments/{segment_id}/evaluate", response_model=ContactListResponse)
def evaluate_segment(
    segment_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user: AuthContext = Depends(get_current_user),
):
    """Evaluate a dynamic segment and return matching contacts."""
    result = contact_service.evaluate_segment(user.tenant_id, segment_id, page, page_size)
    if not result:
        raise HTTPException(status_code=404, detail="Segment nicht gefunden oder keine Filter definiert")
    return result


@router.post("/segments/preview", response_model=SegmentPreviewResponse)
@router.post("/segments/preview/", response_model=SegmentPreviewResponse)
def preview_segment(
    data: SegmentPreviewRequest,
    user: AuthContext = Depends(get_current_user),
):
    """Preview segment evaluation without saving (count + sample)."""
    return contact_service.preview_segment(
        tenant_id=user.tenant_id,
        filter_groups=data.filter_groups,
        group_connector=data.group_connector,
    )


# ── Custom Fields ────────────────────────────────────────────────────────────

@router.get("/custom-fields", response_model=List[CustomFieldDefinitionResponse])
def list_custom_fields(user: AuthContext = Depends(get_current_user)):
    """List all custom field definitions for the tenant."""
    return contact_service.list_custom_field_definitions(user.tenant_id)


@router.post("/custom-fields", response_model=CustomFieldDefinitionResponse, status_code=201)
@router.post("/custom-fields/", response_model=CustomFieldDefinitionResponse, status_code=201)
def create_custom_field(
    data: CustomFieldDefinitionCreate,
    user: AuthContext = Depends(get_current_user),
):
    """Create a custom field definition."""
    _require_admin(user)
    return contact_service.create_custom_field_definition(
        tenant_id=user.tenant_id,
        field_name=data.field_name,
        field_slug=data.field_slug,
        field_type=data.field_type,
        is_required=data.is_required,
        is_visible=data.is_visible,
        options=data.options,
        display_order=data.display_order,
        description=data.description,
    )


# ── Custom Fields (Extended Phase 3) ──────────────────────────────────────

@router.put("/custom-fields/{field_id}", response_model=CustomFieldDefinitionResponse)
def update_custom_field(
    field_id: int,
    data: CustomFieldDefinitionUpdate,
    user: AuthContext = Depends(get_current_user),
):
    """Update a custom field definition."""
    _require_admin(user)
    result = contact_service.update_custom_field_definition(user.tenant_id, field_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Custom Field nicht gefunden")
    return result


@router.delete("/custom-fields/{field_id}", response_model=Dict[str, Any])
def delete_custom_field(
    field_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Delete a custom field definition and all its values."""
    _require_admin(user)
    result = contact_service.delete_custom_field_definition(user.tenant_id, field_id)
    if not result:
        raise HTTPException(status_code=404, detail="Custom Field nicht gefunden")
    return {"deleted": True}


# ── Lifecycle Config (Phase 3) ─────────────────────────────────────────

@router.get("/lifecycle-config", response_model=LifecycleConfigResponse)
def get_lifecycle_config(
    user: AuthContext = Depends(get_current_user),
):
    """Get lifecycle stage configuration for the tenant."""
    return contact_service.get_lifecycle_config(user.tenant_id)


@router.put("/lifecycle-config", response_model=LifecycleConfigResponse)
@router.put("/lifecycle-config/", response_model=LifecycleConfigResponse)
def update_lifecycle_config(
    data: LifecycleConfigUpdate,
    user: AuthContext = Depends(get_current_user),
):
    """Update lifecycle stage configuration for the tenant."""
    _require_admin(user)
    return contact_service.update_lifecycle_config(
        tenant_id=user.tenant_id,
        stages=data.stages,
        default_stage=data.default_stage,
    )


# ── Single Contact ───────────────────────────────────────────────────────────

@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Get a single contact by ID."""
    contact = contact_service.get_contact(user.tenant_id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    data: ContactUpdate,
    user: AuthContext = Depends(get_current_user),
):
    """Update a contact."""
    _require_admin(user)
    try:
        contact = contact_service.update_contact(
            tenant_id=user.tenant_id,
            contact_id=contact_id,
            data=data,
            performed_by=user.user_id,
            performed_by_name=user.email,
        )
        if not contact:
            raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
        return contact
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{contact_id}", response_model=Dict[str, Any])
def delete_contact(
    contact_id: int,
    permanent: bool = Query(False, description="Permanent löschen"),
    user: AuthContext = Depends(get_current_user),
):
    """Delete a single contact."""
    _require_admin(user)
    count = contact_service.delete_contacts(
        tenant_id=user.tenant_id,
        contact_ids=[contact_id],
        permanent=permanent,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if count == 0:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return {"deleted": count, "permanent": permanent}


# ── Notes ─────────────────────────────────────────────────────────────────────

@router.get("/{contact_id}/notes", response_model=List[NoteResponse])
def list_notes(
    contact_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """List all notes for a contact."""
    return contact_service.list_notes(user.tenant_id, contact_id)


@router.post("/{contact_id}/notes", response_model=NoteResponse, status_code=201)
@router.post("/{contact_id}/notes/", response_model=NoteResponse, status_code=201)
def add_note(
    contact_id: int,
    data: NoteCreate,
    user: AuthContext = Depends(get_current_user),
):
    """Add a note to a contact."""
    note = contact_service.add_note(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        data=data,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return note


@router.put("/{contact_id}/notes/{note_id}", response_model=NoteResponse)
def update_note(
    contact_id: int,
    note_id: int,
    data: NoteUpdate,
    user: AuthContext = Depends(get_current_user),
):
    """Update a note."""
    _require_admin(user)
    note = contact_service.update_note(user.tenant_id, note_id, data)
    if not note:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden")
    return note


@router.delete("/{contact_id}/notes/{note_id}", response_model=Dict[str, Any])
def delete_note(
    contact_id: int,
    note_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Delete a note."""
    _require_admin(user)
    result = contact_service.delete_note(user.tenant_id, note_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden")
    return {"deleted": True}


# ── Activities / Timeline ─────────────────────────────────────────────────────

@router.get("/{contact_id}/activities", response_model=ActivityListResponse)
def list_activities(
    contact_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    activity_type: Optional[str] = Query(None),
    user: AuthContext = Depends(get_current_user),
):
    """Get the activity timeline for a contact."""
    return contact_service.list_activities(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        page=page,
        page_size=page_size,
        activity_type=activity_type,
    )


@router.post("/{contact_id}/activities", status_code=201)
@router.post("/{contact_id}/activities/", status_code=201)
def add_activity(
    contact_id: int,
    data: ActivityCreate,
    user: AuthContext = Depends(get_current_user),
):
    """Manually add an activity to a contact's timeline."""
    result = contact_service.add_activity(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        data=data,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return result


# ── Tags on Contact ──────────────────────────────────────────────────────────

@router.post("/{contact_id}/tags", response_model=Dict[str, Any], status_code=201)
@router.post("/{contact_id}/tags/", response_model=Dict[str, Any], status_code=201)
def add_tag_to_contact(
    contact_id: int,
    data: TagAssignRequest,
    user: AuthContext = Depends(get_current_user),
):
    """Add a tag to a contact."""
    result = contact_service.add_tag_to_contact(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        tag_name=data.tag_name,
        color=data.color or "#6C5CE7",
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return {"status": "tag_added", "tag": data.tag_name}


@router.delete("/{contact_id}/tags/{tag_name}", response_model=Dict[str, Any])
def remove_tag_from_contact(
    contact_id: int,
    tag_name: str,
    user: AuthContext = Depends(get_current_user),
):
    """Remove a tag from a contact."""
    result = contact_service.remove_tag_from_contact(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        tag_name=tag_name,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    return {"status": "tag_removed" if result else "tag_not_found", "tag": tag_name}



# ── Custom Field Values on Contact (Phase 3) ───────────────────────────────

@router.get("/{contact_id}/custom-fields", response_model=List[CustomFieldValueResponse])
def get_contact_custom_fields(
    contact_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Get all custom field values for a contact."""
    return contact_service.get_contact_custom_fields(user.tenant_id, contact_id)


@router.put("/{contact_id}/custom-fields", response_model=Dict[str, Any])
@router.put("/{contact_id}/custom-fields/", response_model=Dict[str, Any])
def set_contact_custom_fields(
    contact_id: int,
    data: List[CustomFieldValueSet],
    user: AuthContext = Depends(get_current_user),
):
    """Set custom field values on a contact."""
    _require_admin(user)
    result = contact_service.set_contact_custom_fields(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        field_values=data,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return {"updated": len(data)}


# ── Lifecycle Transition (Phase 3) ──────────────────────────────────────────

@router.post("/{contact_id}/lifecycle-transition", response_model=ContactResponse)
@router.post("/{contact_id}/lifecycle-transition/", response_model=ContactResponse)
def transition_lifecycle(
    contact_id: int,
    data: LifecycleTransitionRequest,
    user: AuthContext = Depends(get_current_user),
):
    """Manually transition a contact's lifecycle stage with audit trail."""
    _require_admin(user)
    result = contact_service.transition_lifecycle(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        new_stage=data.new_stage,
        reason=data.reason,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return result


# ── Import V2 (Phase 3 – with Preview, Mapping, Progress) ──────────────────

@router.post("/import/preview", response_model=ImportPreviewResponse)
@router.post("/import/preview/", response_model=ImportPreviewResponse)
async def import_preview(
    file: UploadFile = File(...),
    user: AuthContext = Depends(get_current_user),
):
    """Upload a CSV and get a preview with auto-detected column mappings."""
    _require_admin(user)
    content = await file.read()
    text_content = content.decode("utf-8")
    return contact_service.preview_import(
        tenant_id=user.tenant_id,
        csv_content=text_content,
        filename=file.filename or "upload.csv",
    )


@router.post("/import/execute", response_model=Dict[str, Any])
@router.post("/import/execute/", response_model=Dict[str, Any])
def import_execute(
    data: ImportV2Request,
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user),
):
    """Execute import with custom column mappings (background)."""
    _require_admin(user)
    background_tasks.add_task(
        _process_import_v2,
        tenant_id=user.tenant_id,
        request=data,
        user_id=user.user_id,
        user_email=user.email,
    )
    return {"status": "import_started", "filename": data.filename}


def _process_import_v2(
    tenant_id: int,
    request: ImportV2Request,
    user_id: int,
    user_email: str,
):
    """Background task for Import V2 with column mapping."""
    contact_service.execute_import_v2(
        tenant_id=tenant_id,
        request=request,
        performed_by=user_id,
        performed_by_name=user_email,
    )


@router.get("/import/logs", response_model=List[ImportLogResponse])
@router.get("/import/logs/", response_model=List[ImportLogResponse])
def list_import_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
):
    """List import history logs."""
    return contact_service.list_import_logs(
        tenant_id=user.tenant_id,
        page=page,
        page_size=page_size,
    )


@router.get("/import/logs/{log_id}", response_model=ImportLogResponse)
def get_import_log(
    log_id: int,
    user: AuthContext = Depends(get_current_user),
):
    """Get details of a specific import log."""
    result = contact_service.get_import_log(user.tenant_id, log_id)
    if not result:
        raise HTTPException(status_code=404, detail="Import-Log nicht gefunden")
    return result


# ── Legacy CSV Import ───────────────────────────────────────────────────────

@router.post("/import/csv", response_model=Dict[str, Any])
@router.post("/import/csv/", response_model=Dict[str, Any])
async def import_csv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: AuthContext = Depends(get_current_user),
):
    """Import contacts from CSV in background (legacy)."""
    _require_admin(user)
    content = await file.read()
    text_content = content.decode("utf-8")
    background_tasks.add_task(
        _process_csv_import, text_content, user.tenant_id,
        user.user_id, user.email, file.filename,
    )
    return {"status": "import_started", "filename": file.filename}


def _process_csv_import(
    csv_content: str,
    tenant_id: int,
    user_id: int,
    user_email: str,
    filename: str,
):
    """Background task for CSV import (legacy)."""
    db = SessionLocal()
    from app.contacts.repository import contact_repo
    from app.core.contact_models import Contact, ContactImportLog, ActivityType

    log = contact_repo.create_import_log(db, tenant_id, "csv", filename)
    db.commit()

    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        log.total_rows = len(rows)

        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors_count = 0
        error_details = []

        for i, row in enumerate(rows):
            try:
                first_name = row.get("first_name", "").strip()
                last_name = row.get("last_name", "").strip()
                email = row.get("email", "").strip()
                phone = row.get("phone", row.get("phone_number", "")).strip()

                if not first_name and not last_name:
                    skipped_count += 1
                    continue

                existing = None
                if email:
                    existing = contact_repo.find_by_email(db, tenant_id, email)

                if existing:
                    if first_name:
                        existing.first_name = first_name
                    if last_name:
                        existing.last_name = last_name
                    if phone:
                        existing.phone = phone
                    if row.get("company"):
                        existing.company = row["company"].strip()
                    existing.updated_at = datetime.now(timezone.utc)
                    updated_count += 1
                else:
                    contact = Contact(
                        tenant_id=tenant_id,
                        first_name=first_name or "Unbekannt",
                        last_name=last_name or "Unbekannt",
                        email=email or None,
                        phone=phone or None,
                        company=row.get("company", "").strip() or None,
                        source="csv",
                        lifecycle_stage=row.get("lifecycle_stage", "subscriber").strip(),
                    )
                    db.add(contact)
                    imported_count += 1

                if (i + 1) % 100 == 0:
                    db.commit()

            except Exception as row_err:
                errors_count += 1
                error_details.append(f"Zeile {i + 1}: {str(row_err)}")

        db.commit()

        log.imported = imported_count
        log.updated = updated_count
        log.skipped = skipped_count
        log.errors = errors_count
        log.error_log = json.dumps(error_details) if error_details else None
        log.status = "completed"
        log.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "contact.csv_import_completed",
            tenant_id=tenant_id,
            imported=imported_count,
            updated=updated_count,
            errors=errors_count,
        )

    except Exception as e:
        log.status = "failed"
        log.error_log = str(e)
        log.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error("contact.csv_import_failed", tenant_id=tenant_id, error=str(e))
    finally:
        db.close()


# ── Export V2 (Phase 3 – with Filters, Segments, Custom Fields) ─────────────

@router.post("/export", response_model=Dict[str, Any])
@router.post("/export/", response_model=Dict[str, Any])
def export_contacts_v2(
    data: ExportRequest,
    user: AuthContext = Depends(get_current_user),
):
    """Export contacts with filters, segment, and custom fields."""
    result = contact_service.export_contacts_v2(
        tenant_id=user.tenant_id,
        export_request=data,
    )
    if data.format == "csv":
        return StreamingResponse(
            iter([result]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=contacts_export.csv"},
        )
    return {"data": result, "format": data.format}


@router.get("/export/csv")
@router.get("/export/csv/")
def export_csv(user: AuthContext = Depends(get_current_user)):
    """Export all contacts as CSV (legacy)."""
    db = SessionLocal()
    try:
        contacts = (
            db.query(Contact)
            .filter(Contact.tenant_id == user.tenant_id, Contact.deleted_at.is_(None))
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "id", "first_name", "last_name", "email", "phone",
            "company", "job_title", "lifecycle_stage", "source",
            "gender", "preferred_language", "score",
            "consent_email", "consent_sms", "consent_phone", "consent_whatsapp",
            "created_at",
        ]
        writer.writerow(headers)

        for c in contacts:
            writer.writerow([
                c.id, c.first_name, c.last_name, c.email, c.phone,
                c.company, c.job_title, c.lifecycle_stage, c.source,
                c.gender, c.preferred_language, c.score,
                c.consent_email, c.consent_sms, c.consent_phone, c.consent_whatsapp,
                c.created_at.isoformat() if c.created_at else "",
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=contacts_export.csv"},
        )
    finally:
        db.close()


# ─── Integration Sync Endpoints ──────────────────────────────────────────────
# These endpoints provide sync status and trigger sync operations
# directly from the Contacts module.

@router.get("/sync/status")
def get_sync_status(
    user: AuthContext = Depends(get_current_user),
):
    """Get sync status for all configured integrations."""
    require_role(user, {"system_admin", "tenant_admin"})
    from app.gateway.persistence import persistence

    sources = ["magicline", "shopify", "woocommerce", "hubspot"]
    integrations = []

    for source in sources:
        enabled = persistence.get_setting(f"integration_{source}_enabled", tenant_id=user.tenant_id) == "true"
        last_sync = persistence.get_setting(f"sync_{source}_last", tenant_id=user.tenant_id)
        status = persistence.get_setting(f"sync_{source}_status", tenant_id=user.tenant_id) or "idle"
        last_result = persistence.get_setting(f"sync_{source}_result", tenant_id=user.tenant_id)
        last_error = persistence.get_setting(f"sync_{source}_error", tenant_id=user.tenant_id)

        integrations.append({
            "source": source,
            "enabled": enabled,
            "last_sync": last_sync,
            "status": status,
            "last_result": last_result,
            "last_error": last_error if status == "failed" else None,
        })

    return {"integrations": integrations}


@router.post("/sync/{source}")
def trigger_sync(
    source: str,
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user),
):
    """Trigger a sync operation for a specific integration source.

    Supported sources: magicline, shopify, woocommerce, hubspot
    """
    require_role(user, {"system_admin", "tenant_admin"})
    from app.gateway.persistence import persistence
    import asyncio

    valid_sources = {"magicline", "shopify", "woocommerce", "hubspot"}
    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültige Quelle: {source}. Erlaubt: {', '.join(sorted(valid_sources))}",
        )

    # Check if integration is enabled
    prefix = f"integration_{source}_{user.tenant_id}"
    enabled = persistence.get_setting(f"{prefix}_enabled")
    if enabled != "true":
        raise HTTPException(
            status_code=400,
            detail=f"Integration '{source}' ist nicht aktiviert. Bitte konfigurieren Sie sie zuerst.",
        )

    # Set status to running
    persistence.set_setting(f"sync_{source}_{user.tenant_id}_status", "running")

    def _run_sync(tenant_id: int, src: str):
        try:
            if src == "magicline":
                from app.integrations.magicline.contact_sync import sync_contacts_from_magicline
                result = sync_contacts_from_magicline(tenant_id)
            elif src == "shopify":
                from app.integrations.shopify.contact_sync import sync_contacts_from_shopify
                result = asyncio.run(sync_contacts_from_shopify(tenant_id))
            elif src == "woocommerce":
                from app.integrations.woocommerce.contact_sync import sync_contacts_from_woocommerce
                result = asyncio.run(sync_contacts_from_woocommerce(tenant_id))
            elif src == "hubspot":
                from app.integrations.hubspot.contact_sync import sync_contacts_from_hubspot
                result = asyncio.run(sync_contacts_from_hubspot(tenant_id))
            else:
                raise ValueError(f"Unbekannte Quelle: {src}")

            persistence.set_setting(f"sync_{src}_{tenant_id}_status", "completed")
            persistence.set_setting(
                f"sync_{src}_{tenant_id}_last",
                datetime.now(timezone.utc).isoformat(),
            )
            persistence.set_setting(f"sync_{src}_{tenant_id}_result", str(result))
            logger.info(f"{src}.sync.completed", tenant_id=tenant_id, result=result)
        except Exception as e:
            persistence.set_setting(f"sync_{src}_{tenant_id}_status", "failed")
            persistence.set_setting(f"sync_{src}_{tenant_id}_error", str(e))
            logger.error(f"{src}.sync.failed", tenant_id=tenant_id, error=str(e))

    background_tasks.add_task(_run_sync, user.tenant_id, source)
    return {"status": "sync_started", "source": source}
