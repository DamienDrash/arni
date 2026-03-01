"""ARIIA v2.0 – Contact Repository (Data Access Layer).

@ARCH: Contacts Refactoring, Phase 2 – Repository Pattern (Extended)
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
from sqlalchemy import and_, func, or_, case, text
from sqlalchemy.orm import Session, joinedload

from app.core.contact_models import (
    Contact,
    ContactActivity,
    ContactCustomFieldDefinition,
    ContactCustomFieldValue,
    ContactIdentifier,
    ContactImportLog,
    ContactLifecycleConfig,
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
        company: Optional[str] = None,
        gender: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Contact], int]:
        """List contacts with filtering, search, sorting, and pagination."""
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
                    Contact.job_title.ilike(search_term),
                    func.concat(Contact.first_name, " ", Contact.last_name).ilike(search_term),
                )
            )

        # ── Filters ──────────────────────────────────────────────────────
        if lifecycle_stage:
            q = q.filter(Contact.lifecycle_stage == lifecycle_stage)
        if source:
            q = q.filter(Contact.source == source)
        if company:
            q = q.filter(Contact.company.ilike(f"%{company}%"))
        if gender:
            q = q.filter(Contact.gender == gender)
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

    def bulk_update(self, db: Session, tenant_id: int, contact_ids: List[int],
                    **update_fields) -> int:
        """Bulk-update multiple contacts with the same field values.
        
        Returns count of affected rows.
        """
        update_fields["updated_at"] = datetime.now(timezone.utc)
        count = (
            db.query(Contact)
            .filter(
                Contact.id.in_(contact_ids),
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None),
            )
            .update(update_fields, synchronize_session=False)
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

    # ── Duplicate Detection ──────────────────────────────────────────────

    def find_duplicates(self, db: Session, tenant_id: int,
                        email: Optional[str] = None,
                        phone: Optional[str] = None,
                        first_name: Optional[str] = None,
                        last_name: Optional[str] = None,
                        exclude_id: Optional[int] = None) -> List[Tuple[Contact, str, float]]:
        """Find potential duplicate contacts based on multiple criteria.
        
        Returns a list of (contact, match_reason, confidence_score) tuples.
        Confidence: 1.0 = exact email match, 0.9 = exact phone match,
                    0.7 = name match, 0.5 = partial name match.
        """
        duplicates: List[Tuple[Contact, str, float]] = []
        seen_ids: set = set()

        base_filter = [
            Contact.tenant_id == tenant_id,
            Contact.deleted_at.is_(None),
        ]
        if exclude_id:
            base_filter.append(Contact.id != exclude_id)

        # Exact email match (highest confidence)
        if email:
            matches = (
                db.query(Contact)
                .filter(*base_filter, Contact.email == email)
                .all()
            )
            for m in matches:
                if m.id not in seen_ids:
                    duplicates.append((m, "email_exact", 1.0))
                    seen_ids.add(m.id)

        # Exact phone match
        if phone:
            # Normalize phone for comparison
            matches = (
                db.query(Contact)
                .filter(*base_filter, Contact.phone == phone)
                .all()
            )
            for m in matches:
                if m.id not in seen_ids:
                    duplicates.append((m, "phone_exact", 0.9))
                    seen_ids.add(m.id)

        # Exact name match
        if first_name and last_name:
            matches = (
                db.query(Contact)
                .filter(
                    *base_filter,
                    func.lower(Contact.first_name) == first_name.lower(),
                    func.lower(Contact.last_name) == last_name.lower(),
                )
                .all()
            )
            for m in matches:
                if m.id not in seen_ids:
                    duplicates.append((m, "name_exact", 0.7))
                    seen_ids.add(m.id)

        # Partial name match (first 3 chars of first_name + exact last_name)
        if first_name and last_name and len(first_name) >= 3:
            matches = (
                db.query(Contact)
                .filter(
                    *base_filter,
                    func.lower(func.substring(Contact.first_name, 1, 3)) == first_name[:3].lower(),
                    func.lower(Contact.last_name) == last_name.lower(),
                )
                .all()
            )
            for m in matches:
                if m.id not in seen_ids:
                    duplicates.append((m, "name_partial", 0.5))
                    seen_ids.add(m.id)

        # Also check identifiers table
        if email:
            ci_matches = (
                db.query(ContactIdentifier)
                .filter(
                    ContactIdentifier.tenant_id == tenant_id,
                    ContactIdentifier.identifier_type == "email",
                    ContactIdentifier.identifier_value == email,
                )
                .all()
            )
            for ci in ci_matches:
                if ci.contact_id not in seen_ids:
                    contact = self.get_by_id(db, tenant_id, ci.contact_id)
                    if contact:
                        duplicates.append((contact, "identifier_email", 0.95))
                        seen_ids.add(ci.contact_id)

        return duplicates

    def find_all_duplicate_groups(self, db: Session, tenant_id: int,
                                  page: int = 1, page_size: int = 20) -> Tuple[List[Dict], int]:
        """Find all groups of potential duplicates within a tenant.
        
        Groups contacts by email or phone, returning groups with 2+ matches.
        Returns (groups, total_groups).
        """
        groups = []

        # Email-based duplicates
        email_dupes = (
            db.query(Contact.email, func.count(Contact.id).label("cnt"))
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None),
                Contact.email.isnot(None),
                Contact.email != "",
            )
            .group_by(Contact.email)
            .having(func.count(Contact.id) > 1)
            .all()
        )

        for email, cnt in email_dupes:
            contacts = (
                db.query(Contact)
                .filter(
                    Contact.tenant_id == tenant_id,
                    Contact.email == email,
                    Contact.deleted_at.is_(None),
                )
                .all()
            )
            groups.append({
                "match_type": "email",
                "match_value": email,
                "confidence": 1.0,
                "contacts": contacts,
            })

        # Phone-based duplicates
        phone_dupes = (
            db.query(Contact.phone, func.count(Contact.id).label("cnt"))
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None),
                Contact.phone.isnot(None),
                Contact.phone != "",
            )
            .group_by(Contact.phone)
            .having(func.count(Contact.id) > 1)
            .all()
        )

        seen_emails = {g["match_value"] for g in groups}
        for phone, cnt in phone_dupes:
            contacts = (
                db.query(Contact)
                .filter(
                    Contact.tenant_id == tenant_id,
                    Contact.phone == phone,
                    Contact.deleted_at.is_(None),
                )
                .all()
            )
            # Avoid double-counting if same contacts already in email group
            contact_ids = {c.id for c in contacts}
            already_grouped = False
            for g in groups:
                existing_ids = {c.id for c in g["contacts"]}
                if contact_ids == existing_ids:
                    already_grouped = True
                    break
            if not already_grouped:
                groups.append({
                    "match_type": "phone",
                    "match_value": phone,
                    "confidence": 0.9,
                    "contacts": contacts,
                })

        # Name-based duplicates
        name_dupes = (
            db.query(
                func.lower(Contact.first_name),
                func.lower(Contact.last_name),
                func.count(Contact.id).label("cnt"),
            )
            .filter(
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None),
            )
            .group_by(func.lower(Contact.first_name), func.lower(Contact.last_name))
            .having(func.count(Contact.id) > 1)
            .all()
        )

        for first, last, cnt in name_dupes:
            contacts = (
                db.query(Contact)
                .filter(
                    Contact.tenant_id == tenant_id,
                    func.lower(Contact.first_name) == first,
                    func.lower(Contact.last_name) == last,
                    Contact.deleted_at.is_(None),
                )
                .all()
            )
            contact_ids = {c.id for c in contacts}
            already_grouped = False
            for g in groups:
                existing_ids = {c.id for c in g["contacts"]}
                if contact_ids.issubset(existing_ids):
                    already_grouped = True
                    break
            if not already_grouped:
                groups.append({
                    "match_type": "name",
                    "match_value": f"{first} {last}",
                    "confidence": 0.7,
                    "contacts": contacts,
                })

        total = len(groups)
        # Sort by confidence desc
        groups.sort(key=lambda g: g["confidence"], reverse=True)
        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        return groups[start:end], total

    def merge_contacts(self, db: Session, tenant_id: int,
                       primary_id: int, secondary_id: int,
                       fields_from_secondary: Optional[List[str]] = None) -> Optional[Contact]:
        """Merge secondary contact into primary contact.
        
        Moves activities, notes, tags, identifiers from secondary to primary.
        Optionally copies specified fields from secondary to primary.
        Soft-deletes the secondary contact.
        """
        primary = self.get_by_id(db, tenant_id, primary_id)
        secondary = self.get_by_id(db, tenant_id, secondary_id)
        if not primary or not secondary:
            return None

        # Copy specified fields from secondary to primary
        if fields_from_secondary:
            for field in fields_from_secondary:
                sec_val = getattr(secondary, field, None)
                if sec_val is not None and hasattr(primary, field):
                    setattr(primary, field, sec_val)

        # Move activities
        db.query(ContactActivity).filter(
            ContactActivity.contact_id == secondary_id,
        ).update({"contact_id": primary_id}, synchronize_session=False)

        # Move notes
        db.query(ContactNote).filter(
            ContactNote.contact_id == secondary_id,
        ).update({"contact_id": primary_id}, synchronize_session=False)

        # Move identifiers (skip duplicates)
        secondary_identifiers = db.query(ContactIdentifier).filter(
            ContactIdentifier.contact_id == secondary_id,
        ).all()
        for si in secondary_identifiers:
            existing = db.query(ContactIdentifier).filter(
                ContactIdentifier.contact_id == primary_id,
                ContactIdentifier.identifier_type == si.identifier_type,
                ContactIdentifier.identifier_value == si.identifier_value,
            ).first()
            if not existing:
                si.contact_id = primary_id
            else:
                db.delete(si)

        # Move tag associations (skip duplicates)
        secondary_tags = db.query(ContactTagAssociation).filter(
            ContactTagAssociation.contact_id == secondary_id,
        ).all()
        for st in secondary_tags:
            existing = db.query(ContactTagAssociation).filter(
                ContactTagAssociation.contact_id == primary_id,
                ContactTagAssociation.tag_id == st.tag_id,
            ).first()
            if not existing:
                st.contact_id = primary_id
            else:
                db.delete(st)

        # Move custom field values (skip duplicates)
        secondary_cfvs = db.query(ContactCustomFieldValue).filter(
            ContactCustomFieldValue.contact_id == secondary_id,
        ).all()
        for cfv in secondary_cfvs:
            existing = db.query(ContactCustomFieldValue).filter(
                ContactCustomFieldValue.contact_id == primary_id,
                ContactCustomFieldValue.field_definition_id == cfv.field_definition_id,
            ).first()
            if not existing:
                cfv.contact_id = primary_id
            else:
                db.delete(cfv)

        # Store merge reference
        if secondary.external_ids:
            try:
                ext = json.loads(secondary.external_ids) if secondary.external_ids else {}
            except (json.JSONDecodeError, TypeError):
                ext = {}
        else:
            ext = {}
        ext["merged_from"] = secondary_id
        
        try:
            primary_ext = json.loads(primary.external_ids) if primary.external_ids else {}
        except (json.JSONDecodeError, TypeError):
            primary_ext = {}
        
        merged_from = primary_ext.get("merged_contacts", [])
        merged_from.append(secondary_id)
        primary_ext["merged_contacts"] = merged_from
        primary.external_ids = json.dumps(primary_ext)

        # Soft-delete secondary
        secondary.deleted_at = datetime.now(timezone.utc)
        primary.updated_at = datetime.now(timezone.utc)

        db.flush()
        return primary

    # ── Identifiers ───────────────────────────────────────────────────────

    def add_identifier(self, db: Session, contact_id: int, tenant_id: int,
                       identifier_type: str, identifier_value: str,
                       is_primary: bool = False) -> ContactIdentifier:
        """Add an identifier to a contact (upsert)."""
        existing = db.query(ContactIdentifier).filter(
            ContactIdentifier.contact_id == contact_id,
            ContactIdentifier.identifier_type == identifier_type,
            ContactIdentifier.identifier_value == identifier_value,
        ).first()
        if existing:
            existing.is_primary = is_primary
            db.flush()
            return existing
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
            note.updated_at = datetime.now(timezone.utc)
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

    def get_tag_by_id(self, db: Session, tenant_id: int, tag_id: int) -> Optional[ContactTag]:
        """Get a tag by ID."""
        return db.query(ContactTag).filter(
            ContactTag.id == tag_id,
            ContactTag.tenant_id == tenant_id,
        ).first()

    def update_tag(self, db: Session, tag: ContactTag, **kwargs) -> ContactTag:
        """Update a tag."""
        for key, value in kwargs.items():
            if hasattr(tag, key) and value is not None:
                setattr(tag, key, value)
        db.flush()
        return tag

    def delete_tag(self, db: Session, tag_id: int, tenant_id: int) -> bool:
        """Delete a tag and all its associations."""
        # Remove associations first
        db.query(ContactTagAssociation).filter(
            ContactTagAssociation.tag_id == tag_id,
        ).delete(synchronize_session=False)
        # Remove tag
        count = db.query(ContactTag).filter(
            ContactTag.id == tag_id,
            ContactTag.tenant_id == tenant_id,
        ).delete(synchronize_session=False)
        db.flush()
        return count > 0

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

    def bulk_add_tag(self, db: Session, tenant_id: int, contact_ids: List[int],
                     tag_name: str, color: str = "#6C5CE7") -> int:
        """Add a tag to multiple contacts. Returns count of new associations."""
        tag = self.get_or_create_tag(db, tenant_id, tag_name, color)
        added = 0
        for cid in contact_ids:
            existing = db.query(ContactTagAssociation).filter(
                ContactTagAssociation.contact_id == cid,
                ContactTagAssociation.tag_id == tag.id,
            ).first()
            if not existing:
                db.add(ContactTagAssociation(contact_id=cid, tag_id=tag.id))
                added += 1
        db.flush()
        return added

    def bulk_remove_tag(self, db: Session, tenant_id: int, contact_ids: List[int],
                        tag_name: str) -> int:
        """Remove a tag from multiple contacts. Returns count of removed associations."""
        tag = db.query(ContactTag).filter(
            ContactTag.tenant_id == tenant_id,
            ContactTag.name == tag_name,
        ).first()
        if not tag:
            return 0
        count = (
            db.query(ContactTagAssociation)
            .filter(
                ContactTagAssociation.contact_id.in_(contact_ids),
                ContactTagAssociation.tag_id == tag.id,
            )
            .delete(synchronize_session=False)
        )
        db.flush()
        return count

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

    # ── Segments ─────────────────────────────────────────────────────────

    def create_segment(self, db: Session, tenant_id: int, **kwargs) -> ContactSegment:
        """Create a new contact segment."""
        if "filter_json" in kwargs and isinstance(kwargs["filter_json"], dict):
            kwargs["filter_json"] = json.dumps(kwargs["filter_json"])
        segment = ContactSegment(tenant_id=tenant_id, **kwargs)
        db.add(segment)
        db.flush()
        return segment

    def get_segment_by_id(self, db: Session, tenant_id: int, segment_id: int) -> Optional[ContactSegment]:
        """Get a segment by ID."""
        return db.query(ContactSegment).filter(
            ContactSegment.id == segment_id,
            ContactSegment.tenant_id == tenant_id,
        ).first()

    def list_segments(self, db: Session, tenant_id: int) -> List[ContactSegment]:
        """List all segments for a tenant."""
        return (
            db.query(ContactSegment)
            .filter(ContactSegment.tenant_id == tenant_id)
            .order_by(ContactSegment.name)
            .all()
        )

    def update_segment(self, db: Session, segment: ContactSegment, **kwargs) -> ContactSegment:
        """Update a segment."""
        for key, value in kwargs.items():
            if hasattr(segment, key):
                if key == "filter_json" and isinstance(value, dict):
                    value = json.dumps(value)
                setattr(segment, key, value)
        segment.updated_at = datetime.now(timezone.utc)
        db.flush()
        return segment

    def delete_segment(self, db: Session, segment_id: int, tenant_id: int) -> bool:
        """Delete a segment."""
        count = db.query(ContactSegment).filter(
            ContactSegment.id == segment_id,
            ContactSegment.tenant_id == tenant_id,
        ).delete(synchronize_session=False)
        db.flush()
        return count > 0

    def evaluate_segment(self, db: Session, tenant_id: int,
                         filter_json: Dict[str, Any]) -> Tuple[List[Contact], int]:
        """Evaluate a legacy flat segment filter."""
        return self.list_contacts(
            db, tenant_id,
            lifecycle_stage=filter_json.get("lifecycle_stage"),
            source=filter_json.get("source"),
            tags=filter_json.get("tags"),
            has_email=filter_json.get("has_email"),
            has_phone=filter_json.get("has_phone"),
            score_min=filter_json.get("score_min"),
            score_max=filter_json.get("score_max"),
            company=filter_json.get("company"),
            gender=filter_json.get("gender"),
            page=1,
            page_size=10000,
        )

    def evaluate_segment_v2(self, db: Session, tenant_id: int,
                            filter_groups: List[Dict], group_connector: str = "and",
                            page: int = 1, page_size: int = 50) -> Tuple[List[Contact], int]:
        """Evaluate segment with Phase 3 AND/OR rule groups.

        Each group has a connector (and/or) and a list of rules.
        Groups are connected by group_connector.
        """
        base_q = db.query(Contact).filter(
            Contact.tenant_id == tenant_id,
            Contact.deleted_at.is_(None),
        )

        group_conditions = []
        for group in filter_groups:
            connector = group.get("connector", "and")
            rules = group.get("rules", [])
            rule_conditions = []
            for rule in rules:
                cond = self._build_rule_condition(db, tenant_id, rule)
                if cond is not None:
                    rule_conditions.append(cond)
            if rule_conditions:
                if connector == "or":
                    group_conditions.append(or_(*rule_conditions))
                else:
                    group_conditions.append(and_(*rule_conditions))

        if group_conditions:
            if group_connector == "or":
                base_q = base_q.filter(or_(*group_conditions))
            else:
                base_q = base_q.filter(and_(*group_conditions))

        total = base_q.count()
        offset = (page - 1) * page_size
        contacts = base_q.order_by(Contact.created_at.desc()).offset(offset).limit(page_size).all()
        return contacts, total

    def _build_rule_condition(self, db: Session, tenant_id: int, rule: Dict):
        """Build a SQLAlchemy condition from a single segment rule."""
        field = rule.get("field", "")
        operator = rule.get("operator", "equals")
        value = rule.get("value")
        value2 = rule.get("value2")

        # Tag-based rules
        if field == "tag":
            tag_ids = db.query(ContactTag.id).filter(
                ContactTag.tenant_id == tenant_id,
                ContactTag.name == value,
            ).subquery()
            contact_ids_with_tag = db.query(ContactTagAssociation.contact_id).filter(
                ContactTagAssociation.tag_id.in_(tag_ids.select())
            ).distinct().subquery()
            if operator in ("equals", "in_list"):
                return Contact.id.in_(contact_ids_with_tag.select())
            elif operator in ("not_equals", "not_in_list"):
                return ~Contact.id.in_(contact_ids_with_tag.select())
            return None

        # Custom field rules (custom:slug)
        if field.startswith("custom:"):
            slug = field.split(":", 1)[1]
            defn = db.query(ContactCustomFieldDefinition).filter(
                ContactCustomFieldDefinition.tenant_id == tenant_id,
                ContactCustomFieldDefinition.field_slug == slug,
            ).first()
            if not defn:
                return None
            cfv_subq = db.query(ContactCustomFieldValue.contact_id).filter(
                ContactCustomFieldValue.field_definition_id == defn.id,
            )
            if operator == "equals":
                cfv_subq = cfv_subq.filter(ContactCustomFieldValue.value == str(value))
            elif operator == "not_equals":
                cfv_subq = cfv_subq.filter(ContactCustomFieldValue.value != str(value))
            elif operator == "contains":
                cfv_subq = cfv_subq.filter(ContactCustomFieldValue.value.ilike(f"%{value}%"))
            elif operator == "is_set":
                pass  # just check existence
            elif operator == "is_not_set":
                return ~Contact.id.in_(cfv_subq.subquery().select())
            return Contact.id.in_(cfv_subq.subquery().select())

        # Standard contact fields
        col = getattr(Contact, field, None)
        if col is None:
            return None

        if operator == "equals":
            return col == value
        elif operator == "not_equals":
            return col != value
        elif operator == "contains":
            return col.ilike(f"%{value}%")
        elif operator == "not_contains":
            return ~col.ilike(f"%{value}%")
        elif operator == "starts_with":
            return col.ilike(f"{value}%")
        elif operator == "ends_with":
            return col.ilike(f"%{value}")
        elif operator == "greater_than":
            return col > value
        elif operator == "less_than":
            return col < value
        elif operator == "greater_equal":
            return col >= value
        elif operator == "less_equal":
            return col <= value
        elif operator == "between":
            return and_(col >= value, col <= value2)
        elif operator == "is_set":
            return and_(col.isnot(None), col != "")
        elif operator == "is_not_set":
            return or_(col.is_(None), col == "")
        elif operator == "in_list":
            vals = value if isinstance(value, list) else [value]
            return col.in_(vals)
        elif operator == "not_in_list":
            vals = value if isinstance(value, list) else [value]
            return ~col.in_(vals)
        return None

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

    def get_import_log(self, db: Session, tenant_id: int, log_id: int) -> Optional[ContactImportLog]:
        """Get an import log by ID."""
        return db.query(ContactImportLog).filter(
            ContactImportLog.id == log_id,
            ContactImportLog.tenant_id == tenant_id,
        ).first()

    def list_import_logs(self, db: Session, tenant_id: int) -> List[ContactImportLog]:
        """List all import logs for a tenant."""
        return (
            db.query(ContactImportLog)
            .filter(ContactImportLog.tenant_id == tenant_id)
            .order_by(ContactImportLog.started_at.desc())
            .all()
        )

    # ── Custom Fields Extended ──────────────────────────────────────────

    def get_custom_field_definition(self, db: Session, tenant_id: int,
                                     field_id: int) -> Optional[ContactCustomFieldDefinition]:
        """Get a custom field definition by ID."""
        return db.query(ContactCustomFieldDefinition).filter(
            ContactCustomFieldDefinition.id == field_id,
            ContactCustomFieldDefinition.tenant_id == tenant_id,
        ).first()

    def get_custom_field_by_slug(self, db: Session, tenant_id: int,
                                  slug: str) -> Optional[ContactCustomFieldDefinition]:
        """Get a custom field definition by slug."""
        return db.query(ContactCustomFieldDefinition).filter(
            ContactCustomFieldDefinition.tenant_id == tenant_id,
            ContactCustomFieldDefinition.field_slug == slug,
        ).first()

    def update_custom_field_definition(self, db: Session,
                                        defn: ContactCustomFieldDefinition,
                                        **kwargs) -> ContactCustomFieldDefinition:
        """Update a custom field definition."""
        for key, value in kwargs.items():
            if hasattr(defn, key) and value is not None:
                setattr(defn, key, value)
        defn.updated_at = datetime.now(timezone.utc)
        db.flush()
        return defn

    def delete_custom_field_definition(self, db: Session, field_id: int,
                                        tenant_id: int) -> bool:
        """Delete a custom field definition and all its values."""
        db.query(ContactCustomFieldValue).filter(
            ContactCustomFieldValue.field_definition_id == field_id,
        ).delete(synchronize_session=False)
        count = db.query(ContactCustomFieldDefinition).filter(
            ContactCustomFieldDefinition.id == field_id,
            ContactCustomFieldDefinition.tenant_id == tenant_id,
        ).delete(synchronize_session=False)
        db.flush()
        return count > 0

    def get_custom_field_values_detailed(self, db: Session, contact_id: int) -> List[Dict[str, Any]]:
        """Get all custom field values for a contact with definition info."""
        values = (
            db.query(ContactCustomFieldValue, ContactCustomFieldDefinition)
            .join(ContactCustomFieldDefinition,
                  ContactCustomFieldValue.field_definition_id == ContactCustomFieldDefinition.id)
            .filter(ContactCustomFieldValue.contact_id == contact_id)
            .all()
        )
        result = []
        for val, defn in values:
            options = None
            if defn.options_json:
                try:
                    options = json.loads(defn.options_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append({
                "field_slug": defn.field_slug,
                "field_name": defn.field_name,
                "field_type": defn.field_type,
                "value": val.value,
                "options": options,
            })
        return result

    # ── Lifecycle Config ───────────────────────────────────────────────

    def get_lifecycle_config(self, db: Session, tenant_id: int) -> Optional[ContactLifecycleConfig]:
        """Get lifecycle configuration for a tenant."""
        return db.query(ContactLifecycleConfig).filter(
            ContactLifecycleConfig.tenant_id == tenant_id,
        ).first()

    def upsert_lifecycle_config(self, db: Session, tenant_id: int,
                                 stages_json: str, default_stage: str) -> ContactLifecycleConfig:
        """Create or update lifecycle configuration for a tenant."""
        existing = self.get_lifecycle_config(db, tenant_id)
        if existing:
            existing.stages_json = stages_json
            existing.default_stage = default_stage
            existing.updated_at = datetime.now(timezone.utc)
            db.flush()
            return existing
        config = ContactLifecycleConfig(
            tenant_id=tenant_id,
            stages_json=stages_json,
            default_stage=default_stage,
        )
        db.add(config)
        db.flush()
        return config


# Singleton instance
contact_repo = ContactRepository()
