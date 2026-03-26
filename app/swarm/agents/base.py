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
                    # Kontrollinstanz: annotate any date params with verified weekday
                    date_annotation = self._annotate_dates(params)
                    if date_annotation:
                        content = f"{content}\n{date_annotation}"
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

        Uses the PromptEngine's full 3-tier resolution (DB registry →
        per-tenant filesystem → system default) and injects all template
        variables expected by the standard agent templates.

        Returns:
            Rendered system prompt string.
        """
        try:
            from app.prompts.engine import get_engine
            from datetime import datetime, timezone, timedelta
            from types import SimpleNamespace

            engine = get_engine()
            ctx = task.tenant_context
            settings = ctx.settings or {}
            active = ctx.active_integrations

            # Build German-formatted current date without locale dependency
            _MONTHS_DE = [
                "Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember",
            ]
            _DAYS_DE = [
                "Montag", "Dienstag", "Mittwoch", "Donnerstag",
                "Freitag", "Samstag", "Sonntag",
            ]
            now = datetime.now(timezone.utc)
            weekday_de = _DAYS_DE[now.weekday()]
            current_date = f"{weekday_de}, {now.day}. {_MONTHS_DE[now.month - 1]} {now.year}"
            tomorrow = (now + timedelta(days=1)).date()
            tomorrow_date = tomorrow.isoformat()
            yesterday = (now - timedelta(days=1)).date()
            yesterday_date = yesterday.isoformat()

            # ISO calendar week maps so the LLM never has to calculate dates.
            # "diese Woche" = current ISO week (Mon–Sun), "nächste Woche" = next ISO week.
            monday_this = (now - timedelta(days=now.weekday())).date()
            monday_next = monday_this + timedelta(days=7)
            this_week_dates: dict[str, str] = {
                _DAYS_DE[i]: (monday_this + timedelta(days=i)).isoformat() for i in range(7)
            }
            next_week_dates: dict[str, str] = {
                _DAYS_DE[i]: (monday_next + timedelta(days=i)).isoformat() for i in range(7)
            }
            # Keep upcoming_dates (rolling 7-day window) for backward compat
            upcoming_dates: dict[str, str] = {}
            for _offset in range(7):
                _day = now + timedelta(days=_offset)
                upcoming_dates[_DAYS_DE[_day.weekday()]] = _day.strftime("%Y-%m-%d")

            # Integration flags as a namespace so templates can use
            # `integrations.magicline_enabled` etc.
            integrations = SimpleNamespace(**{
                f"{name}_enabled": (name in active)
                for name in [
                    "magicline", "calendly", "acuity", "calcom",
                    "whatsapp", "telegram", "smtp_email", "sms",
                    "twilio_voice", "shopify", "woocommerce",
                    "hubspot", "salesforce", "stripe", "paypal",
                    "database_crm", "manual_crm", "knowledge", "member_memory",
                ]
            })

            # tenant_slug and tenant_id are explicit params to render_for_tenant;
            # keep them in context too so templates can reference {{ tenant_slug }}.
            context = {
                # Tenant identity (also passed explicitly to render_for_tenant)
                "tenant_slug": ctx.tenant_slug,
                "tenant_id": ctx.tenant_id,
                "plan_slug": ctx.plan_slug,
                "member_id": ctx.member_id,
                "session_id": ctx.session_id,
                "active_integrations": list(active),
                "settings": settings,
                # Computed context
                "current_date": current_date,
                "tomorrow_date": tomorrow_date,
                "yesterday_date": yesterday_date,
                "upcoming_dates": upcoming_dates,
                "this_week_dates": this_week_dates,
                "next_week_dates": next_week_dates,
                "integrations": integrations,
                # Agent identity
                "agent_display_name": getattr(self, "_display_name", self.agent_id),
                # Studio / persona settings
                "studio_name": settings.get("studio_name", ""),
                "studio_short_name": settings.get("studio_short_name", settings.get("studio_name", "")),
                "studio_description": settings.get("studio_description", ""),
                "studio_address": settings.get("studio_address", ""),
                "studio_phone": settings.get("studio_phone", ""),
                "studio_email": settings.get("studio_email", ""),
                "studio_website": settings.get("studio_website", ""),
                "studio_owner_name": settings.get("studio_owner_name", ""),
                "studio_emergency_number": settings.get("studio_emergency_number", "112"),
                "persona_name": settings.get("persona_name", "ARIIA"),
                "persona_bio_text": settings.get("persona_bio_text", ""),
                "soul_content": settings.get("soul_content", ""),
                # Sales / ops content
                "sales_prices_text": settings.get("sales_prices_text", ""),
                "sales_retention_rules": settings.get("sales_retention_rules", ""),
                "sales_complaint_protocol": settings.get("sales_complaint_protocol", ""),
                "booking_instructions": settings.get("booking_instructions", ""),
                "booking_cancellation_policy": settings.get("booking_cancellation_policy", ""),
                "escalation_contact": settings.get("escalation_contact", ""),
                "escalation_triggers": settings.get("escalation_triggers", ""),
                "health_advice_scope": settings.get("health_advice_scope", ""),
                # Member context
                "user_name": ctx.user_name,
                "member_profile": "",
            }

            # Pop keys that are explicit params of render_for_tenant to avoid
            # "multiple values for keyword argument" errors.
            context.pop("tenant_slug", None)
            context.pop("tenant_id", None)

            return engine.render_for_tenant(
                f"{self.agent_id}/system.j2",
                ctx.tenant_slug,
                tenant_id=ctx.tenant_id,
                **context,
            )
        except Exception as e:
            logger.warning(
                "expert_agent.prompt_render_failed",
                agent=self.agent_id,
                error=str(e),
            )

        # Fallback: minimal prompt
        return f"Du bist der {self.agent_id}-Agent. Beantworte die Anfrage des Nutzers."

    @staticmethod
    def _annotate_dates(params: dict) -> str | None:
        """Kontrollinstanz: scan tool params for YYYY-MM-DD dates and return
        a verified weekday annotation so the LLM cannot mislabel the day.

        Example: params={"date": "2026-04-03"}
        Returns: "[Datumscheck: 2026-04-03 = Freitag]"
        """
        import re
        from datetime import date as _date

        _DAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                    "Freitag", "Samstag", "Sonntag"]
        _DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

        found: dict[str, str] = {}
        for val in params.values():
            if not isinstance(val, str):
                continue
            for match in _DATE_RE.findall(val):
                if match in found:
                    continue
                try:
                    d = _date.fromisoformat(match)
                    found[match] = _DAYS_DE[d.weekday()]
                except ValueError:
                    pass

        if not found:
            return None
        parts = [f"{dt} = {wd}" for dt, wd in sorted(found.items())]
        return "[Datumscheck: " + ", ".join(parts) + "]"

    @staticmethod
    def _get_llm():
        """Get the shared LLM client instance."""
        try:
            from app.gateway.dependencies import get_llm_client
            return get_llm_client()
        except Exception:
            return None
