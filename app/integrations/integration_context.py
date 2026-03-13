"""app/integrations/integration_context.py — Integration awareness layer for campaign agents.

Reads active connector configurations from the settings store and builds
structured context that agents can use to:

  1. Know which services are available (MarketingAgent → use real URLs)
  2. Validate content references (QAAgent → flag inactive services)

No API calls are made; all data comes from the local settings store.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()

# ── Category display names ────────────────────────────────────────────────────
_CATEGORY_LABELS = {
    "scheduling": "Terminbuchung",
    "payments": "Zahlung",
    "crm": "CRM",
    "members": "Mitglieder",
    "messaging": "Messaging",
    "analytics": "Analytics",
    "ai_voice": "KI-Sprache",
}

# ── Which connectors are "content-relevant" for campaign generation ───────────
# Only these appear in agent prompts / QA checks to avoid clutter.
_CONTENT_RELEVANT_CATEGORIES = {"scheduling", "payments", "crm"}

# ── URL fields: how to extract a public-facing URL per connector ──────────────
# Maps connector_id → list of field keys to try (first non-empty value wins)
_URL_FIELDS: dict[str, list[str]] = {
    "calendly": ["organization_uri"],
    "calcom": ["base_url"],
    "acuity": [],
    "shopify": ["domain"],
    "woocommerce": ["store_url"],
    "salesforce": ["instance_url"],
    "stripe": [],
    "paypal": [],
    "mollie": [],
    "hubspot": [],
}

# ── QA: patterns in email/sms content that imply a specific connector ─────────
# Maps regex pattern → connector_id that must be active
CONTENT_SERVICE_PATTERNS: list[tuple[str, str]] = [
    (r"calendly\.com", "calendly"),
    (r"cal\.com", "calcom"),
    (r"acuityscheduling\.com", "acuity"),
    (r"stripe\.com", "stripe"),
    (r"paypal\.com", "paypal"),
    (r"mollie\.com", "mollie"),
    (r"checkout\.shopify\.com|\.myshopify\.com", "shopify"),
    (r"woocommerce\.com", "woocommerce"),
    (r"hubspot\.com", "hubspot"),
]

# ── QA: category-level signals (softer — produce suggestions, not errors) ─────
# Maps regex → category that should be active for credible content
CONTENT_CATEGORY_SIGNALS: list[tuple[str, str]] = [
    (r"jetzt buchen|book now|termin buchen|appointment|calendly|cal\.com", "scheduling"),
    (r"jetzt kaufen|buy now|checkout|zahlung|bezahlen|purchase", "payments"),
]


@dataclass
class ActiveIntegration:
    connector_id: str
    name: str
    category: str
    public_url: str = ""   # booking/store URL visible to customers, if available


@dataclass
class IntegrationContext:
    tenant_id: int
    active: list[ActiveIntegration] = field(default_factory=list)
    # connector_ids that appear in content but are NOT active
    _active_ids: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self):
        self._active_ids = {i.connector_id for i in self.active}

    def get_active_ids(self) -> set[str]:
        return self._active_ids

    def get_active_categories(self) -> set[str]:
        return {i.category for i in self.active}

    # ── Formatted prompt block for LLM agents ────────────────────────────────

    def to_agent_summary(self) -> str:
        """Return a concise text block injected into agent system prompts."""
        if not self.active:
            return (
                "INTEGRATIONEN: Keine externen Dienste konfiguriert. "
                "Füge KEINE externen Service-URLs (Calendly, Stripe etc.) hinzu, "
                "außer sie werden explizit im Prompt genannt."
            )

        lines = ["AKTIVE INTEGRATIONEN (diese Dienste stehen dem Mandanten zur Verfügung):"]
        by_cat: dict[str, list[ActiveIntegration]] = {}
        for intg in self.active:
            by_cat.setdefault(intg.category, []).append(intg)

        for cat, items in by_cat.items():
            cat_label = _CATEGORY_LABELS.get(cat, cat)
            for intg in items:
                url_hint = f" → {intg.public_url}" if intg.public_url else ""
                lines.append(f"  • [{cat_label}] {intg.name}{url_hint}")

        # Warn about inactive content-relevant categories
        active_cats = self.get_active_categories()
        missing = [
            _CATEGORY_LABELS.get(c, c)
            for c in _CONTENT_RELEVANT_CATEGORIES
            if c not in active_cats
        ]
        if missing:
            lines.append(
                f"\nNICHT KONFIGURIERT (nicht erwähnen oder verlinken): {', '.join(missing)}"
            )

        return "\n".join(lines)

    # ── QA helpers ────────────────────────────────────────────────────────────

    def find_inactive_service_references(self, content: str) -> list[str]:
        """Return QA issues for every service URL found in content whose
        connector is not active for this tenant."""
        issues = []
        content_lower = content.lower()
        for pattern, conn_id in CONTENT_SERVICE_PATTERNS:
            if re.search(pattern, content_lower):
                if conn_id not in self._active_ids:
                    from app.integrations.connector_registry import get_connector_meta
                    meta = get_connector_meta(conn_id) or {}
                    name = meta.get("name", conn_id)
                    cat = meta.get("category", "")
                    cat_label = _CATEGORY_LABELS.get(cat, cat)
                    issues.append(
                        f"Campaign references {name} but this integration is not connected. "
                        f"Configure at: Settings → Integrations → {name} ({cat_label})."
                    )
        return issues

    def find_missing_category_suggestions(self, content: str) -> list[str]:
        """Return suggestions when content implies a category (e.g. booking CTA)
        but no integration for that category is active."""
        suggestions = []
        content_lower = content.lower()
        active_cats = self.get_active_categories()
        for pattern, cat in CONTENT_CATEGORY_SIGNALS:
            if cat in active_cats:
                continue
            if re.search(pattern, content_lower):
                cat_label = _CATEGORY_LABELS.get(cat, cat)
                suggestions.append(
                    f"Content implies a {cat_label} action but no {cat_label} "
                    f"integration is active. Connect one under Settings → Integrations."
                )
        return suggestions


class IntegrationContextService:
    """Reads connector configs from persistence and builds an IntegrationContext.

    Stateless — safe to instantiate per request.
    """

    def get_context(self, tenant_id: int) -> IntegrationContext:
        """Build integration context for a tenant from the settings store."""
        try:
            from app.gateway.persistence import persistence
            from app.integrations.connector_registry import CONNECTOR_REGISTRY

            active: list[ActiveIntegration] = []

            for conn_id, meta in CONNECTOR_REGISTRY.items():
                category = meta.get("category", "")
                if category not in _CONTENT_RELEVANT_CATEGORIES:
                    continue  # Only content-relevant categories in agent context

                enabled_key = f"integration_{conn_id}_{tenant_id}_enabled"
                is_enabled = (
                    persistence.get_setting(enabled_key, "false", tenant_id=tenant_id) or ""
                ).lower() == "true"

                if not is_enabled:
                    continue

                # Try to extract a public-facing URL
                public_url = ""
                for field_key in _URL_FIELDS.get(conn_id, []):
                    cfg_key = f"integration_{conn_id}_{tenant_id}_{field_key}"
                    val = persistence.get_setting(cfg_key, "", tenant_id=tenant_id) or ""
                    if val.strip():
                        public_url = val.strip()
                        break

                active.append(ActiveIntegration(
                    connector_id=conn_id,
                    name=meta["name"],
                    category=category,
                    public_url=public_url,
                ))

            ctx = IntegrationContext(tenant_id=tenant_id, active=active)
            logger.debug(
                "integration_context.built",
                tenant_id=tenant_id,
                active_count=len(active),
                active_ids=[i.connector_id for i in active],
            )
            return ctx

        except Exception as e:
            logger.warning("integration_context.failed", tenant_id=tenant_id, error=str(e))
            return IntegrationContext(tenant_id=tenant_id, active=[])
