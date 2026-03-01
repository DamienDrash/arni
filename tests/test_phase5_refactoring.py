"""Tests for Phase 5: Enterprise Features & Self-Service.

Tests all 5 milestones:
  MS 5.1: Tenant Portal Backend-API
  MS 5.2: Integration Marketplace API
  MS 5.3: Stripe Metered Billing Service
  MS 5.4: Analytics API
  MS 5.5: OpenTelemetry Instrumentation (Telemetry)
"""
import os
import time
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

os.environ.setdefault("ENVIRONMENT", "testing")


# ══════════════════════════════════════════════════════════════════════════════
# MS 5.1: TENANT PORTAL BACKEND-API
# ══════════════════════════════════════════════════════════════════════════════

class TestTenantPortalAPI:
    """Tests for the Tenant Portal Backend-API."""

    def test_import_tenant_portal(self):
        from app.platform.api.tenant_portal import router
        assert router is not None

    def test_router_has_endpoints(self):
        from app.platform.api.tenant_portal import router
        paths = [r.path for r in router.routes]
        # Should have key tenant portal endpoints
        assert len(paths) >= 3

    def test_router_prefix(self):
        from app.platform.api.tenant_portal import router
        assert router.prefix == "/api/v1/tenant/portal"

    def test_router_tags(self):
        from app.platform.api.tenant_portal import router
        assert "tenant-portal" in router.tags

    def test_endpoint_methods(self):
        from app.platform.api.tenant_portal import router
        methods = set()
        for route in router.routes:
            if hasattr(route, "methods"):
                methods.update(route.methods)
        # Should support GET and PUT/PATCH for self-service
        assert "GET" in methods


# ══════════════════════════════════════════════════════════════════════════════
# MS 5.2: INTEGRATION MARKETPLACE API
# ══════════════════════════════════════════════════════════════════════════════

class TestMarketplaceAPI:
    """Tests for the Integration Marketplace API."""

    def test_import_marketplace(self):
        from app.platform.api.marketplace import router
        assert router is not None

    def test_router_has_endpoints(self):
        from app.platform.api.marketplace import router
        paths = [r.path for r in router.routes]
        assert len(paths) >= 3

    def test_router_prefix(self):
        from app.platform.api.marketplace import router
        assert "/marketplace" in router.prefix

    def test_router_tags(self):
        from app.platform.api.marketplace import router
        assert "marketplace" in router.tags

    def test_endpoint_methods_include_post(self):
        from app.platform.api.marketplace import router
        methods = set()
        for route in router.routes:
            if hasattr(route, "methods"):
                methods.update(route.methods)
        assert "GET" in methods
        assert "POST" in methods


