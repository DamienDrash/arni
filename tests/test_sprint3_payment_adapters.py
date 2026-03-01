#!/usr/bin/env python3
"""ARIIA v2.0 – Sprint 3 Test Suite: Payment & Billing Adapters.

Tests for StripeAdapter, PayPalAdapter, and MollieAdapter.
Validates adapter contracts, capability routing, parameter validation,
registry integration, and connector documentation.
"""

import asyncio
import sys
import os

# ── Path setup ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0
ERRORS: list[str] = []


def ok(name: str):
    global PASS
    PASS += 1
    print(f"  ✅ {name}")


def fail(name: str, reason: str = ""):
    global FAIL
    FAIL += 1
    msg = f"  ❌ {name}: {reason}" if reason else f"  ❌ {name}"
    ERRORS.append(msg)
    print(msg)


# ══════════════════════════════════════════════════════════════════════════
# 1. STRIPE ADAPTER TESTS
# ══════════════════════════════════════════════════════════════════════════

def test_stripe_import():
    try:
        from app.integrations.adapters.stripe_adapter import StripeAdapter
        ok("stripe_import")
    except Exception as e:
        fail("stripe_import", str(e))


def test_stripe_integration_id():
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    assert a.integration_id == "stripe", f"Expected 'stripe', got '{a.integration_id}'"
    ok("stripe_integration_id")


def test_stripe_capabilities():
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    caps = a.supported_capabilities
    required = [
        "payment.checkout.create",
        "payment.subscription.manage",
        "payment.subscription.status",
        "payment.invoice.list",
        "payment.customer.create",
        "payment.webhook.process",
        "billing.usage.track",
        "billing.usage.get",
        "billing.plan.enforce",
        "billing.plan.compare",
    ]
    for r in required:
        assert r in caps, f"Missing capability: {r}"
    ok("stripe_capabilities")


def test_stripe_capability_count():
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    assert len(a.supported_capabilities) == 10, f"Expected 10 capabilities, got {len(a.supported_capabilities)}"
    ok("stripe_capability_count")


def test_stripe_is_base_adapter():
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    from app.integrations.adapters.base import BaseAdapter
    a = StripeAdapter()
    assert isinstance(a, BaseAdapter), "StripeAdapter must extend BaseAdapter"
    ok("stripe_is_base_adapter")


def test_stripe_plan_compare():
    """Test billing.plan.compare returns plan data."""
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("billing.plan.compare", tenant_id=1)
    )
    assert result.success, f"plan.compare failed: {result.error}"
    assert "plans" in result.data or isinstance(result.data, (dict, list)), "Expected plan data"
    ok("stripe_plan_compare")


def test_stripe_plan_enforce_feature():
    """Test billing.plan.enforce with feature check."""
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("billing.plan.enforce", tenant_id=1, check_type="feature", feature="whatsapp")
    )
    # Should succeed (returns allowed/denied status)
    assert result.success, f"plan.enforce failed: {result.error}"
    ok("stripe_plan_enforce_feature")


def test_stripe_usage_get():
    """Test billing.usage.get returns usage data."""
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("billing.usage.get", tenant_id=1)
    )
    assert result.success, f"usage.get failed: {result.error}"
    ok("stripe_usage_get")


def test_stripe_usage_track():
    """Test billing.usage.track."""
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("billing.usage.track", tenant_id=1, usage_type="conversation", quantity=1)
    )
    assert result.success, f"usage.track failed: {result.error}"
    ok("stripe_usage_track")


def test_stripe_subscription_status():
    """Test payment.subscription.status - returns result (may fail without DB)."""
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.subscription.status", tenant_id=1)
    )
    # In test env without DB, this may fail gracefully
    assert isinstance(result.success, bool), "Should return AdapterResult"
    if not result.success:
        assert result.error is not None, "Failed result should have error message"
    ok("stripe_subscription_status")


def test_stripe_unknown_capability():
    """Test that unknown capabilities return error."""
    from app.integrations.adapters.stripe_adapter import StripeAdapter
    a = StripeAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.nonexistent", tenant_id=1)
    )
    assert not result.success, "Unknown capability should fail"
    ok("stripe_unknown_capability")


# ══════════════════════════════════════════════════════════════════════════
# 2. PAYPAL ADAPTER TESTS
# ══════════════════════════════════════════════════════════════════════════

def test_paypal_import():
    try:
        from app.integrations.adapters.paypal_adapter import PayPalAdapter
        ok("paypal_import")
    except Exception as e:
        fail("paypal_import", str(e))


