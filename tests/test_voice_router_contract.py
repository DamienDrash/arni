from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.core.db import SessionLocal
from app.core.models import Tenant
from app.gateway.persistence import persistence
from app.gateway.routers.voice import router as voice_router


def _build_voice_app() -> FastAPI:
    app = FastAPI()
    app.include_router(voice_router)
    return app


def _ensure_voice_tenant(*, slug: str, is_active: bool = True) -> int:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if tenant is None:
            tenant = Tenant(slug=slug, name=f"Voice {slug}", is_active=is_active)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        else:
            tenant.is_active = is_active
            db.commit()
        return int(tenant.id)
    finally:
        db.close()


async def _voice_client() -> AsyncClient:
    transport = ASGITransport(app=_build_voice_app())
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.anyio
async def test_voice_incoming_uses_tenant_specific_stream_url() -> None:
    tenant_id = _ensure_voice_tenant(slug="voice-route-default")
    persistence.upsert_setting("voice_channel_enabled", "true", tenant_id=tenant_id)
    persistence.upsert_setting(
        "twilio_voice_stream_url",
        "wss://voice.example.test/custom-stream",
        tenant_id=tenant_id,
    )

    try:
        async with await _voice_client() as client:
            response = await client.post("/voice/incoming/voice-route-default")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")
        assert "wss://voice.example.test/custom-stream" in response.text
    finally:
        persistence.delete_setting("voice_channel_enabled", tenant_id=tenant_id)
        persistence.delete_setting("twilio_voice_stream_url", tenant_id=tenant_id)


@pytest.mark.anyio
async def test_voice_incoming_builds_forwarded_stream_url_and_rejects_inactive_tenant() -> None:
    active_tenant_id = _ensure_voice_tenant(slug="voice-route-fallback")
    inactive_tenant_id = _ensure_voice_tenant(slug="voice-route-inactive", is_active=False)
    persistence.upsert_setting("voice_channel_enabled", "true", tenant_id=active_tenant_id)
    persistence.delete_setting("twilio_voice_stream_url", tenant_id=active_tenant_id)
    persistence.delete_setting("voice_channel_enabled", tenant_id=inactive_tenant_id)
    persistence.delete_setting("twilio_voice_stream_url", tenant_id=inactive_tenant_id)

    try:
        async with await _voice_client() as client:
            response = await client.post(
                "/voice/incoming/voice-route-fallback",
                headers={
                    "x-forwarded-host": "voice-forward.example.test",
                    "x-forwarded-proto": "https",
                },
            )
            missing = await client.post("/voice/incoming/voice-route-inactive")
        assert response.status_code == 200
        assert "wss://voice-forward.example.test/voice/stream/voice-route-fallback" in response.text
        assert missing.status_code == 404
    finally:
        persistence.delete_setting("voice_channel_enabled", tenant_id=active_tenant_id)
        persistence.delete_setting("twilio_voice_stream_url", tenant_id=active_tenant_id)
