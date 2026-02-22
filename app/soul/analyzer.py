"""ARNI v1.4 – Log Analyzer.

@DATA: Sprint 6b, Task 6b.1
Analyzes recent chat logs to identify trending topics and user sentiment.
Uses LLM for extraction.
"""

from __future__ import annotations

import structlog

from app.memory.repository import SessionRepository
from app.swarm.llm import LLMClient

logger = structlog.get_logger()


class LogAnalyzer:
    """Analyzes conversation history for insights."""

    def __init__(self, repo: SessionRepository, llm: LLMClient) -> None:
        self._repo = repo
        self._llm = llm

    async def analyze_recent_topics(self, limit: int = 50) -> dict[str, Any]:
        """Analyze recent user messages to find top topics.

        Returns:
            Dict with 'topics': list[str], 'summary': str.
        """
        messages = await self._repo.get_recent_global_messages(limit)
        if not messages:
            return {"topics": [], "summary": "No data"}

        # Combine messages for LLM analysis
        # Truncate to avoid context limit (simple resizing)
        text_block = "\n".join(f"- {m}" for m in messages[:50])

        prompt = (
            "Analyze the following user messages from a gym chatbot.\n"
            "Identify the top 3 trending topics or complaints.\n"
            "Output JSON keys: topics (list of strings), summary (brief text).\n\n"
            f"Messages:\n{text_block}"
        )

        try:
            # We use 'system' as role for instructions, but LLMClient expects user prompt
            # We'll just pass the prompt.
            # Note: LLMClient handles text response parsing.
            response = await self._llm.ask(prompt, system_prompt="You are a Data Analyst.")
            
            # Simple heuristic parsing if JSON fails (or if we trust the output)
            # For now return raw response as summary
            logger.info("analyzer.complete", msg_count=len(messages))
            return {
                "raw_analysis": response,
                "sample_size": len(messages)
            }
        except Exception as e:
            logger.error("analyzer.failed", error=str(e))
            return {"error": str(e)}
