"""Shopify Admin API client — customer resource.

Uses the Shopify Admin REST API (2024-01) for customer retrieval.
Auth: Private App access token or Custom App access token.

Reference: https://shopify.dev/docs/api/admin-rest/2024-01/resources/customer
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ShopifyClient:
    """Low-level Shopify Admin API client for customer operations."""

    API_VERSION = "2024-01"

    def __init__(self, shop_domain: str, access_token: str, timeout: int = 20):
        """
        Args:
            shop_domain: e.g. "my-store.myshopify.com" or "my-store"
            access_token: Shopify Admin API access token
            timeout: HTTP request timeout in seconds
        """
        domain = shop_domain.strip().rstrip("/")
        if not domain.endswith(".myshopify.com"):
            domain = f"{domain}.myshopify.com"
        self.base_url = f"https://{domain}/admin/api/{self.API_VERSION}"
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
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        })

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def list_customers(
        self,
        limit: int = 250,
        since_id: int | None = None,
        fields: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a page of customers.

        Args:
            limit: Max customers per page (max 250)
            since_id: Return customers after this ID (for pagination)
            fields: Comma-separated list of fields to return
        """
        params: dict[str, Any] = {"limit": min(limit, 250)}
        if since_id:
            params["since_id"] = since_id
        if fields:
            params["fields"] = fields
        data = self._get("/customers.json", params)
        return data.get("customers", [])

    def list_all_customers(self) -> list[dict[str, Any]]:
        """Paginate through ALL customers using since_id cursor."""
        all_customers: list[dict[str, Any]] = []
        since_id: int | None = None

        while True:
            batch = self.list_customers(limit=250, since_id=since_id)
            if not batch:
                break
            all_customers.extend(batch)
            since_id = batch[-1]["id"]
            if len(batch) < 250:
                break

        return all_customers

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        """Fetch a single customer by ID."""
        data = self._get(f"/customers/{customer_id}.json")
        return data.get("customer", {})

    def count_customers(self) -> int:
        """Return total customer count."""
        data = self._get("/customers/count.json")
        return data.get("count", 0)

    def test_connection(self) -> dict[str, Any]:
        """Test the API connection by fetching shop info."""
        try:
            count = self.count_customers()
            return {"ok": True, "customer_count": count}
        except requests.HTTPError as e:
            return {"ok": False, "error": str(e), "status_code": e.response.status_code if e.response else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}
