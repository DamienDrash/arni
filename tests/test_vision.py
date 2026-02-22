"""ARNI v1.4 – Vision Module Tests.

@QA: Sprint 5a, Task 5a.5
Tests: Processor, RTSP, Privacy Engine, Agent Vision.
"""

import pytest

from app.vision.processor import (
    VisionProcessor, CrowdResult, AreaResult,
    classify_density, YOLO_AVAILABLE,
)
from app.vision.rtsp import RTSPConnector
from app.vision.privacy import PrivacyEngine, PrivacyAuditEntry


# ──────────────────────────────────────────
# Processor Tests
# ──────────────────────────────────────────


class TestVisionProcessor:
    """Tests for YOLOv8 vision processor."""

    def test_processor_starts_in_stub_mode(self) -> None:
        proc = VisionProcessor()
        # On VPS without ultralytics, should be stub
        assert proc.is_stub is True

    def test_stub_process_returns_crowd_result(self) -> None:
        proc = VisionProcessor()
        result = proc.process_frame(b"fake-image-data")
        assert isinstance(result, CrowdResult)
        assert result.total_count > 0
        assert result.source == "stub"
        assert result.density in ("empty", "low", "medium", "high", "very_high")

    def test_stub_process_has_areas(self) -> None:
        proc = VisionProcessor()
        result = proc.process_frame(b"data")
        assert len(result.areas) > 0
        for area in result.areas:
            assert isinstance(area, AreaResult)
            assert area.name
            assert area.count >= 0

    def test_classify_density_empty(self) -> None:
        assert classify_density(0) == "empty"
        assert classify_density(3) == "empty"

    def test_classify_density_low(self) -> None:
        assert classify_density(5) == "low"
        assert classify_density(10) == "low"

    def test_classify_density_medium(self) -> None:
        assert classify_density(15) == "medium"
        assert classify_density(25) == "medium"

    def test_classify_density_high(self) -> None:
        assert classify_density(30) == "high"
        assert classify_density(45) == "high"

    def test_classify_density_very_high(self) -> None:
        assert classify_density(50) == "very_high"
        assert classify_density(100) == "very_high"


# ──────────────────────────────────────────
# RTSP Connector Tests
# ──────────────────────────────────────────


class TestRTSPConnector:
    """Tests for RTSP stream connector."""

    def test_stub_mode_without_url(self) -> None:
        conn = RTSPConnector()
        assert conn.is_stub is True

    def test_stub_frame_is_valid_jpeg(self) -> None:
        conn = RTSPConnector()
        frame = conn.grab_snapshot()
        assert isinstance(frame, bytes)
        assert len(frame) > 0
        # JPEG starts with FFD8
        assert frame[:2] == b"\xff\xd8"

    def test_test_connection_stub(self) -> None:
        conn = RTSPConnector()
        assert conn.test_connection() is True

    def test_stream_url_property(self) -> None:
        conn = RTSPConnector(stream_url="rtsp://example.com/stream")
        assert conn.stream_url == "rtsp://example.com/stream"

    def test_connector_with_url_but_no_cv2(self) -> None:
        conn = RTSPConnector(stream_url="rtsp://test")
        # Without cv2, still in stub mode
        assert conn.is_stub is True


# ──────────────────────────────────────────
# Privacy Engine Tests
# ──────────────────────────────────────────


class TestPrivacyEngine:
    """Tests for 0s retention privacy engine."""

    def test_safe_process_returns_result(self) -> None:
        proc = VisionProcessor()
        conn = RTSPConnector()
        engine = PrivacyEngine(proc, conn)
        result = engine.safe_process()
        assert isinstance(result, CrowdResult)
        assert result.total_count >= 0

    def test_audit_log_populated(self) -> None:
        proc = VisionProcessor()
        conn = RTSPConnector()
        engine = PrivacyEngine(proc, conn)
        engine.safe_process()
        log = engine.get_audit_log()
        assert len(log) == 1
        assert log[0]["frame_discarded"] is True

    def test_audit_log_multiple_calls(self) -> None:
        proc = VisionProcessor()
        conn = RTSPConnector()
        engine = PrivacyEngine(proc, conn)
        for _ in range(3):
            engine.safe_process()
        log = engine.get_audit_log()
        assert len(log) == 3

    def test_verify_retention_policy(self) -> None:
        proc = VisionProcessor()
        conn = RTSPConnector()
        engine = PrivacyEngine(proc, conn)
        engine.safe_process()
        policy = engine.verify_retention_policy()
        assert policy["compliant"] is True
        assert policy["all_frames_discarded"] is True
        assert policy["no_disk_writes"] is True
        assert policy["no_frame_in_logs"] is True

    def test_audit_log_no_frame_data(self) -> None:
        proc = VisionProcessor()
        conn = RTSPConnector()
        engine = PrivacyEngine(proc, conn)
        engine.safe_process()
        log = engine.get_audit_log()
        entry = log[0]
        # Verify no frame data in audit entry
        assert "frame_data" not in entry
        assert "image" not in entry
        assert isinstance(entry["frame_size_bytes"], int)


# ──────────────────────────────────────────
# Agent Vision Integration Test
# ──────────────────────────────────────────


class TestAgentVision:
    """Tests for upgraded Vision agent."""

    @pytest.mark.anyio
    async def test_handle_returns_response(self) -> None:
        from app.swarm.agents.vision import AgentVision
        from app.gateway.schemas import InboundMessage, Platform

        agent = AgentVision()
        msg = InboundMessage(
            message_id="test-1",
            platform=Platform.WHATSAPP,
            user_id="user1",
            content_type="text",
            content="Ist es gerade voll?",
        )
        result = await agent.handle(msg)
        assert result.content
        assert "Auslastung" in result.content
        assert result.metadata["count"] >= 0

    def test_agent_name(self) -> None:
        from app.swarm.agents.vision import AgentVision
        agent = AgentVision()
        assert agent.name == "vision"

    def test_agent_description(self) -> None:
        from app.swarm.agents.vision import AgentVision
        agent = AgentVision()
        assert "Vision" in agent.description
