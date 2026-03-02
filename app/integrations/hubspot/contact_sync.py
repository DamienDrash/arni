"""HubSpot → Contact sync (v2).

@ARCH: Contacts Refactoring – Integration Sync
Fetches contacts from HubSpot CRM API v3 and syncs them
into the contacts table via ContactSyncService.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.contacts.sync_service import NormalizedContact, contact_sync_service
from app.gateway.persistence import persistence

logger = structlog.get_logger()

# HubSpot lifecycle stage mapping
_HUBSPOT_LIFECYCLE_MAP = {
    "subscriber": "subscriber",
    "lead": "lead",
    "marketingqualifiedlead": "lead",
    "salesqualifiedlead": "opportunity",
    "opportunity": "opportunity",
    "customer": "customer",
    "evangelist": "customer",
    "other": "other",
}


async def sync_contacts_from_hubspot(tenant_id: int) -> dict[str, Any]:
    """Sync contacts from HubSpot CRM into the contacts table.

    Uses HubSpot CRM API v3 with pagination to fetch all contacts.

    Returns:
        Dict with sync statistics
    """
    # 1. Load Credentials
    prefix = f"integration_hubspot_{tenant_id}"
    access_token = persistence.get_setting(f"{prefix}_token")

    if not access_token:
        raise ValueError(
            "HubSpot-Zugangsdaten fehlen. Bitte konfigurieren Sie die HubSpot-Integration "
            "unter Einstellungen → Integrationen."
        )

    # 2. Fetch all contacts with pagination
    all_contacts: List[dict] = []
    after: Optional[str] = None
    base_url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Properties to fetch
    properties = [
        "firstname", "lastname", "email", "phone", "company",
        "jobtitle", "lifecyclestage", "hs_lead_status",
        "date_of_birth", "gender", "hs_language",
        "hs_email_optout", "notes_last_updated",
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: Dict[str, Any] = {
                "limit": 100,
                "properties": ",".join(properties),
            }
            if after:
                params["after"] = after

            resp = await client.get(base_url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            all_contacts.extend(results)

            # Check for next page
            paging = data.get("paging", {})
            next_page = paging.get("next", {})
            after = next_page.get("after")

            if not after:
                break

            # Safety limit
            if len(all_contacts) > 50000:
                logger.warning("hubspot.contact_sync.limit_reached", count=len(all_contacts))
                break

    logger.info(
        "hubspot.contact_sync.fetched",
        tenant_id=tenant_id,
        count=len(all_contacts),
    )

    # 3. Convert to NormalizedContact objects
    normalized_contacts: List[NormalizedContact] = []

    for c in all_contacts:
        source_id = str(c.get("id", ""))
        if not source_id:
            continue

        props = c.get("properties", {})

        first_name = str(props.get("firstname") or "").strip()
        last_name = str(props.get("lastname") or "").strip()
        if not first_name and not last_name:
            email = str(props.get("email") or "").strip()
            if email:
                first_name = email.split("@")[0]
                last_name = "(HubSpot)"
            else:
                first_name = "HubSpot"
                last_name = f"Kontakt #{source_id}"

        email = str(props.get("email") or "").strip() or None
        phone = str(props.get("phone") or "").strip() or None
        company = str(props.get("company") or "").strip() or None
        job_title = str(props.get("jobtitle") or "").strip() or None

        # Map lifecycle stage
        hs_lifecycle = str(props.get("lifecyclestage") or "").strip().lower()
        lifecycle = _HUBSPOT_LIFECYCLE_MAP.get(hs_lifecycle, "subscriber")

        # Language
        hs_language = str(props.get("hs_language") or "").strip().lower()
        preferred_language = hs_language[:2] if hs_language else "de"

        # Consent
        email_optout = str(props.get("hs_email_optout") or "").strip().lower()
        consent_email = email_optout != "true"

        # Build tags
        tags: List[str] = ["hubspot"]
        if hs_lifecycle:
            tags.append(f"hs:{hs_lifecycle}")

        # Build custom fields
        custom_fields: Dict[str, Any] = {}
        lead_status = props.get("hs_lead_status")
        if lead_status:
            custom_fields["lead_status"] = lead_status

        nc = NormalizedContact(
            source_id=source_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            company=company,
            job_title=job_title,
            preferred_language=preferred_language,
            lifecycle_stage=lifecycle,
            tags=tags,
            custom_fields=custom_fields,
            external_ids={"hubspot": source_id},
            consent_email=consent_email,
        )
        normalized_contacts.append(nc)

    # 4. Sync into contacts table
    sync_result = contact_sync_service.sync_contacts(
        tenant_id=tenant_id,
        source="hubspot",
        contacts=normalized_contacts,
        full_sync=True,
        delete_missing=False,
        performed_by_name="HubSpot Sync",
    )

    return {
        "fetched": len(all_contacts),
        **sync_result.to_dict(),
    }
