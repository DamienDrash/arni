"""ARIIA Swarm v3 — LeadAgent (Supervisor).

The LeadAgent is the single entry point for all user messages.
It orchestrates the full pipeline:

1. Check for pending confirmations (ConfirmationGate)
2. Classify intent (IntentClassifier)
3. Load agent (DynamicAgentLoader)
4. Execute with QA (QAJudge revision loop)
5. Handle confirmation requests

Contains NO domain logic — all behavior comes from the expert agents.
"""

from __future__ import annotations

import uuid
import structlog
from typing import Any

from app.gateway.schemas import InboundMessage
from app.swarm.contracts import (
    AgentResult,
    AgentTask,
    TenantContext,
)

logger = structlog.get_logger()


class LeadAgent:
    """Supervisor agent that orchestrates the swarm pipeline.

    Stateless between requests — all per-tenant state comes from
    TenantContext and Redis.
    """

    def __init__(self, llm=None, redis_client=None):
        """Initialize the LeadAgent.

        Args:
            llm: LLMClient instance for the IntentClassifier.
            redis_client: Async Redis client for ConfirmationGate.
        """
        self._llm = llm
        self._redis = redis_client

    async def handle(
        self,
        message: InboundMessage,
        context: TenantContext,
    ) -> AgentResult:
        """Process a user message through the full swarm pipeline.

        Steps:
        1. Check ConfirmationGate for pending confirmations
        2. Classify intent via IntentClassifier
        3. Load agent via DynamicAgentLoader
        4. Create AgentTask and execute with QA
        5. If result requires confirmation, store in gate

        Args:
            message: Normalized inbound message.
            context: Immutable tenant context.

        Returns:
            AgentResult with the final response.
        """
        logger.info(
            "lead_agent.handle",
            message_id=message.message_id,
            tenant_id=context.tenant_id,
            member_id=context.member_id,
        )

        # Step 1: Check for pending confirmation
        if self._redis:
            try:
                from app.swarm.lead.confirmation_gate import ConfirmationGate
                gate = ConfirmationGate(self._redis)
                pending = await gate.check(context)
                if pending:
                    return await self._resume_from_confirmation(
                        pending, message, context, gate
                    )
            except Exception as e:
                logger.warning("lead_agent.confirmation_check_failed", error=str(e))

        # Step 2: Classify intent
        from app.swarm.lead.intent_classifier import classify

        intent = await classify(
            message=message.content,
            context=context,
            history=self._build_history(message),
            llm=self._llm,
        )

        logger.info(
            "lead_agent.intent_classified",
            agent_id=intent.agent_id,
            confidence=intent.confidence,
        )

        # Step 3: Load agent
        from app.swarm.registry.dynamic_loader import get_agent_loader
        loader = get_agent_loader()
        agent = loader.get_agent(intent.agent_id, context)

        if agent is None:
            logger.warning(
                "lead_agent.agent_not_found",
                agent_id=intent.agent_id,
            )
            # Fallback to persona
            agent = loader.get_agent("persona", context)
            if agent is None:
                return AgentResult(
                    agent_id="lead",
                    content="Es tut mir leid, ich kann gerade nicht antworten. Bitte versuche es später erneut.",
                    confidence=0.2,
                )

        # Step 4: Create AgentTask
        task = AgentTask(
            task_id=uuid.uuid4().hex[:12],
            agent_id=intent.agent_id,
            original_message=message.content,
            intent_payload=dict(intent.extracted) if intent.extracted else {},
            tenant_context=context,
            conversation_history=self._build_history(message),
        )

        # Step 5: Execute with QA
        from app.swarm.qa.profiles import QA_PROFILES, AGENT_QA_PROFILES
        qa_profile_name = AGENT_QA_PROFILES.get(intent.agent_id, "standard")
        qa_profile = QA_PROFILES.get(qa_profile_name, QA_PROFILES["standard"])

        result = await self._execute_with_qa(agent, task, qa_profile)

        # Step 6: Handle confirmation if needed
        if result.requires_confirmation and self._redis:
            try:
                from app.swarm.lead.confirmation_gate import ConfirmationGate
                gate = ConfirmationGate(self._redis)
                token = await gate.store(result, context)
                # Return the confirmation prompt to the user
                return AgentResult(
                    agent_id=result.agent_id,
                    content=result.confirmation_prompt or result.content,
                    confidence=result.confidence,
                    metadata={**result.metadata, "confirmation_token": token},
                )
            except Exception as e:
                logger.error("lead_agent.confirmation_store_failed", error=str(e))

        return result

    async def _execute_with_qa(self, agent, task: AgentTask, qa_profile) -> AgentResult:
        """Execute the agent with QA revision loop.

        If the QAJudge returns REVISE, re-execute with feedback injected
        into the task. If ESCALATE, trigger human handoff.

        Args:
            agent: GenericExpertAgent instance.
            task: The original AgentTask.
            qa_profile: QAProfile with criteria and settings.

        Returns:
            AgentResult that passed QA or escalation result.
        """
        from app.swarm.qa.judge import QAJudge, QAStatus

        judge = QAJudge()
        max_attempts = qa_profile.max_revision_attempts + 1  # +1 for initial attempt
        current_task = task

        for attempt in range(max_attempts):
            result = await agent.execute(current_task)

            # Skip QA if profile has no criteria
            if not qa_profile.criteria:
                return result

            verdict = judge.evaluate(result, current_task, qa_profile)

            if verdict.status == QAStatus.PASS:
                return result

            if verdict.status == QAStatus.ESCALATE:
                logger.warning(
                    "lead_agent.qa_escalate",
                    agent_id=task.agent_id,
                    reason=verdict.reason,
                )
                return AgentResult(
                    agent_id=task.agent_id,
                    content=(
                        "Ich leite dich an einen Mitarbeiter weiter, "
                        "der dir besser helfen kann."
                    ),
                    confidence=0.3,
                    metadata={"escalation_reason": verdict.reason, "needs_handoff": True},
                )

            if verdict.status == QAStatus.REVISE and attempt < max_attempts - 1:
                logger.info(
                    "lead_agent.qa_revise",
                    agent_id=task.agent_id,
                    attempt=attempt + 1,
                    feedback=verdict.feedback,
                )
                # Create a new task with QA feedback injected
                enriched_payload = {
                    **current_task.intent_payload,
                    "qa_feedback": verdict.feedback,
                    "qa_attempt": attempt + 1,
                }
                current_task = AgentTask(
                    task_id=current_task.task_id,
                    agent_id=current_task.agent_id,
                    original_message=current_task.original_message,
                    intent_payload=enriched_payload,
                    tenant_context=current_task.tenant_context,
                    conversation_history=current_task.conversation_history,
                )

        # All revision attempts exhausted — return last result
        logger.warning(
            "lead_agent.qa_exhausted",
            agent_id=task.agent_id,
            attempts=max_attempts,
        )
        return result

    async def _resume_from_confirmation(
        self,
        pending,
        message: InboundMessage,
        context: TenantContext,
        gate,
    ) -> AgentResult:
        """Resume a pending confirmation based on user response.

        Checks if the user's message is affirmative, then resolves
        the confirmation gate accordingly.

        Args:
            pending: PendingConfirmation from the gate.
            message: The user's response message.
            context: TenantContext.
            gate: ConfirmationGate instance.

        Returns:
            AgentResult from the resolved action or cancellation.
        """
        from app.swarm.lead.confirmation_gate import ConfirmationGate

        user_confirmed = ConfirmationGate.is_affirmative(message.content)

        logger.info(
            "lead_agent.confirmation_response",
            token=pending.token,
            confirmed=user_confirmed,
            agent_id=pending.agent_id,
        )

        return await gate.resolve(
            token=pending.token,
            user_confirmed=user_confirmed,
            context=context,
        )

    @staticmethod
    def _build_history(message: InboundMessage) -> tuple[dict[str, str], ...]:
        """Build conversation history from the message's stored history.

        Loads recent chat history from persistence for context.
        """
        try:
            from app.gateway.persistence import persistence
            raw = persistence.get_chat_history(
                str(message.user_id),
                limit=10,
                tenant_id=message.tenant_id,
            )
            return tuple(
                {"role": item.role, "content": item.content}
                for item in raw
                if item.role in {"user", "assistant"}
            )
        except Exception:
            return ()
