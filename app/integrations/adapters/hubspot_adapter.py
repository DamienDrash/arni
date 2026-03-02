"""ARIIA v2.0 – HubSpot CRM Integration Adapter.

@ARCH: Contacts-Sync Refactoring
Concrete adapter for HubSpot CRM API v3 integration. Implements both
capability execution (agent runtime) AND contact sync interface.

Contact Sync Data Points:
  - Contact profile: name, email, phone, company, job title, address
  - Lifecycle stage: subscriber → lead → MQL → SQL → opportunity → customer → evangelist
  - Lead status, owner, associated company
  - Custom HubSpot properties → ARIIA custom fields
  - Two-way sync support (HubSpot supports both read and write)

Capabilities (Agent Runtime):
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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.integrations.adapters.base import (
    AdapterResult,
    BaseAdapter,
    ConnectionTestResult,
    NormalizedContact,
    SyncDirection,
    SyncMode,
    SyncResult,
)

logger = structlog.get_logger()

BASE_URL = "https://api.hubapi.com"

# Default HubSpot properties to fetch during contact sync
SYNC_PROPERTIES = [
    "email", "firstname", "lastname", "phone", "mobilephone",
    "company", "jobtitle", "lifecyclestage", "hs_lead_status",
    "address", "city", "zip", "state", "country",
    "website", "hs_object_id", "createdate", "lastmodifieddate",
    "notes_last_updated", "num_associated_deals",
    "hs_email_optout", "hs_analytics_source",
]


class HubSpotAdapter(BaseAdapter):
    """Adapter for HubSpot CRM API v3 integration.

    Supports both capability execution and contact sync.
    """

    @property
    def integration_id(self) -> str:
        return "hubspot"

    @property
    def display_name(self) -> str:
        return "HubSpot"

    @property
    def category(self) -> str:
        return "crm"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "crm.contact.search",
            "crm.contact.create",
            "crm.contact.update",
            "crm.deal.list",
            "crm.deal.create",
            "crm.company.search",
            "crm.ticket.create",
        ]

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        return [SyncDirection.INBOUND, SyncDirection.BIDIRECTIONAL]

    @property
    def supports_incremental_sync(self) -> bool:
        return True  # HubSpot supports recently modified contacts endpoint

    @property
    def supports_webhooks(self) -> bool:
        return True  # HubSpot has webhook subscriptions

    # ── Configuration Schema ─────────────────────────────────────────────

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "fields": [
                {
                    "key": "access_token",
                    "label": "Private App Access Token",
                    "type": "password",
                    "required": True,
                    "help_text": "Erstellen Sie eine Private App unter Settings → Integrations → Private Apps. Benötigte Scopes: crm.objects.contacts.read, crm.objects.contacts.write.",
                },
                {
                    "key": "sync_direction",
                    "label": "Sync-Richtung",
                    "type": "select",
                    "required": False,
                    "default": "inbound",
                    "options": [
                        {"value": "inbound", "label": "Nur Import (HubSpot → ARIIA)"},
                        {"value": "bidirectional", "label": "Zwei-Wege-Sync"},
                    ],
                    "help_text": "Richtung der Kontakt-Synchronisation.",
                },
                {
                    "key": "sync_lifecycle_stages",
                    "label": "Lifecycle Stages synchronisieren",
                    "type": "multiselect",
                    "required": False,
                    "default": ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer", "evangelist"],
                    "options": [
                        {"value": "subscriber", "label": "Subscriber"},
                        {"value": "lead", "label": "Lead"},
                        {"value": "marketingqualifiedlead", "label": "Marketing Qualified Lead"},
                        {"value": "salesqualifiedlead", "label": "Sales Qualified Lead"},
                        {"value": "opportunity", "label": "Opportunity"},
                        {"value": "customer", "label": "Customer"},
                        {"value": "evangelist", "label": "Evangelist"},
                    ],
                    "help_text": "Nur Kontakte mit diesen Lifecycle Stages importieren.",
                },
                {
                    "key": "custom_properties",
                    "label": "Zusätzliche HubSpot Properties",
                    "type": "text",
                    "required": False,
                    "placeholder": "property1, property2, property3",
                    "help_text": "Kommagetrennte Liste zusätzlicher HubSpot-Properties, die als Custom Fields synchronisiert werden sollen.",
                },
            ],
        }

    # ── Helper: HubSpot API Request ──────────────────────────────────────

    @staticmethod
    async def _hs_request(
        token: str,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        timeout: int = 30,
    ) -> httpx.Response:
        """Make an authenticated request to the HubSpot API."""
        url = f"{BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=headers, params=params, json=json_data)
            resp.raise_for_status()
            return resp

    # ── Connection Test ──────────────────────────────────────────────────

    async def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        """Test HubSpot API connection."""
        token = (config.get("access_token") or "").strip()
        if not token:
            return ConnectionTestResult(success=False, message="Access Token ist erforderlich.")

        start = time.monotonic()
        try:
            resp = await self._hs_request(token, "GET", "/crm/v3/objects/contacts", params={"limit": 1})
            latency = (time.monotonic() - start) * 1000
            data = resp.json()
            total = data.get("total", 0)

            # Also check account info
            try:
                acc_resp = await self._hs_request(token, "GET", "/account-info/v3/details")
                acc_data = acc_resp.json()
                portal_id = acc_data.get("portalId", "?")
                return ConnectionTestResult(
                    success=True,
                    message=f"Verbindung erfolgreich. Portal ID: {portal_id}, {total} Kontakte verfügbar.",
                    details={"portal_id": portal_id, "total_contacts": total},
                    latency_ms=latency,
                )
            except Exception:
                return ConnectionTestResult(
                    success=True,
                    message=f"Verbindung erfolgreich. {total} Kontakte verfügbar.",
                    details={"total_contacts": total},
                    latency_ms=latency,
                )
        except httpx.HTTPStatusError as e:
            latency = (time.monotonic() - start) * 1000
            code = e.response.status_code
            if code == 401:
                return ConnectionTestResult(success=False, message="Authentifizierung fehlgeschlagen. Bitte Access Token überprüfen.", latency_ms=latency)
            if code == 403:
                return ConnectionTestResult(success=False, message="Zugriff verweigert. Bitte App-Berechtigungen (Scopes) überprüfen.", latency_ms=latency)
            return ConnectionTestResult(success=False, message=f"HubSpot API-Fehler: {code}", latency_ms=latency)
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=False, message=f"Verbindungsfehler: {str(e)}", latency_ms=latency)

    # ── Contact Sync ─────────────────────────────────────────────────────

    async def get_contacts(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        last_sync_at: Optional[datetime] = None,
        sync_mode: SyncMode = SyncMode.FULL,
    ) -> SyncResult:
        """Fetch contacts from HubSpot CRM API v3."""
        token = (config.get("access_token") or "").strip()
        if not token:
            return SyncResult(success=False, error_message="HubSpot nicht konfiguriert: Access Token fehlt.")

        # Build properties list
        properties = list(SYNC_PROPERTIES)
        custom_props = config.get("custom_properties", "")
        if custom_props:
            for p in custom_props.split(","):
                p = p.strip()
                if p and p not in properties:
                    properties.append(p)

        # Lifecycle stage filter
        allowed_stages = config.get("sync_lifecycle_stages")

        start_time = time.monotonic()
        all_contacts: List[dict] = []

        try:
            if sync_mode == SyncMode.INCREMENTAL and last_sync_at:
                # Use search endpoint with lastmodifieddate filter
                after = "0"
                while True:
                    payload: dict[str, Any] = {
                        "filterGroups": [{
                            "filters": [{
                                "propertyName": "lastmodifieddate",
                                "operator": "GTE",
                                "value": str(int(last_sync_at.timestamp() * 1000)),
                            }],
                        }],
                        "properties": properties,
                        "limit": 100,
                    }
                    if after != "0":
                        payload["after"] = after

                    resp = await self._hs_request(token, "POST", "/crm/v3/objects/contacts/search", json_data=payload)
                    data = resp.json()
                    all_contacts.extend(data.get("results", []))

                    paging = data.get("paging", {}).get("next", {})
                    after = paging.get("after")
                    if not after:
                        break
            else:
                # Full sync via list endpoint
                after = None
                while True:
                    params: dict[str, Any] = {
                        "limit": 100,
                        "properties": ",".join(properties),
                    }
                    if after:
                        params["after"] = after

                    resp = await self._hs_request(token, "GET", "/crm/v3/objects/contacts", params=params)
                    data = resp.json()
                    all_contacts.extend(data.get("results", []))

                    paging = data.get("paging", {}).get("next", {})
                    after = paging.get("after")
                    if not after:
                        break

        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 401:
                return SyncResult(success=False, error_message="HubSpot Authentifizierung fehlgeschlagen.")
            if code == 403:
                return SyncResult(success=False, error_message="HubSpot Zugriff verweigert. Bitte Scopes überprüfen.")
            return SyncResult(success=False, error_message=f"HubSpot API-Fehler: {code}")
        except Exception as e:
            return SyncResult(success=False, error_message=f"HubSpot API-Fehler: {str(e)}")

        # Convert to NormalizedContact
        contacts: List[NormalizedContact] = []
        errors: List[Dict[str, Any]] = []

        for c in all_contacts:
            source_id = str(c.get("id", ""))
            if not source_id:
                continue

            props = c.get("properties", {})

            try:
                # Lifecycle stage filter
                lifecycle = props.get("lifecyclestage", "lead") or "lead"
                if allowed_stages and lifecycle not in allowed_stages:
                    continue

                first_name = str(props.get("firstname") or "").strip()
                last_name = str(props.get("lastname") or "").strip()
                if not first_name and not last_name:
                    email = props.get("email", "")
                    if email:
                        first_name = email.split("@")[0]
                    else:
                        first_name = "HubSpot"
                        last_name = f"Kontakt #{source_id}"

                # Tags
                tags: List[str] = ["hubspot"]
                if lifecycle:
                    tags.append(f"hs:{lifecycle}")

                # Custom fields – collect non-standard properties
                custom_fields: Dict[str, Any] = {}
                if props.get("jobtitle"):
                    custom_fields["jobtitel"] = props["jobtitle"]
                if props.get("hs_lead_status"):
                    custom_fields["lead_status"] = props["hs_lead_status"]
                if props.get("num_associated_deals"):
                    custom_fields["deals_anzahl"] = props["num_associated_deals"]
                if props.get("hs_analytics_source"):
                    custom_fields["akquise_quelle"] = props["hs_analytics_source"]
                if props.get("website"):
                    custom_fields["website"] = props["website"]
                email_optout = props.get("hs_email_optout")
                custom_fields["consent_email"] = email_optout != "true" if email_optout else True

                # Custom properties from config
                if custom_props:
                    for p in custom_props.split(","):
                        p = p.strip()
                        if p and props.get(p) is not None:
                            custom_fields[p] = props[p]

                # Updated at
                updated_at = None
                if props.get("lastmodifieddate"):
                    try:
                        ts = int(props["lastmodifieddate"])
                        updated_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                    except (ValueError, TypeError):
                        try:
                            updated_at = datetime.fromisoformat(props["lastmodifieddate"].replace("Z", "+00:00"))
                        except (ValueError, AttributeError):
                            pass

                nc = NormalizedContact(
                    external_id=source_id,
                    source="hubspot",
                    first_name=first_name,
                    last_name=last_name,
                    email=str(props.get("email") or "").strip() or None,
                    phone=str(props.get("phone") or props.get("mobilephone") or "").strip() or None,
                    company=str(props.get("company") or "").strip() or None,
                    address_street=str(props.get("address") or "").strip() or None,
                    address_city=str(props.get("city") or "").strip() or None,
                    address_zip=str(props.get("zip") or "").strip() or None,
                    address_country=str(props.get("country") or "").strip() or None,
                    tags=tags,
                    lifecycle_stage=lifecycle,
                    custom_fields=custom_fields,
                    raw_data=c,
                    updated_at=updated_at,
                )
                contacts.append(nc)

            except Exception as e:
                errors.append({"contact_id": source_id, "error": str(e)})

        duration = (time.monotonic() - start_time) * 1000

        return SyncResult(
            success=True,
            records_fetched=len(all_contacts),
            contacts=contacts,
            errors=errors,
            records_failed=len(errors),
            duration_ms=duration,
            metadata={"source": "hubspot", "incremental": sync_mode == SyncMode.INCREMENTAL},
        )

    # ── Push Contacts (Outbound / Bidirectional) ─────────────────────────

    async def push_contacts(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        contacts: List[NormalizedContact],
    ) -> SyncResult:
        """Push contacts from ARIIA to HubSpot (for bidirectional sync)."""
        token = (config.get("access_token") or "").strip()
        if not token:
            return SyncResult(success=False, error_message="HubSpot nicht konfiguriert.")

        created = 0
        updated = 0
        errors: List[Dict[str, Any]] = []
        start_time = time.monotonic()

        for nc in contacts:
            properties: Dict[str, str] = {}
            if nc.email:
                properties["email"] = nc.email
            if nc.first_name:
                properties["firstname"] = nc.first_name
            if nc.last_name:
                properties["lastname"] = nc.last_name
            if nc.phone:
                properties["phone"] = nc.phone
            if nc.company:
                properties["company"] = nc.company
            if nc.address_street:
                properties["address"] = nc.address_street
            if nc.address_city:
                properties["city"] = nc.address_city
            if nc.address_zip:
                properties["zip"] = nc.address_zip
            if nc.address_country:
                properties["country"] = nc.address_country

            if not properties.get("email"):
                errors.append({"contact": nc.external_id, "error": "Keine E-Mail-Adresse"})
                continue

            try:
                # Search for existing contact by email
                search_payload = {
                    "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": properties["email"]}]}],
                    "limit": 1,
                }
                resp = await self._hs_request(token, "POST", "/crm/v3/objects/contacts/search", json_data=search_payload)
                results = resp.json().get("results", [])

                if results:
                    # Update existing
                    hs_id = results[0]["id"]
                    await self._hs_request(token, "PATCH", f"/crm/v3/objects/contacts/{hs_id}", json_data={"properties": properties})
                    updated += 1
                else:
                    # Create new
                    await self._hs_request(token, "POST", "/crm/v3/objects/contacts", json_data={"properties": properties})
                    created += 1

            except Exception as e:
                errors.append({"contact": nc.external_id, "error": str(e)})

        duration = (time.monotonic() - start_time) * 1000

        return SyncResult(
            success=True,
            records_fetched=len(contacts),
            records_created=created,
            records_updated=updated,
            records_failed=len(errors),
            errors=errors,
            duration_ms=duration,
            metadata={"source": "hubspot", "direction": "outbound"},
        )

    # ── Webhook Handler ──────────────────────────────────────────────────

    async def handle_webhook(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> SyncResult:
        """Process HubSpot webhook subscription events."""
        # HubSpot sends an array of events
        events = payload if isinstance(payload, list) else [payload]
        contacts: List[NormalizedContact] = []
        deleted_ids: List[str] = []
        token = (config.get("access_token") or "").strip()

        for event in events:
            subscription_type = event.get("subscriptionType", "")
            object_id = str(event.get("objectId", ""))

            if not object_id:
                continue

            if "deletion" in subscription_type:
                deleted_ids.append(object_id)
                continue

            if "contact" not in subscription_type:
                continue

            # Fetch full contact data
            if token:
                try:
                    resp = await self._hs_request(
                        token, "GET", f"/crm/v3/objects/contacts/{object_id}",
                        params={"properties": ",".join(SYNC_PROPERTIES)},
                    )
                    c = resp.json()
                    props = c.get("properties", {})

                    nc = NormalizedContact(
                        external_id=object_id,
                        source="hubspot",
                        first_name=str(props.get("firstname") or "").strip() or "HubSpot",
                        last_name=str(props.get("lastname") or "").strip() or f"Kontakt #{object_id}",
                        email=str(props.get("email") or "").strip() or None,
                        phone=str(props.get("phone") or "").strip() or None,
                        company=str(props.get("company") or "").strip() or None,
                        tags=["hubspot"],
                        lifecycle_stage=props.get("lifecyclestage", "lead"),
                        custom_fields={},
                        raw_data=c,
                    )
                    contacts.append(nc)
                except Exception as e:
                    logger.warning("hubspot.webhook.fetch_failed", object_id=object_id, error=str(e))

        return SyncResult(
            success=True,
            records_fetched=len(contacts),
            records_deleted=len(deleted_ids),
            contacts=contacts,
            metadata={"action": "webhook", "deleted_ids": deleted_ids},
        )

    # ── Capability Execution (Agent Runtime) ─────────────────────────────

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
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HUBSPOT_INTERNAL_ERROR")

    def _get_tenant_token(self, tenant_id: int) -> str:
        """Resolve HubSpot token from Vault for capability execution."""
        from app.core.security.vault import CredentialVault
        vault = CredentialVault()
        config = vault.get_credentials(tenant_id, "hubspot")
        token = (config.get("access_token") or "").strip()
        if not token:
            raise ValueError("HubSpot nicht konfiguriert für diesen Tenant.")
        return token

    async def _contact_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        token = self._get_tenant_token(tenant_id)
        email = kwargs.get("email")
        query = kwargs.get("query") or kwargs.get("search", "")
        limit = kwargs.get("limit", 25)

        if email:
            payload = {"filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}], "properties": ["email", "firstname", "lastname", "phone", "company", "lifecyclestage"], "limit": limit}
        elif query:
            payload = {"query": query, "properties": ["email", "firstname", "lastname", "phone", "company", "lifecyclestage"], "limit": limit}
        else:
            payload = {"properties": ["email", "firstname", "lastname", "phone", "company", "lifecyclestage"], "limit": limit}

        resp = await self._hs_request(token, "POST", "/crm/v3/objects/contacts/search", json_data=payload)
        data = resp.json()
        contacts = [{"id": c.get("id"), "email": c.get("properties", {}).get("email"), "first_name": c.get("properties", {}).get("firstname"), "last_name": c.get("properties", {}).get("lastname"), "phone": c.get("properties", {}).get("phone"), "company": c.get("properties", {}).get("company"), "lifecycle_stage": c.get("properties", {}).get("lifecyclestage")} for c in data.get("results", [])]
        return AdapterResult(success=True, data=contacts, metadata={"total": data.get("total", len(contacts))})

    async def _contact_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        token = self._get_tenant_token(tenant_id)
        email = kwargs.get("email")
        if not email:
            return AdapterResult(success=False, error="Parameter 'email' ist erforderlich", error_code="MISSING_PARAM")
        properties = {"email": email}
        for field, hs_field in [("first_name", "firstname"), ("last_name", "lastname"), ("phone", "phone"), ("company", "company"), ("lifecycle_stage", "lifecyclestage")]:
            if kwargs.get(field):
                properties[hs_field] = kwargs[field]
        resp = await self._hs_request(token, "POST", "/crm/v3/objects/contacts", json_data={"properties": properties})
        data = resp.json()
        return AdapterResult(success=True, data={"id": data.get("id"), "email": data.get("properties", {}).get("email"), "message": "Kontakt erfolgreich erstellt"})

    async def _contact_update(self, tenant_id: int, **kwargs) -> AdapterResult:
        token = self._get_tenant_token(tenant_id)
        contact_id = kwargs.get("contact_id")
        if not contact_id:
            return AdapterResult(success=False, error="Parameter 'contact_id' ist erforderlich", error_code="MISSING_PARAM")
        properties = {}
        for field, hs_field in [("email", "email"), ("first_name", "firstname"), ("last_name", "lastname"), ("phone", "phone"), ("company", "company"), ("lifecycle_stage", "lifecyclestage")]:
            if kwargs.get(field) is not None:
                properties[hs_field] = kwargs[field]
        if not properties:
            return AdapterResult(success=False, error="Mindestens eine Eigenschaft zum Aktualisieren ist erforderlich", error_code="MISSING_PARAM")
        resp = await self._hs_request(token, "PATCH", f"/crm/v3/objects/contacts/{contact_id}", json_data={"properties": properties})
        data = resp.json()
        return AdapterResult(success=True, data={"id": data.get("id"), "message": "Kontakt erfolgreich aktualisiert"})

    async def _deal_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        token = self._get_tenant_token(tenant_id)
        resp = await self._hs_request(token, "GET", "/crm/v3/objects/deals", params={"limit": kwargs.get("limit", 25), "properties": "dealname,amount,dealstage,pipeline,closedate,createdate"})
        data = resp.json()
        deals = [{"id": d.get("id"), "name": d.get("properties", {}).get("dealname"), "amount": d.get("properties", {}).get("amount"), "stage": d.get("properties", {}).get("dealstage"), "pipeline": d.get("properties", {}).get("pipeline")} for d in data.get("results", [])]
        return AdapterResult(success=True, data=deals, metadata={"count": len(deals)})

    async def _deal_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        token = self._get_tenant_token(tenant_id)
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
        resp = await self._hs_request(token, "POST", "/crm/v3/objects/deals", json_data={"properties": properties})
        data = resp.json()
        return AdapterResult(success=True, data={"id": data.get("id"), "name": data.get("properties", {}).get("dealname"), "message": "Deal erfolgreich erstellt"})

    async def _company_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        token = self._get_tenant_token(tenant_id)
        query = kwargs.get("query") or kwargs.get("search") or kwargs.get("name", "")
        domain = kwargs.get("domain")
        limit = kwargs.get("limit", 25)
        if domain:
            payload = {"filterGroups": [{"filters": [{"propertyName": "domain", "operator": "EQ", "value": domain}]}], "properties": ["name", "domain", "industry", "city", "country"], "limit": limit}
        elif query:
            payload = {"query": query, "properties": ["name", "domain", "industry", "city", "country"], "limit": limit}
        else:
            payload = {"properties": ["name", "domain", "industry", "city", "country"], "limit": limit}
        resp = await self._hs_request(token, "POST", "/crm/v3/objects/companies/search", json_data=payload)
        data = resp.json()
        companies = [{"id": c.get("id"), "name": c.get("properties", {}).get("name"), "domain": c.get("properties", {}).get("domain"), "industry": c.get("properties", {}).get("industry")} for c in data.get("results", [])]
        return AdapterResult(success=True, data=companies, metadata={"total": data.get("total", len(companies))})

    async def _ticket_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        token = self._get_tenant_token(tenant_id)
        subject = kwargs.get("subject")
        if not subject:
            return AdapterResult(success=False, error="Parameter 'subject' ist erforderlich", error_code="MISSING_PARAM")
        properties = {"subject": subject}
        if kwargs.get("content"):
            properties["content"] = kwargs["content"]
        if kwargs.get("priority"):
            properties["hs_ticket_priority"] = kwargs["priority"]
        resp = await self._hs_request(token, "POST", "/crm/v3/objects/tickets", json_data={"properties": properties})
        data = resp.json()
        return AdapterResult(success=True, data={"id": data.get("id"), "subject": data.get("properties", {}).get("subject"), "message": "Ticket erfolgreich erstellt"})
