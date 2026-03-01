"""Tests for Phase 6: Die Öffnung – Skalierung & Ökosystem.

Covers:
  - MS 6.1: SSO/SAML 2.0 (SSOManager, SAMLConfig, SSOProvider, SSOStatus)
  - MS 6.2: White-Labeling & Public API (WhiteLabelManager, APIKeyManager, Public API Router)
  - MS 6.3: Ghost Mode v2 (ConversationMonitor, InterventionEngine, KnowledgeGapDetector, GhostModeV2)
  - MS 6.4: ShopifyAdapter + ManualCrmAdapter + AdapterRegistry
"""

import asyncio
import os
import sys
import time
import pytest

# Ensure app root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "testing")


def run_async(coro):
    """Helper to run async code in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ══════════════════════════════════════════════════════════════════════════════
# MS 6.1: SSO/SAML 2.0
# ══════════════════════════════════════════════════════════════════════════════

class TestSSOManager:
    """Tests for SSO/SAML 2.0 Enterprise Authentication."""

    def test_import_sso_module(self):
        from app.core.sso import SSOManager, SSOProvider, SSOStatus, SAMLConfig
        assert SSOManager is not None
        assert SSOProvider is not None
        assert SSOStatus is not None
        assert SAMLConfig is not None

    def test_sso_provider_enum(self):
        from app.core.sso import SSOProvider
        assert SSOProvider.OKTA.value == "okta"
        assert SSOProvider.AZURE_AD.value == "azure_ad"
        assert SSOProvider.GOOGLE_WORKSPACE.value == "google_workspace"
        assert SSOProvider.CUSTOM_SAML.value == "custom_saml"

    def test_sso_status_enum(self):
        from app.core.sso import SSOStatus
        assert SSOStatus.DISABLED.value == "disabled"
        assert SSOStatus.ACTIVE.value == "active"
        assert SSOStatus.CONFIGURING.value == "configuring"

    def test_sso_manager_initialization(self):
        from app.core.sso import SSOManager
        manager = SSOManager()
        assert manager is not None

    def test_sso_configure(self):
        from app.core.sso import SSOManager, SSOProvider
        manager = SSOManager()
        config = manager.configure_sso(
            tenant_id=1,
            provider=SSOProvider.OKTA,
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="MIIC...",
        )
        assert config is not None
        assert config.tenant_id == 1
        assert config.provider == SSOProvider.OKTA

    def test_sso_get_config(self):
        from app.core.sso import SSOManager, SSOProvider
        manager = SSOManager()
        manager.configure_sso(
            tenant_id=2,
            provider=SSOProvider.AZURE_AD,
            idp_entity_id="https://azure.example.com",
            idp_sso_url="https://azure.example.com/sso",
            idp_certificate="MIIC...",
        )
        config = manager.get_config(2)
        assert config is not None
        assert config.provider == SSOProvider.AZURE_AD

    def test_sso_activate_deactivate(self):
        from app.core.sso import SSOManager, SSOProvider, SSOStatus
        manager = SSOManager()
        manager.configure_sso(
            tenant_id=3,
            provider=SSOProvider.GOOGLE_WORKSPACE,
            idp_entity_id="https://google.example.com",
            idp_sso_url="https://google.example.com/sso",
            idp_certificate="MIIC...",
        )
        assert manager.activate_sso(3) is True
        config = manager.get_config(3)
        assert config.status == SSOStatus.ACTIVE

        assert manager.deactivate_sso(3) is True
        config = manager.get_config(3)
        assert config.status == SSOStatus.DISABLED

    def test_sso_is_enabled(self):
        from app.core.sso import SSOManager, SSOProvider
        manager = SSOManager()
        assert manager.is_sso_enabled(99) is False
        manager.configure_sso(
            tenant_id=99,
            provider=SSOProvider.OKTA,
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="MIIC...",
        )
        manager.activate_sso(99)
        assert manager.is_sso_enabled(99) is True

    def test_sso_initiate_login(self):
        from app.core.sso import SSOManager, SSOProvider
        manager = SSOManager()
        manager.configure_sso(
            tenant_id=4,
            provider=SSOProvider.OKTA,
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="MIIC...",
        )
        manager.activate_sso(4)
        result = manager.initiate_login(4)
        assert result is not None
        assert "redirect_url" in result or "saml_request" in result

    def test_sso_list_configured_tenants(self):
        from app.core.sso import SSOManager, SSOProvider
        manager = SSOManager()
        manager.configure_sso(10, SSOProvider.OKTA, "e1", "u1", "c1")
        manager.configure_sso(11, SSOProvider.AZURE_AD, "e2", "u2", "c2")
        tenants = manager.list_configured_tenants()
        assert len(tenants) >= 2

    def test_sso_router_creation(self):
        from app.core.sso import create_sso_router
        router = create_sso_router()
        assert router is not None
        paths = [r.path for r in router.routes]
        assert any("/configure" in p for p in paths)
        assert any("/login" in p for p in paths)
        assert any("/status" in p for p in paths)

    def test_sso_sp_metadata(self):
        from app.core.sso import SSOManager, SSOProvider
        manager = SSOManager()
        manager.configure_sso(
            tenant_id=5,
            provider=SSOProvider.OKTA,
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="MIIC...",
        )
        metadata = manager.generate_sp_metadata(5)
        assert metadata is not None


# ══════════════════════════════════════════════════════════════════════════════
# MS 6.2: White-Labeling & Public API
# ══════════════════════════════════════════════════════════════════════════════

class TestWhiteLabelAndPublicAPI:
    """Tests for White-Labeling Engine and Public API."""

    def test_import_public_api_module(self):
        from app.platform.api.public_api import (
            WhiteLabelManager, APIKeyManager, create_public_api_router
        )
        assert WhiteLabelManager is not None
        assert APIKeyManager is not None

    def test_white_label_defaults(self):
        from app.platform.api.public_api import WhiteLabelManager
        wl = WhiteLabelManager()
        config = wl.get_config(999)
        assert config is not None
        assert config.brand_name == "ARIIA"
        assert config.primary_color == "#6366f1"

    def test_white_label_set_config(self):
        from app.platform.api.public_api import WhiteLabelManager
        wl = WhiteLabelManager()
        config = wl.set_config(1, brand_name="TestBrand", primary_color="#FF0000", logo_url="https://example.com/logo.png")
        assert config.brand_name == "TestBrand"
        assert config.primary_color == "#FF0000"
        # Verify persistence
        config2 = wl.get_config(1)
        assert config2.brand_name == "TestBrand"

    def test_white_label_delete_config(self):
        from app.platform.api.public_api import WhiteLabelManager
        wl = WhiteLabelManager()
        wl.set_config(2, brand_name="ToDelete")
        assert wl.get_config(2).brand_name == "ToDelete"
        wl.delete_config(2)
        assert wl.get_config(2).brand_name == "ARIIA"  # Back to default

    def test_api_key_create(self):
        from app.platform.api.public_api import APIKeyManager, APIKeyScope
        akm = APIKeyManager()
        raw_key, api_key = akm.create_key(
            tenant_id=1, name="Test Key",
            scopes=[APIKeyScope.READ, APIKeyScope.CONVERSATIONS],
        )
        assert raw_key.startswith("ariia_pk_")
        assert api_key.name == "Test Key"
        assert api_key.tenant_id == 1
        assert APIKeyScope.READ in api_key.scopes

    def test_api_key_validate(self):
        from app.platform.api.public_api import APIKeyManager, APIKeyScope
        akm = APIKeyManager()
        raw_key, api_key = akm.create_key(tenant_id=1, name="Validate Test")
        result = akm.validate_key(raw_key)
        assert result is not None
        assert result.tenant_id == 1
        assert result.name == "Validate Test"

    def test_api_key_validate_invalid(self):
        from app.platform.api.public_api import APIKeyManager
        akm = APIKeyManager()
        result = akm.validate_key("ariia_pk_invalid_key_12345")
        assert result is None

    def test_api_key_revoke(self):
        from app.platform.api.public_api import APIKeyManager
        akm = APIKeyManager()
        raw_key, api_key = akm.create_key(tenant_id=1, name="Revoke Test")
        assert akm.validate_key(raw_key) is not None
        assert akm.revoke_key(api_key.id) is True
        assert akm.validate_key(raw_key) is None

    def test_api_key_list(self):
        from app.platform.api.public_api import APIKeyManager
        akm = APIKeyManager()
        akm.create_key(tenant_id=5, name="Key 1")
        akm.create_key(tenant_id=5, name="Key 2")
        akm.create_key(tenant_id=6, name="Key 3")
        keys = akm.list_keys(tenant_id=5)
        assert len(keys) == 2
        assert all(k["tenant_id"] == 5 for k in keys)

    def test_api_key_rotate(self):
        from app.platform.api.public_api import APIKeyManager
        akm = APIKeyManager()
        raw_key, api_key = akm.create_key(tenant_id=1, name="Rotate Test")
        result = akm.rotate_key(api_key.id)
        assert result is not None
        new_raw_key, new_api_key = result
        assert new_raw_key != raw_key
        assert akm.validate_key(raw_key) is None  # Old key revoked
        assert akm.validate_key(new_raw_key) is not None  # New key works

    def test_api_key_scope_check(self):
        from app.platform.api.public_api import APIKeyManager, APIKeyScope
        akm = APIKeyManager()
        raw_key, api_key = akm.create_key(
            tenant_id=1, name="Scoped",
            scopes=[APIKeyScope.READ, APIKeyScope.CONVERSATIONS],
        )
        assert api_key.has_scope(APIKeyScope.READ) is True
        assert api_key.has_scope(APIKeyScope.CONVERSATIONS) is True

    def test_api_key_admin_scope_grants_all(self):
        from app.platform.api.public_api import APIKeyManager, APIKeyScope
        akm = APIKeyManager()
        raw_key, api_key = akm.create_key(
            tenant_id=1, name="Admin",
            scopes=[APIKeyScope.ADMIN],
        )
        assert api_key.has_scope(APIKeyScope.READ) is True
        assert api_key.has_scope(APIKeyScope.WRITE) is True
        assert api_key.has_scope(APIKeyScope.ANALYTICS) is True

    def test_public_api_router_creation(self):
        from app.platform.api.public_api import create_public_api_router
        router = create_public_api_router()
        paths = [r.path for r in router.routes]
        assert any("/messages" in p for p in paths)
        assert any("/conversations" in p for p in paths)
        assert any("/members" in p for p in paths)
        assert any("/knowledge" in p for p in paths)
        assert any("/analytics" in p for p in paths)
        assert any("/webhooks" in p for p in paths)
        assert any("/info" in p for p in paths)


# ══════════════════════════════════════════════════════════════════════════════
# MS 6.3: Ghost Mode v2
# ══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeGapDetector:
    """Tests for Knowledge Gap Detection."""

    def test_import_ghost_mode_v2(self):
        from app.platform.ghost_mode_v2 import (
            GhostModeV2, KnowledgeGapDetector, InterventionEngine,
            ConversationMonitor, GhostEventType
        )
        assert GhostModeV2 is not None

    def test_detect_uncertainty_gap(self):
        from app.platform.ghost_mode_v2 import KnowledgeGapDetector
        detector = KnowledgeGapDetector()
        gap = detector.analyze_exchange(
            tenant_id=1, conversation_id="conv-1",
            user_message="Was kostet das Premium-Abo?",
            agent_response="Das kann ich leider nicht beantworten, dazu habe ich keine Informationen.",
        )
        assert gap is not None
        assert gap.confidence >= 0.4

    def test_detect_frustration_gap(self):
        from app.platform.ghost_mode_v2 import KnowledgeGapDetector
        detector = KnowledgeGapDetector()
        gap = detector.analyze_exchange(
            tenant_id=1, conversation_id="conv-2",
            user_message="Ich habe schon gefragt: Wann öffnet das Studio?",
            agent_response="Dazu habe ich keine Informationen.",
        )
        assert gap is not None
        assert gap.confidence >= 0.4

    def test_no_gap_for_good_response(self):
        from app.platform.ghost_mode_v2 import KnowledgeGapDetector
        detector = KnowledgeGapDetector()
        gap = detector.analyze_exchange(
            tenant_id=1, conversation_id="conv-3",
            user_message="Hallo",
            agent_response="Hallo! Wie kann ich Ihnen helfen? Ich bin der virtuelle Assistent und kann Ihnen bei Fragen zu Terminen, Mitgliedschaften und mehr weiterhelfen.",
        )
        assert gap is None

    def test_gap_summary(self):
        from app.platform.ghost_mode_v2 import KnowledgeGapDetector
        detector = KnowledgeGapDetector()
        detector.analyze_exchange(1, "c1", "Was kostet das?", "Ich bin mir nicht sicher.")
        detector.analyze_exchange(1, "c2", "Wann ist der Termin?", "Das weiß ich leider nicht.")
        summary = detector.get_gap_summary(1)
        assert summary["total_gaps"] >= 2

    def test_resolve_gap(self):
        from app.platform.ghost_mode_v2 import KnowledgeGapDetector
        detector = KnowledgeGapDetector()
        gap = detector.analyze_exchange(1, "c1", "Preis?", "Ich bin mir nicht sicher über den Preis.")
        assert gap is not None
        result = detector.resolve_gap(1, gap.gap_id)
        assert result is True

    def test_gap_fields(self):
        from app.platform.ghost_mode_v2 import KnowledgeGapDetector
        detector = KnowledgeGapDetector()
        gap = detector.analyze_exchange(1, "c1", "Was kostet das?", "Das weiß ich leider nicht.")
        assert gap is not None
        assert hasattr(gap, "gap_id")
        assert hasattr(gap, "tenant_id")
        assert hasattr(gap, "conversation_id")
        assert hasattr(gap, "topic")
        assert hasattr(gap, "confidence")
        assert hasattr(gap, "category")
        assert hasattr(gap, "resolved")


class TestInterventionEngine:
    """Tests for the Intervention Engine."""

    def test_inject_message(self):
        from app.platform.ghost_mode_v2 import InterventionEngine
        engine = InterventionEngine()
        record = engine.inject_message(
            tenant_id=1, conversation_id="conv-1",
            admin_user_id=1, admin_email="admin@test.de",
            content="Hier ist die Antwort...",
        )
        assert record.intervention_id
        assert record.content == "Hier ist die Antwort..."

    def test_takeover_and_release(self):
        from app.platform.ghost_mode_v2 import InterventionEngine, ConversationStatus
        engine = InterventionEngine()
        engine.takeover(1, "conv-1", 1, "admin@test.de")
        assert engine.is_taken_over("conv-1")
        assert engine.is_paused("conv-1")
        assert engine.get_conversation_status("conv-1") == ConversationStatus.TAKEN_OVER

        engine.release(1, "conv-1", 1, "admin@test.de")
        assert not engine.is_taken_over("conv-1")
        assert not engine.is_paused("conv-1")
        assert engine.get_conversation_status("conv-1") == ConversationStatus.ACTIVE

    def test_pause_and_resume(self):
        from app.platform.ghost_mode_v2 import InterventionEngine
        engine = InterventionEngine()
        engine.pause_agent(1, "conv-2", "admin@test.de")
        assert engine.is_paused("conv-2")
        engine.resume_agent(1, "conv-2", "admin@test.de")
        assert not engine.is_paused("conv-2")

    def test_force_escalate(self):
        from app.platform.ghost_mode_v2 import InterventionEngine, ConversationStatus
        engine = InterventionEngine()
        record = engine.force_escalate(1, "conv-3", "admin@test.de", "Kunde sehr verärgert")
        assert record.content == "Kunde sehr verärgert"
        assert engine.get_conversation_status("conv-3") == ConversationStatus.ESCALATED

    def test_intervention_history(self):
        from app.platform.ghost_mode_v2 import InterventionEngine
        engine = InterventionEngine()
        engine.inject_message(1, "conv-1", 1, "admin@test.de", "Msg 1")
        engine.inject_message(1, "conv-1", 1, "admin@test.de", "Msg 2")
        engine.inject_message(1, "conv-2", 1, "admin@test.de", "Msg 3")
        history = engine.get_intervention_history(1)
        assert len(history) == 3
        history_conv1 = engine.get_intervention_history(1, conversation_id="conv-1")
        assert len(history_conv1) == 2


class TestConversationMonitor:
    """Tests for the Conversation Monitor."""

    def test_record_user_message(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        monitor.record_user_message("conv-1", 1, "Hallo, ich brauche Hilfe")
        score = monitor.get_score("conv-1")
        assert score is not None
        assert score.user_message_count == 1

    def test_record_agent_response(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        monitor.record_user_message("conv-1", 1, "Hallo")
        time.sleep(0.01)
        monitor.record_agent_response("conv-1", 1, "Hallo! Wie kann ich helfen?")
        score = monitor.get_score("conv-1")
        assert score.agent_message_count == 1

    def test_negative_sentiment_detection(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        monitor.record_user_message("conv-1", 1, "Das ist schlecht und enttäuschend")
        score = monitor.get_score("conv-1")
        assert score.sentiment_score < 0.5

    def test_positive_sentiment_detection(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        monitor.record_user_message("conv-1", 1, "Super, danke, das ist perfekt!")
        score = monitor.get_score("conv-1")
        assert score.sentiment_score > 0.5

    def test_tool_call_improves_resolution(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        score = monitor.get_or_create_score("conv-1", 1)
        initial_resolution = score.resolution_score
        monitor.record_tool_call("conv-1", 1)
        assert score.resolution_score > initial_resolution

    def test_error_triggers_attention(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        monitor.record_error("conv-1", 1)
        score = monitor.get_score("conv-1")
        assert score.needs_attention is True

    def test_get_active_scores(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        monitor.record_user_message("conv-1", 1, "Hallo")
        monitor.record_user_message("conv-2", 1, "Hi")
        monitor.record_user_message("conv-3", 2, "Hey")
        scores = monitor.get_active_scores(1)
        assert len(scores) == 2

    def test_end_conversation(self):
        from app.platform.ghost_mode_v2 import ConversationMonitor
        monitor = ConversationMonitor()
        monitor.record_user_message("conv-1", 1, "Test")
        final = monitor.end_conversation("conv-1")
        assert final is not None
        assert monitor.get_score("conv-1") is None


class TestGhostModeV2:
    """Tests for the Ghost Mode v2 Manager."""

    def test_ghost_mode_initialization(self):
        from app.platform.ghost_mode_v2 import GhostModeV2
        gm = GhostModeV2()
        assert gm.monitor is not None
        assert gm.intervention is not None
        assert gm.gap_detector is not None

    def test_should_agent_respond_default(self):
        from app.platform.ghost_mode_v2 import GhostModeV2
        gm = GhostModeV2()
        assert gm.should_agent_respond("conv-1") is True

    def test_should_agent_respond_after_takeover(self):
        from app.platform.ghost_mode_v2 import GhostModeV2
        gm = GhostModeV2()
        gm.intervention.takeover(1, "conv-1", 1, "admin@test.de")
        assert gm.should_agent_respond("conv-1") is False
        gm.intervention.release(1, "conv-1", 1, "admin@test.de")
        assert gm.should_agent_respond("conv-1") is True

    def test_dashboard_state(self):
        from app.platform.ghost_mode_v2 import GhostModeV2
        gm = GhostModeV2()
        gm.monitor.record_user_message("conv-1", 1, "Hallo")
        state = gm.get_dashboard_state(1)
        assert "active_conversations" in state
        assert "attention_needed" in state
        assert "knowledge_gaps" in state
        assert "recent_interventions" in state

    def test_on_user_message(self):
        from app.platform.ghost_mode_v2 import GhostModeV2
        gm = GhostModeV2()
        run_async(gm.on_user_message(1, "conv-1", "user-1", "Hallo!"))
        score = gm.monitor.get_score("conv-1")
        assert score is not None
        assert score.user_message_count == 1

    def test_on_agent_response_with_gap(self):
        from app.platform.ghost_mode_v2 import GhostModeV2
        gm = GhostModeV2()
        run_async(gm.on_agent_response(
            1, "conv-1", "user-1",
            response="Ich bin mir nicht sicher, dazu habe ich keine Informationen.",
            user_message="Was kostet das Premium-Abo monatlich?",
        ))
        gaps = gm.gap_detector.get_gaps(1)
        assert len(gaps) >= 1

    def test_ghost_mode_v2_router(self):
        from app.platform.ghost_mode_v2 import create_ghost_mode_v2_router
        router = create_ghost_mode_v2_router()
        paths = [r.path for r in router.routes]
        assert any("/dashboard" in p for p in paths)
        assert any("/intervene" in p for p in paths)
        assert any("/knowledge-gaps" in p for p in paths)

    def test_event_listener(self):
        from app.platform.ghost_mode_v2 import GhostModeV2
        gm = GhostModeV2()
        received_events = []

        async def listener(event):
            received_events.append(event)

        gm.register_listener(1, listener)
        run_async(gm.on_user_message(1, "conv-1", "user-1", "Test"))
        assert len(received_events) >= 1
        assert received_events[0]["type"] == "ghost.message_in"


# ══════════════════════════════════════════════════════════════════════════════
# MS 6.4: ShopifyAdapter + ManualCrmAdapter
# ══════════════════════════════════════════════════════════════════════════════

class TestShopifyAdapter:
    """Tests for the Shopify Adapter."""

    def test_import_shopify_adapter(self):
        from app.integrations.adapters.shopify_adapter import ShopifyAdapter
        adapter = ShopifyAdapter()
        assert adapter.integration_id == "shopify"

    def test_shopify_capabilities(self):
        from app.integrations.adapters.shopify_adapter import ShopifyAdapter
        adapter = ShopifyAdapter()
        assert "crm.customer.search" in adapter.supported_capabilities
        assert "ecommerce.order.list" in adapter.supported_capabilities
        assert "ecommerce.product.list" in adapter.supported_capabilities
        assert "ecommerce.inventory.check" in adapter.supported_capabilities

    def test_shopify_unsupported_capability(self):
        from app.integrations.adapters.shopify_adapter import ShopifyAdapter
        adapter = ShopifyAdapter()
        result = run_async(adapter.execute_capability("nonexistent.capability", 1))
        assert result.success is False
        assert result.error_code == "UNSUPPORTED_CAPABILITY"

    def test_shopify_not_configured_error(self):
        from app.integrations.adapters.shopify_adapter import ShopifyAdapter
        adapter = ShopifyAdapter()
        result = run_async(adapter.execute_capability("crm.customer.search", 999, query="test"))
        assert result.success is False

    def test_shopify_configure_tenant(self):
        from app.integrations.adapters.shopify_adapter import ShopifyAdapter
        adapter = ShopifyAdapter()
        adapter.configure_tenant(1, "test-shop.myshopify.com", "shpat_test123")
        config = adapter._get_client_config(1)
        assert config["domain"] == "test-shop.myshopify.com"

    def test_shopify_display_info(self):
        from app.integrations.adapters.shopify_adapter import ShopifyAdapter
        adapter = ShopifyAdapter()
        assert adapter.display_name == "Shopify"
        assert adapter.version == "1.0.0"


class TestManualCrmAdapter:
    """Tests for the Manual CRM Adapter."""

    def test_import_manual_crm(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        assert adapter.integration_id == "manual_crm"

    def test_manual_crm_capabilities(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        assert "crm.customer.search" in adapter.supported_capabilities
        assert "crm.customer.create" in adapter.supported_capabilities
        assert "crm.import.csv" in adapter.supported_capabilities
        assert "crm.tag.manage" in adapter.supported_capabilities

    def test_create_member(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        result = run_async(adapter.execute_capability(
            "crm.customer.create", 1,
            first_name="Max", last_name="Mustermann",
            email="max@test.de", phone="+49123456789",
        ))
        assert result.success is True
        assert result.data["first_name"] == "Max"
        assert result.data["email"] == "max@test.de"

    def test_search_member(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        run_async(adapter.execute_capability("crm.customer.create", 1, first_name="Anna", email="anna@test.de"))
        result = run_async(adapter.execute_capability("crm.customer.search", 1, query="anna"))
        assert result.success is True
        assert result.data["count"] >= 1

    def test_update_member(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        create_result = run_async(adapter.execute_capability("crm.customer.create", 1, first_name="Bob", email="bob@test.de"))
        member_id = create_result.data["id"]
        update_result = run_async(adapter.execute_capability("crm.customer.update", 1, member_id=member_id, phone="+49999"))
        assert update_result.success is True
        assert "phone" in update_result.data["updated_fields"]

    def test_member_list(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        run_async(adapter.execute_capability("crm.customer.create", 2, first_name="A", email="a@test.de"))
        run_async(adapter.execute_capability("crm.customer.create", 2, first_name="B", email="b@test.de"))
        result = run_async(adapter.execute_capability("crm.customer.list", 2))
        assert result.success is True
        assert result.data["total"] == 2

    def test_member_stats(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        run_async(adapter.execute_capability("crm.customer.create", 3, first_name="X", email="x@test.de"))
        result = run_async(adapter.execute_capability("crm.customer.stats", 3))
        assert result.success is True
        assert result.data["total_members"] >= 1

    def test_csv_import(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        csv_data = "first_name,last_name,email\nMax,Muster,max@csv.de\nAnna,Test,anna@csv.de"
        result = run_async(adapter.execute_capability("crm.import.csv", 4, csv_data=csv_data))
        assert result.success is True
        assert result.data["imported"] == 2

    def test_csv_import_duplicate_skip(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        run_async(adapter.execute_capability("crm.customer.create", 5, first_name="Existing", email="existing@test.de"))
        csv_data = "first_name,email\nExisting,existing@test.de\nNew,new@test.de"
        result = run_async(adapter.execute_capability("crm.import.csv", 5, csv_data=csv_data))
        assert result.success is True
        assert result.data["imported"] == 1
        assert result.data["skipped"] == 1

    def test_tag_management(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        create_result = run_async(adapter.execute_capability("crm.customer.create", 6, first_name="Tag", email="tag@test.de"))
        member_id = create_result.data["id"]
        tag_result = run_async(adapter.execute_capability("crm.tag.manage", 6, member_id=member_id, add_tags=["VIP", "Premium"]))
        assert tag_result.success is True
        assert "VIP" in tag_result.data["tags"]
        assert "Premium" in tag_result.data["tags"]

        tag_result2 = run_async(adapter.execute_capability("crm.tag.manage", 6, member_id=member_id, remove_tags=["VIP"]))
        assert "VIP" not in tag_result2.data["tags"]
        assert "Premium" in tag_result2.data["tags"]

    def test_duplicate_email_prevention(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        run_async(adapter.execute_capability("crm.customer.create", 7, first_name="Dup", email="dup@test.de"))
        result = run_async(adapter.execute_capability("crm.customer.create", 7, first_name="Dup2", email="dup@test.de"))
        assert result.success is False
        assert "DUPLICATE" in result.error_code

    def test_health_check(self):
        from app.integrations.adapters.manual_crm_adapter import ManualCrmAdapter
        adapter = ManualCrmAdapter()
        result = run_async(adapter.health_check(1))
        assert result.success is True
        assert result.data["status"] == "healthy"


class TestAdapterRegistry:
    """Tests for the updated Adapter Registry with new adapters."""

    def test_registry_has_all_adapters(self):
        from app.integrations.adapters.registry import AdapterRegistry
        registry = AdapterRegistry()
        assert "magicline" in registry
        assert "shopify" in registry
        assert "manual_crm" in registry

    def test_registry_adapter_count(self):
        from app.integrations.adapters.registry import AdapterRegistry
        registry = AdapterRegistry()
        adapters = registry.registered_adapters
        assert len(adapters) >= 3

    def test_registry_get_shopify(self):
        from app.integrations.adapters.registry import AdapterRegistry
        registry = AdapterRegistry()
        adapter = registry.get_adapter("shopify")
        assert adapter is not None
        assert adapter.integration_id == "shopify"

    def test_registry_get_manual_crm(self):
        from app.integrations.adapters.registry import AdapterRegistry
        registry = AdapterRegistry()
        adapter = registry.get_adapter("manual_crm")
        assert adapter is not None
        assert adapter.integration_id == "manual_crm"


# ══════════════════════════════════════════════════════════════════════════════
# Skill Files
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillFiles:
    """Tests for Skill definition files."""

    def test_shopify_skill_exists(self):
        skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", "ecommerce", "shopify.SKILL.md")
        assert os.path.exists(skill_path)

    def test_manual_crm_skill_exists(self):
        skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", "crm", "manual_crm.SKILL.md")
        assert os.path.exists(skill_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-p", "no:cacheprovider"])
