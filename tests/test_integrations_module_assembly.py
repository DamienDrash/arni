from __future__ import annotations

from app.domains.integrations.module import (
    get_calendly_routers,
    get_magicline_routers,
    get_telegram_routers,
    get_whatsapp_routers,
)


def test_integrations_module_assembly_exposes_active_router_surfaces() -> None:
    magicline_prefixes = {getattr(router, "prefix", "") for router in get_magicline_routers()}
    whatsapp_paths = {
        route.path
        for router in get_whatsapp_routers()
        for route in getattr(router, "routes", [])
        if hasattr(route, "path")
    }

    assert "/api/v1/integrations" in magicline_prefixes
    assert "/webhook/whatsapp" in whatsapp_paths
    assert "/webhook/whatsapp/{tenant_slug}" in whatsapp_paths
    assert get_telegram_routers() == []
    assert get_calendly_routers() == []
