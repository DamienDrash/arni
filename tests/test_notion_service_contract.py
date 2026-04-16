from __future__ import annotations

from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.core.models import Tenant
from app.memory_platform.notion_models import (
    NotionConnectionDB,
    NotionSyncedPageDB,
    NotionSyncLogDB,
)
from app.memory_platform.notion_service import NotionService


TEST_TENANT_ID = 930001


def _seed_notion_fixture() -> None:
    db = SessionLocal()
    try:
        db.query(NotionSyncedPageDB).filter(NotionSyncedPageDB.tenant_id == TEST_TENANT_ID).delete()
        db.query(NotionSyncLogDB).filter(NotionSyncLogDB.tenant_id == TEST_TENANT_ID).delete()
        db.query(NotionConnectionDB).filter(NotionConnectionDB.tenant_id == TEST_TENANT_ID).delete()
        db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).delete()
        db.flush()

        db.add(
            Tenant(
                id=TEST_TENANT_ID,
                slug="notion-service-contract",
                name="Notion Contract Tenant",
                is_active=True,
            )
        )
        db.add(
            NotionConnectionDB(
                tenant_id=TEST_TENANT_ID,
                workspace_id="ws_contract",
                workspace_name="Contract Workspace",
                access_token_enc="enc-token",
                status="connected",
                connected_at=datetime.now(timezone.utc),
                last_sync_at=datetime.now(timezone.utc),
                last_sync_status="completed",
                webhook_active=True,
                pages_synced=1,
                databases_synced=0,
            )
        )
        db.add(
            NotionSyncedPageDB(
                tenant_id=TEST_TENANT_ID,
                notion_page_id="page_contract",
                title="Contract Page",
                page_type="page",
                parent_type="database",
                parent_name="Contract DB",
                url="https://notion.so/page_contract",
                sync_enabled=True,
                sync_status="synced",
                chunk_count=3,
                last_synced_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            NotionSyncLogDB(
                tenant_id=TEST_TENANT_ID,
                sync_type="full",
                status="completed",
                pages_processed=1,
                chunks_created=3,
                completed_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()


def test_notion_service_reads_status_pages_and_logs() -> None:
    _seed_notion_fixture()
    service = NotionService()

    status = service.get_status(TEST_TENANT_ID)
    pages = service.get_synced_pages(TEST_TENANT_ID)
    logs = service.get_sync_logs(TEST_TENANT_ID)

    assert status["connected"] is True
    assert status["workspace_name"] == "Contract Workspace"
    assert status["pages_synced"] == 1

    assert len(pages) == 1
    assert pages[0]["page_id"] == "page_contract"
    assert pages[0]["sync_status"] == "synced"
    assert pages[0]["chunk_count"] == 3

    assert len(logs) == 1
    assert logs[0]["type"] == "full"
    assert logs[0]["status"] == "completed"
    assert logs[0]["chunks_created"] == 3


def test_notion_service_disconnect_removes_tenant_state() -> None:
    _seed_notion_fixture()
    service = NotionService()

    result = service.disconnect(TEST_TENANT_ID)

    assert result == {"status": "disconnected"}
    assert service.get_status(TEST_TENANT_ID)["connected"] is False
    assert service.get_synced_pages(TEST_TENANT_ID) == []
    assert service.get_sync_logs(TEST_TENANT_ID) == []
