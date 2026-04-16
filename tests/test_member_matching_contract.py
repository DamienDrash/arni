from __future__ import annotations

import time

from app.core.db import SessionLocal
from app.core.models import StudioMember, Tenant
from app.gateway.member_matching import match_member_by_phone


def test_member_matching_returns_single_exact_match() -> None:
    unique = int(time.time() * 1000)
    db = SessionLocal()
    try:
        tenant = Tenant(slug=f"member-match-{unique}", name=f"Member Match {unique}")
        db.add(tenant)
        db.flush()
        db.add(
            StudioMember(
                tenant_id=tenant.id,
                customer_id=1000 + unique,
                member_number=f"M-{unique}",
                first_name="Anna",
                last_name="Muster",
                phone_number="+49 171 1234567",
                email="anna@example.com",
            )
        )
        db.commit()
        tenant_id = tenant.id
    finally:
        db.close()

    result = match_member_by_phone("0171 1234567", tenant_id=tenant_id)
    assert result is not None
    assert result.first_name == "Anna"
    assert result.last_name == "Muster"


def test_member_matching_returns_none_for_ambiguous_match() -> None:
    unique = int(time.time() * 1000)
    db = SessionLocal()
    try:
        tenant = Tenant(slug=f"member-ambiguous-{unique}", name=f"Member Ambiguous {unique}")
        db.add(tenant)
        db.flush()
        db.add_all(
            [
                StudioMember(
                    tenant_id=tenant.id,
                    customer_id=2000 + unique,
                    member_number=f"A-{unique}",
                    first_name="Alex",
                    last_name="One",
                    phone_number="+49 171 9998888",
                ),
                StudioMember(
                    tenant_id=tenant.id,
                    customer_id=3000 + unique,
                    member_number=f"B-{unique}",
                    first_name="Alex",
                    last_name="Two",
                    phone_number="0171 9998888",
                ),
            ]
        )
        db.commit()
        tenant_id = tenant.id
    finally:
        db.close()

    assert match_member_by_phone("+49 171 9998888", tenant_id=tenant_id) is None


def test_member_matching_respects_tenant_scope() -> None:
    unique = int(time.time() * 1000)
    db = SessionLocal()
    try:
        tenant_a = Tenant(slug=f"member-a-{unique}", name="Tenant A")
        tenant_b = Tenant(slug=f"member-b-{unique}", name="Tenant B")
        db.add_all([tenant_a, tenant_b])
        db.flush()
        db.add_all(
            [
                StudioMember(
                    tenant_id=tenant_a.id,
                    customer_id=4000 + unique,
                    member_number=f"TA-{unique}",
                    first_name="Scoped",
                    last_name="A",
                    phone_number="+49 160 5554444",
                ),
                StudioMember(
                    tenant_id=tenant_b.id,
                    customer_id=5000 + unique,
                    member_number=f"TB-{unique}",
                    first_name="Scoped",
                    last_name="B",
                    phone_number="+49 160 5554444",
                ),
            ]
        )
        db.commit()
        tenant_a_id = tenant_a.id
        tenant_b_id = tenant_b.id
    finally:
        db.close()

    result_a = match_member_by_phone("0160 5554444", tenant_id=tenant_a_id)
    result_b = match_member_by_phone("0160 5554444", tenant_id=tenant_b_id)
    assert result_a is not None
    assert result_b is not None
    assert result_a.member_number != result_b.member_number
