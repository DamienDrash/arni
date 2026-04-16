from __future__ import annotations

import csv
import io
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.core.db import SessionLocal
from app.core.models import MemberCustomColumn, StudioMember


def _tenant_admin_headers() -> dict[str, str]:
    token = create_access_token(
        user_id=2,
        email="tenantadmin@test.local",
        tenant_id=1,
        tenant_slug="default",
        role="tenant_admin",
    )
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    return f"members-crud-{int(time.time() * 1000)}@example.com"


@pytest.fixture
async def tenant_admin_client() -> AsyncClient:
    from app.edge.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=_tenant_admin_headers(),
    ) as client:
        yield client


def _cleanup_member(email: str) -> None:
    db = SessionLocal()
    try:
        db.query(StudioMember).filter(
            StudioMember.tenant_id == 1,
            StudioMember.email == email,
        ).delete()
        db.commit()
    finally:
        db.close()


def _cleanup_column(slug: str) -> None:
    db = SessionLocal()
    try:
        db.query(MemberCustomColumn).filter(
            MemberCustomColumn.tenant_id == 1,
            MemberCustomColumn.slug == slug,
        ).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_create_and_list_member_is_tenant_scoped(
    tenant_admin_client: AsyncClient,
) -> None:
    email = _unique_email()
    try:
        create_response = await tenant_admin_client.post(
            "/admin/members",
            json={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": email,
                "tags": ["vip"],
                "custom_fields": {"source": "manual-test"},
            },
        )
        assert create_response.status_code == 200
        assert create_response.json()["email"] == email

        list_response = await tenant_admin_client.get("/admin/members", params={"search": email})
        assert list_response.status_code == 200
        members = list_response.json()
        assert len(members) == 1
        assert members[0]["email"] == email
    finally:
        _cleanup_member(email)


@pytest.mark.anyio
async def test_create_duplicate_member_conflicts(
    tenant_admin_client: AsyncClient,
) -> None:
    email = _unique_email()
    try:
        first = await tenant_admin_client.post(
            "/admin/members",
            json={"first_name": "Grace", "last_name": "Hopper", "email": email},
        )
        assert first.status_code == 200

        second = await tenant_admin_client.post(
            "/admin/members",
            json={"first_name": "Grace", "last_name": "Hopper", "email": email},
        )
        assert second.status_code == 409
    finally:
        _cleanup_member(email)


@pytest.mark.anyio
async def test_export_csv_includes_custom_column_headers(
    tenant_admin_client: AsyncClient,
) -> None:
    slug = f"membership_level_{int(time.time() * 1000)}"
    email = _unique_email()
    try:
        create_column = await tenant_admin_client.post(
            "/admin/members/columns",
            json={
                "name": "Membership Level",
                "slug": slug,
                "field_type": "text",
                "position": 1,
            },
        )
        assert create_column.status_code == 200

        create_member = await tenant_admin_client.post(
            "/admin/members",
            json={
                "first_name": "Katherine",
                "last_name": "Johnson",
                "email": email,
                "custom_fields": {slug: "gold"},
            },
        )
        assert create_member.status_code == 200

        export_response = await tenant_admin_client.get("/admin/members/export/csv")
        assert export_response.status_code == 200
        assert export_response.headers["content-type"].startswith("text/csv")

        rows = list(csv.reader(io.StringIO(export_response.text)))
        assert rows
        assert slug in rows[0]
    finally:
        _cleanup_member(email)
        _cleanup_column(slug)
