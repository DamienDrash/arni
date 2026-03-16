"""ARIIA Swarm v3 — MemberMemoryTool (SkillTool wrapper)."""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool


class MemberMemoryTool(SkillTool):
    """Store and retrieve per-member conversation memory and preferences."""

    name = "member_memory"
    description = "Search member long-term memory for preferences, history, and personal facts."
    required_integrations: frozenset[str] = frozenset()
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in member memory.",
            },
            "user_identifier": {
                "type": "string",
                "description": "User identifier (phone, email, or member ID).",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        from app.swarm.tools.member_memory import search_member_memory

        query = params.get("query", "")
        user_id = params.get("user_identifier") or context.member_id or ""

        if not query:
            return ToolResult(success=False, error_message="Parameter 'query' is required.")
        if not user_id:
            return ToolResult(success=False, error_message="No user identifier available.")

        try:
            result = search_member_memory(
                user_identifier=user_id,
                query=query,
                tenant_id=context.tenant_id,
            )
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
