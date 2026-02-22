"""Unit tests for Voice Ingress Pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.voice.pipeline import process_voice_message
from app.integrations.telegram import TelegramBot

@pytest.mark.asyncio
async def test_process_voice_message_success():
    # Mock Telegram Bot
    bot = AsyncMock(spec=TelegramBot)
    bot.get_file.return_value = {"file_path": "voice/test.ogg"}
    bot.download_file.return_value = b"fake_audio_content"

    # Mock STT Service — transcribe returns (text, language) tuple
    with patch("app.voice.pipeline.get_stt") as mock_get_stt:
        mock_stt_instance = MagicMock()
        mock_stt_instance.transcribe.return_value = ("Hello World", "de")
        mock_get_stt.return_value = mock_stt_instance

        # Mock file operations to avoid actual I/O
        with patch("builtins.open", new_callable=MagicMock):
            with patch("os.remove") as mock_remove:
                with patch("os.path.exists", return_value=True):

                    # Execute — returns dict {"text": ..., "language": ...}
                    result = await process_voice_message("file_123", bot)

                    # Verify
                    assert result["text"] == "Hello World"
                    assert result["language"] == "de"
                    bot.get_file.assert_called_once_with("file_123")
                    bot.download_file.assert_called_once_with("voice/test.ogg")
                    mock_stt_instance.transcribe.assert_called_once()
                    mock_remove.assert_called_once()  # Cleanup

@pytest.mark.asyncio
async def test_process_voice_message_file_not_found():
    bot = AsyncMock(spec=TelegramBot)
    bot.get_file.return_value = {}  # No file_path

    result = await process_voice_message("file_404", bot)
    assert result["text"] == ""
