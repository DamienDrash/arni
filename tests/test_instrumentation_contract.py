from __future__ import annotations

from app.core import instrumentation


class _QueryStub:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        if self.model_name == "UserAccount":
            return object()
        return None

    def count(self):
        if self.model_name == "Campaign":
            return 2
        return 0


class _SessionStub:
    def __init__(self) -> None:
        self.closed = False

    def query(self, model):
        return _QueryStub(getattr(model, "__name__", str(model)))

    def close(self) -> None:
        self.closed = True


def test_metrics_uses_open_session_and_updates_auth_gauge(monkeypatch) -> None:
    session = _SessionStub()
    monkeypatch.setattr(instrumentation, "open_session", lambda: session)
    monkeypatch.setattr(instrumentation, "generate_latest", lambda: b"metrics-payload")

    response = instrumentation.metrics()

    assert response.media_type == instrumentation.CONTENT_TYPE_LATEST
    assert response.body == b"metrics-payload"
    assert instrumentation.AUTH_SYSTEM_STATUS._value.get() == 1
    assert session.closed is True


def test_campaign_health_uses_open_session_for_database_counts(monkeypatch) -> None:
    session = _SessionStub()
    monkeypatch.setattr(instrumentation, "open_session", lambda: session)

    health = instrumentation.campaign_health()

    assert health["components"]["database"]["status"] == "healthy"
    assert health["components"]["database"]["active_campaigns"] == 2
    assert health["components"]["database"]["scheduled_campaigns"] == 2
    assert session.closed is True
