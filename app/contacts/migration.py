"""ARIIA v2.0 – Data Migration: StudioMember → Contact.

@ARCH: Contacts Refactoring, Phase 1 – Migration Script (M1.5)
Migrates data from the legacy `studio_members` table to the new
normalized `contacts` data model.

Features
--------
- Idempotent: Can be run multiple times safely (uses legacy_member_id)
- Batch processing: Processes in configurable batch sizes
- Tag migration: Converts JSON tags to normalized tag associations
- Custom field migration: Maps MemberCustomColumn → ContactCustomFieldDefinition
- Activity logging: Creates initial activity for each migrated contact
- Identifier creation: Creates email/phone identifiers for identity resolution
- Notes migration: Preserves existing notes
- Progress reporting: Logs progress every N records

Usage
-----
    python -m app.contacts.migration [--batch-size 500] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import MemberCustomColumn, StudioMember
from app.core.contact_models import (
    ActivityType,
    Contact,
    ContactActivity,
    ContactCustomFieldDefinition,
    ContactCustomFieldValue,
    ContactIdentifier,
    ContactNote,
    ContactTag,
    ContactTagAssociation,
)

logger = structlog.get_logger()


class MemberToContactMigration:
    """Handles migration from StudioMember to Contact."""

    def __init__(self, batch_size: int = 500, dry_run: bool = False):
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.stats = {
            "total_members": 0,
            "migrated": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "tags_created": 0,
            "notes_migrated": 0,
            "custom_fields_migrated": 0,
            "identifiers_created": 0,
        }

    def run(self) -> Dict[str, Any]:
        """Execute the full migration."""
        db = SessionLocal()
        try:
            logger.info("migration.started", dry_run=self.dry_run, batch_size=self.batch_size)

            # Step 1: Migrate custom column definitions
            self._migrate_custom_field_definitions(db)

            # Step 2: Count total members
            self.stats["total_members"] = db.query(func.count(StudioMember.id)).scalar() or 0
            logger.info("migration.total_members", count=self.stats["total_members"])

            # Step 3: Process members in batches
            offset = 0
            while True:
                members = (
                    db.query(StudioMember)
                    .order_by(StudioMember.id)
                    .offset(offset)
                    .limit(self.batch_size)
                    .all()
                )

                if not members:
                    break

                for member in members:
                    try:
                        self._migrate_member(db, member)
                    except Exception as e:
                        self.stats["errors"] += 1
                        logger.error(
                            "migration.member_error",
                            member_id=member.id,
                            error=str(e),
                        )

                if not self.dry_run:
                    db.commit()

                offset += self.batch_size
                logger.info(
                    "migration.batch_complete",
                    processed=offset,
                    total=self.stats["total_members"],
                    progress=f"{min(offset, self.stats['total_members'])}/{self.stats['total_members']}",
                )

            if not self.dry_run:
                db.commit()

            logger.info("migration.completed", stats=self.stats)
            return self.stats

        except Exception as e:
            db.rollback()
            logger.error("migration.failed", error=str(e))
            raise
        finally:
            db.close()

    def _migrate_member(self, db: Session, member: StudioMember) -> None:
        """Migrate a single StudioMember to Contact."""
        # Check if already migrated
        existing = (
            db.query(Contact)
            .filter(
                Contact.tenant_id == member.tenant_id,
                Contact.legacy_member_id == member.id,
            )
            .first()
        )

        if existing:
            # Update existing contact with latest data
            self._update_existing_contact(db, existing, member)
            self.stats["updated"] += 1
            return

        # ── Create new Contact ────────────────────────────────────────────
        lifecycle_stage = self._determine_lifecycle_stage(member)

        contact = Contact(
            tenant_id=member.tenant_id,
            first_name=member.first_name or "Unbekannt",
            last_name=member.last_name or "Unbekannt",
            email=member.email,
            phone=member.phone_number,
            date_of_birth=member.date_of_birth,
            gender=self._normalize_gender(member.gender),
            preferred_language=member.preferred_language or "de",
            lifecycle_stage=lifecycle_stage,
            source=member.source or "manual",
            source_id=member.source_id,
            legacy_member_id=member.id,
            external_ids=json.dumps({"customer_id": str(member.customer_id)}) if member.customer_id else None,
            created_at=member.created_at or datetime.now(timezone.utc),
            updated_at=member.updated_at or datetime.now(timezone.utc),
        )

        if self.dry_run:
            self.stats["migrated"] += 1
            return

        db.add(contact)
        db.flush()

        # ── Create Identifiers ────────────────────────────────────────────
        if member.email:
            db.add(ContactIdentifier(
                contact_id=contact.id,
                tenant_id=member.tenant_id,
                identifier_type="email",
                identifier_value=member.email,
                is_primary=True,
            ))
            self.stats["identifiers_created"] += 1

        if member.phone_number:
            db.add(ContactIdentifier(
                contact_id=contact.id,
                tenant_id=member.tenant_id,
                identifier_type="phone",
                identifier_value=member.phone_number,
                is_primary=True,
            ))
            self.stats["identifiers_created"] += 1

        if member.member_number:
            db.add(ContactIdentifier(
                contact_id=contact.id,
                tenant_id=member.tenant_id,
                identifier_type="member_number",
                identifier_value=member.member_number,
            ))
            self.stats["identifiers_created"] += 1

        # ── Migrate Tags ─────────────────────────────────────────────────
        if member.tags:
            try:
                tag_list = json.loads(member.tags)
                if isinstance(tag_list, list):
                    for tag_name in tag_list:
                        tag_name = str(tag_name).strip()
                        if not tag_name:
                            continue
                        tag = self._get_or_create_tag(db, member.tenant_id, tag_name)
                        db.add(ContactTagAssociation(
                            contact_id=contact.id,
                            tag_id=tag.id,
                        ))
            except (json.JSONDecodeError, TypeError):
                pass

        # ── Migrate Custom Fields ─────────────────────────────────────────
        if member.custom_fields:
            try:
                custom_data = json.loads(member.custom_fields)
                if isinstance(custom_data, dict):
                    for slug, value in custom_data.items():
                        defn = (
                            db.query(ContactCustomFieldDefinition)
                            .filter(
                                ContactCustomFieldDefinition.tenant_id == member.tenant_id,
                                ContactCustomFieldDefinition.field_slug == slug,
                            )
                            .first()
                        )
                        if defn:
                            db.add(ContactCustomFieldValue(
                                contact_id=contact.id,
                                field_definition_id=defn.id,
                                value=str(value),
                            ))
                            self.stats["custom_fields_migrated"] += 1
            except (json.JSONDecodeError, TypeError):
                pass

        # ── Migrate Notes ─────────────────────────────────────────────────
        if member.notes:
            db.add(ContactNote(
                contact_id=contact.id,
                tenant_id=member.tenant_id,
                content=member.notes,
                created_by_name="Migration",
            ))
            self.stats["notes_migrated"] += 1

        # ── Create Migration Activity ─────────────────────────────────────
        metadata = {}
        if member.contract_info:
            try:
                metadata["contract_info"] = json.loads(member.contract_info)
            except (json.JSONDecodeError, TypeError):
                pass
        if member.checkin_stats:
            try:
                metadata["checkin_stats"] = json.loads(member.checkin_stats)
            except (json.JSONDecodeError, TypeError):
                pass
        if member.additional_info:
            try:
                metadata["additional_info"] = json.loads(member.additional_info)
            except (json.JSONDecodeError, TypeError):
                pass

        db.add(ContactActivity(
            contact_id=contact.id,
            tenant_id=member.tenant_id,
            activity_type=ActivityType.CREATED,
            title=f"Kontakt migriert von StudioMember #{member.id}",
            description=f"Quelle: {member.source or 'manual'}, Customer-ID: {member.customer_id}",
            metadata_json=json.dumps(metadata) if metadata else None,
            performed_by_name="Migration",
        ))

        self.stats["migrated"] += 1

    def _update_existing_contact(self, db: Session, contact: Contact, member: StudioMember) -> None:
        """Update an existing contact with latest data from StudioMember."""
        if member.first_name:
            contact.first_name = member.first_name
        if member.last_name:
            contact.last_name = member.last_name
        if member.email:
            contact.email = member.email
        if member.phone_number:
            contact.phone = member.phone_number
        if member.date_of_birth:
            contact.date_of_birth = member.date_of_birth
        if member.gender:
            contact.gender = self._normalize_gender(member.gender)
        contact.updated_at = datetime.now(timezone.utc)

    def _migrate_custom_field_definitions(self, db: Session) -> None:
        """Migrate MemberCustomColumn definitions to ContactCustomFieldDefinition."""
        columns = db.query(MemberCustomColumn).all()
        for col in columns:
            existing = (
                db.query(ContactCustomFieldDefinition)
                .filter(
                    ContactCustomFieldDefinition.tenant_id == col.tenant_id,
                    ContactCustomFieldDefinition.field_slug == col.slug,
                )
                .first()
            )
            if not existing and not self.dry_run:
                db.add(ContactCustomFieldDefinition(
                    tenant_id=col.tenant_id,
                    field_name=col.name,
                    field_slug=col.slug,
                    field_type=col.field_type,
                    is_visible=col.is_visible,
                    options_json=col.options,
                    display_order=col.position,
                ))
                logger.info("migration.custom_field_def_created", slug=col.slug, tenant_id=col.tenant_id)

        if not self.dry_run:
            db.commit()

    def _determine_lifecycle_stage(self, member: StudioMember) -> str:
        """Determine lifecycle stage from member data."""
        if member.contract_info:
            try:
                info = json.loads(member.contract_info)
                status = info.get("status", "").upper()
                if status == "ACTIVE":
                    return "customer"
                elif status in ("CANCELLED", "EXPIRED"):
                    return "churned"
            except (json.JSONDecodeError, TypeError):
                pass

        if member.is_paused:
            return "customer"

        if member.source == "magicline" and member.source_id:
            return "customer"

        return "subscriber"

    def _normalize_gender(self, gender: Optional[str]) -> Optional[str]:
        """Normalize gender values from legacy format."""
        if not gender:
            return None
        gender_upper = gender.upper()
        mapping = {
            "MALE": "male",
            "FEMALE": "female",
            "DIVERSE": "diverse",
            "M": "male",
            "F": "female",
            "D": "diverse",
        }
        return mapping.get(gender_upper, gender.lower())

    def _get_or_create_tag(self, db: Session, tenant_id: int, name: str) -> ContactTag:
        """Get or create a tag."""
        tag = db.query(ContactTag).filter(
            ContactTag.tenant_id == tenant_id,
            ContactTag.name == name,
        ).first()
        if not tag:
            tag = ContactTag(tenant_id=tenant_id, name=name)
            db.add(tag)
            db.flush()
            self.stats["tags_created"] += 1
        return tag


def main():
    """CLI entry point for migration."""
    parser = argparse.ArgumentParser(description="Migrate StudioMember → Contact")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for processing")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing")
    args = parser.parse_args()

    migration = MemberToContactMigration(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    stats = migration.run()

    print("\n=== Migration Complete ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
