"""ARIIA v2.0 – Contact Service (Business Logic Layer).

@ARCH: Contacts Refactoring, Phase 2 – Service Layer (Extended)
Encapsulates all business logic for the Contact module.
Orchestrates repository calls, validation, activity logging,
duplicate detection, merge, bulk operations, and serialization.

Design Principles
-----------------
- Service methods handle transactions (commit/rollback)
- Business rules and validation live here, not in the router
- Activity logging for all state changes
- Returns Pydantic response models (not ORM objects)
"""

from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from app.contacts.repository import contact_repo
from app.contacts.schemas import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ContactBulkUpdateRequest,
    ContactBulkUpdateResponse,
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
    CustomFieldDefinitionResponse,
    CustomFieldDefinitionUpdate,
    CustomFieldValueResponse,
    DuplicateCheckResponse,
    DuplicateContactResponse,
    DuplicateGroupListResponse,
    DuplicateGroupResponse,
    ImportLogResponse,
    ImportPreviewResponse,
    ImportColumnMapping,
    LifecycleConfigResponse,
    LifecycleStageConfig,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
    SegmentCreate,
    SegmentFilterGroup,
    SegmentListResponse,
    SegmentPreviewResponse,
    SegmentResponse,
    SegmentUpdate,
    TagResponse,
)
from app.core.contact_models import (
    ActivityType,
    Contact,
    ContactActivity,
    ContactCustomFieldDefinition,
    ContactLifecycleConfig,
    ContactNote,
    ContactSegment,
)
from app.shared.db import open_session, session_scope, transaction_scope

logger = structlog.get_logger()


