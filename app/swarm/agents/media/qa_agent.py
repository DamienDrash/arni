"""ImageQAAgent: validates images for task suitability, channel compatibility, and visual quality."""
from __future__ import annotations
import base64
import json
import re
from dataclasses import dataclass, field
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()

VISUAL_QA_PROMPT = """You are a professional image quality reviewer for fitness studio marketing materials.
Examine this image carefully and respond ONLY with valid JSON (no markdown fences):
{
  "passed": true or false,
  "score": 1-10,
  "issues": ["list of specific problems found, empty if none"],
  "suggestions": ["actionable prompt hints for regeneration, empty if none"]
}

Check for these problems — ANY single issue means passed=false and score below 6:
- Unnatural or distorted human anatomy: deformed hands/fingers, extra or missing limbs, twisted joints, impossible poses
- Distorted faces: blurred features, asymmetric eyes, missing nose/mouth, unnatural skin texture, uncanny valley appearance
- Merged or duplicated figures: two people blending into one, ghosting artifacts
- Physically impossible body proportions: oversized heads, wrong limb lengths, floating body parts
- Visible AI artifacts: smearing, repeating texture patterns, undefined blobs, glitch areas
- Garbled or unreadable text rendered in the image
- Content inappropriate for professional fitness studio marketing

Scoring guide:
10 = Professional photography quality, no issues
8-9 = High quality, suitable for marketing
6-7 = Acceptable but noticeable minor flaws
4-5 = Clear issues visible to viewer, regenerate recommended
1-3 = Serious defects, must regenerate

If no people are present, focus on overall composition, lighting quality, and brand suitability for a fitness studio.
Be strict: fitness marketing images represent the studio's brand quality."""


@dataclass
class ImageQAResult:
    passed: bool = True
    score: int = 8
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class ImageQAAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "image_qa"

    @property
    def description(self) -> str:
        return "Image QA Agent – Visual quality + channel compatibility validation via GPT-4o Vision"

    async def handle(self, message):
        return None

    async def validate_visual(
        self,
        *,
        image_bytes: bytes,
        channel: str,
        task_context: str = "general",
        tenant_id: int = 0,
    ) -> ImageQAResult:
        """Full QA: technical rules + GPT-4o Vision quality analysis."""
        from app.media.service import MediaService

        # Step 1: Technical metadata (Pillow, no LLM)
        try:
            metadata = MediaService._extract_image_metadata(image_bytes)
        except Exception:
            metadata = {}

        mime_type = "image/png"
        file_size = len(image_bytes)
        orientation = metadata.get("orientation", "")
        width = metadata.get("width", 0)
        height = metadata.get("height", 0)

        # Step 2: Rule-based technical checks
        rule_result = self._validate_rules(
            mime_type=mime_type,
            channel=channel,
            task_context=task_context,
            file_size=file_size,
            orientation=orientation,
            width=width,
            height=height,
        )

        # Step 3: GPT-4o Vision quality check
        vision_result = await self._validate_vision(
            image_bytes=image_bytes,
            tenant_id=tenant_id,
        )

        # Merge: fail if either check fails
        combined = ImageQAResult(
            passed=rule_result.passed and vision_result.passed,
            score=vision_result.score,
            issues=rule_result.issues + vision_result.issues,
            suggestions=rule_result.suggestions + vision_result.suggestions,
        )

        logger.info(
            "image_qa_agent.validated",
            channel=channel,
            task_context=task_context,
            passed=combined.passed,
            score=combined.score,
            issues=combined.issues,
        )
        return combined

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
        """Legacy rule-only validation (no vision). Used as fallback."""
        return self._validate_rules(
            mime_type=mime_type,
            channel=channel,
            task_context=task_context,
            file_size=file_size,
            orientation=orientation,
            width=width,
            height=height,
        )

    def _validate_rules(
        self,
        *,
        mime_type: str,
        channel: str,
        task_context: str,
        file_size: int,
        orientation: str,
        width: int,
        height: int,
    ) -> ImageQAResult:
        result = ImageQAResult()

        if channel == "email":
            if mime_type and "webp" in mime_type.lower():
                result.passed = False
                result.issues.append(
                    "WebP format not supported by most email clients (Outlook). Use PNG or JPEG."
                )
                result.suggestions.append("Regenerate as PNG for email compatibility.")

            if file_size > 5 * 1024 * 1024:
                result.suggestions.append(
                    f"Image size ({file_size / 1024 / 1024:.1f} MB) is large for email. Consider compression."
                )

            if orientation == "portrait":
                result.suggestions.append(
                    "Portrait orientation may not display well as email hero. Landscape (16:9) recommended."
                )

            if width and width < 600:
                result.suggestions.append(
                    f"Image width ({width}px) below recommended 600px minimum for email hero images."
                )

        if task_context == "hero":
            if width and height and width < height:
                result.suggestions.append("Consider a wider aspect ratio for hero banners.")

        if task_context == "thumbnail":
            if orientation == "landscape" and width and height and (width / height) > 2:
                result.suggestions.append(
                    "Very wide images crop awkwardly as thumbnails. Square (1:1) recommended."
                )

        return result

    async def _validate_vision(self, *, image_bytes: bytes, tenant_id: int) -> ImageQAResult:
        """Use GPT-4o Vision to assess visual quality."""
        result = ImageQAResult(passed=True, score=8)

        if not self._llm:
            logger.warning("image_qa_agent.no_llm_for_vision")
            return result

        try:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISUAL_QA_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",   # High detail for anatomy checks
                            },
                        },
                    ],
                }
            ]

            response = await self._llm.chat(
                messages=messages,
                tenant_id=tenant_id,
                max_tokens=500,
                temperature=0.1,
            )

            if not response:
                return result

            # Parse JSON response
            cleaned = re.sub(r'^```[a-z]*\n?', '', response.strip())
            cleaned = re.sub(r'\n?```$', '', cleaned).strip()

            try:
                data = json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group())
                    except (json.JSONDecodeError, ValueError):
                        return result
                else:
                    return result

            score = int(data.get("score", 8))
            passed = bool(data.get("passed", True)) and score >= 6
            issues = [str(i) for i in data.get("issues", []) if i]
            suggestions = [str(s) for s in data.get("suggestions", []) if s]

            result.passed = passed
            result.score = score
            result.issues = issues
            result.suggestions = suggestions

            logger.info(
                "image_qa_agent.vision_complete",
                score=score,
                passed=passed,
                issues=issues,
            )

        except Exception as e:
            logger.warning("image_qa_agent.vision_failed", error=str(e))

        return result
