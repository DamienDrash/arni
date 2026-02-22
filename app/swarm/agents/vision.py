"""ARNI v1.4 – Agent Vision (The Eye).

@BACKEND: Sprint 5a (live pipeline)
Crowd counting via YOLOv8 on RTSP streams.
Privacy: 0s retention for images (DSGVO_BASELINE R1-R6).
"""

import structlog

from app.gateway.schemas import InboundMessage
from app.swarm.base import AgentResponse, BaseAgent
from app.vision.processor import VisionProcessor, classify_density
from app.vision.rtsp import RTSPConnector
from app.vision.privacy import PrivacyEngine

logger = structlog.get_logger()


class AgentVision(BaseAgent):
    """Vision/crowd counting agent.

    Uses PrivacyEngine for 0s-retention frame processing.
    Returns error when hardware is unavailable.
    """

    def __init__(self, stream_url: str = "") -> None:
        self._processor = VisionProcessor()
        self._connector = RTSPConnector(stream_url=stream_url)
        self._privacy = PrivacyEngine(self._processor, self._connector)

    @property
    def name(self) -> str:
        return "vision"

    @property
    def description(self) -> str:
        mode = "Live (YOLOv8)" if not self._processor.is_stub else "Offline"
        return f"Vision Agent – Crowd Counting ({mode})"

    async def handle(self, message: InboundMessage) -> AgentResponse:
        """Return crowd status via privacy-safe processing."""
        logger.info("agent.vision.handle", message_id=message.message_id)

        result = self._privacy.safe_process()

        # Format response
        density_emoji = {
            "empty": "🟢", "low": "🟢", "medium": "🟡",
            "high": "🟠", "very_high": "🔴", "unknown": "⚪",
        }
        emoji = density_emoji.get(result.density, "⚪")

        area_lines = ""
        if result.areas:
            for area in result.areas:
                a_emoji = density_emoji.get(area.density, "⚪")
                area_lines += f"  {a_emoji} {area.name.title()}: **{area.density}** (~{area.count} Personen)\n"

        source_note = ""
        if result.source in ("unavailable", "error"):
            source_note = "\n_⚠️ Vision-System offline. Keine Live-Daten verfügbar._"

        content = (
            f"📊 **Aktuelle Auslastung:** {emoji} **{result.density}**\n\n"
            f"👥 Gesamt: **{result.total_count} Personen**\n\n"
        )
        if area_lines:
            content += f"{area_lines}\n"
        content += f"Konfidenz: {result.confidence:.0%}{source_note}"

        return AgentResponse(
            content=content,
            confidence=result.confidence,
            metadata={
                "count": result.total_count,
                "density": result.density,
                "source": result.source,
            },
        )

