from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.db import SessionLocal
from app.core.models import ChatMessage, ChatSession, Tenant
from app.memory.librarian_v2 import FallbackSummarization, LibrarianWorker


TEST_TENANT_ID = 960001
TEST_SESSION_ID = 960001
TEST_USER_ID = "491766600001"
TEST_MEMBER_ID = "960001"


def _seed_librarian_fixture() -> None:
    db = SessionLocal()
    try:
        db.query(ChatMessage).filter(
            ChatMessage.tenant_id == TEST_TENANT_ID,
            ChatMessage.session_id.in_([TEST_USER_ID, str(TEST_SESSION_ID)]),
        ).delete(synchronize_session=False)
        db.query(ChatSession).filter(
            ChatSession.tenant_id == TEST_TENANT_ID,
            ChatSession.id == TEST_SESSION_ID,
        ).delete()
        db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).delete()
        db.flush()

        db.add(
            Tenant(
                id=TEST_TENANT_ID,
                slug="librarian-v2-contract",
                name="Librarian V2 Contract",
                is_active=True,
            )
        )
        db.add(
            ChatSession(
                id=TEST_SESSION_ID,
                tenant_id=TEST_TENANT_ID,
                user_id=TEST_USER_ID,
                platform="whatsapp",
                member_id=TEST_MEMBER_ID,
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
                last_message_at=datetime.now(timezone.utc) - timedelta(days=2),
                is_active=True,
            )
        )
        db.add_all(
            [
                ChatMessage(
                    tenant_id=TEST_TENANT_ID,
                    session_id=TEST_USER_ID,
                    role="user",
                    content="Ich möchte meinen Trainingsplan anpassen.",
                    timestamp=datetime.now(timezone.utc) - timedelta(days=2, minutes=5),
                ),
                ChatMessage(
                    tenant_id=TEST_TENANT_ID,
                    session_id=str(TEST_SESSION_ID),
                    role="assistant",
                    content="Wir priorisieren jetzt Regeneration und Mobilität.",
                    timestamp=datetime.now(timezone.utc) - timedelta(days=2, minutes=1),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_librarian_scan_reads_legacy_and_current_session_identifiers() -> None:
    _seed_librarian_fixture()
    worker = LibrarianWorker()

    stale_sessions = await worker.scan_stale_sessions(age_hours=24)

    tenant_sessions = [session for session in stale_sessions if session["tenant_id"] == TEST_TENANT_ID]
    assert len(tenant_sessions) == 1
    assert tenant_sessions[0]["chat_session_id"] == TEST_SESSION_ID
    assert tenant_sessions[0]["message_count"] == 2
    contents = [message["content"] for message in tenant_sessions[0]["messages"]]
    assert "Ich möchte meinen Trainingsplan anpassen." in contents
    assert "Wir priorisieren jetzt Regeneration und Mobilität." in contents


@pytest.mark.anyio
async def test_librarian_cycle_marks_session_archived_by_chat_session_id(monkeypatch) -> None:
    _seed_librarian_fixture()
    worker = LibrarianWorker(primary_strategy=FallbackSummarization(), fallback_strategy=FallbackSummarization())

    async def _fake_scan_stale_sessions() -> list[dict]:
        return [
            {
                "chat_session_id": TEST_SESSION_ID,
                "session_id": TEST_USER_ID,
                "member_id": TEST_MEMBER_ID,
                "tenant_id": TEST_TENANT_ID,
                "messages": [{"role": "user", "content": "Bitte archivieren."}],
                "message_count": 1,
            }
        ]

    async def _fake_store_summary(job) -> bool:
        return True

    monkeypatch.setattr(worker, "scan_stale_sessions", _fake_scan_stale_sessions)
    monkeypatch.setattr(worker, "store_summary", _fake_store_summary)

    result = await worker.run_archival_cycle()

    assert result["completed"] == 1

    db = SessionLocal()
    try:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == TEST_SESSION_ID)
            .first()
        )
        assert session is not None
        assert session.is_active is False
    finally:
        db.close()
