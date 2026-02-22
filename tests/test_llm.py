"""ARNI v1.4 – LLM Client Tests.

@QA: Fixing F2 – llm.py coverage from 51% to ≥80%
Tests: OpenAI calls, Ollama fallback, emergency response, reset_fallback.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.swarm.llm import LLMClient


MOCK_OPENAI_RESPONSE = {
    "choices": [{"message": {"content": "booking|0.95"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}

MOCK_OLLAMA_RESPONSE = {
    "message": {"content": "booking|0.9"},
}


class TestLLMOpenAI:
    """Tests for OpenAI API path."""

    @pytest.mark.anyio
    async def test_openai_call_success(self) -> None:
        """Successful OpenAI call returns content."""
        llm = LLMClient(openai_api_key="test-key-123")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = MOCK_OPENAI_RESPONSE

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await llm.chat(
                [{"role": "user", "content": "test"}],
                model="gpt-4o-mini",
            )
            assert result == "booking|0.95"
            assert not llm.is_fallback_active

    @pytest.mark.anyio
    async def test_openai_failure_switches_to_fallback(self) -> None:
        """Failed OpenAI call should switch to Ollama fallback."""
        llm = LLMClient(openai_api_key="test-key-123")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Both OpenAI and Ollama fail → emergency response
            result = await llm.chat([{"role": "user", "content": "test"}])
            assert llm.is_fallback_active
            assert "technisch eingeschränkt" in result


class TestLLMOllama:
    """Tests for Ollama fallback path."""

    @pytest.mark.anyio
    async def test_ollama_call_success(self) -> None:
        """Direct Ollama call (no API key) returns content."""
        llm = LLMClient(openai_api_key="")  # No OpenAI key

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = MOCK_OLLAMA_RESPONSE

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await llm.chat([{"role": "user", "content": "test"}])
            assert result == "booking|0.9"

    @pytest.mark.anyio
    async def test_ollama_failure_returns_emergency(self) -> None:
        """When both providers fail, emergency response is returned."""
        llm = LLMClient(openai_api_key="")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await llm.chat([{"role": "user", "content": "test"}])
            assert "technisch eingeschränkt" in result


class TestLLMFallbackReset:
    """Tests for reset_fallback mechanism."""

    @pytest.mark.anyio
    async def test_reset_fallback_restores_openai(self) -> None:
        """Successful reset should switch back to OpenAI."""
        llm = LLMClient(openai_api_key="test-key")
        llm._using_fallback = True
        assert llm.is_fallback_active

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = MOCK_OPENAI_RESPONSE

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await llm.reset_fallback()
            assert not llm.is_fallback_active

    @pytest.mark.anyio
    async def test_reset_fallback_stays_on_failure(self) -> None:
        """Failed reset should stay on Ollama fallback."""
        llm = LLMClient(openai_api_key="test-key")
        llm._using_fallback = True

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("still down"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await llm.reset_fallback()
            assert llm.is_fallback_active

    @pytest.mark.anyio
    async def test_reset_fallback_skips_without_key(self) -> None:
        """Reset should do nothing if no API key is set."""
        llm = LLMClient(openai_api_key="")
        llm._using_fallback = True
        await llm.reset_fallback()
        assert llm.is_fallback_active  # Still on fallback, no key to try

    @pytest.mark.anyio
    async def test_reset_fallback_skips_when_not_in_fallback(self) -> None:
        """Reset should do nothing if already on primary."""
        llm = LLMClient(openai_api_key="test-key")
        assert not llm.is_fallback_active
        await llm.reset_fallback()
        assert not llm.is_fallback_active


class TestLLMConfiguration:
    """Tests for LLM client configuration."""

    def test_default_config(self) -> None:
        llm = LLMClient()
        assert llm._openai_api_key == ""
        assert llm._ollama_base_url == "http://127.0.0.1:11434"
        assert llm._ollama_model == "llama3"
        assert not llm.is_fallback_active

    def test_custom_config(self) -> None:
        llm = LLMClient(
            openai_api_key="sk-test",
            ollama_base_url="http://custom:11434",
            ollama_model="mistral",
        )
        assert llm._openai_api_key == "sk-test"
        assert llm._ollama_base_url == "http://custom:11434"
        assert llm._ollama_model == "mistral"