class ContactService:
    """Service layer for Contact Management.

    Handles business logic, transaction management, and response serialization.
    All public methods open their own DB session (consistent with existing codebase).
    """

    # ── Serialization Helpers ─────────────────────────────────────────────

    def _serialize_contact(self, db: Session, contact: Contact) -> ContactResponse:
        """Convert a Contact ORM object to a ContactResponse."""
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

        custom_fields = contact_repo.get_custom_field_values(db, contact.id)

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

    def _serialize_segment(self, db: Session, segment: ContactSegment,
                           tenant_id: int) -> SegmentResponse:
        """Convert a ContactSegment ORM object to a SegmentResponse."""
        filter_data = None
        if segment.filter_json:
            try:
                filter_data = json.loads(segment.filter_json) if isinstance(segment.filter_json, str) else segment.filter_json
            except (json.JSONDecodeError, TypeError):
                filter_data = None

        # Evaluate dynamic segment count
        contact_count = segment.contact_count
        if segment.is_dynamic and filter_data:
            try:
                _, count = contact_repo.evaluate_segment(db, tenant_id, filter_data)
                contact_count = count
            except Exception:
                pass

        # Parse filter_groups
        filter_groups = None
        if hasattr(segment, 'filter_groups_json') and segment.filter_groups_json:
            try:
                fg_raw = json.loads(segment.filter_groups_json) if isinstance(segment.filter_groups_json, str) else segment.filter_groups_json
                filter_groups = [SegmentFilterGroup(**g) for g in fg_raw]
            except Exception:
                filter_groups = None

        gc = getattr(segment, 'group_connector', 'and') or 'and'

        return SegmentResponse(
            id=segment.id,
            name=segment.name,
            description=segment.description,
            filter_json=filter_data,
            filter_groups=filter_groups,
            group_connector=gc,
            is_dynamic=segment.is_dynamic,
            contact_count=contact_count,
            is_active=segment.is_active,
            created_at=segment.created_at,
            updated_at=segment.updated_at,
        )

    # ── Contact CRUD ──────────────────────────────────────────────────────

    def list_contacts(self, tenant_id: int, **kwargs) -> ContactListResponse:
        """List contacts with filtering, search, and pagination."""
        with session_scope() as db:
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

    def get_contact(self, tenant_id: int, contact_id: int) -> Optional[ContactResponse]:
        """Get a single contact by ID."""
        with session_scope() as db:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return None
            return self._serialize_contact(db, contact)

    def create_contact(
        self,
        tenant_id: int,
        data: ContactCreate,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> ContactResponse:
        """Create a new contact with duplicate detection, tagging, and activity logging."""
        with transaction_scope() as db:
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

    def update_contact(
        self,
        tenant_id: int,
        contact_id: int,
        data: ContactUpdate,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> Optional[ContactResponse]:
        """Update an existing contact."""
        with transaction_scope() as db:
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

            # ── Lifecycle Change Detection ────────────────────────────────
            lifecycle_changed = False
            old_lifecycle = contact.lifecycle_stage
            if "lifecycle_stage" in update_data and update_data["lifecycle_stage"] != old_lifecycle:
                lifecycle_changed = True

            # ── Apply Update ──────────────────────────────────────────────
            contact = contact_repo.update(db, contact, **update_data)

            # ── Update Identifiers ────────────────────────────────────────
            if "email" in update_data:
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

            # ── Lifecycle Change Activity ─────────────────────────────────
            if lifecycle_changed:
                contact_repo.add_activity(
                    db, contact.id, tenant_id,
                    activity_type=ActivityType.LIFECYCLE_CHANGE,
                    title=f"Lifecycle geändert: {old_lifecycle} → {update_data['lifecycle_stage']}",
                    metadata_json=json.dumps({
                        "old_stage": old_lifecycle,
                        "new_stage": update_data["lifecycle_stage"],
                    }),
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

    def delete_contacts(
        self,
        tenant_id: int,
        contact_ids: List[int],
        permanent: bool = False,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> int:
        """Delete one or more contacts (soft or hard delete)."""
        with transaction_scope() as db:
            if permanent:
                count = contact_repo.bulk_hard_delete(db, tenant_id, contact_ids)
            else:
                count = contact_repo.bulk_soft_delete(db, tenant_id, contact_ids)

            if not permanent:
                for cid in contact_ids:
                    try:
                        contact_repo.add_activity(
                            db, cid, tenant_id,
                            activity_type=ActivityType.UPDATED,
                            title="Kontakt gelöscht (Soft-Delete)",
                            performed_by=performed_by,
                            performed_by_name=performed_by_name,
                        )
                    except Exception:
                        pass  # Activity logging should not block deletion

            db.commit()

            logger.info(
                "contact.deleted",
                tenant_id=tenant_id,
                count=count,
                permanent=permanent,
            )

            return count

    # ── Bulk Operations ──────────────────────────────────────────────────

    def bulk_update_contacts(
        self,
        tenant_id: int,
        data: ContactBulkUpdateRequest,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> ContactBulkUpdateResponse:
        """Bulk update multiple contacts (lifecycle, tags, consent)."""
        with transaction_scope() as db:
            updated = 0
            tags_added = 0
            tags_removed = 0

            # ── Field updates (lifecycle, source, consent) ────────────────
            field_updates = {}
            if data.lifecycle_stage:
                field_updates["lifecycle_stage"] = data.lifecycle_stage
            if data.source:
                field_updates["source"] = data.source
            if data.consent_email is not None:
                field_updates["consent_email"] = data.consent_email
            if data.consent_sms is not None:
                field_updates["consent_sms"] = data.consent_sms
            if data.consent_phone is not None:
                field_updates["consent_phone"] = data.consent_phone
            if data.consent_whatsapp is not None:
                field_updates["consent_whatsapp"] = data.consent_whatsapp

            if field_updates:
                updated = contact_repo.bulk_update(db, tenant_id, data.ids, **field_updates)

            # ── Tag operations ────────────────────────────────────────────
            if data.add_tags:
                for tag_name in data.add_tags:
                    tags_added += contact_repo.bulk_add_tag(db, tenant_id, data.ids, tag_name)

            if data.remove_tags:
                for tag_name in data.remove_tags:
                    tags_removed += contact_repo.bulk_remove_tag(db, tenant_id, data.ids, tag_name)

            # ── Activity Log ──────────────────────────────────────────────
            desc_parts = []
            if field_updates:
                desc_parts.append(f"Felder: {', '.join(field_updates.keys())}")
            if data.add_tags:
                desc_parts.append(f"Tags hinzugefügt: {', '.join(data.add_tags)}")
            if data.remove_tags:
                desc_parts.append(f"Tags entfernt: {', '.join(data.remove_tags)}")

            for cid in data.ids:
                try:
                    contact_repo.add_activity(
                        db, cid, tenant_id,
                        activity_type=ActivityType.UPDATED,
                        title=f"Bulk-Update ({len(data.ids)} Kontakte)",
                        description="; ".join(desc_parts),
                        performed_by=performed_by,
                        performed_by_name=performed_by_name,
                    )
                except Exception:
                    pass

            db.commit()

            logger.info(
                "contact.bulk_updated",
                tenant_id=tenant_id,
                count=len(data.ids),
                updated=updated,
                tags_added=tags_added,
                tags_removed=tags_removed,
            )

            return ContactBulkUpdateResponse(
                updated=updated or len(data.ids),
                tags_added=tags_added,
                tags_removed=tags_removed,
            )

    # ── Duplicate Detection & Merge ──────────────────────────────────────

    def check_duplicates(
        self,
        tenant_id: int,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        exclude_id: Optional[int] = None,
    ) -> DuplicateCheckResponse:
        """Check for potential duplicates before creating/updating a contact."""
        with session_scope() as db:
            dupes = contact_repo.find_duplicates(
                db, tenant_id,
                email=email, phone=phone,
                first_name=first_name, last_name=last_name,
                exclude_id=exclude_id,
            )

            duplicates = [
                DuplicateContactResponse(
                    contact=self._serialize_contact(db, contact),
                    match_reason=reason,
                    confidence=conf,
                )
                for contact, reason, conf in dupes
            ]

            return DuplicateCheckResponse(
                has_duplicates=len(duplicates) > 0,
                duplicates=duplicates,
            )

    def list_duplicate_groups(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> DuplicateGroupListResponse:
        """List all groups of potential duplicates."""
        with session_scope() as db:
            groups, total = contact_repo.find_all_duplicate_groups(
                db, tenant_id, page=page, page_size=page_size,
            )

            serialized_groups = []
            for g in groups:
                serialized_groups.append(DuplicateGroupResponse(
                    match_type=g["match_type"],
                    match_value=g["match_value"],
                    confidence=g["confidence"],
                    contacts=[self._serialize_contact(db, c) for c in g["contacts"]],
                ))

            return DuplicateGroupListResponse(
                groups=serialized_groups,
                total_groups=total,
                page=page,
                page_size=page_size,
            )

    def merge_contacts(
        self,
        tenant_id: int,
        primary_id: int,
        secondary_id: int,
        fields_from_secondary: Optional[List[str]] = None,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> Optional[ContactResponse]:
        """Merge two contacts into one."""
        with transaction_scope() as db:
            primary = contact_repo.merge_contacts(
                db, tenant_id, primary_id, secondary_id,
                fields_from_secondary=fields_from_secondary,
            )
            if not primary:
                return None

            # Activity log for merge
            contact_repo.add_activity(
                db, primary_id, tenant_id,
                activity_type=ActivityType.MERGE,
                title=f"Kontakt zusammengeführt mit ID {secondary_id}",
                description=f"Felder übernommen: {', '.join(fields_from_secondary or ['keine'])}",
                metadata_json=json.dumps({
                    "merged_from": secondary_id,
                    "fields_from_secondary": fields_from_secondary or [],
                }),
                performed_by=performed_by,
                performed_by_name=performed_by_name,
            )

            db.commit()

            logger.info(
                "contact.merged",
                tenant_id=tenant_id,
                primary_id=primary_id,
                secondary_id=secondary_id,
            )

            return self._serialize_contact(db, primary)

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
        with transaction_scope() as db:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return None

            note = contact_repo.add_note(
                db, contact_id, tenant_id, data.content,
                is_pinned=data.is_pinned,
                created_by=performed_by,
                created_by_name=performed_by_name,
            )

            contact_repo.add_activity(
                db, contact_id, tenant_id,
                activity_type=ActivityType.NOTE_ADDED,
                title="Notiz hinzugefügt",
                description=data.content[:200] if len(data.content) > 200 else data.content,
                performed_by=performed_by,
                performed_by_name=performed_by_name,
            )

            return self._serialize_note(note)

    def list_notes(self, tenant_id: int, contact_id: int) -> List[NoteResponse]:
        """List all notes for a contact."""
        with session_scope() as db:
            notes = contact_repo.list_notes(db, contact_id, tenant_id)
            return [self._serialize_note(n) for n in notes]

    def update_note(self, tenant_id: int, note_id: int, data: NoteUpdate) -> Optional[NoteResponse]:
        """Update a note."""
        with transaction_scope() as db:
            update_data = data.model_dump(exclude_unset=True)
            note = contact_repo.update_note(db, note_id, tenant_id, **update_data)
            if not note:
                return None
            return self._serialize_note(note)

    def delete_note(self, tenant_id: int, note_id: int) -> bool:
        """Delete a note."""
        with transaction_scope() as db:
            result = contact_repo.delete_note(db, note_id, tenant_id)
            return result

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
        with session_scope() as db:
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

    def add_activity(
        self,
        tenant_id: int,
        contact_id: int,
        data: ActivityCreate,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> Optional[ActivityResponse]:
        """Manually add an activity to a contact's timeline."""
        with transaction_scope() as db:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return None

            metadata_json = None
            if data.metadata:
                metadata_json = json.dumps(data.metadata)

            activity = contact_repo.add_activity(
                db, contact_id, tenant_id,
                activity_type=data.activity_type,
                title=data.title,
                description=data.description,
                metadata_json=metadata_json,
                performed_by=performed_by,
                performed_by_name=performed_by_name,
            )

            return self._serialize_activity(activity)

    # ── Tags ──────────────────────────────────────────────────────────────

    def list_tags(self, tenant_id: int) -> List[TagResponse]:
        """List all tags for a tenant."""
        with session_scope() as db:
            tags_data = contact_repo.list_tags(db, tenant_id)
            return [TagResponse(**t) for t in tags_data]

    def create_tag(self, tenant_id: int, name: str, color: str = "#6C5CE7",
                   description: Optional[str] = None) -> TagResponse:
        """Create a new tag."""
        with transaction_scope() as db:
            tag = contact_repo.get_or_create_tag(db, tenant_id, name, color, description)
            return TagResponse(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                description=tag.description,
                contact_count=0,
            )

    def update_tag(self, tenant_id: int, tag_id: int,
                   name: Optional[str] = None,
                   color: Optional[str] = None,
                   description: Optional[str] = None) -> Optional[TagResponse]:
        """Update a tag."""
        with transaction_scope() as db:
            tag = contact_repo.get_tag_by_id(db, tenant_id, tag_id)
            if not tag:
                return None

            update_kwargs = {}
            if name is not None:
                update_kwargs["name"] = name
            if color is not None:
                update_kwargs["color"] = color
            if description is not None:
                update_kwargs["description"] = description

            tag = contact_repo.update_tag(db, tag, **update_kwargs)
            count = contact_repo.count_tag_contacts(db, tag.id)

            return TagResponse(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                description=tag.description,
                contact_count=count,
            )

    def delete_tag(self, tenant_id: int, tag_id: int) -> bool:
        """Delete a tag and all its associations."""
        with transaction_scope() as db:
            result = contact_repo.delete_tag(db, tag_id, tenant_id)
            return result

    def add_tag_to_contact(
        self,
        tenant_id: int,
        contact_id: int,
        tag_name: str,
        color: str = "#6C5CE7",
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> bool:
        """Add a tag to a contact."""
        with transaction_scope() as db:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return False

            tag = contact_repo.get_or_create_tag(db, tenant_id, tag_name, color)
            contact_repo.add_tag_to_contact(db, contact_id, tag.id)

            contact_repo.add_activity(
                db, contact_id, tenant_id,
                activity_type=ActivityType.TAG_ADDED,
                title=f"Tag hinzugefügt: {tag_name}",
                performed_by=performed_by,
                performed_by_name=performed_by_name,
            )

            return True

    def remove_tag_from_contact(
        self,
        tenant_id: int,
        contact_id: int,
        tag_name: str,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> bool:
        """Remove a tag from a contact."""
        with transaction_scope() as db:
            tag = contact_repo.get_tag_by_name(db, tenant_id, tag_name)
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

            return result

    # ── Segments ─────────────────────────────────────────────────────────

    def create_segment(
        self,
        tenant_id: int,
        data: SegmentCreate,
    ) -> SegmentResponse:
        """Create a new contact segment (supports legacy and V2 rule groups)."""
        with transaction_scope() as db:
            kwargs = dict(
                name=data.name,
                description=data.description,
                filter_json=data.filter_json,
                is_dynamic=data.is_dynamic,
            )
            # Phase 3: filter_groups support
            if data.filter_groups:
                kwargs['filter_groups_json'] = json.dumps([g.model_dump() for g in data.filter_groups])
                kwargs['group_connector'] = data.group_connector

            segment = contact_repo.create_segment(db, tenant_id, **kwargs)

            # Evaluate initial count
            if data.filter_groups and data.is_dynamic:
                fg = [g.model_dump() for g in data.filter_groups]
                _, count = contact_repo.evaluate_segment_v2(db, tenant_id, fg, data.group_connector, page_size=10000)
                segment.contact_count = count
                db.flush()
            elif data.filter_json and data.is_dynamic:
                _, count = contact_repo.evaluate_segment(db, tenant_id, data.filter_json)
                segment.contact_count = count
                db.flush()

            return self._serialize_segment(db, segment, tenant_id)

    def list_segments(self, tenant_id: int) -> SegmentListResponse:
        """List all segments for a tenant."""
        with session_scope() as db:
            segments = contact_repo.list_segments(db, tenant_id)
            items = [self._serialize_segment(db, s, tenant_id) for s in segments]
            return SegmentListResponse(items=items, total=len(items))

    def get_segment(self, tenant_id: int, segment_id: int) -> Optional[SegmentResponse]:
        """Get a segment by ID."""
        with session_scope() as db:
            segment = contact_repo.get_segment_by_id(db, tenant_id, segment_id)
            if not segment:
                return None
            return self._serialize_segment(db, segment, tenant_id)

    def update_segment(
        self,
        tenant_id: int,
        segment_id: int,
        data: SegmentUpdate,
    ) -> Optional[SegmentResponse]:
        """Update a segment (supports legacy and V2 rule groups)."""
        with transaction_scope() as db:
            segment = contact_repo.get_segment_by_id(db, tenant_id, segment_id)
            if not segment:
                return None

            update_data = data.model_dump(exclude_unset=True)

            # Phase 3: filter_groups support
            if 'filter_groups' in update_data and update_data['filter_groups']:
                update_data['filter_groups_json'] = json.dumps(update_data.pop('filter_groups'))
            else:
                update_data.pop('filter_groups', None)

            segment = contact_repo.update_segment(db, segment, **update_data)

            # Re-evaluate count
            if segment.filter_groups_json:
                fg = json.loads(segment.filter_groups_json)
                gc = segment.group_connector or 'and'
                _, count = contact_repo.evaluate_segment_v2(db, tenant_id, fg, gc, page_size=10000)
                segment.contact_count = count
                db.flush()
            elif 'filter_json' in update_data and update_data.get('filter_json'):
                _, count = contact_repo.evaluate_segment(db, tenant_id, update_data['filter_json'])
                segment.contact_count = count
                db.flush()

            return self._serialize_segment(db, segment, tenant_id)

    def delete_segment(self, tenant_id: int, segment_id: int) -> bool:
        """Delete a segment."""
        with transaction_scope() as db:
            result = contact_repo.delete_segment(db, segment_id, tenant_id)
            return result

    def evaluate_segment(
        self,
        tenant_id: int,
        segment_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Optional[ContactListResponse]:
        """Evaluate a segment and return matching contacts (supports V2 rule groups)."""
        with transaction_scope() as db:
            segment = contact_repo.get_segment_by_id(db, tenant_id, segment_id)
            if not segment:
                return None

            # Phase 3: Use filter_groups if available
            if segment.filter_groups_json:
                fg = json.loads(segment.filter_groups_json) if isinstance(segment.filter_groups_json, str) else segment.filter_groups_json
                gc = segment.group_connector or 'and'
                contacts, total = contact_repo.evaluate_segment_v2(db, tenant_id, fg, gc, page, page_size)
            elif segment.filter_json:
                filter_data = json.loads(segment.filter_json) if isinstance(segment.filter_json, str) else segment.filter_json
                contacts, total = contact_repo.evaluate_segment(db, tenant_id, filter_data)
            else:
                return None

            items = [self._serialize_contact(db, c) for c in contacts]

            segment.contact_count = total
            db.flush()
            db.commit()

            total_pages = math.ceil(total / page_size) if page_size > 0 else 1
            return ContactListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )

    def preview_segment(
        self,
        tenant_id: int,
        filter_groups: List[SegmentFilterGroup],
        group_connector: str = "and",
    ) -> SegmentPreviewResponse:
        """Preview segment evaluation without saving (count + sample)."""
        with session_scope() as db:
            fg = [g.model_dump() for g in filter_groups]
            contacts, total = contact_repo.evaluate_segment_v2(db, tenant_id, fg, group_connector, page=1, page_size=5)
            sample = [self._serialize_contact(db, c) for c in contacts]
            return SegmentPreviewResponse(contact_count=total, sample_contacts=sample)

    # ── Custom Fields ─────────────────────────────────────────────────────

    def list_custom_field_definitions(self, tenant_id: int) -> List[CustomFieldDefinitionResponse]:
        """List all custom field definitions for a tenant."""
        with session_scope() as db:
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

    def create_custom_field_definition(
        self, tenant_id: int, **kwargs
    ) -> CustomFieldDefinitionResponse:
        """Create a custom field definition."""
        with transaction_scope() as db:
            if "options" in kwargs and kwargs["options"]:
                kwargs["options_json"] = json.dumps(kwargs.pop("options"))
            else:
                kwargs.pop("options", None)

            cfd = contact_repo.create_custom_field_definition(db, tenant_id, **kwargs)

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

    # ── Custom Fields Extended ───────────────────────────────────────────

    def update_custom_field_definition(
        self, tenant_id: int, field_id: int, data: CustomFieldDefinitionUpdate
    ) -> Optional[CustomFieldDefinitionResponse]:
        """Update a custom field definition."""
        with transaction_scope() as db:
            defn = contact_repo.get_custom_field_definition(db, tenant_id, field_id)
            if not defn:
                return None
            update_data = data.model_dump(exclude_unset=True)
            if 'options' in update_data and update_data['options'] is not None:
                update_data['options_json'] = json.dumps(update_data.pop('options'))
            else:
                update_data.pop('options', None)
            defn = contact_repo.update_custom_field_definition(db, defn, **update_data)
            db.commit()
            options = None
            if defn.options_json:
                try:
                    options = json.loads(defn.options_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            return CustomFieldDefinitionResponse(
                id=defn.id, field_name=defn.field_name, field_slug=defn.field_slug,
                field_type=defn.field_type, is_required=defn.is_required,
                is_visible=defn.is_visible, options=options,
                display_order=defn.display_order, description=defn.description,
            )

    def delete_custom_field_definition(self, tenant_id: int, field_id: int) -> bool:
        """Delete a custom field definition and all its values."""
        with transaction_scope() as db:
            result = contact_repo.delete_custom_field_definition(db, field_id, tenant_id)
            return result

    def set_contact_custom_field(
        self, tenant_id: int, contact_id: int, field_slug: str, value: Optional[str]
    ) -> Optional[CustomFieldValueResponse]:
        """Set a custom field value on a contact."""
        with transaction_scope() as db:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return None
            defn = contact_repo.get_custom_field_by_slug(db, tenant_id, field_slug)
            if not defn:
                return None
            contact_repo.set_custom_field_value(db, contact_id, defn.id, value or '')
            options = None
            if defn.options_json:
                try:
                    options = json.loads(defn.options_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            return CustomFieldValueResponse(
                field_slug=defn.field_slug, field_name=defn.field_name,
                field_type=defn.field_type, value=value, options=options,
            )

    def get_contact_custom_fields(
        self, tenant_id: int, contact_id: int
    ) -> List[CustomFieldValueResponse]:
        """Get all custom field values for a contact."""
        with session_scope() as db:
            contact = contact_repo.get_by_id(db, tenant_id, contact_id)
            if not contact:
                return []
            details = contact_repo.get_custom_field_values_detailed(db, contact_id)
            return [CustomFieldValueResponse(**d) for d in details]

    # ── Lifecycle Config ───────────────────────────────────────────────

    DEFAULT_LIFECYCLE_STAGES = [
        {'key': 'subscriber', 'label': 'Subscriber', 'color': '#74B9FF', 'order': 1, 'is_active': True},
        {'key': 'lead', 'label': 'Lead', 'color': '#FDCB6E', 'order': 2, 'is_active': True},
        {'key': 'opportunity', 'label': 'Opportunity', 'color': '#E17055', 'order': 3, 'is_active': True},
        {'key': 'customer', 'label': 'Kunde', 'color': '#00B894', 'order': 4, 'is_active': True},
        {'key': 'churned', 'label': 'Abgewandert', 'color': '#636E72', 'order': 5, 'is_active': True},
        {'key': 'other', 'label': 'Sonstige', 'color': '#B2BEC3', 'order': 6, 'is_active': True},
    ]

    def get_lifecycle_config(self, tenant_id: int) -> LifecycleConfigResponse:
        """Get lifecycle configuration for a tenant (returns defaults if not configured)."""
        with session_scope() as db:
            config = contact_repo.get_lifecycle_config(db, tenant_id)
            if config:
                stages_raw = json.loads(config.stages_json) if isinstance(config.stages_json, str) else config.stages_json
                stages = [LifecycleStageConfig(**s) for s in stages_raw]
                return LifecycleConfigResponse(
                    tenant_id=tenant_id, stages=stages, default_stage=config.default_stage,
                )
            return LifecycleConfigResponse(
                tenant_id=tenant_id,
                stages=[LifecycleStageConfig(**s) for s in self.DEFAULT_LIFECYCLE_STAGES],
                default_stage='subscriber',
            )

    def update_lifecycle_config(
        self, tenant_id: int, stages: List[LifecycleStageConfig], default_stage: str
    ) -> LifecycleConfigResponse:
        """Create or update lifecycle configuration for a tenant."""
        with transaction_scope() as db:
            stages_json = json.dumps([s.model_dump() for s in stages])
            config = contact_repo.upsert_lifecycle_config(db, tenant_id, stages_json, default_stage)
            return LifecycleConfigResponse(
                tenant_id=tenant_id, stages=stages, default_stage=default_stage,
            )

    # ── Import V2 ─────────────────────────────────────────────────────

    CONTACT_FIELD_MAP = {
        'first_name': 'first_name', 'vorname': 'first_name', 'firstname': 'first_name',
        'last_name': 'last_name', 'nachname': 'last_name', 'lastname': 'last_name', 'name': 'last_name',
        'email': 'email', 'e-mail': 'email', 'mail': 'email', 'email_address': 'email',
        'phone': 'phone', 'telefon': 'phone', 'phone_number': 'phone', 'tel': 'phone',
        'company': 'company', 'firma': 'company', 'unternehmen': 'company', 'organization': 'company',
        'job_title': 'job_title', 'position': 'job_title', 'titel': 'job_title', 'title': 'job_title',
        'gender': 'gender', 'geschlecht': 'gender',
        'date_of_birth': 'date_of_birth', 'geburtsdatum': 'date_of_birth', 'birthday': 'date_of_birth',
        'lifecycle_stage': 'lifecycle_stage', 'status': 'lifecycle_stage',
        'source': 'source', 'quelle': 'source',
    }

    def preview_import(
        self, tenant_id: int, csv_content: str, filename: str
    ) -> ImportPreviewResponse:
        """Preview CSV import: detect columns, suggest mappings, return sample rows."""
        import csv as csv_module
        import io
        reader = csv_module.DictReader(io.StringIO(csv_content))
        columns = reader.fieldnames or []
        rows = list(reader)

        # Auto-suggest mappings
        suggested = []
        for col in columns:
            col_lower = col.strip().lower().replace(' ', '_')
            mapped_field = self.CONTACT_FIELD_MAP.get(col_lower, '')
            suggested.append(ImportColumnMapping(
                csv_column=col,
                contact_field=mapped_field or f'custom:{col_lower}',
                is_mapped=bool(mapped_field),
            ))

        sample = rows[:10]
        warnings = []
        if not any(m.contact_field in ('first_name', 'last_name') for m in suggested if m.is_mapped):
            warnings.append('Keine Spalte f\u00fcr Vor- oder Nachname erkannt.')

        return ImportPreviewResponse(
            filename=filename,
            total_rows=len(rows),
            columns=columns,
            sample_rows=[dict(r) for r in sample],
            suggested_mappings=suggested,
            warnings=warnings,
        )

    def list_import_logs(self, tenant_id: int) -> List[ImportLogResponse]:
        """List all import logs for a tenant."""
        with session_scope() as db:
            logs = contact_repo.list_import_logs(db, tenant_id)
            return [
                ImportLogResponse(
                    id=l.id, source=l.source, status=l.status,
                    filename=l.filename, total_rows=l.total_rows,
                    imported=l.imported, updated=l.updated,
                    skipped=l.skipped, errors=l.errors,
                    started_at=l.started_at, completed_at=l.completed_at,
                ) for l in logs
            ]

    def get_import_progress(self, tenant_id: int, import_id: int) -> Optional[Dict[str, Any]]:
        """Get progress of a running import."""
        with session_scope() as db:
            log = contact_repo.get_import_log(db, tenant_id, import_id)
            if not log:
                return None
            processed = log.imported + log.updated + log.skipped + log.errors
            progress = round(processed / log.total_rows * 100, 1) if log.total_rows > 0 else 0
            error_details = []
            if log.error_log:
                try:
                    error_details = json.loads(log.error_log)
                except (json.JSONDecodeError, TypeError):
                    error_details = [log.error_log]
            return {
                'import_id': log.id, 'status': log.status,
                'total_rows': log.total_rows, 'processed': processed,
                'imported': log.imported, 'updated': log.updated,
                'skipped': log.skipped, 'errors': log.errors,
                'progress_percent': progress, 'error_details': error_details,
            }

    # ── Statistics ────────────────────────────────────────────────────────

    def get_statistics(self, tenant_id: int) -> Dict[str, Any]:
        """Get contact statistics for a tenant."""
        with session_scope() as db:
            stats = contact_repo.get_statistics_snapshot(db, tenant_id)
            total = stats["total"]
            return {
                **stats,
                "email_coverage": round(stats["with_email"] / total * 100, 1) if total > 0 else 0,
                "phone_coverage": round(stats["with_phone"] / total * 100, 1) if total > 0 else 0,
            }


    # ── Import V2 Execute (Phase 3) ──────────────────────────────────────

    def execute_import_v2(
        self,
        tenant_id: int,
        request,  # ImportV2Request
        performed_by: int,
        performed_by_name: str,
    ) -> None:
        """Execute Import V2 with column mapping in background."""
        db = open_session()
        try:
            log = contact_repo.create_import_log(db, tenant_id, "csv_v2", request.filename)
            db.commit()

            # Read cached CSV content from /tmp
            import os
            csv_path = f"/tmp/import_{tenant_id}_{request.filename}"
            if not os.path.exists(csv_path):
                log.status = "failed"
                log.error_log = "CSV-Datei nicht gefunden. Bitte erneut hochladen."
                log.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            with open(csv_path, "r", encoding="utf-8") as f:
                csv_content = f.read()

            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)
            log.total_rows = len(rows)

            # Build mapping dict: csv_column -> contact_field
            field_map = {}
            for m in request.mappings:
                if m.is_mapped:
                    field_map[m.csv_column] = m.contact_field

            imported = 0
            updated = 0
            skipped = 0
            errors = 0
            error_details = []

            for i, row in enumerate(rows):
                try:
                    mapped = {}
                    custom_fields = {}
                    for csv_col, contact_field in field_map.items():
                        val = row.get(csv_col, "").strip()
                        if not val:
                            continue
                        if contact_field.startswith("custom:"):
                            custom_fields[contact_field[7:]] = val
                        else:
                            mapped[contact_field] = val

                    first_name = mapped.get("first_name", "")
                    last_name = mapped.get("last_name", "")
                    email = mapped.get("email", "")

                    if not first_name and not last_name:
                        skipped += 1
                        continue

                    # Check for duplicates
                    existing = None
                    if email and request.skip_duplicates:
                        existing = contact_repo.find_by_email(db, tenant_id, email)

                    if existing and request.update_existing:
                        for field, val in mapped.items():
                            if field not in ("first_name", "last_name", "email") or val:
                                setattr(existing, field, val)
                        existing.updated_at = datetime.now(timezone.utc)
                        updated += 1
                    elif existing:
                        skipped += 1
                        continue
                    else:
                        contact = Contact(
                            tenant_id=tenant_id,
                            first_name=first_name or "Unbekannt",
                            last_name=last_name or "Unbekannt",
                            email=email or None,
                            phone=mapped.get("phone"),
                            company=mapped.get("company"),
                            job_title=mapped.get("job_title"),
                            source=request.default_source,
                            lifecycle_stage=mapped.get("lifecycle_stage", request.default_lifecycle),
                            gender=mapped.get("gender"),
                        )
                        db.add(contact)
                        db.flush()

                        # Set custom fields
                        for slug, val in custom_fields.items():
                            contact_repo.set_custom_field_value(
                                db, contact.id, tenant_id, slug, val
                            )

                        imported += 1

                    if (i + 1) % 100 == 0:
                        db.commit()

                except Exception as row_err:
                    errors += 1
                    error_details.append(f"Zeile {i + 1}: {str(row_err)}")

            db.commit()

            log.imported = imported
            log.updated = updated
            log.skipped = skipped
            log.errors = errors
            log.error_log = json.dumps(error_details) if error_details else None
            log.status = "completed"
            log.completed_at = datetime.now(timezone.utc)
            db.commit()

            # Cleanup temp file
            try:
                os.remove(csv_path)
            except Exception:
                pass

            logger.info(
                "contact.import_v2_completed",
                tenant_id=tenant_id,
                imported=imported,
                updated=updated,
                errors=errors,
            )

        except Exception as e:
            log.status = "failed"
            log.error_log = str(e)
            log.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.error("contact.import_v2_failed", tenant_id=tenant_id, error=str(e))
        finally:
            db.close()

    # ── Export V2 (Phase 3) ──────────────────────────────────────────────

    def export_contacts_v2(
        self,
        tenant_id: int,
        export_request,  # ExportRequest
    ) -> str:
        """Export contacts with filters, segment, and custom fields."""
        with session_scope() as db:
            contacts = contact_repo.list_contacts_for_export(
                db,
                tenant_id,
                contact_ids=export_request.contact_ids,
                segment_id=export_request.segment_id,
            )

            # Determine fields to export
            default_fields = [
                "id", "first_name", "last_name", "email", "phone",
                "company", "job_title", "lifecycle_stage", "source",
                "gender", "preferred_language", "score",
                "consent_email", "consent_sms", "consent_phone", "consent_whatsapp",
                "created_at",
            ]
            fields = export_request.fields or default_fields

            output = io.StringIO()
            writer = csv.writer(output)

            # Add custom field headers
            custom_field_slugs = []
            if export_request.include_custom_fields:
                defs = contact_repo.list_custom_field_definitions(db, tenant_id)
                custom_field_slugs = [d.field_slug for d in defs]
                fields = fields + [f"custom:{s}" for s in custom_field_slugs]

            if export_request.include_tags:
                fields = fields + ["tags"]

            writer.writerow(fields)

            for c in contacts:
                row = []
                for f in fields:
                    if f.startswith("custom:"):
                        slug = f[7:]
                        cf_vals = contact_repo.get_custom_field_values(db, c.id)
                        row.append(cf_vals.get(slug, ""))
                    elif f == "tags":
                        tags = contact_repo.get_contact_tags(db, c.id)
                        row.append(", ".join(t.name for t in tags))
                    elif f == "created_at":
                        row.append(c.created_at.isoformat() if c.created_at else "")
                    else:
                        row.append(getattr(c, f, ""))
                writer.writerow(row)

            output.seek(0)
            return output.getvalue()

    # ── Import Log Detail (Phase 3) ──────────────────────────────────────

    def get_import_log(
        self, tenant_id: int, log_id: int
    ) -> Optional[ImportLogResponse]:
        """Get a specific import log by ID."""
        with session_scope() as db:
            log = contact_repo.get_import_log(db, tenant_id, log_id)
            if not log:
                return None
            return ImportLogResponse(
                id=log.id,
                source=log.source,
                status=log.status,
                filename=log.filename,
                total_rows=log.total_rows or 0,
                imported=log.imported or 0,
                updated=log.updated or 0,
                skipped=log.skipped or 0,
                errors=log.errors or 0,
                started_at=log.started_at,
                completed_at=log.completed_at,
            )

    # ── Custom Field Values on Contact (Phase 3) ─────────────────────────

    def set_contact_custom_fields(
        self,
        tenant_id: int,
        contact_id: int,
        field_values: list,  # List[CustomFieldValueSet]
        performed_by: int,
        performed_by_name: str,
    ) -> bool:
        """Set multiple custom field values on a contact."""
        try:
            with transaction_scope() as db:
                contact = contact_repo.get_by_id(db, tenant_id, contact_id)
                if not contact:
                    return False

                for fv in field_values:
                    contact_repo.set_custom_field_value(
                        db, contact_id, tenant_id, fv.field_slug, fv.value
                    )

                contact_repo.add_activity(
                    db, contact_id, tenant_id,
                    activity_type="updated",
                    title="Custom Fields aktualisiert",
                    description=f"{len(field_values)} Felder aktualisiert",
                    performed_by=performed_by,
                    performed_by_name=performed_by_name,
                )

                return True
        except Exception as e:
            logger.error("contact.set_custom_fields_failed", error=str(e))
            return False

    # ── Lifecycle Transition (Phase 3) ────────────────────────────────────

    def transition_lifecycle(
        self,
        tenant_id: int,
        contact_id: int,
        new_stage: str,
        reason: Optional[str] = None,
        performed_by: Optional[int] = None,
        performed_by_name: Optional[str] = None,
    ) -> Optional[ContactResponse]:
        """Transition a contact's lifecycle stage with audit trail."""
        try:
            with transaction_scope() as db:
                contact = contact_repo.get_by_id(db, tenant_id, contact_id)
                if not contact:
                    return None

                old_stage = contact.lifecycle_stage
                contact.lifecycle_stage = new_stage
                contact.updated_at = datetime.now(timezone.utc)

                # Log the transition as an activity
                description = f"Lifecycle: {old_stage} → {new_stage}"
                if reason:
                    description += f" (Grund: {reason})"

                contact_repo.add_activity(
                    db, contact_id, tenant_id,
                    activity_type="lifecycle_change",
                    title=f"Lifecycle-Übergang: {new_stage}",
                    description=description,
                    metadata_json=json.dumps(
                        {"old_stage": old_stage, "new_stage": new_stage, "reason": reason}
                    ),
                    performed_by=performed_by,
                    performed_by_name=performed_by_name,
                )

                db.refresh(contact)
                return self._serialize_contact(db, contact)
        except Exception as e:
            logger.error("contact.lifecycle_transition_failed", error=str(e))
            return None


# Singleton instance
contact_service = ContactService()
