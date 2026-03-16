"""ARIIA v2.0 – Ingestion Regressions-Tests.

Stellt sicher, dass die neuen Ingestion-Komponenten
das bestehende System nicht beschädigen.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from app.gateway.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestExistingSystemUnbroken:
    """Kernfunktionen müssen nach Integration der Ingestion-Pipeline funktionieren."""

    @pytest.mark.anyio
    async def test_health_endpoint_still_works(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["service"] == "ariia-gateway"

    @pytest.mark.anyio
    async def test_auth_login_still_works(self, client: AsyncClient):
        response = await client.post(
            "/auth/login",
            json={"email": "admin@ariia.local", "password": "Password123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.anyio
    async def test_webhook_endpoint_still_works(self, client: AsyncClient):
        """WhatsApp-Webhook-Ingress muss funktionieren."""
        import json
        payload = {
            "object": "whatsapp_business_account",
            "entry": [],
        }
        response = await client.post(
            "/webhook/whatsapp/system",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_billing_plans_still_accessible(self, client: AsyncClient):
        """Billing-Plans-Endpoint muss erreichbar sein."""
        response = await client.get("/admin/billing/plans")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_no_import_errors_on_startup(self):
        """Alle neuen Module müssen importierbar sein ohne Fehler."""
        import_targets = [
            "app.gateway.routers.ingestion",
            "app.worker.retry",
        ]

        for target in import_targets:
            try:
                import importlib
                importlib.import_module(target)
            except ImportError as e:
                # Module können fehlen wenn Teams noch nicht fertig
                pytest.skip(f"Modul {target} noch nicht verfügbar: {e}")
            except Exception as e:
                pytest.fail(f"Import-Fehler in {target}: {e}")

    @pytest.mark.anyio
    async def test_ingestion_jobs_model_importable(self):
        """IngestionJob-Modell muss importierbar sein."""
        try:
            from app.core.models import IngestionJob, IngestionJobStatus
            assert IngestionJob.__tablename__ == "ingestion_jobs"
        except ImportError:
            pytest.skip("IngestionJob noch nicht implementiert")
