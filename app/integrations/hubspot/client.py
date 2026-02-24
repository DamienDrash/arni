"""HubSpot CRM API client — contacts resource.

Uses HubSpot CRM v3 API for contact retrieval.
Auth: Private App access token.

Reference: https://developers.hubspot.com/docs/api/crm/contacts
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HubSpotClient:
    """Low-level HubSpot CRM API client for contact operations."""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, access_token: str, timeout: int = 20):
        """
        Args:
            access_token: HubSpot Private App access token
            timeout: HTTP request timeout in seconds
        """
        self.access_token = access_token
        self.timeout = timeout

        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def list_contacts(
        self,
        limit: int = 100,
        after: str | None = None,
        properties: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch a page of contacts.

        Args:
            limit: Max contacts per page (max 100)
            after: Cursor for pagination
            properties: List of properties to include

        Returns:
            Tuple of (contacts list, next_after cursor or None)
        """
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        if properties:
            params["properties"] = ",".join(properties)

        data = self._get("/crm/v3/objects/contacts", params)
        results = data.get("results", [])
        paging = data.get("paging", {})
        next_after = paging.get("next", {}).get("after")
        return results, next_after

    def list_all_contacts(
        self,
        properties: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate through ALL contacts."""
        if properties is None:
            properties = [
                "firstname", "lastname", "email", "phone", "mobilephone",
                "date_of_birth", "gender", "hs_language",
                "city", "state", "country", "zip",
                "company", "jobtitle", "lifecyclestage",
                "createdate", "lastmodifieddate",
                "hs_lead_status", "notes_last_updated",
            ]

        all_contacts: list[dict[str, Any]] = []
        after: str | None = None

        while True:
            batch, next_after = self.list_contacts(limit=100, after=after, properties=properties)
            all_contacts.extend(batch)
            if not next_after:
                break
            after = next_after

        return all_contacts

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        """Fetch a single contact by ID."""
        return self._get(f"/crm/v3/objects/contacts/{contact_id}")

    def test_connection(self) -> dict[str, Any]:
        """Test the API connection by fetching one contact."""
        try:
            contacts, _ = self.list_contacts(limit=1)
            return {"ok": True, "reachable": True}
        except requests.HTTPError as e:
            return {"ok": False, "error": str(e), "status_code": e.response.status_code if e.response else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}
