"""ARIIA v2.0 – Contact Repository (Data Access Layer).

@ARCH: Contacts Refactoring, Phase 1 – Repository Pattern
Encapsulates all database operations for the Contact module.
Uses SQLAlchemy ORM with sync sessions (consistent with existing codebase).

Design Principles
-----------------
- Single Responsibility: Only DB operations, no business logic
- Tenant isolation enforced at query level
- Soft-delete support (deleted_at != NULL)
- Returns ORM objects; serialization happens in the service layer
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.contact_models import (
    Contact,
    ContactActivity,
    ContactCustomFieldDefinition,
    ContactCustomFieldValue,
    ContactIdentifier,
    ContactImportLog,
    ContactNote,
    ContactSegment,
    ContactTag,
    ContactTagAssociation,
)

logger = structlog.get_logger()


class ContactRepository:
    """Repository for Contact CRUD and query operations.

    All methods require a SQLAlchemy Session and tenant_id for isolation.
    """

    # ── Contact CRUD ──────────────────────────────────────────────────────

    def get_by_id(self, db: Session, tenant_id: int, contact_id: int,
                  include_deleted: bool = False) -> Optional[Contact]:
        """Get a single contact by ID within a tenant."""
        q = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.tenant_id == tenant_id,
        )
        if not include_deleted:
            q = q.filter(Contact.deleted_at.is_(None))
        return q.first()

    def list_contacts(
        self,
        db: Session,
        tenant_id: int,
        *,
        search: Optional[str] = None,
        lifecycle_stage: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        has_email: Optional[bool] = None,
        has_phone: Optional[bool] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Contact], int]:
        """List contacts with filtering, search, sorting, and pagination.

        Returns
        -------
        Tuple[List[Contact], int]
            A tuple of (contacts, total_count).
        """
        q = db.query(Contact).filter(
            Contact.tenant_id == tenant_id,
            Contact.deleted_at.is_(None),
        )

        # ── Full-text search ──────────────────────────────────────────────
        if search:
            search_term = f"%{search}%"
            q = q.filter(
                or_(
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.phone.ilike(search_term),
                    Contact.company.ilike(search_term),
                    func.concat(Contact.first_name, " ", Contact.last_name).ilike(search_term),
                )
            )

        # ── Filters ──────────────────────────────────────────────────────
        if lifecycle_stage:
            q = q.filter(Contact.lifecycle_stage == lifecycle_stage)
        if source:
            q = q.filter(Contact.source == source)
        if has_email is True:
            q = q.filter(Contact.email.isnot(None), Contact.email != "")
        elif has_email is False:
            q = q.filter(or_(Contact.email.is_(None), Contact.email == ""))
        if has_phone is True:
            q = q.filter(Contact.phone.isnot(None), Contact.phone != "")
        elif has_phone is False:
            q = q.filter(or_(Contact.phone.is_(None), Contact.phone == ""))
        if created_after:
            q = q.filter(Contact.created_at >= created_after)
        if created_before:
            q = q.filter(Contact.created_at <= created_before)
        if score_min is not None:
            q = q.filter(Contact.score >= score_min)
        if score_max is not None:
            q = q.filter(Contact.score <= score_max)

        # ── Tag filter ────────────────────────────────────────────────────
        if tags:
            tag_ids_subq = (
                db.query(ContactTag.id)
                .filter(ContactTag.tenant_id == tenant_id, ContactTag.name.in_(tags))
                .subquery()
            )
            contact_ids_with_tags = (
                db.query(ContactTagAssociation.contact_id)
                .filter(ContactTagAssociation.tag_id.in_(tag_ids_subq.select()))
                .distinct()
                .subquery()
            )
            q = q.filter(Contact.id.in_(contact_ids_with_tags.select()))

        # ── Count ─────────────────────────────────────────────────────────
        total = q.count()

        # ── Sorting ───────────────────────────────────────────────────────
        sort_column = getattr(Contact, sort_by, Contact.created_at)
        if sort_order == "asc":
            q = q.order_by(sort_column.asc())
        else:
            q = q.order_by(sort_column.desc())

        # ── Pagination ────────────────────────────────────────────────────
        offset = (page - 1) * page_size
        contacts = q.offset(offset).limit(page_size).all()

        return contacts, total

    def create(self, db: Session, tenant_id: int, **kwargs) -> Contact:
        """Create a new contact."""
        contact = Contact(tenant_id=tenant_id, **kwargs)
        db.add(contact)
        db.flush()
        return contact

    def update(self, db: Session, contact: Contact, **kwargs) -> Contact:
        """Update an existing contact with the given fields."""
        for key, value in kwargs.items():
            if hasattr(contact, key) and value is not None:
                setattr(contact, key, value)
        contact.updated_at = datetime.now(timezone.utc)
        db.flush()
        return contact

    def soft_delete(self, db: Session, contact: Contact) -> Contact:
        """Soft-delete a contact by setting deleted_at."""
        contact.deleted_at = datetime.now(timezone.utc)
        db.flush()
        return contact

    def hard_delete(self, db: Session, contact: Contact) -> None:
        """Permanently delete a contact and all related data."""
        db.delete(contact)
        db.flush()

    def bulk_soft_delete(self, db: Session, tenant_id: int, contact_ids: List[int]) -> int:
        """Soft-delete multiple contacts. Returns count of affected rows."""
        now = datetime.now(timezone.utc)
        count = (
            db.query(Contact)
            .filter(
                Contact.id.in_(contact_ids),
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None),
            )
            .update({"deleted_at": now}, synchronize_session=False)
        )
        db.flush()
        return count

    def bulk_hard_delete(self, db: Session, tenant_id: int, contact_ids: List[int]) -> int:
        """Permanently delete multiple contacts. Returns count of affected rows."""
        count = (
            db.query(Contact)
            .filter(Contact.id.in_(contact_ids), Contact.tenant_id == tenant_id)
            .delete(synchronize_session=False)
        )
        db.flush()
        return count

    def count(self, db: Session, tenant_id: int, include_deleted: bool = False) -> int:
        """Count contacts for a tenant."""
        q = db.query(func.count(Contact.id)).filter(Contact.tenant_id == tenant_id)
        if not include_deleted:
            q = q.filter(Contact.deleted_at.is_(None))
        return q.scalar() or 0

    def find_by_email(self, db: Session, tenant_id: int, email: str) -> Optional[Contact]:
        """Find a contact by email within a tenant."""
        return (
            db.query(Contact)
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.email == email,
                Contact.deleted_at.is_(None),
            )
            .first()
        )

    def find_by_phone(self, db: Session, tenant_id: int, phone: str) -> Optional[Contact]:
        """Find a contact by phone within a tenant."""
        return (
            db.query(Contact)
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.phone == phone,
                Contact.deleted_at.is_(None),
            )
            .first()
        )

    def find_by_identifier(self, db: Session, tenant_id: int,
                           identifier_type: str, identifier_value: str) -> Optional[Contact]:
        """Find a contact by any identifier (email, phone, external_id, etc.)."""
        ci = (
            db.query(ContactIdentifier)
            .filter(
                ContactIdentifier.tenant_id == tenant_id,
                ContactIdentifier.identifier_type == identifier_type,
                ContactIdentifier.identifier_value == identifier_value,
            )
            .first()
        )
        if ci:
            return self.get_by_id(db, tenant_id, ci.contact_id)
        return None

    # ── Identifiers ───────────────────────────────────────────────────────

    def add_identifier(self, db: Session, contact_id: int, tenant_id: int,
                       identifier_type: str, identifier_value: str,
                       is_primary: bool = False) -> ContactIdentifier:
        """Add an identifier to a contact."""
        ci = ContactIdentifier(
            contact_id=contact_id,
            tenant_id=tenant_id,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            is_primary=is_primary,
        )
        db.add(ci)
        db.flush()
        return ci

    # ── Activities ────────────────────────────────────────────────────────

    def add_activity(self, db: Session, contact_id: int, tenant_id: int,
                     activity_type: str, title: str,
                     description: Optional[str] = None,
                     metadata_json: Optional[str] = None,
                     performed_by: Optional[int] = None,
                     performed_by_name: Optional[str] = None) -> ContactActivity:
        """Record an activity for a contact."""
        activity = ContactActivity(
            contact_id=contact_id,
            tenant_id=tenant_id,
            activity_type=activity_type,
            title=title,
            description=description,
            metadata_json=metadata_json,
            performed_by=performed_by,
            performed_by_name=performed_by_name,
        )
        db.add(activity)
        db.flush()
        return activity

    def list_activities(self, db: Session, contact_id: int, tenant_id: int,
                        page: int = 1, page_size: int = 50,
                        activity_type: Optional[str] = None) -> Tuple[List[ContactActivity], int]:
        """List activities for a contact with pagination."""
        q = db.query(ContactActivity).filter(
            ContactActivity.contact_id == contact_id,
            ContactActivity.tenant_id == tenant_id,
        )
        if activity_type:
            q = q.filter(ContactActivity.activity_type == activity_type)

        total = q.count()
        activities = (
            q.order_by(ContactActivity.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return activities, total

    # ── Notes ─────────────────────────────────────────────────────────────

    def add_note(self, db: Session, contact_id: int, tenant_id: int,
                 content: str, is_pinned: bool = False,
                 created_by: Optional[int] = None,
                 created_by_name: Optional[str] = None) -> ContactNote:
        """Add a note to a contact."""
        note = ContactNote(
            contact_id=contact_id,
            tenant_id=tenant_id,
            content=content,
            is_pinned=is_pinned,
            created_by=created_by,
            created_by_name=created_by_name,
        )
        db.add(note)
        db.flush()
        return note

    def list_notes(self, db: Session, contact_id: int, tenant_id: int) -> List[ContactNote]:
        """List all notes for a contact, pinned first."""
        return (
            db.query(ContactNote)
            .filter(
                ContactNote.contact_id == contact_id,
                ContactNote.tenant_id == tenant_id,
            )
            .order_by(ContactNote.is_pinned.desc(), ContactNote.created_at.desc())
            .all()
        )

    def update_note(self, db: Session, note_id: int, tenant_id: int,
                    **kwargs) -> Optional[ContactNote]:
        """Update a note."""
        note = db.query(ContactNote).filter(
            ContactNote.id == note_id,
            ContactNote.tenant_id == tenant_id,
        ).first()
        if note:
            for key, value in kwargs.items():
                if hasattr(note, key) and value is not None:
                    setattr(note, key, value)
            db.flush()
        return note

    def delete_note(self, db: Session, note_id: int, tenant_id: int) -> bool:
        """Delete a note. Returns True if deleted."""
        count = (
            db.query(ContactNote)
            .filter(ContactNote.id == note_id, ContactNote.tenant_id == tenant_id)
            .delete(synchronize_session=False)
        )
        db.flush()
        return count > 0

    # ── Tags ──────────────────────────────────────────────────────────────

    def get_or_create_tag(self, db: Session, tenant_id: int, name: str,
                          color: str = "#6C5CE7",
                          description: Optional[str] = None) -> ContactTag:
        """Get an existing tag or create a new one."""
        tag = db.query(ContactTag).filter(
            ContactTag.tenant_id == tenant_id,
            ContactTag.name == name,
        ).first()
        if not tag:
            tag = ContactTag(
                tenant_id=tenant_id,
                name=name,
                color=color,
                description=description,
            )
            db.add(tag)
            db.flush()
        return tag

    def list_tags(self, db: Session, tenant_id: int) -> List[Dict[str, Any]]:
        """List all tags for a tenant with contact counts."""
        tags = db.query(ContactTag).filter(ContactTag.tenant_id == tenant_id).all()
        result = []
        for tag in tags:
            count = (
                db.query(func.count(ContactTagAssociation.id))
                .filter(ContactTagAssociation.tag_id == tag.id)
                .scalar() or 0
            )
            result.append({
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description,
                "contact_count": count,
            })
        return result

    def add_tag_to_contact(self, db: Session, contact_id: int, tag_id: int) -> Optional[ContactTagAssociation]:
        """Associate a tag with a contact."""
        existing = db.query(ContactTagAssociation).filter(
            ContactTagAssociation.contact_id == contact_id,
            ContactTagAssociation.tag_id == tag_id,
        ).first()
        if existing:
            return existing
        assoc = ContactTagAssociation(contact_id=contact_id, tag_id=tag_id)
        db.add(assoc)
        db.flush()
        return assoc

    def remove_tag_from_contact(self, db: Session, contact_id: int, tag_id: int) -> bool:
        """Remove a tag from a contact."""
        count = (
            db.query(ContactTagAssociation)
            .filter(
                ContactTagAssociation.contact_id == contact_id,
                ContactTagAssociation.tag_id == tag_id,
            )
            .delete(synchronize_session=False)
        )
        db.flush()
        return count > 0

    def get_contact_tags(self, db: Session, contact_id: int) -> List[ContactTag]:
        """Get all tags for a contact."""
        tag_ids = (
            db.query(ContactTagAssociation.tag_id)
            .filter(ContactTagAssociation.contact_id == contact_id)
            .all()
        )
        if not tag_ids:
            return []
        return db.query(ContactTag).filter(ContactTag.id.in_([t[0] for t in tag_ids])).all()

    # ── Custom Fields ─────────────────────────────────────────────────────

    def list_custom_field_definitions(self, db: Session, tenant_id: int) -> List[ContactCustomFieldDefinition]:
        """List all custom field definitions for a tenant."""
        return (
            db.query(ContactCustomFieldDefinition)
            .filter(ContactCustomFieldDefinition.tenant_id == tenant_id)
            .order_by(ContactCustomFieldDefinition.display_order)
            .all()
        )

    def create_custom_field_definition(self, db: Session, tenant_id: int,
                                        **kwargs) -> ContactCustomFieldDefinition:
        """Create a custom field definition."""
        cfd = ContactCustomFieldDefinition(tenant_id=tenant_id, **kwargs)
        db.add(cfd)
        db.flush()
        return cfd

    def set_custom_field_value(self, db: Session, contact_id: int,
                                field_definition_id: int, value: str) -> ContactCustomFieldValue:
        """Set or update a custom field value for a contact."""
        existing = db.query(ContactCustomFieldValue).filter(
            ContactCustomFieldValue.contact_id == contact_id,
            ContactCustomFieldValue.field_definition_id == field_definition_id,
        ).first()
        if existing:
            existing.value = value
            existing.updated_at = datetime.now(timezone.utc)
            db.flush()
            return existing
        cfv = ContactCustomFieldValue(
            contact_id=contact_id,
            field_definition_id=field_definition_id,
            value=value,
        )
        db.add(cfv)
        db.flush()
        return cfv

    def get_custom_field_values(self, db: Session, contact_id: int) -> Dict[str, Any]:
        """Get all custom field values for a contact as a dict."""
        values = (
            db.query(ContactCustomFieldValue, ContactCustomFieldDefinition)
            .join(ContactCustomFieldDefinition,
                  ContactCustomFieldValue.field_definition_id == ContactCustomFieldDefinition.id)
            .filter(ContactCustomFieldValue.contact_id == contact_id)
            .all()
        )
        return {defn.field_slug: val.value for val, defn in values}

    # ── Import Logs ───────────────────────────────────────────────────────

    def create_import_log(self, db: Session, tenant_id: int, source: str,
                          filename: Optional[str] = None) -> ContactImportLog:
        """Create an import log entry."""
        log = ContactImportLog(
            tenant_id=tenant_id,
            source=source,
            filename=filename,
            status="running",
        )
        db.add(log)
        db.flush()
        return log

    def update_import_log(self, db: Session, log: ContactImportLog, **kwargs) -> ContactImportLog:
        """Update an import log entry."""
        for key, value in kwargs.items():
            if hasattr(log, key):
                setattr(log, key, value)
        db.flush()
        return log


# Singleton instance
contact_repo = ContactRepository()
