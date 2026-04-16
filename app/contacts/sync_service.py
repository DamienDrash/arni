"""ARIIA v2.0 – Contact Sync Service.

@ARCH: Contacts Refactoring, Phase 3 – Integration Synchronisation
Universal sync service that bridges external data sources (Magicline,
Shopify, WooCommerce, HubSpot, etc.) with the new Contact model.

Replaces the legacy StudioMember-based sync with a clean, unified
approach that writes directly into the `contacts` table.

Design Principles
-----------------
- Source-aware upsert: Uses (tenant_id, source, source_id) as unique key
- Idempotent: Safe to run multiple times
- Activity logging: Records sync events in the contact timeline
- Preserves manual edits: Only updates fields that come from the source
- Supports both full-sync and incremental modes
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.contacts.repository import contact_repo
from app.core.contact_models import (
    ActivityType,
    Contact,
    ContactActivity,
    ContactIdentifier,
    ContactTag,
    ContactTagAssociation,
)
from app.integrations.magicline.contact_fields import set_magicline_custom_field_values
from app.shared.db import open_session

logger = structlog.get_logger()


class SyncResult:
    """Result of a sync operation."""

    def __init__(self):
        self.fetched: int = 0
        self.created: int = 0
        self.updated: int = 0
        self.unchanged: int = 0
        self.deleted: int = 0
        self.errors: int = 0
        self.error_details: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "deleted": self.deleted,
            "errors": self.errors,
            "error_details": self.error_details[:10],  # Limit to 10
        }


class NormalizedContact:
    """A normalized contact record from an external source.

    All integration adapters must convert their data into this format
    before passing it to the ContactSyncService.
    """

    def __init__(
        self,
        source_id: str,
        first_name: str,
        last_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
        date_of_birth: Optional[Any] = None,
        gender: Optional[str] = None,
        preferred_language: Optional[str] = None,
        lifecycle_stage: str = "subscriber",
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        external_ids: Optional[Dict[str, str]] = None,
        notes: Optional[str] = None,
        consent_email: bool = False,
        consent_sms: bool = False,
        consent_phone: bool = False,
        consent_whatsapp: bool = False,
    ):
        self.source_id = str(source_id)
        self.first_name = first_name or "Unbekannt"
        self.last_name = last_name or "Unbekannt"
        self.email = email.strip() if email else None
        self.phone = phone.strip() if phone else None
        self.company = company
        self.job_title = job_title
        self.date_of_birth = date_of_birth
        self.gender = gender
        self.preferred_language = preferred_language or "de"
        self.lifecycle_stage = lifecycle_stage
        self.tags = tags or []
        self.custom_fields = custom_fields or {}
        self.external_ids = external_ids or {}
        self.notes = notes
        self.consent_email = consent_email
        self.consent_sms = consent_sms
        self.consent_phone = consent_phone
        self.consent_whatsapp = consent_whatsapp


# Fields that are compared for change detection during sync
_SYNC_COMPARE_FIELDS = (
    "first_name", "last_name", "email", "phone", "company",
    "job_title", "gender", "preferred_language",
)


class ContactSyncService:
    """Universal sync service for external integrations.

    Handles the upsert logic for syncing contacts from any external
    source into the new Contact model.
    """

    def sync_contacts(
        self,
        tenant_id: int,
        source: str,
        contacts: List[NormalizedContact],
        *,
        full_sync: bool = True,
        delete_missing: bool = False,
        performed_by_name: str = "System Sync",
    ) -> SyncResult:
        """Sync a list of normalized contacts into the contacts table.

        Args:
            tenant_id: The tenant to sync into
            source: Integration source identifier (e.g., "magicline", "shopify")
            contacts: List of normalized contact records
            full_sync: If True, this represents a complete dataset from the source
            delete_missing: If True and full_sync, soft-delete contacts not in the incoming set
            performed_by_name: Name for activity logging

        Returns:
            SyncResult with counts of created, updated, deleted, etc.
        """
        result = SyncResult()
        result.fetched = len(contacts)

        db = open_session()
        try:
            # Build lookup of existing contacts from this source
            existing_contacts = (
                db.query(Contact)
                .filter(
                    Contact.tenant_id == tenant_id,
                    Contact.source == source,
                    Contact.deleted_at.is_(None),
                )
                .all()
            )
            existing_by_source_id: Dict[str, Contact] = {
                c.source_id: c for c in existing_contacts if c.source_id
            }
            # Also build email/phone lookups for cross-source dedup
            existing_by_email: Dict[str, Contact] = {}
            existing_by_phone: Dict[str, Contact] = {}
            all_contacts = (
                db.query(Contact)
                .filter(
                    Contact.tenant_id == tenant_id,
                    Contact.deleted_at.is_(None),
                )
                .all()
            )
            for c in all_contacts:
                if c.email:
                    existing_by_email[c.email.lower()] = c
                if c.phone:
                    existing_by_phone[c.phone] = c

            incoming_source_ids = set()

            for nc in contacts:
                try:
                    incoming_source_ids.add(nc.source_id)
                    self._upsert_contact(
                        db, tenant_id, source, nc,
                        existing_by_source_id, existing_by_email, existing_by_phone,
                        result, performed_by_name,
                    )
                except Exception as e:
                    result.errors += 1
                    result.error_details.append(
                        f"Fehler bei {nc.first_name} {nc.last_name} ({nc.source_id}): {str(e)}"
                    )
                    logger.error(
                        "contact_sync.upsert_error",
                        source=source,
                        source_id=nc.source_id,
                        error=str(e),
                    )

            # Handle deletions for full sync
            if full_sync and delete_missing:
                for source_id, contact in existing_by_source_id.items():
                    if source_id not in incoming_source_ids:
                        contact.deleted_at = datetime.now(timezone.utc)
                        db.add(ContactActivity(
                            contact_id=contact.id,
                            tenant_id=tenant_id,
                            activity_type=ActivityType.UPDATED,
                            title=f"Kontakt durch {source}-Sync entfernt (nicht mehr in Quelle)",
                            performed_by_name=performed_by_name,
                        ))
                        result.deleted += 1

            db.commit()

            logger.info(
                "contact_sync.completed",
                tenant_id=tenant_id,
                source=source,
                **result.to_dict(),
            )

            return result

        except Exception as e:
            db.rollback()
            logger.error("contact_sync.failed", tenant_id=tenant_id, source=source, error=str(e))
            raise
        finally:
            db.close()

    def _upsert_contact(
        self,
        db: Session,
        tenant_id: int,
        source: str,
        nc: NormalizedContact,
        existing_by_source_id: Dict[str, Contact],
        existing_by_email: Dict[str, Contact],
        existing_by_phone: Dict[str, Contact],
        result: SyncResult,
        performed_by_name: str,
    ) -> None:
        """Upsert a single contact from an external source."""

        # 1. Try to find by source_id (exact match from same source)
        contact = existing_by_source_id.get(nc.source_id)

        # 2. If not found, try cross-source dedup by email
        if not contact and nc.email:
            email_match = existing_by_email.get(nc.email.lower())
            if email_match and email_match.source != source:
                contact = email_match
                # Found by email – link to this source
                contact.source_id = nc.source_id
                if not contact.external_ids:
                    contact.external_ids = json.dumps({source: nc.source_id})
                else:
                    try:
                        ext = json.loads(contact.external_ids)
                        ext[source] = nc.source_id
                        contact.external_ids = json.dumps(ext)
                    except (json.JSONDecodeError, TypeError):
                        contact.external_ids = json.dumps({source: nc.source_id})

        # 3. If not found, try cross-source dedup by phone
        if not contact and nc.phone:
            phone_match = existing_by_phone.get(nc.phone)
            if phone_match and phone_match.source != source:
                contact = phone_match
                if not contact.external_ids:
                    contact.external_ids = json.dumps({source: nc.source_id})
                else:
                    try:
                        ext = json.loads(contact.external_ids)
                        ext[source] = nc.source_id
                        contact.external_ids = json.dumps(ext)
                    except (json.JSONDecodeError, TypeError):
                        contact.external_ids = json.dumps({source: nc.source_id})

        if contact:
            # ── Update existing contact ──────────────────────────────────
            changed = False
            for field in _SYNC_COMPARE_FIELDS:
                new_val = getattr(nc, field, None)
                if new_val is not None:
                    old_val = getattr(contact, field, None)
                    if old_val != new_val:
                        setattr(contact, field, new_val)
                        changed = True

            # Update date_of_birth if provided
            if nc.date_of_birth and contact.date_of_birth != nc.date_of_birth:
                contact.date_of_birth = nc.date_of_birth
                changed = True

            # Update external_ids
            ext_ids = {}
            if contact.external_ids:
                try:
                    ext_ids = json.loads(contact.external_ids)
                except (json.JSONDecodeError, TypeError):
                    ext_ids = {}
            if nc.external_ids:
                ext_ids.update(nc.external_ids)
            ext_ids[source] = nc.source_id
            new_ext = json.dumps(ext_ids, ensure_ascii=False)
            if contact.external_ids != new_ext:
                contact.external_ids = new_ext
                changed = True

            if changed:
                contact.updated_at = datetime.now(timezone.utc)
                result.updated += 1
            else:
                result.unchanged += 1

            # Update identifiers
            self._sync_identifiers(db, contact, tenant_id, nc)

            # Sync tags
            if nc.tags:
                self._sync_tags(db, contact, tenant_id, nc.tags)

            if source == "magicline" and nc.custom_fields:
                set_magicline_custom_field_values(db, tenant_id, contact.id, nc.custom_fields)

        else:
            # ── Create new contact ───────────────────────────────────────
            contact = Contact(
                tenant_id=tenant_id,
                first_name=nc.first_name,
                last_name=nc.last_name,
                email=nc.email,
                phone=nc.phone,
                company=nc.company,
                job_title=nc.job_title,
                date_of_birth=nc.date_of_birth,
                gender=nc.gender,
                preferred_language=nc.preferred_language,
                lifecycle_stage=nc.lifecycle_stage,
                source=source,
                source_id=nc.source_id,
                consent_email=nc.consent_email,
                consent_sms=nc.consent_sms,
                consent_phone=nc.consent_phone,
                consent_whatsapp=nc.consent_whatsapp,
                external_ids=json.dumps(
                    {source: nc.source_id, **nc.external_ids},
                    ensure_ascii=False,
                ),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(contact)
            db.flush()

            # Add identifiers
            self._sync_identifiers(db, contact, tenant_id, nc)

            # Add tags
            if nc.tags:
                self._sync_tags(db, contact, tenant_id, nc.tags)

            if source == "magicline" and nc.custom_fields:
                set_magicline_custom_field_values(db, tenant_id, contact.id, nc.custom_fields)

            # Add initial note
            if nc.notes:
                from app.core.contact_models import ContactNote
                db.add(ContactNote(
                    contact_id=contact.id,
                    tenant_id=tenant_id,
                    content=nc.notes,
                    created_by_name=f"{source} Sync",
                ))

            # Activity log
            db.add(ContactActivity(
                contact_id=contact.id,
                tenant_id=tenant_id,
                activity_type=ActivityType.IMPORT,
                title=f"Kontakt importiert von {source}",
                description=f"Source-ID: {nc.source_id}",
                performed_by_name=performed_by_name,
            ))

            # Update lookup maps for subsequent dedup
            existing_by_source_id = existing_by_source_id  # already passed by ref
            existing_by_source_id[nc.source_id] = contact
            if nc.email:
                existing_by_email = existing_by_email
                existing_by_email[nc.email.lower()] = contact
            if nc.phone:
                existing_by_phone = existing_by_phone
                existing_by_phone[nc.phone] = contact

            result.created += 1

    def _sync_identifiers(
        self, db: Session, contact: Contact, tenant_id: int, nc: NormalizedContact
    ) -> None:
        """Ensure email/phone identifiers exist for the contact."""
        existing_identifiers = (
            db.query(ContactIdentifier)
            .filter(ContactIdentifier.contact_id == contact.id)
            .all()
        )
        existing_values = {
            (i.identifier_type, i.identifier_value) for i in existing_identifiers
        }

        self._add_identifier_if_available(db, contact.id, tenant_id, "email", nc.email, existing_values)
        self._add_identifier_if_available(db, contact.id, tenant_id, "phone", nc.phone, existing_values)

    def _add_identifier_if_available(
        self,
        db: Session,
        contact_id: int,
        tenant_id: int,
        identifier_type: str,
        identifier_value: str | None,
        existing_values: set[tuple[str, str]],
    ) -> None:
        if not identifier_value or (identifier_type, identifier_value) in existing_values:
            return

        tenant_match = (
            db.query(ContactIdentifier)
            .filter(
                ContactIdentifier.tenant_id == tenant_id,
                ContactIdentifier.identifier_type == identifier_type,
                ContactIdentifier.identifier_value == identifier_value,
            )
            .first()
        )
        if tenant_match:
            if tenant_match.contact_id != contact_id:
                logger.warning(
                    "contact_sync.identifier_conflict",
                    tenant_id=tenant_id,
                    contact_id=contact_id,
                    existing_contact_id=tenant_match.contact_id,
                    identifier_type=identifier_type,
                    identifier_value=identifier_value,
                )
            return

        db.add(ContactIdentifier(
            contact_id=contact_id,
            tenant_id=tenant_id,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            is_primary=True,
        ))

    def _sync_tags(
        self, db: Session, contact: Contact, tenant_id: int, tag_names: List[str]
    ) -> None:
        """Ensure tags are associated with the contact."""
        for tag_name in tag_names:
            tag_name = str(tag_name).strip()
            if not tag_name:
                continue
            tag = contact_repo.get_or_create_tag(db, tenant_id, tag_name)
            # Check if association already exists
            existing = (
                db.query(ContactTagAssociation)
                .filter(
                    ContactTagAssociation.contact_id == contact.id,
                    ContactTagAssociation.tag_id == tag.id,
                )
                .first()
            )
            if not existing:
                db.add(ContactTagAssociation(
                    contact_id=contact.id,
                    tag_id=tag.id,
                ))


# Singleton instance
contact_sync_service = ContactSyncService()
