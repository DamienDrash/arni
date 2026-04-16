"""ARIIA – Dedicated worker runtime boot path.

Starts only workers that are exposed by capability-active modules.
This keeps API and worker startup concerns separate while preserving the
legacy worker names used by existing ops scripts.
"""

from __future__ import annotations

import asyncio
import sys

import structlog

from app.core.module_registry import ModuleDefinition, WorkerDefinition, registry

logger = structlog.get_logger()


def _ensure_registry_populated() -> None:
    if registry.get_modules():
        return
    from app.edge import registry_setup  # noqa: F401


def build_worker_map() -> dict[str, WorkerDefinition]:
    _ensure_registry_populated()
    workers: dict[str, WorkerDefinition] = {}
    for module in registry.get_active_modules():
        for worker in module.get_workers():
            workers[worker.name] = worker
    return workers


def get_worker_definition(name: str) -> WorkerDefinition:
    worker_map = build_worker_map()
    try:
        return worker_map[name]
    except KeyError as exc:
        logger.error(
            "worker_runtime.unknown_worker",
            worker=name,
            available=sorted(worker_map),
        )
        raise SystemExit(1) from exc


def list_active_worker_names() -> list[str]:
    return sorted(build_worker_map())


def describe_active_workers() -> list[dict[str, str]]:
    workers = build_worker_map()
    return [
        {
            "name": worker.name,
            "kind": worker.kind,
            "module_path": worker.module_path,
            "target": worker.class_name,
        }
        for _, worker in sorted(workers.items())
    ]


def _parse_worker_name(argv: list[str]) -> str:
    worker_name = "ingestion"
    if "--worker" in argv:
        idx = argv.index("--worker")
        if idx + 1 < len(argv):
            worker_name = argv[idx + 1]
    return worker_name


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--list-workers" in args:
        for name in list_active_worker_names():
            print(name)
        return

    worker_name = _parse_worker_name(args)
    worker = get_worker_definition(worker_name)
    logger.info(
        "worker_runtime.starting",
        worker=worker.name,
        settings_class=worker.class_name,
        active_workers=list_active_worker_names(),
    )
    if worker.kind == "async":
        asyncio.run(worker.load_target()())
        return

    from arq import run_worker

    run_worker(worker.load_target())


if __name__ == "__main__":
    main()
