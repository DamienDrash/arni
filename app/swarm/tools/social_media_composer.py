"""ARIIA Swarm v3 — SocialMediaComposerTool.

LLM-based social media post composer with platform-specific formatting.
"""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool


class SocialMediaComposerTool(SkillTool):
    """Create social media post text with hashtags, tailored to platform and tone."""

    name = "social_media_composer"
    description = "Generate social media post text with hashtags for a specific platform and tone."
    required_integrations = frozenset({"social_media"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic or subject of the post.",
            },
            "platform": {
                "type": "string",
                "enum": ["instagram", "facebook", "linkedin", "tiktok"],
                "description": "Target social media platform.",
            },
            "tone": {
                "type": "string",
                "description": "Desired tone (e.g. 'motivational', 'informative', 'casual', 'professional').",
            },
        },
        "required": ["topic", "platform"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        topic = params.get("topic", "")
        platform = params.get("platform", "instagram")
        tone = params.get("tone", "motivational")

        if not topic:
            return ToolResult(success=False, error_message="Parameter 'topic' is required.")

        # Platform-specific constraints
        platform_config = {
            "instagram": {"max_chars": 2200, "hashtag_count": 15, "emoji_level": "high"},
            "facebook": {"max_chars": 500, "hashtag_count": 3, "emoji_level": "medium"},
            "linkedin": {"max_chars": 700, "hashtag_count": 5, "emoji_level": "low"},
            "tiktok": {"max_chars": 300, "hashtag_count": 8, "emoji_level": "high"},
        }
        config = platform_config.get(platform, platform_config["instagram"])

        # Build LLM prompt for post generation
        prompt = (
            f"Create a {tone} social media post for {platform} about: {topic}\n\n"
            f"Requirements:\n"
            f"- Max {config['max_chars']} characters\n"
            f"- Include {config['hashtag_count']} relevant hashtags\n"
            f"- Emoji usage: {config['emoji_level']}\n"
            f"- Tenant: {context.tenant_slug}\n"
            f"- Language: German\n\n"
            f"Return ONLY the post text with hashtags, no explanation."
        )

        # Return the prompt as data for the agent to process via LLM
        return ToolResult(
            success=True,
            data={
                "prompt": prompt,
                "platform": platform,
                "config": config,
                "topic": topic,
                "tone": tone,
            },
        )
