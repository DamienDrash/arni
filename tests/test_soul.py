"""Tests for Soul Evolution (Sprint 6b)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.soul.analyzer import LogAnalyzer
from app.soul.evolver import PersonaEvolver
from app.soul.flow import EvolutionFlow


class TestLogAnalyzer:
    @pytest.mark.anyio
    async def test_analyze_empty(self):
        repo = MagicMock()
        repo.get_recent_global_messages = AsyncMock(return_value=[])
        llm = MagicMock()
        
        analyzer = LogAnalyzer(repo, llm)
        result = await analyzer.analyze_recent_topics()
        assert result["summary"] == "No data"

    @pytest.mark.anyio
    async def test_analyze_calls_llm(self):
        repo = MagicMock()
        repo.get_recent_global_messages = AsyncMock(return_value=["help", "pricing"])
        llm = MagicMock()
        llm.ask = AsyncMock(return_value='{"topics": ["price"], "summary": "Users ask price"}')
        
        analyzer = LogAnalyzer(repo, llm)
        result = await analyzer.analyze_recent_topics()
        assert "raw_analysis" in result
        llm.ask.assert_called_once()


class TestPersonaEvolver:
    @pytest.mark.anyio
    async def test_propose_evolution(self):
        sandbox = MagicMock()
        sandbox.read_file.return_value = "Old Soul Content Is Very Long And Detailed To Pass The Check"
        llm = MagicMock()
        # Must be different and > 50 chars
        new_content = "New Soul Content Is Also Very Long And Detailed To Pass The Check And Be Different"
        llm.ask = AsyncMock(return_value=new_content)
        
        evolver = PersonaEvolver(sandbox, llm)
        proposal = await evolver.propose_evolution("Analysis")
        
        assert proposal == new_content
        sandbox.read_file.assert_called_with("docs/personas/SOUL.md")

    def test_apply_evolution(self):
        sandbox = MagicMock()
        llm = MagicMock()
        
        evolver = PersonaEvolver(sandbox, llm)
        evolver.apply_evolution("New Content")
        
        sandbox.write_file.assert_called_with("docs/personas/SOUL.md", "New Content")


class TestEvolutionFlow:
    @pytest.mark.anyio
    async def test_run_cycle_skipped_if_no_data(self):
        repo = MagicMock()
        repo.get_recent_global_messages = AsyncMock(return_value=[]) # causes analyzer to return "No data"
        llm = MagicMock()
        
        flow = EvolutionFlow(repo, llm)
        flow._sandbox = MagicMock() # Mock the internal sandbox
        
        result = await flow.run_cycle()
        assert result["status"] == "skipped"

    @pytest.mark.anyio
    async def test_run_cycle_full(self):
        # Mock dependencies
        repo = MagicMock()
        repo.get_recent_global_messages = AsyncMock(return_value=["msg1"])
        
        llm = MagicMock()
        # First call (Analyzer), Second call (Evolver)
        new_soul = "New Soul Content Is Very Long And Detailed To Pass The Logic Check > 50 chars"
        llm.ask = AsyncMock(side_effect=["Analysis Result", new_soul])
        
        flow = EvolutionFlow(repo, llm)
        
        # Mock sandbox methods used by Evolver
        mock_sandbox = MagicMock()
        mock_sandbox.read_file.return_value = "Old Soul Content Is Very Long And Detailed To Pass The Check"
        flow._sandbox = mock_sandbox
        # We need to ensure the evolver instance inside flow uses this sandbox
        # Since EvolutionFlow instantiates Evolver internally, we must patch it or use the one it created.
        flow._evolver._sandbox = mock_sandbox
        flow._evolver._llm = llm # Ensure it uses our mock LLM
        
        result = await flow.run_cycle()
        
        assert result["status"] == "evolved"
        mock_sandbox.write_file.assert_called_once()
