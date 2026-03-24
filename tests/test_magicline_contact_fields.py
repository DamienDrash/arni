from __future__ import annotations

from uuid import uuid4

from app.contacts.repository import contact_repo
from app.contacts.sync_service import NormalizedContact, SyncResult, contact_sync_service
from app.core.contact_models import Contact
from app.core.db import SessionLocal
from app.integrations.magicline.contact_enrichment import enrich_contacts_for_tenant
from app.integrations.magicline.member_enrichment import ENRICHMENT_TTL_HOURS
from app.integrations.magicline.contact_fields import ensure_magicline_custom_field_definitions
from app.integrations.magicline.contact_sync import sync_contacts_from_magicline


def test_magicline_sync_persists_contract_custom_fields(monkeypatch):
    source_id = f"ml-sync-{uuid4()}"
    result = contact_sync_service.sync_contacts(
        tenant_id=1,
        source="magicline",
        contacts=[
            NormalizedContact(
                source_id=source_id,
                first_name="Magic",
                last_name="Member",
                email=f"{source_id}@example.com",
                lifecycle_stage="customer",
                custom_fields={
                    "vertrag": "Premium",
                    "vertrag_status": "ACTIVE",
                    "vertrag_start": "2026-01-01",
                    "vertrag_ende": "2026-12-31",
                    "vertrag_gekuendigt": False,
                },
                external_ids={"magicline": source_id},
            )
        ],
    )
    assert result.created == 1

    db = SessionLocal()
    try:
        contact = db.query(Contact).filter(Contact.source == "magicline", Contact.source_id == source_id).one()
        values = contact_repo.get_custom_field_values(db, contact.id)
        assert values["vertrag"] == "Premium"
        assert values["vertrag_status"] == "ACTIVE"
        assert values["vertrag_start"] == "2026-01-01"
        assert values["vertrag_ende"] == "2026-12-31"
        assert values["vertrag_gekuendigt"] == "false"
    finally:
        db.close()


def test_magicline_enrichment_persists_training_fields(monkeypatch):
    source_id = f"ml-enrich-{uuid4()}"
    contact_sync_service.sync_contacts(
        tenant_id=1,
        source="magicline",
        contacts=[
            NormalizedContact(
                source_id=source_id,
                first_name="Train",
                last_name="Profile",
                email=f"{source_id}@example.com",
                lifecycle_stage="customer",
                external_ids={"magicline": "777001"},
            )
        ],
    )

    async def _fake_enrich_single_contact(contact, tenant_id, force=False):
        return {
            "customer_id": 777001,
            "checkin_stats": {
                "total_30d": 7,
                "total_90d": 19,
                "last_visit": "2026-03-20",
                "preferred_training_days": ["Mon", "Wed"],
                "preferred_training_time": "evening",
                "preferred_training_sessions": ["Yoga", "Strength"],
                "next_appointment": {"start": "2026-03-28T18:00:00+00:00", "title": "Yoga"},
            },
            "bookings": {"upcoming": [{"start": "2026-03-28T18:00:00+00:00"}], "past": [{}]},
            "churn": {"risk": "medium", "score": 42},
        }

    monkeypatch.setattr(
        "app.integrations.magicline.contact_enrichment.enrich_single_contact",
        _fake_enrich_single_contact,
    )

    result = __import__("asyncio").run(enrich_contacts_for_tenant(tenant_id=1, force=True))
    assert result["enriched"] >= 1

    db = SessionLocal()
    try:
        contact = db.query(Contact).filter(Contact.source == "magicline", Contact.source_id == source_id).one()
        values = contact_repo.get_custom_field_values(db, contact.id)
        assert values["letzter_besuch"] == "2026-03-20"
        assert values["besuche_30d"] == "7"
        assert values["bevorzugte_trainingstage"] == "Mon, Wed"
        assert values["bevorzugte_tageszeit"] == "evening"
        assert values["bevorzugte_sessions"] == "Yoga, Strength"
        assert values["naechster_termin"] == "2026-03-28T18:00:00+00:00"
        assert values["churn_risk"] == "medium"
        assert values["churn_score"] == "42"
    finally:
        db.close()


def test_segment_evaluation_supports_magicline_custom_fields():
    source_id = f"ml-segment-{uuid4()}"
    contact_sync_service.sync_contacts(
        tenant_id=1,
        source="magicline",
        contacts=[
            NormalizedContact(
                source_id=source_id,
                first_name="Segment",
                last_name="Target",
                email=f"{source_id}@example.com",
                lifecycle_stage="customer",
                custom_fields={
                    "vertrag": "Premium",
                    "bevorzugte_tageszeit": "evening",
                    "churn_risk": "high",
                    "pausiert": True,
                },
                external_ids={"magicline": source_id},
            )
        ],
    )

    db = SessionLocal()
    try:
        ensure_magicline_custom_field_definitions(db, 1)
        contacts, total = contact_repo.evaluate_segment_v2(
            db,
            tenant_id=1,
            filter_groups=[
                {
                    "connector": "and",
                    "rules": [
                        {"field": "custom:vertrag", "operator": "equals", "value": "Premium"},
                        {"field": "custom:bevorzugte_tageszeit", "operator": "equals", "value": "evening"},
                        {"field": "custom:pausiert", "operator": "is_true"},
                    ],
                }
            ],
            group_connector="and",
            page=1,
            page_size=50,
        )
        assert total >= 1
        assert any(contact.source_id == source_id for contact in contacts)
    finally:
        db.close()


