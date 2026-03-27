"""ARIIA – Active Module Registry Setup (Epic 4).

This file configures which modules are available in the system and maps
the legacy `gateway/routers/*.py` into the new capability-driven Domain Modules.
It is imported by `app/edge/app.py` right before it builds the FastAPI application.
"""

import structlog

from app.core.module_registry import Capability, ModuleDefinition, registry
from app.edge import health

logger = structlog.get_logger()


def register_all_modules() -> None:
    """Populates the global registry with the core domain modules."""
    
    # ── 1. Edge/Foundation (Always Active) ───────────────────────────────
    registry.register(ModuleDefinition(
        name="edge_foundation",
        description="Core routing, health checks, and edge utilities.",
        required_capabilities=[],
        get_routers=lambda: [health.router],
    ))

    # ── 2. Admin Control Plane ──────────────────────────────────────────
    def get_admin_routers():
        from app.gateway.admin import router as fallback_admin
        from app.billing.admin_router import router as billing_admin
        from app.ai_config.router import admin_router as ai_admin
        return [fallback_admin, billing_admin, ai_admin]
        
    registry.register(ModuleDefinition(
        name="admin_control_plane",
        description="Central UI gateway for generic admins (Epic 5 target).",
        required_capabilities=[Capability.ADMIN_CONTROL_PLANE],
        get_routers=get_admin_routers,
    ))
    
    # ── 3. Tenant & Billing Management ──────────────────────────────────
    def get_tenant_routers():
        from app.platform.api.tenant_portal import router as portal
        from app.platform.api.marketplace import router as market
        from app.billing.router import router as v2_billing
        from app.gateway.routers.plans_admin import router as plans
        from app.platform.api.analytics import router as plat_analytics
        from app.gateway.routers.llm_costs import router as llm_costs
        from app.ai_config.router import tenant_router as ai_tenant
        return [portal, market, v2_billing, plans, plat_analytics, llm_costs, ai_tenant]
        
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
        from app.contacts.router import router as contacts
        from app.gateway.routers.members_crud import router as members
        from app.gateway.routers.contact_sync_api import router as sync
        from app.gateway.routers.chats import router as chats
        from app.gateway.routers.agent_teams import router as teams
        return [contacts, members, sync, chats, teams]
        
    registry.register(ModuleDefinition(
        name="support_core",
        description="Contact CRM, chats, agent teams, and basic support.",
        required_capabilities=[Capability.SUPPORT_CORE],
        get_routers=get_support_routers,
    ))

    # ── 6. Active Core: Campaigns ───────────────────────────────────────
    def get_campaign_routers():
        from app.gateway.routers.campaigns import router as cam_main
        from app.gateway.routers.campaign_templates import router as cam_tmp
        from app.gateway.routers.campaign_offers import router as cam_off
        from app.gateway.routers.campaign_webhooks import router as cam_wh
        return [cam_main, cam_tmp, cam_off, cam_wh]
        
    registry.register(ModuleDefinition(
        name="campaigns",
        description="Campaign engines, templates, and outbound marketing.",
        required_capabilities=[Capability.CAMPAIGNS],
        get_routers=get_campaign_routers,
    ))

    # ── 7. Active Core: Knowledge Base ──────────────────────────────────
    def get_knowledge_routers():
        from app.gateway.routers.ingestion import router as ingestion
        from app.gateway.routers.media import router as media
        return [ingestion, media]
        
    registry.register(ModuleDefinition(
        name="knowledge_base",
        description="Vector embeddings, files, chunks, and RAG pipelines.",
        required_capabilities=[Capability.KNOWLEDGE_BASE],
        get_routers=get_knowledge_routers,
    ))

    # ── 8. Active Integrations ──────────────────────────────────────────
    def get_magicline_routers():
        from app.platform.api.integrations import router as integrations_sync
        return [integrations_sync]

    def get_whatsapp_routers():
        from app.gateway.routers.webhooks import router as wa_webhooks
        return [wa_webhooks]
        
    registry.register(ModuleDefinition(
        name="integration_magicline",
        description="Magicline integration and syncing.",
        required_capabilities=[Capability.INTEGRATION_MAGICLINE],
        get_routers=get_magicline_routers,
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
    ))
    registry.register(ModuleDefinition(
        name="integration_calendly",
        description="Calendly booking integration.",
        required_capabilities=[Capability.INTEGRATION_CALENDLY],
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
