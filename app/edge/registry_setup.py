"""ARIIA – Active Module Registry Setup (Epic 4).

This file configures which modules are available in the system and maps
the legacy `gateway/routers/*.py` into the new capability-driven Domain Modules.
It is imported by `app/edge/app.py` right before it builds the FastAPI application.
"""

import structlog
from fastapi import APIRouter

from app.core.module_registry import Capability, ModuleDefinition, registry
from app.edge import health

logger = structlog.get_logger()


def register_all_modules() -> None:
    """Populates the global registry with the core domain modules."""
    registry.clear()

    # ── 1. Edge/Foundation (Always Active) ───────────────────────────────
    registry.register(ModuleDefinition(
        name="edge_foundation",
        description="Core routing, health checks, and edge utilities.",
        required_capabilities=[],
        get_routers=lambda: [health.router],
    ))

    # ── 2. Admin Control Plane ──────────────────────────────────────────
    def get_admin_routers():
        from app.gateway.routers.admin_core_settings import router as admin_core_settings
        from app.gateway.routers.admin_analytics import router as admin_analytics
        from app.gateway.routers.admin_billing_platform import router as admin_billing_platform
        from app.billing.router import router as billing_v2
        from app.gateway.routers.admin_integrations import router as admin_integrations
        from app.gateway.routers.admin_knowledge import router as admin_knowledge
        from app.gateway.routers.admin_operations import router as admin_operations
        from app.gateway.routers.admin_prompts import router as admin_prompts
        from app.gateway.routers.revenue_analytics import router as revenue_analytics
        from app.gateway.routers.admin_settings import router as admin_settings
        from app.gateway.routers.swarm_admin import router as swarm_admin
        from app.billing.admin_router import router as billing_admin
        from app.ai_config.router import admin_router as ai_admin
        # V2 billing replaces legacy gateway/routers/billing.py under /admin/billing/...
        billing_v2_admin = APIRouter(prefix="/admin")
        billing_v2_admin.include_router(billing_v2)
        return [admin_analytics, admin_billing_platform, admin_core_settings, admin_integrations, admin_knowledge, admin_operations, admin_prompts, revenue_analytics, admin_settings, swarm_admin, billing_v2_admin, billing_admin, ai_admin]
        
    registry.register(ModuleDefinition(
        name="admin_control_plane",
        description="Central UI gateway for generic admins (Epic 5 target).",
        required_capabilities=[Capability.ADMIN_CONTROL_PLANE],
        get_routers=get_admin_routers,
    ))
    
    # ── 3. Tenant & Billing Management ──────────────────────────────────
    def get_tenant_routers():
        from app.domains.platform.module import get_tenant_management_routers

        return get_tenant_management_routers()
        
    registry.register(ModuleDefinition(
        name="tenant_management",
        description="Tenant, settings, plans, and addon management.",
        required_capabilities=[Capability.TENANT_MANAGEMENT],
        get_routers=get_tenant_routers,
    ))

    # ── 4. Identity & Access ─────────────────────────────────────────────
    def get_identity_routers():
        from app.gateway.auth import router as auth
        from app.gateway.routers.permissions import router as perms
        return [auth, perms]
        
    registry.register(ModuleDefinition(
        name="identity_access",
        description="Authentication, authorization, SSO, and RBAC.",
        required_capabilities=[Capability.IDENTITY_ACCESS],
        get_routers=get_identity_routers,
    ))

    # ── 5. Active Core: Support & Core CRM ──────────────────────────────
    def get_support_routers():
        from app.domains.support.module import get_support_routers as build_support_routers

        return build_support_routers()

    registry.register(ModuleDefinition(
        name="support_core",
        description="Contact CRM, chats, agent teams, and basic support.",
        required_capabilities=[Capability.SUPPORT_CORE],
        get_routers=get_support_routers,
        get_workers=lambda: __import__(
            "app.domains.support.module",
            fromlist=["get_support_workers"],
        ).get_support_workers(),
    ))

    # ── 6. Active Core: Campaigns ───────────────────────────────────────
    def get_campaign_routers():
        from app.domains.campaigns.module import get_campaign_routers as build_campaign_routers

        return build_campaign_routers()
        
    registry.register(ModuleDefinition(
        name="campaigns",
        description="Campaign engines, templates, and outbound marketing.",
        required_capabilities=[Capability.CAMPAIGNS],
        get_routers=get_campaign_routers,
        get_workers=lambda: __import__(
            "app.domains.campaigns.module",
            fromlist=["get_campaign_workers"],
        ).get_campaign_workers(),
    ))

    # ── 7. Active Core: Knowledge Base ──────────────────────────────────
    def get_knowledge_routers():
        from app.domains.knowledge.module import get_knowledge_routers as build_knowledge_routers

        return build_knowledge_routers()
        
    registry.register(ModuleDefinition(
        name="knowledge_base",
        description="Vector embeddings, files, chunks, and RAG pipelines.",
        required_capabilities=[Capability.KNOWLEDGE_BASE],
        get_routers=get_knowledge_routers,
        get_workers=lambda: __import__(
            "app.domains.knowledge.module",
            fromlist=["get_knowledge_workers"],
        ).get_knowledge_workers(),
    ))

    # ── 8. Active Integrations ──────────────────────────────────────────
    def get_magicline_routers():
        from app.domains.integrations.module import get_magicline_routers

        return get_magicline_routers()

    def get_whatsapp_routers():
        from app.domains.integrations.module import get_whatsapp_routers

        return get_whatsapp_routers()

    def get_telegram_routers():
        from app.domains.integrations.module import get_telegram_routers

        return get_telegram_routers()

    def get_calendly_routers():
        from app.domains.integrations.module import get_calendly_routers

        return get_calendly_routers()
        
    registry.register(ModuleDefinition(
        name="integration_magicline",
        description="Magicline integration and syncing.",
        required_capabilities=[Capability.INTEGRATION_MAGICLINE],
        get_routers=get_magicline_routers,
        get_workers=lambda: __import__(
            "app.domains.integrations.module",
            fromlist=["get_magicline_workers"],
        ).get_magicline_workers(),
    ))

    registry.register(ModuleDefinition(
        name="integration_whatsapp_qr",
        description="WhatsApp channel webhooks via Meta API.",
        required_capabilities=[Capability.INTEGRATION_WHATSAPP_QR],
        get_routers=get_whatsapp_routers,
    ))
    
    # Empty integration modules for Telegram/Calendly as they don't have dedicated routers
    # but might have workers/handlers in the future.
    registry.register(ModuleDefinition(
        name="integration_telegram",
        description="Telegram bot integration.",
        required_capabilities=[Capability.INTEGRATION_TELEGRAM],
        get_routers=get_telegram_routers,
    ))
    registry.register(ModuleDefinition(
        name="integration_calendly",
        description="Calendly booking integration.",
        required_capabilities=[Capability.INTEGRATION_CALENDLY],
        get_routers=get_calendly_routers,
    ))

    # ── 9. Dormant Features (Coming Soon) ───────────────────────────────
    # These modules map to capabilities that are currently hardcoded to False globally
    # in module_registry.py `dormant_caps`, meaning these routes will NOT be loaded 
    # and WILL NOT start up, achieving the "Runtime Shutdown Layer".
    
    def get_voice_routers():
        from app.gateway.routers.voice import router as voice
        return [voice]
        
    registry.register(ModuleDefinition(
        name="voice_pipeline",
        description="Voice ingress/egress and TTS/STT. (DORMANT)",
        required_capabilities=[Capability.VOICE_PIPELINE],
        get_routers=get_voice_routers,
    ))
    
    def get_ab_testing_routers():
        from app.gateway.routers.ab_testing_api import router as ab_test
        return [ab_test]
        
    registry.register(ModuleDefinition(
        name="advanced_analytics",
        description="A/B testing and deep analytics. (DORMANT)",
        required_capabilities=[Capability.ADVANCED_ANALYTICS],
        get_routers=get_ab_testing_routers,
    ))


# Execute registration when this file is imported by app.edge.app
register_all_modules()
