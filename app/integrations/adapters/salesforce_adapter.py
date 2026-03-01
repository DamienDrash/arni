"""ARIIA v2.0 – Salesforce CRM Integration Adapter.

@ARCH: Phase 2, Sprint 5 – CRM & E-Commerce
Concrete adapter for Salesforce REST API v66.0 integration.

Supported Capabilities:
  - crm.contact.search   → Search Salesforce contacts
  - crm.contact.create   → Create a new contact
  - crm.contact.update   → Update an existing contact
  - crm.lead.create      → Create a new lead
  - crm.opportunity.list → List opportunities
  - crm.case.create      → Create a support case
  - crm.soql.query       → Execute a SOQL query
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx
import structlog

from app.integrations.adapters.base import BaseAdapter, AdapterResult

logger = structlog.get_logger()


class SalesforceAdapter(BaseAdapter):
    """Adapter for Salesforce REST API v66.0 integration."""

    integration_id = "salesforce"
    display_name = "Salesforce"
    description = "Enterprise-CRM-Integration für Salesforce: Kontakte, Leads, Opportunities, Cases und SOQL-Abfragen."
    version = "1.0.0"

    supported_capabilities = {
        "crm.contact.search",
        "crm.contact.create",
        "crm.contact.update",
        "crm.lead.create",
        "crm.opportunity.list",
        "crm.case.create",
        "crm.soql.query",
    }

    API_VERSION = "v66.0"

    def __init__(self):
        super().__init__()
        self._clients: dict[int, dict] = {}

    def configure_tenant(self, tenant_id: int, instance_url: str, access_token: str):
        """Configure Salesforce credentials for a tenant.

        Args:
            tenant_id: The tenant ID.
            instance_url: Salesforce instance URL (e.g., https://mycompany.salesforce.com).
            access_token: OAuth 2.0 access token.
        """
        base = instance_url.rstrip("/")
        self._clients[tenant_id] = {
            "instance_url": base,
            "access_token": access_token,
            "base_url": f"{base}/services/data/{self.API_VERSION}",
        }
        logger.info("salesforce.configured", tenant_id=tenant_id, instance_url=base)

    def _get_config(self, tenant_id: int) -> dict:
        config = self._clients.get(tenant_id)
        if not config:
            raise ValueError(f"Salesforce nicht konfiguriert für Tenant {tenant_id}")
        return config

    # ── Core execute ─────────────────────────────────────────────

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs) -> AdapterResult:
        dispatch = {
            "crm.contact.search": self._contact_search,
            "crm.contact.create": self._contact_create,
            "crm.contact.update": self._contact_update,
            "crm.lead.create": self._lead_create,
            "crm.opportunity.list": self._opportunity_list,
            "crm.case.create": self._case_create,
            "crm.soql.query": self._soql_query,
        }

        handler = dispatch.get(capability_id)
        if not handler:
            return AdapterResult(success=False, error=f"Capability '{capability_id}' not supported", error_code="UNSUPPORTED_CAPABILITY")

        try:
            return await handler(tenant_id, **kwargs)
        except ValueError as e:
            return AdapterResult(success=False, error=str(e), error_code="NOT_CONFIGURED")
        except httpx.HTTPStatusError as e:
            return AdapterResult(success=False, error=f"Salesforce API Fehler: {e.response.status_code}", error_code=f"SALESFORCE_HTTP_{e.response.status_code}")
        except httpx.RequestError as e:
            return AdapterResult(success=False, error=f"Verbindungsfehler: {str(e)}", error_code="SALESFORCE_REQUEST_FAILED")
        except Exception as e:
            logger.exception("salesforce.execute_failed", capability=capability_id, tenant_id=tenant_id)
            return AdapterResult(success=False, error=str(e), error_code="SALESFORCE_INTERNAL_ERROR")

    async def _sf_request(self, tenant_id: int, method: str, endpoint: str, params: dict | None = None, json_data: dict | None = None) -> dict | list:
        config = self._get_config(tenant_id)
        url = f"{config['base_url']}{endpoint}"
        headers = {
            "Authorization": f"Bearer {config['access_token']}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, headers=headers, params=params, json=json_data)
            resp.raise_for_status()
            if resp.status_code == 204:
                return {}
            return resp.json()

    # ── Contacts ─────────────────────────────────────────────────

    async def _contact_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        email = kwargs.get("email")
        name = kwargs.get("name") or kwargs.get("query") or kwargs.get("search", "")
        limit = kwargs.get("limit", 25)

        if email:
            soql = f"SELECT Id, FirstName, LastName, Email, Phone, AccountId, Title, Department FROM Contact WHERE Email = '{email}' LIMIT {limit}"
        elif name:
            soql = f"SELECT Id, FirstName, LastName, Email, Phone, AccountId, Title, Department FROM Contact WHERE Name LIKE '%{name}%' LIMIT {limit}"
        else:
            soql = f"SELECT Id, FirstName, LastName, Email, Phone, AccountId, Title, Department FROM Contact ORDER BY CreatedDate DESC LIMIT {limit}"

        data = await self._sf_request(tenant_id, "GET", "/query", params={"q": soql})
        contacts = [
            {
                "id": r.get("Id"),
                "first_name": r.get("FirstName"),
                "last_name": r.get("LastName"),
                "email": r.get("Email"),
                "phone": r.get("Phone"),
                "account_id": r.get("AccountId"),
                "title": r.get("Title"),
                "department": r.get("Department"),
            }
            for r in data.get("records", [])
        ]
        return AdapterResult(success=True, data=contacts, metadata={"total": data.get("totalSize", len(contacts))})

    async def _contact_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        last_name = kwargs.get("last_name")
        if not last_name:
            return AdapterResult(success=False, error="Parameter 'last_name' ist erforderlich (Salesforce Pflichtfeld)", error_code="MISSING_PARAM")

        payload: dict[str, Any] = {"LastName": last_name}
        if kwargs.get("first_name"):
            payload["FirstName"] = kwargs["first_name"]
        if kwargs.get("email"):
            payload["Email"] = kwargs["email"]
        if kwargs.get("phone"):
            payload["Phone"] = kwargs["phone"]
        if kwargs.get("title"):
            payload["Title"] = kwargs["title"]
        if kwargs.get("account_id"):
            payload["AccountId"] = kwargs["account_id"]
        if kwargs.get("department"):
            payload["Department"] = kwargs["department"]

        data = await self._sf_request(tenant_id, "POST", "/sobjects/Contact", json_data=payload)
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "success": data.get("success"),
            "message": "Kontakt erfolgreich erstellt",
        })

    async def _contact_update(self, tenant_id: int, **kwargs) -> AdapterResult:
        contact_id = kwargs.get("contact_id")
        if not contact_id:
            return AdapterResult(success=False, error="Parameter 'contact_id' ist erforderlich", error_code="MISSING_PARAM")

        payload: dict[str, Any] = {}
        field_map = {
            "first_name": "FirstName", "last_name": "LastName", "email": "Email",
            "phone": "Phone", "title": "Title", "department": "Department",
            "account_id": "AccountId",
        }
        for py_field, sf_field in field_map.items():
            if kwargs.get(py_field) is not None:
                payload[sf_field] = kwargs[py_field]

        if not payload:
            return AdapterResult(success=False, error="Mindestens ein Feld zum Aktualisieren ist erforderlich", error_code="MISSING_PARAM")

        await self._sf_request(tenant_id, "PATCH", f"/sobjects/Contact/{contact_id}", json_data=payload)
        return AdapterResult(success=True, data={"id": contact_id, "message": "Kontakt erfolgreich aktualisiert"})

    # ── Leads ────────────────────────────────────────────────────

    async def _lead_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        last_name = kwargs.get("last_name")
        company = kwargs.get("company")
        if not last_name or not company:
            return AdapterResult(success=False, error="Parameter 'last_name' und 'company' sind erforderlich", error_code="MISSING_PARAM")

        payload: dict[str, Any] = {"LastName": last_name, "Company": company}
        if kwargs.get("first_name"):
            payload["FirstName"] = kwargs["first_name"]
        if kwargs.get("email"):
            payload["Email"] = kwargs["email"]
        if kwargs.get("phone"):
            payload["Phone"] = kwargs["phone"]
        if kwargs.get("title"):
            payload["Title"] = kwargs["title"]
        if kwargs.get("status"):
            payload["Status"] = kwargs["status"]
        if kwargs.get("source"):
            payload["LeadSource"] = kwargs["source"]

        data = await self._sf_request(tenant_id, "POST", "/sobjects/Lead", json_data=payload)
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "success": data.get("success"),
            "message": "Lead erfolgreich erstellt",
        })

    # ── Opportunities ────────────────────────────────────────────

    async def _opportunity_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        limit = kwargs.get("limit", 25)
        stage = kwargs.get("stage")

        soql = "SELECT Id, Name, Amount, StageName, CloseDate, Probability, AccountId, CreatedDate FROM Opportunity"
        if stage:
            soql += f" WHERE StageName = '{stage}'"
        soql += f" ORDER BY CreatedDate DESC LIMIT {limit}"

        data = await self._sf_request(tenant_id, "GET", "/query", params={"q": soql})
        opportunities = [
            {
                "id": r.get("Id"),
                "name": r.get("Name"),
                "amount": r.get("Amount"),
                "stage": r.get("StageName"),
                "close_date": r.get("CloseDate"),
                "probability": r.get("Probability"),
                "account_id": r.get("AccountId"),
                "created_at": r.get("CreatedDate"),
            }
            for r in data.get("records", [])
        ]
        return AdapterResult(success=True, data=opportunities, metadata={"total": data.get("totalSize", len(opportunities))})

    # ── Cases ────────────────────────────────────────────────────

    async def _case_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        subject = kwargs.get("subject")
        if not subject:
            return AdapterResult(success=False, error="Parameter 'subject' ist erforderlich", error_code="MISSING_PARAM")

        payload: dict[str, Any] = {"Subject": subject}
        if kwargs.get("description"):
            payload["Description"] = kwargs["description"]
        if kwargs.get("priority"):
            payload["Priority"] = kwargs["priority"]
        if kwargs.get("status"):
            payload["Status"] = kwargs["status"]
        if kwargs.get("origin"):
            payload["Origin"] = kwargs["origin"]
        if kwargs.get("contact_id"):
            payload["ContactId"] = kwargs["contact_id"]
        if kwargs.get("account_id"):
            payload["AccountId"] = kwargs["account_id"]
        if kwargs.get("type"):
            payload["Type"] = kwargs["type"]

        data = await self._sf_request(tenant_id, "POST", "/sobjects/Case", json_data=payload)
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "success": data.get("success"),
            "message": "Case erfolgreich erstellt",
        })

    # ── SOQL Query ───────────────────────────────────────────────

    async def _soql_query(self, tenant_id: int, **kwargs) -> AdapterResult:
        query = kwargs.get("query") or kwargs.get("soql")
        if not query:
            return AdapterResult(success=False, error="Parameter 'query' (SOQL) ist erforderlich", error_code="MISSING_PARAM")

        data = await self._sf_request(tenant_id, "GET", "/query", params={"q": query})
        records = data.get("records", [])
        # Remove Salesforce metadata from records
        cleaned = []
        for r in records:
            clean = {k: v for k, v in r.items() if k != "attributes"}
            cleaned.append(clean)

        return AdapterResult(success=True, data=cleaned, metadata={
            "total": data.get("totalSize", len(cleaned)),
            "done": data.get("done", True),
        })

    # ── Health Check ─────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        try:
            data = await self._sf_request(tenant_id, "GET", "/limits")
            return AdapterResult(success=True, data={
                "status": "healthy",
                "api_version": self.API_VERSION,
                "daily_api_requests_remaining": data.get("DailyApiRequests", {}).get("Remaining"),
            })
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