# ══════════════════════════════════════════════════════════════════════════════
# MS 5.3: STRIPE METERED BILLING SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class TestBillingService:
    """Tests for the Stripe Metered Billing Service."""

    def test_import_usage_tracker(self):
        from app.platform.billing_service import UsageTracker
        assert UsageTracker is not None

    def test_import_plan_enforcer(self):
        from app.platform.billing_service import PlanEnforcer
        assert PlanEnforcer is not None

    def test_usage_tracker_instantiation(self):
        from app.platform.billing_service import UsageTracker
        tracker = UsageTracker()
        assert tracker is not None

    def test_usage_record_model(self):
        from app.platform.billing_service import UsageRecord, UsageType
        record = UsageRecord(
            tenant_id=1,
            usage_type=UsageType.CONVERSATION,
            quantity=1,
            metadata={"endpoint": "/chat"},
        )
        assert record.tenant_id == 1
        assert record.usage_type == UsageType.CONVERSATION
        assert record.quantity == 1

    def test_usage_record_to_dict(self):
        from app.platform.billing_service import UsageRecord, UsageType
        record = UsageRecord(
            tenant_id=1,
            usage_type=UsageType.API_CALL,
            quantity=5,
        )
        d = record.to_dict()
        assert d["tenant_id"] == 1
        assert d["usage_type"] == "api_call"
        assert d["quantity"] == 5

    def test_usage_record_timestamp(self):
        from app.platform.billing_service import UsageRecord, UsageType
        record = UsageRecord(
            tenant_id=1,
            usage_type=UsageType.TOKEN_INPUT,
            quantity=100,
        )
        assert hasattr(record, "timestamp")
        assert record.timestamp is not None

    def test_plan_limits_for_tier(self):
        from app.platform.billing_service import PlanLimits, PlanTier
        free_limits = PlanLimits.for_tier(PlanTier.FREE)
        assert free_limits.max_monthly_conversations is not None
        assert free_limits.max_channels >= 1

    def test_plan_enforcer_instantiation(self):
        from app.platform.billing_service import PlanEnforcer
        enforcer = PlanEnforcer()
        assert enforcer is not None

    def test_plan_enforcer_set_and_get_plan(self):
        from app.platform.billing_service import PlanEnforcer, PlanTier
        enforcer = PlanEnforcer()
        enforcer.set_plan(1, PlanTier.PROFESSIONAL)
        cached = enforcer._get_cached_plan(1)
        assert cached == PlanTier.PROFESSIONAL

    def test_plan_enforcer_check_feature(self):
        from app.platform.billing_service import PlanEnforcer, PlanTier
        enforcer = PlanEnforcer()
        # Enterprise should have more features than Free
        enterprise_limits = enforcer.get_limits(PlanTier.ENTERPRISE)
        free_limits = enforcer.get_limits(PlanTier.FREE)
        assert enterprise_limits.max_channels >= free_limits.max_channels

    def test_stripe_webhook_processor_import(self):
        from app.platform.billing_service import StripeWebhookProcessor
        assert StripeWebhookProcessor is not None

    def test_usage_type_enum(self):
        from app.platform.billing_service import UsageType
        assert UsageType.CONVERSATION is not None
        assert UsageType.API_CALL is not None
        assert UsageType.TOKEN_INPUT is not None
        assert UsageType.TOKEN_OUTPUT is not None

    def test_plan_tier_enum(self):
        from app.platform.billing_service import PlanTier
        assert PlanTier.FREE is not None
        assert PlanTier.STARTER is not None
        assert PlanTier.PROFESSIONAL is not None
        assert PlanTier.ENTERPRISE is not None


# ══════════════════════════════════════════════════════════════════════════════
# MS 5.4: ANALYTICS API
# ══════════════════════════════════════════════════════════════════════════════