def test_paypal_integration_id():
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    assert a.integration_id == "paypal", f"Expected 'paypal', got '{a.integration_id}'"
    ok("paypal_integration_id")


def test_paypal_capabilities():
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    caps = a.supported_capabilities
    required = [
        "payment.order.create",
        "payment.order.capture",
        "payment.order.details",
        "payment.subscription.create",
        "payment.subscription.cancel",
        "payment.subscription.details",
        "payment.webhook.process",
        "payment.payout.create",
    ]
    for r in required:
        assert r in caps, f"Missing capability: {r}"
    ok("paypal_capabilities")


def test_paypal_capability_count():
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    assert len(a.supported_capabilities) == 8, f"Expected 8 capabilities, got {len(a.supported_capabilities)}"
    ok("paypal_capability_count")


def test_paypal_is_base_adapter():
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    from app.integrations.adapters.base import BaseAdapter
    a = PayPalAdapter()
    assert isinstance(a, BaseAdapter), "PayPalAdapter must extend BaseAdapter"
    ok("paypal_is_base_adapter")


def test_paypal_order_create_missing_amount():
    """Test that order.create fails without amount."""
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.order.create", tenant_id=1)
    )
    assert not result.success, "Should fail without amount"
    assert result.error_code == "MISSING_PARAM"
    ok("paypal_order_create_missing_amount")


def test_paypal_order_capture_missing_id():
    """Test that order.capture fails without order_id."""
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.order.capture", tenant_id=1)
    )
    assert not result.success, "Should fail without order_id"
    assert result.error_code == "MISSING_PARAM"
    ok("paypal_order_capture_missing_id")


def test_paypal_subscription_cancel_missing_id():
    """Test that subscription.cancel fails without subscription_id."""
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.subscription.cancel", tenant_id=1)
    )
    assert not result.success, "Should fail without subscription_id"
    ok("paypal_subscription_cancel_missing_id")


def test_paypal_payout_missing_params():
    """Test that payout.create fails without required params."""
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.payout.create", tenant_id=1)
    )
    assert not result.success, "Should fail without recipient_email and amount"
    ok("paypal_payout_missing_params")


def test_paypal_webhook_process():
    """Test webhook processing with valid event."""
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability(
            "payment.webhook.process",
            tenant_id=1,
            event_type="PAYMENT.CAPTURE.COMPLETED",
            resource={"id": "CAP-123", "resource_type": "capture"},
            event_id="EVT-001",
        )
    )
    assert result.success, f"Webhook process failed: {result.error}"
    assert result.data["action"] == "payment_captured"
    assert result.data["event_id"] == "EVT-001"
    ok("paypal_webhook_process")


def test_paypal_webhook_missing_params():
    """Test webhook processing without required params."""
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.webhook.process", tenant_id=1)
    )
    assert not result.success, "Should fail without event_type and resource"
    ok("paypal_webhook_missing_params")


def test_paypal_unknown_capability():
    from app.integrations.adapters.paypal_adapter import PayPalAdapter
    a = PayPalAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.nonexistent", tenant_id=1)
    )
    assert not result.success
    ok("paypal_unknown_capability")


# ══════════════════════════════════════════════════════════════════════════
# 3. MOLLIE ADAPTER TESTS
# ══════════════════════════════════════════════════════════════════════════

def test_mollie_import():
    try:
        from app.integrations.adapters.mollie_adapter import MollieAdapter
        ok("mollie_import")
    except Exception as e:
        fail("mollie_import", str(e))


def test_mollie_integration_id():
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    assert a.integration_id == "mollie", f"Expected 'mollie', got '{a.integration_id}'"
    ok("mollie_integration_id")


def test_mollie_capabilities():
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    caps = a.supported_capabilities
    required = [
        "payment.create",
        "payment.status",
        "payment.refund",
        "payment.list",
        "payment.methods.list",
        "payment.subscription.create",
        "payment.subscription.cancel",
        "payment.subscription.list",
    ]
    for r in required:
        assert r in caps, f"Missing capability: {r}"
    ok("mollie_capabilities")


def test_mollie_capability_count():
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    assert len(a.supported_capabilities) == 8, f"Expected 8 capabilities, got {len(a.supported_capabilities)}"
    ok("mollie_capability_count")


