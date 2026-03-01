"""ARIIA v2.0 – SpecialistAgent Base Class.

A specialist is a focused agent with a specific system prompt and
domain expertise. Unlike the old hardcoded agents, specialists are
configurable profiles that the SupervisorAgent loads on demand.

Architecture:
    SupervisorAgent → loads SpecialistProfile → creates SpecialistAgent → delegates task
"""
from __future__ import annotations

import structlog
from dataclasses import dataclass, field
from typing import Any, Optional

from app.swarm.base import AgentResponse
from app.swarm.llm import LLMClient

logger = structlog.get_logger()


@dataclass
class SpecialistProfile:
    """Configuration profile for a specialist agent.

    Profiles are loaded from the database (TenantConfig) or from
    default configurations. They define the specialist's identity,
    capabilities, and behavioral constraints.
    """
    name: str
    display_name: str
    description: str
    system_prompt: str
    domain: str  # e.g., "booking", "sales", "health", "general"
    capabilities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    requires_confirmation_for: list[str] = field(default_factory=list)
    max_turns: int = 5
    temperature: float = 0.4
    model_override: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "domain": self.domain,
            "capabilities": self.capabilities,
            "constraints": self.constraints,
        }


class SpecialistAgent:
    """A specialist agent that executes tasks within its domain.

    The specialist receives a focused query from the supervisor,
    processes it using its domain-specific system prompt, and
    returns a structured response.
    """

    def __init__(self, profile: SpecialistProfile, llm: LLMClient):
        self._profile = profile
        self._llm = llm

    @property
    def name(self) -> str:
        return self._profile.name

    @property
    def description(self) -> str:
        return self._profile.description

    @property
    def domain(self) -> str:
        return self._profile.domain

    @property
    def profile(self) -> SpecialistProfile:
        return self._profile

    async def execute(
        self,
        query: str,
        tenant_id: int,
        context: Optional[dict[str, Any]] = None,
        chat_history: Optional[list[dict]] = None,
        available_tools: Optional[list[dict]] = None,
    ) -> AgentResponse:
        """Execute a specialist task.

        Args:
            query: The focused question/task from the supervisor
            tenant_id: Current tenant ID
            context: Additional context (member data, previous results, etc.)
            chat_history: Recent conversation history
            available_tools: OpenAI-format tool definitions available to this specialist
        """
        logger.info(
            "specialist.execute",
            name=self.name,
            tenant_id=tenant_id,
            query_length=len(query),
        )

        # Build messages
        messages = self._build_messages(query, context, chat_history)

        try:
            # Use tool calling if tools are available
            if available_tools:
                response = await self._execute_with_tools(
                    messages, available_tools, tenant_id
                )
            else:
                response = await self._llm.chat(
                    messages,
                    temperature=self._profile.temperature,
                    max_tokens=1500,
                )

            # Check if action requires confirmation
            needs_confirmation = self._check_confirmation_required(query)

            return AgentResponse(
                content=response,
                confidence=0.85,
                requires_confirmation=needs_confirmation,
                metadata={
                    "specialist": self.name,
                    "domain": self.domain,
                },
            )

        except Exception as e:
            logger.error(
                "specialist.execute_error",
                name=self.name,
                error=str(e),
            )
            return AgentResponse(
                content=f"Fehler im Spezialisten '{self._profile.display_name}': {str(e)}",
                confidence=0.0,
                metadata={"specialist": self.name, "error": str(e)},
            )

    def _build_messages(
        self,
        query: str,
        context: Optional[dict[str, Any]] = None,
        chat_history: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build the message array for the LLM call."""
        system_prompt = self._profile.system_prompt

        # Inject context if available
        if context:
            context_text = "\n".join(
                f"- {k}: {v}" for k, v in context.items() if v
            )
            system_prompt += f"\n\nAKTUELLER KONTEXT:\n{context_text}"

        # Add constraints
        if self._profile.constraints:
            constraints_text = "\n".join(
                f"- {c}" for c in self._profile.constraints
            )
            system_prompt += f"\n\nEINSCHRÄNKUNGEN:\n{constraints_text}"

        messages = [{"role": "system", "content": system_prompt}]

        # Add chat history
        if chat_history:
            for msg in chat_history[-4:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        messages.append({"role": "user", "content": query})
        return messages

    async def _execute_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tenant_id: int,
    ) -> str:
        """Execute with tool calling support."""
        # Filter tools to only those relevant to this specialist's capabilities
        relevant_tools = tools
        if self._profile.capabilities:
            relevant_tools = [
                t for t in tools
                if t.get("function", {}).get("name", "") in self._profile.capabilities
            ]
            if not relevant_tools:
                relevant_tools = tools  # Fallback to all if no match

        response = await self._llm.chat_with_tools(
            messages=messages,
            tools=relevant_tools,
            temperature=self._profile.temperature,
            max_tokens=1500,
        )

        # If tool calls were made, execute them
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_results = []
            for tc in response.tool_calls:
                try:
                    from app.integrations.adapters.registry import get_adapter_registry
                    registry = get_adapter_registry()
                    cap_id = tc.function.name.replace("_", ".")
                    args = tc.function.arguments
                    if isinstance(args, str):
                        import json
                        args = json.loads(args)

                    for adapter_id in registry.registered_adapters:
                        adapter = registry.get_adapter(adapter_id)
                        if adapter and cap_id in adapter.supported_capabilities:
                            result = await adapter.execute_capability(
                                cap_id, tenant_id=tenant_id, **args
                            )
                            tool_results.append(result.to_agent_response())
                            break
                    else:
                        tool_results.append(f"Tool {tc.function.name} nicht gefunden.")
                except Exception as e:
                    tool_results.append(f"Fehler: {str(e)}")

            # Second LLM call with tool results
            messages.append({"role": "assistant", "content": str(response)})
            messages.append({
                "role": "user",
                "content": "Tool-Ergebnisse:\n" + "\n".join(tool_results),
            })
            return await self._llm.chat(
                messages, temperature=self._profile.temperature
            )

        return str(response)

    def _check_confirmation_required(self, query: str) -> bool:
        """Check if the query involves an action that requires confirmation."""
        if not self._profile.requires_confirmation_for:
            return False
        query_lower = query.lower()
        return any(
            keyword.lower() in query_lower
            for keyword in self._profile.requires_confirmation_for
        )
