#!/usr/bin/env python3
"""Sprint 5 – CRM & E-Commerce Adapter Test Suite.

Tests for WooCommerceAdapter, HubSpotAdapter, and SalesforceAdapter.
Validates imports, capabilities, error handling, registry integration,
connector docs, and skill files.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASSED = 0
FAILED = 0
ERRORS = []


def run_test(name, fn):
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
        print(f"  ✅ {name}")
    except Exception as e:
        FAILED += 1
        ERRORS.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


def run_async_test(name, coro_fn):
    global PASSED, FAILED
    try:
        asyncio.get_event_loop().run_until_complete(coro_fn())
        PASSED += 1
        print(f"  ✅ {name}")
    except Exception as e:
        FAILED += 1
        ERRORS.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


# ═══════════════════════════════════════════════════════════════════
# WooCommerce Adapter Tests
# ═══════════════════════════════════════════════════════════════════

print("\n🛒 WooCommerce Adapter Tests")
print("=" * 50)


def test_wc_import():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    assert WooCommerceAdapter is not None

run_test("import WooCommerceAdapter", test_wc_import)


def test_wc_integration_id():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    assert adapter.integration_id == "woocommerce"

run_test("integration_id == 'woocommerce'", test_wc_integration_id)


def test_wc_capabilities():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    expected = {
        "ecommerce.customer.search", "ecommerce.customer.create",
        "ecommerce.order.list", "ecommerce.order.status",
        "ecommerce.product.list", "ecommerce.product.search",
        "ecommerce.webhook.subscribe",
    }
    assert adapter.supported_capabilities == expected, f"Got: {adapter.supported_capabilities}"

run_test("7 capabilities defined", test_wc_capabilities)


def test_wc_not_configured():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    async def _run():
        result = await adapter.execute_capability("ecommerce.order.list", tenant_id=999)
        assert not result.success
        assert result.error_code == "NOT_CONFIGURED"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("not_configured error for unknown tenant", test_wc_not_configured)


def test_wc_unsupported_capability():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.com", "ck_test", "cs_test")
        result = await adapter.execute_capability("ecommerce.nonexistent", tenant_id=1)
        assert not result.success
        assert result.error_code == "UNSUPPORTED_CAPABILITY"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("unsupported capability error", test_wc_unsupported_capability)


def test_wc_missing_param_order_status():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.com", "ck_test", "cs_test")
        result = await adapter.execute_capability("ecommerce.order.status", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for order_status", test_wc_missing_param_order_status)


def test_wc_missing_param_customer_create():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.com", "ck_test", "cs_test")
        result = await adapter.execute_capability("ecommerce.customer.create", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for customer_create", test_wc_missing_param_customer_create)


def test_wc_missing_param_product_search():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.com", "ck_test", "cs_test")
        result = await adapter.execute_capability("ecommerce.product.search", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for product_search", test_wc_missing_param_product_search)


def test_wc_missing_param_webhook():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.com", "ck_test", "cs_test")
        result = await adapter.execute_capability("ecommerce.webhook.subscribe", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for webhook_subscribe", test_wc_missing_param_webhook)


def test_wc_configure_tenant():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    adapter.configure_tenant(42, "https://myshop.de", "ck_abc", "cs_xyz")
    config = adapter._clients.get(42)
    assert config is not None
    assert "myshop.de" in config["base_url"]
    assert config["consumer_key"] == "ck_abc"

run_test("configure_tenant stores credentials", test_wc_configure_tenant)


def test_wc_display_name():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    adapter = WooCommerceAdapter()
    assert adapter.display_name == "WooCommerce"

run_test("display_name == 'WooCommerce'", test_wc_display_name)


# ═══════════════════════════════════════════════════════════════════
# HubSpot Adapter Tests
# ═══════════════════════════════════════════════════════════════════

print("\n📊 HubSpot Adapter Tests")
print("=" * 50)


def test_hs_import():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    assert HubSpotAdapter is not None

run_test("import HubSpotAdapter", test_hs_import)


def test_hs_integration_id():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    assert adapter.integration_id == "hubspot"

run_test("integration_id == 'hubspot'", test_hs_integration_id)


def test_hs_capabilities():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    expected = {
        "crm.contact.search", "crm.contact.create", "crm.contact.update",
        "crm.deal.list", "crm.deal.create", "crm.company.search", "crm.ticket.create",
    }
    assert adapter.supported_capabilities == expected, f"Got: {adapter.supported_capabilities}"

run_test("7 capabilities defined", test_hs_capabilities)


def test_hs_not_configured():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    async def _run():
        result = await adapter.execute_capability("crm.contact.search", tenant_id=999)
        assert not result.success
        assert result.error_code == "NOT_CONFIGURED"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("not_configured error for unknown tenant", test_hs_not_configured)


def test_hs_missing_param_contact_create():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    async def _run():
        adapter.configure_tenant(1, "test_token")
        result = await adapter.execute_capability("crm.contact.create", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for contact_create", test_hs_missing_param_contact_create)


def test_hs_missing_param_contact_update():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    async def _run():
        adapter.configure_tenant(1, "test_token")
        result = await adapter.execute_capability("crm.contact.update", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for contact_update", test_hs_missing_param_contact_update)


def test_hs_missing_param_deal_create():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    async def _run():
        adapter.configure_tenant(1, "test_token")
        result = await adapter.execute_capability("crm.deal.create", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for deal_create", test_hs_missing_param_deal_create)


def test_hs_missing_param_ticket_create():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    async def _run():
        adapter.configure_tenant(1, "test_token")
        result = await adapter.execute_capability("crm.ticket.create", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for ticket_create", test_hs_missing_param_ticket_create)


def test_hs_configure_tenant():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    adapter.configure_tenant(42, "pat-na1-abc123")
    config = adapter._clients.get(42)
    assert config is not None
    assert config["access_token"] == "pat-na1-abc123"

run_test("configure_tenant stores credentials", test_hs_configure_tenant)


def test_hs_display_name():
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    adapter = HubSpotAdapter()
    assert adapter.display_name == "HubSpot"

run_test("display_name == 'HubSpot'", test_hs_display_name)


# ═══════════════════════════════════════════════════════════════════
# Salesforce Adapter Tests
# ═══════════════════════════════════════════════════════════════════

print("\n☁️ Salesforce Adapter Tests")
print("=" * 50)


def test_sf_import():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    assert SalesforceAdapter is not None

run_test("import SalesforceAdapter", test_sf_import)


def test_sf_integration_id():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    assert adapter.integration_id == "salesforce"

run_test("integration_id == 'salesforce'", test_sf_integration_id)


def test_sf_capabilities():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    expected = {
        "crm.contact.search", "crm.contact.create", "crm.contact.update",
        "crm.lead.create", "crm.opportunity.list", "crm.case.create", "crm.soql.query",
    }
    assert adapter.supported_capabilities == expected, f"Got: {adapter.supported_capabilities}"

run_test("7 capabilities defined", test_sf_capabilities)


def test_sf_not_configured():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    async def _run():
        result = await adapter.execute_capability("crm.contact.search", tenant_id=999)
        assert not result.success
        assert result.error_code == "NOT_CONFIGURED"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("not_configured error for unknown tenant", test_sf_not_configured)


def test_sf_missing_param_contact_create():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.salesforce.com", "token123")
        result = await adapter.execute_capability("crm.contact.create", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for contact_create (last_name)", test_sf_missing_param_contact_create)


def test_sf_missing_param_contact_update():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.salesforce.com", "token123")
        result = await adapter.execute_capability("crm.contact.update", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for contact_update (contact_id)", test_sf_missing_param_contact_update)


def test_sf_missing_param_lead_create():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.salesforce.com", "token123")
        result = await adapter.execute_capability("crm.lead.create", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for lead_create (last_name + company)", test_sf_missing_param_lead_create)


def test_sf_missing_param_case_create():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.salesforce.com", "token123")
        result = await adapter.execute_capability("crm.case.create", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for case_create (subject)", test_sf_missing_param_case_create)


def test_sf_missing_param_soql():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    async def _run():
        adapter.configure_tenant(1, "https://test.salesforce.com", "token123")
        result = await adapter.execute_capability("crm.soql.query", tenant_id=1)
        assert not result.success
        assert result.error_code == "MISSING_PARAM"
    asyncio.get_event_loop().run_until_complete(_run())

run_test("missing param for soql_query", test_sf_missing_param_soql)


def test_sf_configure_tenant():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    adapter.configure_tenant(42, "https://mycompany.salesforce.com", "token_abc")
    config = adapter._clients.get(42)
    assert config is not None
    assert "mycompany.salesforce.com" in config["instance_url"]
    assert config["access_token"] == "token_abc"
    assert "v66.0" in config["base_url"]

run_test("configure_tenant stores credentials", test_sf_configure_tenant)


def test_sf_display_name():
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    adapter = SalesforceAdapter()
    assert adapter.display_name == "Salesforce"

run_test("display_name == 'Salesforce'", test_sf_display_name)


# ═══════════════════════════════════════════════════════════════════
# Registry Integration Tests
# ═══════════════════════════════════════════════════════════════════

print("\n📦 Registry Integration Tests")
print("=" * 50)


def test_registry_contains_woocommerce():
    from app.integrations.adapters.registry import AdapterRegistry
    registry = AdapterRegistry()
    adapter = registry.get_adapter("woocommerce")
    assert adapter is not None, "woocommerce not in registry"
    assert adapter.integration_id == "woocommerce"

run_test("registry contains woocommerce", test_registry_contains_woocommerce)


def test_registry_contains_hubspot():
    from app.integrations.adapters.registry import AdapterRegistry
    registry = AdapterRegistry()
    adapter = registry.get_adapter("hubspot")
    assert adapter is not None, "hubspot not in registry"
    assert adapter.integration_id == "hubspot"

run_test("registry contains hubspot", test_registry_contains_hubspot)


def test_registry_contains_salesforce():
    from app.integrations.adapters.registry import AdapterRegistry
    registry = AdapterRegistry()
    adapter = registry.get_adapter("salesforce")
    assert adapter is not None, "salesforce not in registry"
    assert adapter.integration_id == "salesforce"

run_test("registry contains salesforce", test_registry_contains_salesforce)


def test_registry_total_count():
    from app.integrations.adapters.registry import AdapterRegistry
    registry = AdapterRegistry()
    all_adapters = registry._adapters
    assert len(all_adapters) >= 18, f"Expected >= 18 adapters, got {len(all_adapters)}"

run_test("registry has >= 18 adapters total", test_registry_total_count)


# ═══════════════════════════════════════════════════════════════════
# Connector Docs Tests
# ═══════════════════════════════════════════════════════════════════

print("\n📖 Connector Docs Tests")
print("=" * 50)


def test_docs_woocommerce():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "woocommerce" in CONNECTOR_DOCS
    doc = CONNECTOR_DOCS["woocommerce"]
    assert "title" in doc
    assert "steps" in doc
    assert len(doc["steps"]) >= 3

run_test("woocommerce docs exist with steps", test_docs_woocommerce)


def test_docs_hubspot():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "hubspot" in CONNECTOR_DOCS
    doc = CONNECTOR_DOCS["hubspot"]
    assert "title" in doc
    assert "steps" in doc
    assert len(doc["steps"]) >= 3

run_test("hubspot docs exist with steps", test_docs_hubspot)


def test_docs_salesforce():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "salesforce" in CONNECTOR_DOCS
    doc = CONNECTOR_DOCS["salesforce"]
    assert "title" in doc
    assert "steps" in doc
    assert len(doc["steps"]) >= 3

run_test("salesforce docs exist with steps", test_docs_salesforce)


# ═══════════════════════════════════════════════════════════════════
# Skill File Tests
# ═══════════════════════════════════════════════════════════════════

print("\n📝 Skill File Tests")
print("=" * 50)


def test_skill_woocommerce():
    path = os.path.join(os.path.dirname(__file__), "..", "skills", "ecommerce", "woocommerce.SKILL.md")
    assert os.path.exists(path), f"File not found: {path}"
    with open(path) as f:
        content = f.read()
    assert "woocommerce" in content.lower()
    assert "ecommerce.customer.search" in content

run_test("woocommerce.SKILL.md exists and valid", test_skill_woocommerce)


def test_skill_hubspot():
    path = os.path.join(os.path.dirname(__file__), "..", "skills", "crm", "hubspot.SKILL.md")
    assert os.path.exists(path), f"File not found: {path}"
    with open(path) as f:
        content = f.read()
    assert "hubspot" in content.lower()
    assert "crm.contact.search" in content

run_test("hubspot.SKILL.md exists and valid", test_skill_hubspot)


def test_skill_salesforce():
    path = os.path.join(os.path.dirname(__file__), "..", "skills", "crm", "salesforce.SKILL.md")
    assert os.path.exists(path), f"File not found: {path}"
    with open(path) as f:
        content = f.read()
    assert "salesforce" in content.lower()
    assert "crm.soql.query" in content

run_test("salesforce.SKILL.md exists and valid", test_skill_salesforce)


# ═══════════════════════════════════════════════════════════════════
# BaseAdapter Compliance Tests
# ═══════════════════════════════════════════════════════════════════

print("\n🔧 BaseAdapter Compliance Tests")
print("=" * 50)


def test_all_inherit_base():
    from app.integrations.adapters.base import BaseAdapter
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    assert issubclass(WooCommerceAdapter, BaseAdapter)
    assert issubclass(HubSpotAdapter, BaseAdapter)
    assert issubclass(SalesforceAdapter, BaseAdapter)

run_test("all adapters inherit from BaseAdapter", test_all_inherit_base)


def test_all_have_health_check():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    for cls in [WooCommerceAdapter, HubSpotAdapter, SalesforceAdapter]:
        assert hasattr(cls, "health_check"), f"{cls.__name__} missing health_check"

run_test("all adapters have health_check method", test_all_have_health_check)


def test_all_have_version():
    from app.integrations.adapters.woocommerce_adapter import WooCommerceAdapter
    from app.integrations.adapters.hubspot_adapter import HubSpotAdapter
    from app.integrations.adapters.salesforce_adapter import SalesforceAdapter
    for cls in [WooCommerceAdapter, HubSpotAdapter, SalesforceAdapter]:
        adapter = cls()
        assert hasattr(adapter, "version"), f"{cls.__name__} missing version"
        assert adapter.version == "1.0.0"

run_test("all adapters have version 1.0.0", test_all_have_version)


# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 50)
total = PASSED + FAILED
print(f"Sprint 5 Tests: {PASSED}/{total} passed")
if ERRORS:
    print("\nFailed tests:")
    for name, err in ERRORS:
        print(f"  - {name}: {err}")
if FAILED == 0:
    print("🎉 All tests passed!")
sys.exit(0 if FAILED == 0 else 1)
