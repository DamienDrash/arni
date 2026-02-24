"""ARIIA v1.4 – Base Agent Interface.

@ARCH: Abstract base class for all Swarm Agents (Sprint 2, Task 2.1).
Sprint 14: Added dynamic provider/key lookup (Tenant -> Platform).
"""

from __future__ import annotations
import json
import structlog
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from app.gateway.schemas import InboundMessage, OutboundMessage, Platform

if TYPE_CHECKING:
    from app.swarm.llm import LLMClient

logger = structlog.get_logger()

@dataclass
class AgentResponse:
    content: str
    confidence: float = 1.0
    requires_confirmation: bool = False
    metadata: dict | None = None

class AgentHandoff(Exception):
    """Signal to router to transfer control to another agent."""
    def __init__(self, target_agent: str, reason: str):
        self.target_agent = target_agent
        self.reason = reason

class BaseAgent(ABC):
    _llm: LLMClient | None = None

    @classmethod
    def set_llm(cls, llm: LLMClient) -> None:
        cls._llm = llm

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    async def handle(self, message: InboundMessage) -> AgentResponse:
        pass

    def _parse_tool_call(self, response: str) -> tuple[str, str] | None:
        import re
        match = re.search(r"TOOL:\s*(\w+)\((.*)\)", response, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2).strip()
        return None

    async def _chat(
        self,
        system_prompt: str,
        user_message: str,
        user_id: str | None = None,
        tenant_id: int | None = None,
        history_limit: int = 10,
    ) -> str | None:
        """Call LLM with hierarchical key lookup and dynamic provider config."""
        if not self._llm:
            return None
        
        from app.gateway.persistence import persistence
        
        # 1. Resolve Provider & Model
        # Lookup in Tenant settings, fallback to Platform defaults
        provider_id = persistence.get_setting("llm_provider_id", "openai", tenant_id=tenant_id)
        model = persistence.get_setting("llm_model", "gpt-4o-mini", tenant_id=tenant_id)
        
        # Get Provider Base URL from Platform Inventory
        providers_json = persistence.get_setting("platform_llm_providers_json") or "[]"
        providers = json.loads(providers_json)
        provider_config = next((p for p in providers if p["id"] == provider_id), {"base_url": "https://api.openai.com/v1"})
        
        # 2. Hierarchical API Key Lookup
        # A. Check for Tenant-specific Key (BYOK)
        # We look for a key named '{provider_id}_api_key' in tenant settings
        api_key = persistence.get_setting(f"{provider_id}_api_key", tenant_id=tenant_id)
        
        # B. Fallback to Platform-wide Key
        if not api_key:
            api_key = persistence.get_setting(f"platform_llm_key_{provider_id}")
            
        if not api_key:
            logger.error("agent.chat.no_key_found", provider=provider_id, tenant_id=tenant_id)
            return "Error: No LLM API key configured for this provider."

        # 3. Message Preparation
        messages = [{"role": "system", "content": system_prompt}]
        if user_id:
            try:
                history = persistence.get_chat_history(str(user_id), limit=history_limit, tenant_id=tenant_id)
                for item in history:
                    if item.role in {"user", "assistant"}:
                        messages.append({"role": item.role, "content": item.content})
            except Exception: pass
        messages.append({"role": "user", "content": user_message})

        # 4. LLM Call
        try:
            return await self._llm.chat(
                messages=messages,
                provider_url=provider_config["base_url"],
                model=model,
                api_key=api_key,
                temperature=0.7,
                max_tokens=500
            )
        except Exception as e:
            logger.warning("agent.llm_failed", agent=self.name, error=str(e))
            return None

    async def _chat_with_messages(
        self,
        messages: list[dict[str, str]],
        tenant_id: int | None = None,
    ) -> str | None:
        """Low-level LLM call with a raw message list."""
        if not self._llm:
            return None
        
        from app.gateway.persistence import persistence
        provider_id = persistence.get_setting("llm_provider_id", "openai", tenant_id=tenant_id)
        model = persistence.get_setting("llm_model", "gpt-4o-mini", tenant_id=tenant_id)
        providers_json = persistence.get_setting("platform_llm_providers_json") or "[]"
        providers = json.loads(providers_json)
        provider_config = next((p for p in providers if p["id"] == provider_id), {"base_url": "https://api.openai.com/v1"})
        
        api_key = persistence.get_setting(f"{provider_id}_api_key", tenant_id=tenant_id)
        if not api_key:
            api_key = persistence.get_setting(f"platform_llm_key_{provider_id}")
            
        if not api_key:
            return "Error: No API key."

        try:
            return await self._llm.chat(
                messages=messages,
                provider_url=provider_config["base_url"],
                model=model,
                api_key=api_key,
                temperature=0.1, # Lower temp for tool loops
                max_tokens=500
            )
        except Exception:
            return None

    def _build_outbound(self, message: InboundMessage, response: AgentResponse) -> OutboundMessage:
        return OutboundMessage(
            message_id=f"resp-{message.message_id}",
            platform=message.platform,
            user_id=message.user_id,
            content=response.content,
            reply_to=message.message_id,
            tenant_id=message.tenant_id,
        )
