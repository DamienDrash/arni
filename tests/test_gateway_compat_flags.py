from __future__ import annotations

from app.edge.app import create_app
from app.gateway.main import apply_legacy_compat_routes, settings


def _paths(app) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_legacy_cutover_flags_can_disable_current_compat_aliases(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_legacy_health_endpoint", False)
    monkeypatch.setattr(settings, "enable_legacy_telegram_webhook_alias", False)
    monkeypatch.setattr(settings, "enable_legacy_billing_admin_alias", False)
    monkeypatch.setattr(settings, "enable_legacy_ws_control", False)

    test_app = create_app()
    apply_legacy_compat_routes(test_app)
    paths = _paths(test_app)

    # `/health`, `/webhook/telegram`, and `/admin/billing/plans` are still
    # canonical runtime paths today. `/ws/control` is the active compat alias.
    assert "/health" in paths
    assert "/webhook/telegram" in paths
    assert "/admin/billing/plans" in paths
    assert "/ws/control" not in paths


def test_legacy_cutover_flags_keep_default_compat_aliases_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_legacy_health_endpoint", True)
    monkeypatch.setattr(settings, "enable_legacy_telegram_webhook_alias", True)
    monkeypatch.setattr(settings, "enable_legacy_billing_admin_alias", True)
    monkeypatch.setattr(settings, "enable_legacy_ws_control", True)

    test_app = create_app()
    apply_legacy_compat_routes(test_app)
    paths = _paths(test_app)

    assert "/health" in paths
    assert "/webhook/telegram" in paths
    assert "/admin/billing/plans" in paths
    assert "/ws/control" in paths
