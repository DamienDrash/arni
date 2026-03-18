"""ARIIA Swarm v3 — SocialMediaPublisherTool.

Publish social media posts immediately via configured API.
"""

from __future__ import annotations

import httpx
import structlog
from typing import Any

from app.core.crypto import decrypt_value
from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool

logger = structlog.get_logger()


class SocialMediaPublisherTool(SkillTool):
    """Publish a social media post immediately."""

    name = "social_media_publisher"
    description = "Publish a social media post immediately to a specific platform."
    required_integrations = frozenset({"social_media"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The post content text.",
            },
            "platform": {
                "type": "string",
                "enum": ["instagram", "facebook", "linkedin", "tiktok"],
                "description": "Target platform.",
            },
            "image_url": {
                "type": "string",
                "description": "Optional image URL to attach to the post.",
            },
        },
        "required": ["content", "platform"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        content = params.get("content", "")
        platform = params.get("platform", "")
        image_url = params.get("image_url")

        if not content or not platform:
            return ToolResult(success=False, error_message="Parameters 'content' and 'platform' are required.")

        settings = context.settings or {}
        api_url = settings.get("social_media_api_url", "")
        api_key_enc = settings.get("social_media_api_key", "")

        if not api_url:
            return ToolResult(success=False, error_message="Social media API not configured for this tenant.")

        api_key = decrypt_value(api_key_enc) if api_key_enc else ""

        body: dict[str, Any] = {
            "text": content,
            "platform": platform,
            "tenant_slug": context.tenant_slug,
            "publish_now": True,
        }
        if image_url:
            body["image_url"] = image_url

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{api_url.rstrip('/')}/publish",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

            if response.status_code >= 400:
                return ToolResult(success=False, error_message=f"Publishing failed (HTTP {response.status_code}).")

            data = response.json() if "application/json" in response.headers.get("content-type", "") else {"status": "published"}
            return ToolResult(success=True, data=data)

        except httpx.TimeoutException:
            return ToolResult(success=False, error_message="Social media API timed out.")
        except Exception as e:
            logger.error("social_publisher.failed", error=str(e))
            return ToolResult(success=False, error_message=f"Publishing error: {e}")
