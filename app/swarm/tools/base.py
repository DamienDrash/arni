"""ARIIA Swarm v3 — SkillTool Abstract Base Class.

All swarm tools inherit from SkillTool and implement execute().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.swarm.contracts import TenantContext, ToolResult


class SkillTool(ABC):
    """Abstract base for all swarm skill tools.

    Subclasses must define:
      - name: unique tool identifier
      - description: human-readable purpose (used in LLM prompts)
      - parameters_schema: JSON Schema dict for the tool's parameters
      - required_integrations: frozenset of integration slugs the tool needs
      - execute(): async method that performs the tool action
    """

    name: str
    description: str
    parameters_schema: dict[str, Any]
    required_integrations: frozenset[str] = frozenset()

    @abstractmethod
    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        """Execute the tool with validated params and tenant context."""
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
