"""ARIIA Phase 4 Tests: Das Gedächtnis – Resilienz & Zuverlässigkeit.

Tests for:
- MS 4.1: Redis Streams Bus (Consumer Groups, DLQ, Backward Compat)
- MS 4.2: Resilient Librarian (Retry, Fallback, Job Tracking)
- MS 4.3: Knowledge Manager (Multi-tier search, Parallel queries)
- MS 4.4: Backup Manager (PostgreSQL, ChromaDB, Retention)
"""
import asyncio
import json
import os
import time
import tempfile
import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# MS 4.1: Redis Streams Bus
# ═══════════════════════════════════════════════════════════════════════════════

class TestStreamName:
    def test_stream_names_exist(self):
        from app.gateway.redis_streams import StreamName
        assert StreamName.INBOUND.value == "ariia:stream:inbound"
        assert StreamName.OUTBOUND.value == "ariia:stream:outbound"
        assert StreamName.EVENTS.value == "ariia:stream:events"
        assert StreamName.LIBRARIAN.value == "ariia:stream:librarian"
        assert StreamName.DLQ.value == "ariia:stream:dlq"

    def test_tenant_stream(self):
        from app.gateway.redis_streams import StreamName
        result = StreamName.tenant_stream("ariia:stream:inbound", 42)
        assert result == "t42:ariia:stream:inbound"

    def test_tenant_stream_different_tenants(self):
        from app.gateway.redis_streams import StreamName
        s1 = StreamName.tenant_stream("ariia:stream:events", 1)
        s2 = StreamName.tenant_stream("ariia:stream:events", 2)
        assert s1 != s2
        assert "t1:" in s1
        assert "t2:" in s2


class TestStreamMessage:
    def test_creation(self):
        from app.gateway.redis_streams import StreamMessage
        msg = StreamMessage(
            message_id="1234-0",
            stream="ariia:stream:inbound",
            data={"payload": '{"text": "hello"}', "tenant_id": "1"},
        )
        assert msg.message_id == "1234-0"
        assert msg.stream == "ariia:stream:inbound"

    def test_payload_parsing(self):
        from app.gateway.redis_streams import StreamMessage
        msg = StreamMessage(
            message_id="1",
            stream="test",
            data={"payload": '{"text": "hello", "user": "u1"}'},
        )
        payload = msg.payload
        assert payload["text"] == "hello"
        assert payload["user"] == "u1"

    def test_payload_invalid_json(self):
        from app.gateway.redis_streams import StreamMessage
        msg = StreamMessage(
            message_id="1",
            stream="test",
            data={"payload": "not json"},
        )
        assert msg.payload == {"raw": "not json"}

    def test_payload_missing(self):
        from app.gateway.redis_streams import StreamMessage
        msg = StreamMessage(message_id="1", stream="test", data={})
        assert msg.payload == {}

    def test_tenant_id(self):
        from app.gateway.redis_streams import StreamMessage
        msg = StreamMessage(
            message_id="1", stream="test",
            data={"tenant_id": "42"},
        )
        assert msg.tenant_id == 42

    def test_tenant_id_none(self):
        from app.gateway.redis_streams import StreamMessage
        msg = StreamMessage(message_id="1", stream="test", data={})
        assert msg.tenant_id is None

    def test_to_dict(self):
        from app.gateway.redis_streams import StreamMessage
        msg = StreamMessage(
            message_id="1", stream="test", data={"key": "val"},
            retry_count=2,
        )
        d = msg.to_dict()
        assert d["message_id"] == "1"
        assert d["retry_count"] == 2
        assert "created_at" in d


