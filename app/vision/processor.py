"""ARNI v1.4 – Vision Processor (YOLOv8 Person Detection).

@BACKEND: Sprint 5a, Task 5a.1 + 5a.3
Person counting from video frames with density classification.
Requires ultralytics (YOLOv8). Returns stub data when unavailable or
when VISION_ENABLE_YOLO env var is not set (default: stub mode).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

# Try importing ultralytics (YOLOv8)
try:
    from ultralytics import YOLO  # type: ignore[import-untyped]
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.info("vision.yolo_unavailable", msg="ultralytics not installed, using stub mode")

# Opt-in flag: set VISION_ENABLE_YOLO=1 to enable real inference
_YOLO_ENABLED = os.getenv("VISION_ENABLE_YOLO", "").lower() in ("1", "true", "yes")


DENSITY_THRESHOLDS = {
    "empty": 0,
    "low": 5,
    "medium": 15,
    "high": 30,
    "very_high": 50,
}

PERSON_CLASS_ID = 0  # COCO class ID for 'person'


@dataclass
class AreaResult:
    """Detection result for a specific area."""
    name: str
    count: int
    density: str


@dataclass
class CrowdResult:
    """Aggregated crowd counting result."""
    total_count: int
    density: str
    areas: list[AreaResult] = field(default_factory=list)
    source: str = "yolov8"
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


def classify_density(count: int) -> str:
    """Classify crowd density based on person count.

    Args:
        count: Number of detected persons.

    Returns:
        Density classification string.
    """
    if count >= DENSITY_THRESHOLDS["very_high"]:
        return "very_high"
    elif count >= DENSITY_THRESHOLDS["high"]:
        return "high"
    elif count >= DENSITY_THRESHOLDS["medium"]:
        return "medium"
    elif count >= DENSITY_THRESHOLDS["low"]:
        return "low"
    return "empty"


class VisionProcessor:
    """YOLOv8-based person detection processor.

    Requires ultralytics for real inference.
    Privacy: Frames are NEVER stored. Processing is RAM-only.
    """

    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.5) -> None:
        self._confidence_threshold = confidence_threshold
        self._model: Any = None
        # Stub mode unless VISION_ENABLE_YOLO=1 is explicitly set
        self._stub_mode = not (YOLO_AVAILABLE and _YOLO_ENABLED)

        if not self._stub_mode:
            try:
                self._model = YOLO(model_path)
                logger.info("vision.model_loaded", model=model_path)
            except Exception as e:
                logger.warning("vision.model_load_failed", error=str(e))
                self._stub_mode = True

    @property
    def is_stub(self) -> bool:
        """Whether processor is running in stub mode."""
        return self._stub_mode

    def process_frame(self, frame_data: bytes) -> CrowdResult:
        """Process a single video frame for person detection.

        PRIVACY: frame_data is processed in RAM only.
        No disk writes, no logging of frame content.

        Args:
            frame_data: Raw image bytes (JPEG/PNG).

        Returns:
            CrowdResult with person count and density.
        """
        if self._stub_mode:
            logger.debug("vision.stub_mode", msg="Returning stub crowd result (set VISION_ENABLE_YOLO=1 for real inference)")
            return CrowdResult(
                total_count=3,
                density=classify_density(3),
                areas=[AreaResult(name="main_floor", count=3, density="empty")],
                source="stub",
                confidence=1.0,
            )

        return self._yolo_process(frame_data)

    def _yolo_process(self, frame_data: bytes) -> CrowdResult:
        """Real YOLOv8 inference on frame data."""
        import io
        from PIL import Image  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]

        try:
            image = Image.open(io.BytesIO(frame_data))
            frame_array = np.array(image)

            results = self._model(frame_array, verbose=False, conf=self._confidence_threshold)

            # Count persons (class 0 in COCO)
            person_count = 0
            confidences: list[float] = []
            for result in results:
                for box in result.boxes:
                    if int(box.cls[0]) == PERSON_CLASS_ID:
                        person_count += 1
                        confidences.append(float(box.conf[0]))

            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            # Clear frame from memory explicitly
            del frame_array, image
            frame_data = b""

            logger.info(
                "vision.processed",
                count=person_count,
                density=classify_density(person_count),
                confidence=round(avg_conf, 2),
            )

            return CrowdResult(
                total_count=person_count,
                density=classify_density(person_count),
                source="yolov8",
                confidence=avg_conf,
            )

        except Exception as e:
            logger.error("vision.process_error", error=str(e))
            return CrowdResult(
                total_count=0, density="unknown", source="error",
                confidence=0.0, metadata={"error": str(e)},
            )
