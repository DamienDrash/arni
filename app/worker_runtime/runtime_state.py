"""Shared runtime state for worker-runtime loop workers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class WorkerRuntimeState:
    """In-memory state for worker-runtime loop supervision and health."""

    def __init__(self) -> None:
        self._workers: dict[str, dict[str, Any]] = {}

    def mark_started(self, name: str) -> None:
        worker = self._workers.setdefault(name, self._fresh_state(name))
        worker["status"] = "running"
        worker["last_started_at"] = datetime.now(timezone.utc).isoformat()
        worker["restart_count"] = int(worker.get("restart_count", 0)) + 1

    def mark_failed(self, name: str, error: str) -> None:
        worker = self._workers.setdefault(name, self._fresh_state(name))
        worker["status"] = "degraded"
        worker["last_error"] = error[:500]
        worker["last_failed_at"] = datetime.now(timezone.utc).isoformat()
        worker["failure_count"] = int(worker.get("failure_count", 0)) + 1

    def mark_stopped(self, name: str) -> None:
        worker = self._workers.setdefault(name, self._fresh_state(name))
        worker["status"] = "stopped"
        worker["last_stopped_at"] = datetime.now(timezone.utc).isoformat()

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(worker) for _, worker in sorted(self._workers.items())]

    @staticmethod
    def _fresh_state(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": "registered",
            "restart_count": 0,
            "failure_count": 0,
            "last_error": None,
            "last_started_at": None,
            "last_failed_at": None,
            "last_stopped_at": None,
        }


runtime_state = WorkerRuntimeState()