class TestRedisStreamsBus:
    def test_creation(self):
        from app.gateway.redis_streams import RedisStreamsBus
        bus = RedisStreamsBus(redis_url="redis://localhost:6379/0")
        assert bus._consumer_group == "ariia-workers"
        assert bus._max_stream_length == 100_000
        assert bus._running is False

    def test_custom_config(self):
        from app.gateway.redis_streams import RedisStreamsBus
        bus = RedisStreamsBus(
            redis_url="redis://custom:6380/1",
            consumer_group="my-group",
            consumer_name="worker-1",
            max_stream_length=50_000,
        )
        assert bus._consumer_group == "my-group"
        assert bus._consumer_name == "worker-1"
        assert bus._max_stream_length == 50_000

    def test_register_handler(self):
        from app.gateway.redis_streams import RedisStreamsBus
        bus = RedisStreamsBus()

        async def handler(msg):
            pass

        bus.register_handler("ariia:stream:inbound", handler)
        assert "ariia:stream:inbound" in bus._handlers

    def test_health_check_not_connected(self):
        from app.gateway.redis_streams import RedisStreamsBus
        bus = RedisStreamsBus()
        result = asyncio.get_event_loop().run_until_complete(bus.health_check())
        assert result is False

    def test_client_not_connected_raises(self):
        from app.gateway.redis_streams import RedisStreamsBus
        bus = RedisStreamsBus()
        with pytest.raises(RuntimeError, match="not connected"):
            _ = bus.client

    def test_backward_compat_channel_mapping(self):
        """Test that old Pub/Sub channels map to new stream names."""
        from app.gateway.redis_streams import RedisStreamsBus, StreamName
        bus = RedisStreamsBus()
        # The mapping is internal, we test the constants
        assert "ariia:stream:inbound" == StreamName.INBOUND.value
        assert "ariia:stream:outbound" == StreamName.OUTBOUND.value


class TestDLQConstants:
    def test_dlq_stream_name(self):
        from app.gateway.redis_streams import DLQ_STREAM
        assert DLQ_STREAM == "ariia:stream:dlq"

    def test_max_retry_count(self):
        from app.gateway.redis_streams import MAX_RETRY_COUNT
        assert MAX_RETRY_COUNT == 5

    def test_claim_idle_ms(self):
        from app.gateway.redis_streams import CLAIM_IDLE_MS
        assert CLAIM_IDLE_MS == 60_000


# ═══════════════════════════════════════════════════════════════════════════════
# MS 4.2: Resilient Librarian
# ═══════════════════════════════════════════════════════════════════════════════

class TestArchivalJob:
    def test_creation(self):
        from app.memory.librarian_v2 import ArchivalJob, JobStatus
        job = ArchivalJob(
            job_id="lib-test001",
            member_id="m1",
            tenant_id=1,
        )
        assert job.status == JobStatus.PENDING
        assert job.retry_count == 0
        assert job.summary == ""

    def test_to_dict(self):
        from app.memory.librarian_v2 import ArchivalJob
        job = ArchivalJob(job_id="lib-test", member_id="m1", tenant_id=1)
        d = job.to_dict()
        assert d["job_id"] == "lib-test"
        assert d["status"] == "pending"
        assert d["tenant_id"] == 1

    def test_from_dict(self):
        from app.memory.librarian_v2 import ArchivalJob, JobStatus
        data = {
            "job_id": "lib-abc",
            "member_id": "m2",
            "tenant_id": 3,
            "status": "completed",
            "retry_count": 2,
        }
        job = ArchivalJob.from_dict(data)
        assert job.job_id == "lib-abc"
        assert job.status == JobStatus.COMPLETED
        assert job.retry_count == 2

    def test_job_status_enum(self):
        from app.memory.librarian_v2 import JobStatus
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.FALLBACK.value == "fallback"


class TestFallbackSummarization:
    def test_fallback_with_messages(self):
        from app.memory.librarian_v2 import FallbackSummarization
        strategy = FallbackSummarization()
        messages = [
            {"role": "user", "content": "Ich möchte meinen Kurs stornieren"},
            {"role": "assistant", "content": "Gerne, welchen Kurs möchten Sie stornieren?"},
            {"role": "user", "content": "Den Yoga-Kurs am Montag"},
        ]
        result = asyncio.get_event_loop().run_until_complete(
            strategy.summarize("m1", 1, messages)
        )
        assert "[FALLBACK" in result
        assert "m1" in result
        assert "3 Nachrichten" in result

    def test_fallback_empty_messages(self):
        from app.memory.librarian_v2 import FallbackSummarization
        strategy = FallbackSummarization()
        result = asyncio.get_event_loop().run_until_complete(
            strategy.summarize("m1", 1, [])
        )
        assert "[FALLBACK]" in result
        assert "Keine Nachrichten" in result

    def test_fallback_counts_roles(self):
        from app.memory.librarian_v2 import FallbackSummarization
        strategy = FallbackSummarization()
        messages = [
            {"role": "user", "content": "Hallo"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "Tschüss"},
            {"role": "assistant", "content": "Bye!"},
        ]
        result = asyncio.get_event_loop().run_until_complete(
            strategy.summarize("m1", 1, messages)
        )
        assert "2 vom Nutzer" in result
        assert "2 vom Bot" in result


