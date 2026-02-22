"""ARIIA v1.4 – Integration Tests.

@QA: Sprint 3, Task 3.10
Tests: WhatsApp, Telegram, Normalizer, Dispatcher, PII Filter.
Coverage target: ≥80% for app/integrations/
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.gateway.schemas import InboundMessage, OutboundMessage, Platform
from app.integrations.whatsapp import WhatsAppClient
from app.integrations.telegram import TelegramBot
from app.integrations.normalizer import MessageNormalizer
from app.integrations.dispatcher import OutboundDispatcher
from app.integrations.pii_filter import PIIFilter
from app.integrations import wa_flows


# ──────────────────────────────────────────
# WhatsApp Client Tests
# ──────────────────────────────────────────


class TestWhatsAppClient:
    """Tests for WhatsApp Meta Cloud API client."""

    def setup_method(self) -> None:
        self.client = WhatsAppClient(
            access_token="test-token",
            phone_number_id="123456",
            app_secret="test-secret",
        )

    @pytest.mark.anyio
    async def test_send_text_calls_api(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "messages": [{"id": "wamid.test123"}]
        }

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await self.client.send_text("491701234567", "Hey Ariia!")
            assert result["messages"][0]["id"] == "wamid.test123"
            mock_http.post.assert_called_once()

    @pytest.mark.anyio
    async def test_send_template(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wamid.tpl1"}]}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await self.client.send_template("491701234567", "welcome_de")
            assert "messages" in result

    @pytest.mark.anyio
    async def test_send_interactive(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wamid.int1"}]}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            interactive = wa_flows.booking_confirmation_buttons("Yoga", "18:00", "2026-02-14")
            result = await self.client.send_interactive("491701234567", interactive)
            assert "messages" in result

    def test_verify_signature_valid(self) -> None:
        payload = b'{"test": "data"}'
        import hashlib, hmac as hmac_lib
        sig = "sha256=" + hmac_lib.new(
            b"test-secret", payload, hashlib.sha256
        ).hexdigest()
        assert self.client.verify_webhook_signature(payload, sig) is True

    def test_verify_signature_invalid(self) -> None:
        payload = b'{"test": "data"}'
        assert self.client.verify_webhook_signature(payload, "sha256=wrong") is False

    def test_verify_signature_missing_header(self) -> None:
        assert self.client.verify_webhook_signature(b"data", "") is False

    def test_verify_signature_no_secret(self) -> None:
        client = WhatsAppClient(access_token="t", phone_number_id="p")
        assert client.verify_webhook_signature(b"data", "sha256=abc") is True

    @pytest.mark.anyio
    async def test_rate_limited_raises(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.request = MagicMock()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(Exception):
                await self.client.send_text("491701234567", "test")


# ──────────────────────────────────────────
# Telegram Bot Tests
# ──────────────────────────────────────────


class TestTelegramBot:
    """Tests for Telegram Bot admin features."""

    def setup_method(self) -> None:
        self.bot = TelegramBot(bot_token="123:ABC", admin_chat_id="-100123")

    def test_parse_command_status(self) -> None:
        cmd, args = self.bot.parse_command("/status")
        assert cmd == "/status"
        assert args == ""

    def test_parse_command_ghost_on(self) -> None:
        cmd, args = self.bot.parse_command("/ghost on")
        assert cmd == "/ghost"
        assert args == "on"

    def test_parse_command_with_bot_name(self) -> None:
        cmd, args = self.bot.parse_command("/status@AriiaBot")
        assert cmd == "/status"

    def test_parse_command_no_command(self) -> None:
        cmd, args = self.bot.parse_command("Hello")
        assert cmd == ""
        assert args == "Hello"

    def test_parse_command_empty(self) -> None:
        cmd, args = self.bot.parse_command("")
        assert cmd == ""

    def test_cmd_status_with_health(self) -> None:
        health = {"status": "ok", "redis": "connected", "version": "1.4.0"}
        result = self.bot._cmd_status(health)
        assert "ok" in result
        assert "1.4.0" in result

    def test_cmd_status_without_health(self) -> None:
        result = self.bot._cmd_status()
        assert "online" in result

    def test_cmd_ghost_on(self) -> None:
        result = self.bot._cmd_ghost("on")
        assert "AKTIV" in result

    def test_cmd_ghost_off(self) -> None:
        result = self.bot._cmd_ghost("off")
        assert "DEAKTIVIERT" in result

    def test_cmd_ghost_no_args(self) -> None:
        result = self.bot._cmd_ghost("")
        assert "/ghost on" in result

    def test_cmd_help(self) -> None:
        result = self.bot._cmd_help()
        assert "/status" in result
        assert "/ghost" in result
        assert "/help" in result

    @pytest.mark.anyio
    async def test_send_alert_no_chat_id(self) -> None:
        bot = TelegramBot(bot_token="123:ABC", admin_chat_id="")
        result = await bot.send_alert("test alert")
        assert result["ok"] is False

    @pytest.mark.anyio
    async def test_send_message_calls_api(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 42}}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await self.bot.send_message("-100123", "Hello")
            assert result["ok"] is True

    @pytest.mark.anyio
    async def test_send_emergency_alert(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 99}}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await self.bot.send_emergency_alert("491701234567", "Herzinfarkt")
            assert result["ok"] is True

    @pytest.mark.anyio
    async def test_handle_command_unknown(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await self.bot.handle_command("/unknown", "", "-100123")
            assert "Unbekannt" in result


# ──────────────────────────────────────────
# Normalizer Tests
# ──────────────────────────────────────────


class TestMessageNormalizer:
    """Tests for multi-platform message normalization."""

    def setup_method(self) -> None:
        self.normalizer = MessageNormalizer()

    def test_normalize_whatsapp_text(self) -> None:
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wa1", "from": "491701111", "type": "text", "text": {"body": "Hallo"}}
            ]}}]}]
        }
        result = self.normalizer.normalize_whatsapp(payload)
        assert len(result) == 1
        assert result[0].platform == Platform.WHATSAPP
        assert result[0].content == "Hallo"
        assert result[0].content_type == "text"

    def test_normalize_whatsapp_image(self) -> None:
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wa2", "from": "491702222", "type": "image",
                 "image": {"caption": "Check this!", "id": "media123"}}
            ]}}]}]
        }
        result = self.normalizer.normalize_whatsapp(payload)
        assert result[0].content_type == "image"
        assert result[0].content == "Check this!"
        assert result[0].media_url == "media123"

    def test_normalize_whatsapp_audio(self) -> None:
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wa3", "from": "491703333", "type": "audio",
                 "audio": {"id": "aud123"}}
            ]}}]}]
        }
        result = self.normalizer.normalize_whatsapp(payload)
        assert result[0].content == "[Sprachnachricht]"

    def test_normalize_whatsapp_location(self) -> None:
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wa4", "from": "491704444", "type": "location",
                 "location": {"latitude": 52.52, "longitude": 13.405}}
            ]}}]}]
        }
        result = self.normalizer.normalize_whatsapp(payload)
        assert "52.52" in result[0].content

    def test_normalize_whatsapp_interactive(self) -> None:
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wa5", "from": "491705555", "type": "interactive",
                 "interactive": {"button_reply": {"id": "book_confirm", "title": "Ja, buchen!"}}}
            ]}}]}]
        }
        result = self.normalizer.normalize_whatsapp(payload)
        assert result[0].content == "Ja, buchen!"

    def test_normalize_whatsapp_empty(self) -> None:
        result = self.normalizer.normalize_whatsapp({"entry": []})
        assert result == []

    def test_normalize_whatsapp_unknown_type(self) -> None:
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wa6", "from": "491706666", "type": "contacts"}
            ]}}]}]
        }
        result = self.normalizer.normalize_whatsapp(payload)
        assert result[0].content == "[contacts]"

    def test_normalize_telegram_text(self) -> None:
        update = {
            "message": {
                "message_id": 42,
                "from": {"id": 123456, "username": "testuser", "first_name": "Max"},
                "chat": {"id": 123456, "type": "private"},
                "text": "Hallo Ariia!",
            }
        }
        result = self.normalizer.normalize_telegram(update)
        assert result is not None
        assert result.platform == Platform.TELEGRAM
        assert result.content == "Hallo Ariia!"
        assert result.user_id == "123456"

    def test_normalize_telegram_photo(self) -> None:
        update = {
            "message": {
                "message_id": 43,
                "from": {"id": 123456},
                "chat": {"id": 123456, "type": "private"},
                "photo": [
                    {"file_id": "small", "width": 100},
                    {"file_id": "large", "width": 800},
                ],
                "caption": "Check this",
            }
        }
        result = self.normalizer.normalize_telegram(update)
        assert result is not None
        assert result.content_type == "image"
        assert result.media_url == "large"

    def test_normalize_telegram_voice(self) -> None:
        update = {
            "message": {
                "message_id": 44,
                "from": {"id": 789},
                "chat": {"id": 789, "type": "private"},
                "voice": {"file_id": "voice123", "duration": 5},
            }
        }
        result = self.normalizer.normalize_telegram(update)
        assert result is not None
        assert result.content == "[Sprachnachricht]"
        assert result.content_type == "voice"

    def test_normalize_telegram_location(self) -> None:
        update = {
            "message": {
                "message_id": 45,
                "from": {"id": 111},
                "chat": {"id": 111, "type": "private"},
                "location": {"latitude": 52.52, "longitude": 13.405},
            }
        }
        result = self.normalizer.normalize_telegram(update)
        assert result is not None
        assert "52.52" in result.content

    def test_normalize_telegram_sticker(self) -> None:
        update = {
            "message": {
                "message_id": 46,
                "from": {"id": 222},
                "chat": {"id": 222, "type": "private"},
                "sticker": {"emoji": "💪", "file_id": "stk1"},
            }
        }
        result = self.normalizer.normalize_telegram(update)
        assert result is not None
        assert result.content == "💪"

    def test_normalize_telegram_no_message(self) -> None:
        result = self.normalizer.normalize_telegram({"update_id": 1})
        assert result is None

    def test_normalize_telegram_edited_message(self) -> None:
        update = {
            "edited_message": {
                "message_id": 47,
                "from": {"id": 333},
                "chat": {"id": 333, "type": "private"},
                "text": "Edited text",
            }
        }
        result = self.normalizer.normalize_telegram(update)
        assert result is not None
        assert result.content == "Edited text"


# ──────────────────────────────────────────
# Dispatcher Tests
# ──────────────────────────────────────────


class TestOutboundDispatcher:
    """Tests for outbound message routing."""

    @pytest.mark.anyio
    async def test_dispatch_whatsapp(self) -> None:
        mock_wa = AsyncMock()
        mock_wa.send_text = AsyncMock()
        dispatcher = OutboundDispatcher(whatsapp_client=mock_wa)
        msg = OutboundMessage(
            message_id="out1", platform=Platform.WHATSAPP,
            user_id="491701234567", content="Hey!"
        )
        result = await dispatcher.dispatch(msg)
        assert result is True
        mock_wa.send_text.assert_called_once_with("491701234567", "Hey!")

    @pytest.mark.anyio
    async def test_dispatch_telegram(self) -> None:
        mock_tg = AsyncMock()
        mock_tg.send_message = AsyncMock()
        dispatcher = OutboundDispatcher(telegram_bot=mock_tg)
        msg = OutboundMessage(
            message_id="out2", platform=Platform.TELEGRAM,
            user_id="123456", content="Hallo!"
        )
        result = await dispatcher.dispatch(msg)
        assert result is True

    @pytest.mark.anyio
    async def test_dispatch_dashboard(self) -> None:
        mock_ws = AsyncMock()
        dispatcher = OutboundDispatcher(websocket_broadcast=mock_ws)
        msg = OutboundMessage(
            message_id="out3", platform=Platform.DASHBOARD,
            user_id="admin", content="Test"
        )
        result = await dispatcher.dispatch(msg)
        assert result is True

    @pytest.mark.anyio
    async def test_dispatch_no_client(self) -> None:
        dispatcher = OutboundDispatcher()
        msg = OutboundMessage(
            message_id="out4", platform=Platform.WHATSAPP,
            user_id="491701234567", content="Test"
        )
        result = await dispatcher.dispatch(msg)
        assert result is False

    @pytest.mark.anyio
    async def test_dispatch_voice_unknown(self) -> None:
        dispatcher = OutboundDispatcher()
        msg = OutboundMessage(
            message_id="out5", platform=Platform.VOICE,
            user_id="voice1", content="Test"
        )
        result = await dispatcher.dispatch(msg)
        assert result is False

    @pytest.mark.anyio
    async def test_dispatch_error_handling(self) -> None:
        mock_wa = AsyncMock()
        mock_wa.send_text = AsyncMock(side_effect=ConnectionError("API down"))
        dispatcher = OutboundDispatcher(whatsapp_client=mock_wa)
        msg = OutboundMessage(
            message_id="out6", platform=Platform.WHATSAPP,
            user_id="491701234567", content="Test"
        )
        result = await dispatcher.dispatch(msg)
        assert result is False


# ──────────────────────────────────────────
# PII Filter Tests
# ──────────────────────────────────────────


class TestPIIFilter:
    """Tests for PII detection and masking."""

    def setup_method(self) -> None:
        self.pii = PIIFilter()

    def test_detect_phone_de(self) -> None:
        assert self.pii.contains_pii("Ruf mich an: +49 170 1234567") is True

    def test_detect_email(self) -> None:
        assert self.pii.contains_pii("Mail: max@example.com") is True

    def test_detect_iban(self) -> None:
        assert self.pii.contains_pii("IBAN: DE89 3704 0044 0532 0130 00") is True

    def test_detect_credit_card(self) -> None:
        assert self.pii.contains_pii("Karte: 4111 1111 1111 1111") is True

    def test_detect_dob(self) -> None:
        assert self.pii.contains_pii("Geboren am 15.03.1990") is True

    def test_no_pii(self) -> None:
        assert self.pii.contains_pii("Ich möchte einen Kurs buchen") is False

    def test_mask_phone(self) -> None:
        result = self.pii.mask("Ruf an: +49 170 1234567")
        assert "1234567" not in result
        assert "+49 1" in result

    def test_mask_email(self) -> None:
        result = self.pii.mask("Mail: max@example.com")
        assert "max@example" not in result
        assert "****" in result

    def test_mask_iban(self) -> None:
        result = self.pii.mask("DE89370400440532013000")
        assert "****" in result
        assert "DE89" in result

    def test_mask_credit_card(self) -> None:
        result = self.pii.mask("4111 1111 1111 1111")
        assert "****" in result
        assert "4111" in result

    def test_mask_dob(self) -> None:
        result = self.pii.mask("Geboren am 15.03.1990")
        assert "15.03.1990" not in result
        assert "**/**/**" in result

    def test_scan_and_report(self) -> None:
        text = "Mail: test@mail.de, Tel: +49 170 1234567"
        findings = self.pii.scan_and_report(text)
        assert len(findings) > 0


# ──────────────────────────────────────────
# WhatsApp Native Flows Tests
# ──────────────────────────────────────────


class TestWhatsAppFlows:
    """Tests for WhatsApp interactive message schemas."""

    def test_booking_confirmation(self) -> None:
        result = wa_flows.booking_confirmation_buttons("Yoga", "18:00", "2026-02-14")
        assert result["type"] == "button"
        assert len(result["action"]["buttons"]) == 2
        assert "Yoga" in result["body"]["text"]

    def test_time_slot_list(self) -> None:
        slots = [
            {"id": "s1", "time": "09:00", "spots": "5"},
            {"id": "s2", "time": "17:00", "spots": "3"},
        ]
        result = wa_flows.time_slot_list(slots, "Spinning")
        assert result["type"] == "list"
        rows = result["action"]["sections"][0]["rows"]
        assert len(rows) == 2
        assert rows[0]["title"] == "09:00"

    def test_cancellation_confirmation(self) -> None:
        result = wa_flows.cancellation_confirmation()
        assert result["type"] == "button"
        assert len(result["action"]["buttons"]) == 3
        # One-Way-Door: must have alternatives
        button_ids = [b["reply"]["id"] for b in result["action"]["buttons"]]
        assert "cancel_confirm" in button_ids
        assert "cancel_alternatives" in button_ids
        assert "cancel_abort" in button_ids

    def test_time_slot_list_max_10(self) -> None:
        slots = [{"id": f"s{i}", "time": f"{i}:00", "spots": "2"} for i in range(15)]
        result = wa_flows.time_slot_list(slots, "Test")
        rows = result["action"]["sections"][0]["rows"]
        assert len(rows) == 10  # WhatsApp max
