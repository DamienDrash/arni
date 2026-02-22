"""ARIIA v1.4 – Base Agent Interface.

@ARCH: Abstract base class for all Swarm Agents (Sprint 2, Task 2.1).
Every agent MUST implement `handle()` and provide metadata.
Sprint 9: Added shared LLM integration via `_chat()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from app.gateway.schemas import InboundMessage, OutboundMessage, Platform

if TYPE_CHECKING:
    from app.swarm.llm import LLMClient

logger = structlog.get_logger()


@dataclass
class AgentResponse:
    """Standardized agent response.

    Attributes:
        content: Response text to send back to the user.
        confidence: Agent's confidence in its response (0.0–1.0).
        requires_confirmation: If True, this is a Type-2 (One-Way-Door) action.
        metadata: Additional data (e.g., booking details, crowd count).
    """

    content: str
    confidence: float = 1.0
    requires_confirmation: bool = False
    metadata: dict | None = None


class BaseAgent(ABC):
    """Abstract base class for Swarm Agents.

    All agents must:
    1. Define a `name` and `description`.
    2. Implement `handle()` for message processing.
    3. Respect One-Way-Door principle for irreversible actions.
    4. NOT log PII (see DSGVO_BASELINE.md).
    """

    _llm: LLMClient | None = None

    @classmethod
    def set_llm(cls, llm: LLMClient) -> None:
        """Set the shared LLM client for all agents."""
        cls._llm = llm

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier (e.g., 'ops', 'sales')."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the agent's purpose."""

    @abstractmethod
    async def handle(self, message: InboundMessage) -> AgentResponse:
        """Process an inbound message and return a response.

        Args:
            message: Normalized inbound message from any platform.

        Returns:
            AgentResponse with content, confidence, and optional confirmation flag.
        """

    def _parse_tool_call(self, response: str) -> tuple[str, str] | None:
        """Parse 'TOOL: name(args)' from response using Regex."""
        import re
        # Look for TOOL: name(args) case-insensitive
        match = re.search(r"TOOL:\s*(\w+)\((.*)\)", response, re.IGNORECASE)
        if match:
            name = match.group(1)
            args = match.group(2).strip()
            return name, args
        return None

    async def _chat(
        self,
        system_prompt: str,
        user_message: str,
        user_id: str | None = None,
        tenant_id: int | None = None,
        history_limit: int = 10,
    ) -> str | None:
        """Call LLM with system prompt + user message. Returns None if LLM unavailable."""
        if not self._llm:
            return None
        
        # 1. Guardrails Check (Pre-LLM)
        try:
            from app.core.guardrails import get_guardrails
            block_msg = get_guardrails().check(user_message)
            if block_msg:
                logger.wariiang("agent.guardrail_blocked", agent=self.name, user_id=user_id)
                return block_msg
        except ImportError:
            pass # Fallback if guardrails module broken/missing

        from app.core.observability import get_obs
        obs = get_obs()
        
        # Start Trace
        trace = obs.trace(
            name=f"agent.{self.name}.chat",
            user_id=user_id,
            metadata={"system_prompt_len": len(system_prompt)}
        )
        
        span = trace.span(
            name="llm-generation",
            input={"system": system_prompt, "user": user_message}
        ) if trace else None

        try:
            messages = [{"role": "system", "content": system_prompt}]
            
            # Load Context
            if user_id:
                try:
                    from app.gateway.persistence import persistence
                    history = persistence.get_chat_history(
                        str(user_id),
                        limit=max(1, int(history_limit)),
                        tenant_id=tenant_id,
                    )
                    for item in history[-history_limit:]:
                        role = str(getattr(item, "role", "") or "").lower()
                        if role not in {"user", "assistant"}:
                            continue
                        content = str(getattr(item, "content", "") or "").strip()
                        if not content:
                            continue
                        messages.append({"role": role, "content": content})
                except Exception:
                    pass

            messages.append({"role": "user", "content": user_message})

            # Resolve tenant-specific API key (BYOK)
            from app.gateway.persistence import persistence
            tenant_api_key = persistence.get_setting("openai_api_key", tenant_id=tenant_id)

            response = await self._llm.chat(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=300,
                api_key=tenant_api_key,
            )
            
            if span:
                span.update(output=response)
                
            return response.strip()
            
        except Exception as e:
            logger.wariiang("agent.llm_fallback", agent=self.name, error=str(e))
            if span:
                span.update(status_message=str(e), level="ERROR")
            return None
        finally:
            if span:
                span.end()
            obs.flush()

    def _build_outbound(
        self,
        message: InboundMessage,
        response: AgentResponse,
    ) -> OutboundMessage:
        """Helper: Convert AgentResponse to OutboundMessage."""
        return OutboundMessage(
            message_id=f"resp-{message.message_id}",
            platform=message.platform,
            user_id=message.user_id,
            content=response.content,
            reply_to=message.message_id,
            tenant_id=message.tenant_id,
        )
