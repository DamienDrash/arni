"""ARIIA v2.0 – SupervisorAgent: Intelligent Orchestration Engine.

Replaces the reactive MasterAgent with a proactive planning supervisor
that creates execution plans, delegates to specialists, verifies results,
and handles confidence-based escalation.

Architecture:
    User → SupervisorAgent → [Plan] → SpecialistAgents → [Verify] → OutputPipeline → User
"""
from __future__ import annotations

import json
import time
import structlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.swarm.base import AgentResponse
from app.swarm.llm import LLMClient

logger = structlog.get_logger()


# ─── Execution Plan Data Structures ──────────────────────────────────────────

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_CLARIFICATION = "needs_clarification"


class StepType(str, Enum):
    TOOL_CALL = "tool_call"
    SPECIALIST = "specialist"
    VERIFICATION = "verification"
    CLARIFICATION = "clarification"
    HANDOFF = "handoff"
    SYNTHESIS = "synthesis"


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""
    id: int
    type: StepType
    description: str
    target: str  # tool name, specialist name, or action
    parameters: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    confidence: float = 1.0
    depends_on: list[int] = field(default_factory=list)
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class ExecutionPlan:
    """A dynamic execution plan created by the supervisor."""
    goal: str
    steps: list[ExecutionStep] = field(default_factory=list)
    current_step_index: int = 0
    overall_confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    completed: bool = False
    requires_clarification: bool = False
    clarification_question: Optional[str] = None

    @property
    def pending_steps(self) -> list[ExecutionStep]:
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    @property
    def completed_steps(self) -> list[ExecutionStep]:
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    @property
    def failed_steps(self) -> list[ExecutionStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    def get_next_step(self) -> Optional[ExecutionStep]:
        """Get the next executable step (all dependencies met)."""
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            deps_met = all(
                self.steps[d].status == StepStatus.COMPLETED
                for d in step.depends_on
                if d < len(self.steps)
            )
            if deps_met:
                return step
        return None

    def to_summary(self) -> str:
        """Human-readable plan summary."""
        lines = [f"Ziel: {self.goal}"]
        for s in self.steps:
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
                StepStatus.NEEDS_CLARIFICATION: "❓",
            }.get(s.status, "?")
            lines.append(f"  {status_icon} Schritt {s.id}: {s.description}")
        return "\n".join(lines)


# ─── Planning Prompt ─────────────────────────────────────────────────────────

PLANNING_SYSTEM_PROMPT = """Du bist der Supervisor-Agent von ARIIA, eine intelligente Planungs-Engine.
Deine Aufgabe: Analysiere die Nutzeranfrage und erstelle einen strukturierten Ausführungsplan.

VERFÜGBARE SPEZIALISTEN:
{specialists}

VERFÜGBARE TOOLS:
{tools}

REGELN FÜR DIE PLANUNG:
1. Zerlege komplexe Anfragen in einzelne, sequenzielle Schritte.
2. Jeder Schritt hat einen Typ: "tool_call", "specialist", "verification", "clarification", "handoff", "synthesis".
3. Verwende "verification" für kritische Aktionen (Kündigungen, Buchungen, Änderungen).
4. Verwende "clarification" wenn wichtige Informationen fehlen.
5. Verwende "handoff" wenn du die Anfrage nicht lösen kannst oder der Nutzer einen Menschen möchte.
6. Der letzte Schritt sollte immer "synthesis" sein – die finale Antwort an den Nutzer.
7. Bewerte deine Zuversicht (0.0-1.0) für jeden Schritt.

ANTWORTE NUR mit einem JSON-Objekt in diesem Format:
{
  "goal": "Zusammenfassung des Nutzeranliegens",
  "steps": [
    {
      "id": 0,
      "type": "tool_call|specialist|verification|clarification|handoff|synthesis",
      "description": "Was dieser Schritt tut",
      "target": "tool_name oder specialist_name",
      "parameters": {"key": "value"},
      "depends_on": [],
      "confidence": 0.95
    }
  ]
}"""

SYNTHESIS_SYSTEM_PROMPT = """Du bist der Supervisor-Agent von ARIIA.
Du hast einen Plan ausgeführt und Ergebnisse gesammelt.
Erstelle jetzt eine finale, hilfreiche Antwort für den Nutzer.

KONTEXT:
- Tenant-Persona: {persona}
- Sprache: {language}

AUSGEFÜHRTER PLAN:
{plan_summary}

ERGEBNISSE DER SCHRITTE:
{step_results}

REGELN:
1. Fasse die Ergebnisse zu einer natürlichen, zusammenhängenden Antwort zusammen.
2. Erwähne NICHT den internen Plan oder die Schritte.
3. Sei hilfreich, freundlich und professionell.
4. Wenn Schritte fehlgeschlagen sind, erkläre das dem Nutzer verständlich.
5. Antworte in der Sprache des Nutzers ({language}).
"""

