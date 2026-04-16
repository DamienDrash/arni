"""ARIIA Swarm v3 — DynamicToolProxy.

HTTP-based proxy for custom tenant integrations. Non-system tools
with an endpoint_url in their tenant config are executed as HTTP
POST calls to the configured endpoint.
"""

from __future__ import annotations

import httpx
import structlog
from typing import Any

from app.core.crypto import decrypt_value
from app.domains.ai.models import ToolDefinition
from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool

logger = structlog.get_logger()

DEFAULT_TIMEOUT = 10


class DynamicToolProxy(SkillTool):
    """Proxy that forwards tool calls to an external HTTP endpoint.

    Used by the DynamicAgentLoader for tools where is_system=False
    and the tenant config contains an endpoint_url.
    """

    def __init__(self, tool_def: ToolDefinition, tenant_config: dict[str, Any]) -> None:
        self.name = tool_def.id
        self.description = tool_def.description or tool_def.display_name
        self.parameters_schema = self._parse_schema(tool_def.config_schema)
        self.required_integrations = (
            frozenset({tool_def.required_integration})
            if tool_def.required_integration
            else frozenset()
        )
        self._endpoint_url: str = tenant_config.get("endpoint_url", "")
        self._api_key_encrypted: str = tenant_config.get("api_key", "")
        self._timeout: int = int(tenant_config.get("timeout_seconds", DEFAULT_TIMEOUT))
        self._extra_headers: dict[str, str] = tenant_config.get("headers", {})

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        if not self._endpoint_url:
            return ToolResult(success=False, error_message="No endpoint_url configured for this tool.")

        # Decrypt API key
        api_key = ""
        if self._api_key_encrypted:
            try:
                api_key = decrypt_value(self._api_key_encrypted)
            except Exception as e:
                logger.error("dynamic_tool.decrypt_failed", tool=self.name, error=str(e))
                return ToolResult(success=False, error_message="Failed to decrypt API key.")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(self._extra_headers)

        body = {
            "params": params,
            "tenant_id": context.tenant_id,
            "tenant_slug": context.tenant_slug,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._endpoint_url,
                    json=body,
                    headers=headers,
                )

            if response.status_code >= 500:
                logger.error(
                    "dynamic_tool.server_error",
                    tool=self.name,
                    status=response.status_code,
                )
                return ToolResult(
                    success=False,
                    error_message=f"Remote service error (HTTP {response.status_code}).",
                )

            if response.status_code >= 400:
                return ToolResult(
                    success=False,
                    error_message=f"Request rejected (HTTP {response.status_code}): {response.text[:200]}",
                )

            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
            return ToolResult(success=True, data=data)

        except httpx.TimeoutException:
            return ToolResult(success=False, error_message=f"Request timed out after {self._timeout}s.")
        except httpx.ConnectError:
            return ToolResult(success=False, error_message="Could not connect to remote endpoint.")
        except Exception as e:
            logger.error("dynamic_tool.unexpected_error", tool=self.name, error=str(e))
            return ToolResult(success=False, error_message=f"Unexpected error: {e}")

    @staticmethod
    def _parse_schema(config_schema: str | None) -> dict[str, Any]:
        """Parse JSON Schema from the ToolDefinition config_schema field."""
        if not config_schema:
            return {"type": "object", "properties": {}}
        try:
            import json
            return json.loads(config_schema)
        except (ValueError, TypeError):
            return {"type": "object", "properties": {}}
