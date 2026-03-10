"""ImageQAAgent: validates images for task suitability and channel compatibility."""
from __future__ import annotations
from dataclasses import dataclass, field
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()


@dataclass
class ImageQAResult:
    passed: bool = True
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class ImageQAAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "image_qa"

    @property
    def description(self) -> str:
        return "Image QA Agent – Validates images for channel compatibility and task suitability"

    async def handle(self, message):
        return None

    def validate(
        self,
        *,
        mime_type: str,
        channel: str,
        task_context: str = "general",
        file_size: int = 0,
        orientation: str = "",
        width: int = 0,
        height: int = 0,
    ) -> ImageQAResult:
        """Validate image against channel and task requirements."""
        result = ImageQAResult()

        # Email channel checks
        if channel == "email":
            if mime_type and "webp" in mime_type.lower():
                result.passed = False
                result.issues.append(
                    "WebP format is not supported by most email clients (Outlook). Use PNG or JPEG."
                )
                result.suggestions.append("Regenerate as PNG for maximum email client compatibility.")

            if file_size > 5 * 1024 * 1024:
                result.suggestions.append(
                    f"Image size ({file_size / 1024 / 1024:.1f} MB) is large for email. Consider compression."
                )

            if orientation == "portrait":
                result.suggestions.append(
                    "Portrait orientation may not display well as a hero image in email clients. Landscape (16:9) is recommended."
                )

            if width and width < 600:
                result.suggestions.append(
                    f"Image width ({width}px) is below recommended minimum of 600px for email hero images."
                )

        # Hero context checks
        if task_context == "hero":
            if orientation == "portrait":
                result.suggestions.append(
                    "Hero images typically use landscape orientation (16:9 or wider)."
                )
            if width and height and width < height:
                result.suggestions.append("Consider using a wider aspect ratio for hero banners.")

        # Thumbnail context checks
        if task_context == "thumbnail":
            if orientation == "landscape" and width and height and (width / height) > 2:
                result.suggestions.append(
                    "Very wide images may be cropped awkwardly as thumbnails. Square (1:1) is recommended."
                )

        logger.info(
            "image_qa_agent.validated",
            channel=channel,
            task_context=task_context,
            passed=result.passed,
            issues=len(result.issues),
        )
        return result
