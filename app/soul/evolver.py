"""ARIIA v1.4 – Persona Evolver.

@BACKEND: Sprint 6b, Task 6b.2
Proposes updates to SOUL.md based on analysis results.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from app.acp.sandbox import Sandbox
from app.swarm.llm import LLMClient

logger = structlog.get_logger()


class PersonaEvolver:
    """Updates SOUL.md based on feedback/analysis."""

    def __init__(self, sandbox: Sandbox, llm: LLMClient) -> None:
        self._sandbox = sandbox
        self._llm = llm
        self._soul_path = "docs/personas/SOUL.md"

    async def propose_evolution(self, analysis_result: str) -> str | None:
        """Generate a new version of SOUL.md based on analysis.

        Args:
            analysis_result: Text summary of user needs/topics.

        Returns:
            New content for SOUL.md (or None if no change needed).
        """
        try:
            current_soul = self._sandbox.read_file(self._soul_path)
        except Exception:
            logger.warning("evolver.soul_not_found")
            return None

        prompt = (
            "You are a Persona Designer. Update the following persona definition based on the user feedback.\n"
            "Maintain the core 'Ariia' character (Arnold Schwarzenegger style).\n"
            "Only add/modify sections if clearly needed by the feedback.\n\n"
            f"User Feedback Analysis:\n{analysis_result}\n\n"
            f"Current SOUL.md:\n{current_soul}\n\n"
            "Output ONLY the new full SOUL.md content."
        )

        try:
            new_soul = await self._llm.ask(prompt, system_prompt="You are an expert Persona Designer.")
            
            if new_soul and len(new_soul) > 50 and new_soul != current_soul:
                return new_soul
            return None

        except Exception as e:
            logger.error("evolver.failed", error=str(e))
            return None

    def apply_evolution(self, new_content: str) -> None:
        """Apply the calculated evolution to SOUL.md."""
        self._sandbox.write_file(self._soul_path, new_content)
        logger.info("evolver.applied", path=self._soul_path)
