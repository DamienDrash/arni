from __future__ import annotations

import json as _json
from typing import Any

import httpx

from app.core.auth import AuthContext
from app.domains.billing.models import Plan
from app.gateway.admin_shared import REDACTED_SECRET_VALUE, mask_if_sensitive, write_admin_audit
from app.gateway.admin_billing_repository import admin_billing_repository
from app.gateway.persistence import persistence
from app.shared.db import session_scope
from config.settings import get_settings

settings = get_settings()

DEFAULT_BILLING_PROVIDERS = [
    {"id": "stripe", "name": "Stripe", "enabled": True, "mode": "mock", "note": "Default Provider"},
    {"id": "paypal", "name": "PayPal", "enabled": False, "mode": "mock", "note": "Planned"},
    {"id": "klarna", "name": "Klarna", "enabled": False, "mode": "mock", "note": "Planned"},
]

PREDEFINED_PROVIDERS = [
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_models": ["gpt-5-mini", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o4-mini"],
    },
    {
        "id": "groq",
        "name": "Groq Cloud",
        "base_url": "https://api.groq.com/openai/v1",
        "default_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    },
    {
        "id": "anthropic",
        "name": "Anthropic (via Proxy/Shim)",
        "base_url": "https://api.anthropic.com/v1",
        "default_models": ["claude-3-5-sonnet-20240620", "claude-3-haiku-20240307"],
    },
    {
        "id": "custom",
        "name": "Custom OpenAI-Compatible",
        "base_url": "",
        "default_models": [],
    },
]


