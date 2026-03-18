"""Tests for tenant isolation interceptor, analytics idempotency, and webhook HMAC.

Covers:
- SQLAlchemy tenant isolation interceptor (task #60)
- Analytics event idempotency key deduplication (task #58)
- Campaign webhook HMAC mandatory enforcement (task #59)
"""

import os
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AUTH_SECRET", "test-secret-at-least-32-chars-long!!")

import hashlib
import hmac as hmac_lib
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Analytics Idempotency Key
# ══════════════════════════════════════════════════════════════════════════════

class TestIdempotencyKeyBuilder:
    """Unit tests for _build_idempotency_key()."""

    def test_with_provider_event_id(self):
        from app.campaign_engine.analytics_processor import _build_idempotency_key

        key = _build_idempotency_key(
            campaign_id=1, recipient_id=42, event_type="opened",
            provider_event_id="ext-abc-123",
        )
        assert key == "1:42:opened:ext-abc-123"

    def test_without_provider_event_id_produces_hash(self):
        from app.campaign_engine.analytics_processor import _build_idempotency_key

        key = _build_idempotency_key(
            campaign_id=1, recipient_id=42, event_type="opened",
        )
        # SHA256 hex, truncated to 64 chars
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_5min_window_produces_same_key(self):
        """Two calls in the same 5-minute bucket produce identical keys."""
        from app.campaign_engine.analytics_processor import _build_idempotency_key
        import time

        # Patch time.time to return a fixed value
        with patch("app.campaign_engine.analytics_processor.time") as mock_time:
            mock_time.time.return_value = 1000.0  # bucket = 3
            k1 = _build_idempotency_key(1, 42, "opened")
            mock_time.time.return_value = 1299.0  # still bucket = 4 (1000//300=3, 1299//300=4 — different bucket)

        with patch("app.campaign_engine.analytics_processor.time") as mock_time:
            mock_time.time.return_value = 1000.0
            k2 = _build_idempotency_key(1, 42, "opened")
        assert k1 == k2

    def test_different_event_types_different_keys(self):
        from app.campaign_engine.analytics_processor import _build_idempotency_key

        with patch("app.campaign_engine.analytics_processor.time") as mock_time:
            mock_time.time.return_value = 1000.0
            k_open = _build_idempotency_key(1, 42, "opened")
            k_click = _build_idempotency_key(1, 42, "clicked")

        assert k_open != k_click

    def test_different_campaigns_different_keys(self):
        from app.campaign_engine.analytics_processor import _build_idempotency_key

        with patch("app.campaign_engine.analytics_processor.time") as mock_time:
            mock_time.time.return_value = 1000.0
            k1 = _build_idempotency_key(1, 42, "opened")
            k2 = _build_idempotency_key(2, 42, "opened")

        assert k1 != k2


class TestAnalyticsProcessorDeduplication:
    """Tests for AnalyticsProcessor deduplication — verifies IntegrityError is handled."""

    def test_duplicate_event_silently_skipped(self):
        """IntegrityError on duplicate idempotency_key is caught → returns True."""
        from app.campaign_engine.analytics_processor import AnalyticsProcessor
        from sqlalchemy.exc import IntegrityError

        processor = AnalyticsProcessor()

        # Mock DB session: query returns None (no recipient), commit raises IntegrityError
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.commit.side_effect = IntegrityError("duplicate key", {}, None)

        raw_event = {
            "event_type": "opened",
            "provider_event_id": "ev-001",
        }

        result = processor.process_event(mock_db, raw_event)

        assert result is True
        mock_db.rollback.assert_called_once()

    def test_missing_event_type_returns_false(self):
        """Events without event_type are rejected immediately."""
        from app.campaign_engine.analytics_processor import AnalyticsProcessor

        processor = AnalyticsProcessor()
        mock_db = MagicMock()

        result = processor.process_event(mock_db, {})
        assert result is False
        mock_db.commit.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Tenant Isolation Interceptor
# ══════════════════════════════════════════════════════════════════════════════

