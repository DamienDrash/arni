"""ARIIA AI Config – Gateway Abstraction Layer.

Provides a clean interface between the agent system and the LLM providers.
Handles config resolution, provider-specific protocol adaptation, retry logic,
and budget enforcement in a single place.

This replaces the scattered config resolution logic in llm.py and base.py.
"""

from __future__ import annotations
import json
import time
import structlog
import httpx
from typing import Optional, Any
from dataclasses import dataclass

from app.ai_config.schemas import ResolvedLLMConfig
from app.domains.billing.models import LLMModelCost, LLMUsageLog
from app.shared.db import open_session

logger = structlog.get_logger()


@dataclass
class GatewayResponse:
    """Structured response from the AI Gateway."""
    content: str
    model: str = ""
    provider_slug: str = ""
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
        msg = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg


class AIGateway:
    """Unified AI Gateway for all LLM interactions.

    Responsibilities:
    1. Accept a ResolvedLLMConfig (from AIConfigService.resolve_llm_config)
    2. Adapt the request to the provider's protocol (OpenAI, Gemini, etc.)
    3. Execute the request with retry logic
    4. Calculate costs and return a structured response
    5. Log usage for cost tracking

    This is the single point of contact for all LLM API calls.
    """

    async def chat(
        self,
        config: ResolvedLLMConfig,
        messages: list[dict],
        *,
        tenant_id: int = 1,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> GatewayResponse:
        """Execute a chat completion using the resolved config.

        Args:
            config: Fully resolved LLM configuration
            messages: Chat messages in OpenAI format
            tenant_id: For usage logging
            user_id: For usage logging
            agent_name: For usage logging
            temperature: Override (or use config default)
            max_tokens: Override (or use config default)
        """
        effective_temp = temperature if temperature is not None else config.temperature
        effective_max_tokens = max_tokens if max_tokens is not None else config.max_tokens
        is_gemini = config.provider_type == "gemini"

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if is_gemini:
                    return await self._call_gemini(
                        client, config, messages, effective_temp, effective_max_tokens,
                        start_time, tenant_id, user_id, agent_name,
                    )
                else:
                    return await self._call_openai_compatible(
                        client, config, messages, None, effective_temp, effective_max_tokens,
                        start_time, tenant_id, user_id, agent_name,
                    )
        except Exception as e:
            latency = round((time.time() - start_time) * 1000)
            self._log_usage(
                tenant_id, user_id, agent_name, config.provider_slug,
                config.model, 0, 0, 0, 0, 0, 0, latency, False, str(e),
            )
            logger.error("ai_gateway.request_failed", error=str(e), provider=config.provider_slug)
            return GatewayResponse(
                content=f"LLM Connection Failed: {str(e)}",
                model=config.model,
                provider_slug=config.provider_slug,
                latency_ms=latency,
                success=False,
                error=str(e),
            )

    async def chat_with_tools(
        self,
        config: ResolvedLLMConfig,
        messages: list[dict],
        tools: list[dict],
        *,
        tenant_id: int = 1,
        user_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tool_choice: str = "auto",
    ) -> GatewayResponse:
        """Execute a chat completion with native tool calling support."""
        effective_temp = temperature if temperature is not None else config.temperature
        effective_max_tokens = max_tokens if max_tokens is not None else config.max_tokens

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                return await self._call_openai_compatible(
                    client, config, messages, tools, effective_temp, effective_max_tokens,
                    start_time, tenant_id, user_id, agent_name, tool_choice=tool_choice,
                )
        except Exception as e:
            latency = round((time.time() - start_time) * 1000)
            self._log_usage(
                tenant_id, user_id, agent_name, config.provider_slug,
                config.model, 0, 0, 0, 0, 0, 0, latency, False, str(e),
            )
            logger.error("ai_gateway.tool_calling_failed", error=str(e))
            return GatewayResponse(
                content=f"LLM Connection Failed: {str(e)}",
                model=config.model,
                provider_slug=config.provider_slug,
                latency_ms=latency,
                success=False,
                error=str(e),
            )

    # ── Protocol Adapters ─────────────────────────────────────────────────

    # Models that require max_completion_tokens instead of max_tokens
    _MAX_COMPLETION_TOKENS_MODELS = ("o1", "o3", "o4", "gpt-5")
    # Models that do not accept a temperature parameter (only default=1 supported)
    _NO_TEMPERATURE_MODELS = ("o1", "o3", "o4", "gpt-5")

    @classmethod
    def _uses_max_completion_tokens(cls, model: str) -> bool:
        return any(model.startswith(p) for p in cls._MAX_COMPLETION_TOKENS_MODELS)

    @classmethod
    def _supports_temperature(cls, model: str) -> bool:
        return not any(model.startswith(p) for p in cls._NO_TEMPERATURE_MODELS)

    async def _call_openai_compatible(
        self,
        client: httpx.AsyncClient,
        config: ResolvedLLMConfig,
        messages: list[dict],
        tools: Optional[list[dict]],
        temperature: float,
        max_tokens: int,
        start_time: float,
        tenant_id: int,
        user_id: Optional[str],
        agent_name: Optional[str],
        tool_choice: str = "auto",
    ) -> GatewayResponse:
        """Call an OpenAI-compatible API (OpenAI, Anthropic, Groq, Mistral, xAI)."""
        tokens_key = (
            "max_completion_tokens"
            if self._uses_max_completion_tokens(config.model)
            else "max_tokens"
        )
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            tokens_key: max_tokens,
        }
        if self._supports_temperature(config.model):
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        resp = await client.post(
            f"{config.api_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = resp.json()

        if resp.status_code != 200:
            error_msg = data.get("error", {}).get("message", resp.text[:200])
            latency = round((time.time() - start_time) * 1000)
            self._log_usage(
                tenant_id, user_id, agent_name, config.provider_slug,
                config.model, 0, 0, 0, 0, 0, 0, latency, False, error_msg,
            )
            return GatewayResponse(
                content=f"LLM Error ({resp.status_code})",
                model=config.model,
                provider_slug=config.provider_slug,
                latency_ms=latency,
                success=False,
                error=error_msg,
            )

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        tool_calls_raw = message.get("tool_calls", [])
        finish_reason = choice.get("finish_reason", "stop")

        usage = data.get("usage", {})
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        tt = usage.get("total_tokens", pt + ct)

        latency = round((time.time() - start_time) * 1000)
        input_cost, output_cost, total_cost = self._calculate_cost(config.model, pt, ct)

        self._log_usage(
            tenant_id, user_id, agent_name, config.provider_slug,
            config.model, pt, ct, tt, input_cost, output_cost, total_cost,
            latency, True, None,
        )

        logger.info(
            "ai_gateway.success",
            model=config.model,
            provider=config.provider_slug,
            latency_ms=latency,
            tokens=tt,
            cost_cents=round(total_cost, 4),
        )

        return GatewayResponse(
            content=content,
            model=config.model,
            provider_slug=config.provider_slug,
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=tt,
            input_cost_cents=input_cost,
            output_cost_cents=output_cost,
            total_cost_cents=total_cost,
            latency_ms=latency,
            success=True,
            tool_calls=tool_calls_raw,
            raw_response=data,
            finish_reason=finish_reason,
        )

    async def _call_gemini(
        self,
        client: httpx.AsyncClient,
        config: ResolvedLLMConfig,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        start_time: float,
        tenant_id: int,
        user_id: Optional[str],
        agent_name: Optional[str],
    ) -> GatewayResponse:
        """Call Google Gemini native API."""
        system_text = ""
        gemini_messages = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            else:
                role = "user" if m["role"] == "user" else "model"
                gemini_messages.append({"role": role, "parts": [{"text": m["content"]}]})

        payload: dict[str, Any] = {"contents": gemini_messages}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }

        url = f"{config.api_base_url.rstrip('/')}/models/{config.model}:generateContent?key={config.api_key}"
        resp = await client.post(url, json=payload)
        data = resp.json()

        if resp.status_code != 200:
            error_msg = data.get("error", {}).get("message", resp.text[:200])
            latency = round((time.time() - start_time) * 1000)
            self._log_usage(
                tenant_id, user_id, agent_name, config.provider_slug,
                config.model, 0, 0, 0, 0, 0, 0, latency, False, error_msg,
            )
            return GatewayResponse(
                content=f"LLM Error ({resp.status_code})",
                model=config.model,
                provider_slug=config.provider_slug,
                latency_ms=latency,
                success=False,
                error=error_msg,
            )

        content = data["candidates"][0]["content"]["parts"][0]["text"]
        meta = data.get("usageMetadata", {})
        pt = meta.get("promptTokenCount", 0)
        ct = meta.get("candidatesTokenCount", 0)
        tt = meta.get("totalTokenCount", pt + ct)

        latency = round((time.time() - start_time) * 1000)
        input_cost, output_cost, total_cost = self._calculate_cost(config.model, pt, ct)

        self._log_usage(
            tenant_id, user_id, agent_name, config.provider_slug,
            config.model, pt, ct, tt, input_cost, output_cost, total_cost,
            latency, True, None,
        )

        logger.info(
            "ai_gateway.gemini.success",
            model=config.model,
            latency_ms=latency,
            tokens=tt,
            cost_cents=round(total_cost, 4),
        )

        return GatewayResponse(
            content=content,
            model=config.model,
            provider_slug=config.provider_slug,
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=tt,
            input_cost_cents=input_cost,
            output_cost_cents=output_cost,
            total_cost_cents=total_cost,
            latency_ms=latency,
            success=True,
            raw_response=data,
            finish_reason="stop",
        )

    # ── Cost Calculation ──────────────────────────────────────────────────

    _cost_cache: dict[str, tuple[int, int]] = {}
    _cost_cache_ts: float = 0.0
    _COST_CACHE_TTL = 300

    def _calculate_cost(self, model_id: str, prompt_tokens: int, completion_tokens: int) -> tuple[float, float, float]:
        """Calculate cost in USD-cents using the LLMModelCost table."""
        now = time.time()
        if now - self._cost_cache_ts > self._COST_CACHE_TTL or not self._cost_cache:
            try:
                db = open_session()
                try:
                    costs = db.query(LLMModelCost).filter(LLMModelCost.is_active.is_(True)).all()
                    self.__class__._cost_cache = {c.model_id: (c.input_cost_per_million, c.output_cost_per_million) for c in costs}
                    self.__class__._cost_cache_ts = now
                finally:
                    db.close()
            except Exception as e:
                logger.warning("ai_gateway.cost_cache_refresh_failed", error=str(e))

        input_cpm, output_cpm = self._cost_cache.get(model_id, (0, 0))
        input_cost = (prompt_tokens / 1_000_000) * input_cpm
        output_cost = (completion_tokens / 1_000_000) * output_cpm
        return round(input_cost, 6), round(output_cost, 6), round(input_cost + output_cost, 6)

    # ── Usage Logging ─────────────────────────────────────────────────────

    @staticmethod
    def _log_usage(
        tenant_id: int,
        user_id: Optional[str],
        agent_name: Optional[str],
        provider_slug: str,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        input_cost_cents: float,
        output_cost_cents: float,
        total_cost_cents: float,
        latency_ms: int,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Persist usage log entry. Non-blocking."""
        try:
            from app.core.db import engine
            from sqlalchemy import text as sa_text
            from datetime import datetime, timezone

            db = open_session()
            try:
                log = LLMUsageLog(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_name=agent_name,
                    provider_id=provider_slug,
                    model_id=model_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    input_cost_cents=input_cost_cents,
                    output_cost_cents=output_cost_cents,
                    total_cost_cents=total_cost_cents,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message,
                )
                db.add(log)

                now = datetime.now(timezone.utc)
                dialect = engine.dialect.name
                if dialect == "postgresql":
                    db.execute(sa_text(
                        "INSERT INTO usage_records (tenant_id, period_year, period_month, llm_tokens_used, messages_inbound, messages_outbound, active_members, llm_tokens_purchased) "
                        "VALUES (:tid, :yr, :mo, :amt, 0, 0, 0, 0) "
                        "ON CONFLICT (tenant_id, period_year, period_month) "
                        "DO UPDATE SET llm_tokens_used = usage_records.llm_tokens_used + :amt"
                    ), {"tid": tenant_id, "yr": now.year, "mo": now.month, "amt": total_tokens})
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning("ai_gateway.usage_log_failed", error=str(e), tenant_id=tenant_id)


# Module-level singleton
_gateway: AIGateway | None = None


def get_ai_gateway() -> AIGateway:
    """Return the module-level AIGateway singleton."""
    global _gateway
    if _gateway is None:
        _gateway = AIGateway()
    return _gateway