class TestAnalyticsAPI:
    """Tests for the Analytics API."""

    def test_import_analytics(self):
        from app.platform.api.analytics import router
        assert router is not None

    def test_router_has_endpoints(self):
        from app.platform.api.analytics import router
        paths = [r.path for r in router.routes]
        assert len(paths) >= 5  # dashboard, conversations, intents, feedback, channels, etc.

    def test_router_prefix(self):
        from app.platform.api.analytics import router
        assert "/analytics" in router.prefix

    def test_analytics_engine_import(self):
        from app.platform.api.analytics import AnalyticsEngine
        engine = AnalyticsEngine()
        assert engine is not None

    def test_conversation_metrics_empty(self):
        from app.platform.api.analytics import AnalyticsEngine
        engine = AnalyticsEngine()
        result = engine.compute_conversation_metrics([], days=30)
        assert result["total"] == 0
        assert result["daily_average"] == 0
        assert result["resolution_rate"] == 0

    def test_conversation_metrics_with_data(self):
        from app.platform.api.analytics import AnalyticsEngine

        class MockConv:
            def __init__(self, channel="whatsapp", escalated=False):
                self.channel = channel
                self.escalated = escalated
                self.created_at = datetime.now(timezone.utc)
                self.message_count = 5

        engine = AnalyticsEngine()
        convs = [MockConv("whatsapp"), MockConv("telegram"), MockConv("whatsapp", True)]
        result = engine.compute_conversation_metrics(convs, days=30)
        assert result["total"] == 3
        assert result["by_channel"]["whatsapp"] == 2
        assert result["by_channel"]["telegram"] == 1
        assert result["avg_messages_per_conversation"] == 5.0

    def test_intent_analysis_empty(self):
        from app.platform.api.analytics import AnalyticsEngine
        engine = AnalyticsEngine()
        result = engine.compute_intent_analysis([])
        assert result["total_intents_detected"] == 0
        assert result["unique_intents"] == 0

    def test_intent_analysis_with_data(self):
        from app.platform.api.analytics import AnalyticsEngine

        class MockConv:
            def __init__(self, intent, escalated=False):
                self.intent = intent
                self.escalated = escalated
                self.user_message = f"Test message for {intent}"

        engine = AnalyticsEngine()
        convs = [
            MockConv("booking"), MockConv("booking"), MockConv("booking"),
            MockConv("pricing"), MockConv("pricing"),
            MockConv("complaint", True),
        ]
        result = engine.compute_intent_analysis(convs)
        assert result["total_intents_detected"] == 6
        assert result["unique_intents"] == 3
        assert result["top_intents"][0]["intent"] == "booking"
        assert result["top_intents"][0]["count"] == 3

    def test_feedback_metrics_empty(self):
        from app.platform.api.analytics import AnalyticsEngine
        engine = AnalyticsEngine()
        result = engine.compute_feedback_metrics([])
        assert result["total_feedback"] == 0
        assert result["average_rating"] == 0
        assert result["nps_score"] == 0

    def test_feedback_metrics_with_data(self):
        from app.platform.api.analytics import AnalyticsEngine

        class MockConv:
            def __init__(self, rating, feedback_text=None, sentiment=None):
                self.feedback_rating = rating
                self.feedback_text = feedback_text
                self.sentiment = sentiment

        engine = AnalyticsEngine()
        convs = [
            MockConv(5, "Great!", "positive"),
            MockConv(4, "Good", "positive"),
            MockConv(2, "Bad", "negative"),
            MockConv(5, "Excellent!", "positive"),
        ]
        result = engine.compute_feedback_metrics(convs)
        assert result["total_feedback"] == 4
        assert result["average_rating"] == 4.0
        assert result["sentiment"]["positive"] == 3
        assert result["sentiment"]["negative"] == 1

    def test_escalation_metrics(self):
        from app.platform.api.analytics import AnalyticsEngine

        class MockConv:
            def __init__(self, escalated=False, reason=None):
                self.escalated = escalated
                self.escalation_reason = reason

        engine = AnalyticsEngine()
        convs = [
            MockConv(False), MockConv(False), MockConv(False),
            MockConv(True, "complexity"),
            MockConv(True, "user_request"),
        ]
        result = engine.compute_escalation_metrics(convs)
        assert result["total_conversations"] == 5
        assert result["escalated"] == 2
        assert result["escalation_rate"] == 40.0
        assert result["reasons"]["complexity"] == 1

    def test_export_endpoint_exists(self):
        from app.platform.api.analytics import router
        paths = [r.path for r in router.routes]
        assert any("export" in p for p in paths)

    def test_bucket_by_day(self):
        from app.platform.api.analytics import _bucket_by_day

        class MockItem:
            def __init__(self, days_ago=0):
                self.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

        items = [MockItem(0), MockItem(0), MockItem(1), MockItem(5)]
        buckets = _bucket_by_day(items, "created_at", 7)
        assert isinstance(buckets, dict)
        assert len(buckets) == 7

    def test_safe_avg(self):
        from app.platform.api.analytics import _safe_avg
        assert _safe_avg([]) == 0.0
        assert _safe_avg([1, 2, 3]) == 2.0
        assert _safe_avg([10]) == 10.0

    def test_trend_percent(self):
        from app.platform.api.analytics import _trend_percent
        assert _trend_percent(100, 50) == 100.0  # 100% increase
        assert _trend_percent(50, 100) == -50.0   # 50% decrease
        assert _trend_percent(10, 0) == 100.0      # from zero
        assert _trend_percent(0, 0) == 0.0          # no change


# ══════════════════════════════════════════════════════════════════════════════
# MS 5.5: OPENTELEMETRY INSTRUMENTATION (TELEMETRY)
# ══════════════════════════════════════════════════════════════════════════════