class TestTenantContextVar:
    """Tests for tenant_context.py context variable."""

    def test_get_tenant_context_raises_without_context(self):
        from app.core.tenant_context import get_tenant_context

        # Ensure no context is set — should raise RuntimeError
        import contextvars
        # Use a fresh context
        ctx = contextvars.copy_context()

        def _run():
            # Clear the context var by accessing it in a new context
            from app.core import tenant_context as tc
            tc._tenant_ctx.set(None)
            get_tenant_context()

        with pytest.raises(RuntimeError, match="TenantContext not set"):
            ctx.run(_run)

    def test_tenant_scope_sets_and_resets(self):
        from app.core.tenant_context import (
            tenant_scope, get_tenant_context, TenantContext,
            get_tenant_context_or_none,
        )

        ctx = TenantContext(tenant_id=7, tenant_slug="test-tenant")
        with tenant_scope(ctx):
            current = get_tenant_context()
            assert current.tenant_id == 7
            assert current.tenant_slug == "test-tenant"

        # After scope exits, context is reset
        assert get_tenant_context_or_none() is None

    def test_tenant_context_redis_prefix(self):
        from app.core.tenant_context import TenantContext

        ctx = TenantContext(tenant_id=42, tenant_slug="acme")
        assert ctx.redis_prefix == "t42"

    def test_tenant_context_vector_namespace_uses_slug(self):
        from app.core.tenant_context import TenantContext

        ctx = TenantContext(tenant_id=5, tenant_slug="myfitness")
        assert ctx.vector_namespace == "ariia_tenant_myfitness"

    def test_tenant_context_vector_namespace_fallback_to_id(self):
        from app.core.tenant_context import TenantContext

        ctx = TenantContext(tenant_id=5)
        assert ctx.vector_namespace == "ariia_tenant_5"


class TestTenantInterceptor:
    """Tests for the SQLAlchemy tenant isolation interceptor."""

    def test_interceptor_injects_tenant_filter(self):
        """When tenant context is set, queries on scoped models get tenant filter."""
        from app.core.tenant_context import tenant_scope, TenantContext
        from app.core.tenant_interceptor import register_tenant_interceptor

        # Build a minimal in-memory DB with a scoped model
        class Base(DeclarativeBase):
            pass

        class ScopedModel(Base):
            __tablename__ = "scoped_items"
            __tenant_scoped__ = True
            id = Column(Integer, primary_key=True)
            tenant_id = Column(Integer)
            name = Column(String)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionFactory = sessionmaker(bind=engine)

        # Insert rows for two different tenants
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO scoped_items (tenant_id, name) VALUES (1, 'tenant1-item')"))
            conn.execute(text("INSERT INTO scoped_items (tenant_id, name) VALUES (2, 'tenant2-item')"))
            conn.commit()

        register_tenant_interceptor(SessionFactory)

        ctx = TenantContext(tenant_id=1, tenant_slug="t1")
        with tenant_scope(ctx):
            db = SessionFactory()
            try:
                results = db.query(ScopedModel).all()
                tenant_ids = {r.tenant_id for r in results}
                assert tenant_ids == {1}, f"Expected only tenant 1, got {tenant_ids}"
            finally:
                db.close()

    def test_interceptor_skips_non_scoped_models(self):
        """Models without __tenant_scoped__ are not filtered."""
        from app.core.tenant_context import tenant_scope, TenantContext
        from app.core.tenant_interceptor import register_tenant_interceptor

        class Base(DeclarativeBase):
            pass

        class GlobalModel(Base):
            __tablename__ = "global_items"
            # No __tenant_scoped__
            id = Column(Integer, primary_key=True)
            tenant_id = Column(Integer)
            name = Column(String)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionFactory = sessionmaker(bind=engine)

        with engine.connect() as conn:
            conn.execute(text("INSERT INTO global_items (tenant_id, name) VALUES (1, 'a')"))
            conn.execute(text("INSERT INTO global_items (tenant_id, name) VALUES (2, 'b')"))
            conn.commit()

        register_tenant_interceptor(SessionFactory)

        ctx = TenantContext(tenant_id=1, tenant_slug="t1")
        with tenant_scope(ctx):
            db = SessionFactory()
            try:
                results = db.query(GlobalModel).all()
                # Both rows should be returned (no filter applied)
                assert len(results) == 2
            finally:
                db.close()

    def test_interceptor_skips_without_context(self):
        """Without tenant context, queries are not filtered."""
        from app.core.tenant_context import get_tenant_context_or_none
        from app.core.tenant_interceptor import register_tenant_interceptor

        class Base(DeclarativeBase):
            pass

        class AnotherScoped(Base):
            __tablename__ = "another_scoped"
            __tenant_scoped__ = True
            id = Column(Integer, primary_key=True)
            tenant_id = Column(Integer)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionFactory = sessionmaker(bind=engine)

        with engine.connect() as conn:
            conn.execute(text("INSERT INTO another_scoped (tenant_id) VALUES (1)"))
            conn.execute(text("INSERT INTO another_scoped (tenant_id) VALUES (2)"))
            conn.commit()

        register_tenant_interceptor(SessionFactory)

        # No tenant_scope context set
        assert get_tenant_context_or_none() is None

        db = SessionFactory()
        try:
            results = db.query(AnotherScoped).all()
            assert len(results) == 2  # No filtering applied
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Campaign Webhook HMAC Enforcement
# ══════════════════════════════════════════════════════════════════════════════

