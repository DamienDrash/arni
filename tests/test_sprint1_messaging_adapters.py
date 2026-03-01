"""ARIIA v2.0 – Sprint 1: Messaging Core Adapter Tests.

Tests all four messaging adapters:
  S1.1: WhatsAppAdapter (9 capabilities)
  S1.2: TelegramAdapter (13 capabilities)
  S1.3: EmailAdapter (7 capabilities)
  S1.4: SmsVoiceAdapter (6 capabilities)
  Registry: All 7 adapters registered (3 Phase 2 + 4 Sprint 1)
  Skills: All 4 SKILL.md files exist and are valid
"""

import os
import sys
import asyncio

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "testing")

RESULTS = {"passed": 0, "failed": 0, "errors": []}


def test(name):
    """Decorator for test functions."""
    def decorator(func):
        def wrapper():
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(result)
                    finally:
                        loop.close()
                RESULTS["passed"] += 1
                print(f"  ✅ {name}")
            except Exception as e:
                RESULTS["failed"] += 1
                RESULTS["errors"].append(f"{name}: {e}")
                print(f"  ❌ {name}: {e}")
        wrapper._test_name = name
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# S1.1: WhatsAppAdapter
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔷 S1.1: WhatsAppAdapter")


@test("WhatsAppAdapter importable")
def test_whatsapp_adapter_import():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    assert adapter is not None


@test("WhatsAppAdapter integration_id is 'whatsapp'")
def test_whatsapp_adapter_id():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    assert adapter.integration_id == "whatsapp"


@test("WhatsAppAdapter has 9 capabilities")
def test_whatsapp_adapter_capabilities():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    assert len(adapter.supported_capabilities) == 9
    assert "messaging.send.text" in adapter.supported_capabilities
    assert "messaging.send.template" in adapter.supported_capabilities
    assert "messaging.send.interactive" in adapter.supported_capabilities
    assert "messaging.send.media" in adapter.supported_capabilities
    assert "messaging.mark_read" in adapter.supported_capabilities
    assert "messaging.verify_webhook" in adapter.supported_capabilities
    assert "messaging.flow.booking" in adapter.supported_capabilities
    assert "messaging.flow.time_slots" in adapter.supported_capabilities
    assert "messaging.flow.cancellation" in adapter.supported_capabilities


@test("WhatsAppAdapter inherits from BaseAdapter")
def test_whatsapp_adapter_inheritance():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    from app.integrations.adapters.base import BaseAdapter
    assert issubclass(WhatsAppAdapter, BaseAdapter)


@test("WhatsAppAdapter rejects unsupported capability")
async def test_whatsapp_adapter_unsupported():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("nonexistent.capability", tenant_id=1)
    assert not result.success
    assert result.error_code == "UNSUPPORTED_CAPABILITY"


@test("WhatsAppAdapter send_text requires 'to'")
async def test_whatsapp_send_text_missing_to():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.send.text", tenant_id=1, body="Hello")
    assert not result.success
    assert result.error_code == "MISSING_RECIPIENT"


@test("WhatsAppAdapter send_text requires 'body'")
async def test_whatsapp_send_text_missing_body():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.send.text", tenant_id=1, to="491234567890")
    assert not result.success
    assert result.error_code == "MISSING_BODY"


@test("WhatsAppAdapter send_template requires params")
async def test_whatsapp_send_template_missing():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.send.template", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("WhatsAppAdapter send_interactive requires params")
async def test_whatsapp_send_interactive_missing():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.send.interactive", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("WhatsAppAdapter send_media requires 'to'")
async def test_whatsapp_send_media_missing_to():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.send.media", tenant_id=1, media_url="http://example.com/img.jpg")
    assert not result.success
    assert result.error_code == "MISSING_RECIPIENT"


@test("WhatsAppAdapter send_media requires media")
async def test_whatsapp_send_media_missing_media():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.send.media", tenant_id=1, to="491234567890")
    assert not result.success
    assert result.error_code == "MISSING_MEDIA"


@test("WhatsAppAdapter mark_read requires message_id")
async def test_whatsapp_mark_read_missing():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.mark_read", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_MESSAGE_ID"


