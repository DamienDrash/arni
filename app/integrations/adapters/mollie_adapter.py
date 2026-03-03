"""ARIIA v2.0 – Mollie Payment Adapter.

@ARCH: Sprint 3 (Integration Roadmap), Task S3.3
Concrete adapter for Mollie payment processing via API v2.
Uses API Key authentication. Ideal for European payment methods
(iDEAL, SEPA, Bancontact, Sofort, etc.).

Supported Capabilities:
  - payment.create             → Create a Mollie payment
  - payment.status             → Get payment status
  - payment.refund             → Refund a payment
  - payment.list               → List payments
  - payment.methods.list       → List available payment methods
  - payment.subscription.create → Create a Mollie subscription
  - payment.subscription.cancel → Cancel a Mollie subscription
  - payment.subscription.list   → List subscriptions for a customer
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class MollieAdapter(BaseAdapter):
    """Adapter for Mollie API v2 payment processing.

    Specializes in European payment methods and provides a clean API
    for payments, refunds, subscriptions, and method discovery.
    """

    MOLLIE_API_BASE = "https://api.mollie.com/v2"

    @property
    def integration_id(self) -> str:
        return "mollie"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "payment.create",
            "payment.status",
            "payment.refund",
            "payment.list",
            "payment.methods.list",
            "payment.subscription.create",
            "payment.subscription.cancel",
            "payment.subscription.list",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "Mollie"

    @property
    def category(self) -> str:
        return "payment"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "required": True,
                    "help_text": "Mollie API Key (live oder test).",
                },
            ],
        }

    async def get_contacts(
        self,
        tenant_id: int,
        config: dict,
        last_sync_at=None,
        sync_mode=None,
    ) -> "SyncResult":
        from app.integrations.adapters.base import SyncResult
        return SyncResult(
            success=True,
            records_fetched=0,
            contacts=[],
            metadata={"note": "Mollie does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="Mollie-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate Mollie method."""
        handlers = {
            "payment.create": self._create_payment,
            "payment.status": self._get_payment_status,
            "payment.refund": self._refund_payment,
            "payment.list": self._list_payments,
            "payment.methods.list": self._list_methods,
            "payment.subscription.create": self._create_subscription,
            "payment.subscription.cancel": self._cancel_subscription,
            "payment.subscription.list": self._list_subscriptions,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_api_key(self, tenant_id: int) -> tuple[str | None, AdapterResult | None]:
        """Get Mollie API key for a tenant."""
        try:
            from app.gateway.persistence import persistence

            api_key = (persistence.get_setting(f"mollie_api_key_{tenant_id}") or
                       persistence.get_setting("mollie_api_key", "")).strip()
            if not api_key:
                return None, AdapterResult(
                    success=False,
                    error="Mollie-API-Key nicht konfiguriert. Bitte in den Integrationseinstellungen hinterlegen.",
                    error_code="MOLLIE_NOT_CONFIGURED",
                )
            return api_key, None
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"Mollie configuration error: {exc}",
                error_code="MOLLIE_CONFIG_ERROR",
            )

    async def _mollie_request(
        self, tenant_id: int, method: str, path: str, json_data: dict | None = None
    ) -> tuple[dict | None, AdapterResult | None]:
        """Make an authenticated request to the Mollie API."""
        import httpx

        api_key, err = self._get_api_key(tenant_id)
        if err:
            return None, err

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method,
                    f"{self.MOLLIE_API_BASE}{path}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=json_data,
                )
                resp.raise_for_status()
                return resp.json() if resp.content else {}, None
        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text[:500] if exc.response else "No response"
            return None, AdapterResult(
                success=False,
                error=f"Mollie API error ({exc.response.status_code}): {error_body}",
                error_code=f"MOLLIE_HTTP_{exc.response.status_code}",
            )
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"Mollie request failed: {exc}",
                error_code="MOLLIE_REQUEST_FAILED",
            )

    # ── payment.create ───────────────────────────────────────────────────

    async def _create_payment(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a Mollie payment.

        Required kwargs:
            amount (str): Payment amount (e.g., "29.99").
            description (str): Payment description.
        Optional kwargs:
            currency (str): Currency code (default: "EUR").
            redirect_url (str): URL after payment completion.
            webhook_url (str): URL for status updates.
            method (str): Specific payment method (ideal, creditcard, bancontact, etc.).
            metadata (dict): Additional metadata.
        """
        amount = kwargs.get("amount")
        description = kwargs.get("description")

        if not amount or not description:
            return AdapterResult(
                success=False,
                error="Parameters 'amount' and 'description' are required",
                error_code="MISSING_PARAM",
            )

        payment_body: dict[str, Any] = {
            "amount": {
                "currency": kwargs.get("currency", "EUR"),
                "value": str(amount),
            },
            "description": description,
            "redirectUrl": kwargs.get("redirect_url", "https://app.ariia.io/payment/complete"),
        }

        if kwargs.get("webhook_url"):
            payment_body["webhookUrl"] = kwargs["webhook_url"]
        if kwargs.get("method"):
            payment_body["method"] = kwargs["method"]
        if kwargs.get("metadata"):
            payment_body["metadata"] = kwargs["metadata"]

        data, err = await self._mollie_request(tenant_id, "POST", "/payments", payment_body)
        if err:
            return err

        checkout_url = data.get("_links", {}).get("checkout", {}).get("href")

        return AdapterResult(
            success=True,
            data={
                "payment_id": data.get("id"),
                "status": data.get("status"),
                "checkout_url": checkout_url,
                "amount": amount,
                "currency": kwargs.get("currency", "EUR"),
                "method": data.get("method"),
                "created_at": data.get("createdAt"),
            },
            metadata={"tenant_id": tenant_id},
        )

    # ── payment.status ───────────────────────────────────────────────────

    async def _get_payment_status(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get the status of a Mollie payment.

        Required kwargs:
            payment_id (str): The Mollie payment ID.
        """
        payment_id = kwargs.get("payment_id")
        if not payment_id:
            return AdapterResult(success=False, error="Parameter 'payment_id' is required", error_code="MISSING_PARAM")

        data, err = await self._mollie_request(tenant_id, "GET", f"/payments/{payment_id}")
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "payment_id": data.get("id"),
                "status": data.get("status"),
                "amount": data.get("amount", {}).get("value"),
                "currency": data.get("amount", {}).get("currency"),
                "description": data.get("description"),
                "method": data.get("method"),
                "created_at": data.get("createdAt"),
                "paid_at": data.get("paidAt"),
                "expired_at": data.get("expiredAt"),
                "metadata": data.get("metadata"),
            },
        )

    # ── payment.refund ───────────────────────────────────────────────────

    async def _refund_payment(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Refund a Mollie payment (full or partial).

        Required kwargs:
            payment_id (str): The Mollie payment ID to refund.
        Optional kwargs:
            amount (str): Refund amount (full refund if omitted).
            currency (str): Currency code (default: "EUR").
            description (str): Refund description.
        """
        payment_id = kwargs.get("payment_id")
        if not payment_id:
            return AdapterResult(success=False, error="Parameter 'payment_id' is required", error_code="MISSING_PARAM")

        refund_body: dict[str, Any] = {}
        if kwargs.get("amount"):
            refund_body["amount"] = {
                "currency": kwargs.get("currency", "EUR"),
                "value": str(kwargs["amount"]),
            }
        if kwargs.get("description"):
            refund_body["description"] = kwargs["description"]

        data, err = await self._mollie_request(
            tenant_id, "POST",
            f"/payments/{payment_id}/refunds",
            refund_body if refund_body else None,
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "refund_id": data.get("id"),
                "payment_id": data.get("paymentId"),
                "status": data.get("status"),
                "amount": data.get("amount", {}).get("value"),
                "currency": data.get("amount", {}).get("currency"),
                "created_at": data.get("createdAt"),
            },
        )

    # ── payment.list ─────────────────────────────────────────────────────

    async def _list_payments(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List Mollie payments.

        Optional kwargs:
            limit (int): Number of payments to return (default: 25, max: 250).
            from_id (str): Start listing from this payment ID (pagination).
        """
        params = []
        limit = kwargs.get("limit", 25)
        params.append(f"limit={limit}")
        if kwargs.get("from_id"):
            params.append(f"from={kwargs['from_id']}")

        query = "?" + "&".join(params) if params else ""

        data, err = await self._mollie_request(tenant_id, "GET", f"/payments{query}")
        if err:
            return err

        payments = []
        for p in data.get("_embedded", {}).get("payments", []):
            payments.append({
                "id": p.get("id"),
                "status": p.get("status"),
                "amount": p.get("amount", {}).get("value"),
                "currency": p.get("amount", {}).get("currency"),
                "description": p.get("description"),
                "method": p.get("method"),
                "created_at": p.get("createdAt"),
            })

        return AdapterResult(
            success=True,
            data=payments,
            metadata={"count": data.get("count", len(payments))},
        )

    # ── payment.methods.list ─────────────────────────────────────────────

    async def _list_methods(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List available payment methods for the Mollie account.

        Optional kwargs:
            amount (str): Filter methods available for this amount.
            currency (str): Filter by currency (default: "EUR").
            locale (str): Locale for method names (default: "de_DE").
        """
        params = []
        if kwargs.get("amount"):
            params.append(f"amount[value]={kwargs['amount']}")
            params.append(f"amount[currency]={kwargs.get('currency', 'EUR')}")
        if kwargs.get("locale"):
            params.append(f"locale={kwargs['locale']}")
        else:
            params.append("locale=de_DE")

        query = "?" + "&".join(params) if params else ""

        data, err = await self._mollie_request(tenant_id, "GET", f"/methods{query}")
        if err:
            return err

        methods = []
        for m in data.get("_embedded", {}).get("methods", data.get("data", [])):
            methods.append({
                "id": m.get("id"),
                "description": m.get("description"),
                "minimum_amount": m.get("minimumAmount", {}).get("value"),
                "maximum_amount": m.get("maximumAmount", {}).get("value"),
                "image": m.get("image", {}).get("svg"),
            })

        return AdapterResult(
            success=True,
            data=methods,
            metadata={"count": len(methods)},
        )

    # ── payment.subscription.create ──────────────────────────────────────

    async def _create_subscription(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a Mollie subscription for a customer.

        Required kwargs:
            customer_id (str): The Mollie customer ID.
            amount (str): Subscription amount.
            interval (str): Billing interval (e.g., "1 month", "1 year").
            description (str): Subscription description.
        Optional kwargs:
            currency (str): Currency code (default: "EUR").
            start_date (str): Start date in YYYY-MM-DD format.
            webhook_url (str): URL for subscription webhooks.
            method (str): Payment method for recurring charges.
        """
        customer_id = kwargs.get("customer_id")
        amount = kwargs.get("amount")
        interval = kwargs.get("interval")
        description = kwargs.get("description")

        if not all([customer_id, amount, interval, description]):
            return AdapterResult(
                success=False,
                error="Parameters 'customer_id', 'amount', 'interval', and 'description' are required",
                error_code="MISSING_PARAM",
            )

        sub_body: dict[str, Any] = {
            "amount": {
                "currency": kwargs.get("currency", "EUR"),
                "value": str(amount),
            },
            "interval": interval,
            "description": description,
        }

        if kwargs.get("start_date"):
            sub_body["startDate"] = kwargs["start_date"]
        if kwargs.get("webhook_url"):
            sub_body["webhookUrl"] = kwargs["webhook_url"]
        if kwargs.get("method"):
            sub_body["method"] = kwargs["method"]

        data, err = await self._mollie_request(
            tenant_id, "POST",
            f"/customers/{customer_id}/subscriptions",
            sub_body,
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "subscription_id": data.get("id"),
                "customer_id": customer_id,
                "status": data.get("status"),
                "amount": amount,
                "interval": interval,
                "description": description,
                "start_date": data.get("startDate"),
                "next_payment_date": data.get("nextPaymentDate"),
            },
        )

    # ── payment.subscription.cancel ──────────────────────────────────────

    async def _cancel_subscription(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Cancel a Mollie subscription.

        Required kwargs:
            customer_id (str): The Mollie customer ID.
            subscription_id (str): The Mollie subscription ID.
        """
        customer_id = kwargs.get("customer_id")
        subscription_id = kwargs.get("subscription_id")

        if not customer_id or not subscription_id:
            return AdapterResult(
                success=False,
                error="Parameters 'customer_id' and 'subscription_id' are required",
                error_code="MISSING_PARAM",
            )

        _, err = await self._mollie_request(
            tenant_id, "DELETE",
            f"/customers/{customer_id}/subscriptions/{subscription_id}",
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "status": "cancelled",
                "action": "subscription_cancelled",
            },
        )

    # ── payment.subscription.list ────────────────────────────────────────

    async def _list_subscriptions(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List subscriptions for a Mollie customer.

        Required kwargs:
            customer_id (str): The Mollie customer ID.
        """
        customer_id = kwargs.get("customer_id")
        if not customer_id:
            return AdapterResult(success=False, error="Parameter 'customer_id' is required", error_code="MISSING_PARAM")

        data, err = await self._mollie_request(
            tenant_id, "GET",
            f"/customers/{customer_id}/subscriptions",
        )
        if err:
            return err

        subs = []
        for s in data.get("_embedded", {}).get("subscriptions", []):
            subs.append({
                "id": s.get("id"),
                "status": s.get("status"),
                "amount": s.get("amount", {}).get("value"),
                "currency": s.get("amount", {}).get("currency"),
                "interval": s.get("interval"),
                "description": s.get("description"),
                "start_date": s.get("startDate"),
                "next_payment_date": s.get("nextPaymentDate"),
            })

        return AdapterResult(
            success=True,
            data=subs,
            metadata={"count": len(subs), "customer_id": customer_id},
        )

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Mollie is configured and accessible."""
        api_key, err = self._get_api_key(tenant_id)
        if err:
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": err.error},
            )

        # Try listing methods as a simple health check
        data, req_err = await self._mollie_request(tenant_id, "GET", "/methods?limit=1")
        if req_err:
            return AdapterResult(
                success=True,
                data={"status": "ERROR", "reason": req_err.error},
            )

        is_test = api_key.startswith("test_") if api_key else False
        return AdapterResult(
            success=True,
            data={
                "status": "CONNECTED",
                "mode": "test" if is_test else "live",
                "methods_available": data.get("count", 0),
            },
        )
