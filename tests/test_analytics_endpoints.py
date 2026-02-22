"""Tests für K1: Backend Analytics Aggregation Endpoints.

Verifies:
  1. Alle 4 Endpoints erreichbar und geben korrekte Struktur zurück
  2. Unauthentifizierte Requests → 401
  3. Tenant-Isolation: Tenant A sieht nicht die Daten von Tenant B
  4. Leere DB → leere aber valide Responses (keine 500er)
  5. Stündliche und wöchentliche Daten haben korrekte Array-Länge
  6. Intent-Endpoint gibt maximal 8 Einträge zurück
"""

import time
import json
import pytest
from httpx import AsyncClient


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _register_tenant(client: AsyncClient, suffix: str) -> tuple[str, int]:
    """Register a new tenant, return (access_token, tenant_id)."""
    unique = f"{suffix}-{int(time.time() * 1000)}"
    resp = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Analytics Test {unique}",
            "tenant_slug": f"analytics-test-{unique}",
            "email": f"admin-{unique}@analytics-test.example",
            "password": "TestPass!1234",
            "full_name": "Test Admin",
        },
    )
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    data = resp.json()
    return data["access_token"], data["user"]["tenant_id"]


async def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── 1. Auth Guard ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_analytics_overview_requires_auth() -> None:
    """Unauthenticated request → 401."""
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}  # force real dependencies
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/admin/analytics/overview", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_analytics_hourly_requires_auth() -> None:
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/admin/analytics/hourly", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_analytics_weekly_requires_auth() -> None:
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/admin/analytics/weekly", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_analytics_intents_requires_auth() -> None:
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/admin/analytics/intents", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code in (401, 403)


# ── 2. Response Shape ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_analytics_overview_shape(client: AsyncClient) -> None:
    """Overview endpoint returns all required KPI fields."""
    token, _ = await _register_tenant(client, "shape-ov")
    resp = await client.get("/admin/analytics/overview", headers=await _auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()

    required_keys = [
        "tickets_24h", "resolved_24h", "escalated_24h",
        "ai_resolution_rate", "escalation_rate",
        "confidence_avg", "confidence_high_pct", "confidence_low_pct",
        "confidence_distribution",
        "channels_24h",
        "tickets_30d", "tickets_prev_30d", "month_trend_pct",
    ]
    for key in required_keys:
        assert key in data, f"Missing key: {key}"

    # Type checks
    assert isinstance(data["tickets_24h"], int)
    assert isinstance(data["ai_resolution_rate"], (int, float))
    assert isinstance(data["channels_24h"], dict)
    assert isinstance(data["confidence_distribution"], list)


@pytest.mark.anyio
async def test_analytics_hourly_has_24_entries(client: AsyncClient) -> None:
    """Hourly endpoint always returns exactly 24 entries (0:00–23:00)."""
    token, _ = await _register_tenant(client, "shape-hourly")
    resp = await client.get("/admin/analytics/hourly", headers=await _auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 24

    # Verify entry shape
    entry = data[0]
    assert "hour" in entry
    assert "aiResolved" in entry
    assert "escalated" in entry
    assert entry["hour"].endswith(":00")  # e.g. "00:00"
    assert isinstance(entry["aiResolved"], int)
    assert isinstance(entry["escalated"], int)


@pytest.mark.anyio
async def test_analytics_weekly_has_7_entries(client: AsyncClient) -> None:
    """Weekly endpoint always returns exactly 7 entries."""
    token, _ = await _register_tenant(client, "shape-weekly")
    resp = await client.get("/admin/analytics/weekly", headers=await _auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 7

    entry = data[0]
    assert "day" in entry
    assert "date" in entry
    assert "tickets" in entry
    assert "resolved" in entry
    assert "escalated" in entry
    # resolved + escalated == tickets
    assert entry["resolved"] + entry["escalated"] == entry["tickets"]


@pytest.mark.anyio
async def test_analytics_intents_shape(client: AsyncClient) -> None:
    """Intents endpoint returns list, max 8 items, each with required fields."""
    token, _ = await _register_tenant(client, "shape-intents")
    resp = await client.get("/admin/analytics/intents", headers=await _auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 8  # max 8 intents

    for item in data:
        assert "intent" in item
        assert "label" in item
        assert "count" in item
        assert "aiRate" in item
        assert 0 <= item["aiRate"] <= 100


# ── 3. Empty DB → no 500 ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_analytics_overview_empty_db_returns_zeros(client: AsyncClient) -> None:
    """Fresh tenant with no messages → all counters are 0, no server error."""
    token, _ = await _register_tenant(client, "empty-ov")
    resp = await client.get("/admin/analytics/overview", headers=await _auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["tickets_24h"] == 0
    assert data["resolved_24h"] == 0
    assert data["escalated_24h"] == 0
    assert data["ai_resolution_rate"] == 0.0
    assert data["channels_24h"] == {}


@pytest.mark.anyio
async def test_analytics_intents_empty_returns_empty_list(client: AsyncClient) -> None:
    """Fresh tenant with no messages → intents endpoint returns []."""
    token, _ = await _register_tenant(client, "empty-intents")
    resp = await client.get("/admin/analytics/intents", headers=await _auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


# ── 4. Tenant Isolation ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_analytics_tenant_isolation(client: AsyncClient) -> None:
    """Tenant A's messages are not visible in Tenant B's analytics overview."""
    from app.core.db import SessionLocal
    from app.core.models import ChatMessage
    from datetime import datetime, timezone

    token_a, tenant_id_a = await _register_tenant(client, "iso-a")
    token_b, tenant_id_b = await _register_tenant(client, "iso-b")

    # Insert 5 messages directly for Tenant A
    db = SessionLocal()
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for i in range(5):
            db.add(ChatMessage(
                session_id=f"iso-user-{i}",
                tenant_id=tenant_id_a,
                role="assistant",
                content=f"Test message {i}",
                timestamp=now,
                metadata_json=json.dumps({"channel": "whatsapp", "escalated": False, "confidence": 0.9}),
            ))
        db.commit()
    finally:
        db.close()

    # Tenant A sees 5 tickets
    resp_a = await client.get("/admin/analytics/overview", headers=await _auth_headers(token_a))
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["tickets_24h"] == 5

    # Tenant B sees 0 tickets (isolation!)
    resp_b = await client.get("/admin/analytics/overview", headers=await _auth_headers(token_b))
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["tickets_24h"] == 0, "Tenant isolation violated — Tenant B can see Tenant A's data!"


# ── 5. Confidence Distribution ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_analytics_confidence_distribution_sums(client: AsyncClient) -> None:
    """confidence_distribution entries should sum to total messages with confidence data."""
    from app.core.db import SessionLocal
    from app.core.models import ChatMessage
    from datetime import datetime, timezone

    token, tenant_id = await _register_tenant(client, "conf-dist")
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for conf in [0.95, 0.80, 0.60, 0.40, 0.95]:
            db.add(ChatMessage(
                session_id="conf-user",
                tenant_id=tenant_id,
                role="assistant",
                content="Test",
                timestamp=now,
                metadata_json=json.dumps({"confidence": conf, "escalated": False}),
            ))
        db.commit()
    finally:
        db.close()

    resp = await client.get("/admin/analytics/overview", headers=await _auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()

    dist = data["confidence_distribution"]
    assert len(dist) == 4  # 4 buckets: 90-100%, 75-89%, 50-74%, <50%
    assert all("range" in b and "count" in b for b in dist)
    total = sum(b["count"] for b in dist)
    assert total == 5  # all 5 messages have confidence data
