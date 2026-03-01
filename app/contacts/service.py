"""ARIIA v2.0 – Contact Service (Business Logic Layer).

@ARCH: Contacts Refactoring, Phase 1 – Service Layer
Encapsulates all business logic for the Contact module.
Orchestrates repository calls, validation, activity logging,
duplicate detection, and serialization.

Design Principles
-----------------
- Service methods handle transactions (commit/rollback)
- Business rules and validation live here, not in the router
- Activity logging for all state changes
- Returns Pydantic response models (not ORM objects)
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from app.contacts.repository import contact_repo
from app.contacts.schemas import (
    ActivityListResponse,
    ActivityResponse,
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
    CustomFieldDefinitionResponse,
    ImportLogResponse,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
    TagResponse,
)
from app.core.contact_models import (
    ActivityType,
    Contact,
    ContactActivity,
    ContactCustomFieldDefinition,
    ContactNote,
    ContactTag,
)
from app.core.db import SessionLocal

logger = structlog.get_logger()


class ContactService:
    """Service layer for Contact Management.

    Handles business logic, transaction management, and response serialization.
    All public methods open their own DB session (consistent with existing codebase).
    """

    # ── Serialization Helpers ─────────────────────────────────────────────

    def _serialize_contact(self, db: Session, contact: Contact) -> ContactResponse:
        """Convert a Contact ORM object to a ContactResponse."""
        # Get tags
        tags_orm = contact_repo.get_contact_tags(db, contact.id)
        tags = [
            TagResponse(
                id=t.id,
                name=t.name,
                color=t.color,
                description=t.description,
                contact_count=0,
            )
            for t in tags_orm
        ]

        # Get custom fields
        custom_fields = contact_repo.get_custom_field_values(db, contact.id)

        # Parse external_ids
        external_ids = None
        if contact.external_ids:
            try:
                external_ids = json.loads(contact.external_ids)
            except (json.JSONDecodeError, TypeError):
                external_ids = None

        return ContactResponse(
            id=contact.id,
            tenant_id=contact.tenant_id,
            first_name=contact.first_name,
            last_name=contact.last_name,
            full_name=contact.full_name,
            email=contact.email,
            phone=contact.phone,
            company=contact.company,
            job_title=contact.job_title,
            date_of_birth=contact.date_of_birth,
            gender=contact.gender,
            preferred_language=contact.preferred_language,
            avatar_url=contact.avatar_url,
            lifecycle_stage=contact.lifecycle_stage,
            source=contact.source,
            source_id=contact.source_id,
            consent_email=contact.consent_email,
            consent_sms=contact.consent_sms,
            consent_phone=contact.consent_phone,
            consent_whatsapp=contact.consent_whatsapp,
            gdpr_accepted_at=contact.gdpr_accepted_at,
            score=contact.score,
            external_ids=external_ids,
            tags=tags,
            custom_fields=custom_fields,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
            deleted_at=contact.deleted_at,
        )

    def _serialize_note(self, note: ContactNote) -> NoteResponse:
        """Convert a ContactNote ORM object to a NoteResponse."""
        return NoteResponse(
            id=note.id,
            contact_id=note.contact_id,
            content=note.content,
            is_pinned=note.is_pinned,
            created_by=note.created_by,
            created_by_name=note.created_by_name,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    def _serialize_activity(self, activity: ContactActivity) -> ActivityResponse:
        """Convert a ContactActivity ORM object to an ActivityResponse."""
        metadata = None
        if activity.metadata_json:
            try:
                metadata = json.loads(activity.metadata_json)
            except (json.JSONDecodeError, TypeError):
                metadata = None

        return ActivityResponse(
            id=activity.id,
            contact_id=activity.contact_id,
            activity_type=activity.activity_type,
            title=activity.title,
            description=activity.description,
            metadata=metadata,
            performed_by=activity.performed_by,
            performed_by_name=activity.performed_by_name,
            created_at=activity.created_at,
        )

    # ── Contact CRUD ──────────────────────────────────────────────────────

    def list_contacts(self, tenant_id: int, **kwargs) -> ContactListResponse:
        """List contacts with filtering, search, and pagination."""
        db = SessionLocal()
        try:
            contacts, total = contact_repo.list_contacts(db, tenant_id, **kwargs)
            page = kwargs.get("page", 1)
            page_size = kwargs.get("page_size", 50)
            total_pages = max(1, math.ceil(total / page_size))

            items = [self._serialize_contact(db, c) for c in contacts]

            return ContactListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )
        finally:
            db.close()

    def get_contact(self, tenant_id: int, contact_id: int) -> Optional[ContactResponse]:
        """Get a single contact by ID."""
        db = SessionLocal()
        try:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return None
            return self._serialize_contact(db, contact)
        finally:
            db.close()

    def create_contact(
        self,
        tenant_id: int,
        data: ContactCreate,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> ContactResponse:
        """Create a new contact with duplicate detection, tagging, and activity logging."""
        db = SessionLocal()
        try:
            # ── Duplicate Detection ───────────────────────────────────────
            if data.email:
                existing = contact_repo.find_by_email(db, tenant_id, data.email)
                if existing:
                    raise ValueError(f"Ein Kontakt mit der E-Mail {data.email} existiert bereits (ID: {existing.id}).")
            if data.phone:
                existing = contact_repo.find_by_phone(db, tenant_id, data.phone)
                if existing:
                    raise ValueError(f"Ein Kontakt mit der Telefonnummer {data.phone} existiert bereits (ID: {existing.id}).")

            # ── Create Contact ────────────────────────────────────────────
            contact_data = data.model_dump(exclude={"tags", "custom_fields", "notes"})
            contact = contact_repo.create(db, tenant_id, **contact_data)

            # ── Add Identifiers ───────────────────────────────────────────
            if data.email:
                contact_repo.add_identifier(db, contact.id, tenant_id, "email", data.email, is_primary=True)
            if data.phone:
                contact_repo.add_identifier(db, contact.id, tenant_id, "phone", data.phone, is_primary=True)

            # ── Add Tags ──────────────────────────────────────────────────
            if data.tags:
                for tag_name in data.tags:
                    tag = contact_repo.get_or_create_tag(db, tenant_id, tag_name)
                    contact_repo.add_tag_to_contact(db, contact.id, tag.id)

            # ── Set Custom Fields ─────────────────────────────────────────
            if data.custom_fields:
                defs = contact_repo.list_custom_field_definitions(db, tenant_id)
                slug_to_def = {d.field_slug: d for d in defs}
                for slug, value in data.custom_fields.items():
                    if slug in slug_to_def:
                        contact_repo.set_custom_field_value(
                            db, contact.id, slug_to_def[slug].id, str(value)
                        )

            # ── Add Initial Note ──────────────────────────────────────────
            if data.notes:
                contact_repo.add_note(
                    db, contact.id, tenant_id, data.notes,
                    created_by=performed_by, created_by_name=performed_by_name,
                )

            # ── Activity Log ──────────────────────────────────────────────
            contact_repo.add_activity(
                db, contact.id, tenant_id,
                activity_type=ActivityType.CREATED,
                title=f"Kontakt erstellt: {contact.full_name}",
                description=f"Quelle: {data.source or 'manual'}",
                performed_by=performed_by,
                performed_by_name=performed_by_name,
            )

            db.commit()

            logger.info(
                "contact.created",
                contact_id=contact.id,
                tenant_id=tenant_id,
                source=data.source,
            )

            return self._serialize_contact(db, contact)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def update_contact(
        self,
        tenant_id: int,
        contact_id: int,
        data: ContactUpdate,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> Optional[ContactResponse]:
        """Update an existing contact."""
        db = SessionLocal()
        try:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return None

            # ── Duplicate Check for email/phone changes ───────────────────
            update_data = data.model_dump(exclude_unset=True)
            if "email" in update_data and update_data["email"] != contact.email:
                existing = contact_repo.find_by_email(db, tenant_id, update_data["email"])
                if existing and existing.id != contact_id:
                    raise ValueError(f"E-Mail {update_data['email']} wird bereits von Kontakt ID {existing.id} verwendet.")
            if "phone" in update_data and update_data["phone"] != contact.phone:
                existing = contact_repo.find_by_phone(db, tenant_id, update_data["phone"])
                if existing and existing.id != contact_id:
                    raise ValueError(f"Telefonnummer {update_data['phone']} wird bereits von Kontakt ID {existing.id} verwendet.")

            # ── Track Changes for Activity Log ────────────────────────────
            changes = []
            for key, new_val in update_data.items():
                old_val = getattr(contact, key, None)
                if old_val != new_val:
                    changes.append(f"{key}: {old_val} → {new_val}")

            # ── Apply Update ──────────────────────────────────────────────
            contact = contact_repo.update(db, contact, **update_data)

            # ── Update Identifiers ────────────────────────────────────────
            if "email" in update_data:
                # Update or create email identifier
                contact_repo.add_identifier(db, contact.id, tenant_id, "email", update_data["email"], is_primary=True)
            if "phone" in update_data:
                contact_repo.add_identifier(db, contact.id, tenant_id, "phone", update_data["phone"], is_primary=True)

            # ── Activity Log ──────────────────────────────────────────────
            if changes:
                contact_repo.add_activity(
                    db, contact.id, tenant_id,
                    activity_type=ActivityType.UPDATED,
                    title=f"Kontakt aktualisiert: {contact.full_name}",
                    description="; ".join(changes),
                    performed_by=performed_by,
                    performed_by_name=performed_by_name,
                )

            db.commit()

            logger.info(
                "contact.updated",
                contact_id=contact.id,
                tenant_id=tenant_id,
                changes=len(changes),
            )

            return self._serialize_contact(db, contact)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_contacts(
        self,
        tenant_id: int,
        contact_ids: List[int],
        permanent: bool = False,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> int:
        """Delete one or more contacts (soft or hard delete)."""
        db = SessionLocal()
        try:
            if permanent:
                count = contact_repo.bulk_hard_delete(db, tenant_id, contact_ids)
            else:
                count = contact_repo.bulk_soft_delete(db, tenant_id, contact_ids)

            # Log activity for each deleted contact (soft-delete only)
            if not permanent:
                for cid in contact_ids:
                    contact_repo.add_activity(
                        db, cid, tenant_id,
                        activity_type=ActivityType.UPDATED,
                        title="Kontakt gelöscht (Soft-Delete)",
                        performed_by=performed_by,
                        performed_by_name=performed_by_name,
                    )

            db.commit()

            logger.info(
                "contact.deleted",
                tenant_id=tenant_id,
                count=count,
                permanent=permanent,
            )

            return count
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ── Notes ─────────────────────────────────────────────────────────────

    def add_note(
        self,
        tenant_id: int,
        contact_id: int,
        data: NoteCreate,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> Optional[NoteResponse]:
        """Add a note to a contact."""
        db = SessionLocal()
        try:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return None

            note = contact_repo.add_note(
                db, contact_id, tenant_id, data.content,
                is_pinned=data.is_pinned,
                created_by=performed_by,
                created_by_name=performed_by_name,
            )

            # Activity log
            contact_repo.add_activity(
                db, contact_id, tenant_id,
                activity_type=ActivityType.NOTE_ADDED,
                title="Notiz hinzugefügt",
                description=data.content[:200] if len(data.content) > 200 else data.content,
                performed_by=performed_by,
                performed_by_name=performed_by_name,
            )

            db.commit()
            return self._serialize_note(note)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_notes(self, tenant_id: int, contact_id: int) -> List[NoteResponse]:
        """List all notes for a contact."""
        db = SessionLocal()
        try:
            notes = contact_repo.list_notes(db, contact_id, tenant_id)
            return [self._serialize_note(n) for n in notes]
        finally:
            db.close()

    def update_note(self, tenant_id: int, note_id: int, data: NoteUpdate) -> Optional[NoteResponse]:
        """Update a note."""
        db = SessionLocal()
        try:
            update_data = data.model_dump(exclude_unset=True)
            note = contact_repo.update_note(db, note_id, tenant_id, **update_data)
            if not note:
                return None
            db.commit()
            return self._serialize_note(note)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_note(self, tenant_id: int, note_id: int) -> bool:
        """Delete a note."""
        db = SessionLocal()
        try:
            result = contact_repo.delete_note(db, note_id, tenant_id)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ── Activities / Timeline ─────────────────────────────────────────────

    def list_activities(
        self,
        tenant_id: int,
        contact_id: int,
        page: int = 1,
        page_size: int = 50,
        activity_type: Optional[str] = None,
    ) -> ActivityListResponse:
        """List activities for a contact."""
        db = SessionLocal()
        try:
            activities, total = contact_repo.list_activities(
                db, contact_id, tenant_id,
                page=page, page_size=page_size,
                activity_type=activity_type,
            )
            return ActivityListResponse(
                items=[self._serialize_activity(a) for a in activities],
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            db.close()

    # ── Tags ──────────────────────────────────────────────────────────────

    def list_tags(self, tenant_id: int) -> List[TagResponse]:
        """List all tags for a tenant."""
        db = SessionLocal()
        try:
            tags_data = contact_repo.list_tags(db, tenant_id)
            return [TagResponse(**t) for t in tags_data]
        finally:
            db.close()

    def create_tag(self, tenant_id: int, name: str, color: str = "#6C5CE7",
                   description: Optional[str] = None) -> TagResponse:
        """Create a new tag."""
        db = SessionLocal()
        try:
            tag = contact_repo.get_or_create_tag(db, tenant_id, name, color, description)
            db.commit()
            return TagResponse(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                description=tag.description,
                contact_count=0,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def add_tag_to_contact(
        self,
        tenant_id: int,
        contact_id: int,
        tag_name: str,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> bool:
        """Add a tag to a contact."""
        db = SessionLocal()
        try:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return False

            tag = contact_repo.get_or_create_tag(db, tenant_id, tag_name)
            contact_repo.add_tag_to_contact(db, contact_id, tag.id)

            contact_repo.add_activity(
                db, contact_id, tenant_id,
                activity_type=ActivityType.TAG_ADDED,
                title=f"Tag hinzugefügt: {tag_name}",
                performed_by=performed_by,
                performed_by_name=performed_by_name,
            )

            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def remove_tag_from_contact(
        self,
        tenant_id: int,
        contact_id: int,
        tag_name: str,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> bool:
        """Remove a tag from a contact."""
        db = SessionLocal()
        try:
            tag = db.query(ContactTag).filter(
                ContactTag.tenant_id == tenant_id,
                ContactTag.name == tag_name,
            ).first()
            if not tag:
                return False

            result = contact_repo.remove_tag_from_contact(db, contact_id, tag.id)

            if result:
                contact_repo.add_activity(
                    db, contact_id, tenant_id,
                    activity_type=ActivityType.TAG_REMOVED,
                    title=f"Tag entfernt: {tag_name}",
                    performed_by=performed_by,
                    performed_by_name=performed_by_name,
                )

            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ── Custom Fields ─────────────────────────────────────────────────────

    def list_custom_field_definitions(self, tenant_id: int) -> List[CustomFieldDefinitionResponse]:
        """List all custom field definitions for a tenant."""
        db = SessionLocal()
        try:
            defs = contact_repo.list_custom_field_definitions(db, tenant_id)
            result = []
            for d in defs:
                options = None
                if d.options_json:
                    try:
                        options = json.loads(d.options_json)
                    except (json.JSONDecodeError, TypeError):
                        options = None
                result.append(CustomFieldDefinitionResponse(
                    id=d.id,
                    field_name=d.field_name,
                    field_slug=d.field_slug,
                    field_type=d.field_type,
                    is_required=d.is_required,
                    is_visible=d.is_visible,
                    options=options,
                    display_order=d.display_order,
                    description=d.description,
                ))
            return result
        finally:
            db.close()

    def create_custom_field_definition(
        self, tenant_id: int, **kwargs
    ) -> CustomFieldDefinitionResponse:
        """Create a custom field definition."""
        db = SessionLocal()
        try:
            # Convert options list to JSON
            if "options" in kwargs and kwargs["options"]:
                kwargs["options_json"] = json.dumps(kwargs.pop("options"))
            else:
                kwargs.pop("options", None)

            cfd = contact_repo.create_custom_field_definition(db, tenant_id, **kwargs)
            db.commit()

            options = None
            if cfd.options_json:
                try:
                    options = json.loads(cfd.options_json)
                except (json.JSONDecodeError, TypeError):
                    options = None

            return CustomFieldDefinitionResponse(
                id=cfd.id,
                field_name=cfd.field_name,
                field_slug=cfd.field_slug,
                field_type=cfd.field_type,
                is_required=cfd.is_required,
                is_visible=cfd.is_visible,
                options=options,
                display_order=cfd.display_order,
                description=cfd.description,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ── Statistics ────────────────────────────────────────────────────────

    def get_statistics(self, tenant_id: int) -> Dict[str, Any]:
        """Get contact statistics for a tenant."""
        db = SessionLocal()
        try:
            from app.core.contact_models import Contact
            from sqlalchemy import func

            total = contact_repo.count(db, tenant_id)

            # Lifecycle distribution
            lifecycle_dist = (
                db.query(Contact.lifecycle_stage, func.count(Contact.id))
                .filter(Contact.tenant_id == tenant_id, Contact.deleted_at.is_(None))
                .group_by(Contact.lifecycle_stage)
                .all()
            )

            # Source distribution
            source_dist = (
                db.query(Contact.source, func.count(Contact.id))
                .filter(Contact.tenant_id == tenant_id, Contact.deleted_at.is_(None))
                .group_by(Contact.source)
                .all()
            )

            # Contacts with email/phone
            with_email = (
                db.query(func.count(Contact.id))
                .filter(
                    Contact.tenant_id == tenant_id,
                    Contact.deleted_at.is_(None),
                    Contact.email.isnot(None),
                    Contact.email != "",
                )
                .scalar() or 0
            )
            with_phone = (
                db.query(func.count(Contact.id))
                .filter(
                    Contact.tenant_id == tenant_id,
                    Contact.deleted_at.is_(None),
                    Contact.phone.isnot(None),
                    Contact.phone != "",
                )
                .scalar() or 0
            )

            return {
                "total": total,
                "lifecycle_distribution": {stage: count for stage, count in lifecycle_dist},
                "source_distribution": {src: count for src, count in source_dist},
                "with_email": with_email,
                "with_phone": with_phone,
                "email_coverage": round(with_email / total * 100, 1) if total > 0 else 0,
                "phone_coverage": round(with_phone / total * 100, 1) if total > 0 else 0,
            }
        finally:
            db.close()


# Singleton instance
contact_service = ContactService()
