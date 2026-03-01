"""Sprint 2 – Agent Tools & Knowledge + Integrations Management Tests

Tests:
  S2.1: KnowledgeAdapter (4 capabilities)
  S2.2: MemberMemoryAdapter (5 capabilities)
  S2.3: WhatsApp Flows Skill Update
  S2.4: AdapterRegistry (9 total adapters: 3 Phase 2 + 4 Sprint 1 + 2 Sprint 2)
  S2.5: Backend API Endpoints (connector_hub extensions)
  S2.6: Connector Documentation (CONNECTOR_DOCS structure)
  S2.7: Frontend RBAC + SettingsSubnav
  S2.8: i18n Keys (admin + docs)
"""

import os
import sys
import asyncio
import json

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "testing")

RESULTS = {"passed": 0, "failed": 0, "errors": []}


def test(name):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper():
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(result)
                    finally:
                        loop.close()
                RESULTS["passed"] += 1
                print(f"  ✅ {name}")
            except Exception as e:
                RESULTS["failed"] += 1
                RESULTS["errors"].append(f"{name}: {e}")
                print(f"  ❌ {name}: {e}")
        wrapper._test_name = name
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# S2.1: KnowledgeAdapter
# ═══════════════════════════════════════════════════════════════════════════════

print("\n📚 S2.1: KnowledgeAdapter")

@test("KnowledgeAdapter importierbar")
def test_knowledge_import():
    from app.integrations.adapters.knowledge_adapter import KnowledgeAdapter
    adapter = KnowledgeAdapter()
    assert adapter is not None

@test("KnowledgeAdapter integration_id = 'knowledge'")
def test_knowledge_id():
    from app.integrations.adapters.knowledge_adapter import KnowledgeAdapter
    adapter = KnowledgeAdapter()
    assert adapter.integration_id == "knowledge"

@test("KnowledgeAdapter hat 6 Capabilities")
def test_knowledge_capabilities():
    from app.integrations.adapters.knowledge_adapter import KnowledgeAdapter
    adapter = KnowledgeAdapter()
    expected = [
        "knowledge.search",
        "knowledge.ingest",
        "knowledge.list_collections",
        "knowledge.document.add",
        "knowledge.document.delete",
        "knowledge.stats",
    ]
    for cap in expected:
        assert cap in adapter.supported_capabilities, f"Missing: {cap}"

@test("KnowledgeAdapter Capabilities starten mit 'knowledge.'")
def test_knowledge_category():
    from app.integrations.adapters.knowledge_adapter import KnowledgeAdapter
    adapter = KnowledgeAdapter()
    for cap in adapter.supported_capabilities:
        assert cap.startswith("knowledge."), f"Capability '{cap}' startet nicht mit 'knowledge.'"

@test("KnowledgeAdapter health_check definiert")
def test_knowledge_health():
    from app.integrations.adapters.knowledge_adapter import KnowledgeAdapter
    adapter = KnowledgeAdapter()
    assert hasattr(adapter, "health_check")
    assert callable(adapter.health_check)

@test("KnowledgeAdapter execute_capability für unbekannte Capability gibt Fehler")
async def test_knowledge_unknown_cap():
    from app.integrations.adapters.knowledge_adapter import KnowledgeAdapter
    adapter = KnowledgeAdapter()
    result = await adapter.execute_capability("knowledge.nonexistent", tenant_id=1)
    assert result.success is False, "Sollte fehlschlagen für unbekannte Capability"
    assert "unsupported" in (result.error_code or "").lower() or "not supported" in (result.error or "").lower()

test_knowledge_import()
test_knowledge_id()
test_knowledge_capabilities()
test_knowledge_category()
test_knowledge_health()
test_knowledge_unknown_cap()


# ═══════════════════════════════════════════════════════════════════════════════
# S2.2: MemberMemoryAdapter
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🧠 S2.2: MemberMemoryAdapter")

@test("MemberMemoryAdapter importierbar")
def test_memory_import():
    from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter
    adapter = MemberMemoryAdapter()
    assert adapter is not None

@test("MemberMemoryAdapter integration_id = 'member_memory'")
def test_memory_id():
    from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter
    adapter = MemberMemoryAdapter()
    assert adapter.integration_id == "member_memory"

