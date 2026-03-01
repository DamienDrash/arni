"""ARIIA v2.0 – Native Tool Calling Framework.

@ARCH: Phase 1, Meilenstein 1.4 – Modernes Tool-Calling
Replaces the brittle regex-based TOOL: worker_name("query") pattern
with native LLM function calling (OpenAI tools API).

Benefits:
- Structured, typed tool definitions (JSON Schema)
- No regex parsing of LLM output
- Parallel tool calls supported natively
- Tool results fed back as proper tool messages
- Works with OpenAI, Anthropic, Gemini (via adapter)

Architecture:
- ToolDefinition: Describes a tool's name, description, and parameters
- ToolRegistry: Central registry of all available tools
- ToolExecutor: Executes tool calls and returns results
- The MasterAgent uses these instead of regex parsing
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

import structlog

logger = structlog.get_logger()


# ─── Tool Definition ─────────────────────────────────────────────────────────


@dataclass
class ToolParameter:
    """A single parameter for a tool."""

    name: str
    type: str = "string"  # string, integer, number, boolean, array, object
    description: str = ""
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


@dataclass
class ToolDefinition:
    """Defines a tool that can be called by the LLM.

    This maps to the OpenAI function calling schema:
    {
        "type": "function",
        "function": {
            "name": "...",
            "description": "...",
            "parameters": { ... }
        }
    }
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable[..., Coroutine[Any, Any, str]]] = None

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }

        if required:
            schema["function"]["parameters"]["required"] = required

        return schema


# ─── Tool Call Result ────────────────────────────────────────────────────────


@dataclass
class ToolCallRequest:
    """A tool call requested by the LLM."""

    id: str  # Tool call ID from the API
    name: str
    arguments: dict[str, Any]

    @classmethod
    def from_openai(cls, tool_call: dict[str, Any]) -> "ToolCallRequest":
        """Parse from OpenAI API response format."""
        func = tool_call.get("function", {})
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {"raw": args_str}

        return cls(
            id=tool_call.get("id", ""),
            name=func.get("name", ""),
            arguments=args if isinstance(args, dict) else {"value": args},
        )


@dataclass
class ToolCallResult:
    """Result of executing a tool call."""

    tool_call_id: str
    name: str
    content: str
    success: bool = True
    error: str = ""

    def to_openai_message(self) -> dict[str, Any]:
        """Convert to OpenAI tool message format."""
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


# ─── Tool Registry ──────────────────────────────────────────────────────────


