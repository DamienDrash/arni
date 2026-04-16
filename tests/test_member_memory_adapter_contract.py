from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.db import SessionLocal
from app.core.models import ChatMessage, ChatSession, StudioMember
from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter


def _seed_member_history() -> None:
    db = SessionLocal()
    try:
        db.query(ChatMessage).filter(ChatMessage.tenant_id == 1, ChatMessage.session_id == "900001").delete()
        db.query(ChatSession).filter(ChatSession.tenant_id == 1, ChatSession.id == 900001).delete()
        db.query(StudioMember).filter(StudioMember.tenant_id == 1, StudioMember.customer_id == 900001).delete()

        db.add(
            StudioMember(
                tenant_id=1,
                customer_id=900001,
                member_number="MM-900001",
                first_name="Memory",
                last_name="Member",
            )
        )
        db.add(
            ChatSession(
                id=900001,
                tenant_id=1,
                user_id="491700000001",
                platform="whatsapp",
                member_id="900001",
                created_at=datetime.now(timezone.utc),
                last_message_at=datetime.now(timezone.utc),
            )
        )
        db.add_all(
            [
                ChatMessage(
                    tenant_id=1,
                    session_id="900001",
                    role="user",
                    content="Ich moechte meinen Trainingsplan anpassen.",
                ),
                ChatMessage(
                    tenant_id=1,
                    session_id="900001",
                    role="assistant",
                    content="Gerne, ich schaue mir deine letzten Ziele an.",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_member_memory_history_returns_recent_messages() -> None:
    _seed_member_history()
    adapter = MemberMemoryAdapter()

    result = await adapter.execute_capability(
        "memory.member.history",
        tenant_id=1,
        member_id="MM-900001",
        limit=10,
    )

    assert result.success is True
    assert result.metadata["member_name"] == "Memory Member"
    assert result.metadata["message_count"] == 2
    assert result.data[0]["role"] == "user"
    assert "Trainingsplan" in result.data[0]["content"]
