"""ARIIA v1.4 – Silent Flush (Intelligent Context Compaction).

@BACKEND: Gold Standard Upgrade
Replaces Regex with LLM extraction to capture semantic meaning and emotional anchors.
"""

import asyncio
import json
import structlog
from app.memory.context import ConversationContext, Turn
from app.memory.knowledge import KnowledgeStore
from app.swarm.llm import LLMClient
from config.settings import get_settings

logger = structlog.get_logger()

FLUSH_PROMPT = """
ANALYSE-MODUS: Silent Flush (Gedächtnis-Extraktion)

Deine Aufgabe:
Extrahiere alle relevanten, langlebigen Fakten aus dem folgenden Chat-Verlauf.
Ignoriere Smalltalk. Fokus auf:
1. Ziele (z.B. Marathon, Abnehmen)
2. Einschränkungen (z.B. Knieprobleme, Zeitmangel)
3. Präferenzen (z.B. mag kein Cardio, trainiert morgens)
4. Motivations-Anker (z.B. "will für Hochzeit fit sein")

FORMAT:
Gib eine JSON-Liste von Strings zurück. Beispiel:
["Ziel: Marathon 2026", "Einschränkung: Linkes Knie schmerzt", "Präferenz: Sauna nach Training"]

CHAT-VERLAUF:
{chat_text}
"""

class SilentFlush:
    """Intelligent context compaction engine using LLM."""

    def __init__(
        self,
        context: ConversationContext,
        knowledge: KnowledgeStore,
    ) -> None:
        self._context = context
        self._knowledge = knowledge
        self._llm = LLMClient(get_settings().openai_api_key)

    async def extract_facts_llm(self, turns: list[Turn]) -> list[str]:
        """Extract facts using GPT-4o-mini."""
        chat_text = "\n".join([f"{t.role}: {t.content}" for t in turns])
        
        try:
            response = await self._llm.chat(
                messages=[{"role": "system", "content": FLUSH_PROMPT.format(chat_text=chat_text)}],
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=500
            )
            
            # Clean up response to ensure valid JSON
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:-3]
            
            facts = json.loads(cleaned)
            if isinstance(facts, list):
                return [str(f) for f in facts if isinstance(f, (str, int, float))]
            return []
            
        except Exception as e:
            logger.warning("flush.llm_extraction_failed", error=str(e))
            return []

    def create_summary(self, turns: list[Turn]) -> str:
        """Create a mechanical summary (fallback/header)."""
        # We keep this simple to save tokens, the real value is in the extracted facts
        user_msgs = [t.content[:50] for t in turns if t.role == "user"]
        return f"Kontext: {len(turns)} Nachrichten. Themen: {'; '.join(user_msgs[:3])}..."

    async def flush_if_needed(self, user_id: str) -> bool:
        """Check and perform flush if context is near limit."""
        if not self._context.is_near_limit(user_id):
            return False

        turns = self._context.get_turns(user_id)
        if not turns:
            return False

        logger.info("flush.started", user_id=user_id, turns=len(turns))

        # 1. Extract facts via LLM (Async)
        facts = await self.extract_facts_llm(turns)
        
        # 2. Store facts
        if facts:
            # We append to the markdown file. 
            # Ideally, we would trigger the full MemberMemoryAnalyzer here, 
            # but append_facts is a safe, fast write operation.
            self._knowledge.append_facts(user_id, facts)
            logger.info("flush.facts_persisted", user_id=user_id, count=len(facts))

        # 3. Compact Context
        summary = self.create_summary(turns)
        self._context.replace_with_summary(user_id, summary, keep_last=5) # Keep a bit more context for flow

        logger.info("flush.completed", user_id=user_id)
        return True
