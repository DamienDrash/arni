"""ARIIA Swarm v3 — ExpertAgent Abstract Base Class.

All domain agents (ops, sales, medic, etc.) inherit from ExpertAgent.
The LeadAgent dispatches AgentTask objects; experts return AgentResult.

Key design decisions:
- ExpertAgent contains NO domain logic (no booking code, no sales code)
- Tool loop with loop-detection and max-turns guard
- Jinja2 prompt rendering per agent
- execute_confirmed() for ConfirmationGate re-dispatch
"""

from __future__ import annotations

import json
import structlog
from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.swarm.contracts import AgentTask, AgentResult, TenantContext, ToolResult
from app.swarm.tools.base import SkillTool

logger = structlog.get_logger()


class MaxTurnsExceeded(Exception):
    """Raised when the tool loop exceeds max_turns."""

    def __init__(self, agent_id: str, turns: int):
        self.agent_id = agent_id
        self.turns = turns
        super().__init__(f"Agent {agent_id} exceeded max turns ({turns})")


class ToolExecutionError(Exception):
    """Raised when a tool fails during execution."""

    def __init__(self, tool_name: str, error: str):
        self.tool_name = tool_name
        self.error = error
        super().__init__(f"Tool {tool_name} failed: {error}")


class ExpertAgent(ABC):
    """Abstract base for all domain expert agents in Swarm v3.

    Subclasses must define:
      - agent_id: unique identifier matching AgentDefinition.id
      - execute(): handle an AgentTask and return an AgentResult
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique agent identifier (must match AgentDefinition.id)."""
        ...

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute the task and return a result.

        Args:
            task: Immutable task from the LeadAgent with message, intent,
                  tenant context, and conversation history.

        Returns:
            AgentResult with content, confidence, and optional confirmation.
        """
        ...

    async def execute_confirmed(
        self, action: dict[str, Any], context: TenantContext
    ) -> AgentResult:
        """Re-execute after user confirms a one-way-door action.

        Called by the ConfirmationGate when the user approves.
        Default implementation returns a not-implemented message;
        agents with confirmable actions should override this.

        Args:
            action: The action dict stored during the original confirmation request.
            context: The tenant context for scoped execution.
        """
        return AgentResult(
            agent_id=self.agent_id,
            content="Diese Aktion unterstützt keine Bestätigung.",
            confidence=0.5,
        )

    async def _run_tool_loop(
        self,
        task: AgentTask,
        tools: Sequence[SkillTool],
        system_prompt: str,
        max_turns: int = 5,
    ) -> AgentResult:
        """Run an LLM tool-calling loop with loop detection.

        This is the standard ReAct pattern:
        1. Send system prompt + user message + tools to LLM
        2. If LLM returns tool_calls -> execute them
        3. Feed results back and repeat
        4. Stop when LLM returns a final text response or max_turns reached

        Loop detection: if the same tool call (name + args) appears twice,
        break out and ask the LLM for a final answer.

        Args:
            task: The agent task with message and context.
            tools: Available SkillTool instances for this execution.
            system_prompt: Rendered system prompt.
            max_turns: Maximum tool-calling iterations.

        Returns:
            AgentResult with the final response.

        Raises:
            MaxTurnsExceeded: If the loop hits max_turns without resolution.
        """
        from app.swarm.llm import LLMClient

        # Build tool schemas for LLM
        tool_schemas = [t.to_openai_schema() for t in tools]
        tool_map = {t.name: t for t in tools}

        # Build message history
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        for msg in task.conversation_history:
            messages.append(dict(msg))
        messages.append({"role": "user", "content": task.original_message})

        seen_calls: set[str] = set()

        for turn in range(max_turns):
            # Get LLM client from the gateway
            llm = self._get_llm()
            if not llm:
                return AgentResult(
                    agent_id=self.agent_id,
                    content="LLM-Client nicht verfügbar.",
                    confidence=0.0,
                )

            response = await llm.chat_with_tools(
                messages=messages,
                tools=tool_schemas,
                tenant_id=task.tenant_context.tenant_id,
                agent_name=self.agent_id,
                temperature=0.3,
                max_tokens=1500,
            )

            if not response.success:
                logger.error(
                    "expert_agent.llm_error",
                    agent=self.agent_id,
                    error=response.error,
                    turn=turn + 1,
                )
                return AgentResult(
                    agent_id=self.agent_id,
                    content="Es gab ein technisches Problem. Bitte versuche es gleich nochmal!",
                    confidence=0.3,
                )

            # No tool calls -> final answer
            if not response.has_tool_calls:
                content = (response.content or "").strip()
                if not content:
                    content = "Ich konnte keine passende Antwort finden."
                return AgentResult(
                    agent_id=self.agent_id,
                    content=content,
                    confidence=0.9,
                )

            # Process tool calls
            messages.append(response.assistant_message)

            for tc_raw in response.tool_calls:
                tc_name = tc_raw.get("function", {}).get("name", "")
                tc_args_str = tc_raw.get("function", {}).get("arguments", "{}")
                tc_id = tc_raw.get("id", "")

                # Loop detection
                call_fingerprint = f"{tc_name}:{tc_args_str}"
                if call_fingerprint in seen_calls:
                    logger.warning(
                        "expert_agent.loop_detected",
                        agent=self.agent_id,
                        tool=tc_name,
                        turn=turn + 1,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": "Du wiederholst dich. Nutze die bereits erhaltenen Daten für eine finale Antwort.",
                    })
                    continue
                seen_calls.add(call_fingerprint)

                # Execute tool
                tool = tool_map.get(tc_name)
                if not tool:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"Tool '{tc_name}' nicht verfügbar.",
                    })
                    continue

                try:
                    params = json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
                    result: ToolResult = await tool.execute(params, task.tenant_context)
                    content = json.dumps(result.data) if result.success else (result.error_message or "Tool-Fehler")
                except Exception as e:
                    logger.error(
                        "expert_agent.tool_error",
                        agent=self.agent_id,
                        tool=tc_name,
                        error=str(e),
                    )
                    content = f"Tool-Fehler: {str(e)}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": str(content),
                })

        # Max turns exceeded
        raise MaxTurnsExceeded(self.agent_id, max_turns)

    def _render_prompt(self, task: AgentTask) -> str:
        """Render the Jinja2 system prompt for this agent.

        Looks up the agent's prompt template and renders it with
        the task's tenant context and metadata.

        Returns:
            Rendered system prompt string.
        """
        try:
            from app.prompts.engine import get_engine
            engine = get_engine()

            # Try tenant-specific prompt first
            tenant_slug = task.tenant_context.tenant_slug
            tenant_template = f"tenants/{tenant_slug}/{self.agent_id}-system.j2"
            default_template = f"{self.agent_id}/system.j2"

            context = {
                "tenant_slug": tenant_slug,
                "tenant_id": task.tenant_context.tenant_id,
                "plan_slug": task.tenant_context.plan_slug,
                "active_integrations": list(task.tenant_context.active_integrations),
                "member_id": task.tenant_context.member_id,
                "session_id": task.tenant_context.session_id,
                "settings": task.tenant_context.settings,
            }

            try:
                return engine.render(tenant_template, **context)
            except Exception:
                pass

            try:
                return engine.render(default_template, **context)
            except Exception:
                pass
        except Exception as e:
            logger.warning(
                "expert_agent.prompt_render_failed",
                agent=self.agent_id,
                error=str(e),
            )

        # Fallback: minimal prompt
        return f"Du bist der {self.agent_id}-Agent. Beantworte die Anfrage des Nutzers."

    @staticmethod
    def _get_llm():
        """Get the shared LLM client instance."""
        try:
            from app.gateway.dependencies import get_llm_client
            return get_llm_client()
        except Exception:
            return None
