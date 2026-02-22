"""ARNI v1.4 – Silent Flush (Context Compaction).

@BACKEND: Sprint 4, Task 4.4
Extracts facts from conversation context when nearing capacity.
"""

import re

import structlog

from app.memory.context import ConversationContext, Turn
from app.memory.knowledge import KnowledgeStore

logger = structlog.get_logger()

# Patterns that indicate extractable facts
FACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:ich habe|ich hab|mein)\s+(.+?)(?:verletzt|schmerz|problem)", re.IGNORECASE),
    re.compile(r"(?:ich bin|name ist|heiße)\s+(\w+)", re.IGNORECASE),
    re.compile(r"(?:trainiere|training)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:allergi|unverträglich)\w*\s+(?:gegen\s+)?(.+?)(?:\.|,|$)", re.IGNORECASE),
    re.compile(r"(?:ziel|goal|möchte)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:termin|buche|buchung)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:mitglied(?:schaft)?|abo|vertrag)\s+(.+?)(?:\.|$)", re.IGNORECASE),
]


class SilentFlush:
    """Context compaction engine.

    When context nears capacity (>80%):
    1. Extract facts from user messages
    2. Store facts in KnowledgeStore
    3. Replace context with summary + last 3 turns
    """

    def __init__(
        self,
        context: ConversationContext,
        knowledge: KnowledgeStore,
    ) -> None:
        self._context = context
        self._knowledge = knowledge

    def extract_facts(self, turns: list[Turn]) -> list[str]:
        """Extract factual statements from conversation turns.

        Args:
            turns: List of conversation turns.

        Returns:
            List of extracted fact strings.
        """
        facts: list[str] = []

        for turn in turns:
            if turn.role != "user":
                continue

            content = turn.content.strip()

            # Pattern-based extraction
            for pattern in FACT_PATTERNS:
                matches = pattern.findall(content)
                for match in matches:
                    fact = match.strip()
                    if len(fact) > 3 and fact not in facts:
                        facts.append(fact)

            # Long messages likely contain useful info
            if len(content) > 50 and not content.startswith("["):
                # Store first sentence as a fact
                first_sentence = content.split(".")[0].strip()
                if first_sentence and first_sentence not in facts:
                    facts.append(first_sentence)

        return facts

    def create_summary(self, turns: list[Turn]) -> str:
        """Create a brief summary of the conversation for context preservation.

        Args:
            turns: Full conversation turns.

        Returns:
            Summary string.
        """
        topics: list[str] = []
        for turn in turns:
            if turn.role == "user" and len(turn.content) > 10:
                # Extract first meaningful phrase
                phrase = turn.content.split(".")[0][:80].strip()
                if phrase and phrase not in topics:
                    topics.append(phrase)

        if not topics:
            return "Konversation ohne spezifische Themen."

        topic_str = "; ".join(topics[:5])
        return f"Bisherige Themen: {topic_str}"

    async def flush_if_needed(self, user_id: str) -> bool:
        """Check and perform flush if context is near limit.

        Args:
            user_id: User identifier.

        Returns:
            True if flush was performed.
        """
        if not self._context.is_near_limit(user_id):
            return False

        turns = self._context.get_turns(user_id)
        if not turns:
            return False

        # Extract facts
        facts = self.extract_facts(turns)
        if facts:
            self._knowledge.append_facts(user_id, facts)
            logger.info("flush.facts_extracted", user_id=user_id, count=len(facts))

        # Create summary and compact context
        summary = self.create_summary(turns)
        self._context.replace_with_summary(user_id, summary, keep_last=3)

        logger.info("flush.completed", user_id=user_id, facts=len(facts))
        return True
