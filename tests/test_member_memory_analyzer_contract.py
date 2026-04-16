from __future__ import annotations

from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.core.models import ChatMessage, ChatSession, Tenant
from app.memory.member_memory_analyzer import _chat_summary_for_member


TEST_TENANT_ID = 950001
TEST_SESSION_ID = 950001
TEST_USER_ID = "491755500001"
TEST_MEMBER_ID = "950001"


def _seed_analyzer_fixture() -> None:
    db = SessionLocal()
    try:
        db.query(ChatMessage).filter(
            ChatMessage.tenant_id == TEST_TENANT_ID,
            ChatMessage.session_id.in_([TEST_USER_ID, str(TEST_SESSION_ID)]),
        ).delete(synchronize_session=False)
        db.query(ChatSession).filter(ChatSession.tenant_id == TEST_TENANT_ID, ChatSession.id == TEST_SESSION_ID).delete()
        db.query(Tenant).filter(Tenant.id == TEST_TENANT_ID).delete()
        db.flush()

        db.add(
            Tenant(
                id=TEST_TENANT_ID,
                slug="member-memory-analyzer-contract",
                name="Member Memory Analyzer Contract",
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
                created_at=datetime.now(timezone.utc),
                last_message_at=datetime.now(timezone.utc),
            )
        )
        db.add_all(
            [
                ChatMessage(
                    tenant_id=TEST_TENANT_ID,
                    session_id=TEST_USER_ID,
                    role="user",
                    content="Ich trainiere lieber morgens.",
                    timestamp=datetime.now(timezone.utc),
                ),
                ChatMessage(
                    tenant_id=TEST_TENANT_ID,
                    session_id=str(TEST_SESSION_ID),
                    role="assistant",
                    content="Ich merke mir deinen Morgenfokus.",
                    timestamp=datetime.now(timezone.utc),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def test_chat_summary_reads_legacy_and_current_session_identifiers() -> None:
    _seed_analyzer_fixture()

    summary = _chat_summary_for_member(TEST_MEMBER_ID, TEST_TENANT_ID, max_messages=10)

    assert "Ich trainiere lieber morgens." in summary
    assert "Ich merke mir deinen Morgenfokus." in summary
