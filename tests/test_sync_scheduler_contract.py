from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.contacts.sync_scheduler import SyncScheduler
from app.core.db import SessionLocal
from app.core.integration_models import IntegrationDefinition, SyncLog, SyncSchedule, TenantIntegration
from app.core.models import Tenant


TEST_TENANT_ID = 940002
TEST_INTEGRATION_ID = "sync_scheduler_contract"
TEST_DISABLED_INTEGRATION_ID = "sync_scheduler_disabled"
TEST_RECENT_INTEGRATION_ID = "sync_scheduler_recent"


def _seed_sync_scheduler_fixture() -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        db.query(SyncLog).filter(SyncLog.tenant_id == TEST_TENANT_ID).delete()
        db.query(SyncSchedule).filter(SyncSchedule.tenant_id == TEST_TENANT_ID).delete()
        db.query(TenantIntegration).filter(TenantIntegration.tenant_id == TEST_TENANT_ID).delete()
        db.query(IntegrationDefinition).filter(
            IntegrationDefinition.id.in_(
                [
                    TEST_INTEGRATION_ID,
                    TEST_DISABLED_INTEGRATION_ID,
                    TEST_RECENT_INTEGRATION_ID,
                ]
            )
        ).delete(synchronize_session=False)
        db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).delete()
        db.flush()

        db.add(
            Tenant(
                id=TEST_TENANT_ID,
                slug="sync-scheduler-contract",
                name="Sync Scheduler Contract Tenant",
                is_active=True,
            )
        )
        db.add_all(
            [
                IntegrationDefinition(
                    id=TEST_INTEGRATION_ID,
                    name="Sync Scheduler Contract",
                    category="custom",
                    auth_type="api_key",
                    is_active=True,
                    is_public=True,
                ),
                IntegrationDefinition(
                    id=TEST_DISABLED_INTEGRATION_ID,
                    name="Sync Scheduler Disabled",
                    category="custom",
                    auth_type="api_key",
                    is_active=True,
                    is_public=True,
                ),
                IntegrationDefinition(
                    id=TEST_RECENT_INTEGRATION_ID,
                    name="Sync Scheduler Recent",
                    category="custom",
                    auth_type="api_key",
                    is_active=True,
                    is_public=True,
                ),
            ]
        )
        db.flush()

        now = datetime.now(timezone.utc)
        due_ti = TenantIntegration(
            tenant_id=TEST_TENANT_ID,
            integration_id=TEST_INTEGRATION_ID,
            enabled=True,
            status="connected",
            last_sync_at=now - timedelta(hours=3),
            last_sync_status="success",
        )
        disabled_ti = TenantIntegration(
            tenant_id=TEST_TENANT_ID,
            integration_id=TEST_DISABLED_INTEGRATION_ID,
            enabled=True,
            status="connected",
            last_sync_at=now - timedelta(hours=6),
            last_sync_status="success",
        )
        recent_ti = TenantIntegration(
            tenant_id=TEST_TENANT_ID,
            integration_id=TEST_RECENT_INTEGRATION_ID,
            enabled=True,
            status="connected",
            last_sync_at=now - timedelta(minutes=30),
            last_sync_status="success",
        )
        db.add_all([due_ti, disabled_ti, recent_ti])
        db.flush()

        db.add_all(
            [
                SyncSchedule(
                    tenant_integration_id=due_ti.id,
                    tenant_id=TEST_TENANT_ID,
                    is_enabled=True,
                    cron_expression="0 */2 * * *",
                ),
                SyncSchedule(
                    tenant_integration_id=disabled_ti.id,
                    tenant_id=TEST_TENANT_ID,
                    is_enabled=False,
                    cron_expression="0 */1 * * *",
                ),
                SyncSchedule(
                    tenant_integration_id=recent_ti.id,
                    tenant_id=TEST_TENANT_ID,
                    is_enabled=True,
                    cron_expression="0 */1 * * *",
                ),
            ]
        )
        db.commit()
        return due_ti.id, disabled_ti.id, recent_ti.id
    finally:
        db.close()


def test_sync_scheduler_reads_due_integrations_from_schedule_cron() -> None:
    due_ti_id, _disabled_ti_id, _recent_ti_id = _seed_sync_scheduler_fixture()

    scheduler = SyncScheduler()
    due_integrations = scheduler._get_due_integrations()
    tenant_due_integrations = [ti for ti in due_integrations if ti.tenant_id == TEST_TENANT_ID]

    assert [ti.id for ti in tenant_due_integrations] == [due_ti_id]
    assert tenant_due_integrations[0].integration_id == TEST_INTEGRATION_ID


def test_sync_scheduler_counts_consecutive_errors_via_tenant_integration_id() -> None:
    due_ti_id, _disabled_ti_id, _recent_ti_id = _seed_sync_scheduler_fixture()

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        db.add_all(
            [
                SyncLog(
                    tenant_integration_id=due_ti_id,
                    tenant_id=TEST_TENANT_ID,
                    sync_type="full",
                    trigger="scheduled",
                    status="success",
                    started_at=now - timedelta(minutes=40),
                ),
                SyncLog(
                    tenant_integration_id=due_ti_id,
                    tenant_id=TEST_TENANT_ID,
                    sync_type="full",
                    trigger="scheduled",
                    status="error",
                    started_at=now - timedelta(minutes=20),
                ),
                SyncLog(
                    tenant_integration_id=due_ti_id,
                    tenant_id=TEST_TENANT_ID,
                    sync_type="full",
                    trigger="scheduled",
                    status="error",
                    started_at=now - timedelta(minutes=10),
                ),
            ]
        )
        db.commit()

        tenant_integration = (
            db.query(TenantIntegration)
            .filter(TenantIntegration.id == due_ti_id)
            .first()
        )
        assert tenant_integration is not None
    finally:
        db.close()

    scheduler = SyncScheduler()
    assert scheduler._get_consecutive_errors(tenant_integration) == 2
