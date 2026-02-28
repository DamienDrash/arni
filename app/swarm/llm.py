"""app/swarm/llm.py — Gold-Standard LLM Client with Cost Tracking.

Resolves configuration (Provider, URL, Key) from the database settings.
Supports OpenAI, Gemini, Mistral, Groq, Anthropic, xAI and more.
Tracks token usage and costs per request in llm_usage_log.
"""
import time
import structlog
import httpx
import json
from typing import Any, Optional
from dataclasses import dataclass

from app.gateway.persistence import persistence
from config.settings import get_settings

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


# ── Cost Cache ─────────────────────────────────────────────────────────────────
_cost_cache: dict[str, tuple[int, int]] = {}
_cost_cache_ts: float = 0.0
COST_CACHE_TTL = 300  # 5 minutes


def _get_model_costs(model_id: str) -> tuple[int, int]:
    """Return (input_cost_per_million, output_cost_per_million) for a model.
    Uses an in-memory cache refreshed every 5 minutes."""
    global _cost_cache, _cost_cache_ts
    now = time.time()
    if now - _cost_cache_ts > COST_CACHE_TTL or not _cost_cache:
        try:
            from app.core.db import SessionLocal
            from app.core.models import LLMModelCost
            db = SessionLocal()
            try:
                costs = db.query(LLMModelCost).filter(LLMModelCost.is_active.is_(True)).all()
                _cost_cache = {c.model_id: (c.input_cost_per_million, c.output_cost_per_million) for c in costs}
                _cost_cache_ts = now
            finally:
                db.close()
        except Exception as e:
            logger.warning("llm.cost_cache_refresh_failed", error=str(e))
    return _cost_cache.get(model_id, (0, 0))


def _calculate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> tuple[float, float, float]:
    """Calculate cost in USD-cents for a given token usage."""
    input_cpm, output_cpm = _get_model_costs(model_id)
    input_cost = (prompt_tokens / 1_000_000) * input_cpm
    output_cost = (completion_tokens / 1_000_000) * output_cpm
    return round(input_cost, 6), round(output_cost, 6), round(input_cost + output_cost, 6)


