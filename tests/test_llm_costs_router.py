from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_access_token
from app.core.db import SessionLocal
from app.core.models import LLMModelCost, LLMUsageLog


def _auth_headers(*, role: str, user_id: int, email: str, tenant_id: int) -> dict[str, str]:
    token = create_access_token(
        user_id=user_id,
        email=email,
        tenant_id=tenant_id,
        tenant_slug="default",
        role=role,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def system_admin_client() -> AsyncClient:
    from app.edge.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=_auth_headers(
            role="system_admin",
            user_id=1,
            email="admin@ariia.local",
            tenant_id=1,
        ),
    ) as client:
        yield client


def _cleanup_model_cost(model_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(LLMModelCost).filter(LLMModelCost.model_id == model_id).delete()
        db.commit()
    finally:
        db.close()


def _cleanup_usage_log(agent_name: str) -> None:
    db = SessionLocal()
    try:
        db.query(LLMUsageLog).filter(LLMUsageLog.agent_name == agent_name).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_model_cost_crud_requires_system_admin_and_roundtrips(
    system_admin_client: AsyncClient,
) -> None:
    model_id = f"test-model-{int(time.time() * 1000)}"
    try:
        upsert = await system_admin_client.put(
            "/llm/model-costs",
            json={
                "provider_id": "openai",
                "model_id": model_id,
                "display_name": "Test Model",
                "input_cost_per_million": 123,
                "output_cost_per_million": 456,
                "is_active": True,
            },
        )
        assert upsert.status_code == 200
        assert upsert.json() == {"status": "ok"}

        listed = await system_admin_client.get("/llm/model-costs")
        assert listed.status_code == 200
        costs = listed.json()
        created = next(item for item in costs if item["model_id"] == model_id)
        assert created["provider_id"] == "openai"
        assert created["input_cost_per_million"] == 123
        assert created["output_cost_per_million"] == 456

        deleted = await system_admin_client.delete(f"/llm/model-costs/{model_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted"}
    finally:
        _cleanup_model_cost(model_id)


@pytest.mark.anyio
async def test_usage_summary_aggregates_recent_usage(
    system_admin_client: AsyncClient,
) -> None:
    agent_name = f"llm-costs-test-{int(time.time() * 1000)}"
    db = SessionLocal()
    try:
        db.add(
            LLMUsageLog(
                tenant_id=1,
                user_id="user-1",
                agent_name=agent_name,
                provider_id="openai",
                model_id="gpt-4.1-mini",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                total_cost_cents=12.5,
                latency_ms=800,
                success=True,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        response = await system_admin_client.get("/llm/usage-summary", params={"days": 30, "tenant_id": 1})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_requests"] >= 1
        assert payload["total_tokens"] >= 150
        assert payload["total_cost_cents"] >= 12.5
    finally:
        _cleanup_usage_log(agent_name)
