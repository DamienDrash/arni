"""ARIIA v2.0 – PayPal Payment Adapter.

@ARCH: Sprint 3 (Integration Roadmap), Task S3.2
Concrete adapter for PayPal payment processing via REST API v2.
Uses OAuth 2.0 (Client ID + Secret) for authentication.

Supported Capabilities:
  - payment.order.create       → Create a PayPal order
  - payment.order.capture      → Capture an approved order
  - payment.order.details      → Get order details
  - payment.subscription.create → Create a PayPal subscription
  - payment.subscription.cancel → Cancel a PayPal subscription
  - payment.subscription.details → Get subscription details
  - payment.webhook.process    → Process a PayPal webhook event
  - payment.payout.create      → Create a payout to a recipient
"""

from __future__ import annotations

import base64
from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class PayPalAdapter(BaseAdapter):
    """Adapter for PayPal REST API v2 payment processing.

    Handles orders, subscriptions, webhooks, and payouts.
    Credentials are loaded from the tenant's integration settings.
    """

    @property
    def integration_id(self) -> str:
        return "paypal"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "payment.order.create",
            "payment.order.capture",
            "payment.order.details",
            "payment.subscription.create",
            "payment.subscription.cancel",
            "payment.subscription.details",
            "payment.webhook.process",
            "payment.payout.create",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "PayPal"

    @property
    def category(self) -> str:
        return "payment"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "client_id",
                    "label": "Client ID",
                    "type": "text",
                    "required": True,
                    "help_text": "PayPal REST API Client ID.",
                },
                {
                    "key": "client_secret",
                    "label": "Client Secret",
                    "type": "password",
                    "required": True,
                    "help_text": "PayPal REST API Client Secret.",
                },
                {
                    "key": "sandbox",
                    "label": "Sandbox-Modus",
                    "type": "checkbox",
                    "required": False,
                    "help_text": "Aktivieren für PayPal Sandbox-Umgebung.",
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
            metadata={"note": "PayPal does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="PayPal-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate PayPal method."""
        handlers = {
            "payment.order.create": self._create_order,
            "payment.order.capture": self._capture_order,
            "payment.order.details": self._get_order_details,
            "payment.subscription.create": self._create_subscription,
            "payment.subscription.cancel": self._cancel_subscription,
            "payment.subscription.details": self._get_subscription_details,
            "payment.webhook.process": self._process_webhook,
            "payment.payout.create": self._create_payout,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_credentials(self, tenant_id: int) -> tuple[str | None, str | None, str]:
        """Get PayPal credentials for a tenant.

        Returns (client_id, client_secret, base_url).
        """
        try:
            from app.gateway.persistence import persistence

            client_id = (persistence.get_setting(f"paypal_client_id_{tenant_id}") or
                         persistence.get_setting("paypal_client_id", "")).strip()
            client_secret = (persistence.get_setting(f"paypal_client_secret_{tenant_id}") or
                             persistence.get_setting("paypal_client_secret", "")).strip()
            sandbox = (persistence.get_setting(f"paypal_sandbox_{tenant_id}") or
                       persistence.get_setting("paypal_sandbox", "true")).lower() == "true"

            base_url = "https://api-m.sandbox.paypal.com" if sandbox else "https://api-m.paypal.com"
            return client_id, client_secret, base_url
        except Exception:
            return None, None, "https://api-m.sandbox.paypal.com"

    async def _get_access_token(self, tenant_id: int) -> tuple[str | None, AdapterResult | None]:
        """Obtain an OAuth 2.0 access token from PayPal."""
        import httpx

        client_id, client_secret, base_url = self._get_credentials(tenant_id)
        if not client_id or not client_secret:
            return None, AdapterResult(
                success=False,
                error="PayPal-Zugangsdaten nicht konfiguriert. Bitte Client ID und Secret in den Integrationseinstellungen hinterlegen.",
                error_code="PAYPAL_NOT_CONFIGURED",
            )

        try:
            auth_str = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{base_url}/v1/oauth2/token",
                    headers={
                        "Authorization": f"Basic {auth_str}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data="grant_type=client_credentials",
                )
                resp.raise_for_status()
                token = resp.json().get("access_token")
                return token, None
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"PayPal OAuth failed: {exc}",
                error_code="PAYPAL_AUTH_FAILED",
            )

    async def _paypal_request(
        self, tenant_id: int, method: str, path: str, json_data: dict | None = None
    ) -> tuple[dict | None, AdapterResult | None]:
        """Make an authenticated request to the PayPal API."""
        import httpx

        token, err = await self._get_access_token(tenant_id)
        if err:
            return None, err

        _, _, base_url = self._get_credentials(tenant_id)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method,
                    f"{base_url}{path}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    json=json_data,
                )
                resp.raise_for_status()
                return resp.json() if resp.content else {}, None
        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text[:500] if exc.response else "No response"
            return None, AdapterResult(
                success=False,
                error=f"PayPal API error ({exc.response.status_code}): {error_body}",
                error_code=f"PAYPAL_HTTP_{exc.response.status_code}",
            )
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"PayPal request failed: {exc}",
                error_code="PAYPAL_REQUEST_FAILED",
            )

    # ── payment.order.create ─────────────────────────────────────────────

    async def _create_order(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a PayPal order.

        Required kwargs:
            amount (str): Order amount (e.g., "29.99").
            currency (str): Currency code (default: "EUR").
        Optional kwargs:
            description (str): Order description.
            return_url (str): URL after approval.
            cancel_url (str): URL after cancellation.
            items (list[dict]): Line items with name, quantity, unit_amount.
        """
        amount = kwargs.get("amount")
        if not amount:
            return AdapterResult(
                success=False,
                error="Parameter 'amount' is required",
                error_code="MISSING_PARAM",
            )

        currency = kwargs.get("currency", "EUR")
        order_body = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": currency,
                    "value": str(amount),
                },
                "description": kwargs.get("description", "ARIIA Payment"),
            }],
        }

        if kwargs.get("return_url") or kwargs.get("cancel_url"):
            order_body["application_context"] = {
                "return_url": kwargs.get("return_url", "https://app.ariia.io/payment/success"),
                "cancel_url": kwargs.get("cancel_url", "https://app.ariia.io/payment/cancel"),
            }

        if kwargs.get("items"):
            order_body["purchase_units"][0]["items"] = kwargs["items"]
            breakdown_value = str(amount)
            order_body["purchase_units"][0]["amount"]["breakdown"] = {
                "item_total": {"currency_code": currency, "value": breakdown_value}
            }

        data, err = await self._paypal_request(tenant_id, "POST", "/v2/checkout/orders", order_body)
        if err:
            return err

        approval_url = None
        for link in data.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break

        return AdapterResult(
            success=True,
            data={
                "order_id": data.get("id"),
                "status": data.get("status"),
                "approval_url": approval_url,
                "amount": amount,
                "currency": currency,
            },
            metadata={"tenant_id": tenant_id},
        )

    # ── payment.order.capture ────────────────────────────────────────────

    async def _capture_order(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Capture an approved PayPal order.

        Required kwargs:
            order_id (str): The PayPal order ID to capture.
        """
        order_id = kwargs.get("order_id")
        if not order_id:
            return AdapterResult(success=False, error="Parameter 'order_id' is required", error_code="MISSING_PARAM")

        data, err = await self._paypal_request(tenant_id, "POST", f"/v2/checkout/orders/{order_id}/capture")
        if err:
            return err

        capture = {}
        pu = data.get("purchase_units", [{}])
        if pu and pu[0].get("payments", {}).get("captures"):
            cap = pu[0]["payments"]["captures"][0]
            capture = {
                "capture_id": cap.get("id"),
                "amount": cap.get("amount", {}).get("value"),
                "currency": cap.get("amount", {}).get("currency_code"),
            }

        return AdapterResult(
            success=True,
            data={
                "order_id": data.get("id"),
                "status": data.get("status"),
                **capture,
            },
        )

    # ── payment.order.details ────────────────────────────────────────────

    async def _get_order_details(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get details of a PayPal order.

        Required kwargs:
            order_id (str): The PayPal order ID.
        """
        order_id = kwargs.get("order_id")
        if not order_id:
            return AdapterResult(success=False, error="Parameter 'order_id' is required", error_code="MISSING_PARAM")

        data, err = await self._paypal_request(tenant_id, "GET", f"/v2/checkout/orders/{order_id}")
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "order_id": data.get("id"),
                "status": data.get("status"),
                "intent": data.get("intent"),
                "payer": data.get("payer", {}),
                "purchase_units": data.get("purchase_units", []),
                "create_time": data.get("create_time"),
            },
        )

    # ── payment.subscription.create ──────────────────────────────────────

    async def _create_subscription(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a PayPal subscription.

        Required kwargs:
            plan_id (str): The PayPal billing plan ID.
        Optional kwargs:
            return_url (str): URL after approval.
            cancel_url (str): URL after cancellation.
            subscriber (dict): Subscriber info (name, email_address).
        """
        plan_id = kwargs.get("plan_id")
        if not plan_id:
            return AdapterResult(success=False, error="Parameter 'plan_id' is required", error_code="MISSING_PARAM")

        sub_body: dict[str, Any] = {
            "plan_id": plan_id,
            "application_context": {
                "return_url": kwargs.get("return_url", "https://app.ariia.io/payment/success"),
                "cancel_url": kwargs.get("cancel_url", "https://app.ariia.io/payment/cancel"),
                "brand_name": "ARIIA",
                "user_action": "SUBSCRIBE_NOW",
            },
        }

        if kwargs.get("subscriber"):
            sub_body["subscriber"] = kwargs["subscriber"]

        data, err = await self._paypal_request(tenant_id, "POST", "/v1/billing/subscriptions", sub_body)
        if err:
            return err

        approval_url = None
        for link in data.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break

        return AdapterResult(
            success=True,
            data={
                "subscription_id": data.get("id"),
                "status": data.get("status"),
                "approval_url": approval_url,
                "plan_id": plan_id,
            },
        )

    # ── payment.subscription.cancel ──────────────────────────────────────

    async def _cancel_subscription(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Cancel a PayPal subscription.

        Required kwargs:
            subscription_id (str): The PayPal subscription ID.
        Optional kwargs:
            reason (str): Cancellation reason.
        """
        subscription_id = kwargs.get("subscription_id")
        if not subscription_id:
            return AdapterResult(success=False, error="Parameter 'subscription_id' is required", error_code="MISSING_PARAM")

        cancel_body = {"reason": kwargs.get("reason", "Cancelled by user")}
        _, err = await self._paypal_request(
            tenant_id, "POST",
            f"/v1/billing/subscriptions/{subscription_id}/cancel",
            cancel_body,
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "subscription_id": subscription_id,
                "status": "CANCELLED",
                "action": "subscription_cancelled",
            },
        )

    # ── payment.subscription.details ─────────────────────────────────────

    async def _get_subscription_details(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get details of a PayPal subscription.

        Required kwargs:
            subscription_id (str): The PayPal subscription ID.
        """
        subscription_id = kwargs.get("subscription_id")
        if not subscription_id:
            return AdapterResult(success=False, error="Parameter 'subscription_id' is required", error_code="MISSING_PARAM")

        data, err = await self._paypal_request(
            tenant_id, "GET",
            f"/v1/billing/subscriptions/{subscription_id}",
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "subscription_id": data.get("id"),
                "status": data.get("status"),
                "plan_id": data.get("plan_id"),
                "start_time": data.get("start_time"),
                "billing_info": data.get("billing_info", {}),
                "subscriber": data.get("subscriber", {}),
            },
        )

    # ── payment.webhook.process ──────────────────────────────────────────

    async def _process_webhook(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Process a PayPal webhook event.

        Required kwargs:
            event_type (str): The PayPal event type.
            resource (dict): The event resource object.
        Optional kwargs:
            event_id (str): The PayPal event ID.
        """
        event_type = kwargs.get("event_type")
        resource = kwargs.get("resource")

        if not event_type or not resource:
            return AdapterResult(
                success=False,
                error="Parameters 'event_type' and 'resource' are required",
                error_code="MISSING_PARAM",
            )

        event_id = kwargs.get("event_id", "unknown")

        # Map PayPal events to actions
        action_map = {
            "PAYMENT.CAPTURE.COMPLETED": "payment_captured",
            "PAYMENT.CAPTURE.DENIED": "payment_denied",
            "BILLING.SUBSCRIPTION.CREATED": "subscription_created",
            "BILLING.SUBSCRIPTION.ACTIVATED": "subscription_activated",
            "BILLING.SUBSCRIPTION.CANCELLED": "subscription_cancelled",
            "BILLING.SUBSCRIPTION.SUSPENDED": "subscription_suspended",
            "BILLING.SUBSCRIPTION.PAYMENT.FAILED": "subscription_payment_failed",
        }

        action = action_map.get(event_type, "unhandled")

        logger.info("paypal_adapter.webhook_processed",
                     event_type=event_type, event_id=event_id, action=action)

        return AdapterResult(
            success=True,
            data={
                "event_type": event_type,
                "event_id": event_id,
                "action": action,
                "resource_id": resource.get("id"),
                "resource_type": resource.get("resource_type", type(resource).__name__),
            },
            metadata={"tenant_id": tenant_id},
        )

    # ── payment.payout.create ────────────────────────────────────────────

    async def _create_payout(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Create a PayPal payout to a recipient.

        Required kwargs:
            recipient_email (str): PayPal email of the recipient.
            amount (str): Payout amount.
        Optional kwargs:
            currency (str): Currency code (default: "EUR").
            note (str): Note to the recipient.
            sender_item_id (str): Unique item ID for tracking.
        """
        recipient = kwargs.get("recipient_email")
        amount = kwargs.get("amount")

        if not recipient or not amount:
            return AdapterResult(
                success=False,
                error="Parameters 'recipient_email' and 'amount' are required",
                error_code="MISSING_PARAM",
            )

        currency = kwargs.get("currency", "EUR")
        payout_body = {
            "sender_batch_header": {
                "sender_batch_id": kwargs.get("sender_item_id", f"ariia_payout_{tenant_id}_{int(__import__('time').time())}"),
                "email_subject": "You have a payout!",
                "email_message": kwargs.get("note", "You received a payout from ARIIA."),
            },
            "items": [{
                "recipient_type": "EMAIL",
                "amount": {"value": str(amount), "currency": currency},
                "receiver": recipient,
                "note": kwargs.get("note", "ARIIA Payout"),
                "sender_item_id": kwargs.get("sender_item_id", f"item_{tenant_id}"),
            }],
        }

        data, err = await self._paypal_request(tenant_id, "POST", "/v1/payments/payouts", payout_body)
        if err:
            return err

        batch_header = data.get("batch_header", {})
        return AdapterResult(
            success=True,
            data={
                "payout_batch_id": batch_header.get("payout_batch_id"),
                "batch_status": batch_header.get("batch_status"),
                "recipient": recipient,
                "amount": amount,
                "currency": currency,
            },
        )

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if PayPal is configured and accessible."""
        token, err = await self._get_access_token(tenant_id)
        if err:
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": err.error},
            )

        return AdapterResult(
            success=True,
            data={"status": "CONNECTED", "has_token": bool(token)},
        )