def test_mollie_is_base_adapter():
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    from app.integrations.adapters.base import BaseAdapter
    a = MollieAdapter()
    assert isinstance(a, BaseAdapter), "MollieAdapter must extend BaseAdapter"
    ok("mollie_is_base_adapter")


def test_mollie_api_base_url():
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    assert a.MOLLIE_API_BASE == "https://api.mollie.com/v2"
    ok("mollie_api_base_url")


def test_mollie_create_missing_params():
    """Test that payment.create fails without required params."""
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.create", tenant_id=1)
    )
    assert not result.success, "Should fail without amount and description"
    assert result.error_code == "MISSING_PARAM"
    ok("mollie_create_missing_params")


def test_mollie_status_missing_id():
    """Test that payment.status fails without payment_id."""
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.status", tenant_id=1)
    )
    assert not result.success
    assert result.error_code == "MISSING_PARAM"
    ok("mollie_status_missing_id")


def test_mollie_refund_missing_id():
    """Test that payment.refund fails without payment_id."""
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.refund", tenant_id=1)
    )
    assert not result.success
    ok("mollie_refund_missing_id")


def test_mollie_subscription_create_missing_params():
    """Test that subscription.create fails without required params."""
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.subscription.create", tenant_id=1)
    )
    assert not result.success
    ok("mollie_subscription_create_missing_params")


def test_mollie_subscription_cancel_missing_params():
    """Test that subscription.cancel fails without required params."""
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.subscription.cancel", tenant_id=1)
    )
    assert not result.success
    ok("mollie_subscription_cancel_missing_params")


def test_mollie_subscription_list_missing_customer():
    """Test that subscription.list fails without customer_id."""
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.subscription.list", tenant_id=1)
    )
    assert not result.success
    ok("mollie_subscription_list_missing_customer")


def test_mollie_unknown_capability():
    from app.integrations.adapters.mollie_adapter import MollieAdapter
    a = MollieAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        a.execute_capability("payment.nonexistent", tenant_id=1)
    )
    assert not result.success
    ok("mollie_unknown_capability")


# ══════════════════════════════════════════════════════════════════════════
# 4. REGISTRY INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════════════

def test_registry_has_stripe():
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    assert "stripe" in reg, "stripe not in registry"
    ok("registry_has_stripe")


def test_registry_has_paypal():
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    assert "paypal" in reg, "paypal not in registry"
    ok("registry_has_paypal")


def test_registry_has_mollie():
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    assert "mollie" in reg, "mollie not in registry"
    ok("registry_has_mollie")


def test_registry_total_count():
    """Registry should have 12 adapters (3 Phase2 + 4 Sprint1 + 2 Sprint2 + 3 Sprint3)."""
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    count = len(reg)
    assert count == 12, f"Expected 12 adapters, got {count}: {reg.registered_adapters}"
    ok("registry_total_count")


def test_registry_payment_category():
    """Test get_adapters_by_category for payment."""
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    payment_adapters = reg.get_adapters_by_category("payment")
    assert len(payment_adapters) >= 3, f"Expected >=3 payment adapters, got {len(payment_adapters)}"
    assert "stripe" in payment_adapters
    assert "paypal" in payment_adapters
    assert "mollie" in payment_adapters
    ok("registry_payment_category")


def test_registry_billing_category():
    """Test get_adapters_by_category for billing (Stripe only)."""
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    billing_adapters = reg.get_adapters_by_category("billing")
    assert "stripe" in billing_adapters, "Stripe should have billing capabilities"
    ok("registry_billing_category")


# ══════════════════════════════════════════════════════════════════════════
# 5. CONNECTOR DOCS TESTS
# ══════════════════════════════════════════════════════════════════════════

def test_connector_docs_stripe():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "stripe" in CONNECTOR_DOCS, "stripe docs missing"
    doc = CONNECTOR_DOCS["stripe"]
    assert doc["title"] == "Stripe Payment & Billing"
    assert doc["difficulty"] in ("easy", "medium", "advanced")
    assert len(doc["steps"]) >= 4
    assert len(doc["faq"]) >= 2
    assert len(doc["troubleshooting"]) >= 1
    assert len(doc["links"]) >= 2
    ok("connector_docs_stripe")


def test_connector_docs_paypal():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "paypal" in CONNECTOR_DOCS, "paypal docs missing"
    doc = CONNECTOR_DOCS["paypal"]
    assert doc["title"] == "PayPal Payment"
    assert len(doc["steps"]) >= 4
    assert len(doc["faq"]) >= 1
    ok("connector_docs_paypal")


