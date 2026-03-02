"""ARIIA v2.0 – Shopify Integration Adapter.

@ARCH: Contacts-Sync Refactoring
Concrete adapter for Shopify e-commerce integration. Implements both
capability execution (agent runtime) AND contact sync interface.

Contact Sync Data Points:
  - Customer profile: name, email, phone, company, address
  - Order stats: order count, total spent, currency
  - Marketing consent: email + SMS opt-in status
  - Shopify tags → ARIIA tags
  - Lifecycle: customer / lead / churned (based on Shopify state)

Capabilities (Agent Runtime):
  - crm.customer.search       → Search Shopify customers
  - crm.customer.sync         → Full customer sync
  - ecommerce.order.list      → List recent orders
  - ecommerce.order.detail    → Get order details
  - ecommerce.product.list    → List products
  - ecommerce.product.detail  → Get product details
  - ecommerce.inventory.check → Check inventory levels
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

# Default Shopify API version
DEFAULT_API_VERSION = "2024-10"


class ShopifyAdapter(BaseAdapter):
    """Adapter for Shopify Admin API integration.

    Supports both capability execution and contact sync.
    """

    @property
    def integration_id(self) -> str:
        return "shopify"

    @property
    def display_name(self) -> str:
        return "Shopify"

    @property
    def category(self) -> str:
        return "ecommerce"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "crm.customer.search",
            "crm.customer.sync",
            "ecommerce.order.list",
            "ecommerce.order.detail",
            "ecommerce.product.list",
            "ecommerce.product.detail",
            "ecommerce.inventory.check",
        ]

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        return [SyncDirection.INBOUND]

    @property
    def supports_incremental_sync(self) -> bool:
        return True  # Shopify supports updated_at_min filter

    @property
    def supports_webhooks(self) -> bool:
        return True  # Shopify has robust webhook support

    # ── Configuration Schema ─────────────────────────────────────────────

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "fields": [
                {
                    "key": "shop_domain",
                    "label": "Shop Domain",
                    "type": "text",
                    "required": True,
                    "placeholder": "mein-shop.myshopify.com",
                    "help_text": "Ihre Shopify-Shop-Domain (ohne https://).",
                },
                {
                    "key": "access_token",
                    "label": "Admin API Access Token",
                    "type": "password",
                    "required": True,
                    "help_text": "Erstellen Sie eine Custom App unter Settings → Apps → Develop Apps. Benötigte Scopes: read_customers, read_orders.",
                },
                {
                    "key": "api_version",
                    "label": "API Version",
                    "type": "select",
                    "required": False,
                    "default": DEFAULT_API_VERSION,
                    "options": [
                        {"value": "2024-10", "label": "2024-10 (Empfohlen)"},
                        {"value": "2024-07", "label": "2024-07"},
                        {"value": "2024-04", "label": "2024-04"},
                        {"value": "2024-01", "label": "2024-01"},
                    ],
                    "help_text": "Shopify Admin API Version.",
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
                    "key": "import_tags",
                    "label": "Shopify Tags importieren",
                    "type": "toggle",
                    "required": False,
                    "default": True,
                    "help_text": "Shopify-Kunden-Tags als ARIIA-Tags importieren.",
                },
            ],
        }

    # ── Helper: Shopify API Request ──────────────────────────────────────

    @staticmethod
    async def _shopify_request(
        domain: str,
        token: str,
        method: str,
        endpoint: str,
        api_version: str = DEFAULT_API_VERSION,
        params: dict = None,
        json_data: dict = None,
        timeout: int = 30,
    ) -> httpx.Response:
        """Make an authenticated request to the Shopify Admin API."""
        url = f"https://{domain}/admin/api/{api_version}/{endpoint}"
        headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method, url=url, headers=headers,
                params=params, json=json_data,
            )
            response.raise_for_status()
            return response

    # ── Connection Test ──────────────────────────────────────────────────

    async def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        """Test Shopify API connection."""
        domain = (config.get("shop_domain") or "").strip().replace("https://", "").replace("http://", "").rstrip("/")
        token = (config.get("access_token") or "").strip()
        api_version = config.get("api_version", DEFAULT_API_VERSION)

        if not domain or not token:
            return ConnectionTestResult(success=False, message="Shop Domain und Access Token sind erforderlich.")

        start = time.monotonic()
        try:
            resp = await self._shopify_request(domain, token, "GET", "shop.json", api_version)
            latency = (time.monotonic() - start) * 1000
            shop_data = resp.json().get("shop", {})
            return ConnectionTestResult(
                success=True,
                message=f"Verbindung erfolgreich zu Shop '{shop_data.get('name', domain)}'.",
                details={"shop_name": shop_data.get("name"), "plan": shop_data.get("plan_name"), "domain": shop_data.get("domain")},
                latency_ms=latency,
            )
        except httpx.HTTPStatusError as e:
            latency = (time.monotonic() - start) * 1000
            if e.response.status_code == 401:
                return ConnectionTestResult(success=False, message="Authentifizierung fehlgeschlagen. Bitte Access Token überprüfen.", latency_ms=latency)
            if e.response.status_code == 403:
                return ConnectionTestResult(success=False, message="Zugriff verweigert. Bitte App-Berechtigungen überprüfen.", latency_ms=latency)
            return ConnectionTestResult(success=False, message=f"Shopify API-Fehler: {e.response.status_code}", latency_ms=latency)
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
        """Fetch customers from Shopify Admin API."""
        domain = (config.get("shop_domain") or "").strip().replace("https://", "").replace("http://", "").rstrip("/")
        token = (config.get("access_token") or "").strip()
        api_version = config.get("api_version", DEFAULT_API_VERSION)
        sync_orders = config.get("sync_orders", True)
        import_tags = config.get("import_tags", True)

        if not domain or not token:
            return SyncResult(success=False, error_message="Shopify nicht konfiguriert: Domain und Token fehlen.")

        start_time = time.monotonic()
        all_customers: List[dict] = []

        # Build URL with optional incremental filter
        base_url = f"https://{domain}/admin/api/{api_version}/customers.json?limit=250"
        if sync_mode == SyncMode.INCREMENTAL and last_sync_at:
            base_url += f"&updated_at_min={last_sync_at.isoformat()}"

        headers = {"X-Shopify-Access-Token": token}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url: str | None = base_url
                while url:
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    all_customers.extend(data.get("customers", []))

                    # Pagination via Link header
                    link_header = resp.headers.get("Link", "")
                    url = None
                    if 'rel="next"' in link_header:
                        for part in link_header.split(","):
                            if 'rel="next"' in part:
                                url = part.split("<")[1].split(">")[0]
                                break
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 401:
                return SyncResult(success=False, error_message="Shopify Authentifizierung fehlgeschlagen.")
            if code == 403:
                return SyncResult(success=False, error_message="Shopify Zugriff verweigert. Bitte read_customers Scope prüfen.")
            return SyncResult(success=False, error_message=f"Shopify API-Fehler: {code}")
        except Exception as e:
            return SyncResult(success=False, error_message=f"Shopify API-Fehler: {str(e)}")

        # Convert to NormalizedContact
        contacts: List[NormalizedContact] = []
        errors: List[Dict[str, Any]] = []

        for c in all_customers:
            source_id = str(c.get("id", ""))
            if not source_id:
                continue

            try:
                first_name = str(c.get("first_name") or "").strip()
                last_name = str(c.get("last_name") or "").strip()
                if not first_name and not last_name:
                    first_name = "Shopify"
                    last_name = f"Kunde #{source_id}"

                # Lifecycle
                lifecycle = "customer"
                state = c.get("state", "")
                if state == "disabled":
                    lifecycle = "churned"
                elif state == "invited":
                    lifecycle = "lead"

                # Tags
                tags: List[str] = ["shopify"]
                if import_tags:
                    shopify_tags = c.get("tags", "")
                    if shopify_tags:
                        for t in shopify_tags.split(","):
                            t = t.strip()
                            if t:
                                tags.append(t)

                # Custom fields
                custom_fields: Dict[str, Any] = {}
                if sync_orders:
                    if c.get("orders_count"):
                        custom_fields["bestellungen"] = c["orders_count"]
                    if c.get("total_spent"):
                        custom_fields["gesamtumsatz"] = c["total_spent"]
                    if c.get("currency"):
                        custom_fields["waehrung"] = c["currency"]
                if c.get("note"):
                    custom_fields["shopify_notiz"] = c["note"]

                # Marketing consent
                consent_email = c.get("email_marketing_consent", {}).get("state") == "subscribed"
                consent_sms = c.get("sms_marketing_consent", {}).get("state") == "subscribed"
                custom_fields["consent_email"] = consent_email
                custom_fields["consent_sms"] = consent_sms

                # Address
                default_address = c.get("default_address") or {}
                company = default_address.get("company") or None
                address_street = None
                if default_address.get("address1"):
                    address_street = default_address["address1"]
                    if default_address.get("address2"):
                        address_street += f" {default_address['address2']}"

                # Updated at
                updated_at = None
                if c.get("updated_at"):
                    try:
                        updated_at = datetime.fromisoformat(c["updated_at"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                nc = NormalizedContact(
                    external_id=source_id,
                    source="shopify",
                    first_name=first_name,
                    last_name=last_name,
                    email=str(c.get("email") or "").strip() or None,
                    phone=str(c.get("phone") or "").strip() or None,
                    company=company,
                    address_street=address_street,
                    address_city=default_address.get("city"),
                    address_zip=default_address.get("zip"),
                    address_country=default_address.get("country"),
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
            metadata={"source": "shopify", "api_version": api_version, "incremental": sync_mode == SyncMode.INCREMENTAL},
        )

    # ── Webhook Handler ──────────────────────────────────────────────────

    async def handle_webhook(
        self,
        tenant_id: int,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> SyncResult:
        """Process Shopify customer webhook events."""
        topic = headers.get("x-shopify-topic", "")
        if topic not in ("customers/create", "customers/update", "customers/delete"):
            return SyncResult(success=True, metadata={"skipped": True, "topic": topic})

        if topic == "customers/delete":
            return SyncResult(
                success=True, records_deleted=1,
                metadata={"action": "delete", "external_id": str(payload.get("id", ""))},
            )

        c = payload
        source_id = str(c.get("id", ""))
        first_name = str(c.get("first_name") or "").strip() or "Shopify"
        last_name = str(c.get("last_name") or "").strip() or f"Kunde #{source_id}"

        tags: List[str] = ["shopify"]
        shopify_tags = c.get("tags", "")
        if shopify_tags:
            for t in shopify_tags.split(","):
                t = t.strip()
                if t:
                    tags.append(t)

        custom_fields: Dict[str, Any] = {}
        if c.get("orders_count"):
            custom_fields["bestellungen"] = c["orders_count"]
        if c.get("total_spent"):
            custom_fields["gesamtumsatz"] = c["total_spent"]

        default_address = c.get("default_address") or {}
        nc = NormalizedContact(
            external_id=source_id, source="shopify",
            first_name=first_name, last_name=last_name,
            email=str(c.get("email") or "").strip() or None,
            phone=str(c.get("phone") or "").strip() or None,
            company=default_address.get("company"),
            address_street=default_address.get("address1"),
            address_city=default_address.get("city"),
            address_zip=default_address.get("zip"),
            address_country=default_address.get("country"),
            tags=tags, lifecycle_stage="customer",
            custom_fields=custom_fields, raw_data=c,
        )

        return SyncResult(
            success=True, records_fetched=1, contacts=[nc],
            metadata={"action": "upsert", "webhook_topic": topic},
        )

    # ── Capability Execution (Agent Runtime) ─────────────────────────────

    async def _execute(self, capability_id: str, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Route capability to the appropriate Shopify API call."""
        handlers = {
            "crm.customer.search": self._customer_search,
            "crm.customer.sync": self._customer_sync,
            "ecommerce.order.list": self._order_list,
            "ecommerce.order.detail": self._order_detail,
            "ecommerce.product.list": self._product_list,
            "ecommerce.product.detail": self._product_detail,
            "ecommerce.inventory.check": self._inventory_check,
        }
        handler = handlers.get(capability_id)
        if not handler:
            return AdapterResult(success=False, error=f"Unknown capability: {capability_id}", error_code="UNKNOWN_CAPABILITY")
        return await handler(tenant_id, **kwargs)

    def _get_tenant_config(self, tenant_id: int) -> tuple[str, str, str]:
        """Resolve Shopify config from Vault/Settings for capability execution."""
        from app.core.credential_vault import CredentialVault
        vault = CredentialVault()
        config = vault.get_credentials(tenant_id, "shopify")
        domain = (config.get("shop_domain") or "").strip().replace("https://", "").replace("http://", "").rstrip("/")
        token = (config.get("access_token") or "").strip()
        api_version = config.get("api_version", DEFAULT_API_VERSION)
        if not domain or not token:
            raise ValueError("Shopify nicht konfiguriert für diesen Tenant.")
        return domain, token, api_version

    async def _customer_search(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Search Shopify customers by email, name, or phone."""
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 10)
        if not query:
            return AdapterResult(success=False, error="Suchbegriff erforderlich.", error_code="MISSING_QUERY")

        try:
            domain, token, api_version = self._get_tenant_config(tenant_id)
            params: dict[str, Any] = {"limit": limit}
            if "@" in query:
                params["query"] = f"email:{query}"
            elif query.replace("+", "").replace(" ", "").isdigit():
                params["query"] = f"phone:{query}"
            else:
                params["query"] = query

            resp = await self._shopify_request(domain, token, "GET", "customers/search.json", api_version, params=params)
            customers = resp.json().get("customers", [])
            results = [{
                "id": c.get("id"), "email": c.get("email", ""),
                "first_name": c.get("first_name", ""), "last_name": c.get("last_name", ""),
                "phone": c.get("phone", ""), "orders_count": c.get("orders_count", 0),
                "total_spent": c.get("total_spent", "0.00"), "tags": c.get("tags", ""),
            } for c in customers]
            return AdapterResult(success=True, data={"customers": results, "count": len(results)})
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SHOPIFY_ERROR")

    async def _customer_sync(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Full customer sync (delegates to get_contacts)."""
        try:
            domain, token, api_version = self._get_tenant_config(tenant_id)
            config = {"shop_domain": domain, "access_token": token, "api_version": api_version}
            result = await self.get_contacts(tenant_id, config)
            return AdapterResult(success=result.success, data={
                "total_fetched": result.records_fetched,
                "contacts": len(result.contacts),
                "errors": result.records_failed,
            })
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SYNC_ERROR")

    async def _order_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        """List recent orders."""
        limit = kwargs.get("limit", 20)
        status = kwargs.get("status", "any")
        customer_id = kwargs.get("customer_id")
        try:
            domain, token, api_version = self._get_tenant_config(tenant_id)
            params: dict[str, Any] = {"limit": limit, "status": status}
            if customer_id:
                params["customer_id"] = customer_id
            resp = await self._shopify_request(domain, token, "GET", "orders.json", api_version, params=params)
            orders = resp.json().get("orders", [])
            results = [{
                "id": o.get("id"), "order_number": o.get("order_number"),
                "email": o.get("email", ""), "total_price": o.get("total_price", "0.00"),
                "currency": o.get("currency", "EUR"),
                "financial_status": o.get("financial_status", ""),
                "fulfillment_status": o.get("fulfillment_status", ""),
                "created_at": o.get("created_at", ""),
                "line_items_count": len(o.get("line_items", [])),
            } for o in orders]
            return AdapterResult(success=True, data={"orders": results, "count": len(results)})
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SHOPIFY_ERROR")

    async def _order_detail(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get detailed order information."""
        order_id = kwargs.get("order_id")
        if not order_id:
            return AdapterResult(success=False, error="order_id erforderlich.", error_code="MISSING_PARAM")
        try:
            domain, token, api_version = self._get_tenant_config(tenant_id)
            resp = await self._shopify_request(domain, token, "GET", f"orders/{order_id}.json", api_version)
            order = resp.json().get("order", {})
            line_items = [{"title": i.get("title", ""), "quantity": i.get("quantity", 0), "price": i.get("price", "0.00"), "sku": i.get("sku", "")} for i in order.get("line_items", [])]
            return AdapterResult(success=True, data={
                "order_id": order.get("id"), "order_number": order.get("order_number"),
                "total_price": order.get("total_price", "0.00"), "currency": order.get("currency", "EUR"),
                "financial_status": order.get("financial_status", ""),
                "fulfillment_status": order.get("fulfillment_status", ""),
                "line_items": line_items, "created_at": order.get("created_at", ""),
            })
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SHOPIFY_ERROR")

    async def _product_list(self, tenant_id: int, **kwargs) -> AdapterResult:
        """List products from the Shopify store."""
        limit = kwargs.get("limit", 20)
        try:
            domain, token, api_version = self._get_tenant_config(tenant_id)
            params: dict[str, Any] = {"limit": limit}
            if kwargs.get("collection_id"):
                params["collection_id"] = kwargs["collection_id"]
            resp = await self._shopify_request(domain, token, "GET", "products.json", api_version, params=params)
            products = resp.json().get("products", [])
            results = []
            for p in products:
                variants = p.get("variants", [])
                prices = [float(v.get("price", 0)) for v in variants]
                price_range = f"{min(prices):.2f} - {max(prices):.2f}" if prices and len(set(prices)) > 1 else (f"{prices[0]:.2f}" if prices else "0.00")
                results.append({
                    "id": p.get("id"), "title": p.get("title", ""),
                    "vendor": p.get("vendor", ""), "status": p.get("status", ""),
                    "price_range": price_range, "variants_count": len(variants),
                })
            return AdapterResult(success=True, data={"products": results, "count": len(results)})
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SHOPIFY_ERROR")

    async def _product_detail(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Get detailed product information."""
        product_id = kwargs.get("product_id")
        if not product_id:
            return AdapterResult(success=False, error="product_id erforderlich.", error_code="MISSING_PARAM")
        try:
            domain, token, api_version = self._get_tenant_config(tenant_id)
            resp = await self._shopify_request(domain, token, "GET", f"products/{product_id}.json", api_version)
            product = resp.json().get("product", {})
            variants = [{"id": v.get("id"), "title": v.get("title", ""), "price": v.get("price", "0.00"), "sku": v.get("sku", ""), "inventory_quantity": v.get("inventory_quantity", 0)} for v in product.get("variants", [])]
            return AdapterResult(success=True, data={
                "product_id": product.get("id"), "title": product.get("title", ""),
                "body_html": product.get("body_html", ""), "vendor": product.get("vendor", ""),
                "status": product.get("status", ""), "variants": variants,
                "images": [img.get("src", "") for img in product.get("images", [])],
            })
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SHOPIFY_ERROR")

    async def _inventory_check(self, tenant_id: int, **kwargs) -> AdapterResult:
        """Check inventory levels for a product."""
        product_id = kwargs.get("product_id")
        if not product_id:
            return AdapterResult(success=False, error="product_id erforderlich.", error_code="MISSING_PARAM")
        try:
            domain, token, api_version = self._get_tenant_config(tenant_id)
            resp = await self._shopify_request(domain, token, "GET", f"products/{product_id}.json", api_version)
            product = resp.json().get("product", {})
            total_available = 0
            inventory = []
            for v in product.get("variants", []):
                qty = v.get("inventory_quantity", 0)
                total_available += max(0, qty)
                inventory.append({"variant_id": v.get("id"), "variant_title": v.get("title", "Default"), "sku": v.get("sku", ""), "quantity": qty, "available": qty > 0})
            return AdapterResult(success=True, data={
                "product_id": product_id, "product_title": product.get("title", ""),
                "total_available": total_available, "in_stock": total_available > 0, "variants": inventory,
            })
        except Exception as e:
            return AdapterResult(success=False, error=str(e), error_code="SHOPIFY_ERROR")
