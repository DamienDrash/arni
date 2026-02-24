"""ARIIA v1.4 – Unified LLM Client (Multi-Provider).

Supports OpenAI-compatible APIs (Groq, Anthropic-Shim, Local vLLM/Ollama).
Provides failover and tenant-aware key management.
"""

import time
import structlog
import httpx
from typing import Any, Optional

logger = structlog.get_logger()

class LLMClient:
    """Multi-provider LLM client with OpenAI-compatible interface."""

    def __init__(self, openai_api_key: str = ""):
        self._default_key = openai_api_key

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        provider_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Execute a chat completion against a specific provider."""
        effective_key = api_key or self._default_key
        if not effective_key:
            logger.error("llm.missing_api_key", provider=provider_url)
            return "Error: No API key configured for LLM."

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{provider_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {effective_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                
                if response.status_code != 200:
                    error_detail = response.text[:200]
                    logger.error("llm.provider_error", status=response.status_code, detail=error_detail)
                    return f"LLM Error ({response.status_code}): {error_detail}"

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                latency = round((time.time() - start_time) * 1000)
                logger.debug("llm.success", model=model, latency_ms=latency)
                
                return content

        except Exception as e:
            logger.error("llm.request_failed", error=str(e))
            return f"LLM Connection Failed: {str(e)}"

    async def check_health(self, provider_url: str, api_key: str, model: str) -> dict[str, Any]:
        """Verify if a provider/key combo is working."""
        start = time.time()
        try:
            res = await self.chat(
                [{"role": "user", "content": "health-check-ping"}],
                provider_url=provider_url,
                model=model,
                api_key=api_key,
                max_tokens=5
            )
            latency = round((time.time() - start) * 1000)
            is_ok = not res.startswith("Error") and not res.startswith("LLM")
            return {"status": "ok" if is_ok else "error", "latency": latency, "response": res[:50]}
        except Exception as e:
            return {"status": "error", "error": str(e)}
