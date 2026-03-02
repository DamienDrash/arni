"""ARIIA v2.0 – Contact Sync Webhook Handler.

@ARCH: Contacts-Sync Refactoring, Phase 3
Handles incoming webhooks from external integrations (Shopify, HubSpot, etc.)
and triggers incremental syncs or direct contact updates.

Design:
  - Generic webhook router that dispatches to integration-specific handlers
  - HMAC signature verification per integration
  - Idempotency via webhook_id tracking
  - Async processing: acknowledge webhook immediately, process in background
"""

from __future__ import annotations

import hashlib
import hmac
import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Request, Response, HTTPException

from app.core.db import SessionLocal
from app.core.integration_models import TenantIntegration, WebhookEndpoint, SyncLog
from app.core.credential_vault import credential_vault

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# ── Webhook ID Tracking (in-memory, could be Redis) ──────────────────────────

_processed_webhooks: Dict[str, datetime] = {}
_MAX_TRACKED = 10_000


def _is_duplicate(webhook_id: str) -> bool:
    """Check if webhook was already processed (idempotency)."""
    if webhook_id in _processed_webhooks:
        return True
    if len(_processed_webhooks) > _MAX_TRACKED:
        # Evict oldest entries
        oldest = sorted(_processed_webhooks.items(), key=lambda x: x[1])[:_MAX_TRACKED // 2]
        for k, _ in oldest:
            _processed_webhooks.pop(k, None)
    _processed_webhooks[webhook_id] = datetime.now(timezone.utc)
    return False


# ── Signature Verification ────────────────────────────────────────────────────

def verify_shopify_hmac(body: bytes, secret: str, header_hmac: str) -> bool:
    """Verify Shopify webhook HMAC-SHA256 signature."""
    computed = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    import base64
    expected = base64.b64encode(computed).decode("utf-8")
    return hmac.compare_digest(expected, header_hmac)


def verify_hubspot_signature(body: bytes, secret: str, header_sig: str, version: str = "v3") -> bool:
    """Verify HubSpot webhook signature."""
    if version == "v3":
        computed = hashlib.sha256(secret.encode("utf-8") + body).hexdigest()
        return hmac.compare_digest(computed, header_sig)
    return True  # Fallback for older versions


def verify_woocommerce_signature(body: bytes, secret: str, header_sig: str) -> bool:
    """Verify WooCommerce webhook signature (HMAC-SHA256 base64)."""
    computed = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    import base64
    expected = base64.b64encode(computed).decode("utf-8")
    return hmac.compare_digest(expected, header_sig)


# ── Generic Webhook Endpoint ─────────────────────────────────────────────────

@router.post("/{integration_id}/{tenant_id}")
async def receive_webhook(
    integration_id: str,
    tenant_id: int,
    request: Request,
) -> Response:
    """
    Generic webhook receiver.
    
    URL pattern: /webhooks/{integration_id}/{tenant_id}
    Example: /webhooks/shopify/42
    
    Each integration has its own signature verification and payload parsing.
    """
    body = await request.body()
    headers = dict(request.headers)

    logger.info(
        "webhook.received",
        integration_id=integration_id,
        tenant_id=tenant_id,
        content_length=len(body),
    )

    # Verify the tenant integration exists and is enabled
    db = SessionLocal()
    try:
        ti = (
            db.query(TenantIntegration)
            .filter(
                TenantIntegration.tenant_id == tenant_id,
                TenantIntegration.integration_id == integration_id,
                TenantIntegration.enabled == True,
            )
            .first()
        )

        if not ti:
            logger.warning("webhook.integration_not_found", integration_id=integration_id, tenant_id=tenant_id)
            raise HTTPException(status_code=404, detail="Integration not found or disabled")

        # Get webhook secret for signature verification
        webhook_secret = None
        try:
            creds = credential_vault.get_credentials(tenant_id, integration_id)
            webhook_secret = creds.get("webhook_secret")
        except Exception:
            pass

        # Verify signature based on integration type
        if not _verify_signature(integration_id, body, headers, webhook_secret):
            logger.warning("webhook.signature_invalid", integration_id=integration_id, tenant_id=tenant_id)
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        # Parse payload
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body.decode("utf-8", errors="replace")}

        # Check idempotency
        webhook_id = _extract_webhook_id(integration_id, headers, payload)
        if webhook_id and _is_duplicate(webhook_id):
            logger.info("webhook.duplicate", webhook_id=webhook_id)
            return Response(status_code=200, content='{"status": "already_processed"}')

        # Log the webhook
        _log_webhook(db, tenant_id, integration_id, webhook_id, payload)

        # Process asynchronously
        import asyncio
        asyncio.create_task(
            _process_webhook(tenant_id, integration_id, payload, headers)
        )

        return Response(status_code=200, content='{"status": "accepted"}')

    except HTTPException:
        raise
    except Exception as e:
        logger.error("webhook.error", error=str(e), traceback=traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal error processing webhook")
    finally:
        db.close()


@router.get("/{integration_id}/{tenant_id}")
async def webhook_verification(
    integration_id: str,
    tenant_id: int,
    request: Request,
) -> Response:
    """
    Handle webhook verification challenges (used by some platforms).
    E.g., HubSpot sends a GET request to verify the endpoint.
    """
    params = dict(request.query_params)

    # Shopify verification
    if integration_id == "shopify":
        return Response(status_code=200, content="OK")

    # HubSpot verification
    if integration_id == "hubspot" and "challenge" in params:
        return Response(
            status_code=200,
            content=params["challenge"],
            media_type="text/plain",
        )

    return Response(status_code=200, content="OK")


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _verify_signature(
    integration_id: str,
    body: bytes,
    headers: Dict[str, str],
    webhook_secret: Optional[str],
) -> bool:
    """Dispatch signature verification to integration-specific handler."""
    if not webhook_secret:
        # No secret configured – skip verification (log warning)
        logger.warning("webhook.no_secret_configured", integration_id=integration_id)
        return True

    if integration_id == "shopify":
        hmac_header = headers.get("x-shopify-hmac-sha256", "")
        return verify_shopify_hmac(body, webhook_secret, hmac_header)

    elif integration_id == "hubspot":
        sig_header = headers.get("x-hubspot-signature-v3", headers.get("x-hubspot-signature", ""))
        return verify_hubspot_signature(body, webhook_secret, sig_header)

    elif integration_id == "woocommerce":
        sig_header = headers.get("x-wc-webhook-signature", "")
        return verify_woocommerce_signature(body, webhook_secret, sig_header)

    # Unknown integration – accept if secret matches a simple token
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return hmac.compare_digest(auth_header[7:], webhook_secret)

    return True


def _extract_webhook_id(
    integration_id: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Optional[str]:
    """Extract a unique webhook ID for idempotency."""
    if integration_id == "shopify":
        return headers.get("x-shopify-webhook-id")
    elif integration_id == "hubspot":
        return payload.get("requestId") or payload.get("correlationId")
    elif integration_id == "woocommerce":
        return headers.get("x-wc-webhook-id")
    return None


def _log_webhook(
    db,
    tenant_id: int,
    integration_id: str,
    webhook_id: Optional[str],
    payload: Dict[str, Any],
) -> None:
    """Log webhook receipt to database."""
    try:
        from app.core.integration_models import WebhookEndpoint
        endpoint = (
            db.query(WebhookEndpoint)
            .filter(
                WebhookEndpoint.tenant_id == tenant_id,
                WebhookEndpoint.integration_id == integration_id,
            )
            .first()
        )
        if endpoint:
            endpoint.last_received_at = datetime.now(timezone.utc)
            endpoint.total_received = (endpoint.total_received or 0) + 1
            db.commit()
    except Exception as e:
        logger.debug("webhook.log_error", error=str(e))
        db.rollback()


async def _process_webhook(
    tenant_id: int,
    integration_id: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
) -> None:
    """Process webhook payload asynchronously."""
    try:
        logger.info("webhook.processing", integration_id=integration_id, tenant_id=tenant_id)

        # Determine the event type
        event_type = _extract_event_type(integration_id, headers, payload)

        if not event_type:
            logger.debug("webhook.unknown_event", integration_id=integration_id)
            return

        # Only process contact-related events
        contact_events = {
            "shopify": ["customers/create", "customers/update", "customers/delete"],
            "hubspot": ["contact.creation", "contact.propertyChange", "contact.deletion"],
            "woocommerce": ["customer.created", "customer.updated", "customer.deleted"],
        }

        relevant_events = contact_events.get(integration_id, [])
        if event_type not in relevant_events:
            logger.debug("webhook.irrelevant_event", event_type=event_type, integration_id=integration_id)
            return

        # Trigger incremental sync for the specific contact
        from app.contacts.sync_core import sync_core

        result = await sync_core.run_sync(
            tenant_id=tenant_id,
            integration_id=integration_id,
            triggered_by="webhook",
            sync_mode="incremental",
        )

        logger.info(
            "webhook.sync_completed",
            integration_id=integration_id,
            tenant_id=tenant_id,
            success=result.get("success"),
            records_created=result.get("records_created", 0),
            records_updated=result.get("records_updated", 0),
        )

    except Exception as e:
        logger.error(
            "webhook.processing_error",
            integration_id=integration_id,
            tenant_id=tenant_id,
            error=str(e),
            traceback=traceback.format_exc(),
        )


def _extract_event_type(
    integration_id: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Optional[str]:
    """Extract the event type from webhook headers/payload."""
    if integration_id == "shopify":
        return headers.get("x-shopify-topic")
    elif integration_id == "hubspot":
        # HubSpot sends an array of events
        if isinstance(payload, list) and len(payload) > 0:
            return payload[0].get("subscriptionType")
        return payload.get("subscriptionType")
    elif integration_id == "woocommerce":
        return headers.get("x-wc-webhook-topic")
    return None


# ── Webhook URL Generator ────────────────────────────────────────────────────

def get_webhook_url(tenant_id: int, integration_id: str, base_url: str = "") -> str:
    """Generate the webhook URL for a tenant integration."""
    if not base_url:
        base_url = "https://api.ariia.io"  # Default, should be from config
    return f"{base_url}/webhooks/{integration_id}/{tenant_id}"
