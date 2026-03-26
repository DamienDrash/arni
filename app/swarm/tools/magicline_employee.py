"""ARIIA Swarm v3 — MagiclineEmployeeTool.

Handles employee-related Magicline operations:
get_employee_list, get_employee.
"""

from __future__ import annotations

from typing import Any

from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool
from app.swarm.tools.magicline import get_employee_list, get_employee


class MagiclineEmployeeTool(SkillTool):
    """Employee operations: list all staff, get individual employee details."""

    name = "magicline_employee"
    description = (
        "Retrieve Magicline employee/trainer information: list all staff members "
        "with their roles and competences, or get details for a specific employee."
    )
    required_integrations = frozenset({"magicline"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_employee_list", "get_employee"],
                "description": (
                    "'get_employee_list' — list all employees with roles and competences.\n"
                    "'get_employee' — detailed profile for a specific employee (requires employee_id)."
                ),
            },
            "employee_id": {
                "type": "integer",
                "description": "Magicline employee ID (for get_employee).",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        action = params.get("action")
        tenant_id = context.tenant_id

        try:
            if action == "get_employee_list":
                result = get_employee_list(tenant_id=tenant_id)

            elif action == "get_employee":
                employee_id = params.get("employee_id")
                if not employee_id:
                    return ToolResult(success=False, error_message="Parameter 'employee_id' is required.")
                result = get_employee(int(employee_id), tenant_id=tenant_id)

            else:
                return ToolResult(success=False, error_message=f"Unknown action: {action}")

            is_error = result.startswith("Error:") or "Fehler" in result
            return ToolResult(success=not is_error, data=result, error_message=result if is_error else None)

        except Exception as e:
            return ToolResult(success=False, error_message=str(e))
