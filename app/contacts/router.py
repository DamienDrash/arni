"""ARIIA v2.0 – Contact Management API Router (v2).

@ARCH: Contacts Refactoring, Phase 1 – REST API
New v2 API endpoints for the Contact Management module.
Replaces the legacy /admin/members/ endpoints with a clean,
RESTful API following Enterprise CRM best practices.

Endpoints
---------
GET    /v2/contacts              – List contacts (paginated, filterable)
POST   /v2/contacts              – Create a new contact
GET    /v2/contacts/{id}         – Get a single contact
PUT    /v2/contacts/{id}         – Update a contact
DELETE /v2/contacts/{id}         – Soft-delete a contact
POST   /v2/contacts/bulk-delete  – Bulk delete contacts

GET    /v2/contacts/{id}/notes       – List notes
POST   /v2/contacts/{id}/notes       – Add a note
PUT    /v2/contacts/{id}/notes/{nid} – Update a note
DELETE /v2/contacts/{id}/notes/{nid} – Delete a note

GET    /v2/contacts/{id}/activities  – Activity timeline

POST   /v2/contacts/{id}/tags       – Add a tag
DELETE /v2/contacts/{id}/tags/{name} – Remove a tag

GET    /v2/contacts/tags             – List all tags
POST   /v2/contacts/tags             – Create a tag

GET    /v2/contacts/custom-fields    – List custom field definitions
POST   /v2/contacts/custom-fields    – Create a custom field definition

GET    /v2/contacts/stats            – Contact statistics

POST   /v2/contacts/import/csv       – CSV import
GET    /v2/contacts/export/csv       – CSV export
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.contacts.schemas import (
    ActivityListResponse,
    ContactBulkDeleteRequest,
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactSearchParams,
    ContactUpdate,
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionResponse,
    ImportLogResponse,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
    SegmentCreate,
    SegmentResponse,
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
    tags: Optional[str] = Query(None, description="Tags (kommagetrennt)"),
    has_email: Optional[bool] = Query(None, description="Hat E-Mail"),
    has_phone: Optional[bool] = Query(None, description="Hat Telefon"),
    sort_by: str = Query("created_at", description="Sortierfeld"),
    sort_order: str = Query("desc", description="Sortierrichtung"),
    page: int = Query(1, ge=1, description="Seite"),
    page_size: int = Query(50, ge=1, le=500, description="Einträge pro Seite"),
    user: AuthContext = Depends(get_current_user),
):
    """List contacts with filtering, search, and pagination."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    return contact_service.list_contacts(
        tenant_id=user.tenant_id,
        search=search,
        lifecycle_stage=lifecycle_stage,
        source=source,
        tags=tag_list,
        has_email=has_email,
        has_phone=has_phone,
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


# ── Tags on Contact ──────────────────────────────────────────────────────────

@router.post("/{contact_id}/tags", response_model=Dict[str, Any], status_code=201)
@router.post("/{contact_id}/tags/", response_model=Dict[str, Any], status_code=201)
def add_tag_to_contact(
    contact_id: int,
    data: TagCreate,
    user: AuthContext = Depends(get_current_user),
):
    """Add a tag to a contact."""
    result = contact_service.add_tag_to_contact(
        tenant_id=user.tenant_id,
        contact_id=contact_id,
        tag_name=data.name,
        performed_by=user.user_id,
        performed_by_name=user.email,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return {"status": "tag_added", "tag": data.name}


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


# ── CSV Import/Export ─────────────────────────────────────────────────────────

@router.post("/import/csv", response_model=Dict[str, Any])
@router.post("/import/csv/", response_model=Dict[str, Any])
async def import_csv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: AuthContext = Depends(get_current_user),
):
    """Import contacts from CSV in background."""
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
    """Background task for CSV import."""
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

                # Check for existing contact by email
                existing = None
                if email:
                    existing = contact_repo.find_by_email(db, tenant_id, email)

                if existing:
                    # Update existing
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
                    # Create new
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

                # Commit in batches of 100
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


@router.get("/export/csv")
@router.get("/export/csv/")
def export_csv(user: AuthContext = Depends(get_current_user)):
    """Export all contacts as CSV."""
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
