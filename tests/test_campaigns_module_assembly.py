from __future__ import annotations

from app.domains.campaigns.module import get_campaign_routers


def test_campaigns_module_assembly_includes_optin_and_tracking_surfaces() -> None:
    routers = get_campaign_routers()
    prefixes = {getattr(router, "prefix", "") for router in routers}
    paths = {
        route.path
        for router in routers
        for route in getattr(router, "routes", [])
        if hasattr(route, "path")
    }

    assert "/admin/campaigns" in prefixes
    assert "/v2/admin/templates" in prefixes
    assert "/admin/campaign-offers" in prefixes
    assert "/webhooks/campaigns" in prefixes
    assert "/public" in prefixes
    assert "/tracking/open/{recipient_id}" in paths
    assert "/tracking/click/{recipient_id}" in paths
    assert "/unsubscribe/{recipient_id}" in paths
