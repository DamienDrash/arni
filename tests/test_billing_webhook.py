"""Tests für K2: Stripe Billing Webhook + Checkout Endpoints (V2).

Verifies:
  1. /admin/billing/plans ist öffentlich erreichbar (kein Auth)
  2. /admin/billing/checkout-session → auth required; 402/422 wenn Stripe nicht konfiguriert
  3. /admin/billing/customer-portal → auth required
  4. Webhook: Kein Webhook-Secret → 400
  5. Webhook: Ungültige Signatur → 400
  6. Webhook: checkout.session.completed → handled without server error
  7. Webhook: invoice.payment_failed → Subscription.status = 'past_due' (V2 handler)
  8. Plan-Katalog enthält mind. 3 Pläne mit korrekten Feldern

Subscription-deleted handler coverage lives in test_webhook_processor_contract.py.
"""

import json
import time
import hmac
import hashlib
import pytest
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
            "accept_tos": True,
            "accept_privacy": True,
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
    """/admin/billing/plans erfordert kein Auth."""
    resp = await client.get("/admin/billing/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert isinstance(plans, list)
    assert len(plans) >= 3  # Starter, Pro, Enterprise


@pytest.mark.anyio
async def test_billing_plans_have_required_fields(client: AsyncClient) -> None:
    """Jeder Plan hat Pflichtfelder inkl. legacy-kompatibler features-Liste."""
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


# ── 2. Checkout-Session ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_checkout_session_requires_auth() -> None:
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/admin/billing/checkout-session",
            json={"plan_slug": "pro"},
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_checkout_session_returns_4xx_when_stripe_not_working(client: AsyncClient) -> None:
    """Wenn Stripe nicht konfiguriert oder fehlerhaft → 4xx oder 502."""
    token, _ = await _register_tenant(client, "co-disabled")
    resp = await client.post(
        "/admin/billing/checkout-session",
        headers=_auth_header(token),
        json={"plan_slug": "pro"},
    )
    # Stripe not activated → 422; activated with invalid key → 502
    assert resp.status_code in (402, 422, 502), f"Unexpected: {resp.status_code} — {resp.text}"


# ── 3. Customer Portal ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_customer_portal_requires_auth() -> None:
    from httpx import AsyncClient, ASGITransport
    from app.gateway.main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/admin/billing/customer-portal",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_customer_portal_returns_error_without_stripe(client: AsyncClient) -> None:
    """Ohne Stripe-Konfiguration → Fehler-Response."""
    token, _ = await _register_tenant(client, "portal-no-sub")
    resp = await client.post(
        "/admin/billing/customer-portal",
        headers=_auth_header(token),
    )
    assert resp.status_code in (402, 404, 422, 502)


# ── 4. Webhook ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_webhook_rejects_missing_secret(client: AsyncClient) -> None:
    """Kein Webhook-Secret konfiguriert → 400."""
    resp = await client.post(
        "/admin/billing/webhook",
        content=b'{"type":"test"}',
        headers={"stripe-signature": "t=1,v1=abc", "content-type": "application/json"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_webhook_rejects_invalid_signature(client: AsyncClient) -> None:
    """Ungültige Stripe-Signatur → 400."""
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
async def test_webhook_checkout_completed_returns_200_or_400(client: AsyncClient) -> None:
    """checkout.session.completed webhook path — no server error."""
    from app.core.db import SessionLocal
    from app.domains.billing.models import Plan

    token, tenant_id = await _register_tenant(client, "wh-checkout")

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

    resp = await client.post(
        "/admin/billing/webhook",
        content=payload_bytes,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )
    # Without matching webhook secret in DB → 400; with valid secret → 200
    assert resp.status_code in (200, 400)


@pytest.mark.anyio
async def test_webhook_invoice_payment_failed_sets_past_due() -> None:
    """invoice.payment_failed → SubscriptionV2.status = 'past_due' (V2 handler)."""
    from app.core.db import SessionLocal
    from app.billing.models import PlanV2, SubscriptionV2
    from app.billing.webhook_processor import webhook_processor

    db = SessionLocal()
    try:
        plan = db.query(PlanV2).filter(PlanV2.slug == "starter").first()
        if not plan:
            plan = PlanV2(
                name="Starter Test",
                slug="starter-v2-test-fail",
                price_monthly_cents=0,
                is_active=True,
                is_public=False,
            )
            db.add(plan)
            db.flush()
        plan_id = plan.id

        sub = SubscriptionV2(
            tenant_id=999_997,
            plan_id=plan_id,
            status="active",
            stripe_subscription_id="sub_v2_invoice_fail_test",
            stripe_customer_id="cus_v2_invoice_fail_test",
        )
        db.add(sub)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        event = {
            "id": "evt_v2_invoice_fail",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "inv_v2_test",
                    "customer": "cus_v2_invoice_fail_test",
                    "amount_due": 1490,
                    "attempt_count": 1,
                }
            },
        }
        await webhook_processor._handle_invoice_payment_failed(db, event)
        db.commit()

        db.expire_all()
        updated = db.query(SubscriptionV2).filter(
            SubscriptionV2.stripe_customer_id == "cus_v2_invoice_fail_test"
        ).first()
        assert updated is not None
        status_val = updated.status.value if hasattr(updated.status, "value") else updated.status
        assert status_val == "past_due"
    finally:
        db.query(SubscriptionV2).filter(
            SubscriptionV2.stripe_customer_id == "cus_v2_invoice_fail_test"
        ).delete()
        db.commit()
        db.close()
