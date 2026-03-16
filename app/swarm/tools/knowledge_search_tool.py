"""ARIIA Swarm v3 — KnowledgeSearchTool (SkillTool wrapper)."""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool


class KnowledgeSearchTool(SkillTool):
    """Search tenant knowledge base (ChromaDB) for contextual answers."""

    name = "knowledge_search"
    description = "Search the tenant knowledge base for prices, rules, opening hours, FAQs, and policies."
    required_integrations: frozenset[str] = frozenset()
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term or question (e.g. 'Was kostet Premium?').",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        from app.swarm.tools.knowledge_base import search_knowledge_base

        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, error_message="Parameter 'query' is required.")

        collection_name = f"ariia_knowledge_{context.tenant_slug}"
        try:
            result = search_knowledge_base(query, collection_name=collection_name)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