@test("MemberMemoryAdapter hat 5 Capabilities")
def test_memory_capabilities():
    from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter
    adapter = MemberMemoryAdapter()
    expected = [
        "memory.member.search",
        "memory.member.summary",
        "memory.member.history",
        "memory.member.index",
        "memory.member.list",
    ]
    for cap in expected:
        assert cap in adapter.supported_capabilities, f"Missing: {cap}"

@test("MemberMemoryAdapter Capabilities starten mit 'memory.'")
def test_memory_category():
    from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter
    adapter = MemberMemoryAdapter()
    for cap in adapter.supported_capabilities:
        assert cap.startswith("memory."), f"Capability '{cap}' startet nicht mit 'memory.'"

@test("MemberMemoryAdapter health_check definiert")
def test_memory_health():
    from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter
    adapter = MemberMemoryAdapter()
    assert hasattr(adapter, "health_check")
    assert callable(adapter.health_check)

@test("MemberMemoryAdapter execute_capability für unbekannte Capability")
async def test_memory_unknown_cap():
    from app.integrations.adapters.member_memory_adapter import MemberMemoryAdapter
    adapter = MemberMemoryAdapter()
    result = await adapter.execute_capability("memory.nonexistent", tenant_id=1)
    assert result.success is False, "Sollte fehlschlagen für unbekannte Capability"
    assert "unsupported" in (result.error_code or "").lower() or "not supported" in (result.error or "").lower()

test_memory_import()
test_memory_id()
test_memory_capabilities()
test_memory_category()
test_memory_health()
test_memory_unknown_cap()


# ═══════════════════════════════════════════════════════════════════════════════
# S2.3: WhatsApp Flows Skill Update
# ═══════════════════════════════════════════════════════════════════════════════

print("\n📱 S2.3: WhatsApp Flows Skill")

@test("WhatsApp SKILL.md existiert und enthält Flow-Capabilities")
def test_wa_skill():
    skill_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "messaging", "whatsapp.SKILL.md")
    assert os.path.exists(skill_path), f"SKILL.md nicht gefunden: {skill_path}"
    with open(skill_path) as f:
        content = f.read()
    assert "flow_booking" in content, "flow_booking nicht in SKILL.md"
    assert "flow_time_slots" in content, "flow_time_slots nicht in SKILL.md"
    assert "flow_cancellation" in content, "flow_cancellation nicht in SKILL.md"

@test("Knowledge SKILL.md existiert")
def test_knowledge_skill():
    skill_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "knowledge", "knowledge.SKILL.md")
    assert os.path.exists(skill_path), f"SKILL.md nicht gefunden: {skill_path}"
    with open(skill_path) as f:
        content = f.read()
    assert "knowledge.search" in content or "search" in content.lower()

@test("MemberMemory SKILL.md existiert")
def test_memory_skill():
    skill_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "knowledge", "member_memory.SKILL.md")
    assert os.path.exists(skill_path), f"SKILL.md nicht gefunden: {skill_path}"
    with open(skill_path) as f:
        content = f.read()
    assert "memory" in content.lower()

test_wa_skill()
test_knowledge_skill()
test_memory_skill()


# ═══════════════════════════════════════════════════════════════════════════════
# S2.4: AdapterRegistry (9 total adapters)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔌 S2.4: AdapterRegistry")

@test("AdapterRegistry enthält 9 Adapter (3 Phase 2 + 4 Sprint 1 + 2 Sprint 2)")
def test_registry_count():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    adapters = registry.registered_adapters
    assert len(adapters) >= 9, f"Erwartet >= 9, gefunden: {len(adapters)} → {list(adapters.keys())}"

@test("AdapterRegistry enthält knowledge Adapter")
def test_registry_knowledge():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    assert "knowledge" in registry, "knowledge nicht in Registry"

@test("AdapterRegistry enthält member_memory Adapter")
def test_registry_member_memory():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    assert "member_memory" in registry, "member_memory nicht in Registry"

@test("AdapterRegistry get_adapters_by_category('knowledge') liefert >= 1 Adapter")
def test_registry_knowledge_category():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    knowledge_adapters = registry.get_adapters_by_category("knowledge")
    assert len(knowledge_adapters) >= 1, f"Erwartet >= 1, gefunden: {len(knowledge_adapters)}"

@test("AdapterRegistry get_adapters_by_category('memory') liefert >= 1 Adapter")
def test_registry_memory_category():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    memory_adapters = registry.get_adapters_by_category("memory")
    assert len(memory_adapters) >= 1, f"Erwartet >= 1, gefunden: {len(memory_adapters)}"

