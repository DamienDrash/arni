#!/usr/bin/env python3
"""ARIIA Sprint 4 – Scheduling & Booking Adapter Tests.

Tests for CalendlyAdapter, CalComAdapter, AcuityAdapter,
AdapterRegistry integration, Connector Docs, and Skill files.
"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0

def ok(name):
    global passed
    passed += 1
    print(f"  \u2705 {name}")

def fail(name, msg=""):
    global failed
    failed += 1
    print(f"  \u274c {name}: {msg}")

def run(name, fn):
    try:
        fn()
        ok(name)
    except Exception as e:
        fail(name, str(e))

def run_async(name, coro_fn):
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(coro_fn())
        loop.close()
        ok(name)
    except Exception as e:
        fail(name, str(e))

# ═══════════════════════════════════════════════════════════════════
print("\U0001f4c5 ARIIA Sprint 4 \u2013 Scheduling & Booking Adapter Tests")

# ── Calendly Adapter ─────────────────────────────────────────────
print("\u2500\u2500 Calendly Adapter \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

def test_calendly_import():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    a = CalendlyAdapter()
    assert a is not None
run("calendly_import", test_calendly_import)

def test_calendly_integration_id():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    assert CalendlyAdapter().integration_id == "calendly"
run("calendly_integration_id", test_calendly_integration_id)

def test_calendly_capabilities():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    caps = CalendlyAdapter().supported_capabilities
    assert "scheduling.event_types.list" in caps
    assert "scheduling.events.list" in caps
    assert "scheduling.events.cancel" in caps
    assert "scheduling.availability.get" in caps
    assert "scheduling.invitee.list" in caps
    assert "scheduling.webhook.subscribe" in caps
run("calendly_capabilities", test_calendly_capabilities)

def test_calendly_capability_count():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    assert len(CalendlyAdapter().supported_capabilities) == 8
run("calendly_capability_count", test_calendly_capability_count)

def test_calendly_is_base_adapter():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    from app.integrations.adapters.base import BaseAdapter
    assert issubclass(CalendlyAdapter, BaseAdapter)
run("calendly_is_base_adapter", test_calendly_is_base_adapter)

async def test_calendly_unknown_cap():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    a = CalendlyAdapter()
    result = await a.execute_capability("scheduling.nonexistent", tenant_id=1)
    assert not result.success
    assert "not supported" in result.error
run_async("calendly_unknown_capability", test_calendly_unknown_cap)

async def test_calendly_not_configured():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    a = CalendlyAdapter()
    result = await a.execute_capability("scheduling.event_types.list", tenant_id=99999)
    assert not result.success
    assert "nicht konfiguriert" in result.error or "NOT_CONFIGURED" in (result.error_code or "")
run_async("calendly_not_configured", test_calendly_not_configured)

async def test_calendly_cancel_missing_param():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    a = CalendlyAdapter()
    result = await a.execute_capability("scheduling.events.cancel", tenant_id=1)
    assert not result.success
    assert "event_uuid" in result.error.lower() or "MISSING_PARAM" in (result.error_code or "")
run_async("calendly_cancel_missing_param", test_calendly_cancel_missing_param)

async def test_calendly_invitee_missing_param():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    a = CalendlyAdapter()
    result = await a.execute_capability("scheduling.invitee.list", tenant_id=1)
    assert not result.success
    assert "MISSING_PARAM" in (result.error_code or "")
run_async("calendly_invitee_missing_param", test_calendly_invitee_missing_param)

async def test_calendly_webhook_missing_param():
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter
    a = CalendlyAdapter()
    result = await a.execute_capability("scheduling.webhook.subscribe", tenant_id=1)
    assert not result.success
run_async("calendly_webhook_missing_param", test_calendly_webhook_missing_param)

# ── Cal.com Adapter ──────────────────────────────────────────────
print("\u2500\u2500 Cal.com Adapter \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

def test_calcom_import():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    a = CalComAdapter()
    assert a is not None
run("calcom_import", test_calcom_import)

def test_calcom_integration_id():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    assert CalComAdapter().integration_id == "calcom"
run("calcom_integration_id", test_calcom_integration_id)

def test_calcom_capabilities():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    caps = CalComAdapter().supported_capabilities
    assert "scheduling.event_types.list" in caps
    assert "scheduling.bookings.list" in caps
    assert "scheduling.bookings.create" in caps
    assert "scheduling.bookings.cancel" in caps
    assert "scheduling.bookings.reschedule" in caps
    assert "scheduling.availability.get" in caps
    assert "scheduling.slots.list" in caps
run("calcom_capabilities", test_calcom_capabilities)

def test_calcom_capability_count():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    assert len(CalComAdapter().supported_capabilities) == 7
run("calcom_capability_count", test_calcom_capability_count)

def test_calcom_is_base_adapter():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    from app.integrations.adapters.base import BaseAdapter
    assert issubclass(CalComAdapter, BaseAdapter)
run("calcom_is_base_adapter", test_calcom_is_base_adapter)

async def test_calcom_unknown_cap():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    a = CalComAdapter()
    result = await a.execute_capability("scheduling.nonexistent", tenant_id=1)
    assert not result.success
run_async("calcom_unknown_capability", test_calcom_unknown_cap)

async def test_calcom_not_configured():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    a = CalComAdapter()
    result = await a.execute_capability("scheduling.event_types.list", tenant_id=99999)
    assert not result.success
run_async("calcom_not_configured", test_calcom_not_configured)

async def test_calcom_create_missing_params():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    a = CalComAdapter()
    result = await a.execute_capability("scheduling.bookings.create", tenant_id=1)
    assert not result.success
    assert "MISSING_PARAM" in (result.error_code or "")
run_async("calcom_create_missing_params", test_calcom_create_missing_params)

async def test_calcom_cancel_missing_param():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    a = CalComAdapter()
    result = await a.execute_capability("scheduling.bookings.cancel", tenant_id=1)
    assert not result.success
run_async("calcom_cancel_missing_param", test_calcom_cancel_missing_param)

async def test_calcom_reschedule_missing_params():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    a = CalComAdapter()
    result = await a.execute_capability("scheduling.bookings.reschedule", tenant_id=1)
    assert not result.success
run_async("calcom_reschedule_missing_params", test_calcom_reschedule_missing_params)

async def test_calcom_slots_missing_params():
    from app.integrations.adapters.calcom_adapter import CalComAdapter
    a = CalComAdapter()
    result = await a.execute_capability("scheduling.slots.list", tenant_id=1)
    assert not result.success
run_async("calcom_slots_missing_params", test_calcom_slots_missing_params)

# ── Acuity Adapter ───────────────────────────────────────────────
print("\u2500\u2500 Acuity Adapter \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

def test_acuity_import():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    a = AcuityAdapter()
    assert a is not None
run("acuity_import", test_acuity_import)

def test_acuity_integration_id():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    assert AcuityAdapter().integration_id == "acuity"
run("acuity_integration_id", test_acuity_integration_id)

def test_acuity_capabilities():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    caps = AcuityAdapter().supported_capabilities
    assert "scheduling.appointments.list" in caps
    assert "scheduling.appointments.create" in caps
    assert "scheduling.appointments.cancel" in caps
    assert "scheduling.appointments.reschedule" in caps
    assert "scheduling.availability.get" in caps
    assert "scheduling.calendars.list" in caps
    assert "scheduling.appointment_types.list" in caps
run("acuity_capabilities", test_acuity_capabilities)

def test_acuity_capability_count():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    assert len(AcuityAdapter().supported_capabilities) == 7
run("acuity_capability_count", test_acuity_capability_count)

def test_acuity_is_base_adapter():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    from app.integrations.adapters.base import BaseAdapter
    assert issubclass(AcuityAdapter, BaseAdapter)
run("acuity_is_base_adapter", test_acuity_is_base_adapter)

async def test_acuity_unknown_cap():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    a = AcuityAdapter()
    result = await a.execute_capability("scheduling.nonexistent", tenant_id=1)
    assert not result.success
run_async("acuity_unknown_capability", test_acuity_unknown_cap)

async def test_acuity_not_configured():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    a = AcuityAdapter()
    result = await a.execute_capability("scheduling.appointments.list", tenant_id=99999)
    assert not result.success
    assert "nicht konfiguriert" in result.error or "NOT_CONFIGURED" in (result.error_code or "")
run_async("acuity_not_configured", test_acuity_not_configured)

async def test_acuity_create_missing_params():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    a = AcuityAdapter()
    result = await a.execute_capability("scheduling.appointments.create", tenant_id=1)
    assert not result.success
    assert "MISSING_PARAM" in (result.error_code or "")
run_async("acuity_create_missing_params", test_acuity_create_missing_params)

async def test_acuity_cancel_missing_param():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    a = AcuityAdapter()
    result = await a.execute_capability("scheduling.appointments.cancel", tenant_id=1)
    assert not result.success
run_async("acuity_cancel_missing_param", test_acuity_cancel_missing_param)

async def test_acuity_reschedule_missing_params():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    a = AcuityAdapter()
    result = await a.execute_capability("scheduling.appointments.reschedule", tenant_id=1)
    assert not result.success
run_async("acuity_reschedule_missing_params", test_acuity_reschedule_missing_params)

async def test_acuity_availability_missing_params():
    from app.integrations.adapters.acuity_adapter import AcuityAdapter
    a = AcuityAdapter()
    result = await a.execute_capability("scheduling.availability.get", tenant_id=1)
    assert not result.success
    assert "MISSING_PARAM" in (result.error_code or "")
run_async("acuity_availability_missing_params", test_acuity_availability_missing_params)

# ── AdapterRegistry ──────────────────────────────────────────────
print("\u2500\u2500 AdapterRegistry \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

def test_registry_total_count():
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    assert len(reg) == 15, f"Expected 15, got {len(reg)}: {list(reg.registered_adapters.keys())}"
run("registry_total_count", test_registry_total_count)

def test_registry_scheduling_adapters():
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    assert "calendly" in reg
    assert "calcom" in reg
    assert "acuity" in reg
run("registry_scheduling_adapters", test_registry_scheduling_adapters)

def test_registry_scheduling_category():
    from app.integrations.adapters.registry import AdapterRegistry
    reg = AdapterRegistry()
    scheduling = reg.get_adapters_by_category("scheduling")
    assert len(scheduling) >= 3, f"Expected >=3 scheduling adapters, got {len(scheduling)}"
    assert "calendly" in scheduling
    assert "calcom" in scheduling
    assert "acuity" in scheduling
run("registry_scheduling_category", test_registry_scheduling_category)

# ── Connector Docs ───────────────────────────────────────────────
print("\u2500\u2500 Connector Docs \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

def test_connector_docs_calendly():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "calendly" in CONNECTOR_DOCS
    doc = CONNECTOR_DOCS["calendly"]
    assert doc["category"] == "scheduling"
    assert len(doc["setup_steps"]) >= 3
    assert len(doc["capabilities"]) >= 6
run("connector_docs_calendly", test_connector_docs_calendly)

def test_connector_docs_calcom():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "calcom" in CONNECTOR_DOCS
    doc = CONNECTOR_DOCS["calcom"]
    assert doc["category"] == "scheduling"
    assert len(doc["capabilities"]) >= 5
run("connector_docs_calcom", test_connector_docs_calcom)

def test_connector_docs_acuity():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "acuity" in CONNECTOR_DOCS
    doc = CONNECTOR_DOCS["acuity"]
    assert doc["category"] == "scheduling"
    assert len(doc["capabilities"]) >= 5
run("connector_docs_acuity", test_connector_docs_acuity)

def test_connector_docs_structure():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    for key in ["calendly", "calcom", "acuity"]:
        doc = CONNECTOR_DOCS[key]
        for field in ["display_name", "description", "category", "setup_steps", "capabilities", "faq", "troubleshooting", "links"]:
            assert field in doc, f"Missing '{field}' in {key} docs"
run("connector_docs_structure", test_connector_docs_structure)

# ── Skill Files ──────────────────────────────────────────────────
print("\u2500\u2500 Skill Files \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

def test_skill_files_exist():
    for path in [
        "skills/scheduling/calendly.SKILL.md",
        "skills/scheduling/calcom.SKILL.md",
        "skills/scheduling/acuity.SKILL.md",
    ]:
        assert os.path.exists(path), f"Missing: {path}"
run("skill_files_exist", test_skill_files_exist)

def test_skill_files_content():
    for path, adapter_id in [
        ("skills/scheduling/calendly.SKILL.md", "calendly"),
        ("skills/scheduling/calcom.SKILL.md", "calcom"),
        ("skills/scheduling/acuity.SKILL.md", "acuity"),
    ]:
        content = open(path).read()
        assert adapter_id in content, f"'{adapter_id}' not found in {path}"
        assert "Capability" in content or "capability" in content, f"No capabilities in {path}"
        assert len(content) > 200, f"Skill file too short: {path}"
run("skill_files_content", test_skill_files_content)

# ═══════════════════════════════════════════════════════════════════
print("=" * 60)
print(f"  Sprint 4 Results: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(1 if failed else 0)
