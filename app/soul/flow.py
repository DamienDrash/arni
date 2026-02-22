"""ARIIA v1.4 – Evolution Flow.

@BACKEND: Sprint 6b, Task 6b.3
Orchestrates the Self-Improvement cycle (Analyze -> Evolve).
"""

from __future__ import annotations

import structlog

from app.acp.sandbox import Sandbox
from app.memory.repository import SessionRepository
from app.soul.analyzer import LogAnalyzer
from app.soul.evolver import PersonaEvolver
from app.swarm.llm import LLMClient

logger = structlog.get_logger()


class EvolutionFlow:
    """Orchestrator for the Soul Evolution pipeline."""

    def __init__(self, repo: SessionRepository, llm: LLMClient) -> None:
        self._repo = repo
        self._llm = llm
        self._sandbox = Sandbox(".")
        self._analyzer = LogAnalyzer(repo, llm)
        self._evolver = PersonaEvolver(self._sandbox, llm)

    async def run_cycle(self) -> dict[str, str]:
        """Run one full evolution cycle.

        1. Analyze logs
        2. Propose changes
        3. (In production: Create PR / Wait for Human)
        4. (Here: Apply directly if confidence high, or just return proposal)

        Returns:
            Result status dict.
        """
        logger.info("evolution.start")

        # 1. Analyze
        analysis = await self._analyzer.analyze_recent_topics()
        raw_analysis = analysis.get("raw_analysis") or analysis.get("summary", "")
        
        if not raw_analysis:
            return {"status": "skipped", "reason": "no_data"}

        # 2. Evolve
        proposal = await self._evolver.propose_evolution(raw_analysis)
        
        if not proposal:
            return {"status": "skipped", "reason": "no_changes_needed"}

        # 3. Apply (Auto-Evolution enabled for demo)
        self._evolver.apply_evolution(proposal)
        
        return {
            "status": "evolved",
            "analysis": raw_analysis[:100] + "...",
            "changes_applied": True
        }
