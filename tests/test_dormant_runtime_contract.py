from __future__ import annotations

from app.edge.app import app as edge_app
from app.gateway.main import app as gateway_app


def _paths(app) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_dormant_voice_routes_are_not_booted_in_gateway_runtime() -> None:
    paths = _paths(gateway_app)

    assert "/voice/incoming/{tenant_slug}" not in paths
    assert "/voice/stream/{tenant_slug}" not in paths


def test_dormant_ab_testing_routes_are_not_booted_in_edge_runtime() -> None:
    paths = _paths(edge_app)

    assert not any(path.startswith("/v2/admin/ab-tests") for path in paths)