class ToolRegistry:
    """Central registry for all available tools.

    Tools are registered at startup and made available to the LLM
    via their OpenAI-compatible schemas.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool.name in self._tools:
            logger.warning("tool_registry.duplicate", name=tool.name)
        self._tools[tool.name] = tool
        logger.debug("tool_registry.registered", name=tool.name)

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[ToolDefinition]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def get_tools_for_agent(self, agent_name: str) -> list[dict[str, Any]]:
        """Get tools available to a specific agent.

        Currently returns all tools; can be filtered per agent in the future.
        """
        return self.get_openai_tools()


# ─── Tool Executor ───────────────────────────────────────────────────────────


class ToolExecutor:
    """Executes tool calls from LLM responses.

    Handles:
    - Looking up the tool in the registry
    - Calling the handler with parsed arguments
    - Returning structured results
    - Error handling and logging
    """

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def execute(self, call: ToolCallRequest) -> ToolCallResult:
        """Execute a single tool call.

        Args:
            call: The tool call request from the LLM.

        Returns:
            ToolCallResult with the tool's output.
        """
        tool = self._registry.get(call.name)
        if not tool:
            logger.warning("tool_executor.unknown_tool", name=call.name)
            return ToolCallResult(
                tool_call_id=call.id,
                name=call.name,
                content=f"Error: Unknown tool '{call.name}'",
                success=False,
                error=f"Tool '{call.name}' not found in registry",
            )

        if not tool.handler:
            logger.warning("tool_executor.no_handler", name=call.name)
            return ToolCallResult(
                tool_call_id=call.id,
                name=call.name,
                content=f"Error: Tool '{call.name}' has no handler",
                success=False,
                error="No handler registered",
            )

        try:
            logger.info(
                "tool_executor.executing",
                tool=call.name,
                args=list(call.arguments.keys()),
            )
            result = await tool.handler(**call.arguments)
            return ToolCallResult(
                tool_call_id=call.id,
                name=call.name,
                content=str(result),
                success=True,
            )
        except Exception as e:
            logger.error(
                "tool_executor.failed",
                tool=call.name,
                error=str(e),
            )
            return ToolCallResult(
                tool_call_id=call.id,
                name=call.name,
                content=f"Error executing tool '{call.name}': {str(e)}",
                success=False,
                error=str(e),
            )

    async def execute_all(
        self, calls: list[ToolCallRequest]
    ) -> list[ToolCallResult]:
        """Execute multiple tool calls (sequentially for now).

        For parallel execution, use asyncio.gather in the caller.
        """
        results = []
        for call in calls:
            result = await self.execute(call)
            results.append(result)
        return results


# ─── Default Worker Tools ────────────────────────────────────────────────────


def create_worker_tools() -> ToolRegistry:
    """Create the default tool registry with worker agent tools.

    These replace the old TOOL: worker_name("query") pattern.
    Each worker agent is now a proper tool with typed parameters.
    """
    registry = ToolRegistry()

    registry.register(ToolDefinition(
        name="ops_agent",
        description=(
            "Specialist for bookings, courses, trainers, check-ins, and schedules. "
            "Call this tool when the user asks about appointments, class bookings, "
            "cancellations, trainer availability, or check-in history."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The user's request related to operations/bookings",
                required=True,
            ),
            ToolParameter(
                name="action_type",
                type="string",
                description="Type of operation requested",
                required=False,
                enum=["query", "book", "cancel", "reschedule", "check_availability"],
            ),
        ],
    ))

    registry.register(ToolDefinition(
        name="sales_agent",
        description=(
            "Specialist for contracts, pricing, cancellations, upgrades, and membership plans. "
            "Call this tool when the user asks about their contract, pricing, "
            "membership options, or wants to upgrade/downgrade."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The user's request related to sales/contracts",
                required=True,
            ),
        ],
    ))

    registry.register(ToolDefinition(
        name="medic_agent",
        description=(
            "Specialist for health, pain, injuries, and medical advice (with disclaimer). "
            "Call this tool when the user mentions health issues, pain, injuries, "
            "or asks for exercise modifications due to physical conditions."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The user's health-related question or concern",
                required=True,
            ),
        ],
    ))

    registry.register(ToolDefinition(
        name="vision_agent",
        description=(
            "Specialist for gym occupancy, camera analysis, and capacity information. "
            "Call this tool when the user asks about current gym occupancy, "
            "how busy it is, or wants capacity information."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The user's question about occupancy or capacity",
                required=True,
            ),
        ],
    ))

    registry.register(ToolDefinition(
        name="persona_agent",
        description=(
            "The inner personality for smalltalk, general life advice, and motivation. "
            "Call this tool for casual conversation, motivational messages, "
            "or general questions not related to specific gym operations."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The casual/general topic to respond to",
                required=True,
            ),
        ],
    ))

    registry.register(ToolDefinition(
        name="knowledge_base",
        description=(
            "Search the tenant's knowledge base for specific information about "
            "the gym, its services, opening hours, rules, and policies. "
            "Call this tool when you need factual information about the business."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The search query for the knowledge base",
                required=True,
            ),
            ToolParameter(
                name="top_k",
                type="integer",
                description="Number of results to return (default: 3)",
                required=False,
                default=3,
            ),
        ],
    ))

    registry.register(ToolDefinition(
        name="member_memory",
        description=(
            "Retrieve or store information about the current member from long-term memory. "
            "Call this tool to recall past interactions, preferences, or personal details "
            "about the member you're talking to."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="What to look up or store about the member",
                required=True,
            ),
            ToolParameter(
                name="action",
                type="string",
                description="Whether to retrieve or store information",
                required=False,
                enum=["retrieve", "store"],
                default="retrieve",
            ),
        ],
    ))

    return registry


# ─── LLM Response Parsing ───────────────────────────────────────────────────


def parse_tool_calls_from_response(response_data: dict[str, Any]) -> list[ToolCallRequest]:
    """Parse tool calls from an OpenAI-compatible API response.

    Args:
        response_data: The full API response JSON.

    Returns:
        List of ToolCallRequest objects, empty if no tool calls.
    """
    choices = response_data.get("choices", [])
    if not choices:
        return []

    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls", [])

    return [ToolCallRequest.from_openai(tc) for tc in tool_calls]


def has_tool_calls(response_data: dict[str, Any]) -> bool:
    """Check if an API response contains tool calls."""
    choices = response_data.get("choices", [])
    if not choices:
        return False
    message = choices[0].get("message", {})
    return bool(message.get("tool_calls"))


def get_response_content(response_data: dict[str, Any]) -> str:
    """Extract the text content from an API response."""
    choices = response_data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return message.get("content", "") or ""
