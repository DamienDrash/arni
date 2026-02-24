"""WooCommerce REST API client — customer resource.

Uses WooCommerce REST API v3 for customer retrieval.
Auth: Consumer Key + Consumer Secret (Basic Auth over HTTPS).

Reference: https://woocommerce.github.io/woocommerce-rest-api-docs/#customers
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class WooCommerceClient:
    """Low-level WooCommerce REST API client for customer operations."""

    API_VERSION = "wc/v3"

    def __init__(self, store_url: str, consumer_key: str, consumer_secret: str, timeout: int = 20):
        """
        Args:
            store_url: e.g. "https://my-store.com"
            consumer_key: WooCommerce REST API consumer key
            consumer_secret: WooCommerce REST API consumer secret
            timeout: HTTP request timeout in seconds
        """
        self.base_url = f"{store_url.rstrip('/')}/wp-json/{self.API_VERSION}"
        self.auth = (consumer_key, consumer_secret)
        self.timeout = timeout

        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, auth=self.auth, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _get_with_headers(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, dict]:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, auth=self.auth, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json(), dict(resp.headers)

    def list_customers(self, page: int = 1, per_page: int = 100) -> tuple[list[dict[str, Any]], int]:
        """Fetch a page of customers.

        Returns:
            Tuple of (customers list, total pages)
        """
        params = {"page": page, "per_page": min(per_page, 100)}
        data, headers = self._get_with_headers("/customers", params)
        total_pages = int(headers.get("X-WP-TotalPages", 1))
        return data, total_pages

    def list_all_customers(self) -> list[dict[str, Any]]:
        """Paginate through ALL customers."""
        all_customers: list[dict[str, Any]] = []
        page = 1

        while True:
            batch, total_pages = self.list_customers(page=page, per_page=100)
            all_customers.extend(batch)
            if page >= total_pages:
                break
            page += 1

        return all_customers

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        """Fetch a single customer by ID."""
        return self._get(f"/customers/{customer_id}")

    def test_connection(self) -> dict[str, Any]:
        """Test the API connection."""
        try:
            customers, total_pages = self.list_customers(page=1, per_page=1)
            return {"ok": True, "reachable": True}
        except requests.HTTPError as e:
            return {"ok": False, "error": str(e), "status_code": e.response.status_code if e.response else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}
