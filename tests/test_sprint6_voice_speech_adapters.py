#!/usr/bin/env python3
"""Sprint 6 – AI Voice & Speech Adapter Tests.

Tests for: ElevenLabsAdapter, OpenAITtsAdapter, OpenAIWhisperAdapter,
           DeepgramAdapter, GoogleTtsAdapter, AzureSpeechAdapter
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0
total = 0


def test(name: str, condition: bool) -> None:
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}")


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════════════
# 1. ElevenLabsAdapter
# ═══════════════════════════════════════════════════════════════════════
print("\n🔊 ElevenLabsAdapter Tests")
from app.integrations.adapters.elevenlabs_adapter import ElevenLabsAdapter

el = ElevenLabsAdapter()
test("integration_id == 'elevenlabs'", el.integration_id == "elevenlabs")
test("has 5 capabilities", len(el.supported_capabilities) == 5)
test("voice.tts.generate supported", "voice.tts.generate" in el.supported_capabilities)
test("voice.tts.stream supported", "voice.tts.stream" in el.supported_capabilities)
test("voice.voices.list supported", "voice.voices.list" in el.supported_capabilities)
test("voice.voices.clone supported", "voice.voices.clone" in el.supported_capabilities)
test("voice.stt.transcribe supported", "voice.stt.transcribe" in el.supported_capabilities)

# Not configured test
result = run_async(el.execute_capability("voice.tts.generate", 999, text="test"))
test("returns NOT_CONFIGURED when not configured", result.error_code == "NOT_CONFIGURED")

# Configure and test missing param
el.configure_tenant(1, "test-key")
result = run_async(el.execute_capability("voice.tts.generate", 1))
test("returns MISSING_PARAM without text", result.error_code == "MISSING_PARAM")

# Clone missing params
result = run_async(el.execute_capability("voice.voices.clone", 1))
test("clone returns MISSING_PARAM without name/files", result.error_code == "MISSING_PARAM")


# ═══════════════════════════════════════════════════════════════════════
# 2. OpenAITtsAdapter
# ═══════════════════════════════════════════════════════════════════════
print("\n🎙️ OpenAITtsAdapter Tests")
from app.integrations.adapters.openai_tts_adapter import OpenAITtsAdapter

oai_tts = OpenAITtsAdapter()
test("integration_id == 'openai_tts'", oai_tts.integration_id == "openai_tts")
test("has 3 capabilities", len(oai_tts.supported_capabilities) == 3)
test("voice.tts.generate supported", "voice.tts.generate" in oai_tts.supported_capabilities)
test("voice.tts.stream supported", "voice.tts.stream" in oai_tts.supported_capabilities)
test("voice.voices.list supported", "voice.voices.list" in oai_tts.supported_capabilities)

# Not configured
result = run_async(oai_tts.execute_capability("voice.tts.generate", 999, text="test"))
test("returns NOT_CONFIGURED when not configured", result.error_code == "NOT_CONFIGURED")

# Voices list (static)
oai_tts.configure_tenant(1, "test-key")
result = run_async(oai_tts.execute_capability("voice.voices.list", 1))
test("voices.list returns success", result.success is True)
test("voices.list returns 10 voices", len(result.data) == 10)

# Missing param
result = run_async(oai_tts.execute_capability("voice.tts.generate", 1))
test("returns MISSING_PARAM without text", result.error_code == "MISSING_PARAM")


# ═══════════════════════════════════════════════════════════════════════
# 3. OpenAIWhisperAdapter
# ═══════════════════════════════════════════════════════════════════════
print("\n📝 OpenAIWhisperAdapter Tests")
from app.integrations.adapters.openai_whisper_adapter import OpenAIWhisperAdapter

whisper = OpenAIWhisperAdapter()
test("integration_id == 'openai_whisper'", whisper.integration_id == "openai_whisper")
test("has 3 capabilities", len(whisper.supported_capabilities) == 3)
test("voice.stt.transcribe supported", "voice.stt.transcribe" in whisper.supported_capabilities)
test("voice.stt.translate supported", "voice.stt.translate" in whisper.supported_capabilities)
test("voice.stt.timestamps supported", "voice.stt.timestamps" in whisper.supported_capabilities)

# Not configured
result = run_async(whisper.execute_capability("voice.stt.transcribe", 999, file_path="/tmp/test.mp3"))
test("returns NOT_CONFIGURED when not configured", result.error_code == "NOT_CONFIGURED")

# Missing param
whisper.configure_tenant(1, "test-key")
result = run_async(whisper.execute_capability("voice.stt.transcribe", 1))
test("returns MISSING_PARAM without file_path/audio_data", result.error_code == "MISSING_PARAM")

# Translate missing param
result = run_async(whisper.execute_capability("voice.stt.translate", 1))
test("translate returns MISSING_PARAM", result.error_code == "MISSING_PARAM")

# File not found
result = run_async(whisper.execute_capability("voice.stt.transcribe", 1, file_path="/nonexistent/file.mp3"))
test("returns FILE_NOT_FOUND for missing file", result.error_code == "FILE_NOT_FOUND")


# ═══════════════════════════════════════════════════════════════════════
# 4. DeepgramAdapter
# ═══════════════════════════════════════════════════════════════════════
print("\n🎧 DeepgramAdapter Tests")
from app.integrations.adapters.deepgram_adapter import DeepgramAdapter

dg = DeepgramAdapter()
test("integration_id == 'deepgram'", dg.integration_id == "deepgram")
test("has 4 capabilities", len(dg.supported_capabilities) == 4)
test("voice.stt.transcribe supported", "voice.stt.transcribe" in dg.supported_capabilities)
test("voice.stt.realtime supported", "voice.stt.realtime" in dg.supported_capabilities)
test("voice.tts.generate supported", "voice.tts.generate" in dg.supported_capabilities)
test("voice.intelligence.analyze supported", "voice.intelligence.analyze" in dg.supported_capabilities)

# Not configured
result = run_async(dg.execute_capability("voice.stt.transcribe", 999, audio_url="https://example.com/audio.mp3"))
test("returns NOT_CONFIGURED when not configured", result.error_code == "NOT_CONFIGURED")

# Realtime returns WebSocket URL
dg.configure_tenant(1, "test-key")
result = run_async(dg.execute_capability("voice.stt.realtime", 1))
test("realtime returns success with websocket_url", result.success is True and "websocket_url" in result.data)

# Missing param
result = run_async(dg.execute_capability("voice.stt.transcribe", 1))
test("returns MISSING_PARAM without audio source", result.error_code == "MISSING_PARAM")

# TTS missing param
result = run_async(dg.execute_capability("voice.tts.generate", 1))
test("tts returns MISSING_PARAM without text", result.error_code == "MISSING_PARAM")


# ═══════════════════════════════════════════════════════════════════════
# 5. GoogleTtsAdapter
# ═══════════════════════════════════════════════════════════════════════
print("\n🔈 GoogleTtsAdapter Tests")
from app.integrations.adapters.google_tts_adapter import GoogleTtsAdapter

gtts = GoogleTtsAdapter()
test("integration_id == 'google_tts'", gtts.integration_id == "google_tts")
test("has 3 capabilities", len(gtts.supported_capabilities) == 3)
test("voice.tts.generate supported", "voice.tts.generate" in gtts.supported_capabilities)
test("voice.tts.ssml supported", "voice.tts.ssml" in gtts.supported_capabilities)
test("voice.voices.list supported", "voice.voices.list" in gtts.supported_capabilities)

# Not configured
result = run_async(gtts.execute_capability("voice.tts.generate", 999, text="test"))
test("returns NOT_CONFIGURED when not configured", result.error_code == "NOT_CONFIGURED")

# Missing param
gtts.configure_tenant(1, "test-key")
result = run_async(gtts.execute_capability("voice.tts.generate", 1))
test("returns MISSING_PARAM without text", result.error_code == "MISSING_PARAM")

# SSML missing param
result = run_async(gtts.execute_capability("voice.tts.ssml", 1))
test("ssml returns MISSING_PARAM without ssml", result.error_code == "MISSING_PARAM")


# ═══════════════════════════════════════════════════════════════════════
# 6. AzureSpeechAdapter
# ═══════════════════════════════════════════════════════════════════════
print("\n☁️ AzureSpeechAdapter Tests")
from app.integrations.adapters.azure_speech_adapter import AzureSpeechAdapter

azure = AzureSpeechAdapter()
test("integration_id == 'azure_speech'", azure.integration_id == "azure_speech")
test("has 4 capabilities", len(azure.supported_capabilities) == 4)
test("voice.tts.generate supported", "voice.tts.generate" in azure.supported_capabilities)
test("voice.stt.transcribe supported", "voice.stt.transcribe" in azure.supported_capabilities)
test("voice.stt.realtime supported", "voice.stt.realtime" in azure.supported_capabilities)
test("voice.translation.speech supported", "voice.translation.speech" in azure.supported_capabilities)

# Not configured
result = run_async(azure.execute_capability("voice.tts.generate", 999, text="test"))
test("returns NOT_CONFIGURED when not configured", result.error_code == "NOT_CONFIGURED")

# Configure and test
azure.configure_tenant(1, "test-key", region="westeurope")
result = run_async(azure.execute_capability("voice.tts.generate", 1))
test("returns MISSING_PARAM without text/ssml", result.error_code == "MISSING_PARAM")

# Realtime returns WebSocket URL
result = run_async(azure.execute_capability("voice.stt.realtime", 1))
test("realtime returns success with websocket_url", result.success is True and "websocket_url" in result.data)

# STT missing param
result = run_async(azure.execute_capability("voice.stt.transcribe", 1))
test("stt returns MISSING_PARAM without audio", result.error_code == "MISSING_PARAM")

# Translation missing param
result = run_async(azure.execute_capability("voice.translation.speech", 1))
test("translation returns MISSING_PARAM without audio", result.error_code == "MISSING_PARAM")


# ═══════════════════════════════════════════════════════════════════════
# 7. Registry Integration
# ═══════════════════════════════════════════════════════════════════════
print("\n📋 Registry Integration Tests")
from app.integrations.adapters.registry import AdapterRegistry

registry = AdapterRegistry()
adapters = registry.registered_adapters

test("elevenlabs in registry", "elevenlabs" in adapters)
test("openai_tts in registry", "openai_tts" in adapters)
test("openai_whisper in registry", "openai_whisper" in adapters)
test("deepgram in registry", "deepgram" in adapters)
test("google_tts in registry", "google_tts" in adapters)
test("azure_speech in registry", "azure_speech" in adapters)

# Category filter
voice_adapters = registry.get_adapters_by_category("voice")
test("get_adapters_by_category('voice') returns 6+ adapters", len(voice_adapters) >= 6)

# Total count (should be 24: 18 from Sprint 1-5 + 6 from Sprint 6)
test(f"total registry count >= 24 (actual: {len(registry)})", len(registry) >= 24)


# ═══════════════════════════════════════════════════════════════════════
# 8. Connector Docs
# ═══════════════════════════════════════════════════════════════════════
print("\n📚 Connector Docs Tests")
from app.integrations.connector_docs import CONNECTOR_DOCS

voice_connectors = ["elevenlabs", "openai_tts", "openai_whisper", "deepgram", "google_tts", "azure_speech"]
for c in voice_connectors:
    test(f"{c} has docs entry", c in CONNECTOR_DOCS)
    if c in CONNECTOR_DOCS:
        doc = CONNECTOR_DOCS[c]
        test(f"{c} has steps", len(doc.get("steps", [])) >= 2)
        test(f"{c} has faq", len(doc.get("faq", [])) >= 1)


# ═══════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"Sprint 6 Tests: {passed}/{total} passed, {failed} failed")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
