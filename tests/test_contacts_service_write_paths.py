from __future__ import annotations

import csv
import io
from uuid import uuid4

from app.contacts.schemas import ContactCreate, ContactUpdate, ExportRequest
from app.contacts.service import contact_service
from app.core.contact_models import Contact
from app.core.models import Tenant
from app.core.db import SessionLocal


def _create_test_tenant() -> int:
    db = SessionLocal()
    try:
        token = uuid4().hex[:10]
        tenant = Tenant(
            slug=f"contacts-service-{token}",
            name=f"Contacts Service {token}",
            is_active=True,
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant.id
    finally:
        db.close()


def test_contact_service_create_update_and_soft_delete() -> None:
    token = uuid4().hex
    phone = f"0151{token[:8]}"
    created = contact_service.create_contact(
        tenant_id=1,
        data=ContactCreate(
            first_name="Write",
            last_name="Path",
            email=f"{token}@example.com",
            notes="initial note",
        ),
        performed_by=1,
        performed_by_name="Admin",
    )

    assert created.email == f"{token}@example.com"
    assert created.lifecycle_stage == "subscriber"

    updated = contact_service.update_contact(
        tenant_id=1,
        contact_id=created.id,
        data=ContactUpdate(phone=phone, lifecycle_stage="customer"),
        performed_by=1,
        performed_by_name="Admin",
    )

    assert updated is not None
    assert updated.phone == phone
    assert updated.lifecycle_stage == "customer"

    deleted = contact_service.delete_contacts(
        tenant_id=1,
        contact_ids=[created.id],
        permanent=False,
        performed_by=1,
        performed_by_name="Admin",
    )

    assert deleted == 1

    db = SessionLocal()
    try:
        contact = db.query(Contact).filter(Contact.id == created.id).one()
        assert contact.deleted_at is not None
    finally:
        db.close()


def test_contact_service_custom_field_tag_and_lifecycle_transition() -> None:
    token = uuid4().hex
    field_slug = f"plan_{token[:8]}"

    definition = contact_service.create_custom_field_definition(
        tenant_id=1,
        field_name="Plan",
        field_slug=field_slug,
        field_type="text",
        is_required=False,
        is_visible=True,
        display_order=0,
        description="Membership plan",
    )
    assert definition.field_slug == field_slug

    created = contact_service.create_contact(
        tenant_id=1,
        data=ContactCreate(
            first_name="Lifecycle",
            last_name="Flow",
            email=f"flow-{token}@example.com",
        ),
        performed_by=1,
        performed_by_name="Admin",
    )

    custom_value = contact_service.set_contact_custom_field(
        tenant_id=1,
        contact_id=created.id,
        field_slug=field_slug,
        value="Premium",
    )
    assert custom_value is not None
    assert custom_value.value == "Premium"

    tagged = contact_service.add_tag_to_contact(
        tenant_id=1,
        contact_id=created.id,
        tag_name=f"vip-{token[:6]}",
        performed_by=1,
        performed_by_name="Admin",
    )
    assert tagged is True

    transitioned = contact_service.transition_lifecycle(
        tenant_id=1,
        contact_id=created.id,
        new_stage="customer",
        reason="upgrade",
        performed_by=1,
        performed_by_name="Admin",
    )
    assert transitioned is not None
    assert transitioned.lifecycle_stage == "customer"

    custom_fields = contact_service.get_contact_custom_fields(tenant_id=1, contact_id=created.id)
    assert any(field.field_slug == field_slug and field.value == "Premium" for field in custom_fields)

    refreshed = contact_service.get_contact(tenant_id=1, contact_id=created.id)
    assert refreshed is not None
    assert any(tag.name == f"vip-{token[:6]}" for tag in refreshed.tags)


def test_contact_service_statistics_are_isolated_and_complete() -> None:
    tenant_id = _create_test_tenant()
    token = uuid4().hex

    first = contact_service.create_contact(
        tenant_id=tenant_id,
        data=ContactCreate(
            first_name="Stats",
            last_name="Alpha",
            email=f"alpha-{token}@example.com",
            source="manual",
        ),
        performed_by=1,
        performed_by_name="Admin",
    )
    second = contact_service.create_contact(
        tenant_id=tenant_id,
        data=ContactCreate(
            first_name="Stats",
            last_name="Beta",
            email=f"beta-{token}@example.com",
            phone=f"0170{token[:8]}",
            source="import",
            lifecycle_stage="lead",
        ),
        performed_by=1,
        performed_by_name="Admin",
    )

    contact_service.update_contact(
        tenant_id=tenant_id,
        contact_id=first.id,
        data=ContactUpdate(score=80),
        performed_by=1,
        performed_by_name="Admin",
    )
    contact_service.add_tag_to_contact(
        tenant_id=tenant_id,
        contact_id=first.id,
        tag_name=f"stats-{token[:6]}",
        performed_by=1,
        performed_by_name="Admin",
    )

    stats = contact_service.get_statistics(tenant_id)

    assert stats["total"] == 2
    assert stats["lifecycle_distribution"]["subscriber"] == 1
    assert stats["lifecycle_distribution"]["lead"] == 1
    assert stats["source_distribution"]["manual"] == 1
    assert stats["source_distribution"]["import"] == 1
    assert stats["with_email"] == 2
    assert stats["with_phone"] == 1
    assert stats["email_coverage"] == 100.0
    assert stats["phone_coverage"] == 50.0
    assert stats["average_score"] == 40.0
    assert stats["tag_count"] == 1
    assert stats["recent_activities_7d"] >= 4


def test_contact_service_export_includes_custom_fields_and_tags() -> None:
    tenant_id = _create_test_tenant()
    token = uuid4().hex
    field_slug = f"tier_{token[:8]}"
    tag_name = f"export-{token[:6]}"

    contact_service.create_custom_field_definition(
        tenant_id=tenant_id,
        field_name="Tier",
        field_slug=field_slug,
        field_type="text",
        is_required=False,
        is_visible=True,
        display_order=0,
        description="Export tier",
    )
    contact = contact_service.create_contact(
        tenant_id=tenant_id,
        data=ContactCreate(
            first_name="Export",
            last_name="Target",
            email=f"export-{token}@example.com",
        ),
        performed_by=1,
        performed_by_name="Admin",
    )
    contact_service.set_contact_custom_field(
        tenant_id=tenant_id,
        contact_id=contact.id,
        field_slug=field_slug,
        value="Gold",
    )
    contact_service.add_tag_to_contact(
        tenant_id=tenant_id,
        contact_id=contact.id,
        tag_name=tag_name,
        performed_by=1,
        performed_by_name="Admin",
    )

    csv_content = contact_service.export_contacts_v2(
        tenant_id,
        ExportRequest(
            contact_ids=[contact.id],
            fields=["first_name", "email"],
            include_custom_fields=True,
            include_tags=True,
        ),
    )

    rows = list(csv.DictReader(io.StringIO(csv_content)))

    assert len(rows) == 1
    assert rows[0]["first_name"] == "Export"
    assert rows[0]["email"] == f"export-{token}@example.com"
    assert rows[0][f"custom:{field_slug}"] == "Gold"
    assert rows[0]["tags"] == tag_name