@test("AdapterRegistry get_adapters_by_category('messaging') liefert >= 4 Adapter")
def test_registry_messaging_category():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    messaging_adapters = registry.get_adapters_by_category("messaging")
    assert len(messaging_adapters) >= 4, f"Erwartet >= 4, gefunden: {len(messaging_adapters)}"

test_registry_count()
test_registry_knowledge()
test_registry_member_memory()
test_registry_knowledge_category()
test_registry_memory_category()
test_registry_messaging_category()


# ═══════════════════════════════════════════════════════════════════════════════
# S2.5: Backend API Endpoints (connector_hub extensions)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🌐 S2.5: Backend API Endpoints")

@test("connector_hub.py enthält System-Admin CRUD Endpoints")
def test_api_system_crud():
    api_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "gateway", "routers", "connector_hub.py")
    with open(api_path) as f:
        content = f.read()
    assert "/system/connectors" in content, "GET /system/connectors fehlt"
    assert "POST" in content or "post" in content, "POST endpoint fehlt"
    assert "PUT" in content or "put" in content, "PUT endpoint fehlt"
    assert "DELETE" in content or "delete" in content, "DELETE endpoint fehlt"

@test("connector_hub.py enthält Docs-Endpoint")
def test_api_docs_endpoint():
    api_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "gateway", "routers", "connector_hub.py")
    with open(api_path) as f:
        content = f.read()
    assert "/docs" in content, "Docs endpoint fehlt"
    assert "docs/all" in content, "docs/all endpoint fehlt"

@test("connector_hub.py enthält Usage-Overview Endpoint")
def test_api_usage_overview():
    api_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "gateway", "routers", "connector_hub.py")
    with open(api_path) as f:
        content = f.read()
    assert "usage-overview" in content, "usage-overview endpoint fehlt"

test_api_system_crud()
test_api_docs_endpoint()
test_api_usage_overview()


# ═══════════════════════════════════════════════════════════════════════════════
# S2.6: Connector Documentation (CONNECTOR_DOCS structure)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n📖 S2.6: Connector Documentation")

@test("connector_docs.py existiert und ist importierbar")
def test_docs_import():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert isinstance(CONNECTOR_DOCS, dict)
    assert len(CONNECTOR_DOCS) > 0, "CONNECTOR_DOCS ist leer"

@test("CONNECTOR_DOCS enthält mindestens 5 Connectors")
def test_docs_count():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert len(CONNECTOR_DOCS) >= 5, f"Erwartet >= 5, gefunden: {len(CONNECTOR_DOCS)}"

@test("CONNECTOR_DOCS Einträge haben korrekte Struktur")
def test_docs_structure():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    required_fields = ["title", "overview", "difficulty", "estimated_time", "steps"]
    for connector_id, docs in CONNECTOR_DOCS.items():
        for field in required_fields:
            assert field in docs, f"{connector_id} fehlt Feld: {field}"

@test("CONNECTOR_DOCS WhatsApp hat Steps mit title und description")
def test_docs_whatsapp():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    assert "whatsapp" in CONNECTOR_DOCS, "whatsapp nicht in CONNECTOR_DOCS"
    wa_docs = CONNECTOR_DOCS["whatsapp"]
    assert len(wa_docs["steps"]) >= 3, f"WhatsApp hat zu wenige Steps: {len(wa_docs['steps'])}"
    for step in wa_docs["steps"]:
        assert "title" in step, "Step fehlt title"
        assert "description" in step, "Step fehlt description"

@test("CONNECTOR_DOCS hat FAQ und Troubleshooting")
def test_docs_faq_troubleshooting():
    from app.integrations.connector_docs import CONNECTOR_DOCS
    has_faq = any("faq" in docs for docs in CONNECTOR_DOCS.values())
    has_trouble = any("troubleshooting" in docs for docs in CONNECTOR_DOCS.values())
    assert has_faq, "Kein Connector hat FAQ"
    assert has_trouble, "Kein Connector hat Troubleshooting"

test_docs_import()
test_docs_count()
test_docs_structure()
test_docs_whatsapp()
test_docs_faq_troubleshooting()


# ═══════════════════════════════════════════════════════════════════════════════
# S2.7: Frontend RBAC + SettingsSubnav
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔐 S2.7: Frontend RBAC + SettingsSubnav")

