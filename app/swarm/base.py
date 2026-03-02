"""ARIIA v2.0 – Base Agent Interface (Refactored for AI Config Management).

@ARCH: Abstract base class for all Swarm Agents.
Refactored: Uses AIConfigService for hierarchical config resolution instead of
scattered Settings-table lookups. Backward compatible with existing agents.
"""

from __future__ import annotations
import json
import structlog
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

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
        """Call LLM with hierarchical config resolution via AI Config Service.

        Resolution hierarchy:
        1. Agent Definition defaults (from ai_agent_definitions)
        2. Tenant Agent Override (from ai_tenant_agent_configs)
        3. Plan Budget Constraints (from ai_plan_budgets)
        4. Tenant/Platform Provider (BYOK or platform key)

        Falls back to legacy Settings-based resolution if new system unavailable.
        """
        if not self._llm:
            return None

        # Resolve config via the new AI Config system
        config = self._resolve_agent_config(tenant_id)

        # Message Preparation
        messages = [{"role": "system", "content": system_prompt}]
        if user_id:
            try:
                from app.gateway.persistence import persistence
                history = persistence.get_chat_history(str(user_id), limit=history_limit, tenant_id=tenant_id)
                for item in history:
                    if item.role in {"user", "assistant"}:
                        messages.append({"role": item.role, "content": item.content})
            except Exception:
                pass
        messages.append({"role": "user", "content": user_message})

        # LLM Call via refactored LLMClient (which uses AIGateway)
        try:
            if config:
                return await self._llm.chat(
                    messages=messages,
                    tenant_id=tenant_id or 1,
                    user_id=user_id,
                    agent_name=self.name,
                    provider_id=config.provider_slug,
                    provider_url=config.api_base_url,
                    model=config.model,
                    api_key=config.api_key,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )
            else:
                # Fallback: let LLMClient handle resolution
                return await self._llm.chat(
                    messages=messages,
                    tenant_id=tenant_id or 1,
                    user_id=user_id,
                    agent_name=self.name,
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

        config = self._resolve_agent_config(tenant_id)

        try:
            if config:
                return await self._llm.chat(
                    messages=messages,
                    tenant_id=tenant_id or 1,
                    agent_name=self.name,
                    provider_id=config.provider_slug,
                    provider_url=config.api_base_url,
                    model=config.model,
                    api_key=config.api_key,
                    temperature=0.1,
                    max_tokens=500,
                )
            else:
                return await self._llm.chat(
                    messages=messages,
                    tenant_id=tenant_id or 1,
                    agent_name=self.name,
                )
        except Exception:
            return None

    def _resolve_agent_config(self, tenant_id: Optional[int] = None):
        """Resolve LLM config for this agent via AIConfigService.

        Returns a ResolvedLLMConfig or None (fallback to legacy).
        """
        try:
            from app.core.db import SessionLocal
            from app.ai_config.service import AIConfigService

            db = SessionLocal()
            try:
                svc = AIConfigService(db)
                config = svc.resolve_llm_config(
                    tenant_id=tenant_id or 1,
                    agent_slug=self.name,
                )
                if config and config.api_key:
                    return config
            finally:
                db.close()
        except Exception as e:
            logger.debug("agent.config_resolve_fallback", agent=self.name, error=str(e))

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
