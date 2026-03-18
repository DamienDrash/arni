"""ARIIA Swarm v3 — OdooTool.

Generic Odoo JSON-RPC client for ERP integration.
Supports: member_lookup, contract_info, booking_create, invoice_query.
"""

from __future__ import annotations

import httpx
import structlog
from typing import Any

from app.core.crypto import decrypt_value
from app.swarm.contracts import TenantContext, ToolResult
from app.swarm.tools.base import SkillTool

logger = structlog.get_logger()

DEFAULT_TIMEOUT = 15


class OdooTool(SkillTool):
    """Odoo ERP integration via JSON-RPC.

    Tenant config (from TenantToolConfig.config JSON):
        - odoo_url: Base URL (e.g. "https://erp.example.com")
        - odoo_db: Database name
        - odoo_api_key: Encrypted API key
    """

    name = "odoo"
    description = "Query and manage ERP data in Odoo: members, contracts, bookings, invoices."
    required_integrations = frozenset({"odoo"})
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["member_lookup", "contract_info", "booking_create", "invoice_query"],
                "description": "The Odoo action to perform.",
            },
            "member_id": {
                "type": "string",
                "description": "Member/partner ID or email for lookup.",
            },
            "contract_id": {
                "type": "integer",
                "description": "Contract ID for contract_info.",
            },
            "booking_data": {
                "type": "object",
                "description": "Booking details for booking_create (date, service, etc.).",
            },
            "invoice_filter": {
                "type": "object",
                "description": "Filter criteria for invoice_query (state, date_from, etc.).",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict[str, Any], context: TenantContext) -> ToolResult:
        # Resolve tenant Odoo config
        odoo_url, odoo_db, api_key, err = self._resolve_config(context)
        if err:
            return ToolResult(success=False, error_message=err)

        action = params.get("action")
        try:
            if action == "member_lookup":
                member_id = params.get("member_id", "")
                if not member_id:
                    return ToolResult(success=False, error_message="Parameter 'member_id' is required.")
                domain = ["|", ["email", "=", member_id], ["ref", "=", member_id]]
                result = await self._jsonrpc_call(
                    odoo_url, odoo_db, api_key,
                    model="res.partner",
                    method="search_read",
                    args=[domain],
                    kwargs={"fields": ["id", "name", "email", "phone", "ref", "active"], "limit": 5},
                )
                return ToolResult(success=True, data=result)

            elif action == "contract_info":
                contract_id = params.get("contract_id")
                if not contract_id:
                    return ToolResult(success=False, error_message="Parameter 'contract_id' is required.")
                result = await self._jsonrpc_call(
                    odoo_url, odoo_db, api_key,
                    model="sale.order",
                    method="read",
                    args=[[int(contract_id)]],
                    kwargs={"fields": ["id", "name", "state", "date_order", "amount_total", "partner_id"]},
                )
                return ToolResult(success=True, data=result)

            elif action == "booking_create":
                booking_data = params.get("booking_data", {})
                if not booking_data:
                    return ToolResult(success=False, error_message="Parameter 'booking_data' is required.")
                result = await self._jsonrpc_call(
                    odoo_url, odoo_db, api_key,
                    model="calendar.event",
                    method="create",
                    args=[booking_data],
                )
                return ToolResult(success=True, data={"event_id": result})

            elif action == "invoice_query":
                inv_filter = params.get("invoice_filter", {})
                domain: list = [["move_type", "=", "out_invoice"]]
                if inv_filter.get("state"):
                    domain.append(["state", "=", inv_filter["state"]])
                if inv_filter.get("partner_id"):
                    domain.append(["partner_id", "=", int(inv_filter["partner_id"])])
                result = await self._jsonrpc_call(
                    odoo_url, odoo_db, api_key,
                    model="account.move",
                    method="search_read",
                    args=[domain],
                    kwargs={"fields": ["id", "name", "state", "amount_total", "invoice_date", "partner_id"], "limit": 20},
                )
                return ToolResult(success=True, data=result)

            else:
                return ToolResult(success=False, error_message=f"Unknown action: {action}")

        except httpx.TimeoutException:
            return ToolResult(success=False, error_message=f"Odoo request timed out after {DEFAULT_TIMEOUT}s.")
        except httpx.ConnectError:
            return ToolResult(success=False, error_message="Could not connect to Odoo server.")
        except Exception as e:
            logger.error("odoo.execute_failed", action=action, error=str(e))
            return ToolResult(success=False, error_message=f"Odoo error: {e}")

    @staticmethod
    def _resolve_config(context: TenantContext) -> tuple[str, str, str, str | None]:
        """Extract Odoo connection details from tenant settings.

        Returns: (odoo_url, odoo_db, api_key, error_message)
        """
        settings = context.settings or {}
        odoo_url = settings.get("odoo_url", "")
        odoo_db = settings.get("odoo_db", "")
        api_key_enc = settings.get("odoo_api_key", "")

        if not odoo_url:
            return "", "", "", "Odoo URL not configured for this tenant."
        if not odoo_db:
            return "", "", "", "Odoo database not configured for this tenant."

        api_key = ""
        if api_key_enc:
            try:
                api_key = decrypt_value(api_key_enc)
            except Exception:
                return "", "", "", "Failed to decrypt Odoo API key."

        return odoo_url, odoo_db, api_key, None

    @staticmethod
    async def _jsonrpc_call(
        odoo_url: str,
        odoo_db: str,
        api_key: str,
        *,
        model: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> Any:
        """Execute an Odoo JSON-RPC call."""
        import json

        endpoint = f"{odoo_url.rstrip('/')}/jsonrpc"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    odoo_db,
                    2,  # uid (API key auth uses uid=2 by convention)
                    api_key,
                    model,
                    method,
                    args or [],
                    kwargs or {},
                ],
            },
            "id": 1,
        }

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                err_msg = data["error"].get("message", str(data["error"]))
                raise RuntimeError(f"Odoo RPC error: {err_msg}")

            return data.get("result")
