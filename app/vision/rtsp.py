"""ARIIA v1.4 – RTSP Connector.

@BACKEND: Sprint 5a, Task 5a.2
Snapshot grabber for CCTV/RTSP streams.
Requires OpenCV and a configured stream URL.
"""

from __future__ import annotations

import os
import structlog

logger = structlog.get_logger()

# Try importing cv2 for RTSP capture
try:
    import cv2  # type: ignore[import-untyped]
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.info("vision.cv2_unavailable", msg="opencv not installed, using stub mode")

# Opt-in flag: set RTSP_ENABLE_LIVE=1 to enable real RTSP capture
_RTSP_ENABLED = os.getenv("RTSP_ENABLE_LIVE", "").lower() in ("1", "true", "yes")

DEFAULT_TIMEOUT_MS = 5000


class RTSPConnector:
    """RTSP stream snapshot grabber.

    Requires OpenCV, a configured stream URL, and RTSP_ENABLE_LIVE=1.
    Privacy: Grabbed frames are returned as bytes (RAM only).
    In stub mode, grab_snapshot() returns a placeholder JPEG.
    """

    def __init__(self, stream_url: str = "", timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        self._stream_url = stream_url
        self._timeout_ms = timeout_ms
        # Stub unless explicitly enabled via env var
        self._stub_mode = not (CV2_AVAILABLE and stream_url and _RTSP_ENABLED)

    @property
    def is_stub(self) -> bool:
        """Whether connector is offline (no OpenCV or no stream)."""
        return self._stub_mode

    @property
    def stream_url(self) -> str:
        return self._stream_url

    # Minimal JPEG stub: SOI (FFD8) + EOI (FFD9) markers with JFIF APP0 header
    _STUB_JPEG: bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"

    def grab_snapshot(self) -> bytes:
        """Grab a single frame from the RTSP stream.

        In stub mode, returns a minimal placeholder JPEG.

        Returns:
            JPEG-encoded frame bytes.
        """
        if self._stub_mode:
            logger.debug("rtsp.stub_snapshot", msg="Returning stub JPEG (no RTSP stream configured)")
            return self._STUB_JPEG

        return self._rtsp_grab()

    def _rtsp_grab(self) -> bytes:
        """Real RTSP frame grab via OpenCV."""
        cap = None
        try:
            cap = cv2.VideoCapture(self._stream_url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._timeout_ms)

            if not cap.isOpened():
                raise ConnectionError(f"Cannot open RTSP stream: {self._stream_url}")

            ret, frame = cap.read()
            if not ret or frame is None:
                raise ConnectionError("Failed to grab frame from RTSP stream")

            # Encode as JPEG
            _, buffer = cv2.imencode(".jpg", frame)
            frame_bytes = buffer.tobytes()

            # Clear frame from memory
            del frame, buffer

            logger.debug("rtsp.frame_grabbed", stream=self._stream_url, size=len(frame_bytes))
            return frame_bytes

        except Exception as e:
            logger.error("rtsp.grab_failed", error=str(e), stream=self._stream_url)
            raise ConnectionError(f"RTSP grab failed: {e}") from e

        finally:
            if cap is not None:
                cap.release()



    def test_connection(self) -> bool:
        """Test if RTSP stream is reachable.

        In stub mode, always returns True (stub is always "available").

        Returns:
            True if stream is reachable, False otherwise.
        """
        if self._stub_mode:
            return True
        try:
            self.grab_snapshot()
            return True
        except ConnectionError:
            return False
