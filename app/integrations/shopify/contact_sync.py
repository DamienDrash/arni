"""Shopify → Contact sync (v2).

@ARCH: Contacts Refactoring – Integration Sync
Replaces the legacy members_sync.py by writing directly into the
new `contacts` table via the ContactSyncService.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
import structlog

from app.contacts.sync_service import NormalizedContact, contact_sync_service
from app.gateway.persistence import persistence

logger = structlog.get_logger()


async def sync_contacts_from_shopify(tenant_id: int) -> dict[str, Any]:
    """Sync customers from Shopify into the contacts table.

    Fetches all customers from the Shopify Admin API and upserts
    them into the contacts table via ContactSyncService.

    Returns:
        Dict with sync statistics
    """
    # 1. Load Credentials
    prefix = f"integration_shopify_{tenant_id}"
    domain = persistence.get_setting(f"{prefix}_domain")
    token = persistence.get_setting(f"{prefix}_access_token")

    if not domain or not token:
        raise ValueError(
            "Shopify-Zugangsdaten fehlen. Bitte konfigurieren Sie die Shopify-Integration "
            "unter Einstellungen → Integrationen."
        )

    # 2. Fetch customers from Shopify (with pagination)
    all_customers: List[dict] = []
    url = f"https://{domain}/admin/api/2024-01/customers.json?limit=250"
    headers = {"X-Shopify-Access-Token": token}

    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            customers = data.get("customers", [])
            all_customers.extend(customers)

            # Handle pagination via Link header
            link_header = resp.headers.get("Link", "")
            url = None
            if 'rel="next"' in link_header:
                for part in link_header.split(","):
                    if 'rel="next"' in part:
                        url = part.split("<")[1].split(">")[0]
                        break

    logger.info(
        "shopify.contact_sync.fetched",
        tenant_id=tenant_id,
        count=len(all_customers),
    )

    # 3. Convert to NormalizedContact objects
    normalized_contacts: List[NormalizedContact] = []

    for c in all_customers:
        source_id = str(c.get("id", ""))
        if not source_id:
            continue

        first_name = str(c.get("first_name") or "").strip()
        last_name = str(c.get("last_name") or "").strip()
        if not first_name and not last_name:
            first_name = "Shopify"
            last_name = f"Kunde #{source_id}"

        email = str(c.get("email") or "").strip() or None
        phone = str(c.get("phone") or "").strip() or None

        # Determine lifecycle from Shopify data
        lifecycle = "customer"  # Shopify customers are customers by default
        state = c.get("state", "")
        if state == "disabled":
            lifecycle = "churned"
        elif state == "invited":
            lifecycle = "lead"

        # Build tags
        tags: List[str] = ["shopify"]
        shopify_tags = c.get("tags", "")
        if shopify_tags:
            for t in shopify_tags.split(","):
                t = t.strip()
                if t:
                    tags.append(t)

        # Build custom fields
        custom_fields: Dict[str, Any] = {}
        if c.get("orders_count"):
            custom_fields["bestellungen"] = c["orders_count"]
        if c.get("total_spent"):
            custom_fields["gesamtumsatz"] = c["total_spent"]
        if c.get("currency"):
            custom_fields["währung"] = c["currency"]
        if c.get("note"):
            custom_fields["shopify_notiz"] = c["note"]

        # Build company from default address
        company = None
        default_address = c.get("default_address") or {}
        if default_address.get("company"):
            company = default_address["company"]

        # Consent
        consent_email = c.get("email_marketing_consent", {}).get("state") == "subscribed"
        consent_sms = c.get("sms_marketing_consent", {}).get("state") == "subscribed"

        nc = NormalizedContact(
            source_id=source_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            company=company,
            lifecycle_stage=lifecycle,
            tags=tags,
            custom_fields=custom_fields,
            external_ids={"shopify": source_id},
            consent_email=consent_email,
            consent_sms=consent_sms,
        )
        normalized_contacts.append(nc)

    # 4. Sync into contacts table
    sync_result = contact_sync_service.sync_contacts(
        tenant_id=tenant_id,
        source="shopify",
        contacts=normalized_contacts,
        full_sync=True,
        delete_missing=False,
        performed_by_name="Shopify Sync",
    )

    return {
        "fetched": len(all_customers),
        **sync_result.to_dict(),
    }