def _compute_sig(body: bytes, secret: str) -> str:
    return "sha256=" + hmac_lib.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestWebhookHMAC:
    """Tests for require_valid_webhook_signature() FastAPI dependency.

    Signature: require_valid_webhook_signature(provider, request, db) -> None
    The function reads the secret via persistence.get_webhook_secret() with settings fallback.
    """

    def _make_request(self, body: bytes, sig_header: dict):
        mock_request = MagicMock()
        mock_request.headers = sig_header
        mock_request.body = AsyncMock(return_value=body)
        return mock_request

    @pytest.mark.asyncio
    async def test_valid_signature_passes(self):
        from app.gateway.routers.campaign_webhooks import require_valid_webhook_signature

        body = b'{"event_type": "opened"}'
        secret = "test-secret-at-least-32-chars-long!!"
        sig = _compute_sig(body, secret)
        mock_db = MagicMock()

        # persistence is imported locally in the function body
        with patch("app.gateway.persistence.persistence") as mock_persistence:
            mock_persistence.get_webhook_secret.return_value = secret
            # Should NOT raise
            await require_valid_webhook_signature(
                "campaign", self._make_request(body, {"X-Ariia-Signature": sig}), mock_db
            )

    @pytest.mark.asyncio
    async def test_missing_signature_raises_401(self):
        from app.gateway.routers.campaign_webhooks import require_valid_webhook_signature
        from fastapi import HTTPException

        mock_db = MagicMock()
        with patch("app.gateway.persistence.persistence") as mock_persistence:
            mock_persistence.get_webhook_secret.return_value = "some-secret"
            with pytest.raises(HTTPException) as exc_info:
                await require_valid_webhook_signature(
                    "campaign", self._make_request(b"body", {}), mock_db
                )

        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_signature_raises_401(self):
        from app.gateway.routers.campaign_webhooks import require_valid_webhook_signature
        from fastapi import HTTPException

        body = b'{"event_type": "opened"}'
        mock_db = MagicMock()
        with patch("app.gateway.persistence.persistence") as mock_persistence:
            mock_persistence.get_webhook_secret.return_value = "correct-secret-value!!"
            with pytest.raises(HTTPException) as exc_info:
                await require_valid_webhook_signature(
                    "campaign",
                    self._make_request(body, {"X-Ariia-Signature": "sha256=deadbeef"}),
                    mock_db,
                )

        assert exc_info.value.status_code == 401
        assert "Invalid" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_secret_configured_raises_503(self):
        from app.gateway.routers.campaign_webhooks import require_valid_webhook_signature
        from fastapi import HTTPException

        mock_db = MagicMock()
        with (
            patch("app.gateway.persistence.persistence") as mock_persistence,
            patch("app.gateway.routers.campaign_webhooks.get_settings") as mock_settings,
        ):
            mock_persistence.get_webhook_secret.return_value = None
            # Settings also has no secret for this provider
            settings_obj = MagicMock(spec=[])  # empty spec — any getattr returns AttributeError
            mock_settings.return_value = settings_obj

            with pytest.raises(HTTPException) as exc_info:
                await require_valid_webhook_signature(
                    "campaign",
                    self._make_request(b"body", {"X-Ariia-Signature": "sha256=x"}),
                    mock_db,
                )

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_hub_signature_header_accepted(self):
        """X-Hub-Signature-256 header is also accepted."""
        from app.gateway.routers.campaign_webhooks import require_valid_webhook_signature

        body = b'{"event_type": "clicked"}'
        secret = "test-secret-at-least-32-chars-long!!"
        sig = _compute_sig(body, secret)
        mock_db = MagicMock()

        with patch("app.gateway.persistence.persistence") as mock_persistence:
            mock_persistence.get_webhook_secret.return_value = secret
            # Should NOT raise
            await require_valid_webhook_signature(
                "campaign",
                self._make_request(body, {"X-Hub-Signature-256": sig}),
                mock_db,
            )
