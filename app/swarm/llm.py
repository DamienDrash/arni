"""app/swarm/llm.py — Refactored LLM Client with AI Gateway Integration.

@ARCH: Phase 1 Refactoring – AI Config Management
Now delegates all LLM calls to the centralized AIGateway.
Config resolution uses the hierarchical AIConfigService.
Backward-compatible: existing callers (BaseAgent._chat, etc.) work unchanged.

The LLMResponse dataclass is preserved for backward compatibility.
"""
import json
import structlog
from typing import Any, Optional
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class LLMResponse:
    """Structured response from an LLM call including usage metadata."""
    content: str
    model: str = ""
    provider_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    input_cost_cents: float = 0.0
    output_cost_cents: float = 0.0
    total_cost_cents: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error: str = ""
    tool_calls: list = None
    raw_response: dict = None
    finish_reason: str = ""

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []
        if self.raw_response is None:
            self.raw_response = {}

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def assistant_message(self) -> dict:
        """Return the assistant message dict for the conversation history."""
        msg = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg


class LLMClient:
    """Refactored LLM Client – delegates to AIGateway.

    Maintains backward compatibility with existing callers while using
    the new centralized AI configuration system under the hood.

    Two calling patterns are supported:
    1. Explicit: provider_url + model + api_key (legacy, from BaseAgent._chat)
    2. Resolved: Uses AIConfigService for hierarchical config resolution (new)
    """

    def __init__(self, openai_api_key: str = ""):
        self._env_key = openai_api_key

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tenant_id: int = 1,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        provider_id: Optional[str] = None,
        provider_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Execute a chat completion with full cost tracking.

        Supports two calling patterns:
        1. Explicit: provider_url + model + api_key (from BaseAgent._chat)
        2. Resolved: auto-detect from new AI Config system
        """
        from app.ai_config.gateway import get_ai_gateway
        gateway = get_ai_gateway()

        if provider_url and api_key and model:
            # Pattern 1: Legacy explicit params – build a ResolvedLLMConfig directly
            from app.ai_config.schemas import ResolvedLLMConfig
            provider_type = self._detect_provider_type(provider_url)
            config = ResolvedLLMConfig(
                provider_slug=provider_id or self._detect_provider_slug(provider_url),
                provider_type=provider_type,
                api_base_url=provider_url,
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            # Pattern 2: Resolve from new AI Config system
            config = self._resolve_config(tenant_id, agent_name, temperature, max_tokens)

        if not config.api_key:
            return f"Error: API Key for provider {config.provider_slug} missing."

        response = await gateway.chat(
            config,
            messages,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_name=agent_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.success:
            return response.content  # Error message

        return response.content

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        tenant_id: int = 1,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        provider_id: Optional[str] = None,
        provider_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """Execute a chat completion with native tool calling support.

        Returns a full LLMResponse with tool_calls if the LLM wants to use tools.
        """
        from app.ai_config.gateway import get_ai_gateway
        gateway = get_ai_gateway()

        if provider_url and api_key and model:
            from app.ai_config.schemas import ResolvedLLMConfig
            config = ResolvedLLMConfig(
                provider_slug=provider_id or self._detect_provider_slug(provider_url),
                provider_type=self._detect_provider_type(provider_url),
                api_base_url=provider_url,
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            config = self._resolve_config(tenant_id, agent_name, temperature, max_tokens)

        if not config.api_key:
            return LLMResponse(
                content=f"Error: API Key for provider {config.provider_slug} missing.",
                success=False,
                error="missing_api_key",
            )

        gw_response = await gateway.chat_with_tools(
            config,
            messages,
            tools,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_name=agent_name,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
        )

        # Convert GatewayResponse → LLMResponse for backward compatibility
        return LLMResponse(
            content=gw_response.content,
            model=gw_response.model,
            provider_id=gw_response.provider_slug,
            prompt_tokens=gw_response.prompt_tokens,
            completion_tokens=gw_response.completion_tokens,
            total_tokens=gw_response.total_tokens,
            input_cost_cents=gw_response.input_cost_cents,
            output_cost_cents=gw_response.output_cost_cents,
            total_cost_cents=gw_response.total_cost_cents,
            latency_ms=gw_response.latency_ms,
            success=gw_response.success,
            error=gw_response.error,
            tool_calls=gw_response.tool_calls,
            raw_response=gw_response.raw_response,
            finish_reason=gw_response.finish_reason,
        )

    async def ask(self, prompt: str, system_prompt: str = "You are a helpful assistant.",
                  tenant_id: int = 1) -> str:
        """Simple helper for single-turn questions."""
        return await self.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            tenant_id=tenant_id,
        )

    # ── Config Resolution ─────────────────────────────────────────────────

    def _resolve_config(
        self,
        tenant_id: int,
        agent_name: Optional[str],
        temperature: float,
        max_tokens: int,
    ):
        """Resolve LLM config using the new AIConfigService.

        Falls back to legacy Settings-based resolution if the new system
        is not yet seeded.
        """
        from app.ai_config.schemas import ResolvedLLMConfig

        try:
            from app.shared.db import open_session
            from app.ai_config.service import AIConfigService

            db = open_session()
            try:
                svc = AIConfigService(db)
                config = svc.resolve_llm_config(tenant_id, agent_slug=agent_name)
                return config
            finally:
                db.close()
        except Exception as e:
            logger.warning("llm.config_resolve_fallback", error=str(e))
            # Fallback to legacy resolution
            return self._legacy_resolve(tenant_id, temperature, max_tokens)

    def _legacy_resolve(self, tenant_id: int, temperature: float, max_tokens: int):
        """Legacy config resolution from Settings table (backward compatibility)."""
        from app.gateway.persistence import persistence
        from app.ai_config.schemas import ResolvedLLMConfig
        from config.settings import get_settings

        providers_json = persistence.get_setting("platform_llm_providers_json", "[]", tenant_id=1)
        configured_providers = json.loads(providers_json)

        if configured_providers:
            provider = configured_providers[0]
            api_key = persistence.get_setting(f"platform_llm_key_{provider['id']}", "", tenant_id=1)
            is_gemini = "gemini" in provider.get("type", "").lower()
            return ResolvedLLMConfig(
                provider_slug=provider["id"],
                provider_type="gemini" if is_gemini else "openai_compatible",
                api_base_url=provider.get("base_url", "https://api.openai.com/v1"),
                api_key=api_key,
                model=provider["models"][0] if provider.get("models") else "gpt-4o-mini",
                temperature=temperature,
                max_tokens=max_tokens,
            )

        settings = get_settings()
        return ResolvedLLMConfig(
            provider_slug="openai",
            provider_type="openai_compatible",
            api_base_url="https://api.openai.com/v1",
            api_key=self._env_key or settings.openai_api_key,
            model="gpt-4o-mini",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ── Provider Detection Helpers ────────────────────────────────────────

    @staticmethod
    def _detect_provider_slug(url: str) -> str:
        """Detect provider slug from API URL."""
        url_lower = url.lower()
        if "gemini" in url_lower or "generativelanguage" in url_lower:
            return "gemini"
        elif "groq" in url_lower:
            return "groq"
        elif "mistral" in url_lower:
            return "mistral"
        elif "anthropic" in url_lower:
            return "anthropic"
        elif "x.ai" in url_lower:
            return "xai"
        elif "openai" in url_lower:
            return "openai"
        return "unknown"

    @staticmethod
    def _detect_provider_type(url: str) -> str:
        """Detect provider protocol type from API URL."""
        url_lower = url.lower()
        if "gemini" in url_lower or "generativelanguage" in url_lower:
            return "gemini"
        return "openai_compatible"
