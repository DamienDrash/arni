from __future__ import annotations

from app.domains.knowledge.module import get_knowledge_routers


def test_knowledge_module_assembly_includes_ingestion_and_media_surfaces() -> None:
    routers = get_knowledge_routers()
    prefixes = {getattr(router, "prefix", "") for router in routers}
    paths = {
        route.path
        for router in routers
        for route in getattr(router, "routes", [])
        if hasattr(route, "path")
    }

    assert "/admin/media" in prefixes
    assert "/knowledge/upload" in paths
    assert "/knowledge/jobs" in paths
