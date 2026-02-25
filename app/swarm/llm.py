import time
import structlog
import httpx
import json
from typing import Any, Optional
from app.gateway.persistence import persistence
from config.settings import get_settings

logger = structlog.get_logger()

class LLMClient:
    """
    Gold Standard LLM Client.
    Resolves configuration (Provider, URL, Key) from the database settings.
    Supports OpenAI, Gemini, Mistral, and more.
    """

    def __init__(self, openai_api_key: str = ""):
        # Fallback to env key if nothing is in DB yet
        self._env_key = openai_api_key

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        tenant_id: int = 1, # Default to System for platform features
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Execute a chat completion resolving credentials from DB."""
        
        # 1. Resolve Provider Configuration
        # We look for the configured providers in the DB
        providers_json = persistence.get_setting("platform_llm_providers_json", "[]", tenant_id=1)
        configured_providers = json.loads(providers_json)
        
        if not configured_providers and not self._env_key:
            return "Error: No LLM providers configured in AI Engine."

        # 2. Select Provider
        # If no provider_id requested, use the first enabled one
        provider = None
        if provider_id:
            provider = next((p for p in configured_providers if p["id"] == provider_id), None)
        elif configured_providers:
            provider = configured_providers[0] # Use first as default

        # 3. Resolve API Key and URL
        if provider:
            api_key = persistence.get_setting(f"platform_llm_key_{provider['id']}", "", tenant_id=1)
            base_url = provider["base_url"]
            effective_model = model or provider["models"][0]
        else:
            # Fallback to OpenAI ENV if no provider in DB
            api_key = self._env_key
            base_url = "https://api.openai.com/v1"
            effective_model = model or "gpt-4o-mini"

        if not api_key:
            return f"Error: API Key for provider {provider['id'] if provider else 'Default'} missing."

        # 4. API Request
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                # Handle different API types
                if provider and "gemini" in provider.get("type", "").lower():
                    # Google Gemini Protocol
                    resp = await client.post(
                        f"{base_url.rstrip('/')}/models/{effective_model}:generateContent?key={api_key}",
                        json={"contents": [{"parts": [{"text": json.dumps(messages)}]}]} # Simplified for now
                    )
                    data = resp.json()
                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    # OpenAI / Mistral / Groq / Anthropic-Shim Protocol
                    resp = await client.post(
                        f"{base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": effective_model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    )
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                
                if resp.status_code != 200:
                    logger.error("llm.provider_error", status=resp.status_code, detail=resp.text[:200])
                    return f"LLM Error ({resp.status_code})"

                latency = round((time.time() - start_time) * 1000)
                logger.info("llm.success", model=effective_model, latency_ms=latency, provider=provider["id"] if provider else "openai_env")
                
                return content

        except Exception as e:
            logger.error("llm.request_failed", error=str(e))
            return f"LLM Connection Failed: {str(e)}"

    async def ask(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        """Simple helper for single-turn questions."""
        return await self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
