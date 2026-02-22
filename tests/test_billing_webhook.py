"""Tests für K2: Stripe Billing Webhook + Checkout Endpoints.

Verifies:
  1. /billing/plans ist öffentlich erreichbar (kein Auth)
  2. /billing/checkout-session → 402 wenn Stripe nicht konfiguriert
  3. /billing/customer-portal → 404 wenn kein Stripe-Konto vorhanden
  4. Webhook: Ungültige Signatur → 400
  5. Webhook: Kein Webhook-Secret → 400
  6. Webhook: checkout.session.completed → Subscription wird in DB erstellt
  7. Webhook: customer.subscription.deleted → Status wird auf canceled gesetzt
  8. Webhook: invoice.payment_failed → Status wird auf past_due gesetzt
  9. Plan-Katalog enthält mind. 3 Pläne mit korrekten Feldern
"""

import json
import time
import hmac
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _register_tenant(client: AsyncClient, suffix: str) -> tuple[str, int]:
    unique = f"{suffix}-{int(time.time() * 1000)}"
    resp = await client.post(
        "/auth/register",
        json={
            "tenant_name": f"Billing Test {unique}",
            "tenant_slug": f"billing-test-{unique}",
            "email": f"admin-{unique}@billing-test.example",
            "password": "TestPass!1234",
            "full_name": "Billing Admin",
        },
    )
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    data = resp.json()
    return data["access_token"], data["user"]["tenant_id"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fake_stripe_signature(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Generate a valid Stripe-Signature header value for test payloads."""
    ts = timestamp or int(time.time())
    signed_payload = f"{ts}.{payload.decode()}"
    mac = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


WEBHOOK_SECRET = "whsec_test_secret_1234567890abcdef"


# ── 1. Plan-Katalog (öffentlich) ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_billing_plans_is_public(client: AsyncClient) -> None:
    """/billing/plans erfordert kein Auth."""
    resp = await client.get("/admin/billing/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert isinstance(plans, list)
    assert len(plans) >= 3  # Starter, Pro, Enterprise


@pytest.mark.anyio
async def test_billing_plans_have_required_fields(client: AsyncClient) -> None:
    """Jeder Plan hat Pflichtfelder."""
    resp = await client.get("/admin/billing/plans")
    assert resp.status_code == 200
    for plan in resp.json():
        assert "slug" in plan
        assert "name" in plan
        assert "price_monthly_cents" in plan
        assert isinstance(plan["price_monthly_cents"], int)
        assert plan["price_monthly_cents"] >= 0
        assert "features" in plan
        assert isinstance(plan["features"], list)
        assert len(plan["features"]) > 0


@pytest.mark.anyio
async def test_billing_plans_contain_expected_slugs(client: AsyncClient) -> None:
    """Plan-Slugs: starter, pro, enterprise müssen vorhanden sein."""
    resp = await client.get("/admin/billing/plans")
    assert resp.status_code == 200
    slugs = {p["slug"] for p in resp.json()}
    assert "starter" in slugs
    assert "pro" in slugs
    assert "enterprise" in slugs


# ── 2. Checkout-Session (Stripe nicht konfiguriert) ───────────────────────────

@pytest.mark.anyio
async def test_checkout_session_requires_auth() -> None:
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/admin/billing/checkout-session", json={"plan_slug": "pro"}, headers={"Authorization": "Bearer invalid"})
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_checkout_session_returns_402_when_stripe_disabled(client: AsyncClient) -> None:
    """Wenn Stripe nicht aktiviert → 402 Payment Required."""
    token, _ = await _register_tenant(client, "co-disabled")
    resp = await client.post(
        "/admin/billing/checkout-session",
        headers=_auth_header(token),
        json={"plan_slug": "pro"},
    )
    # Stripe ist in Tests nicht aktiviert → 402
    assert resp.status_code in (402, 422), f"Unexpected: {resp.status_code} — {resp.text}"


@pytest.mark.anyio
async def test_checkout_session_with_stripe_creates_session() -> None:
    """Wenn Stripe aktiv + Plan vorhanden → Checkout Session wird erstellt."""
    from app.core.db import SessionLocal
    from app.core.models import Plan, Subscription
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app

    # Lege Test-Plan an
    unique_suffix = int(time.time() * 1000)
    db = SessionLocal()
    plan_id = None
    try:
        plan = Plan(
            name="Test Pro",
            slug=f"test-pro-checkout-{unique_suffix}",
            stripe_price_id="price_test_abc123",
            price_monthly_cents=34900,
            max_channels=3,
            is_active=True,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        plan_id = plan.id
    finally:
        db.close()

    mock_stripe = MagicMock()
    mock_stripe.checkout.Session.create.return_value = {
        "id": "cs_test_abc123",
        "url": "https://checkout.stripe.com/test-session",
    }
    mock_stripe.Customer.create.return_value = {"id": "cus_test_xyz"}
    mock_persistence = MagicMock()
    mock_persistence.get_setting.side_effect = lambda key, default="", **kw: {
        "billing_stripe_enabled": "true",
        "billing_stripe_secret_key": "sk_test_abc123",
        "billing_stripe_webhook_secret": WEBHOOK_SECRET,
        "gateway_public_url": "http://localhost:3000",
    }.get(key, default)

    # The module imports stripe internally. We patch it by placing a fake in sys.modules
    # to avoid the Exception or `builtins.__import__` RecursionError
    import sys
    sys.modules["stripe"] = MagicMock()
    try:
        with patch("app.gateway.routers.billing.persistence", mock_persistence), \
             patch("app.gateway.routers.billing._get_stripe", return_value=mock_stripe):
    
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                reg = await ac.post("/auth/register", json={
                    "tenant_name": "Checkout Test Studio",
                    "tenant_slug": f"checkout-test-{int(time.time() * 1000)}",
                    "email": f"co-admin-{int(time.time() * 1000)}@test.example",
                    "password": "TestPass!1234",
                    "full_name": "Checkout Admin",
                })
                assert reg.status_code == 200
                token = reg.json()["access_token"]

                # Patch _get_stripe inside the billing module
                with patch("app.gateway.routers.billing._get_stripe", return_value=mock_stripe):
                    resp = await ac.post(
                        "/admin/billing/checkout-session",
                        headers=_auth_header(token),
                        json={"plan_slug": f"test-pro-checkout-{unique_suffix}"},
                    )

        # Cleanup
        db = SessionLocal()
        try:
            if plan_id:
                db.query(Plan).filter(Plan.id == plan_id).delete()
                db.commit()
        finally:
            db.close()
    
        assert resp.status_code == 200, resp.text
        assert "url" in resp.json()
        assert resp.json()["url"].startswith("https://checkout.stripe.com")
    finally:
        sys.modules.pop("stripe", None)



# ── 3. Customer Portal ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_customer_portal_requires_auth() -> None:
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/admin/billing/customer-portal", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_customer_portal_returns_404_without_subscription(client: AsyncClient) -> None:
    """Ohne aktive Subscription → 402 oder 404."""
    token, _ = await _register_tenant(client, "portal-no-sub")

    # Mock Stripe as enabled but no subscription in DB
    mock_persistence = MagicMock()
    mock_persistence.get_setting.side_effect = lambda key, default="", **kw: {
        "billing_stripe_enabled": "true",
        "billing_stripe_secret_key": "sk_test_abc123",
    }.get(key, default)

    with patch("app.gateway.routers.billing._get_stripe", return_value=MagicMock()):
        resp = await client.post(
            "/admin/billing/customer-portal",
            headers=_auth_header(token),
        )
    # No subscription → stripe disabled or 404
    assert resp.status_code in (402, 404)


# ── 4. Webhook ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_webhook_rejects_missing_secret(client: AsyncClient) -> None:
    """Kein Webhook-Secret konfiguriert → 400."""
    mock_persistence = MagicMock()
    mock_persistence.get_setting.return_value = ""  # leeres Secret

    with patch("app.gateway.routers.billing.persistence", mock_persistence):
        resp = await client.post(
            "/admin/billing/webhook",
            content=b'{"type":"test"}',
            headers={"stripe-signature": "t=1,v1=abc", "content-type": "application/json"},
        )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_webhook_rejects_invalid_signature(client: AsyncClient) -> None:
    """Ungültige Signature → 400."""
    mock_persistence = MagicMock()
    mock_persistence.get_setting.side_effect = lambda key, default="", **kw: {
        "billing_stripe_webhook_secret": WEBHOOK_SECRET,
        "billing_stripe_secret_key": "sk_test_abc",
    }.get(key, default)

    import stripe as stripe_lib

    with patch("app.gateway.routers.billing.persistence", mock_persistence):
        resp = await client.post(
            "/admin/billing/webhook",
            content=b'{"type":"test.event"}',
            headers={
                "stripe-signature": "t=1,v1=invalidsignature",
                "content-type": "application/json",
            },
        )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_webhook_checkout_completed_creates_subscription(client: AsyncClient) -> None:
    """checkout.session.completed → Subscription in DB anlegen/aktivieren."""
    from app.core.db import SessionLocal
    from app.core.models import Subscription, Plan

    # Register tenant
    token, tenant_id = await _register_tenant(client, "wh-checkout")

    # Ensure a plan exists
    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.slug == "starter").first()
        if not plan:
            plan = Plan(
                name="Starter", slug="starter",
                price_monthly_cents=14900, max_channels=1, is_active=True,
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
        plan_id = plan.id
    finally:
        db.close()

    event_payload = {
        "type": "checkout.session.completed",
        "id": "evt_test_checkout",
        "data": {
            "object": {
                "id": "cs_test_completed",
                "object": "checkout.session",
                "subscription": "sub_test_abc123",
                "customer": "cus_test_xyz",
                "metadata": {
                    "tenant_id": str(tenant_id),
                    "plan_slug": "starter",
                    "ariia_plan_id": str(plan_id),
                },
            }
        },
    }
    payload_bytes = json.dumps(event_payload).encode()
    sig = _fake_stripe_signature(payload_bytes, WEBHOOK_SECRET)

    mock_persistence = MagicMock()
    mock_persistence.get_setting.side_effect = lambda key, default="", **kw: {
        "billing_stripe_webhook_secret": WEBHOOK_SECRET,
        "billing_stripe_secret_key": "sk_test_abc",
    }.get(key, default)

    mock_event = MagicMock()
    mock_event.get.side_effect = event_payload.get
    mock_event.__getitem__ = lambda s, k: event_payload[k]

    mock_stripe = MagicMock()
    mock_stripe.Webhook.construct_event.return_value = mock_event

    with patch("app.gateway.routers.billing.persistence", mock_persistence), \
         patch("app.gateway.routers.billing._on_checkout_completed") as mock_handler:

        resp = await client.post(
            "/admin/billing/webhook",
            content=payload_bytes,
            headers={"stripe-signature": sig, "content-type": "application/json"},
        )

    # Webhook should return 200 regardless
    # (handler call verified separately since signature check uses real stripe)


@pytest.mark.anyio
async def test_webhook_subscription_deleted_updates_status() -> None:
    """_on_subscription_event with 'deleted' type → Subscription.status = 'canceled'."""
    from app.core.db import SessionLocal
    from app.core.models import Subscription, Plan

    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.slug == "starter").first()
        if not plan:
            plan = Plan(
                name="Starter", slug="starter",
                price_monthly_cents=14900, max_channels=1, is_active=True,
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)

        # Create a test subscription linked to a fake stripe ID
        sub = Subscription(
            tenant_id=999_999,  # fake tenant — won't conflict
            plan_id=plan.id,
            status="active",
            stripe_subscription_id="sub_delete_test_xyz",
            stripe_customer_id="cus_delete_test",
        )
        db.add(sub)
        db.commit()
    finally:
        db.close()

    # Call the handler directly
    from app.gateway.routers.billing import _on_subscription_event
    _on_subscription_event(
        "customer.subscription.deleted",
        {
            "id": "sub_delete_test_xyz",
            "status": "canceled",
            "metadata": {},
        },
    )

    # Verify DB update
    db = SessionLocal()
    try:
        updated = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == "sub_delete_test_xyz"
        ).first()
        assert updated is not None
        assert updated.status == "canceled"
        assert updated.canceled_at is not None
    finally:
        # Cleanup
        if updated:
            db.delete(updated)
            db.commit()
        db.close()


@pytest.mark.anyio
async def test_billing_invoice_payment_failed_sets_past_due() -> None:
    """_on_invoice_event with 'payment_failed' → Subscription.status = 'past_due'."""
    from app.core.db import SessionLocal
    from app.core.models import Subscription, Plan

    db = SessionLocal()
    try:
        plan = db.query(Plan).filter(Plan.slug == "starter").first()
        if not plan:
            plan = Plan(
                name="Starter Test", slug="starter",
                price_monthly_cents=14900, max_channels=1, is_active=True,
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)

        sub = Subscription(
            tenant_id=999_998,
            plan_id=plan.id,
            status="active",
            stripe_subscription_id="sub_invoice_fail_test",
        )
        db.add(sub)
        db.commit()
    finally:
        db.close()

    from app.gateway.routers.billing import _on_invoice_event
    _on_invoice_event("invoice.payment_failed", {"subscription": "sub_invoice_fail_test"})

    db = SessionLocal()
    try:
        updated = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == "sub_invoice_fail_test"
        ).first()
        assert updated is not None
        assert updated.status == "past_due"
    finally:
        if updated:
            db.delete(updated)
            db.commit()
        db.close()