def _log_usage(
    tenant_id: int,
    user_id: Optional[str],
    agent_name: Optional[str],
    provider_id: str,
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
    """Persist a usage log entry and update the monthly usage counter. Non-blocking."""
    try:
        from app.core.db import SessionLocal, engine
        from app.core.models import LLMUsageLog
        from sqlalchemy import text as sa_text
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            # 1. Insert detailed log entry
            log = LLMUsageLog(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_name=agent_name,
                provider_id=provider_id,
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

            # 2. Atomically increment monthly token counter
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
        logger.warning("llm.usage_log_failed", error=str(e), tenant_id=tenant_id)


def _extract_usage_openai(data: dict) -> tuple[int, int, int]:
    """Extract token usage from OpenAI-compatible response."""
    usage = data.get("usage", {})
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    tt = usage.get("total_tokens", pt + ct)
    return pt, ct, tt


def _extract_usage_gemini(data: dict) -> tuple[int, int, int]:
    """Extract token usage from Gemini response."""
    meta = data.get("usageMetadata", {})
    pt = meta.get("promptTokenCount", 0)
    ct = meta.get("candidatesTokenCount", 0)
    tt = meta.get("totalTokenCount", pt + ct)
    return pt, ct, tt


class LLMClient:
    """
    Gold Standard LLM Client with Cost Tracking.
    Resolves configuration (Provider, URL, Key) from the database settings.
    Supports OpenAI, Gemini, Mistral, Groq, Anthropic, xAI and more.
    Logs every request with token counts and calculated costs.
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
        2. Resolved: provider_id or auto-detect from DB settings
        """

        # ── 1. Resolve Provider Configuration ──────────────────────────────
        effective_provider_id = provider_id or "unknown"
        effective_model = model
        effective_url = provider_url
        effective_key = api_key
        is_gemini = False

        if effective_url and effective_key and effective_model:
            # Pattern 1: All params provided by caller (BaseAgent._chat)
            if "gemini" in (effective_url or "").lower() or "generativelanguage" in (effective_url or "").lower():
                is_gemini = True
                effective_provider_id = "gemini"
            elif "groq" in (effective_url or "").lower():
                effective_provider_id = "groq"
            elif "mistral" in (effective_url or "").lower():
                effective_provider_id = "mistral"
            elif "anthropic" in (effective_url or "").lower():
                effective_provider_id = "anthropic"
            elif "x.ai" in (effective_url or "").lower():
                effective_provider_id = "xai"
            elif "openai" in (effective_url or "").lower():
                effective_provider_id = "openai"
        else:
            # Pattern 2: Resolve from DB
            providers_json = persistence.get_setting("platform_llm_providers_json", "[]", tenant_id=1)
            configured_providers = json.loads(providers_json)

            if not configured_providers and not self._env_key:
                return "Error: No LLM providers configured in AI Engine."

            provider = None
            if provider_id:
                provider = next((p for p in configured_providers if p["id"] == provider_id), None)
            elif configured_providers:
                provider = configured_providers[0]

            if provider:
                effective_key = effective_key or persistence.get_setting(f"platform_llm_key_{provider['id']}", "", tenant_id=1)
                effective_url = provider.get("base_url", "")
                effective_model = effective_model or provider["models"][0]
                effective_provider_id = provider["id"]
                is_gemini = "gemini" in provider.get("type", "").lower()
            else:
                effective_key = effective_key or self._env_key
                effective_url = "https://api.openai.com/v1"
                effective_model = effective_model or "gpt-4o-mini"
                effective_provider_id = "openai"

        if not effective_key:
            return f"Error: API Key for provider {effective_provider_id} missing."

        # ── 2. API Request ─────────────────────────────────────────────────
        start_time = time.time()
        prompt_tokens = completion_tokens = total_tokens = 0

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if is_gemini:
                    # Google Gemini Protocol
                    gemini_messages = []
                    system_text = ""
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

                    url = f"{effective_url.rstrip('/')}/models/{effective_model}:generateContent?key={effective_key}"
                    resp = await client.post(url, json=payload)
                    data = resp.json()

                    if resp.status_code != 200:
                        error_msg = data.get("error", {}).get("message", resp.text[:200])
                        latency = round((time.time() - start_time) * 1000)
                        _log_usage(tenant_id, user_id, agent_name, effective_provider_id, effective_model,
                                   0, 0, 0, 0, 0, 0, latency, False, error_msg)
                        logger.error("llm.provider_error", status=resp.status_code, detail=error_msg[:200])
                        return f"LLM Error ({resp.status_code})"

                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                    prompt_tokens, completion_tokens, total_tokens = _extract_usage_gemini(data)

                else:
                    # OpenAI / Mistral / Groq / xAI / Anthropic-Shim Protocol
                    resp = await client.post(
                        f"{effective_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {effective_key}", "Content-Type": "application/json"},
                        json={
                            "model": effective_model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    )
                    data = resp.json()

                    if resp.status_code != 200:
                        error_msg = data.get("error", {}).get("message", resp.text[:200])
                        latency = round((time.time() - start_time) * 1000)
                        _log_usage(tenant_id, user_id, agent_name, effective_provider_id, effective_model or "unknown",
                                   0, 0, 0, 0, 0, 0, latency, False, error_msg)
                        logger.error("llm.provider_error", status=resp.status_code, detail=error_msg[:200])
                        return f"LLM Error ({resp.status_code})"

                    content = data["choices"][0]["message"]["content"]
                    prompt_tokens, completion_tokens, total_tokens = _extract_usage_openai(data)

                # ── 3. Cost Calculation & Logging ──────────────────────────
                latency = round((time.time() - start_time) * 1000)
                input_cost, output_cost, total_cost = _calculate_cost(
                    effective_model or "unknown", prompt_tokens, completion_tokens
                )

                _log_usage(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_name=agent_name,
                    provider_id=effective_provider_id,
                    model_id=effective_model or "unknown",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    input_cost_cents=input_cost,
                    output_cost_cents=output_cost,
                    total_cost_cents=total_cost,
                    latency_ms=latency,
                    success=True,
                )

                logger.info(
                    "llm.success",
                    model=effective_model,
                    latency_ms=latency,
                    provider=effective_provider_id,
                    tokens=total_tokens,
                    cost_cents=round(total_cost, 4),
                    tenant_id=tenant_id,
                )

                return content

        except Exception as e:
            latency = round((time.time() - start_time) * 1000)
            _log_usage(tenant_id, user_id, agent_name, effective_provider_id, effective_model or "unknown",
                       0, 0, 0, 0, 0, 0, latency, False, str(e))
            logger.error("llm.request_failed", error=str(e))
            return f"LLM Connection Failed: {str(e)}"

    async def ask(self, prompt: str, system_prompt: str = "You are a helpful assistant.",
                  tenant_id: int = 1) -> str:
        """Simple helper for single-turn questions."""
        return await self.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            tenant_id=tenant_id,
        )