def test_magicline_sync_loads_member_prospect_and_former_member(monkeypatch):
    captured_contacts: list[NormalizedContact] = []
    original_sync_contacts = contact_sync_service.sync_contacts

    class _FakeClient:
        def customer_additional_info_fields(self):
            return []

        def customer_list(self, **kwargs):
            return {"result": [], "hasNext": False}

        def customer_contracts(self, customer_id: int, status: str | None = None):
            if customer_id == 1003 and status == "INACTIVE":
                return [{
                    "name": "Legacy Tarif",
                    "status": "INACTIVE",
                    "startDate": "2024-01-01",
                    "endDate": "2025-01-01",
                }]
            if customer_id == 1001 and status == "ACTIVE":
                return [{
                    "name": "Premium",
                    "status": "ACTIVE",
                    "startDate": "2026-01-01",
                    "endDate": "2026-12-31",
                }]
            return []

    def _fake_iter_pages(fetch_fn, **kwargs):
        status = kwargs.get("customer_status")
        if status == "MEMBER":
            return [{"id": 1001, "firstName": "Max", "lastName": "Member", "email": "max@example.com", "status": "MEMBER"}]
        if status == "PROSPECT":
            return [{"id": 1002, "firstName": "Petra", "lastName": "Prospect", "email": "petra@example.com", "status": "PROSPECT"}]
        if status == "FORMER_MEMBER":
            return [{"id": 1003, "firstName": "Franz", "lastName": "Former", "email": "franz@example.com", "status": "FORMER_MEMBER"}]
        return []

    def _fake_sync_contacts(**kwargs):
        captured_contacts.extend(kwargs["contacts"])
        result = SyncResult()
        result.fetched = len(kwargs["contacts"])
        return result

    monkeypatch.setattr("app.integrations.magicline.contact_sync.get_client", lambda tenant_id: _FakeClient())
    monkeypatch.setattr("app.integrations.magicline.contact_sync.MagiclineClient.iter_pages", _fake_iter_pages)
    monkeypatch.setattr("app.integrations.magicline.contact_sync.contact_sync_service.sync_contacts", _fake_sync_contacts)

    result = sync_contacts_from_magicline(tenant_id=1)
    assert result["fetched"] == 3

    lifecycle_by_status = {contact.custom_fields.get("magicline_status"): contact.lifecycle_stage for contact in captured_contacts}
    assert lifecycle_by_status == {
        "MEMBER": "customer",
        "PROSPECT": "lead",
        "FORMER_MEMBER": "churned",
    }

    former = next(contact for contact in captured_contacts if contact.custom_fields.get("magicline_status") == "FORMER_MEMBER")
    assert former.custom_fields["vertrag"] == "Legacy Tarif"
    assert former.custom_fields["vertrag_status"] == "INACTIVE"

    # Keep the original around so accidental service mutation does not leak across tests.
    assert original_sync_contacts is not None


def test_magicline_enrichment_runs_hourly():
    assert ENRICHMENT_TTL_HOURS == 1


def test_magicline_sync_tolerates_duplicate_phone_identifiers():
    source_a = f"ml-dup-a-{uuid4()}"
    source_b = f"ml-dup-b-{uuid4()}"

    result = contact_sync_service.sync_contacts(
        tenant_id=1,
        source="magicline",
        contacts=[
            NormalizedContact(
                source_id=source_a,
                first_name="Anna",
                last_name="Alpha",
                email=f"{source_a}@example.com",
                phone="015199900000",
                lifecycle_stage="lead",
                external_ids={"magicline": source_a},
            ),
            NormalizedContact(
                source_id=source_b,
                first_name="Berta",
                last_name="Beta",
                email=f"{source_b}@example.com",
                phone="015199900000",
                lifecycle_stage="lead",
                external_ids={"magicline": source_b},
            ),
        ],
    )

    assert result.errors == 0

    db = SessionLocal()
    try:
        contacts = (
            db.query(Contact)
            .filter(Contact.source == "magicline", Contact.source_id.in_([source_a, source_b]))
            .all()
        )
        assert len(contacts) == 2
    finally:
        db.close()


def test_contact_list_multiple_tags_require_all_tags():
    source_id = f"ml-tags-and-{uuid4()}"
    contact_sync_service.sync_contacts(
        tenant_id=1,
        source="magicline",
        contacts=[
            NormalizedContact(
                source_id=source_id,
                first_name="Tagged",
                last_name="Contact",
                email=f"{source_id}@example.com",
                lifecycle_stage="customer",
                tags=["magicline:member", "pausiert"],
                external_ids={"magicline": source_id},
            ),
            NormalizedContact(
                source_id=f"{source_id}-other",
                first_name="Only",
                last_name="Member",
                email=f"{source_id}-other@example.com",
                lifecycle_stage="customer",
                tags=["magicline:member"],
                external_ids={"magicline": f"{source_id}-other"},
            ),
        ],
    )

    db = SessionLocal()
    try:
        contacts, total = contact_repo.list_contacts(
            db,
            tenant_id=1,
            tags=["magicline:member", "pausiert"],
            page=1,
            page_size=50,
        )
        assert total >= 1
        assert any(contact.source_id == source_id for contact in contacts)
        assert all(contact.source_id != f"{source_id}-other" for contact in contacts)
    finally:
        db.close()