@test("RBAC: system_admin hat /settings/integrations")
def test_rbac_system_admin():
    rbac_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "lib", "rbac.ts")
    with open(rbac_path) as f:
        content = f.read()
    # Find system_admin exact array (first occurrence after 'system_admin')
    import re
    sa_match = re.search(r'system_admin.*?exact:\s*\[(.*?)\]', content, re.DOTALL)
    assert sa_match, "system_admin exact block nicht gefunden"
    sa_exact = sa_match.group(1)
    assert "/settings/integrations" in sa_exact, f"system_admin hat kein /settings/integrations in exact: {sa_exact[:200]}"

@test("SettingsSubnav: system_admin sieht Integrations-Tab")
def test_subnav_system_admin():
    subnav_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "components", "settings", "SettingsSubnav.tsx")
    with open(subnav_path) as f:
        content = f.read()
    # Find system_admin filter
    sa_start = content.find("system_admin")
    sa_end = content.find("tenant_admin", sa_start)
    sa_block = content[sa_start:sa_end]
    assert "/settings/integrations" in sa_block, "SettingsSubnav: system_admin sieht Integrations nicht"

@test("Frontend: page.tsx enthält renderSystemAdminView")
def test_frontend_system_admin_view():
    page_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "app", "settings", "integrations", "page.tsx")
    with open(page_path) as f:
        content = f.read()
    assert "renderSystemAdminView" in content, "renderSystemAdminView fehlt"
    assert "renderDocsView" in content, "renderDocsView fehlt"

@test("Frontend: page.tsx importiert getStoredUser")
def test_frontend_auth_import():
    page_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "app", "settings", "integrations", "page.tsx")
    with open(page_path) as f:
        content = f.read()
    assert "getStoredUser" in content, "getStoredUser import fehlt"

@test("Frontend: page.tsx hat ViewState mit 'docs' und 'system_admin'")
def test_frontend_viewstate():
    page_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "app", "settings", "integrations", "page.tsx")
    with open(page_path) as f:
        content = f.read()
    assert '"docs"' in content, "ViewState 'docs' fehlt"
    assert '"system_admin"' in content, "ViewState 'system_admin' fehlt"

test_rbac_system_admin()
test_subnav_system_admin()
test_frontend_system_admin_view()
test_frontend_auth_import()
test_frontend_viewstate()


# ═══════════════════════════════════════════════════════════════════════════════
# S2.8: i18n Keys
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🌍 S2.8: i18n Keys")

@test("de.json enthält integrations.admin Keys")
def test_i18n_admin_de():
    locale_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "locales", "de.json")
    with open(locale_path) as f:
        data = json.load(f)
    admin = data.get("integrations", {}).get("admin", {})
    assert len(admin) > 0, "integrations.admin fehlt in de.json"
    assert "title" in admin, "admin.title fehlt"
    assert "create" in admin, "admin.create fehlt"
    assert "delete" in admin, "admin.delete fehlt"

@test("de.json enthält integrations.docs Keys")
def test_i18n_docs_de():
    locale_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "locales", "de.json")
    with open(locale_path) as f:
        data = json.load(f)
    docs = data.get("integrations", {}).get("docs", {})
    assert len(docs) > 0, "integrations.docs fehlt in de.json"
    assert "title" in docs, "docs.title fehlt"
    assert "prerequisites" in docs, "docs.prerequisites fehlt"
    assert "troubleshooting" in docs, "docs.troubleshooting fehlt"

@test("en.json enthält integrations.admin Keys")
def test_i18n_admin_en():
    locale_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "locales", "en.json")
    with open(locale_path) as f:
        data = json.load(f)
    admin = data.get("integrations", {}).get("admin", {})
    assert len(admin) > 0, "integrations.admin fehlt in en.json"

@test("en.json enthält integrations.docs Keys")
def test_i18n_docs_en():
    locale_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "locales", "en.json")
    with open(locale_path) as f:
        data = json.load(f)
    docs = data.get("integrations", {}).get("docs", {})
    assert len(docs) > 0, "integrations.docs fehlt in en.json"

test_i18n_admin_de()
test_i18n_docs_de()
test_i18n_admin_en()
test_i18n_docs_en()


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "═" * 60)
total = RESULTS["passed"] + RESULTS["failed"]
print(f"Sprint 2 Tests: {RESULTS['passed']}/{total} bestanden")
if RESULTS["errors"]:
    print("\nFehler:")
    for err in RESULTS["errors"]:
        print(f"  ❌ {err}")
print("═" * 60)

sys.exit(0 if RESULTS["failed"] == 0 else 1)
