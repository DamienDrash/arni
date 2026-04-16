from __future__ import annotations

import app.worker.main as legacy_worker_main
import app.worker_runtime.main as runtime_worker_main


def test_worker_main_compat_shim_delegates_to_runtime_entrypoint() -> None:
    assert legacy_worker_main.main is runtime_worker_main.main


def test_worker_main_compat_shim_lists_same_workers() -> None:
    assert runtime_worker_main.list_active_worker_names()
    assert legacy_worker_main.main.__module__ == "app.worker_runtime.main"
