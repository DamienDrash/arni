"""ARIIA v2.0 – WooCommerce Integration Adapter.

@ARCH: Contacts-Sync Refactoring
Concrete adapter for WooCommerce REST API v3 integration. Implements
both capability execution (agent runtime) AND contact sync interface.

Contact Sync Data Points:
  - Customer profile: name, email, phone, company, address
  - Order stats: order count, total spent
  - Billing/Shipping address
  - WooCommerce role → lifecycle stage

Capabilities (Agent Runtime):
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
from datetime import datetime
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

API_VERSION = "wc/v3"


class WooCommerceAdapter(BaseAdapter):
    """Adapter for WooCommerce REST API v3 integration.

    Supports both capability execution and contact sync.
    """

    @property
    def integration_id(self) -> str:
        return "woocommerce"

    @property
    def display_name(self) -> str:
        return "WooCommerce"

    @property
    def category(self) -> str:
        return "ecommerce"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "ecommerce.customer.search",
            "ecommerce.customer.create",
            "ecommerce.order.list",
            "ecommerce.order.status",
            "ecommerce.product.list",
            "ecommerce.product.search",
            "ecommerce.webhook.subscribe",
        ]

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        return [SyncDirection.INBOUND]

    @property
    def supports_incremental_sync(self) -> bool:
        return True  # WooCommerce supports modified_after filter

    @property
    def supports_webhooks(self) -> bool:
        return True  # WooCommerce has built-in webhook support

    # ── Configuration Schema ─────────────────────────────────────────────

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "fields": [
                {
                    "key": "store_url",
                    "label": "Shop URL",
                    "type": "text",
                    "required": True,
                    "placeholder": "https://mein-shop.de",
                    "help_text": "Die vollständige URL Ihres WooCommerce-Shops.",
                },
                {
                    "key": "consumer_key",
                    "label": "Consumer Key",
                    "type": "password",
                    "required": True,
                    "help_text": "WooCommerce REST API Consumer Key. Erstellen unter WooCommerce → Einstellungen → Erweitert → REST API.",
                },
                {
                    "key": "consumer_secret",
                    "label": "Consumer Secret",
                    "type": "password",
                    "required": True,
                    "help_text": "WooCommerce REST API Consumer Secret.",
                },
                {
                    "key": "sync_orders",
                    "label": "Bestelldaten synchronisieren",
                    "type": "toggle",
                    "required": False,
                    "default": True,
                    "help_text": "Bestellanzahl und Gesamtumsatz pro Kunde synchronisieren.",
                },
                {
                    "key": "sync_guests",
                    "label": "Gast-Kunden synchronisieren",
                    "type": "toggle",
                    "required": False,
                    "default": False,
                    "help_text": "Auch Gast-Bestellungen (ohne Konto) als Kontakte importieren.",
                },
            ],
        }

    # ── Helper: WooCommerce API Request ──────────────────────────────────

    @staticmethod
    async def _wc_request(
        store_url: str,
        consumer_key: str,
        consumer_secret: str,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        timeout: int = 30,
    ) -> httpx.Response:
        """Make an authenticated request to the WooCommerce REST API."""
        base_url = store_url.rstrip("/")
        url = f"{base_url}/wp-json/{API_VERSION}/{endpoint}"
        auth_params = {"consumer_key": consumer_key, "consumer_secret": consumer_secret}
        if params:
            auth_params.update(params)

        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(url, params=auth_params)
            elif method == "POST":
                resp = await client.post(url, params=auth_params, json=json_data)
            else:
                resp = await client.request(method, url, params=auth_params, json=json_data)
            resp.raise_for_status()
            return resp

    # ── Connection Test ──────────────────────────────────────────────────

    async def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        """Test WooCommerce API connection."""
        store_url = (config.get("store_url") or "").strip()
        consumer_key = (config.get("consumer_key") or "").strip()
        consumer_secret = (config.get("consumer_secret") or "").strip()

        if not store_url or not consumer_key or not consumer_secret:
            return ConnectionTestResult(success=False, message="Shop URL, Consumer Key und Consumer Secret sind erforderlich.")

        start = time.monotonic()
        try:
            resp = await self._wc_request(store_url, consumer_key, consumer_secret, "GET", "system_status")
            latency = (time.monotonic() - start) * 1000
            data = resp.json()
            env = data.get("environment", {})
            return ConnectionTestResult(
                success=True,
                message=f"Verbindung erfolgreich. WooCommerce {env.get('version', '?')} auf WordPress {env.get('wp_version', '?')}.",
                details={"wc_version": env.get("version"), "wp_version": env.get("wp_version")},
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as e:
            latency = (time.monotonic() - start) * 1000
            code = e.response.status_code
            if code == 401:
                return ConnectionTestResult(success=False, message="Authentifizierung fehlgeschlagen. Bitte Consumer Key/Secret überprüfen.", latency_ms=latency)
            if code == 403:
                return ConnectionTestResult(success=False, message="Zugriff verweigert. Bitte API-Berechtigungen überprüfen.", latency_ms=latency)
            return ConnectionTestResult(success=False, message=f"WooCommerce API-Fehler: {code}", latency_ms=latency)
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
        """Fetch customers from WooCommerce REST API."""
        store_url = (config.get("store_url") or "").strip()
        consumer_key = (config.get("consumer_key") or "").strip()
        consumer_secret = (config.get("consumer_secret") or "").strip()
        sync_orders = config.get("sync_orders", True)

        if not store_url or not consumer_key or not consumer_secret:
            return SyncResult(success=False, error_message="WooCommerce nicht konfiguriert.")

        start_time = time.monotonic()
        all_customers: List[dict] = []

        try:
            page = 1
            while True:
                params: dict[str, Any] = {"per_page": 100, "page": page}
                if sync_mode == SyncMode.INCREMENTAL and last_sync_at:
                    params["modified_after"] = last_sync_at.isoformat()

                resp = await self._wc_request(store_url, consumer_key, consumer_secret, "GET", "customers", params=params)
                customers = resp.json()
                if not customers:
                    break
                all_customers.extend(customers)

                # Check total pages from header
                total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
                if page >= total_pages:
                    break
                page += 1
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 401:
                return SyncResult(success=False, error_message="WooCommerce Authentifizierung fehlgeschlagen.")
            return SyncResult(success=False, error_message=f"WooCommerce API-Fehler: {code}")
        except Exception as e:
            return SyncResult(success=False, error_message=f"WooCommerce API-Fehler: {str(e)}")

        # Convert to NormalizedContact
        contacts: List[NormalizedContact] = []
        errors: List[Dict[str, Any]] = []

        for c in all_customers:
            source_id = str(c.get("id", ""))
            if not source_id or source_id == "0":
                continue

            try:
                first_name = str(c.get("first_name") or "").strip()
                last_name = str(c.get("last_name") or "").strip()
                if not first_name and not last_name:
                    first_name = "WooCommerce"
                    last_name = f"Kunde #{source_id}"

                # Lifecycle from WooCommerce role
                role = c.get("role", "customer")
                lifecycle = "customer"
                if role == "subscriber":
                    lifecycle = "subscriber"

                tags: List[str] = ["woocommerce"]

                # Custom fields
                custom_fields: Dict[str, Any] = {}
                if sync_orders:
                    if c.get("orders_count"):
                        custom_fields["bestellungen"] = c["orders_count"]
                    if c.get("total_spent"):
                        custom_fields["gesamtumsatz"] = c["total_spent"]

                # Billing address
                billing = c.get("billing") or {}
                shipping = c.get("shipping") or {}

                # Use billing address as primary, fallback to shipping
                address_street = billing.get("address_1") or shipping.get("address_1") or None
                if address_street and (billing.get("address_2") or shipping.get("address_2")):
                    address_street += f" {billing.get('address_2') or shipping.get('address_2')}"
                address_city = billing.get("city") or shipping.get("city") or None
                address_zip = billing.get("postcode") or shipping.get("postcode") or None
                address_country = billing.get("country") or shipping.get("country") or None
                company = billing.get("company") or shipping.get("company") or None
                phone = billing.get("phone") or None

                # Updated at
                updated_at = None
                if c.get("date_modified"):
                    try:
                        updated_at = datetime.fromisoformat(c["date_modified"])
                    except (ValueError, AttributeError):
                        pass

                nc = NormalizedContact(
                    external_id=source_id,
                    source="woocommerce",
                    first_name=first_name,
                    last_name=last_name,
                    email=str(c.get("email") or "").strip() or None,
                    phone=phone,
                    company=company,
                    address_street=address_street,
                    address_city=address_city,
                    address_zip=address_zip,
                    address_country=address_country,
                    tags=tags,
                    lifecycle_stage=lifecycle,
                    custom_fields=custom_fields,
                    raw_data=c,
                    updated_at=updated_at,
                )
                contacts.append(nc)

            except Exception as e:
                errors.append({"customer_id": source_id, "error": str(e)})

        duration = (time.monotonic() - start_time) * 1000

        return SyncResult(
            success=True,
            records_fetched=len(all_customers),
            contacts=contacts,
            errors=errors,
            records_failed=len(errors),
            duration_ms=duration,
            metadata={"source": "woocommerce", "incremental": sync_mode == SyncMode.INCREMENTAL},
        )

    # ── Webhook Handler ──────────────────────────────────────────────────

    async def handle_webhook(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> SyncResult:
        """Process WooCommerce customer webhook events."""
        topic = headers.get("x-wc-webhook-topic", "")
        if "customer" not in topic:
            return SyncResult(success=True, metadata={"skipped": True, "topic": topic})

        if topic == "customer.deleted":
            return SyncResult(
                success=True, records_deleted=1,
                metadata={"action": "delete", "external_id": str(payload.get("id", ""))},
            )

        c = payload
        source_id = str(c.get("id", ""))
        billing = c.get("billing") or {}

        nc = NormalizedContact(
            external_id=source_id,
            source="woocommerce",
            first_name=str(c.get("first_name") or "").strip() or "WooCommerce",
            last_name=str(c.get("last_name") or "").strip() or f"Kunde #{source_id}",
            email=str(c.get("email") or "").strip() or None,
            phone=billing.get("phone"),
            company=billing.get("company"),
            address_street=billing.get("address_1"),
            address_city=billing.get("city"),
            address_zip=billing.get("postcode"),
            address_country=billing.get("country"),
            tags=["woocommerce"],
            lifecycle_stage="customer",
            custom_fields={},
            raw_data=c,
        )

        return SyncResult(
            success=True, records_fetched=1, contacts=[nc],
            metadata={"action": "upsert", "webhook_topic": topic},
        )

    # ── Capability Execution (Agent Runtime) ─────────────────────────────

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
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="WOOCOMMERCE_INTERNAL_ERROR")

    def _get_tenant_config(self, tenant_id: int) -> tuple[str, str, str]:
        """Resolve WooCommerce config from Vault for capability execution."""
        from app.core.security.vault import CredentialVault
        vault = CredentialVault()
        config = vault.get_credentials(tenant_id, "woocommerce")
        store_url = (config.get("store_url") or "").strip()
        consumer_key = (config.get("consumer_key") or "").strip()
        consumer_secret = (config.get("consumer_secret") or "").strip()
        if not store_url or not consumer_key or not consumer_secret:
            raise ValueError("WooCommerce nicht konfiguriert für diesen Tenant.")
        return store_url, consumer_key, consumer_secret

    async def _customer_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        store_url, consumer_key, consumer_secret = self._get_tenant_config(tenant_id)
        email = kwargs.get("email")
        search = kwargs.get("search", "")
        params: dict[str, Any] = {"per_page": kwargs.get("limit", 25)}
        if email:
            params["email"] = email
        elif search:
            params["search"] = search
        resp = await self._wc_request(store_url, consumer_key, consumer_secret, "GET", "customers", params=params)
        data = resp.json()
        customers = [{"id": c.get("id"), "email": c.get("email"), "first_name": c.get("first_name"), "last_name": c.get("last_name"), "orders_count": c.get("orders_count"), "total_spent": c.get("total_spent")} for c in data]
        return AdapterResult(success=True, data=customers, metadata={"count": len(customers)})

    async def _customer_create(self, tenant_id: int, **kwargs) -> AdapterResult:
        store_url, consumer_key, consumer_secret = self._get_tenant_config(tenant_id)
        email = kwargs.get("email")
        if not email:
            return AdapterResult(success=False, error="Parameter 'email' ist erforderlich", error_code="MISSING_PARAM")
        payload = {"email": email, "first_name": kwargs.get("first_name", ""), "last_name": kwargs.get("last_name", "")}
        if kwargs.get("phone"):
            payload["billing"] = {"phone": kwargs["phone"]}
        resp = await self._wc_request(store_url, consumer_key, consumer_secret, "POST", "customers", json_data=payload)
        data = resp.json()
        return AdapterResult(success=True, data={"id": data.get("id"), "email": data.get("email"), "message": "Kunde erfolgreich erstellt"})

    async def _order_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        store_url, consumer_key, consumer_secret = self._get_tenant_config(tenant_id)
        params: dict[str, Any] = {"per_page": kwargs.get("limit", 25), "orderby": "date", "order": "desc"}
        if kwargs.get("status"):
            params["status"] = kwargs["status"]
        if kwargs.get("customer"):
            params["customer"] = kwargs["customer"]
        resp = await self._wc_request(store_url, consumer_key, consumer_secret, "GET", "orders", params=params)
        data = resp.json()
        orders = [{"id": o.get("id"), "number": o.get("number"), "status": o.get("status"), "total": o.get("total"), "currency": o.get("currency"), "date_created": o.get("date_created")} for o in data]
        return AdapterResult(success=True, data=orders, metadata={"count": len(orders)})

    async def _order_status(self, tenant_id: int, **kwargs) -> AdapterResult:
        order_id = kwargs.get("order_id")
        if not order_id:
            return AdapterResult(success=False, error="Parameter 'order_id' ist erforderlich", error_code="MISSING_PARAM")
        store_url, consumer_key, consumer_secret = self._get_tenant_config(tenant_id)
        resp = await self._wc_request(store_url, consumer_key, consumer_secret, "GET", f"orders/{order_id}")
        data = resp.json()
        return AdapterResult(success=True, data={
            "id": data.get("id"), "number": data.get("number"), "status": data.get("status"),
            "total": data.get("total"), "currency": data.get("currency"),
            "line_items": [{"name": li.get("name"), "quantity": li.get("quantity"), "total": li.get("total")} for li in data.get("line_items", [])],
        })

    async def _product_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        store_url, consumer_key, consumer_secret = self._get_tenant_config(tenant_id)
        params: dict[str, Any] = {"per_page": kwargs.get("limit", 25)}
        if kwargs.get("category"):
            params["category"] = kwargs["category"]
        resp = await self._wc_request(store_url, consumer_key, consumer_secret, "GET", "products", params=params)
        data = resp.json()
        products = [{"id": p.get("id"), "name": p.get("name"), "sku": p.get("sku"), "price": p.get("price"), "status": p.get("status"), "stock_status": p.get("stock_status")} for p in data]
        return AdapterResult(success=True, data=products, metadata={"count": len(products)})

    async def _product_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        search = kwargs.get("search") or kwargs.get("query")
        if not search:
            return AdapterResult(success=False, error="Parameter 'search' ist erforderlich", error_code="MISSING_PARAM")
        store_url, consumer_key, consumer_secret = self._get_tenant_config(tenant_id)
        resp = await self._wc_request(store_url, consumer_key, consumer_secret, "GET", "products", params={"search": search, "per_page": 25})
        data = resp.json()
        products = [{"id": p.get("id"), "name": p.get("name"), "sku": p.get("sku"), "price": p.get("price"), "stock_status": p.get("stock_status")} for p in data]
        return AdapterResult(success=True, data=products, metadata={"count": len(products)})

    async def _webhook_subscribe(self, tenant_id: int, **kwargs) -> AdapterResult:
        topic = kwargs.get("topic")
        delivery_url = kwargs.get("delivery_url")
        if not topic or not delivery_url:
            return AdapterResult(success=False, error="Parameter 'topic' und 'delivery_url' sind erforderlich", error_code="MISSING_PARAM")
        store_url, consumer_key, consumer_secret = self._get_tenant_config(tenant_id)
        payload = {"name": f"ARIIA Webhook – {topic}", "topic": topic, "delivery_url": delivery_url, "status": "active"}
        if kwargs.get("secret"):
            payload["secret"] = kwargs["secret"]
        resp = await self._wc_request(store_url, consumer_key, consumer_secret, "POST", "webhooks", json_data=payload)
        data = resp.json()
        return AdapterResult(success=True, data={"id": data.get("id"), "topic": data.get("topic"), "status": data.get("status"), "message": "Webhook erfolgreich erstellt"})