@test("WhatsAppAdapter verify_webhook requires params")
async def test_whatsapp_verify_webhook_missing():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.verify_webhook", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("WhatsAppAdapter flow_booking requires params")
async def test_whatsapp_flow_booking_missing():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.flow.booking", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("WhatsAppAdapter flow_time_slots requires params")
async def test_whatsapp_flow_time_slots_missing():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.flow.time_slots", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("WhatsAppAdapter flow_cancellation requires 'to'")
async def test_whatsapp_flow_cancellation_missing():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.flow.cancellation", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_RECIPIENT"


@test("WhatsAppAdapter health_check returns NOT_CONFIGURED without config")
async def test_whatsapp_health_check():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.health_check(tenant_id=99999)
    assert not result.success
    assert result.error_code == "NOT_CONFIGURED"


@test("WhatsAppAdapter AdapterResult has execution_time_ms")
async def test_whatsapp_execution_time():
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    adapter = WhatsAppAdapter()
    result = await adapter.execute_capability("messaging.send.text", tenant_id=1, body="test")
    assert result.execution_time_ms >= 0


test_whatsapp_adapter_import()
test_whatsapp_adapter_id()
test_whatsapp_adapter_capabilities()
test_whatsapp_adapter_inheritance()
test_whatsapp_adapter_unsupported()
test_whatsapp_send_text_missing_to()
test_whatsapp_send_text_missing_body()
test_whatsapp_send_template_missing()
test_whatsapp_send_interactive_missing()
test_whatsapp_send_media_missing_to()
test_whatsapp_send_media_missing_media()
test_whatsapp_mark_read_missing()
test_whatsapp_verify_webhook_missing()
test_whatsapp_flow_booking_missing()
test_whatsapp_flow_time_slots_missing()
test_whatsapp_flow_cancellation_missing()
test_whatsapp_health_check()
test_whatsapp_execution_time()


# ═══════════════════════════════════════════════════════════════════════════════
# S1.2: TelegramAdapter
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔷 S1.2: TelegramAdapter")


@test("TelegramAdapter importable")
def test_telegram_adapter_import():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    assert adapter is not None


@test("TelegramAdapter integration_id is 'telegram'")
def test_telegram_adapter_id():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    assert adapter.integration_id == "telegram"


@test("TelegramAdapter has 13 capabilities")
def test_telegram_adapter_capabilities():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    assert len(adapter.supported_capabilities) == 13
    assert "messaging.send.text" in adapter.supported_capabilities
    assert "messaging.send.voice" in adapter.supported_capabilities
    assert "messaging.send.alert" in adapter.supported_capabilities
    assert "messaging.send.emergency" in adapter.supported_capabilities
    assert "messaging.send.contact_request" in adapter.supported_capabilities
    assert "admin.command.handle" in adapter.supported_capabilities
    assert "admin.webhook.set" in adapter.supported_capabilities


@test("TelegramAdapter inherits from BaseAdapter")
def test_telegram_adapter_inheritance():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    from app.integrations.adapters.base import BaseAdapter
    assert issubclass(TelegramAdapter, BaseAdapter)


@test("TelegramAdapter rejects unsupported capability")
async def test_telegram_adapter_unsupported():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("nonexistent.capability", tenant_id=1)
    assert not result.success
    assert result.error_code == "UNSUPPORTED_CAPABILITY"


@test("TelegramAdapter send_text requires chat_id")
async def test_telegram_send_text_missing_chat_id():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.send.text", tenant_id=1, text="Hello")
    assert not result.success
    assert result.error_code == "MISSING_CHAT_ID"


@test("TelegramAdapter send_text requires text")
async def test_telegram_send_text_missing_text():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.send.text", tenant_id=1, chat_id="123")
    assert not result.success
    assert result.error_code == "MISSING_TEXT"


@test("TelegramAdapter send_voice requires params")
async def test_telegram_send_voice_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.send.voice", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("TelegramAdapter send_alert requires message")
async def test_telegram_send_alert_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.send.alert", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_MESSAGE"


@test("TelegramAdapter send_emergency requires user_id")
async def test_telegram_send_emergency_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.send.emergency", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_USER_ID"


