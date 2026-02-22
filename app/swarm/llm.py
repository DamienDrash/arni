"""ARIIA v1.4 – LLM Client Abstraction.

@BACKEND: Sprint 2, Task 2.9
OpenAI primary → Ollama fallback. Automatic switchover on error/timeout.
"""

import structlog
from typing import Any

logger = structlog.get_logger()


class LLMClient:
    """Unified LLM interface with automatic fallback.

    Primary: OpenAI GPT-4o-mini (fast, cheap)
    Fallback: Ollama/Llama-3 (local, offline-capable)
    """

    def __init__(
        self,
        openai_api_key: str = "",
        ollama_base_url: str = "http://127.0.0.1:11434",
        ollama_model: str = "llama3",
    ) -> None:
        self._openai_api_key = openai_api_key
        self._ollama_base_url = ollama_base_url
        self._ollama_model = ollama_model
        self._using_fallback = False

    @property
    def is_fallback_active(self) -> bool:
        """Check if currently using local Ollama fallback."""
        return self._using_fallback

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 500,
        api_key: str | None = None,
    ) -> str:
        """Send a chat completion request.

        Tries OpenAI first, falls back to Ollama on failure.

        Args:
            messages: Chat messages in OpenAI format.
            model: Model name (ignored for Ollama fallback).
            temperature: Sampling temperature.
            max_tokens: Max response tokens.
            api_key: Optional tenant-specific API key.

        Returns:
            Response text content.
        """
        # Use provided api_key or fallback to instance default
        effective_key = api_key or self._openai_api_key

        # Try OpenAI first
        if effective_key and not self._using_fallback:
            try:
                return await self._call_openai(messages, model, temperature, max_tokens, effective_key)
            except Exception as e:
                logger.wariiang(
                    "llm.openai_failed",
                    error=str(e),
                    action="switching_to_ollama",
                )
                self._using_fallback = True

        # Ollama fallback
        try:
            return await self._call_ollama(messages, temperature, max_tokens)
        except Exception as e:
            logger.error("llm.all_providers_failed", error=str(e))
            return self._emergency_response()

    async def _call_openai(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: str,
    ) -> str:
        """Call OpenAI Chat Completions API."""
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug("llm.openai_response", model=model, tokens=data.get("usage", {}))
            return content

    async def _call_ollama(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call local Ollama instance."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._ollama_base_url}/api/chat",
                json={
                    "model": self._ollama_model,
                    "messages": messages,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["message"]["content"]
            logger.debug("llm.ollama_response", model=self._ollama_model)
            return content

    def _emergency_response(self) -> str:
        """Last-resort response when all LLM providers fail."""
        return (
            "Hey, sorry – ich bin gerade technisch eingeschränkt. 🔧 "
            "Bitte versuch es gleich nochmal oder ruf direkt im Studio an. "
            "Wir sind für dich da! 💪"
        )

    async def reset_fallback(self) -> None:
        """Try to switch back to OpenAI (called periodically)."""
        if self._using_fallback and self._openai_api_key:
            try:
                test = await self._call_openai(
                    [{"role": "user", "content": "ping"}],
                    "gpt-4o-mini",
                    0.0,
                    5,
                )
                if test:
                    self._using_fallback = False
                    logger.info("llm.openai_restored")
            except Exception:
                pass  # Stay on fallback
