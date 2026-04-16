from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import AuthContext, get_current_user
from app.core.db import SessionLocal
from app.core.integration_models import SyncLog, TenantIntegration
from app.core.models import Tenant
from app.gateway.main import app


@pytest.fixture
async def tenant_admin_client() -> AsyncClient:
    async def override_get_current_user() -> AuthContext:
        return AuthContext(
            user_id="sync-admin",
            email="sync-admin@test.example",
            tenant_id=1,
            tenant_slug="default",
            role="tenant_admin",
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def _ensure_tenant_slug() -> None:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        if tenant and tenant.slug != "default":
            tenant.slug = "default"
            db.commit()
    finally:
        db.close()


def _cleanup_integration(integration_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == 1,
            TenantIntegration.integration_id == integration_id,
        ).delete()
        db.commit()
    finally:
        db.close()


def _cleanup_sync_logs(integration_id: str) -> None:
    db = SessionLocal()
    try:
        tenant_integration = (
            db.query(TenantIntegration)
            .filter(
                TenantIntegration.tenant_id == 1,
                TenantIntegration.integration_id == integration_id,
            )
            .first()
        )
        if tenant_integration:
            db.query(SyncLog).filter(
                SyncLog.tenant_integration_id == tenant_integration.id,
            ).delete()
            db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_toggle_integration_updates_enabled_flag(
    tenant_admin_client: AsyncClient,
) -> None:
    integration_id = "sync-toggle-test"
    db = SessionLocal()
    try:
        db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == 1,
            TenantIntegration.integration_id == integration_id,
        ).delete()
        db.add(
            TenantIntegration(
                tenant_id=1,
                integration_id=integration_id,
                status="active",
                enabled=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        response = await tenant_admin_client.put(
            f"/sync/integrations/{integration_id}/toggle",
            json={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        db = SessionLocal()
        try:
            row = db.query(TenantIntegration).filter(
                TenantIntegration.tenant_id == 1,
                TenantIntegration.integration_id == integration_id,
            ).first()
            assert row is not None
            assert row.enabled is False
        finally:
            db.close()
    finally:
        _cleanup_integration(integration_id)


@pytest.mark.anyio
async def test_webhook_resolves_tenant_slug_and_dispatches(
    tenant_admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_tenant_slug()

    captured: dict[str, object] = {}

    class _FakeSyncCore:
        async def handle_webhook(self, tenant_id: int, integration_id: str, payload: dict, headers: dict) -> dict:
            captured["tenant_id"] = tenant_id
            captured["integration_id"] = integration_id
            captured["payload"] = payload
            return {"success": True, "handled": True}

    monkeypatch.setattr("app.gateway.routers.contact_sync_api._get_sync_core", lambda: _FakeSyncCore())

    response = await tenant_admin_client.post(
        "/webhook/sync/magicline/default",
        json={"event": "contact.updated"},
    )
    assert response.status_code == 200
    assert response.json()["handled"] is True
    assert captured["tenant_id"] == 1
    assert captured["integration_id"] == "magicline"
    assert captured["payload"] == {"event": "contact.updated"}


@pytest.mark.anyio
async def test_sync_stats_returns_tenant_scoped_breakdown(
    tenant_admin_client: AsyncClient,
) -> None:
    integration_id = "sync-stats-test"
    _cleanup_sync_logs(integration_id)
    _cleanup_integration(integration_id)

    db = SessionLocal()
    try:
        tenant_integration = TenantIntegration(
            tenant_id=1,
            integration_id=integration_id,
            status="active",
            enabled=True,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(tenant_integration)
        db.commit()
        db.refresh(tenant_integration)
        db.add_all(
            [
                SyncLog(
                    tenant_integration_id=tenant_integration.id,
                    tenant_id=1,
                    sync_type="full",
                    trigger="manual",
                    status="success",
                    started_at=datetime.now(timezone.utc),
                    records_created=2,
                    records_updated=3,
                ),
                SyncLog(
                    tenant_integration_id=tenant_integration.id,
                    tenant_id=1,
                    sync_type="incremental",
                    trigger="scheduled",
                    status="error",
                    started_at=datetime.now(timezone.utc),
                    records_created=1,
                    records_updated=0,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    try:
        response = await tenant_admin_client.get("/sync/stats")
        assert response.status_code == 200
        payload = response.json()

        assert payload["period_24h"]["total_syncs"] == 2
        assert payload["period_24h"]["successful_syncs"] == 1
        assert payload["period_24h"]["failed_syncs"] == 1
        assert payload["period_24h"]["records_synced"] == 6

        integration_stats = next(
            item for item in payload["integrations"] if item["integration_id"] == integration_id
        )
        assert integration_stats["syncs_24h"] == 2
        assert integration_stats["records_24h"] == 6
        assert integration_stats["errors_24h"] == 1
    finally:
        _cleanup_sync_logs(integration_id)
        _cleanup_integration(integration_id)