@test("TelegramAdapter send_contact_request requires chat_id")
async def test_telegram_contact_request_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.send.contact_request", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_CHAT_ID"


@test("TelegramAdapter normalize_update requires update")
async def test_telegram_normalize_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.receive.normalize", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_UPDATE"


@test("TelegramAdapter normalize_update with valid message")
async def test_telegram_normalize_valid():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    update = {
        "message": {
            "message_id": 42,
            "from": {"id": 123456, "username": "testuser", "first_name": "Test"},
            "chat": {"id": 123456, "type": "private"},
            "text": "Hello World"
        }
    }
    result = await adapter.execute_capability("messaging.receive.normalize", tenant_id=1, update=update, bot_token="dummy")
    assert result.success
    assert result.data["content"] == "Hello World"
    assert result.data["user_id"] == "123456"


@test("TelegramAdapter parse_command works")
async def test_telegram_parse_command():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("admin.command.parse", tenant_id=1, text="/status")
    assert result.success
    assert result.data["command"] == "/status"
    assert result.data["is_command"] is True


@test("TelegramAdapter parse_command with args")
async def test_telegram_parse_command_args():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("admin.command.parse", tenant_id=1, text="/ghost on")
    assert result.success
    assert result.data["command"] == "/ghost"
    assert result.data["args"] == "on"


@test("TelegramAdapter parse_command non-command")
async def test_telegram_parse_non_command():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("admin.command.parse", tenant_id=1, text="Hello World")
    assert result.success
    assert result.data["command"] == ""
    assert result.data["is_command"] is False


@test("TelegramAdapter get_file requires file_id")
async def test_telegram_get_file_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.receive.get_file", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_FILE_ID"


