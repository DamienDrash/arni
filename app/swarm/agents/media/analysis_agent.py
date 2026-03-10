"""ImageAnalysisAgent: uses GPT-4o Vision to describe images and extract semantic metadata."""
from __future__ import annotations
import base64
import json
import re
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()

ANALYSIS_PROMPT = """Analyze this image and respond ONLY with valid JSON (no markdown fences) in this exact structure:
{
  "description": "One or two sentences describing what is shown in the image",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "alt_text": "Short accessible description for screen readers",
  "usage_context": "one of: hero, thumbnail, logo, background, product, general",
  "dominant_colors": ["#hex1", "#hex2", "#hex3"],
  "brightness": "one of: light, dark, neutral"
}
Keep tags relevant to fitness studio marketing. Tags in German are preferred."""


class ImageAnalysisAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "image_analysis"

    @property
    def description(self) -> str:
        return "Image Analysis Agent – GPT-4o Vision semantic image description"

    async def handle(self, message):
        return None

    async def describe(self, *, image_bytes: bytes, tenant_id: int) -> dict:
        """Analyze image with GPT-4o Vision. Returns dict with description/tags/alt_text/usage_context/dominant_colors/brightness."""
        if not image_bytes:
            return {}

        try:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ]

            # Call LLM directly with higher token limit for vision response
            if not self._llm:
                logger.warning("image_analysis_agent.no_llm")
                return {}

            response = await self._llm.chat(
                messages=messages,
                tenant_id=tenant_id,
                max_tokens=800,
                temperature=0.1,
            )

            if not response:
                return {}

            # Strip markdown fences if present
            cleaned = re.sub(r'^```[a-z]*\n?', '', response.strip())
            cleaned = re.sub(r'\n?```$', '', cleaned).strip()

            try:
                return json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                # Try to find JSON object
                match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except (json.JSONDecodeError, ValueError):
                        pass
            return {}

        except Exception as e:
            logger.warning("image_analysis_agent.failed", error=str(e), tenant_id=tenant_id)
            return {}
