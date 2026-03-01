"""ARIIA v2.0 – HubSpot CRM Integration Adapter.

@ARCH: Phase 2, Sprint 5 – CRM & E-Commerce
Concrete adapter for HubSpot CRM API v3 integration.

Supported Capabilities:
  - crm.contact.search   → Search HubSpot contacts
  - crm.contact.create   → Create a new contact
  - crm.contact.update   → Update an existing contact
  - crm.deal.list        → List deals
  - crm.deal.create      → Create a new deal
  - crm.company.search   → Search companies
  - crm.ticket.create    → Create a support ticket
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx
import structlog

from app.integrations.adapters.base import BaseAdapter, AdapterResult

logger = structlog.get_logger()


class HubSpotAdapter(BaseAdapter):
    """Adapter for HubSpot CRM API v3 integration."""

    integration_id = "hubspot"
    display_name = "HubSpot"
    description = "CRM-Integration für HubSpot: Kontakte, Deals, Unternehmen und Tickets verwalten."
    version = "1.0.0"

    supported_capabilities = {
        "crm.contact.search",
        "crm.contact.create",
        "crm.contact.update",
        "crm.deal.list",
        "crm.deal.create",
        "crm.company.search",
        "crm.ticket.create",
    }

    BASE_URL = "https://api.hubapi.com"

    def __init__(self):
        super().__init__()
        self._clients: dict[int, dict] = {}

    def configure_tenant(self, tenant_id: int, access_token: str):
        """Configure HubSpot credentials for a tenant."""
        self._clients[tenant_id] = {"access_token": access_token}
        logger.info("hubspot.configured", tenant_id=tenant_id)

    def _get_config(self, tenant_id: int) -> dict:
        config = self._clients.get(tenant_id)
        if not config:
            raise ValueError(f"HubSpot nicht konfiguriert für Tenant {tenant_id}")
        return config

    # ── Core execute ─────────────────────────────────────────────

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs) -> AdapterResult:
        dispatch = {
            "crm.contact.search": self._contact_search,
            "crm.contact.create": self._contact_create,
            "crm.contact.update": self._contact_update,
            "crm.deal.list": self._deal_list,
            "crm.deal.create": self._deal_create,
            "crm.company.search": self._company_search,
            "crm.ticket.create": self._ticket_create,
        }

        handler = dispatch.get(capability_id)
        if not handler:
            return AdapterResult(success=False, error=f"Capability '{capability_id}' not supported", error_code="UNSUPPORTED_CAPABILITY")

        try:
            return await handler(tenant_id, **kwargs)
        except ValueError as e:
            return AdapterResult(success=False, error=str(e), error_code="NOT_CONFIGURED")
        except httpx.HTTPStatusError as e:
            return AdapterResult(success=False, error=f"HubSpot API Fehler: {e.response.status_code}", error_code=f"HUBSPOT_HTTP_{e.response.status_code}")
        except httpx.RequestError as e:
            return AdapterResult(success=False, error=f"Verbindungsfehler: {str(e)}", error_code="HUBSPOT_REQUEST_FAILED")
        except Exception as e:
            logger.exception("hubspot.execute_failed", capability=capability_id, tenant_id=tenant_id)
            return AdapterResult(success=False, error=str(e), error_code="HUBSPOT_INTERNAL_ERROR")

    async def _hs_request(self, tenant_id: int, method: str, endpoint: str, params: dict | None = None, json_data: dict | None = None) -> dict | list:
        config = self._get_config(tenant_id)
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {config['access_token']}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, headers=headers, params=params, json=json_data)
            resp.raise_for_status()
            return resp.json()

    # ── Contacts ─────────────────────────────────────────────────

    async def _contact_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        email = kwargs.get("email")
        query = kwargs.get("query") or kwargs.get("search", "")
        limit = kwargs.get("limit", 25)

        if email:
            payload = {
                "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
                "properties": ["email", "firstname", "lastname", "phone", "company", "lifecyclestage", "createdate"],
                "limit": limit,
            }
        elif query:
            payload = {
                "query": query,
                "properties": ["email", "firstname", "lastname", "phone", "company", "lifecyclestage", "createdate"],
                "limit": limit,
            }
        else:
            payload = {
                "properties": ["email", "firstname", "lastname", "phone", "company", "lifecyclestage", "createdate"],
                "limit": limit,
            }

        data = await self._hs_request(tenant_id, "POST", "/crm/v3/objects/contacts/search", json_data=payload)
        contacts = [
            {
                "id": c.get("id"),
                "email": c.get("properties", {}).get("email"),
                "first_name": c.get("properties", {}).get("firstname"),
                "last_name": c.get("properties", {}).get("lastname"),
                "phone": c.get("properties", {}).get("phone"),
                "company": c.get("properties", {}).get("company"),
                "lifecycle_stage": c.get("properties", {}).get("lifecyclestage"),
                "created_at": c.get("properties", {}).get("createdate"),
            }
            for c in data.get("results", [])
        ]
        return AdapterResult(success=True, data=contacts, metadata={"total": data.get("total", len(contacts))})

    async def _contact_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        email = kwargs.get("email")
        if not email:
            return AdapterResult(success=False, error="Parameter 'email' ist erforderlich", error_code="MISSING_PARAM")

        properties = {"email": email}
        if kwargs.get("first_name"):
            properties["firstname"] = kwargs["first_name"]
        if kwargs.get("last_name"):
            properties["lastname"] = kwargs["last_name"]
        if kwargs.get("phone"):
            properties["phone"] = kwargs["phone"]
        if kwargs.get("company"):
            properties["company"] = kwargs["company"]
        if kwargs.get("lifecycle_stage"):
            properties["lifecyclestage"] = kwargs["lifecycle_stage"]

        data = await self._hs_request(tenant_id, "POST", "/crm/v3/objects/contacts", json_data={"properties": properties})
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "email": data.get("properties", {}).get("email"),
            "message": "Kontakt erfolgreich erstellt",
        })

    async def _contact_update(self, tenant_id: int, **kwargs) -> AdapterResult:
        contact_id = kwargs.get("contact_id")
        if not contact_id:
            return AdapterResult(success=False, error="Parameter 'contact_id' ist erforderlich", error_code="MISSING_PARAM")

        properties = {}
        for field, hs_field in [("email", "email"), ("first_name", "firstname"), ("last_name", "lastname"), ("phone", "phone"), ("company", "company"), ("lifecycle_stage", "lifecyclestage")]:
            if kwargs.get(field) is not None:
                properties[hs_field] = kwargs[field]

        if not properties:
            return AdapterResult(success=False, error="Mindestens eine Eigenschaft zum Aktualisieren ist erforderlich", error_code="MISSING_PARAM")

        data = await self._hs_request(tenant_id, "PATCH", f"/crm/v3/objects/contacts/{contact_id}", json_data={"properties": properties})
        return AdapterResult(success=True, data={"id": data.get("id"), "message": "Kontakt erfolgreich aktualisiert"})

    # ── Deals ────────────────────────────────────────────────────

    async def _deal_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        limit = kwargs.get("limit", 25)
        params = {
            "limit": limit,
            "properties": "dealname,amount,dealstage,pipeline,closedate,createdate",
        }

        data = await self._hs_request(tenant_id, "GET", "/crm/v3/objects/deals", params=params)
        deals = [
            {
                "id": d.get("id"),
                "name": d.get("properties", {}).get("dealname"),
                "amount": d.get("properties", {}).get("amount"),
                "stage": d.get("properties", {}).get("dealstage"),
                "pipeline": d.get("properties", {}).get("pipeline"),
                "close_date": d.get("properties", {}).get("closedate"),
                "created_at": d.get("properties", {}).get("createdate"),
            }
            for d in data.get("results", [])
        ]
        return AdapterResult(success=True, data=deals, metadata={"count": len(deals)})

    async def _deal_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        deal_name = kwargs.get("deal_name") or kwargs.get("name")
        if not deal_name:
            return AdapterResult(success=False, error="Parameter 'deal_name' ist erforderlich", error_code="MISSING_PARAM")

        properties = {"dealname": deal_name}
        if kwargs.get("amount"):
            properties["amount"] = str(kwargs["amount"])
        if kwargs.get("stage"):
            properties["dealstage"] = kwargs["stage"]
        if kwargs.get("pipeline"):
            properties["pipeline"] = kwargs["pipeline"]
        if kwargs.get("close_date"):
            properties["closedate"] = kwargs["close_date"]

        data = await self._hs_request(tenant_id, "POST", "/crm/v3/objects/deals", json_data={"properties": properties})
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "name": data.get("properties", {}).get("dealname"),
            "message": "Deal erfolgreich erstellt",
        })

    # ── Companies ────────────────────────────────────────────────

    async def _company_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        query = kwargs.get("query") or kwargs.get("search") or kwargs.get("name", "")
        domain = kwargs.get("domain")
        limit = kwargs.get("limit", 25)

        if domain:
            payload = {
                "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "EQ", "value": domain}]}],
                "properties": ["name", "domain", "industry", "city", "country", "numberofemployees", "annualrevenue"],
                "limit": limit,
            }
        elif query:
            payload = {
                "query": query,
                "properties": ["name", "domain", "industry", "city", "country", "numberofemployees", "annualrevenue"],
                "limit": limit,
            }
        else:
            payload = {
                "properties": ["name", "domain", "industry", "city", "country", "numberofemployees", "annualrevenue"],
                "limit": limit,
            }

        data = await self._hs_request(tenant_id, "POST", "/crm/v3/objects/companies/search", json_data=payload)
        companies = [
            {
                "id": c.get("id"),
                "name": c.get("properties", {}).get("name"),
                "domain": c.get("properties", {}).get("domain"),
                "industry": c.get("properties", {}).get("industry"),
                "city": c.get("properties", {}).get("city"),
                "country": c.get("properties", {}).get("country"),
                "employees": c.get("properties", {}).get("numberofemployees"),
                "revenue": c.get("properties", {}).get("annualrevenue"),
            }
            for c in data.get("results", [])
        ]
        return AdapterResult(success=True, data=companies, metadata={"total": data.get("total", len(companies))})

    # ── Tickets ──────────────────────────────────────────────────

    async def _ticket_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        subject = kwargs.get("subject")
        if not subject:
            return AdapterResult(success=False, error="Parameter 'subject' ist erforderlich", error_code="MISSING_PARAM")

        properties = {"subject": subject}
        if kwargs.get("content"):
            properties["content"] = kwargs["content"]
        if kwargs.get("priority"):
            properties["hs_ticket_priority"] = kwargs["priority"]
        if kwargs.get("pipeline"):
            properties["hs_pipeline"] = kwargs["pipeline"]
        if kwargs.get("stage"):
            properties["hs_pipeline_stage"] = kwargs["stage"]

        data = await self._hs_request(tenant_id, "POST", "/crm/v3/objects/tickets", json_data={"properties": properties})
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "subject": data.get("properties", {}).get("subject"),
            "message": "Ticket erfolgreich erstellt",
        })

    # ── Health Check ─────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        try:
            data = await self._hs_request(tenant_id, "GET", "/crm/v3/objects/contacts", params={"limit": 1})
            return AdapterResult(success=True, data={"status": "healthy", "contacts_accessible": True})
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
