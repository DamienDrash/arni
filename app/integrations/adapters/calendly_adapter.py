"""ARIIA v2.0 – Calendly Scheduling Adapter.

@ARCH: Sprint 4 (Integration Roadmap), Task S4.1
Concrete adapter for Calendly API v2 scheduling integration.
Uses Personal Access Token or OAuth 2.0 for authentication.

Supported Capabilities:
  - scheduling.event_types.list    → List available event types
  - scheduling.events.list         → List scheduled events
  - scheduling.events.get          → Get event details
  - scheduling.events.cancel       → Cancel an event
  - scheduling.availability.get    → Get user availability
  - scheduling.invitee.list        → List invitees for an event
  - scheduling.webhook.subscribe   → Subscribe to event webhooks
  - scheduling.webhook.list        → List active webhook subscriptions
"""

from __future__ import annotations

from typing import Any

import structlog

from app.integrations.adapters.base import AdapterResult, BaseAdapter

logger = structlog.get_logger()


class CalendlyAdapter(BaseAdapter):
    """Adapter for Calendly API v2 scheduling integration.

    Handles event types, scheduled events, availability checks,
    invitee management, and webhook subscriptions.
    """

    CALENDLY_API_BASE = "https://api.calendly.com"

    @property
    def integration_id(self) -> str:
        return "calendly"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "scheduling.event_types.list",
            "scheduling.events.list",
            "scheduling.events.get",
            "scheduling.events.cancel",
            "scheduling.availability.get",
            "scheduling.invitee.list",
            "scheduling.webhook.subscribe",
            "scheduling.webhook.list",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "Calendly"

    @property
    def category(self) -> str:
        return "scheduling"

    def get_config_schema(self) -> dict:
        return {
            "fields": [
                {
                    "key": "api_token",
                    "label": "Personal Access Token",
                    "type": "password",
                    "required": True,
                    "help_text": "Calendly Personal Access Token aus den Integrations-Einstellungen.",
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
            metadata={"note": "Calendly does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="Calendly-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate Calendly method."""
        handlers = {
            "scheduling.event_types.list": self._list_event_types,
            "scheduling.events.list": self._list_events,
            "scheduling.events.get": self._get_event,
            "scheduling.events.cancel": self._cancel_event,
            "scheduling.availability.get": self._get_availability,
            "scheduling.invitee.list": self._list_invitees,
            "scheduling.webhook.subscribe": self._subscribe_webhook,
            "scheduling.webhook.list": self._list_webhooks,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_credentials(self, tenant_id: int) -> tuple[str | None, str | None]:
        """Get Calendly credentials for a tenant.

        Returns (api_token, organization_uri).
        Looks up keys using the standard integration naming convention:
          integration_calendly_{tenant_id}_api_key
        Falls back to legacy key names for backwards compatibility.
        """
        try:
            from app.gateway.persistence import persistence

            # Standard integration naming convention (set by Connector Hub)
            api_token = (
                persistence.get_setting(f"integration_calendly_{tenant_id}_api_key", "", tenant_id=tenant_id) or
                # Legacy fallback keys
                persistence.get_setting(f"calendly_api_key_{tenant_id}", "", tenant_id=tenant_id) or
                persistence.get_setting("calendly_api_key", "", tenant_id=tenant_id)
            ).strip()

            org_uri = (
                persistence.get_setting(f"integration_calendly_{tenant_id}_organization_uri", "", tenant_id=tenant_id) or
                # Legacy fallback keys
                persistence.get_setting(f"calendly_organization_uri_{tenant_id}", "", tenant_id=tenant_id) or
                persistence.get_setting("calendly_organization_uri", "", tenant_id=tenant_id)
            ).strip()

            logger.debug("calendly.credentials_loaded",
                         tenant_id=tenant_id,
                         has_token=bool(api_token),
                         has_org_uri=bool(org_uri))

            return api_token or None, org_uri or None
        except Exception as exc:
            logger.error("calendly.credentials_load_failed", tenant_id=tenant_id, error=str(exc))
            return None, None

    async def _calendly_request(
        self, tenant_id: int, method: str, path: str,
        json_data: dict | None = None, params: dict | None = None,
    ) -> tuple[dict | None, AdapterResult | None]:
        """Make an authenticated request to the Calendly API."""
        import httpx

        api_token, _ = self._get_credentials(tenant_id)
        if not api_token:
            return None, AdapterResult(
                success=False,
                error="Calendly-Zugangsdaten nicht konfiguriert. Bitte Personal Access Token in den Integrationseinstellungen hinterlegen.",
                error_code="CALENDLY_NOT_CONFIGURED",
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method,
                    f"{self.CALENDLY_API_BASE}{path}",
                    headers={
                        "Authorization": f"Bearer {api_token}",
                        "Content-Type": "application/json",
                    },
                    json=json_data,
                    params=params,
                )
                resp.raise_for_status()
                return resp.json() if resp.content else {}, None
        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text[:500] if exc.response else "No response"
            return None, AdapterResult(
                success=False,
                error=f"Calendly API error ({exc.response.status_code}): {error_body}",
                error_code=f"CALENDLY_HTTP_{exc.response.status_code}",
            )
        except Exception as exc:
            return None, AdapterResult(
                success=False,
                error=f"Calendly request failed: {exc}",
                error_code="CALENDLY_REQUEST_FAILED",
            )

    async def _get_current_user(self, tenant_id: int) -> tuple[dict | None, AdapterResult | None]:
        """Get the current authenticated user (needed for org/user URIs)."""
        return await self._calendly_request(tenant_id, "GET", "/users/me")

    async def _resolve_user_uri(self, tenant_id: int) -> tuple[str | None, str | None, AdapterResult | None]:
        """Resolve the user URI and organization URI for the authenticated user."""
        data, err = await self._get_current_user(tenant_id)
        if err:
            return None, None, err

        resource = data.get("resource", {})
        user_uri = resource.get("uri")
        org_uri = resource.get("current_organization")

        return user_uri, org_uri, None

    # ── scheduling.event_types.list ──────────────────────────────────────

    async def _list_event_types(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List available event types for the user.

        Optional kwargs:
            active (bool): Filter by active status (default: True).
            count (int): Number of results (default: 20).
        """
        user_uri, org_uri, err = await self._resolve_user_uri(tenant_id)
        if err:
            return err

        params: dict[str, Any] = {"user": user_uri}
        if kwargs.get("active") is not None:
            params["active"] = str(kwargs["active"]).lower()
        params["count"] = kwargs.get("count", 20)

        data, req_err = await self._calendly_request(tenant_id, "GET", "/event_types", params=params)
        if req_err:
            return req_err

        event_types = []
        for et in data.get("collection", []):
            event_types.append({
                "uri": et.get("uri"),
                "name": et.get("name"),
                "slug": et.get("slug"),
                "duration": et.get("duration"),
                "kind": et.get("kind"),
                "active": et.get("active"),
                "scheduling_url": et.get("scheduling_url"),
                "description_plain": et.get("description_plain", ""),
            })

        return AdapterResult(
            success=True,
            data=event_types,
            metadata={"count": len(event_types)},
        )

    # ── scheduling.events.list ───────────────────────────────────────────

    async def _list_events(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List scheduled events.

        Optional kwargs:
            min_start_time (str): ISO 8601 datetime (e.g., "2026-03-01T00:00:00Z").
            max_start_time (str): ISO 8601 datetime.
            status (str): "active" or "canceled".
            count (int): Number of results (default: 20).
            invitee_email (str): Filter by invitee email.
        """
        user_uri, org_uri, err = await self._resolve_user_uri(tenant_id)
        if err:
            return err

        params: dict[str, Any] = {"user": user_uri}
        if kwargs.get("min_start_time"):
            params["min_start_time"] = kwargs["min_start_time"]
        if kwargs.get("max_start_time"):
            params["max_start_time"] = kwargs["max_start_time"]
        if kwargs.get("status"):
            params["status"] = kwargs["status"]
        if kwargs.get("invitee_email"):
            params["invitee_email"] = kwargs["invitee_email"]
        params["count"] = kwargs.get("count", 20)

        data, req_err = await self._calendly_request(tenant_id, "GET", "/scheduled_events", params=params)
        if req_err:
            return req_err

        events = []
        for ev in data.get("collection", []):
            events.append({
                "uri": ev.get("uri"),
                "name": ev.get("name"),
                "status": ev.get("status"),
                "start_time": ev.get("start_time"),
                "end_time": ev.get("end_time"),
                "event_type": ev.get("event_type"),
                "location": ev.get("location", {}).get("location") if ev.get("location") else None,
                "created_at": ev.get("created_at"),
            })

        return AdapterResult(
            success=True,
            data=events,
            metadata={"count": len(events)},
        )

    # ── scheduling.events.get ────────────────────────────────────────────

    async def _get_event(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get details of a specific scheduled event.

        Required kwargs:
            event_uuid (str): The event UUID (last segment of the event URI).
        """
        event_uuid = kwargs.get("event_uuid")
        if not event_uuid:
            return AdapterResult(success=False, error="Parameter 'event_uuid' is required", error_code="MISSING_PARAM")

        data, err = await self._calendly_request(
            tenant_id, "GET", f"/scheduled_events/{event_uuid}"
        )
        if err:
            return err

        resource = data.get("resource", {})
        return AdapterResult(
            success=True,
            data={
                "uri": resource.get("uri"),
                "name": resource.get("name"),
                "status": resource.get("status"),
                "start_time": resource.get("start_time"),
                "end_time": resource.get("end_time"),
                "event_type": resource.get("event_type"),
                "location": resource.get("location"),
                "invitees_counter": resource.get("invitees_counter"),
                "created_at": resource.get("created_at"),
                "updated_at": resource.get("updated_at"),
                "cancellation": resource.get("cancellation"),
            },
        )

    # ── scheduling.events.cancel ─────────────────────────────────────────

    async def _cancel_event(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Cancel a scheduled event.

        Required kwargs:
            event_uuid (str): The event UUID.
        Optional kwargs:
            reason (str): Cancellation reason.
        """
        event_uuid = kwargs.get("event_uuid")
        if not event_uuid:
            return AdapterResult(success=False, error="Parameter 'event_uuid' is required", error_code="MISSING_PARAM")

        cancel_body: dict[str, Any] = {}
        if kwargs.get("reason"):
            cancel_body["reason"] = kwargs["reason"]

        _, err = await self._calendly_request(
            tenant_id, "POST",
            f"/scheduled_events/{event_uuid}/cancellation",
            json_data=cancel_body if cancel_body else None,
        )
        if err:
            return err

        return AdapterResult(
            success=True,
            data={
                "event_uuid": event_uuid,
                "status": "cancelled",
                "action": "event_cancelled",
                "reason": kwargs.get("reason", ""),
            },
        )

    # ── scheduling.availability.get ──────────────────────────────────────

    async def _get_availability(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get user availability schedules.

        Optional kwargs:
            user_uri (str): Specific user URI (defaults to authenticated user).
        """
        user_uri = kwargs.get("user_uri")
        if not user_uri:
            user_uri, _, err = await self._resolve_user_uri(tenant_id)
            if err:
                return err

        params = {"user": user_uri}
        data, req_err = await self._calendly_request(
            tenant_id, "GET", "/user_availability_schedules", params=params
        )
        if req_err:
            return req_err

        schedules = []
        for sched in data.get("collection", []):
            rules = []
            for rule in sched.get("rules", []):
                rules.append({
                    "type": rule.get("type"),
                    "wday": rule.get("wday"),
                    "date": rule.get("date"),
                    "intervals": rule.get("intervals", []),
                })
            schedules.append({
                "uri": sched.get("uri"),
                "name": sched.get("name"),
                "default": sched.get("default"),
                "timezone": sched.get("timezone"),
                "rules": rules,
            })

        return AdapterResult(
            success=True,
            data=schedules,
            metadata={"count": len(schedules)},
        )

    # ── scheduling.invitee.list ──────────────────────────────────────────

    async def _list_invitees(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List invitees for a scheduled event.

        Required kwargs:
            event_uuid (str): The event UUID.
        Optional kwargs:
            count (int): Number of results (default: 20).
            status (str): "active" or "canceled".
        """
        event_uuid = kwargs.get("event_uuid")
        if not event_uuid:
            return AdapterResult(success=False, error="Parameter 'event_uuid' is required", error_code="MISSING_PARAM")

        params: dict[str, Any] = {"count": kwargs.get("count", 20)}
        if kwargs.get("status"):
            params["status"] = kwargs["status"]

        data, err = await self._calendly_request(
            tenant_id, "GET",
            f"/scheduled_events/{event_uuid}/invitees",
            params=params,
        )
        if err:
            return err

        invitees = []
        for inv in data.get("collection", []):
            invitees.append({
                "uri": inv.get("uri"),
                "name": inv.get("name"),
                "email": inv.get("email"),
                "status": inv.get("status"),
                "timezone": inv.get("timezone"),
                "created_at": inv.get("created_at"),
                "questions_and_answers": inv.get("questions_and_answers", []),
            })

        return AdapterResult(
            success=True,
            data=invitees,
            metadata={"count": len(invitees), "event_uuid": event_uuid},
        )

    # ── scheduling.webhook.subscribe ─────────────────────────────────────

    async def _subscribe_webhook(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Subscribe to Calendly webhook events.

        Required kwargs:
            url (str): The webhook callback URL.
            events (list[str]): List of events to subscribe to.
        Optional kwargs:
            scope (str): "user" or "organization" (default: "user").
        """
        url = kwargs.get("url")
        events = kwargs.get("events")

        if not url or not events:
            return AdapterResult(
                success=False,
                error="Parameters 'url' and 'events' are required",
                error_code="MISSING_PARAM",
            )

        user_uri, org_uri, err = await self._resolve_user_uri(tenant_id)
        if err:
            return err

        scope = kwargs.get("scope", "user")
        webhook_body: dict[str, Any] = {
            "url": url,
            "events": events,
            "scope": scope,
        }

        if scope == "organization" and org_uri:
            webhook_body["organization"] = org_uri
        elif user_uri:
            webhook_body["user"] = user_uri
            webhook_body["organization"] = org_uri

        data, req_err = await self._calendly_request(
            tenant_id, "POST", "/webhook_subscriptions", json_data=webhook_body
        )
        if req_err:
            return req_err

        resource = data.get("resource", {})
        return AdapterResult(
            success=True,
            data={
                "webhook_uri": resource.get("uri"),
                "callback_url": resource.get("callback_url"),
                "state": resource.get("state"),
                "events": resource.get("events", []),
                "scope": resource.get("scope"),
                "created_at": resource.get("created_at"),
            },
        )

    # ── scheduling.webhook.list ──────────────────────────────────────────

    async def _list_webhooks(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List active webhook subscriptions.

        Optional kwargs:
            scope (str): "user" or "organization" (default: "user").
            count (int): Number of results (default: 20).
        """
        user_uri, org_uri, err = await self._resolve_user_uri(tenant_id)
        if err:
            return err

        scope = kwargs.get("scope", "user")
        params: dict[str, Any] = {
            "scope": scope,
            "organization": org_uri,
            "count": kwargs.get("count", 20),
        }
        if scope == "user":
            params["user"] = user_uri

        data, req_err = await self._calendly_request(
            tenant_id, "GET", "/webhook_subscriptions", params=params
        )
        if req_err:
            return req_err

        webhooks = []
        for wh in data.get("collection", []):
            webhooks.append({
                "uri": wh.get("uri"),
                "callback_url": wh.get("callback_url"),
                "state": wh.get("state"),
                "events": wh.get("events", []),
                "scope": wh.get("scope"),
                "created_at": wh.get("created_at"),
            })

        return AdapterResult(
            success=True,
            data=webhooks,
            metadata={"count": len(webhooks)},
        )

    # ── Health Check ─────────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if Calendly is configured and accessible."""
        data, err = await self._get_current_user(tenant_id)
        if err:
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": err.error},
            )

        resource = data.get("resource", {})
        return AdapterResult(
            success=True,
            data={
                "status": "CONNECTED",
                "user_name": resource.get("name"),
                "email": resource.get("email"),
                "scheduling_url": resource.get("scheduling_url"),
            },
        )
