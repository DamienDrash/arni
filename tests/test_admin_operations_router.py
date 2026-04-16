from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.core.db import SessionLocal
from app.core.models import ChatSession, StudioMember
from app.gateway.main import app


class _FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> int:
        existed = key in self.store
        self.store.pop(key, None)
        return 1 if existed else 0


class _FakeBus:
    def __init__(self) -> None:
        self.client = _FakeRedisClient()

    async def disconnect(self) -> None:
        return None


@pytest.fixture
async def tenant_admin_client():
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="admin-ops",
            email="admin@test.example",
            tenant_id=1,
            tenant_slug="ops-test",
            role="tenant_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_members_stats_route_is_tenant_scoped(tenant_admin_client: AsyncClient) -> None:
    db = SessionLocal()
    try:
        db.query(StudioMember).filter(StudioMember.tenant_id.in_([1, 2])).delete(synchronize_session=False)
        db.add_all([
            StudioMember(tenant_id=1, customer_id=101, first_name="Alice", last_name="Admin", email="alice@test.example"),
            StudioMember(tenant_id=1, customer_id=102, first_name="Bob", last_name="Builder", phone_number="+49123"),
            StudioMember(tenant_id=2, customer_id=201, first_name="Other", last_name="Tenant", email="other@test.example", phone_number="+49999"),
        ])
        db.commit()
    finally:
        db.close()

    response = await tenant_admin_client.get("/admin/members/stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_members"] == 2
    assert payload["with_email"] == 1
    assert payload["with_phone"] == 1
    assert payload["with_both"] == 0


@pytest.mark.anyio
async def test_members_route_hydrates_chat_aggregation_per_tenant(
    tenant_admin_client: AsyncClient,
) -> None:
    db = SessionLocal()
    try:
        db.query(ChatSession).filter(ChatSession.tenant_id.in_([1, 2])).delete(synchronize_session=False)
        db.query(StudioMember).filter(StudioMember.tenant_id.in_([1, 2])).delete(synchronize_session=False)
        db.add_all([
            StudioMember(
                tenant_id=1,
                customer_id=301,
                member_number="M-301",
                first_name="Carla",
                last_name="Contact",
                email="carla@test.example",
            ),
            StudioMember(
                tenant_id=2,
                customer_id=401,
                member_number="M-401",
                first_name="Foreign",
                last_name="Member",
                email="foreign@test.example",
            ),
        ])
        db.add_all([
            ChatSession(
                tenant_id=1,
                user_id="member-session-1",
                member_id="M-301",
                platform="telegram",
                last_message_at=datetime.now(timezone.utc),
            ),
            ChatSession(
                tenant_id=2,
                user_id="member-session-foreign",
                member_id="M-401",
                platform="telegram",
                last_message_at=datetime.now(timezone.utc),
            ),
        ])
        db.commit()
    finally:
        db.close()

    response = await tenant_admin_client.get("/admin/members", params={"limit": 10})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["customer_id"] == 301
    assert payload[0]["verified"] is True
    assert payload[0]["chat_sessions"] == 1


@pytest.mark.anyio
async def test_chats_route_is_available_and_hydrates_token(
    tenant_admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = SessionLocal()
    try:
        db.query(ChatSession).filter(ChatSession.tenant_id.in_([1, 2])).delete(synchronize_session=False)
        db.add_all([
            ChatSession(
                tenant_id=1,
                user_id="ops-user-1",
                platform="telegram",
                user_name="Ops User",
                phone_number="+491234",
                email="ops-user@test.example",
                last_message_at=datetime.now(timezone.utc),
            ),
            ChatSession(
                tenant_id=2,
                user_id="foreign-user",
                platform="telegram",
                user_name="Foreign User",
                last_message_at=datetime.now(timezone.utc),
            ),
        ])
        db.commit()
    finally:
        db.close()

    fake_bus = _FakeBus()

    async def fake_get_redis() -> _FakeBus:
        return fake_bus

    monkeypatch.setattr("app.gateway.services.admin_operations_service.service.create_redis_bus", fake_get_redis)

    response = await tenant_admin_client.get("/admin/chats?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["user_id"] == "ops-user-1"
    assert payload[0]["active_token"] is not None
    assert len(payload[0]["active_token"]) == 6


@pytest.mark.anyio
async def test_chats_route_migrates_legacy_user_token_key(
    tenant_admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = SessionLocal()
    try:
        db.query(ChatSession).filter(ChatSession.tenant_id == 1).delete(synchronize_session=False)
        db.add(ChatSession(
            tenant_id=1,
            user_id="ops-user-legacy",
            platform="telegram",
            user_name="Legacy User",
            last_message_at=datetime.now(timezone.utc),
        ))
        db.commit()
    finally:
        db.close()

    fake_bus = _FakeBus()
    fake_bus.client.store["user_token:ops-user-legacy"] = "123456"
    fake_bus.client.store["token:123456"] = '{"member_id": null, "user_id": "ops-user-legacy"}'

    async def fake_get_redis() -> _FakeBus:
        return fake_bus

    monkeypatch.setattr("app.gateway.services.admin_operations_service.service.create_redis_bus", fake_get_redis)

    response = await tenant_admin_client.get("/admin/chats?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["active_token"] == "123456"
    assert fake_bus.client.store["t1:user_token:ops-user-legacy"] == "123456"
    assert "user_token:ops-user-legacy" not in fake_bus.client.store
