"""ARIIA Swarm v3 — SocialMediaSchedulerTool.

Schedule posts via Buffer/Hootsuite API (or configured social media API).
"""

from __future__ import annotations

import httpx
import structlog
from typing import Any

from app.core.crypto import decrypt_value
from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool

logger = structlog.get_logger()


class SocialMediaSchedulerTool(SkillTool):
    """Schedule a social media post for a future time."""

    name = "social_media_scheduler"
    description = "Schedule a social media post for a specific date/time via Buffer or Hootsuite."
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
            "scheduled_at": {
                "type": "string",
                "description": "ISO 8601 datetime for scheduling (e.g. '2026-03-20T14:00:00Z').",
            },
        },
        "required": ["content", "platform", "scheduled_at"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        content = params.get("content", "")
        platform = params.get("platform", "")
        scheduled_at = params.get("scheduled_at", "")

        if not content or not platform or not scheduled_at:
            return ToolResult(success=False, error_message="Parameters 'content', 'platform', and 'scheduled_at' are required.")

        settings = context.settings or {}
        api_url = settings.get("social_media_api_url", "")
        api_key_enc = settings.get("social_media_api_key", "")

        if not api_url:
            return ToolResult(success=False, error_message="Social media API not configured for this tenant.")

        api_key = decrypt_value(api_key_enc) if api_key_enc else ""

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{api_url.rstrip('/')}/schedules",
                    json={
                        "text": content,
                        "platform": platform,
                        "scheduled_at": scheduled_at,
                        "tenant_slug": context.tenant_slug,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

            if response.status_code >= 400:
                return ToolResult(success=False, error_message=f"Scheduling failed (HTTP {response.status_code}).")

            data = response.json() if "application/json" in response.headers.get("content-type", "") else {"status": "scheduled"}
            return ToolResult(success=True, data=data)

        except httpx.TimeoutException:
            return ToolResult(success=False, error_message="Social media API timed out.")
        except Exception as e:
            logger.error("social_scheduler.failed", error=str(e))
            return ToolResult(success=False, error_message=f"Scheduling error: {e}")