CONFIDENCE_THRESHOLD = 0.6
MAX_PLAN_STEPS = 10
MAX_RETRIES_PER_STEP = 2


class SupervisorAgent:
    """The central intelligence of ARIIA v2.0.

    Unlike the reactive MasterAgent, the SupervisorAgent:
    1. Creates an execution plan BEFORE acting
    2. Delegates to specialists with clear instructions
    3. Verifies critical operations
    4. Evaluates confidence at each step
    5. Escalates to humans when uncertain
    """

    def __init__(
        self,
        llm: LLMClient,
        specialists: Optional[dict[str, Any]] = None,
        tools: Optional[dict[str, Any]] = None,
    ):
        self._llm = llm
        self._specialists = specialists or {}
        self._tools = tools or {}
        self._current_plan: Optional[ExecutionPlan] = None

    @property
    def name(self) -> str:
        return "supervisor"

    # ─── Core Loop ────────────────────────────────────────────────────────

    async def handle(
        self,
        user_message: str,
        tenant_id: int,
        user_id: str,
        chat_history: Optional[list[dict]] = None,
        persona: str = "Professioneller Support-Agent",
        language: str = "de",
        tool_definitions: Optional[list[dict]] = None,
        skill_prompt: str = "",
    ) -> AgentResponse:
        """Main entry point: Plan → Execute → Synthesize → Respond."""
        start_time = time.time()

        logger.info(
            "supervisor.handle_start",
            tenant_id=tenant_id,
            user_id=user_id,
            message_length=len(user_message),
        )

        try:
            # Step 1: Create execution plan
            plan = await self._create_plan(
                user_message=user_message,
                chat_history=chat_history or [],
                tool_definitions=tool_definitions,
                skill_prompt=skill_prompt,
            )
            self._current_plan = plan

            logger.info(
                "supervisor.plan_created",
                goal=plan.goal,
                step_count=len(plan.steps),
                tenant_id=tenant_id,
            )

            # Step 2: Check if clarification needed before execution
            if plan.requires_clarification:
                return AgentResponse(
                    content=plan.clarification_question or "Könnten Sie Ihre Anfrage bitte genauer beschreiben?",
                    confidence=0.5,
                    requires_confirmation=False,
                    metadata={"plan": plan.to_summary(), "action": "clarification"},
                )

            # Step 3: Execute plan step by step
            plan = await self._execute_plan(plan, tenant_id, user_id)

            # Step 4: Check overall confidence
            if plan.overall_confidence < CONFIDENCE_THRESHOLD:
                # Low confidence → ask for clarification instead of guessing
                clarification = await self._generate_clarification(
                    plan, user_message, language
                )
                return AgentResponse(
                    content=clarification,
                    confidence=plan.overall_confidence,
                    requires_confirmation=False,
                    metadata={"plan": plan.to_summary(), "action": "low_confidence"},
                )

            # Step 5: Synthesize final response
            response_text = await self._synthesize_response(
                plan=plan,
                persona=persona,
                language=language,
            )

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "supervisor.handle_complete",
                tenant_id=tenant_id,
                steps_completed=len(plan.completed_steps),
                steps_failed=len(plan.failed_steps),
                confidence=plan.overall_confidence,
                elapsed_ms=round(elapsed_ms, 1),
            )

            # Check if any step requires user confirmation
            needs_confirmation = any(
                s.type == StepType.VERIFICATION and s.status == StepStatus.COMPLETED
                for s in plan.steps
            )

            return AgentResponse(
                content=response_text,
                confidence=plan.overall_confidence,
                requires_confirmation=needs_confirmation,
                metadata={
                    "plan": plan.to_summary(),
                    "steps_completed": len(plan.completed_steps),
                    "steps_failed": len(plan.failed_steps),
                    "elapsed_ms": round(elapsed_ms, 1),
                },
            )

        except Exception as e:
            logger.error(
                "supervisor.handle_error",
                error=str(e),
                tenant_id=tenant_id,
            )
            return AgentResponse(
                content="Es tut mir leid, bei der Bearbeitung Ihrer Anfrage ist ein Fehler aufgetreten. "
                        "Bitte versuchen Sie es erneut oder kontaktieren Sie den Support.",
                confidence=0.0,
                metadata={"error": str(e)},
            )

    # ─── Planning ─────────────────────────────────────────────────────────

    async def _create_plan(
        self,
        user_message: str,
        chat_history: list[dict],
        tool_definitions: Optional[list[dict]] = None,
        skill_prompt: str = "",
    ) -> ExecutionPlan:
        """Use LLM to create a structured execution plan."""
        # Build specialist descriptions
        specialist_desc = "\n".join(
            f"- {name}: {spec.get('description', 'Spezialist')}"
            for name, spec in self._specialists.items()
        ) or "Keine Spezialisten konfiguriert."

        # Build tool descriptions
        tool_desc = ""
        if tool_definitions:
            for td in tool_definitions:
                fn = td.get("function", {})
                tool_desc += f"- {fn.get('name', '?')}: {fn.get('description', '')}\n"
        if not tool_desc:
            tool_desc = "Keine spezifischen Tools konfiguriert."

        system_prompt = PLANNING_SYSTEM_PROMPT.format(
            specialists=specialist_desc,
            tools=tool_desc,
        )
        if skill_prompt:
            system_prompt += f"\n\nSKILL-INFORMATIONEN:\n{skill_prompt}"

        messages = [{"role": "system", "content": system_prompt}]

        # Add recent chat history for context
        for msg in (chat_history or [])[-6:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        messages.append({"role": "user", "content": user_message})

        try:
            response = await self._llm.chat(messages, temperature=0.2, max_tokens=2000)
            plan_data = self._parse_plan_json(response)
            return self._build_plan(plan_data)
        except Exception as e:
            logger.warning("supervisor.plan_creation_failed", error=str(e))
            # Fallback: simple single-step plan
            return ExecutionPlan(
                goal=user_message[:200],
                steps=[
                    ExecutionStep(
                        id=0,
                        type=StepType.SYNTHESIS,
                        description="Direkte Antwort ohne spezifischen Plan",
                        target="direct_response",
                        confidence=0.7,
                    )
                ],
            )

    def _parse_plan_json(self, response: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        text = response.strip()
        # Remove markdown code blocks
        if "```json" in text:
            text = text.split("```json", 1)[1]
            text = text.split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            text = text.split("```", 1)[0]

        return json.loads(text.strip())

    def _build_plan(self, data: dict) -> ExecutionPlan:
        """Build an ExecutionPlan from parsed JSON data."""
        steps = []
        raw_steps = data.get("steps", [])[:MAX_PLAN_STEPS]

        for raw in raw_steps:
            step_type = StepType(raw.get("type", "synthesis"))
            step = ExecutionStep(
                id=raw.get("id", len(steps)),
                type=step_type,
                description=raw.get("description", ""),
                target=raw.get("target", ""),
                parameters=raw.get("parameters", {}),
                depends_on=raw.get("depends_on", []),
                confidence=raw.get("confidence", 0.8),
            )
            steps.append(step)

        plan = ExecutionPlan(
            goal=data.get("goal", "Unbekanntes Ziel"),
            steps=steps,
        )

        # Check if first step is clarification
        if steps and steps[0].type == StepType.CLARIFICATION:
            plan.requires_clarification = True
            plan.clarification_question = steps[0].parameters.get(
                "question", steps[0].description
            )

        return plan

    # ─── Execution ────────────────────────────────────────────────────────

    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        tenant_id: int,
        user_id: str,
    ) -> ExecutionPlan:
        """Execute the plan step by step."""
        max_iterations = len(plan.steps) * (MAX_RETRIES_PER_STEP + 1)
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            step = plan.get_next_step()
            if step is None:
                break

            # Skip synthesis – that's done after execution
            if step.type == StepType.SYNTHESIS:
                step.status = StepStatus.COMPLETED
                continue

            step.status = StepStatus.RUNNING
            step_start = time.time()

            try:
                result = await self._execute_step(step, tenant_id, user_id)
                step.result = result
                step.status = StepStatus.COMPLETED
                step.execution_time_ms = (time.time() - step_start) * 1000

                logger.info(
                    "supervisor.step_completed",
                    step_id=step.id,
                    step_type=step.type.value,
                    target=step.target,
                    confidence=step.confidence,
                    time_ms=round(step.execution_time_ms, 1),
                )

            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                step.execution_time_ms = (time.time() - step_start) * 1000

                logger.warning(
                    "supervisor.step_failed",
                    step_id=step.id,
                    step_type=step.type.value,
                    target=step.target,
                    error=str(e),
                )

                # Mark dependent steps as skipped
                for other in plan.steps:
                    if step.id in other.depends_on and other.status == StepStatus.PENDING:
                        other.status = StepStatus.SKIPPED

        # Calculate overall confidence
        completed = plan.completed_steps
        if completed:
            plan.overall_confidence = sum(s.confidence for s in completed) / len(completed)
        else:
            plan.overall_confidence = 0.0

        plan.completed = True
        return plan

    async def _execute_step(
        self,
        step: ExecutionStep,
        tenant_id: int,
        user_id: str,
    ) -> str:
        """Execute a single step based on its type."""
        if step.type == StepType.TOOL_CALL:
            return await self._execute_tool_call(step, tenant_id)
        elif step.type == StepType.SPECIALIST:
            return await self._execute_specialist(step, tenant_id, user_id)
        elif step.type == StepType.VERIFICATION:
            return await self._execute_verification(step, tenant_id)
        elif step.type == StepType.HANDOFF:
            return await self._execute_handoff(step, tenant_id, user_id)
        elif step.type == StepType.CLARIFICATION:
            return step.parameters.get("question", step.description)
        else:
            return f"Schritt {step.id} abgeschlossen."

    async def _execute_tool_call(self, step: ExecutionStep, tenant_id: int) -> str:
        """Execute a tool call via the adapter registry."""
        tool_name = step.target
        params = step.parameters

        # Try to resolve through adapter registry
        try:
            from app.integrations.adapters.registry import get_adapter_registry
            registry = get_adapter_registry()

            # Map tool name back to capability_id (e.g., crm_customer_search → crm.customer.search)
            capability_id = tool_name.replace("_", ".")

            # Find the right adapter
            for adapter_id in registry.registered_adapters:
                adapter = registry.get_adapter(adapter_id)
                if adapter and capability_id in adapter.supported_capabilities:
                    result = await adapter.execute_capability(
                        capability_id=capability_id,
                        tenant_id=tenant_id,
                        **params,
                    )
                    return result.to_agent_response()

            # Fallback: try the tool from the registered tools dict
            if tool_name in self._tools:
                tool_fn = self._tools[tool_name]
                if callable(tool_fn):
                    import asyncio
                    if asyncio.iscoroutinefunction(tool_fn):
                        result = await tool_fn(**params, tenant_id=tenant_id)
                    else:
                        result = tool_fn(**params, tenant_id=tenant_id)
                    return str(result)

            return f"Tool '{tool_name}' nicht gefunden."

        except Exception as e:
            logger.error("supervisor.tool_call_error", tool=tool_name, error=str(e))
            raise

    async def _execute_specialist(
        self, step: ExecutionStep, tenant_id: int, user_id: str
    ) -> str:
        """Delegate to a specialist agent."""
        specialist_name = step.target
        query = step.parameters.get("query", step.description)

        if specialist_name in self._specialists:
            specialist = self._specialists[specialist_name]
            if hasattr(specialist, "handle"):
                # Build a minimal InboundMessage-like object
                from app.gateway.schemas import InboundMessage, Platform
                msg = InboundMessage(
                    platform=Platform.API,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    message_id=f"supervisor_{step.id}",
                    content=query,
                )
                result = await specialist.handle(msg)
                return result.content
            elif hasattr(specialist, "execute"):
                result = await specialist.execute(query=query, tenant_id=tenant_id)
                return result

        return f"Spezialist '{specialist_name}' nicht verfügbar."

    async def _execute_verification(self, step: ExecutionStep, tenant_id: int) -> str:
        """Run a verification check on a previous step's result."""
        # Find the step to verify
        verify_step_id = step.parameters.get("verify_step", step.id - 1)
        if self._current_plan:
            for s in self._current_plan.steps:
                if s.id == verify_step_id and s.result:
                    # Use LLM to verify
                    checklist = step.parameters.get("checklist", [
                        "Ist die Aktion korrekt?",
                        "Sind alle Daten vollständig?",
                        "Gibt es Sicherheitsbedenken?",
                    ])
                    return await self._verify_with_llm(s.result, checklist)

        return "Verifikation: Kein Ergebnis zum Prüfen gefunden."

    async def _verify_with_llm(self, result: str, checklist: list[str]) -> str:
        """Use LLM to verify a result against a checklist."""
        checklist_text = "\n".join(f"- {item}" for item in checklist)
        messages = [
            {
                "role": "system",
                "content": (
                    "Du bist ein Verifikations-Agent. Prüfe das folgende Ergebnis "
                    "anhand der Checkliste und gib ein Urteil ab.\n\n"
                    f"CHECKLISTE:\n{checklist_text}\n\n"
                    "Antworte mit JSON: {\"passed\": true/false, \"issues\": [\"...\"], \"summary\": \"...\"}"
                ),
            },
            {"role": "user", "content": f"Zu prüfendes Ergebnis:\n{result}"},
        ]
        response = await self._llm.chat(messages, temperature=0.1, max_tokens=500)
        return f"Verifikation: {response}"

    async def _execute_handoff(
        self, step: ExecutionStep, tenant_id: int, user_id: str
    ) -> str:
        """Escalate to human support."""
        reason = step.parameters.get("reason", step.description)
        try:
            from app.agent.runtime.handoff import HandoffManager
            manager = HandoffManager()
            ticket = await manager.create_handoff(
                tenant_id=tenant_id,
                user_id=user_id,
                reason=reason,
                context=step.parameters.get("context", ""),
                priority=step.parameters.get("priority", "normal"),
            )
            return f"Eskalation erstellt: {ticket.get('ticket_id', 'unknown')}"
        except ImportError:
            logger.warning("supervisor.handoff_module_not_available")
            return f"Eskalation angefordert: {reason}"

    # ─── Synthesis ────────────────────────────────────────────────────────

    async def _synthesize_response(
        self,
        plan: ExecutionPlan,
        persona: str = "Professioneller Support-Agent",
        language: str = "de",
    ) -> str:
        """Synthesize a final user-facing response from plan results."""
        step_results = []
        for step in plan.steps:
            if step.status == StepStatus.COMPLETED and step.result:
                step_results.append(
                    f"Schritt {step.id} ({step.description}): {step.result}"
                )
            elif step.status == StepStatus.FAILED:
                step_results.append(
                    f"Schritt {step.id} ({step.description}): FEHLGESCHLAGEN – {step.error}"
                )

        # If only synthesis step and no real results, generate direct response
        if not step_results:
            return await self._generate_direct_response(plan.goal, persona, language)

        messages = [
            {
                "role": "system",
                "content": SYNTHESIS_SYSTEM_PROMPT.format(
                    persona=persona,
                    language=language,
                    plan_summary=plan.to_summary(),
                    step_results="\n".join(step_results),
                ),
            },
            {"role": "user", "content": f"Erstelle die finale Antwort für: {plan.goal}"},
        ]

        response = await self._llm.chat(messages, temperature=0.5, max_tokens=1500)
        return response

    async def _generate_direct_response(
        self, goal: str, persona: str, language: str
    ) -> str:
        """Generate a direct response when no plan steps produced results."""
        messages = [
            {
                "role": "system",
                "content": (
                    f"Du bist {persona}. Antworte hilfreich und freundlich auf {language}. "
                    "Wenn du die Anfrage nicht beantworten kannst, sage das ehrlich."
                ),
            },
            {"role": "user", "content": goal},
        ]
        return await self._llm.chat(messages, temperature=0.5, max_tokens=1000)

    async def _generate_clarification(
        self, plan: ExecutionPlan, user_message: str, language: str
    ) -> str:
        """Generate a clarification question when confidence is low."""
        failed_info = "\n".join(
            f"- {s.description}: {s.error}" for s in plan.failed_steps
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"Du bist ein Support-Agent. Deine Zuversicht bei der Beantwortung ist niedrig.\n"
                    f"Fehlgeschlagene Schritte:\n{failed_info}\n\n"
                    f"Stelle eine präzise Rückfrage an den Nutzer auf {language}, "
                    "um die fehlenden Informationen zu erhalten."
                ),
            },
            {"role": "user", "content": user_message},
        ]
        return await self._llm.chat(messages, temperature=0.3, max_tokens=500)

    # ─── Utilities ────────────────────────────────────────────────────────

    def get_current_plan(self) -> Optional[ExecutionPlan]:
        """Return the current execution plan for debugging/monitoring."""
        return self._current_plan

    def register_specialist(self, name: str, specialist: Any) -> None:
        """Register a specialist agent at runtime."""
        self._specialists[name] = specialist
        logger.info("supervisor.specialist_registered", name=name)

    def register_tool(self, name: str, tool_fn: Any) -> None:
        """Register a tool function at runtime."""
        self._tools[name] = tool_fn
        logger.info("supervisor.tool_registered", name=name)