class AdminBillingPlatformService:
    @staticmethod
    def parse_json_setting(key: str, default: Any, tenant_id: int | None = None) -> Any:
        raw = persistence.get_setting(key, None, tenant_id=tenant_id)
        if not raw:
            return default
        try:
            return _json.loads(raw)
        except Exception:
            return default

    def get_plans_config(self, user: AuthContext) -> dict[str, Any]:
        with session_scope() as db:
            plans = admin_billing_repository.list_plans(db)
            plans_list = [
                {
                    "id": plan.slug,
                    "name": plan.name,
                    "priceMonthly": round(plan.price_monthly_cents / 100),
                    "membersIncluded": plan.max_members if plan.max_members is not None else 999999,
                    "messagesIncluded": plan.max_monthly_messages if plan.max_monthly_messages is not None else 999999,
                    "aiAgents": 5,
                    "support": "Email",
                    "highlight": plan.slug in {"pro", "professional"},
                    "stripe_price_id": plan.stripe_price_id,
                }
                for plan in plans
            ]

        providers = self.parse_json_setting("billing_providers_json", DEFAULT_BILLING_PROVIDERS, tenant_id=user.tenant_id)
        default_provider = persistence.get_setting("billing_default_provider", "stripe", tenant_id=user.tenant_id) or "stripe"
        return {
            "scope": "global_system",
            "plans": plans_list,
            "providers": providers,
            "default_provider": default_provider,
        }

    def update_plans_config(self, user: AuthContext, *, providers: list[dict[str, Any]], default_provider: str) -> dict[str, Any]:
        provider_ids = {str(provider.get("id") or "").strip().lower() for provider in providers}
        normalized_default = (default_provider or "stripe").strip().lower()
        if normalized_default and normalized_default not in provider_ids:
            raise ValueError("default_provider must exist in providers")
        if not normalized_default:
            normalized_default = "stripe"

        persistence.upsert_setting("billing_providers_json", _json.dumps(providers, ensure_ascii=False), tenant_id=user.tenant_id)
        persistence.upsert_setting("billing_default_provider", normalized_default, tenant_id=user.tenant_id)
        return {"status": "ok", "scope": "global_system"}

    def get_billing_connectors(self, user: AuthContext) -> dict[str, Any]:
        public_url = (settings.gateway_public_url or "").rstrip("/")
        webhook_url = f"{public_url}/admin/billing/webhook" if public_url else "/admin/billing/webhook"
        return {
            "scope": "global_system",
            "webhook_url": webhook_url,
            "stripe": {
                "enabled": persistence.get_setting("billing_stripe_enabled", "false", tenant_id=user.tenant_id) == "true",
                "mode": persistence.get_setting("billing_stripe_mode", "test", tenant_id=user.tenant_id) or "test",
                "publishable_key": persistence.get_setting("billing_stripe_publishable_key", "", tenant_id=user.tenant_id) or "",
                "secret_key": mask_if_sensitive(
                    "billing_stripe_secret_key",
                    persistence.get_setting("billing_stripe_secret_key", "", tenant_id=user.tenant_id) or "",
                ),
                "webhook_secret": mask_if_sensitive(
                    "billing_stripe_webhook_secret",
                    persistence.get_setting("billing_stripe_webhook_secret", "", tenant_id=user.tenant_id) or "",
                ),
            },
        }

    def update_billing_connectors(
        self,
        user: AuthContext,
        *,
        enabled: bool,
        mode: str,
        publishable_key: str | None,
        secret_key: str | None,
        webhook_secret: str | None,
    ) -> dict[str, Any]:
        normalized_mode = (mode or "test").strip().lower()
        if normalized_mode not in {"test", "live"}:
            raise ValueError("Stripe mode must be test or live")

        persistence.upsert_setting("billing_stripe_enabled", "true" if enabled else "false", tenant_id=user.tenant_id)
        persistence.upsert_setting("billing_stripe_mode", normalized_mode, tenant_id=user.tenant_id)
        if publishable_key is not None:
            persistence.upsert_setting("billing_stripe_publishable_key", publishable_key, tenant_id=user.tenant_id)
        if secret_key is not None and secret_key != REDACTED_SECRET_VALUE:
            persistence.upsert_setting("billing_stripe_secret_key", secret_key, tenant_id=user.tenant_id)
        if webhook_secret is not None and webhook_secret != REDACTED_SECRET_VALUE:
            persistence.upsert_setting("billing_stripe_webhook_secret", webhook_secret, tenant_id=user.tenant_id)
        return {"status": "ok", "scope": "global_system"}

    async def test_stripe_connector(self, user: AuthContext) -> dict[str, Any]:
        secret_key = persistence.get_setting("billing_stripe_secret_key", "", tenant_id=user.tenant_id) or ""
        mode = persistence.get_setting("billing_stripe_mode", "test", tenant_id=user.tenant_id) or "test"
        if not secret_key:
            raise ValueError("Stripe secret key is not configured")
        if mode == "test" and not secret_key.startswith("sk_test_"):
            raise ValueError("Stripe mode is test but secret key is not sk_test_*")
        if mode == "live" and not secret_key.startswith("sk_live_"):
            raise ValueError("Stripe mode is live but secret key is not sk_live_*")

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get("https://api.stripe.com/v1/account", auth=(secret_key, ""))
            if response.status_code >= 400:
                detail = ""
                try:
                    payload = response.json()
                    detail = payload.get("error", {}).get("message", "") if isinstance(payload, dict) else ""
                except Exception:
                    detail = response.text[:180]
                raise RuntimeError(f"Stripe test failed ({response.status_code}): {detail or 'unknown error'}")
            data = response.json() if response.content else {}
            return {
                "status": "ok",
                "provider": "stripe",
                "mode": mode,
                "account_id": data.get("id"),
                "charges_enabled": data.get("charges_enabled"),
                "payouts_enabled": data.get("payouts_enabled"),
            }
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Stripe test failed: {exc}")

    def get_billing_subscription(self, user: AuthContext) -> dict[str, Any]:
        with session_scope() as db:
            subscription = admin_billing_repository.get_subscription_by_tenant(db, user.tenant_id)
            if not subscription:
                return {
                    "has_subscription": False,
                    "status": "free",
                    "plan": {
                        "name": "Starter",
                        "slug": "starter",
                        "price_monthly_cents": 0,
                        "max_members": 500,
                        "max_monthly_messages": 1000,
                        "max_channels": 1,
                        "whatsapp_enabled": True,
                        "telegram_enabled": False,
                        "sms_enabled": False,
                        "email_channel_enabled": False,
                        "voice_enabled": False,
                        "memory_analyzer_enabled": False,
                        "custom_prompts_enabled": False,
                    },
                }

            plan = admin_billing_repository.get_plan_by_id(db, subscription.plan_id)
            plan_data: dict[str, Any] = {}
            if plan:
                plan_data = {
                    "name": plan.name,
                    "slug": plan.slug,
                    "price_monthly_cents": plan.price_monthly_cents,
                    "max_members": plan.max_members,
                    "max_monthly_messages": plan.max_monthly_messages,
                    "max_channels": plan.max_channels,
                    "whatsapp_enabled": plan.whatsapp_enabled,
                    "telegram_enabled": plan.telegram_enabled,
                    "sms_enabled": plan.sms_enabled,
                    "email_channel_enabled": plan.email_channel_enabled,
                    "voice_enabled": plan.voice_enabled,
                    "memory_analyzer_enabled": plan.memory_analyzer_enabled,
                    "custom_prompts_enabled": plan.custom_prompts_enabled,
                }

            return {
                "has_subscription": True,
                "status": subscription.status,
                "stripe_subscription_id": subscription.stripe_subscription_id,
                "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
                "plan": plan_data,
            }

    def get_billing_usage(self, user: AuthContext) -> dict[str, Any]:
        from datetime import datetime, timezone
        from app.core.feature_gates import FeatureGate

        now = datetime.now(timezone.utc)
        gate = FeatureGate(tenant_id=user.tenant_id)
        usage = gate._get_current_usage()
        plan_data = gate._plan_data
        max_msgs = plan_data.get("max_monthly_messages")
        total_msgs = usage.get("messages_inbound", 0) + usage.get("messages_outbound", 0)
        return {
            "period": {"year": now.year, "month": now.month},
            "messages_inbound": usage.get("messages_inbound", 0),
            "messages_outbound": usage.get("messages_outbound", 0),
            "messages_total": total_msgs,
            "messages_limit": max_msgs,
            "messages_pct": round(total_msgs / int(max_msgs) * 100, 1) if max_msgs and int(max_msgs) > 0 else None,
            "active_members": usage.get("active_members", 0),
            "llm_tokens_used": usage.get("llm_tokens_used", 0),
        }

    @staticmethod
    def get_predefined_providers() -> list[dict[str, Any]]:
        return PREDEFINED_PROVIDERS

    def get_platform_llm_providers(self, user: AuthContext) -> list[dict[str, Any]]:
        providers_json = persistence.get_setting("platform_llm_providers_json", tenant_id=user.tenant_id) or "[]"
        return _json.loads(providers_json)

    def save_platform_llm_provider(
        self,
        user: AuthContext,
        *,
        provider_id: str,
        name: str,
        base_url: str,
        models: list[str],
        api_key: str | None,
    ) -> dict[str, str]:
        providers = self.get_platform_llm_providers(user)
        new_provider = {"id": provider_id, "name": name, "base_url": base_url, "models": models}
        existing = next((provider for provider in providers if provider["id"] == provider_id), None)
        if existing:
            providers = [provider if provider["id"] != provider_id else new_provider for provider in providers]
        else:
            providers.append(new_provider)

        persistence.upsert_setting("platform_llm_providers_json", _json.dumps(providers), tenant_id=user.tenant_id)
        if api_key and api_key != REDACTED_SECRET_VALUE:
            persistence.upsert_setting(f"platform_llm_key_{provider_id}", api_key, tenant_id=user.tenant_id)
        return {"status": "ok"}

    def delete_platform_llm_provider(self, user: AuthContext, provider_id: str) -> dict[str, str]:
        providers = self.get_platform_llm_providers(user)
        providers = [provider for provider in providers if provider["id"] != provider_id]
        persistence.upsert_setting("platform_llm_providers_json", _json.dumps(providers), tenant_id=user.tenant_id)
        return {"status": "ok"}

    async def test_llm_config(
        self,
        user: AuthContext,
        *,
        provider_id: str,
        api_key: str | None,
        base_url: str,
        models: list[str],
    ) -> dict[str, Any]:
        from app.swarm.llm import LLMClient

        effective_key = api_key
        if effective_key == REDACTED_SECRET_VALUE:
            effective_key = persistence.get_setting(f"platform_llm_key_{provider_id}", tenant_id=user.tenant_id)
        if not effective_key:
            return {"status": "error", "error": "No API key provided"}

        client = LLMClient()
        model = models[0] if models else "gpt-4o-mini"
        return await client.check_health(base_url, effective_key, model)

    async def get_platform_llm_status(self, user: AuthContext) -> list[dict[str, Any]]:
        from app.swarm.llm import LLMClient

        providers = self.get_platform_llm_providers(user)
        client = LLMClient()
        results = []
        for provider in providers:
            provider_id = provider.get("id")
            api_key = persistence.get_setting(f"platform_llm_key_{provider_id}", tenant_id=user.tenant_id)
            if not api_key:
                results.append({**provider, "health": "error", "error": "No platform key configured"})
                continue
            model = provider.get("models", ["gpt-4o-mini"])[0]
            health = await client.check_health(provider.get("base_url"), api_key, model)
            results.append({
                **provider,
                "health": health["status"],
                "latency": health.get("latency", 0),
                "error": health.get("error"),
            })
        return results

    def update_platform_llm_key(self, user: AuthContext, provider_id: str, key: str) -> dict[str, str]:
        persistence.upsert_setting(f"platform_llm_key_{provider_id.lower()}", key, tenant_id=user.tenant_id)
        write_admin_audit(
            actor=user,
            action="platform.llm_key.update",
            category="security",
            target_type="llm_provider",
            target_id=provider_id,
            details={"provider": provider_id},
        )
        return {"status": "ok"}


service = AdminBillingPlatformService()
