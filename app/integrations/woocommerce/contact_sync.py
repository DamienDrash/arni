"""WooCommerce → Contact sync (v2).

@ARCH: Contacts Refactoring – Integration Sync
Fetches customers from WooCommerce REST API v3 and syncs them
into the contacts table via ContactSyncService.
"""

from __future__ import annotations

from typing import Any, Dict, List

import httpx
import structlog

from app.contacts.sync_service import NormalizedContact, contact_sync_service
from app.gateway.persistence import persistence

logger = structlog.get_logger()


async def sync_contacts_from_woocommerce(tenant_id: int) -> dict[str, Any]:
    """Sync customers from WooCommerce into the contacts table.

    Returns:
        Dict with sync statistics
    """
    # 1. Load Credentials
    prefix = f"integration_woocommerce_{tenant_id}"
    store_url = persistence.get_setting(f"{prefix}_url")
    consumer_key = persistence.get_setting(f"{prefix}_key")
    consumer_secret = persistence.get_setting(f"{prefix}_secret")

    if not store_url or not consumer_key or not consumer_secret:
        raise ValueError(
            "WooCommerce-Zugangsdaten fehlen. Bitte konfigurieren Sie die WooCommerce-Integration "
            "unter Einstellungen → Integrationen."
        )

    base_url = f"{store_url.rstrip('/')}/wp-json/wc/v3"

    # 2. Fetch all customers with pagination
    all_customers: List[dict] = []
    page = 1

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {
                "consumer_key": consumer_key,
                "consumer_secret": consumer_secret,
                "per_page": 100,
                "page": page,
            }
            resp = await client.get(f"{base_url}/customers", params=params)
            resp.raise_for_status()
            customers = resp.json()

            if not customers:
                break

            all_customers.extend(customers)
            page += 1

            # Safety limit
            if page > 100:
                break

    logger.info(
        "woocommerce.contact_sync.fetched",
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
            first_name = "WooCommerce"
            last_name = f"Kunde #{source_id}"

        email = str(c.get("email") or "").strip() or None

        # Extract phone from billing
        billing = c.get("billing") or {}
        phone = str(billing.get("phone") or "").strip() or None
        company = str(billing.get("company") or "").strip() or None

        # Determine lifecycle
        lifecycle = "customer"
        role = c.get("role", "")
        if role == "subscriber":
            lifecycle = "subscriber"

        # Build tags
        tags: List[str] = ["woocommerce"]

        # Build custom fields
        custom_fields: Dict[str, Any] = {}
        if c.get("orders_count"):
            custom_fields["bestellungen"] = c["orders_count"]
        if c.get("total_spent"):
            custom_fields["gesamtumsatz"] = c["total_spent"]

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
            external_ids={"woocommerce": source_id},
        )
        normalized_contacts.append(nc)

    # 4. Sync into contacts table
    sync_result = contact_sync_service.sync_contacts(
        tenant_id=tenant_id,
        source="woocommerce",
        contacts=normalized_contacts,
        full_sync=True,
        delete_missing=False,
        performed_by_name="WooCommerce Sync",
    )

    return {
        "fetched": len(all_customers),
        **sync_result.to_dict(),
    }
