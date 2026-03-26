"""ARIIA Swarm v3 — GenericExpertAgent.

DB-configured expert agent that loads its behavior from AgentDefinition.
Uses Jinja2 prompt templates and the tool loop from ExpertAgent ABC.
This is the single implementation that replaces all hardcoded agent classes.
"""

from __future__ import annotations

import structlog
from typing import Any, Sequence

from app.swarm.agents.base import ExpertAgent, MaxTurnsExceeded, ToolExecutionError
from app.swarm.contracts import AgentTask, AgentResult, TenantContext, ToolResult
from app.swarm.tools.base import SkillTool

logger = structlog.get_logger()


class GenericExpertAgent(ExpertAgent):
    """DB-configured expert agent with Jinja2 prompts.

    Created by the DynamicAgentLoader from AgentDefinition rows.
    All domain behavior comes from configuration, not code.
    """

    def __init__(
        self,
        agent_id: str,
        display_name: str,
        system_prompt_template: str,
        tools: Sequence[SkillTool],
        max_turns: int = 5,
        qa_profile: str = "standard",
        llm=None,
    ):
        self._agent_id = agent_id
        self._display_name = display_name
        self._system_prompt_template = system_prompt_template
        self._tools = list(tools)
        self._max_turns = max_turns
        self._qa_profile = qa_profile
        self._llm_override = llm

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute the task using the configured prompt and tools.

        Flow:
        1. Render Jinja2 system prompt with task context
        2. Run tool loop until final answer or max turns
        3. Handle errors with fallbacks

        Args:
            task: AgentTask from the LeadAgent.

        Returns:
            AgentResult with the response.
        """
        logger.info(
            "generic_agent.execute",
            agent_id=self._agent_id,
            task_id=task.task_id,
            tenant_id=task.tenant_context.tenant_id,
        )

        try:
            # Render system prompt
            system_prompt = self._render_prompt_from_template(task)

            # Run tool loop
            result = await self._run_tool_loop(
                task=task,
                tools=self._tools,
                system_prompt=system_prompt,
                max_turns=self._max_turns,
            )

            return result

        except MaxTurnsExceeded:
            logger.warning(
                "generic_agent.max_turns",
                agent_id=self._agent_id,
                task_id=task.task_id,
            )
            return self._escalate_to_knowledge(task)

        except ToolExecutionError as e:
            logger.error(
                "generic_agent.tool_error",
                agent_id=self._agent_id,
                tool=e.tool_name,
                error=e.error,
            )
            return AgentResult(
                agent_id=self._agent_id,
                content="Es gab ein Problem beim Abrufen der Informationen. Bitte versuche es erneut.",
                confidence=0.4,
            )

        except Exception as e:
            logger.error(
                "generic_agent.unexpected_error",
                agent_id=self._agent_id,
                error=str(e),
            )
            return self._trigger_emergency_handoff(task)

    async def execute_confirmed(
        self, action: dict[str, Any], context: TenantContext
    ) -> AgentResult:
        """Re-execute a confirmed one-way-door action.

        The action dict contains the tool name and parameters that
        were stored by the ConfirmationGate.
        """
        tool_name = action.get("tool")
        params = action.get("params", {})

        if not tool_name:
            return AgentResult(
                agent_id=self._agent_id,
                content="Aktion konnte nicht ausgeführt werden: fehlende Tool-Angabe.",
                confidence=0.3,
            )

        # Find the tool
        tool = next((t for t in self._tools if t.name == tool_name), None)
        if not tool:
            return AgentResult(
                agent_id=self._agent_id,
                content=f"Das Tool '{tool_name}' ist nicht mehr verfügbar.",
                confidence=0.3,
            )

        try:
            result: ToolResult = await tool.execute(params, context)
            if result.success:
                return AgentResult(
                    agent_id=self._agent_id,
                    content=f"Erledigt! {result.data}" if result.data else "Die Aktion wurde erfolgreich ausgeführt.",
                    confidence=1.0,
                )
            else:
                return AgentResult(
                    agent_id=self._agent_id,
                    content=result.error_message or "Die Aktion konnte nicht ausgeführt werden.",
                    confidence=0.5,
                )
        except Exception as e:
            logger.error(
                "generic_agent.confirm_error",
                agent_id=self._agent_id,
                tool=tool_name,
                error=str(e),
            )
            return AgentResult(
                agent_id=self._agent_id,
                content="Fehler bei der Ausführung. Bitte versuche es erneut.",
                confidence=0.3,
            )

    def _render_prompt_from_template(self, task: AgentTask) -> str:
        """Render the Jinja2 system prompt template with task context.

        Template variables available:
        - tenant_slug, tenant_id, plan_slug
        - member_id, session_id
        - active_integrations
        - settings (dict with all tenant settings)
        - studio_name, persona_name, sales_prices_text
        - qa_feedback, qa_attempt (for revision loops)
        """
        if not self._system_prompt_template:
            return self._render_prompt(task)

        try:
            from jinja2 import Template
            from datetime import datetime, timezone, timedelta
            from types import SimpleNamespace

            ctx = task.tenant_context
            settings = ctx.settings or {}
            active = ctx.active_integrations

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
            tomorrow_date = (now + timedelta(days=1)).date().isoformat()
            yesterday_date = (now - timedelta(days=1)).date().isoformat()

            # ISO calendar week maps so the LLM never has to calculate dates.
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

            template_vars = {
                "tenant_slug": ctx.tenant_slug,
                "tenant_id": ctx.tenant_id,
                "plan_slug": ctx.plan_slug,
                "member_id": ctx.member_id,
                "session_id": ctx.session_id,
                "active_integrations": list(active),
                "settings": settings,
                "current_date": current_date,
                "tomorrow_date": tomorrow_date,
                "yesterday_date": yesterday_date,
                "upcoming_dates": upcoming_dates,
                "this_week_dates": this_week_dates,
                "next_week_dates": next_week_dates,
                "integrations": integrations,
                "agent_display_name": self._display_name,
                "studio_name": settings.get("studio_name", ""),
                "studio_short_name": settings.get("studio_short_name", settings.get("studio_name", "")),
                "studio_description": settings.get("studio_description", ""),
                "studio_address": settings.get("studio_address", ""),
                "studio_phone": settings.get("studio_phone", ""),
                "studio_email": settings.get("studio_email", ""),
                "studio_website": settings.get("studio_website", ""),
                "studio_emergency_number": settings.get("studio_emergency_number", "112"),
                "persona_name": settings.get("persona_name", "ARIIA"),
                "persona_bio_text": settings.get("persona_bio_text", ""),
                "soul_content": settings.get("soul_content", ""),
                "sales_prices_text": settings.get("sales_prices_text", ""),
                "sales_retention_rules": settings.get("sales_retention_rules", ""),
                "booking_instructions": settings.get("booking_instructions", ""),
                "booking_cancellation_policy": settings.get("booking_cancellation_policy", ""),
                "escalation_contact": settings.get("escalation_contact", ""),
                "health_advice_scope": settings.get("health_advice_scope", ""),
                "user_name": ctx.user_name,
                "member_profile": "",
                # QA revision context (injected by LeadAgent on retry)
                "qa_feedback": task.intent_payload.get("qa_feedback", ""),
                "qa_attempt": task.intent_payload.get("qa_attempt", 0),
            }

            template = Template(self._system_prompt_template)
            return template.render(**template_vars)

        except Exception as e:
            logger.warning(
                "generic_agent.template_render_failed",
                agent_id=self._agent_id,
                error=str(e),
            )
            return self._render_prompt(task)

    def _escalate_to_knowledge(self, task: AgentTask) -> AgentResult:
        """Fallback: return a knowledge-based generic response.

        Called when the tool loop exceeds max turns.
        """
        return AgentResult(
            agent_id=self._agent_id,
            content=(
                "Ich konnte die Informationen gerade nicht vollständig abrufen. "
                "Bitte versuche es in einem Moment erneut oder kontaktiere "
                "das Team direkt."
            ),
            confidence=0.4,
            metadata={"escalation_reason": "max_turns_exceeded"},
        )

    def _trigger_emergency_handoff(self, task: AgentTask) -> AgentResult:
        """Fallback: trigger an emergency handoff to a human.

        Called on unexpected errors.
        """
        return AgentResult(
            agent_id=self._agent_id,
            content=(
                "Es tut mir leid, da ist leider etwas schiefgelaufen. "
                "Ich leite dich an einen Mitarbeiter weiter."
            ),
            confidence=0.2,
            metadata={"escalation_reason": "unexpected_error", "needs_handoff": True},
        )