@test("TelegramAdapter download_file requires file_path")
async def test_telegram_download_file_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("messaging.receive.download_file", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_FILE_PATH"


@test("TelegramAdapter set_webhook requires url")
async def test_telegram_set_webhook_missing():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.execute_capability("admin.webhook.set", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_URL"


@test("TelegramAdapter health_check returns NOT_CONFIGURED")
async def test_telegram_health_check():
    from app.integrations.adapters.telegram_adapter import TelegramAdapter
    adapter = TelegramAdapter()
    result = await adapter.health_check(tenant_id=99999)
    assert not result.success
    assert result.error_code == "NOT_CONFIGURED"


test_telegram_adapter_import()
test_telegram_adapter_id()
test_telegram_adapter_capabilities()
test_telegram_adapter_inheritance()
test_telegram_adapter_unsupported()
test_telegram_send_text_missing_chat_id()
test_telegram_send_text_missing_text()
test_telegram_send_voice_missing()
test_telegram_send_alert_missing()
test_telegram_send_emergency_missing()
test_telegram_contact_request_missing()
test_telegram_normalize_missing()
test_telegram_normalize_valid()
test_telegram_parse_command()
test_telegram_parse_command_args()
test_telegram_parse_non_command()
test_telegram_get_file_missing()
test_telegram_download_file_missing()
test_telegram_set_webhook_missing()
test_telegram_health_check()


# ═══════════════════════════════════════════════════════════════════════════════
# S1.3: EmailAdapter
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔷 S1.3: EmailAdapter")


@test("EmailAdapter importable")
def test_email_adapter_import():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    assert adapter is not None


@test("EmailAdapter integration_id is 'email'")
def test_email_adapter_id():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    assert adapter.integration_id == "email"


@test("EmailAdapter has 7 capabilities")
def test_email_adapter_capabilities():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    assert len(adapter.supported_capabilities) == 7
    assert "messaging.send.email" in adapter.supported_capabilities
    assert "messaging.send.html_email" in adapter.supported_capabilities
    assert "messaging.send.postmark" in adapter.supported_capabilities
    assert "messaging.send.template_email" in adapter.supported_capabilities
    assert "messaging.receive.email" in adapter.supported_capabilities
    assert "messaging.track.opens" in adapter.supported_capabilities
    assert "messaging.track.bounces" in adapter.supported_capabilities


@test("EmailAdapter inherits from BaseAdapter")
def test_email_adapter_inheritance():
    from app.integrations.adapters.email_adapter import EmailAdapter
    from app.integrations.adapters.base import BaseAdapter
    assert issubclass(EmailAdapter, BaseAdapter)


@test("EmailAdapter rejects unsupported capability")
async def test_email_adapter_unsupported():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("nonexistent.capability", tenant_id=1)
    assert not result.success
    assert result.error_code == "UNSUPPORTED_CAPABILITY"


@test("EmailAdapter send_email requires to_email")
async def test_email_send_missing_to():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.send.email", tenant_id=1, subject="Test", body="Hello")
    assert not result.success
    assert result.error_code == "MISSING_RECIPIENT"


@test("EmailAdapter send_email requires subject")
async def test_email_send_missing_subject():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.send.email", tenant_id=1, to_email="test@test.de", body="Hello")
    assert not result.success
    assert result.error_code == "MISSING_SUBJECT"


@test("EmailAdapter send_email requires body")
async def test_email_send_missing_body():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.send.email", tenant_id=1, to_email="test@test.de", subject="Test")
    assert not result.success
    assert result.error_code == "MISSING_BODY"


@test("EmailAdapter send_postmark requires params")
async def test_email_send_postmark_missing():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.send.postmark", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("EmailAdapter send_template_email requires params")
async def test_email_send_template_missing():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.send.template_email", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PARAMS"


@test("EmailAdapter receive_email requires payload")
async def test_email_receive_missing():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.receive.email", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PAYLOAD"


@test("EmailAdapter receive_email normalizes payload")
async def test_email_receive_valid():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    payload = {
        "MessageID": "msg-123",
        "From": "sender@example.com",
        "FromName": "Sender",
        "To": "recipient@example.com",
        "Subject": "Test Email",
        "TextBody": "Hello World",
        "HtmlBody": "<p>Hello World</p>",
        "Date": "2026-03-01T10:00:00Z",
        "Attachments": [
            {"Name": "file.pdf", "ContentType": "application/pdf", "ContentLength": 1024}
        ],
        "Headers": [
            {"Name": "X-Custom", "Value": "test"}
        ],
    }
    result = await adapter.execute_capability("messaging.receive.email", tenant_id=1, payload=payload)
    assert result.success
    assert result.data["message_id"] == "msg-123"
    assert result.data["from"] == "sender@example.com"
    assert result.data["subject"] == "Test Email"
    assert len(result.data["attachments"]) == 1


@test("EmailAdapter track_opens requires payload")
async def test_email_track_opens_missing():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.track.opens", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PAYLOAD"


@test("EmailAdapter track_bounces requires payload")
async def test_email_track_bounces_missing():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.execute_capability("messaging.track.bounces", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PAYLOAD"


@test("EmailAdapter track_bounces processes payload")
async def test_email_track_bounces_valid():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    payload = {
        "ID": 42,
        "Type": "HardBounce",
        "TypeCode": 1,
        "MessageID": "msg-456",
        "Email": "bounced@example.com",
        "Description": "Address not found",
        "Inactive": True,
        "CanActivate": False,
        "BouncedAt": "2026-03-01T10:00:00Z",
    }
    result = await adapter.execute_capability("messaging.track.bounces", tenant_id=1, payload=payload)
    assert result.success
    assert result.data["type"] == "HardBounce"
    assert result.data["email"] == "bounced@example.com"
    assert result.data["inactive"] is True


@test("EmailAdapter health_check returns NOT_CONFIGURED")
async def test_email_health_check():
    from app.integrations.adapters.email_adapter import EmailAdapter
    adapter = EmailAdapter()
    result = await adapter.health_check(tenant_id=99999)
    assert not result.success
    assert result.error_code == "NOT_CONFIGURED"


test_email_adapter_import()
test_email_adapter_id()
test_email_adapter_capabilities()
test_email_adapter_inheritance()
test_email_adapter_unsupported()
test_email_send_missing_to()
test_email_send_missing_subject()
test_email_send_missing_body()
test_email_send_postmark_missing()
test_email_send_template_missing()
test_email_receive_missing()
test_email_receive_valid()
test_email_track_opens_missing()
test_email_track_bounces_missing()
test_email_track_bounces_valid()
test_email_health_check()


# ═══════════════════════════════════════════════════════════════════════════════
# S1.4: SmsVoiceAdapter
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔷 S1.4: SmsVoiceAdapter")


@test("SmsVoiceAdapter importable")
def test_sms_voice_adapter_import():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    assert adapter is not None


@test("SmsVoiceAdapter integration_id is 'sms_voice'")
def test_sms_voice_adapter_id():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    assert adapter.integration_id == "sms_voice"


@test("SmsVoiceAdapter has 6 capabilities")
def test_sms_voice_adapter_capabilities():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    assert len(adapter.supported_capabilities) == 6
    assert "messaging.send.sms" in adapter.supported_capabilities
    assert "messaging.receive.sms" in adapter.supported_capabilities
    assert "messaging.sms.status" in adapter.supported_capabilities
    assert "voice.call.outbound" in adapter.supported_capabilities
    assert "voice.call.twiml" in adapter.supported_capabilities
    assert "voice.call.status" in adapter.supported_capabilities


@test("SmsVoiceAdapter inherits from BaseAdapter")
def test_sms_voice_adapter_inheritance():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    from app.integrations.adapters.base import BaseAdapter
    assert issubclass(SmsVoiceAdapter, BaseAdapter)


@test("SmsVoiceAdapter rejects unsupported capability")
async def test_sms_voice_adapter_unsupported():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("nonexistent.capability", tenant_id=1)
    assert not result.success
    assert result.error_code == "UNSUPPORTED_CAPABILITY"


@test("SmsVoiceAdapter send_sms requires 'to'")
async def test_sms_send_missing_to():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("messaging.send.sms", tenant_id=1, body="Hello")
    assert not result.success
    assert result.error_code == "MISSING_RECIPIENT"


@test("SmsVoiceAdapter send_sms requires 'body'")
async def test_sms_send_missing_body():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("messaging.send.sms", tenant_id=1, to="+491234567890")
    assert not result.success
    assert result.error_code == "MISSING_BODY"


@test("SmsVoiceAdapter receive_sms requires payload")
async def test_sms_receive_missing():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("messaging.receive.sms", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PAYLOAD"


@test("SmsVoiceAdapter receive_sms normalizes payload")
async def test_sms_receive_valid():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    payload = {
        "MessageSid": "SM123",
        "From": "+491234567890",
        "To": "+491111111111",
        "Body": "Hello from SMS",
        "NumMedia": "0",
        "FromCity": "Berlin",
        "FromCountry": "DE",
    }
    result = await adapter.execute_capability("messaging.receive.sms", tenant_id=1, payload=payload)
    assert result.success
    assert result.data["message_sid"] == "SM123"
    assert result.data["from"] == "+491234567890"
    assert result.data["body"] == "Hello from SMS"


@test("SmsVoiceAdapter sms_status requires payload")
async def test_sms_status_missing():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("messaging.sms.status", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PAYLOAD"


@test("SmsVoiceAdapter outbound_call requires 'to'")
async def test_voice_call_missing_to():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("voice.call.outbound", tenant_id=1, twiml="<Response/>")
    assert not result.success
    assert result.error_code == "MISSING_RECIPIENT"


@test("SmsVoiceAdapter outbound_call requires twiml")
async def test_voice_call_missing_twiml():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("voice.call.outbound", tenant_id=1, to="+491234567890")
    assert not result.success
    assert result.error_code == "MISSING_TWIML"


@test("SmsVoiceAdapter generate_twiml say action")
async def test_voice_twiml_say():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability(
        "voice.call.twiml", tenant_id=1,
        action="say", text="Willkommen bei ARIIA", language="de-DE"
    )
    assert result.success
    assert "<Say" in result.data["twiml"]
    assert "Willkommen bei ARIIA" in result.data["twiml"]


@test("SmsVoiceAdapter generate_twiml gather action")
async def test_voice_twiml_gather():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability(
        "voice.call.twiml", tenant_id=1,
        action="gather", text="Bitte sprechen Sie nach dem Ton"
    )
    assert result.success
    assert "<Gather" in result.data["twiml"]
    assert "<Say" in result.data["twiml"]


@test("SmsVoiceAdapter generate_twiml dial action")
async def test_voice_twiml_dial():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability(
        "voice.call.twiml", tenant_id=1,
        action="dial", dial_number="+491234567890"
    )
    assert result.success
    assert "<Dial>" in result.data["twiml"]
    assert "+491234567890" in result.data["twiml"]


@test("SmsVoiceAdapter generate_twiml record action")
async def test_voice_twiml_record():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("voice.call.twiml", tenant_id=1, action="record")
    assert result.success
    assert "<Record" in result.data["twiml"]


@test("SmsVoiceAdapter call_status requires payload")
async def test_voice_call_status_missing():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.execute_capability("voice.call.status", tenant_id=1)
    assert not result.success
    assert result.error_code == "MISSING_PAYLOAD"


@test("SmsVoiceAdapter health_check returns NOT_CONFIGURED")
async def test_sms_voice_health_check():
    from app.integrations.adapters.sms_voice_adapter import SmsVoiceAdapter
    adapter = SmsVoiceAdapter()
    result = await adapter.health_check(tenant_id=99999)
    assert not result.success
    assert result.error_code == "NOT_CONFIGURED"


test_sms_voice_adapter_import()
test_sms_voice_adapter_id()
test_sms_voice_adapter_capabilities()
test_sms_voice_adapter_inheritance()
test_sms_voice_adapter_unsupported()
test_sms_send_missing_to()
test_sms_send_missing_body()
test_sms_receive_missing()
test_sms_receive_valid()
test_sms_status_missing()
test_voice_call_missing_to()
test_voice_call_missing_twiml()
test_voice_twiml_say()
test_voice_twiml_gather()
test_voice_twiml_dial()
test_voice_twiml_record()
test_voice_call_status_missing()
test_sms_voice_health_check()


# ═══════════════════════════════════════════════════════════════════════════════
# Registry: All adapters registered
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔷 AdapterRegistry Integration")


@test("AdapterRegistry has 7 registered adapters")
def test_registry_count():
    # Reset singleton to force re-registration
    import app.integrations.adapters.registry as reg_module
    reg_module._adapter_registry = None
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    adapters = registry.registered_adapters
    assert len(adapters) >= 7, f"Expected >= 7 adapters, got {len(adapters)}: {list(adapters.keys())}"


@test("AdapterRegistry contains 'whatsapp'")
def test_registry_whatsapp():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    assert "whatsapp" in registry


@test("AdapterRegistry contains 'telegram'")
def test_registry_telegram():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    assert "telegram" in registry


@test("AdapterRegistry contains 'email'")
def test_registry_email():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    assert "email" in registry


@test("AdapterRegistry contains 'sms_voice'")
def test_registry_sms_voice():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    assert "sms_voice" in registry


@test("AdapterRegistry contains Phase 2 adapters")
def test_registry_phase2():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    assert "magicline" in registry
    assert "shopify" in registry
    assert "manual_crm" in registry


@test("AdapterRegistry get_adapter returns correct type")
def test_registry_get_adapter():
    from app.integrations.adapters.registry import get_adapter_registry
    from app.integrations.adapters.whatsapp_adapter import WhatsAppAdapter
    registry = get_adapter_registry()
    adapter = registry.get_adapter("whatsapp")
    assert isinstance(adapter, WhatsAppAdapter)


@test("AdapterRegistry get_adapters_by_category works for messaging")
def test_registry_category_messaging():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    messaging = registry.get_adapters_by_category("messaging")
    assert "whatsapp" in messaging
    assert "telegram" in messaging
    assert "email" in messaging
    assert "sms_voice" in messaging


@test("AdapterRegistry get_adapters_by_category works for voice")
def test_registry_category_voice():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    voice = registry.get_adapters_by_category("voice")
    assert "sms_voice" in voice


@test("AdapterRegistry get_adapters_by_category works for admin")
def test_registry_category_admin():
    from app.integrations.adapters.registry import get_adapter_registry
    registry = get_adapter_registry()
    admin = registry.get_adapters_by_category("admin")
    assert "telegram" in admin


test_registry_count()
test_registry_whatsapp()
test_registry_telegram()
test_registry_email()
test_registry_sms_voice()
test_registry_phase2()
test_registry_get_adapter()
test_registry_category_messaging()
test_registry_category_voice()
test_registry_category_admin()


# ═══════════════════════════════════════════════════════════════════════════════
# Skills: SKILL.md files exist and are valid
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔷 Skill Files")


@test("whatsapp.SKILL.md exists and has content")
def test_whatsapp_skill():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "messaging", "whatsapp.SKILL.md")
    assert os.path.exists(path), f"File not found: {path}"
    with open(path) as f:
        content = f.read()
    assert len(content) > 500
    assert "messaging_send_text" in content
    assert "messaging_send_template" in content
    assert "messaging_flow_booking" in content


@test("telegram.SKILL.md exists and has content")
def test_telegram_skill():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "messaging", "telegram.SKILL.md")
    assert os.path.exists(path), f"File not found: {path}"
    with open(path) as f:
        content = f.read()
    assert len(content) > 500
    assert "messaging_send_text" in content
    assert "messaging_send_alert" in content
    assert "admin_command_handle" in content


@test("email.SKILL.md exists and has content")
def test_email_skill():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "messaging", "email.SKILL.md")
    assert os.path.exists(path), f"File not found: {path}"
    with open(path) as f:
        content = f.read()
    assert len(content) > 500
    assert "messaging_send_email" in content
    assert "messaging_send_postmark" in content


@test("sms_voice.SKILL.md exists and has content")
def test_sms_voice_skill():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "messaging", "sms_voice.SKILL.md")
    assert os.path.exists(path), f"File not found: {path}"
    with open(path) as f:
        content = f.read()
    assert len(content) > 500
    assert "messaging_send_sms" in content
    assert "voice_call_outbound" in content
    assert "voice_call_twiml" in content


test_whatsapp_skill()
test_telegram_skill()
test_email_skill()
test_sms_voice_skill()


# ═══════════════════════════════════════════════════════════════════════════════
# AdapterResult Tests
# ═══════════════════════════════════════════════════════════════════════════════

print("\n🔷 AdapterResult Format")


@test("AdapterResult to_agent_response for success")
def test_adapter_result_success():
    from app.integrations.adapters.base import AdapterResult
    result = AdapterResult(success=True, data={"status": "sent", "to": "491234567890"})
    response = result.to_agent_response()
    assert "Status" in response
    assert "sent" in response


@test("AdapterResult to_agent_response for error")
def test_adapter_result_error():
    from app.integrations.adapters.base import AdapterResult
    result = AdapterResult(success=False, error="Test error")
    response = result.to_agent_response()
    assert "Fehler" in response
    assert "Test error" in response


@test("AdapterResult to_agent_response for list data")
def test_adapter_result_list():
    from app.integrations.adapters.base import AdapterResult
    result = AdapterResult(success=True, data=[{"name": "Item 1"}, {"name": "Item 2"}])
    response = result.to_agent_response()
    assert "Item 1" in response
    assert "Item 2" in response


@test("AdapterResult to_agent_response for empty list")
def test_adapter_result_empty_list():
    from app.integrations.adapters.base import AdapterResult
    result = AdapterResult(success=True, data=[])
    response = result.to_agent_response()
    assert "Keine Ergebnisse" in response


@test("AdapterResult to_agent_response for string data")
def test_adapter_result_string():
    from app.integrations.adapters.base import AdapterResult
    result = AdapterResult(success=True, data="Nachricht gesendet")
    response = result.to_agent_response()
    assert response == "Nachricht gesendet"


test_adapter_result_success()
test_adapter_result_error()
test_adapter_result_list()
test_adapter_result_empty_list()
test_adapter_result_string()


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
total = RESULTS["passed"] + RESULTS["failed"]
print(f"📊 Sprint 1 Tests: {RESULTS['passed']}/{total} passed")

if RESULTS["errors"]:
    print(f"\n❌ {RESULTS['failed']} Fehler:")
    for err in RESULTS["errors"]:
        print(f"  - {err}")
else:
    print("✅ Alle Tests bestanden!")

print("=" * 70)

# Exit with error code if any tests failed
sys.exit(1 if RESULTS["failed"] > 0 else 0)