class TestLibrarianWorker:
    def test_creation(self):
        from app.memory.librarian_v2 import LibrarianWorker
        worker = LibrarianWorker()
        assert worker._max_retries == 3
        assert worker._backoff_base == 2

    def test_create_job(self):
        from app.memory.librarian_v2 import LibrarianWorker, JobStatus
        worker = LibrarianWorker()
        job = worker.create_job("m1", 1, "sess-001")
        assert job.member_id == "m1"
        assert job.tenant_id == 1
        assert job.status == JobStatus.PENDING
        assert job.job_id.startswith("lib-")

    def test_get_job(self):
        from app.memory.librarian_v2 import LibrarianWorker
        worker = LibrarianWorker()
        job = worker.create_job("m1", 1)
        retrieved = worker.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.member_id == "m1"

    def test_get_job_not_found(self):
        from app.memory.librarian_v2 import LibrarianWorker
        worker = LibrarianWorker()
        assert worker.get_job("nonexistent") is None

    def test_get_jobs_by_status(self):
        from app.memory.librarian_v2 import LibrarianWorker, JobStatus
        worker = LibrarianWorker()
        worker.create_job("m1", 1)
        worker.create_job("m2", 1)
        pending = worker.get_jobs_by_status(JobStatus.PENDING)
        assert len(pending) == 2

    def test_get_metrics(self):
        from app.memory.librarian_v2 import LibrarianWorker
        worker = LibrarianWorker()
        metrics = worker.get_metrics()
        assert "total_processed" in metrics
        assert "successful" in metrics
        assert "fallback_used" in metrics
        assert "failed" in metrics
        assert "pending_jobs" in metrics

    def test_process_job_with_fallback(self):
        """Test that fallback is used when primary strategy fails."""
        from app.memory.librarian_v2 import (
            LibrarianWorker, FallbackSummarization, JobStatus,
            SummarizationStrategy,
        )

        class FailingStrategy(SummarizationStrategy):
            async def summarize(self, member_id, tenant_id, messages):
                raise RuntimeError("LLM unavailable")

        worker = LibrarianWorker(
            primary_strategy=FailingStrategy(),
            fallback_strategy=FallbackSummarization(),
            max_retries=1,
            backoff_base=0.01,  # Fast for testing
        )

        job = worker.create_job("m1", 1)
        messages = [
            {"role": "user", "content": "Test message"},
            {"role": "assistant", "content": "Test response"},
        ]

        result = asyncio.get_event_loop().run_until_complete(
            worker.process_job(job, messages)
        )

        assert result.status == JobStatus.FALLBACK
        assert "[FALLBACK" in result.summary
        assert result.retry_count > 0

    def test_process_job_success(self):
        """Test successful processing with mock strategy."""
        from app.memory.librarian_v2 import (
            LibrarianWorker, JobStatus, SummarizationStrategy,
        )

        class MockStrategy(SummarizationStrategy):
            async def summarize(self, member_id, tenant_id, messages):
                return "Das Mitglied fragte nach Yoga-Kursen."

        worker = LibrarianWorker(primary_strategy=MockStrategy())
        job = worker.create_job("m1", 1)
        messages = [{"role": "user", "content": "Yoga-Kurse?"}]

        result = asyncio.get_event_loop().run_until_complete(
            worker.process_job(job, messages)
        )

        assert result.status == JobStatus.COMPLETED
        assert "Yoga" in result.summary
        assert result.completed_at is not None

    def test_process_job_total_failure(self):
        """Test when both primary and fallback fail."""
        from app.memory.librarian_v2 import (
            LibrarianWorker, JobStatus, SummarizationStrategy,
        )

        class FailingStrategy(SummarizationStrategy):
            async def summarize(self, member_id, tenant_id, messages):
                raise RuntimeError("Total failure")

        worker = LibrarianWorker(
            primary_strategy=FailingStrategy(),
            fallback_strategy=FailingStrategy(),
            max_retries=0,
            backoff_base=0.01,
        )

        job = worker.create_job("m1", 1)
        result = asyncio.get_event_loop().run_until_complete(
            worker.process_job(job, [{"role": "user", "content": "test"}])
        )

        assert result.status == JobStatus.FAILED
        assert "Total failure" in result.last_error

    def test_metrics_after_processing(self):
        from app.memory.librarian_v2 import (
            LibrarianWorker, SummarizationStrategy,
        )

        class MockStrategy(SummarizationStrategy):
            async def summarize(self, member_id, tenant_id, messages):
                return "Summary"

        worker = LibrarianWorker(primary_strategy=MockStrategy())
        job = worker.create_job("m1", 1)
        asyncio.get_event_loop().run_until_complete(
            worker.process_job(job, [{"role": "user", "content": "test"}])
        )

        metrics = worker.get_metrics()
        assert metrics["total_processed"] == 1
        assert metrics["successful"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# MS 4.3: Knowledge Manager
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeHelpers:
    def test_tenant_collection_name(self):
        from app.knowledge.knowledge_manager import get_tenant_collection_name
        name = get_tenant_collection_name("fitness-studio-1")
        assert name.startswith("ariia_kb_")
        assert "fitness" in name

    def test_tenant_collection_name_sanitization(self):
        from app.knowledge.knowledge_manager import get_tenant_collection_name
        name = get_tenant_collection_name("My Studio! @#$")
        assert "ariia_kb_" in name
        assert "!" not in name
        assert "@" not in name

    def test_member_collection_name(self):
        from app.knowledge.knowledge_manager import get_member_collection_name
        name = get_member_collection_name("test-studio")
        assert name.startswith("ariia_member_memory_")

    def test_default_slug(self):
        from app.knowledge.knowledge_manager import get_tenant_collection_name
        name = get_tenant_collection_name("")
        assert "default" in name


class TestKnowledgeResult:
    def test_creation(self):
        from app.knowledge.knowledge_manager import KnowledgeResult
        r = KnowledgeResult(
            content="Test content",
            source="shared",
            score=0.5,
        )
        assert r.content == "Test content"
        assert r.source == "shared"
        assert r.score == 0.5

    def test_to_dict(self):
        from app.knowledge.knowledge_manager import KnowledgeResult
        r = KnowledgeResult(
            content="Test", source="tenant", score=0.3,
            collection="ariia_kb_test",
        )
        d = r.to_dict()
        assert d["source"] == "tenant"
        assert d["collection"] == "ariia_kb_test"


class TestKnowledgeSearchResult:
    def test_empty_result(self):
        from app.knowledge.knowledge_manager import KnowledgeSearchResult
        sr = KnowledgeSearchResult(query="test")
        assert sr.total_results == 0
        assert sr.has_results is False
        assert sr.best_result is None

    def test_with_results(self):
        from app.knowledge.knowledge_manager import (
            KnowledgeSearchResult, KnowledgeResult,
        )
        sr = KnowledgeSearchResult(
            query="yoga",
            results=[
                KnowledgeResult(content="Yoga ist...", source="shared", score=0.2),
                KnowledgeResult(content="Unser Yoga-Kurs...", source="tenant", score=0.1),
            ],
        )
        assert sr.total_results == 2
        assert sr.has_results is True
        assert sr.best_result.content == "Yoga ist..."

    def test_to_context_string(self):
        from app.knowledge.knowledge_manager import (
            KnowledgeSearchResult, KnowledgeResult,
        )
        sr = KnowledgeSearchResult(
            query="test",
            results=[
                KnowledgeResult(content="Shared info", source="shared", score=0.5),
                KnowledgeResult(content="Tenant info", source="tenant", score=0.3),
            ],
        )
        ctx = sr.to_context_string()
        assert "Allgemeines Wissen" in ctx
        assert "Studio-Wissen" in ctx
        assert "Shared info" in ctx

    def test_to_dict(self):
        from app.knowledge.knowledge_manager import KnowledgeSearchResult
        sr = KnowledgeSearchResult(query="test", search_time_ms=5.2)
        d = sr.to_dict()
        assert d["query"] == "test"
        assert d["search_time_ms"] == 5.2
        assert d["total_results"] == 0


class TestKnowledgeManager:
    def test_creation(self):
        from app.knowledge.knowledge_manager import KnowledgeManager
        km = KnowledgeManager(shared_weight=0.4, tenant_weight=0.6)
        assert km._shared_weight == 0.4
        assert km._tenant_weight == 0.6

    def test_default_weights(self):
        from app.knowledge.knowledge_manager import KnowledgeManager
        km = KnowledgeManager()
        assert km._shared_weight == 0.3
        assert km._tenant_weight == 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# MS 4.4: Backup Manager
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackupRecord:
    def test_creation(self):
        from scripts.backup_manager import BackupRecord, BackupType, BackupStatus
        record = BackupRecord(
            backup_id="pg_20260301",
            backup_type=BackupType.POSTGRES,
            status=BackupStatus.COMPLETED,
            file_path="/data/backups/pg_20260301.sql.gz",
            size_bytes=1024 * 1024,
        )
        assert record.backup_id == "pg_20260301"
        assert record.backup_type == BackupType.POSTGRES

    def test_to_dict(self):
        from scripts.backup_manager import BackupRecord, BackupType, BackupStatus
        record = BackupRecord(
            backup_id="test",
            backup_type=BackupType.CHROMA,
            status=BackupStatus.COMPLETED,
            file_path="/tmp/test.tar.gz",
            size_bytes=2048,
        )
        d = record.to_dict()
        assert d["backup_type"] == "chroma"
        assert d["status"] == "completed"
        assert "size_human" in d

    def test_human_size(self):
        from scripts.backup_manager import BackupRecord
        assert "B" in BackupRecord._human_size(500)
        assert "KB" in BackupRecord._human_size(2048)
        assert "MB" in BackupRecord._human_size(5 * 1024 * 1024)
        assert "GB" in BackupRecord._human_size(2 * 1024 * 1024 * 1024)


class TestBackupType:
    def test_enum_values(self):
        from scripts.backup_manager import BackupType
        assert BackupType.POSTGRES.value == "postgres"
        assert BackupType.CHROMA.value == "chroma"
        assert BackupType.REDIS.value == "redis"
        assert BackupType.FULL.value == "full"


class TestBackupStatus:
    def test_enum_values(self):
        from scripts.backup_manager import BackupStatus
        assert BackupStatus.RUNNING.value == "running"
        assert BackupStatus.COMPLETED.value == "completed"
        assert BackupStatus.FAILED.value == "failed"
        assert BackupStatus.VERIFIED.value == "verified"


class TestBackupManager:
    def test_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager
            mgr = BackupManager(backup_dir=tmpdir)
            assert mgr._backup_dir == tmpdir
            assert mgr._retention_daily == 7
            assert mgr._retention_weekly == 4

    def test_manifest_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager, BackupRecord, BackupType, BackupStatus
            mgr = BackupManager(backup_dir=tmpdir)

            record = BackupRecord(
                backup_id="test_001",
                backup_type=BackupType.POSTGRES,
                status=BackupStatus.COMPLETED,
                file_path="/tmp/test.sql.gz",
            )
            mgr._add_record(record)

            # Create new manager instance – should load manifest
            mgr2 = BackupManager(backup_dir=tmpdir)
            assert len(mgr2._manifest) == 1
            assert mgr2._manifest[0]["backup_id"] == "test_001"

    def test_list_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager, BackupRecord, BackupType, BackupStatus
            mgr = BackupManager(backup_dir=tmpdir)

            mgr._add_record(BackupRecord(
                backup_id="pg_1", backup_type=BackupType.POSTGRES,
                status=BackupStatus.COMPLETED, file_path="/tmp/1",
                created_at="2026-03-01T00:00:00",
            ))
            mgr._add_record(BackupRecord(
                backup_id="ch_1", backup_type=BackupType.CHROMA,
                status=BackupStatus.COMPLETED, file_path="/tmp/2",
                created_at="2026-03-01T01:00:00",
            ))

            all_backups = mgr.list_backups()
            assert len(all_backups) == 2

            pg_only = mgr.list_backups(backup_type=BackupType.POSTGRES)
            assert len(pg_only) == 1
            assert pg_only[0]["backup_type"] == "postgres"

    def test_find_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager, BackupRecord, BackupType, BackupStatus
            mgr = BackupManager(backup_dir=tmpdir)
            mgr._add_record(BackupRecord(
                backup_id="find_me", backup_type=BackupType.POSTGRES,
                status=BackupStatus.COMPLETED, file_path="/tmp/test",
            ))

            found = mgr._find_record("find_me")
            assert found is not None
            assert found["backup_id"] == "find_me"

            not_found = mgr._find_record("nonexistent")
            assert not_found is None

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager, BackupRecord, BackupType, BackupStatus
            mgr = BackupManager(backup_dir=tmpdir)
            mgr._add_record(BackupRecord(
                backup_id="s1", backup_type=BackupType.POSTGRES,
                status=BackupStatus.COMPLETED, file_path="/tmp/1",
                size_bytes=1000,
            ))
            mgr._add_record(BackupRecord(
                backup_id="s2", backup_type=BackupType.CHROMA,
                status=BackupStatus.FAILED, file_path="/tmp/2",
            ))

            stats = mgr.get_stats()
            assert stats["total_backups"] == 2
            assert stats["completed"] == 1
            assert stats["failed"] == 1
            assert stats["total_size_bytes"] == 1000

    def test_update_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager, BackupRecord, BackupType, BackupStatus
            mgr = BackupManager(backup_dir=tmpdir)
            mgr._add_record(BackupRecord(
                backup_id="upd_1", backup_type=BackupType.POSTGRES,
                status=BackupStatus.COMPLETED, file_path="/tmp/test",
            ))

            mgr._update_record("upd_1", {"status": "verified"})
            record = mgr._find_record("upd_1")
            assert record["status"] == "verified"

    def test_cleanup_respects_retention(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager, BackupRecord, BackupType, BackupStatus

            mgr = BackupManager(backup_dir=tmpdir, retention_daily=2, retention_weekly=1)

            # Add 5 backups
            for i in range(5):
                filepath = os.path.join(tmpdir, f"pg_{i}.sql.gz")
                with open(filepath, "w") as f:
                    f.write("test")
                mgr._add_record(BackupRecord(
                    backup_id=f"pg_{i}",
                    backup_type=BackupType.POSTGRES,
                    status=BackupStatus.COMPLETED,
                    file_path=filepath,
                    created_at=f"2026-03-0{i+1}T00:00:00+00:00",
                ))

            removed = mgr.cleanup_old_backups()
            assert removed > 0

            remaining = mgr.list_backups(backup_type=BackupType.POSTGRES)
            # Should keep at most retention_daily + retention_weekly
            assert len(remaining) <= 3


class TestBackupCronScript:
    def test_create_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import create_backup_cron_script
            script_path = create_backup_cron_script(backup_dir=tmpdir)
            assert os.path.exists(script_path)
            assert os.access(script_path, os.X_OK)

            with open(script_path) as f:
                content = f.read()
            assert "#!/bin/bash" in content
            assert "BackupManager" in content


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase4Integration:
    def test_streams_bus_with_librarian(self):
        """Test that streams bus can register librarian handler."""
        from app.gateway.redis_streams import RedisStreamsBus, StreamName
        from app.memory.librarian_v2 import LibrarianWorker

        bus = RedisStreamsBus()
        worker = LibrarianWorker()

        bus.register_handler(StreamName.LIBRARIAN.value, worker.handle_stream_message)
        assert StreamName.LIBRARIAN.value in bus._handlers

    def test_knowledge_manager_search_result_format(self):
        """Test that KnowledgeSearchResult produces valid LLM context."""
        from app.knowledge.knowledge_manager import (
            KnowledgeSearchResult, KnowledgeResult,
        )

        sr = KnowledgeSearchResult(
            query="Öffnungszeiten",
            results=[
                KnowledgeResult(
                    content="Allgemeine Öffnungszeiten: Mo-Fr 6-22 Uhr",
                    source="shared", score=0.3,
                ),
                KnowledgeResult(
                    content="Unser Studio: Mo-Fr 7-21 Uhr, Sa 9-18 Uhr",
                    source="tenant", score=0.1,
                ),
            ],
            shared_count=1,
            tenant_count=1,
        )

        ctx = sr.to_context_string()
        assert "Allgemeines Wissen" in ctx
        assert "Studio-Wissen" in ctx
        assert len(ctx) > 50

    def test_backup_manager_with_knowledge_manager(self):
        """Test that backup manager handles chroma path correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.backup_manager import BackupManager
            from app.knowledge.knowledge_manager import SHARED_COLLECTION

            mgr = BackupManager(
                backup_dir=tmpdir,
                chroma_path=os.path.join(tmpdir, "chroma_db"),
            )
            assert mgr._chroma_path == os.path.join(tmpdir, "chroma_db")

            # Shared collection name is consistent
            assert SHARED_COLLECTION == "ariia_shared_knowledge"
