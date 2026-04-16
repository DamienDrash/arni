from __future__ import annotations

import asyncio

import pytest

from app.edge.health import build_workers_health
from app.worker_runtime.loop_supervisor import compute_restart_backoff, run_supervised_loop
from app.worker_runtime.runtime_state import runtime_state
from app.worker_runtime.main import build_worker_map, describe_active_workers, list_active_worker_names


def test_worker_runtime_discovers_only_active_module_workers() -> None:
    worker_map = build_worker_map()

    assert "ingestion" in worker_map
    assert "campaign" in worker_map
    assert "analytics" in worker_map
    assert "automation" in worker_map
    assert "contact-sync-scheduler" in worker_map
    assert "member-memory-scheduler" in worker_map
    assert "magicline-sync-scheduler" in worker_map
    assert "voice" not in worker_map
    assert worker_map["campaign"].kind == "arq"
    assert worker_map["contact-sync-scheduler"].kind == "async"


def test_worker_runtime_lists_sorted_active_workers() -> None:
    assert list_active_worker_names() == sorted(list_active_worker_names())


def test_worker_runtime_describes_active_workers_for_health() -> None:
    descriptions = describe_active_workers()

    assert any(item["name"] == "ingestion" and item["kind"] == "arq" for item in descriptions)
    assert any(item["name"] == "contact-sync-scheduler" and item["kind"] == "async" for item in descriptions)


async def test_worker_health_reports_active_worker_runtime() -> None:
    payload = await build_workers_health()

    assert payload["status"] == "up"
    assert payload["component"] == "worker_runtime"
    assert payload["worker_count"] >= 1
    assert any(worker["name"] == "magicline-sync-scheduler" for worker in payload["active_workers"])


def test_worker_runtime_backoff_is_exponential_and_capped() -> None:
    assert compute_restart_backoff(1) == 5
    assert compute_restart_backoff(2) == 10
    assert compute_restart_backoff(3) == 20
    assert compute_restart_backoff(20) == 300


async def test_supervised_loop_records_failure_and_restart(monkeypatch) -> None:
    runtime_state._workers.clear()
    calls = {"count": 0}

    async def _fake_sleep(_seconds: int) -> None:
        return None

    async def _loop() -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        raise asyncio.CancelledError()

    monkeypatch.setattr("app.worker_runtime.loop_supervisor.asyncio.sleep", _fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await run_supervised_loop("test-loop", _loop)

    snapshot = {item["name"]: item for item in runtime_state.snapshot()}
    assert snapshot["test-loop"]["failure_count"] == 1
    assert snapshot["test-loop"]["restart_count"] >= 2
    assert snapshot["test-loop"]["last_error"] == "boom"
