"""Integration tests for Telegram Webhook."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.gateway.main import app
from app.gateway.schemas import Platform

client = TestClient(app)

@patch("app.gateway.main.redis_bus")
@patch("app.gateway.main.process_and_reply")
def test_telegram_webhook_chat(mock_process, mock_redis):
    mock_redis.publish = AsyncMock()
    
    payload = {
        "update_id": 12345,
        "message": {
            "message_id": 101,
            "from": {"id": 999111, "is_bot": False, "first_name": "Test", "username": "tester"},
            "chat": {"id": 999111, "type": "private"},
            "date": 1678900000,
            "text": "Hallo Ariia"
        }
    }
    
    response = client.post("/webhook/telegram", json=payload)
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    # Verify Redis Publish
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args[0]
    assert "ariia:inbound" == call_args[0]
    assert '"platform":"telegram"' in call_args[1]
    assert '"user_id":"999111"' in call_args[1]
    
    # Verify Process Task
    mock_process.assert_called_once()


@patch("app.gateway.main._telegram_bot")
def test_telegram_webhook_command(mock_bot):
    mock_bot.normalize_update.return_value = {
        "message_id": "102",
        "user_id": "888", # Admin ID (mocked settings needed?)
        "chat_id": "888",
        "content": "/status",
        "username": "admin"
    }
    mock_bot.parse_command.return_value = ("/status", "")
    mock_bot.handle_command = AsyncMock(return_value="Status OK")
    
    # We need to mock settings to match user_id="888"
    with patch("app.gateway.main.settings") as mock_settings:
        mock_settings.telegram_admin_chat_id = "888"
        
        response = client.post("/webhook/telegram", json={})
        
        assert response.status_code == 200
        assert response.json() == {"status": "handled_command"}
        mock_bot.handle_command.assert_called_once()
