"""Platform domain runtime assembly."""

from __future__ import annotations

from typing import Any


def get_tenant_management_routers() -> list[Any]:
    from app.ai_config.router import tenant_router as ai_tenant
    from app.billing.admin_router import router as plans
    from app.billing.router import router as v2_billing
    from app.gateway.routers.llm_costs import router as llm_costs
    from app.platform.api.analytics import router as plat_analytics
    from app.platform.api.marketplace import router as market
    from app.platform.api.tenant_portal import router as portal

    return [portal, market, v2_billing, plans, plat_analytics, llm_costs, ai_tenant]


__all__ = ["get_tenant_management_routers"]
