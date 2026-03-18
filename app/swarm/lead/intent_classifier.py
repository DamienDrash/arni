"""ARIIA Swarm v3 — IntentClassifier.

Single LLM call with OpenAI Structured Output (response_format=JSON)
to classify user intent and route to the correct agent.

No ReAct loop. No tool-calling in the classifier itself.
"""

from __future__ import annotations

import json
import structlog
from typing import Any

from app.swarm.contracts import TenantContext, IntentResult

logger = structlog.get_logger()

# Agents that require specific integrations to be active
AGENT_INTEGRATION_REQUIREMENTS: dict[str, set[str]] = {
    "ops": {"magicline"},
    "sales": {"magicline"},
}

# Emergency keywords that bypass classification entirely
EMERGENCY_KEYWORDS = frozenset({
    "notfall", "unfall", "notruf", "112", "rettung",
    "emergency", "accident", "ambulance",
})

CLASSIFY_SYSTEM_PROMPT = """\
You are an intent classifier for a fitness studio AI assistant.
Your job is to determine which agent should handle the user's message.

Available agents:
{agent_list}

Respond with ONLY a JSON object (no markdown, no explanation):
{{"agent_id": "<agent_id>", "confidence": <0.0-1.0>, "extracted": {{}}}}\

Rules:
- "extracted" may contain key entities from the message (date, time, name, etc.)
- If unsure, set confidence below 0.5 — the system will default to "persona"
- For health/medical/injury questions, always choose "medic"
- For booking/scheduling/cancel/reschedule, choose "ops"
- For membership status, retention, churn, choose "sales"
- For general questions about the studio (hours, prices), choose "knowledge"
- For casual conversation or unclear intent, choose "persona"
"""


def _check_emergency(message: str) -> bool:
    """Check if the message contains emergency keywords."""
    words = set(message.lower().split())
    return bool(words & EMERGENCY_KEYWORDS)


def _build_system_prompt(available_agents: dict[str, str]) -> str:
    """Build the system prompt with only the available agents listed."""
    agent_list = "\n".join(
        f'- "{aid}": {desc}' for aid, desc in available_agents.items()
    )
    return CLASSIFY_SYSTEM_PROMPT.format(agent_list=agent_list)


async def classify(
    message: str,
    context: TenantContext,
    available_agents: dict[str, str],
    history: tuple[dict[str, str], ...] = (),
    llm: Any = None,
) -> IntentResult:
    """Classify user intent and return the target agent.

    Args:
        message: The user's message text.
        context: Tenant context with active integrations and plan info.
        available_agents: Dictionary of agent_id -> description.
        history: Recent conversation history (role/content dicts).
        llm: LLMClient instance. If None, falls back to persona.

    Returns:
        IntentResult with agent_id, confidence, and extracted entities.
    """
    # Emergency bypass — route directly to medic
    if _check_emergency(message):
        logger.info("intent.emergency_bypass", message=message[:50])
        return IntentResult(agent_id="medic", confidence=1.0, extracted={"emergency": True})

    if not available_agents:
        logger.warning("intent.no_agents_available", tenant_id=context.tenant_id)
        return IntentResult(agent_id="persona", confidence=0.5)

    if not llm:
        logger.warning("intent.no_llm", fallback="persona")
        return IntentResult(agent_id="persona", confidence=0.5)

    # Build messages for the LLM
    system_prompt = _build_system_prompt(available_agents)
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    # Include recent history for context
    for h in history[-5:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    messages.append({"role": "user", "content": message})

    try:
        response = await llm.chat(
            messages=messages,
            tenant_id=context.tenant_id,
            agent_name="intent_classifier",
            temperature=0.1,
            max_tokens=200,
        )

        if not response:
            return IntentResult(agent_id="persona", confidence=0.3)

        # Parse JSON response
        cleaned = response.strip()
        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        result = json.loads(cleaned)
        agent_id = str(result.get("agent_id", "persona"))
        confidence = float(result.get("confidence", 0.0))
        extracted = result.get("extracted", {})

        # Validate agent_id is in available agents
        if agent_id not in available_agents:
            logger.warning("intent.invalid_agent", agent_id=agent_id, available=list(available_agents))
            agent_id = "persona"
            confidence = 0.3

        # Low confidence fallback
        if confidence < 0.5:
            logger.info("intent.low_confidence", agent_id=agent_id, confidence=confidence)
            agent_id = "persona"

        return IntentResult(
            agent_id=agent_id,
            confidence=confidence,
            extracted=extracted if isinstance(extracted, dict) else {},
        )

    except json.JSONDecodeError as e:
        logger.warning("intent.json_parse_failed", error=str(e), response=response[:200] if response else "")
        return IntentResult(agent_id="persona", confidence=0.3)
    except Exception as e:
        logger.error("intent.classify_failed", error=str(e))
        return IntentResult(agent_id="persona", confidence=0.3)
