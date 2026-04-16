from __future__ import annotations

from app.domains.platform.module import get_tenant_management_routers


def test_platform_module_assembly_includes_tenant_management_surfaces() -> None:
    routers = get_tenant_management_routers()
    prefixes = {getattr(router, "prefix", "") for router in routers}

    assert "/api/v1/tenant/portal" in prefixes
    assert "/api/v1/marketplace" in prefixes
    assert "/api/v1/analytics" in prefixes
    assert "/api/v1/tenant/ai" in prefixes