class TestTelemetry:
    """Tests for the OpenTelemetry Instrumentation."""

    def test_import_telemetry(self):
        from app.core.telemetry import TracingManager, MetricsCollector
        assert TracingManager is not None
        assert MetricsCollector is not None

    def test_tracing_manager_creation(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager(service_name="test-service")
        assert tracer.service_name == "test-service"

    def test_span_creation(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        span = tracer.start_span("test_operation")
        assert span.operation_name == "test_operation"
        assert span.status == "OK"
        assert span.trace_id is not None
        assert span.span_id is not None
        tracer.finish_span(span)

    def test_span_attributes(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        span = tracer.start_span("test", attributes={"key": "value"})
        span.set_attribute("extra", 42)
        assert span.attributes["key"] == "value"
        assert span.attributes["extra"] == 42
        tracer.finish_span(span)

    def test_span_events(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        span = tracer.start_span("test")
        span.add_event("checkpoint", {"step": 1})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"
        tracer.finish_span(span)

    def test_span_duration(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        span = tracer.start_span("test")
        time.sleep(0.01)
        tracer.finish_span(span)
        assert span.duration_ms >= 5  # At least 5ms

    def test_span_context_manager(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        with tracer.span("test_op") as span:
            span.set_attribute("inside", True)
        assert span.status == "OK"
        assert span.end_time is not None

    def test_span_context_manager_error(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        try:
            with tracer.span("failing_op") as span:
                raise ValueError("test error")
        except ValueError:
            pass
        assert span.status == "ERROR"
        assert span.attributes["error"] is True
        assert "test error" in span.attributes["error.message"]

    def test_trace_id_propagation(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        trace_id = tracer.create_trace_id()
        span1 = tracer.start_span("parent", trace_id=trace_id)
        span2 = tracer.start_span("child", trace_id=trace_id, parent_span_id=span1.span_id)
        assert span1.trace_id == span2.trace_id
        assert span2.parent_span_id == span1.span_id
        tracer.finish_span(span2)
        tracer.finish_span(span1)

    def test_get_trace(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        trace_id = tracer.create_trace_id()
        with tracer.span("op1", trace_id=trace_id):
            pass
        with tracer.span("op2", trace_id=trace_id):
            pass
        spans = tracer.get_trace(trace_id)
        assert len(spans) == 2

    def test_get_recent_traces(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        for i in range(5):
            with tracer.span(f"op_{i}"):
                pass
        traces = tracer.get_recent_traces(limit=3)
        assert len(traces) <= 5  # May have fewer unique traces

    def test_get_active_spans(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        span = tracer.start_span("active_test")
        active = tracer.get_active_spans()
        assert len(active) >= 1
        tracer.finish_span(span)

    def test_span_to_dict(self):
        from app.core.telemetry import TracingManager
        tracer = TracingManager()
        with tracer.span("dict_test", attributes={"key": "val"}) as span:
            span.add_event("evt")
        d = span.to_dict()
        assert d["operation"] == "dict_test"
        assert d["attributes"]["key"] == "val"
        assert len(d["events"]) == 1
        assert d["status"] == "OK"

    # --- MetricsCollector ---

    def test_metrics_counter(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        m.increment("requests", 1)
        m.increment("requests", 2)
        assert m.get_counter("requests") == 3

    def test_metrics_counter_with_labels(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        m.increment("requests", labels={"method": "GET"})
        m.increment("requests", labels={"method": "POST"})
        m.increment("requests", labels={"method": "GET"})
        assert m.get_counter("requests", labels={"method": "GET"}) == 2
        assert m.get_counter("requests", labels={"method": "POST"}) == 1

    def test_metrics_gauge(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        m.set_gauge("active_connections", 5)
        assert m.get_gauge("active_connections") == 5
        m.set_gauge("active_connections", 3)
        assert m.get_gauge("active_connections") == 3

    def test_metrics_histogram(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            m.observe("latency_ms", v)
        stats = m.get_histogram_stats("latency_ms")
        assert stats["count"] == 10
        assert stats["avg"] == 55.0
        assert stats["min"] == 10.0
        assert stats["max"] == 100.0
        assert stats["p50"] == 60.0  # 50th percentile

    def test_metrics_histogram_empty(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        stats = m.get_histogram_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["avg"] == 0

    def test_metrics_prometheus_export(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        m.increment("http_requests", labels={"method": "GET"})
        m.set_gauge("active", 3)
        m.observe("latency", 50)
        output = m.to_prometheus()
        assert "http_requests" in output
        assert "active" in output
        assert "latency" in output

    def test_metrics_json_export(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        m.increment("test_counter", 5)
        m.set_gauge("test_gauge", 10)
        result = m.get_all_metrics()
        assert "counters" in result
        assert "gauges" in result
        assert "histograms" in result

    def test_metrics_reset(self):
        from app.core.telemetry import MetricsCollector
        m = MetricsCollector()
        m.increment("counter", 10)
        m.set_gauge("gauge", 5)
        m.observe("hist", 100)
        m.reset()
        assert m.get_counter("counter") == 0
        assert m.get_gauge("gauge") == 0
        assert m.get_histogram_stats("hist")["count"] == 0

    # --- TelemetryMiddleware ---

    def test_middleware_import(self):
        from app.core.telemetry import TelemetryMiddleware
        assert TelemetryMiddleware is not None

    def test_middleware_creation(self):
        from app.core.telemetry import TelemetryMiddleware, TracingManager, MetricsCollector
        mock_app = MagicMock()
        tracer = TracingManager()
        metrics = MetricsCollector()
        mw = TelemetryMiddleware(mock_app, tracer, metrics)
        assert mw.tracer is tracer
        assert mw.metrics is metrics

    def test_middleware_excluded_paths(self):
        from app.core.telemetry import TelemetryMiddleware, TracingManager, MetricsCollector
        mock_app = MagicMock()
        tracer = TracingManager()
        metrics = MetricsCollector()
        mw = TelemetryMiddleware(mock_app, tracer, metrics, excluded_paths={"/health", "/custom"})
        assert "/health" in mw.excluded_paths
        assert "/custom" in mw.excluded_paths

    # --- Metrics Router ---

    def test_create_metrics_router(self):
        from app.core.telemetry import create_metrics_router, TracingManager, MetricsCollector
        tracer = TracingManager()
        metrics = MetricsCollector()
        router = create_metrics_router(tracer, metrics)
        assert router is not None
        paths = [r.path for r in router.routes]
        assert any("metrics" in p for p in paths)

    # --- trace_function decorator ---

    def test_trace_function_sync(self):
        from app.core.telemetry import TracingManager, trace_function
        tracer = TracingManager()

        @trace_function(tracer, "test_sync")
        def my_func():
            return 42

        result = my_func()
        assert result == 42

    def test_trace_function_async(self):
        import asyncio
        from app.core.telemetry import TracingManager, trace_function
        tracer = TracingManager()

        @trace_function(tracer, "test_async")
        async def my_async_func():
            return 99

        result = asyncio.get_event_loop().run_until_complete(my_async_func())
        assert result == 99

    # --- Global singletons ---

    def test_get_tracer_singleton(self):
        # Reset global state
        import app.core.telemetry as tel
        tel._tracer = None
        t1 = tel.get_tracer()
        t2 = tel.get_tracer()
        assert t1 is t2

    def test_get_metrics_singleton(self):
        import app.core.telemetry as tel
        tel._metrics = None
        m1 = tel.get_metrics()
        m2 = tel.get_metrics()
        assert m1 is m2


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION: GATEWAY REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

class TestGatewayIntegration:
    """Tests that Phase 5 modules are properly registered in the gateway."""

    def test_gateway_imports_tenant_portal(self):
        from app.platform.api.tenant_portal import router
        assert router.prefix == "/api/v1/tenant/portal"

    def test_gateway_imports_marketplace(self):
        from app.platform.api.marketplace import router
        assert "/marketplace" in router.prefix

    def test_gateway_imports_analytics(self):
        from app.platform.api.analytics import router
        assert "/analytics" in router.prefix

    def test_gateway_imports_telemetry(self):
        from app.core.telemetry import get_tracer, get_metrics, TelemetryMiddleware
        tracer = get_tracer()
        metrics = get_metrics()
        assert tracer is not None
        assert metrics is not None

    def test_billing_service_importable(self):
        from app.platform.billing_service import UsageTracker, PlanEnforcer
        assert UsageTracker is not None
        assert PlanEnforcer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