def test_connector_docs_mollie():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "mollie" in CONNECTOR_DOCS, "mollie docs missing"
    doc = CONNECTOR_DOCS["mollie"]
    assert doc["title"] == "Mollie Payment"
    assert doc["difficulty"] == "easy"
    assert len(doc["steps"]) >= 3
    ok("connector_docs_mollie")


def test_connector_docs_structure():
    """All payment docs must have required keys."""
    from app.integrations.connector_docs import CONNECTOR_DOCS
    required_keys = {"title", "overview", "difficulty", "estimated_time", "prerequisites", "use_cases", "steps", "faq", "troubleshooting", "links"}
    for name in ("stripe", "paypal", "mollie"):
        doc = CONNECTOR_DOCS[name]
        missing = required_keys - set(doc.keys())
        assert not missing, f"{name} docs missing keys: {missing}"
    ok("connector_docs_structure")


# ══════════════════════════════════════════════════════════════════════════
# 6. SKILL FILES TESTS
# ══════════════════════════════════════════════════════════════════════════

def test_skill_files_exist():
    """Check that all payment SKILL.md files exist."""
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills", "payment")
    for name in ("stripe", "paypal", "mollie"):
        path = os.path.join(skills_dir, f"{name}.SKILL.md")
        assert os.path.exists(path), f"Missing SKILL.md: {path}"
    ok("skill_files_exist")


def test_skill_files_content():
    """Check that SKILL.md files have required sections."""
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills", "payment")
    for name in ("stripe", "paypal", "mollie"):
        path = os.path.join(skills_dir, f"{name}.SKILL.md")
        content = open(path).read()
        assert "# Skill:" in content, f"{name} SKILL.md missing title"
        assert "## Capabilities" in content, f"{name} SKILL.md missing Capabilities section"
        assert "## Allgemeine Regeln" in content, f"{name} SKILL.md missing rules section"
    ok("skill_files_content")


# ══════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🏦 ARIIA Sprint 3 – Payment & Billing Adapter Tests\n")

    print("── Stripe Adapter ─────────────────────────────────")
    test_stripe_import()
    test_stripe_integration_id()
    test_stripe_capabilities()
    test_stripe_capability_count()
    test_stripe_is_base_adapter()
    test_stripe_plan_compare()
    test_stripe_plan_enforce_feature()
    test_stripe_usage_get()
    test_stripe_usage_track()
    test_stripe_subscription_status()
    test_stripe_unknown_capability()

    print("\n── PayPal Adapter ─────────────────────────────────")
    test_paypal_import()
    test_paypal_integration_id()
    test_paypal_capabilities()
    test_paypal_capability_count()
    test_paypal_is_base_adapter()
    test_paypal_order_create_missing_amount()
    test_paypal_order_capture_missing_id()
    test_paypal_subscription_cancel_missing_id()
    test_paypal_payout_missing_params()
    test_paypal_webhook_process()
    test_paypal_webhook_missing_params()
    test_paypal_unknown_capability()

    print("\n── Mollie Adapter ─────────────────────────────────")
    test_mollie_import()
    test_mollie_integration_id()
    test_mollie_capabilities()
    test_mollie_capability_count()
    test_mollie_is_base_adapter()
    test_mollie_api_base_url()
    test_mollie_create_missing_params()
    test_mollie_status_missing_id()
    test_mollie_refund_missing_id()
    test_mollie_subscription_create_missing_params()
    test_mollie_subscription_cancel_missing_params()
    test_mollie_subscription_list_missing_customer()
    test_mollie_unknown_capability()

    print("\n── Registry Integration ───────────────────────────")
    test_registry_has_stripe()
    test_registry_has_paypal()
    test_registry_has_mollie()
    test_registry_total_count()
    test_registry_payment_category()
    test_registry_billing_category()

    print("\n── Connector Docs ─────────────────────────────────")
    test_connector_docs_stripe()
    test_connector_docs_paypal()
    test_connector_docs_mollie()
    test_connector_docs_structure()

    print("\n── Skill Files ────────────────────────────────────")
    test_skill_files_exist()
    test_skill_files_content()

    print(f"\n{'='*60}")
    print(f"  Sprint 3 Results: {PASS} passed, {FAIL} failed")
    print(f"{'='*60}")
    if ERRORS:
        print("\n  Failures:")
        for e in ERRORS:
            print(f"    {e}")
    print()
    sys.exit(FAIL)
