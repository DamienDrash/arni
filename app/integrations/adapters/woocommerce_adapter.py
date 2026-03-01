"""ARIIA v2.0 – WooCommerce Integration Adapter.

@ARCH: Phase 2, Sprint 5 – CRM & E-Commerce
Concrete adapter for WooCommerce REST API v3 integration.

Supported Capabilities:
  - ecommerce.customer.search    → Search WooCommerce customers
  - ecommerce.customer.create    → Create a new customer
  - ecommerce.order.list         → List recent orders
  - ecommerce.order.status       → Get order status by ID
  - ecommerce.product.list       → List products
  - ecommerce.product.search     → Search products by name/SKU
  - ecommerce.webhook.subscribe  → Register a webhook
"""

from __future__ import annotations

import time
from typing import Any, Optional
from hashlib import md5

import httpx
import structlog

from app.integrations.adapters.base import BaseAdapter, AdapterResult

logger = structlog.get_logger()


class WooCommerceAdapter(BaseAdapter):
    """Adapter for WooCommerce REST API v3 integration."""

    integration_id = "woocommerce"
    display_name = "WooCommerce"
    description = "E-Commerce-Integration für WooCommerce-Shops: Kunden, Bestellungen, Produkte und Webhooks."
    version = "1.0.0"

    supported_capabilities = {
        "ecommerce.customer.search",
        "ecommerce.customer.create",
        "ecommerce.order.list",
        "ecommerce.order.status",
        "ecommerce.product.list",
        "ecommerce.product.search",
        "ecommerce.webhook.subscribe",
    }

    API_VERSION = "wc/v3"

    def __init__(self):
        super().__init__()
        self._clients: dict[int, dict] = {}

    def configure_tenant(self, tenant_id: int, store_url: str, consumer_key: str, consumer_secret: str):
        """Configure WooCommerce credentials for a tenant."""
        base = store_url.rstrip("/")
        self._clients[tenant_id] = {
            "base_url": f"{base}/wp-json/{self.API_VERSION}",
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
        }
        logger.info("woocommerce.configured", tenant_id=tenant_id, store_url=base)

    def _get_config(self, tenant_id: int) -> dict:
        config = self._clients.get(tenant_id)
        if not config:
            raise ValueError(f"WooCommerce nicht konfiguriert für Tenant {tenant_id}")
        return config

    # ── Core execute ─────────────────────────────────────────────

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs) -> AdapterResult:
        dispatch = {
            "ecommerce.customer.search": self._customer_search,
            "ecommerce.customer.create": self._customer_create,
            "ecommerce.order.list": self._order_list,
            "ecommerce.order.status": self._order_status,
            "ecommerce.product.list": self._product_list,
            "ecommerce.product.search": self._product_search,
            "ecommerce.webhook.subscribe": self._webhook_subscribe,
        }

        handler = dispatch.get(capability_id)
        if not handler:
            return AdapterResult(success=False, error=f"Capability '{capability_id}' not supported", error_code="UNSUPPORTED_CAPABILITY")

        try:
            return await handler(tenant_id, **kwargs)
        except ValueError as e:
            return AdapterResult(success=False, error=str(e), error_code="NOT_CONFIGURED")
        except httpx.HTTPStatusError as e:
            return AdapterResult(success=False, error=f"WooCommerce API Fehler: {e.response.status_code}", error_code=f"WOOCOMMERCE_HTTP_{e.response.status_code}")
        except httpx.RequestError as e:
            return AdapterResult(success=False, error=f"Verbindungsfehler: {str(e)}", error_code="WOOCOMMERCE_REQUEST_FAILED")
        except Exception as e:
            logger.exception("woocommerce.execute_failed", capability=capability_id, tenant_id=tenant_id)
            return AdapterResult(success=False, error=str(e), error_code="WOOCOMMERCE_INTERNAL_ERROR")

    async def _wc_request(self, tenant_id: int, method: str, endpoint: str, params: dict | None = None, json_data: dict | None = None) -> dict | list:
        config = self._get_config(tenant_id)
        url = f"{config['base_url']}/{endpoint}"
        auth_params = {
            "consumer_key": config["consumer_key"],
            "consumer_secret": config["consumer_secret"],
        }
        if params:
            auth_params.update(params)

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, params=auth_params)
            elif method == "POST":
                resp = await client.post(url, params=auth_params, json=json_data)
            elif method == "PUT":
                resp = await client.put(url, params=auth_params, json=json_data)
            else:
                resp = await client.request(method, url, params=auth_params, json=json_data)
            resp.raise_for_status()
            return resp.json()

    # ── Customers ────────────────────────────────────────────────

    async def _customer_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        email = kwargs.get("email")
        search = kwargs.get("search", "")
        params = {"per_page": kwargs.get("limit", 25)}
        if email:
            params["email"] = email
        elif search:
            params["search"] = search

        data = await self._wc_request(tenant_id, "GET", "customers", params=params)
        customers = [
            {
                "id": c.get("id"),
                "email": c.get("email"),
                "first_name": c.get("first_name"),
                "last_name": c.get("last_name"),
                "username": c.get("username"),
                "orders_count": c.get("orders_count"),
                "total_spent": c.get("total_spent"),
                "date_created": c.get("date_created"),
            }
            for c in data
        ]
        return AdapterResult(success=True, data=customers, metadata={"count": len(customers)})

    async def _customer_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        email = kwargs.get("email")
        if not email:
            return AdapterResult(success=False, error="Parameter 'email' ist erforderlich", error_code="MISSING_PARAM")

        payload = {
            "email": email,
            "first_name": kwargs.get("first_name", ""),
            "last_name": kwargs.get("last_name", ""),
        }
        if kwargs.get("phone"):
            payload["billing"] = {"phone": kwargs["phone"]}

        data = await self._wc_request(tenant_id, "POST", "customers", json_data=payload)
        return AdapterResult(success=True, data={"id": data.get("id"), "email": data.get("email"), "message": "Kunde erfolgreich erstellt"})

    # ── Orders ───────────────────────────────────────────────────

    async def _order_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        params = {
            "per_page": kwargs.get("limit", 25),
            "orderby": kwargs.get("orderby", "date"),
            "order": kwargs.get("order", "desc"),
        }
        if kwargs.get("status"):
            params["status"] = kwargs["status"]
        if kwargs.get("customer"):
            params["customer"] = kwargs["customer"]
        if kwargs.get("after"):
            params["after"] = kwargs["after"]

        data = await self._wc_request(tenant_id, "GET", "orders", params=params)
        orders = [
            {
                "id": o.get("id"),
                "number": o.get("number"),
                "status": o.get("status"),
                "total": o.get("total"),
                "currency": o.get("currency"),
                "customer_id": o.get("customer_id"),
                "date_created": o.get("date_created"),
                "line_items_count": len(o.get("line_items", [])),
            }
            for o in data
        ]
        return AdapterResult(success=True, data=orders, metadata={"count": len(orders)})

    async def _order_status(self, tenant_id: int, **kwargs) -> AdapterResult:
        order_id = kwargs.get("order_id")
        if not order_id:
            return AdapterResult(success=False, error="Parameter 'order_id' ist erforderlich", error_code="MISSING_PARAM")

        data = await self._wc_request(tenant_id, "GET", f"orders/{order_id}")
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "number": data.get("number"),
            "status": data.get("status"),
            "total": data.get("total"),
            "currency": data.get("currency"),
            "payment_method": data.get("payment_method_title"),
            "customer_id": data.get("customer_id"),
            "billing": data.get("billing"),
            "shipping": data.get("shipping"),
            "line_items": [
                {"name": li.get("name"), "quantity": li.get("quantity"), "total": li.get("total")}
                for li in data.get("line_items", [])
            ],
            "date_created": data.get("date_created"),
            "date_modified": data.get("date_modified"),
        })

    # ── Products ─────────────────────────────────────────────────

    async def _product_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        params = {
            "per_page": kwargs.get("limit", 25),
            "orderby": kwargs.get("orderby", "date"),
            "order": kwargs.get("order", "desc"),
        }
        if kwargs.get("category"):
            params["category"] = kwargs["category"]
        if kwargs.get("status"):
            params["status"] = kwargs["status"]

        data = await self._wc_request(tenant_id, "GET", "products", params=params)
        products = [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "sku": p.get("sku"),
                "price": p.get("price"),
                "regular_price": p.get("regular_price"),
                "sale_price": p.get("sale_price"),
                "status": p.get("status"),
                "stock_status": p.get("stock_status"),
                "stock_quantity": p.get("stock_quantity"),
                "type": p.get("type"),
            }
            for p in data
        ]
        return AdapterResult(success=True, data=products, metadata={"count": len(products)})

    async def _product_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        search = kwargs.get("search") or kwargs.get("query")
        sku = kwargs.get("sku")
        if not search and not sku:
            return AdapterResult(success=False, error="Parameter 'search' oder 'sku' ist erforderlich", error_code="MISSING_PARAM")

        params = {"per_page": kwargs.get("limit", 25)}
        if search:
            params["search"] = search
        if sku:
            params["sku"] = sku

        data = await self._wc_request(tenant_id, "GET", "products", params=params)
        products = [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "sku": p.get("sku"),
                "price": p.get("price"),
                "status": p.get("status"),
                "stock_status": p.get("stock_status"),
                "permalink": p.get("permalink"),
            }
            for p in data
        ]
        return AdapterResult(success=True, data=products, metadata={"count": len(products)})

    # ── Webhooks ─────────────────────────────────────────────────

    async def _webhook_subscribe(self, tenant_id: int, **kwargs) -> AdapterResult:
        topic = kwargs.get("topic")
        delivery_url = kwargs.get("delivery_url")
        if not topic or not delivery_url:
            return AdapterResult(success=False, error="Parameter 'topic' und 'delivery_url' sind erforderlich", error_code="MISSING_PARAM")

        payload = {
            "name": kwargs.get("name", f"ARIIA Webhook – {topic}"),
            "topic": topic,
            "delivery_url": delivery_url,
            "status": "active",
        }
        if kwargs.get("secret"):
            payload["secret"] = kwargs["secret"]

        data = await self._wc_request(tenant_id, "POST", "webhooks", json_data=payload)
        return AdapterResult(success=True, data={
            "id": data.get("id"),
            "topic": data.get("topic"),
            "delivery_url": data.get("delivery_url"),
            "status": data.get("status"),
            "message": "Webhook erfolgreich erstellt",
        })

    # ── Health Check ─────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        try:
            data = await self._wc_request(tenant_id, "GET", "system_status")
            return AdapterResult(success=True, data={
                "status": "healthy",
                "wc_version": data.get("environment", {}).get("version"),
                "wp_version": data.get("environment", {}).get("wp_version"),
            })
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="HEALTH_CHECK_FAILED")
