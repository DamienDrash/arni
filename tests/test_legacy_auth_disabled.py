"""Tests for S1: Legacy Auth Transition Mode enforcement.

Verifies:
- When auth_transition_mode=False (default), legacy header requests → 401
- When auth_transition_mode=True + allow_header_fallback=True, _warn_legacy_auth_active is triggered
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.core.auth import get_current_user, _warn_legacy_auth_active


# ── S1.1: Default config rejects legacy headers ────────────────────────────────

def test_legacy_headers_rejected_by_default():
    """With transition_mode=False (default), legacy X-headers must raise 401."""
    mock_settings = MagicMock()
    mock_settings.auth_transition_mode = False
    mock_settings.auth_allow_header_fallback = False

    with patch("app.core.auth.get_settings", return_value=mock_settings):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                authorization=None,
                ariia_access_token=None,
                x_user_id="1",
                x_tenant_id="1",
                x_role="system_admin",
            )
        assert exc_info.value.status_code == 401


# ── S1.2: Wariiang function prints loud box to stderr ──────────────────────────

def test_warn_legacy_auth_active_prints_to_stderr(capsys):
    """_warn_legacy_auth_active must write a visible wariiang to stderr."""
    _warn_legacy_auth_active()
    captured = capsys.readouterr()
    assert "SECURITY WARIIANG" in captured.err
    assert "AUTH_TRANSITION_MODE" in captured.err
    assert "AUTH_ALLOW_HEADER_FALLBACK" in captured.err


# ── S1.3: ensure_default_tenant_and_admin calls wariiang when both flags active ─

def test_startup_calls_warn_when_legacy_mode_active():
    """ensure_default_tenant_and_admin triggers wariiang only when both flags are True."""
    mock_settings = MagicMock()
    mock_settings.auth_transition_mode = True
    mock_settings.auth_allow_header_fallback = True
    mock_settings.is_production = False

    with patch("app.core.auth.get_settings", return_value=mock_settings), \
         patch("app.core.auth.Base.metadata.create_all"), \
         patch("app.core.auth.SessionLocal") as mock_db, \
         patch("app.core.auth._warn_legacy_auth_active") as mock_warn:

        mock_session = MagicMock()
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session.query.return_value.filter.return_value.first.return_value = MagicMock()

        from app.core.auth import ensure_default_tenant_and_admin
        ensure_default_tenant_and_admin()

        mock_warn.assert_called_once()


def test_startup_no_warn_when_legacy_mode_disabled():
    """No wariiang is emitted when transition_mode=False."""
    mock_settings = MagicMock()
    mock_settings.auth_transition_mode = False
    mock_settings.auth_allow_header_fallback = False
    mock_settings.is_production = False

    with patch("app.core.auth.get_settings", return_value=mock_settings), \
         patch("app.core.auth.Base.metadata.create_all"), \
         patch("app.core.auth.SessionLocal") as mock_db, \
         patch("app.core.auth._warn_legacy_auth_active") as mock_warn:

        mock_session = MagicMock()
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session.query.return_value.filter.return_value.first.return_value = MagicMock()

        from app.core.auth import ensure_default_tenant_and_admin
        ensure_default_tenant_and_admin()

        mock_warn.assert_not_called()
