"""Tests for LLM Fallback Mechanism (Sprint 7a)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.swarm.llm import LLMClient


class TestLLMFallback:
    @pytest.fixture
    def client(self):
        return LLMClient(openai_api_key="fake-key")

    @pytest.mark.anyio
    async def test_openai_success(self, client):
        """Should use OpenAI by default."""
        with patch.object(client, "_call_openai", new_callable=AsyncMock) as mock_openai:
            mock_openai.return_value = "OpenAI Response"
            
            response = await client.chat([{"role": "user", "content": "hi"}])
            
            assert response == "OpenAI Response"
            assert not client.is_fallback_active
            mock_openai.assert_called_once()

    @pytest.mark.anyio
    async def test_fallback_to_ollama(self, client):
        """Should switch to Ollama if OpenAI fails."""
        with patch.object(client, "_call_openai", new_callable=AsyncMock) as mock_openai, \
             patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
            
            mock_openai.side_effect = Exception("OpenAI Down")
            mock_ollama.return_value = "Ollama Response"
            
            response = await client.chat([{"role": "user", "content": "hi"}])
            
            assert response == "Ollama Response"
            assert client.is_fallback_active
            mock_openai.assert_called_once()
            mock_ollama.assert_called_once()

    @pytest.mark.anyio
    async def test_emergency_response(self, client):
        """Should return emergency message if both fail."""
        with patch.object(client, "_call_openai", new_callable=AsyncMock) as mock_openai, \
             patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
            
            mock_openai.side_effect = Exception("OpenAI Down")
            mock_ollama.side_effect = Exception("Ollama Down")
            
            response = await client.chat([{"role": "user", "content": "hi"}])
            
            assert "technisch eingeschränkt" in response
            assert client.is_fallback_active

    @pytest.mark.anyio
    async def test_reset_fallback(self, client):
        """Should restore OpenAI if it becomes available."""
        # Force fallback state
        client._using_fallback = True
        
        with patch.object(client, "_call_openai", new_callable=AsyncMock) as mock_openai:
            mock_openai.return_value = "pong"
            
            await client.reset_fallback()
            
            assert not client.is_fallback_active
            mock_openai.assert_called_once()
