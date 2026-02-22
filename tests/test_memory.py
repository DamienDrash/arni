"""ARIIA v1.4 – Memory Module Tests.

@QA: Sprint 4, Task 4.10
Tests: Context, Database, Repository, Knowledge, Flush, Graph, Consent.
Coverage target: ≥80% for app/memory/
"""

import os
import time
import pytest
import tempfile
from pathlib import Path

from app.memory.context import ConversationContext, Turn
from app.memory.database import MemoryDB
from app.memory.repository import SessionRepository
from app.memory.knowledge import KnowledgeStore
from app.memory.flush import SilentFlush
from app.memory.graph import FactGraph
from app.memory.consent import ConsentManager


# ──────────────────────────────────────────
# Context Tests (RAM Short-Term Memory)
# ──────────────────────────────────────────


class TestConversationContext:
    """Tests for per-user RAM context manager."""

    def test_add_and_get_turns(self) -> None:
        ctx = ConversationContext()
        ctx.add_turn("user1", "user", "Hallo!")
        ctx.add_turn("user1", "assistant", "Hey! 💪")
        result = ctx.get_context("user1")
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["content"] == "Hey! 💪"

    def test_max_turns_enforcement(self) -> None:
        ctx = ConversationContext(max_turns=5)
        for i in range(10):
            ctx.add_turn("user1", "user", f"msg-{i}")
        result = ctx.get_context("user1")
        assert len(result) == 5
        assert result[0]["content"] == "msg-5"

    def test_separate_users(self) -> None:
        ctx = ConversationContext()
        ctx.add_turn("user1", "user", "Hello")
        ctx.add_turn("user2", "user", "World")
        assert len(ctx.get_context("user1")) == 1
        assert len(ctx.get_context("user2")) == 1

    def test_is_near_limit(self) -> None:
        ctx = ConversationContext(max_turns=10)
        for i in range(8):
            ctx.add_turn("user1", "user", f"msg-{i}")
        assert ctx.is_near_limit("user1") is True
        assert ctx.is_near_limit("user2") is False

    def test_is_near_limit_below_threshold(self) -> None:
        ctx = ConversationContext(max_turns=10)
        for i in range(5):
            ctx.add_turn("user1", "user", f"msg-{i}")
        assert ctx.is_near_limit("user1") is False

    def test_clear(self) -> None:
        ctx = ConversationContext()
        ctx.add_turn("user1", "user", "Hello")
        ctx.clear("user1")
        assert ctx.get_context("user1") == []

    def test_replace_with_summary(self) -> None:
        ctx = ConversationContext()
        for i in range(10):
            ctx.add_turn("user1", "user", f"msg-{i}")
        ctx.replace_with_summary("user1", "User talked about fitness", keep_last=3)
        result = ctx.get_context("user1")
        assert len(result) == 4  # summary + 3 recent
        assert "[Zusammenfassung]" in result[0]["content"]

    def test_get_user_count(self) -> None:
        ctx = ConversationContext()
        ctx.add_turn("user1", "user", "a")
        ctx.add_turn("user2", "user", "b")
        assert ctx.get_user_count() == 2

    def test_ttl_expiry(self) -> None:
        ctx = ConversationContext(ttl_seconds=0)  # Expire immediately
        ctx.add_turn("user1", "user", "Hello")
        time.sleep(0.01)
        assert ctx.get_context("user1") == []

    def test_get_turns_returns_copies(self) -> None:
        ctx = ConversationContext()
        ctx.add_turn("user1", "user", "test")
        turns = ctx.get_turns("user1")
        assert len(turns) == 1
        assert isinstance(turns[0], Turn)

    def test_empty_user_context(self) -> None:
        ctx = ConversationContext()
        assert ctx.get_context("nonexistent") == []


# ──────────────────────────────────────────
# Database Tests (SQLite)
# ──────────────────────────────────────────


