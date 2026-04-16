from __future__ import annotations

from datetime import datetime, timezone

from app.contacts.sync_core import AdapterRegistry, SyncCore
from app.core.db import SessionLocal
from app.core.integration_models import IntegrationDefinition, SyncLog, SyncSchedule, TenantIntegration
from app.core.models import Tenant
from app.integrations.adapters.base import BaseAdapter, ConnectionTestResult, SyncResult


TEST_TENANT_ID = 940001
TEST_INTEGRATION_ID = "sync_core_contract"


class _DummySyncAdapter(BaseAdapter):
    @property
    def integration_id(self) -> str:
        return TEST_INTEGRATION_ID

    @property
    def display_name(self) -> str:
        return "Sync Core Contract"

    @property
    def category(self) -> str:
        return "custom"

    @property
    def supported_capabilities(self) -> list[str]:
        return []

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {"key": "api_key", "type": "password", "required": True},
                {"key": "region", "type": "text", "required": False},
            ]
        }

    async def get_contacts(self, tenant_id: int, config: dict, last_sync_at=None, sync_mode=None) -> SyncResult:
        return SyncResult(success=True)

    async def test_connection(self, config: dict) -> ConnectionTestResult:
        return ConnectionTestResult(success=True, message="ok")

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs):
        raise NotImplementedError


def _seed_sync_core_fixture() -> None:
    db = SessionLocal()
    try:
        db.query(SyncLog).filter(SyncLog.tenant_id == TEST_TENANT_ID).delete()
        db.query(SyncSchedule).filter(SyncSchedule.tenant_id == TEST_TENANT_ID).delete()
        db.query(TenantIntegration).filter(TenantIntegration.tenant_id == TEST_TENANT_ID).delete()
        db.query(IntegrationDefinition).filter(IntegrationDefinition.id == TEST_INTEGRATION_ID).delete()
        db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).delete()
        db.flush()

        db.add(
            Tenant(
                id=TEST_TENANT_ID,
                slug="sync-core-contract",
                name="Sync Core Contract Tenant",
                is_active=True,
            )
        )
        db.add(
            IntegrationDefinition(
                id=TEST_INTEGRATION_ID,
                name="Sync Core Contract",
                category="custom",
                auth_type="api_key",
                is_active=True,
                is_public=True,
            )
        )
        db.commit()
    finally:
        db.close()


def test_sync_core_save_list_and_delete_roundtrip() -> None:
    _seed_sync_core_fixture()
    core = SyncCore()
    previous = AdapterRegistry.get_all()
    AdapterRegistry.clear()
    AdapterRegistry.register(_DummySyncAdapter())
    try:
        save_result = core.save_integration(
            tenant_id=TEST_TENANT_ID,
            integration_id=TEST_INTEGRATION_ID,
            config={"api_key": "secret", "region": "eu"},
            sync_direction="inbound",
            sync_interval_minutes=120,
            enabled=True,
        )

        assert save_result["status"] == "configured"

        integrations = core.get_tenant_integrations(TEST_TENANT_ID)
        assert len(integrations) == 1
        assert integrations[0]["integration_id"] == TEST_INTEGRATION_ID
        assert integrations[0]["display_name"] == "Sync Core Contract"
        assert integrations[0]["sync_interval_minutes"] == 120

        db = SessionLocal()
        try:
            tenant_integration = (
                db.query(TenantIntegration)
                .filter(TenantIntegration.tenant_id == TEST_TENANT_ID, TenantIntegration.integration_id == TEST_INTEGRATION_ID)
                .first()
            )
            assert tenant_integration is not None
            assert tenant_integration.config_meta == {"region": "eu"}
            assert tenant_integration.config_encrypted

            schedule = (
                db.query(SyncSchedule)
                .filter(SyncSchedule.tenant_integration_id == tenant_integration.id)
                .first()
            )
            assert schedule is not None
            assert schedule.cron_expression == "0 */2 * * *"
            assert schedule.is_enabled is True
        finally:
            db.close()

        delete_result = core.delete_integration(TEST_TENANT_ID, TEST_INTEGRATION_ID)
        assert delete_result["success"] is True
        assert core.get_tenant_integrations(TEST_TENANT_ID) == []
    finally:
        AdapterRegistry.clear()
        for adapter in previous.values():
            AdapterRegistry.register(adapter)


def test_sync_core_history_reads_real_synclog_schema() -> None:
    _seed_sync_core_fixture()
    core = SyncCore()
    previous = AdapterRegistry.get_all()
    AdapterRegistry.clear()
    AdapterRegistry.register(_DummySyncAdapter())
    try:
        core.save_integration(
            tenant_id=TEST_TENANT_ID,
            integration_id=TEST_INTEGRATION_ID,
            config={"api_key": "secret"},
            sync_interval_minutes=60,
        )

        db = SessionLocal()
        try:
            tenant_integration = (
                db.query(TenantIntegration)
                .filter(TenantIntegration.tenant_id == TEST_TENANT_ID, TenantIntegration.integration_id == TEST_INTEGRATION_ID)
                .first()
            )
            assert tenant_integration is not None
            core._log_sync(
                db=db,
                tenant_integration_id=tenant_integration.id,
                tenant_id=TEST_TENANT_ID,
                integration_id=TEST_INTEGRATION_ID,
                started_at=datetime.now(timezone.utc),
                success=True,
                triggered_by="manual",
                records_fetched=5,
                records_created=2,
                records_updated=1,
                records_failed=0,
                duration_ms=25,
            )
        finally:
            db.close()

        history = core.get_sync_history(TEST_TENANT_ID, TEST_INTEGRATION_ID)
        assert len(history) == 1
        assert history[0]["integration_id"] == TEST_INTEGRATION_ID
        assert history[0]["sync_mode"] == "full"
        assert history[0]["triggered_by"] == "manual"
        assert history[0]["records_fetched"] == 5
        assert history[0]["records_created"] == 2
    finally:
        AdapterRegistry.clear()
        for adapter in previous.values():
            AdapterRegistry.register(adapter)