class TestMemoryDB:
    """Tests for async SQLite database."""

    @pytest.mark.anyio
    async def test_init_creates_tables(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            db = MemoryDB(db_path)
            await db.init()
            # Verify tables exist
            cursor = await db.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            assert "sessions" in tables
            assert "messages" in tables
            await db.close()
        finally:
            os.unlink(db_path)

    @pytest.mark.anyio
    async def test_db_property_raises_when_not_init(self) -> None:
        db = MemoryDB("/tmp/nonexistent.db")
        with pytest.raises(RuntimeError):
            _ = db.db

    @pytest.mark.anyio
    async def test_cleanup_expired(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            db = MemoryDB(db_path)
            await db.init()
            # Insert an old session
            await db.db.execute(
                """INSERT INTO sessions (session_id, platform, user_id, consent_status, last_interaction)
                   VALUES (?, ?, ?, ?, ?)""",
                ("old-sess", "whatsapp", "user1", "granted", "2020-01-01T00:00:00"),
            )
            await db.db.commit()
            deleted = await db.cleanup_expired()
            assert deleted == 1
            await db.close()
        finally:
            os.unlink(db_path)

    @pytest.mark.anyio
    async def test_close(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            db = MemoryDB(db_path)
            await db.init()
            await db.close()
            assert db._db is None
        finally:
            os.unlink(db_path)


# ──────────────────────────────────────────
# Repository Tests (CRUD)
# ──────────────────────────────────────────


class TestSessionRepository:
    """Tests for session/message CRUD."""

    @pytest.fixture
    async def repo(self):
        db = MemoryDB(":memory:")
        await db.init()
        repo = SessionRepository(db)
        yield repo
        await db.close()

    @pytest.mark.anyio
    async def test_create_and_get_session(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        session = await repo.get_session(session_id)
        assert session is not None
        assert session["user_id"] == "user1"
        assert session["consent_status"] == "granted"

    @pytest.mark.anyio
    async def test_get_session_by_user(self, repo: SessionRepository) -> None:
        await repo.create_session("user1", "whatsapp")
        session = await repo.get_session_by_user("user1", "whatsapp")
        assert session is not None
        assert session["platform"] == "whatsapp"

    @pytest.mark.anyio
    async def test_get_session_nonexistent(self, repo: SessionRepository) -> None:
        assert await repo.get_session("nonexistent") is None

    @pytest.mark.anyio
    async def test_get_session_by_user_nonexistent(self, repo: SessionRepository) -> None:
        assert await repo.get_session_by_user("nobody", "whatsapp") is None

    @pytest.mark.anyio
    async def test_update_session(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        result = await repo.update_session(session_id, consent_status="revoked")
        assert result is True
        session = await repo.get_session(session_id)
        assert session["consent_status"] == "revoked"

    @pytest.mark.anyio
    async def test_update_session_no_valid_fields(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        result = await repo.update_session(session_id, invalid_field="x")
        assert result is False

    @pytest.mark.anyio
    async def test_delete_session(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        result = await repo.delete_session(session_id)
        assert result is True
        assert await repo.get_session(session_id) is None

    @pytest.mark.anyio
    async def test_delete_nonexistent_session(self, repo: SessionRepository) -> None:
        result = await repo.delete_session("nonexistent")
        assert result is False

    @pytest.mark.anyio
    async def test_delete_user_sessions(self, repo: SessionRepository) -> None:
        await repo.create_session("user1", "whatsapp")
        await repo.create_session("user1", "telegram")
        count = await repo.delete_user_sessions("user1")
        assert count == 2

    @pytest.mark.anyio
    async def test_add_and_get_messages(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        await repo.add_message(session_id, "user", "Hello!")
        await repo.add_message(session_id, "assistant", "Hey! 💪")
        messages = await repo.get_messages(session_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Hey! 💪"

    @pytest.mark.anyio
    async def test_get_message_count(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        await repo.add_message(session_id, "user", "One")
        await repo.add_message(session_id, "user", "Two")
        count = await repo.get_message_count(session_id)
        assert count == 2

    @pytest.mark.anyio
    async def test_cascade_delete_messages(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        await repo.add_message(session_id, "user", "Hello")
        await repo.delete_session(session_id)
        messages = await repo.get_messages(session_id)
        assert len(messages) == 0

    @pytest.mark.anyio
    async def test_update_metadata(self, repo: SessionRepository) -> None:
        session_id = await repo.create_session("user1", "whatsapp")
        await repo.update_session(session_id, metadata={"key": "value"})
        session = await repo.get_session(session_id)
        assert "key" in session["metadata"]


# ──────────────────────────────────────────
# Knowledge Store Tests
# ──────────────────────────────────────────


class TestKnowledgeStore:
    """Tests for per-member knowledge files."""

    @pytest.fixture
    def knowledge(self, tmp_path: Path) -> KnowledgeStore:
        return KnowledgeStore(str(tmp_path / "knowledge"))

    def test_append_and_get_facts(self, knowledge: KnowledgeStore) -> None:
        knowledge.append_facts("user1", ["Hat Knieprobleme", "Trainiert Yoga"])
        content = knowledge.get_facts("user1")
        assert "Knieprobleme" in content
        assert "Yoga" in content

    def test_append_empty(self, knowledge: KnowledgeStore) -> None:
        count = knowledge.append_facts("user1", [])
        assert count == 0

    def test_get_facts_no_file(self, knowledge: KnowledgeStore) -> None:
        assert knowledge.get_facts("nonexistent") == ""

    def test_has_knowledge(self, knowledge: KnowledgeStore) -> None:
        knowledge.append_facts("user1", ["fact1"])
        assert knowledge.has_knowledge("user1") is True
        assert knowledge.has_knowledge("user2") is False

    def test_delete_member(self, knowledge: KnowledgeStore) -> None:
        knowledge.append_facts("user1", ["fact1"])
        result = knowledge.delete_member("user1")
        assert result is True
        assert knowledge.get_facts("user1") == ""

    def test_delete_nonexistent(self, knowledge: KnowledgeStore) -> None:
        assert knowledge.delete_member("nobody") is False

    def test_list_members(self, knowledge: KnowledgeStore) -> None:
        knowledge.append_facts("user1", ["a"])
        knowledge.append_facts("user2", ["b"])
        members = knowledge.list_members()
        assert "user1" in members
        assert "user2" in members

    def test_multiple_appends(self, knowledge: KnowledgeStore) -> None:
        knowledge.append_facts("user1", ["Fact A"])
        knowledge.append_facts("user1", ["Fact B"])
        content = knowledge.get_facts("user1")
        assert "Fact A" in content
        assert "Fact B" in content


# ──────────────────────────────────────────
# Silent Flush Tests
# ──────────────────────────────────────────


class TestSilentFlush:
    """Tests for context compaction and fact extraction."""

    @pytest.fixture
    def flush_system(self, tmp_path: Path):
        ctx = ConversationContext(max_turns=10)
        knowledge = KnowledgeStore(str(tmp_path / "knowledge"))
        flush = SilentFlush(ctx, knowledge)
        return ctx, knowledge, flush

    def test_extract_facts_from_user_turns(self, flush_system) -> None:
        _, _, flush = flush_system
        turns = [
            Turn(role="user", content="Ich habe Knieschmerzen seit letzter Woche."),
            Turn(role="assistant", content="Das tut mir leid!"),
            Turn(role="user", content="Ich trainiere Yoga jeden Mittwoch."),
        ]
        facts = flush.extract_facts(turns)
        assert len(facts) > 0

    def test_extract_facts_ignores_assistant(self, flush_system) -> None:
        _, _, flush = flush_system
        turns = [Turn(role="assistant", content="Ich habe Knieprobleme")]
        facts = flush.extract_facts(turns)
        assert len(facts) == 0

    def test_create_summary(self, flush_system) -> None:
        _, _, flush = flush_system
        turns = [
            Turn(role="user", content="Wann habt ihr morgen offen?"),
            Turn(role="user", content="Ich möchte Spinning buchen."),
        ]
        summary = flush.create_summary(turns)
        assert "Themen" in summary

    def test_create_summary_empty(self, flush_system) -> None:
        _, _, flush = flush_system
        summary = flush.create_summary([])
        assert "ohne" in summary

    @pytest.mark.anyio
    async def test_flush_when_near_limit(self, flush_system) -> None:
        ctx, knowledge, flush = flush_system
        for i in range(9):
            ctx.add_turn("user1", "user", f"Nachricht Nummer {i} mit langem Inhalt der Fakten enthalten könnte.")
        result = await flush.flush_if_needed("user1")
        assert result is True
        # Context should be compacted
        turns = ctx.get_context("user1")
        assert len(turns) <= 5

    @pytest.mark.anyio
    async def test_no_flush_below_limit(self, flush_system) -> None:
        ctx, _, flush = flush_system
        ctx.add_turn("user1", "user", "Hello")
        result = await flush.flush_if_needed("user1")
        assert result is False


# ──────────────────────────────────────────
# FactGraph Tests
# ──────────────────────────────────────────


class TestFactGraph:
    """Tests for NetworkX knowledge graph."""

    def test_add_and_query(self) -> None:
        graph = FactGraph()
        graph.add_fact("user1", "HAS_INJURY", "Knie")
        graph.add_fact("user1", "TRAINS", "Yoga")
        facts = graph.query_user("user1")
        assert len(facts) == 2
        relations = {f["relation"] for f in facts}
        assert "HAS_INJURY" in relations
        assert "TRAINS" in relations

    def test_query_nonexistent_user(self) -> None:
        graph = FactGraph()
        assert graph.query_user("nobody") == []

    def test_remove_user(self) -> None:
        graph = FactGraph()
        graph.add_fact("user1", "TRAINS", "Yoga")
        result = graph.remove_user("user1")
        assert result is True
        assert graph.query_user("user1") == []

    def test_remove_nonexistent_user(self) -> None:
        graph = FactGraph()
        assert graph.remove_user("nobody") is False

    def test_get_stats(self) -> None:
        graph = FactGraph()
        graph.add_fact("user1", "TRAINS", "Yoga")
        graph.add_fact("user2", "TRAINS", "Spinning")
        stats = graph.get_stats()
        assert stats["members"] == 2
        assert stats["nodes"] >= 4
        assert stats["edges"] >= 2

    def test_shared_entity_not_deleted(self) -> None:
        graph = FactGraph()
        graph.add_fact("user1", "TRAINS", "Yoga")
        graph.add_fact("user2", "TRAINS", "Yoga")
        graph.remove_user("user1")
        # Yoga entity still exists because user2 references it
        facts = graph.query_user("user2")
        assert len(facts) == 1


# ──────────────────────────────────────────
# Consent Manager Tests
# ──────────────────────────────────────────


class TestConsentManager:
    """Tests for GDPR consent enforcement."""

    @pytest.fixture
    async def consent_system(self, tmp_path: Path):
        db = MemoryDB(":memory:")
        await db.init()
        repo = SessionRepository(db)
        knowledge = KnowledgeStore(str(tmp_path / "knowledge"))
        graph = FactGraph()
        context = ConversationContext()
        consent = ConsentManager(repo, knowledge, graph, context)
        yield consent, repo, knowledge, graph, context, db
        await db.close()

    @pytest.mark.anyio
    async def test_check_consent_new_user(self, consent_system) -> None:
        consent, *_ = consent_system
        assert await consent.check_consent("new_user", "whatsapp") is True

    @pytest.mark.anyio
    async def test_grant_consent(self, consent_system) -> None:
        consent, repo, *_ = consent_system
        session_id = await consent.grant_consent("user1", "whatsapp")
        assert session_id.startswith("sess-")
        session = await repo.get_session(session_id)
        assert session["consent_status"] == "granted"

    @pytest.mark.anyio
    async def test_grant_consent_existing_session(self, consent_system) -> None:
        consent, repo, *_ = consent_system
        s1 = await consent.grant_consent("user1", "whatsapp")
        s2 = await consent.grant_consent("user1", "whatsapp")
        assert s1 == s2  # Same session, not new

    @pytest.mark.anyio
    async def test_check_consent_revoked(self, consent_system) -> None:
        consent, repo, *_ = consent_system
        session_id = await consent.grant_consent("user1", "whatsapp")
        await repo.update_session(session_id, consent_status="revoked")
        assert await consent.check_consent("user1", "whatsapp") is False

    @pytest.mark.anyio
    async def test_revoke_cascade_delete(self, consent_system) -> None:
        consent, repo, knowledge, graph, context, _ = consent_system

        # Set up data across all tiers
        context.add_turn("user1", "user", "Hello")
        await consent.grant_consent("user1", "whatsapp")
        knowledge.append_facts("user1", ["Fact 1"])
        graph.add_fact("user1", "TRAINS", "Yoga")

        # Revoke
        result = await consent.revoke_consent("user1", "whatsapp")

        assert result["context_cleared"] == 1
        assert result["sessions_deleted"] >= 1
        assert result["knowledge_deleted"] == 1
        assert result["graph_removed"] == 1

        # Verify everything is deleted
        assert context.get_context("user1") == []
        assert knowledge.get_facts("user1") == ""
        assert graph.query_user("user1") == []
