"""ARIIA v2.0 – Calendly Tool Module (CAL-1 / CAL-2).

Provides high-level tool functions for the MasterAgentV2 to interact
with Calendly via the CalendlyAdapter.

Functions:
  - get_booking_link: Returns a booking URL for a given event type.
  - list_event_types: Lists all available event types for a tenant.
  - get_upcoming_events: Lists upcoming scheduled events.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


async def get_booking_link(
    event_type_name: str = "",
    tenant_id: int = 1,
) -> str:
    """Get a Calendly booking link for a specific event type.

    This is the primary tool function called by the MasterAgentV2 when
    a user wants to book an appointment.

    Strategy:
    1. Fetch all event types from Calendly via the adapter.
    2. If ``event_type_name`` is provided, find the best match.
    3. Return the scheduling URL for the matched event type.
    4. If no match is found, return the user's default scheduling page.

    Args:
        event_type_name: The name/type of appointment to book
            (e.g. "Erstgespräch", "Beratung", "Personal Training").
            If empty, returns the default scheduling page.
        tenant_id: The tenant ID for credential lookup.

    Returns:
        A human-readable message containing the booking link.
    """
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter

    adapter = CalendlyAdapter()

    # Step 1: Get all event types
    result = await adapter.execute_capability("scheduling.event_types.list", tenant_id)

    if not result.success:
        logger.warning(
            "calendly_tool.event_types_failed",
            tenant_id=tenant_id,
            error=result.error,
        )
        # Fallback: Try to return the user's scheduling page
        return await _get_fallback_scheduling_url(adapter, tenant_id)

    event_types = result.data
    if not event_types:
        return await _get_fallback_scheduling_url(adapter, tenant_id)

    # Step 2: Find the best matching event type
    if event_type_name:
        matched = _find_best_match(event_type_name, event_types)
        if matched:
            url = matched.get("scheduling_url", "")
            name = matched.get("name", "Termin")
            duration = matched.get("duration", "")
            duration_text = f" ({duration} Min.)" if duration else ""

            return (
                f"Hier ist dein Buchungslink für *{name}*{duration_text}:\n"
                f"{url}\n\n"
                "Klicke auf den Link, um einen passenden Termin auszuwählen."
            )

    # Step 3: No specific match → show all available event types
    if len(event_types) == 1:
        et = event_types[0]
        url = et.get("scheduling_url", "")
        name = et.get("name", "Termin")
        return (
            f"Hier ist dein Buchungslink für *{name}*:\n"
            f"{url}\n\n"
            "Klicke auf den Link, um einen passenden Termin auszuwählen."
        )

    # Multiple event types → list them
    lines = ["Folgende Terminarten sind verfügbar:\n"]
    for i, et in enumerate(event_types, 1):
        name = et.get("name", "Unbekannt")
        duration = et.get("duration", "")
        url = et.get("scheduling_url", "")
        duration_text = f" ({duration} Min.)" if duration else ""
        lines.append(f"{i}. *{name}*{duration_text}\n   {url}")

    lines.append("\nKlicke auf den Link deiner Wahl, um einen Termin zu buchen.")
    return "\n".join(lines)


async def list_event_types(tenant_id: int = 1) -> str:
    """List all available Calendly event types for a tenant.

    Args:
        tenant_id: The tenant ID for credential lookup.

    Returns:
        A formatted list of event types with their details.
    """
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter

    adapter = CalendlyAdapter()
    result = await adapter.execute_capability("scheduling.event_types.list", tenant_id)

    if not result.success:
        return f"Fehler beim Abrufen der Terminarten: {result.error}"

    event_types = result.data
    if not event_types:
        return "Es sind aktuell keine Terminarten in Calendly konfiguriert."

    lines = ["Verfügbare Terminarten:\n"]
    for i, et in enumerate(event_types, 1):
        name = et.get("name", "Unbekannt")
        duration = et.get("duration", "")
        description = et.get("description_plain", "")
        active = "✓" if et.get("active") else "✗"
        lines.append(f"{i}. {active} {name} ({duration} Min.)")
        if description:
            lines.append(f"   {description[:100]}")

    return "\n".join(lines)


async def get_upcoming_events(
    tenant_id: int = 1,
    count: int = 5,
) -> str:
    """List upcoming scheduled events from Calendly.

    Args:
        tenant_id: The tenant ID for credential lookup.
        count: Maximum number of events to return.

    Returns:
        A formatted list of upcoming events.
    """
    from app.integrations.adapters.calendly_adapter import CalendlyAdapter

    adapter = CalendlyAdapter()
    result = await adapter.execute_capability(
        "scheduling.events.list",
        tenant_id,
        status="active",
        count=count,
        sort="start_time:asc",
    )

    if not result.success:
        return f"Fehler beim Abrufen der Termine: {result.error}"

    events = result.data
    if not events:
        return "Es gibt aktuell keine anstehenden Termine."

    lines = ["Anstehende Termine:\n"]
    for i, ev in enumerate(events, 1):
        name = ev.get("name", "Termin")
        start = ev.get("start_time", "")
        status = ev.get("status", "")
        # Format the datetime for display
        if start:
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start_formatted = dt.strftime("%d.%m.%Y um %H:%M Uhr")
            except (ValueError, TypeError):
                start_formatted = start
        else:
            start_formatted = "Unbekannt"

        lines.append(f"{i}. {name} – {start_formatted} ({status})")

    return "\n".join(lines)


# ─── Private Helpers ─────────────────────────────────────────────────────────


def _find_best_match(
    query: str,
    event_types: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find the best matching event type by name.

    Uses case-insensitive substring matching with a scoring system.

    Args:
        query: The user's requested event type name.
        event_types: List of event type dicts from the adapter.

    Returns:
        The best matching event type dict, or None if no match found.
    """
    query_lower = query.lower().strip()
    if not query_lower:
        return None

    best_match = None
    best_score = 0

    for et in event_types:
        name = (et.get("name") or "").lower()
        description = (et.get("description_plain") or "").lower()

        score = 0

        # Exact match
        if query_lower == name:
            return et

        # Name contains query
        if query_lower in name:
            score = 80

        # Query contains name
        elif name in query_lower:
            score = 60

        # Word-level matching
        else:
            query_words = set(query_lower.split())
            name_words = set(name.split())
            overlap = query_words & name_words
            if overlap:
                score = len(overlap) * 20

            # Check description as fallback
            if score == 0 and description:
                desc_words = set(description.split())
                desc_overlap = query_words & desc_words
                if desc_overlap:
                    score = len(desc_overlap) * 10

        if score > best_score:
            best_score = score
            best_match = et

    # Only return if we have a reasonable match
    return best_match if best_score >= 20 else None


async def _get_fallback_scheduling_url(adapter: Any, tenant_id: int) -> str:
    """Get the user's default Calendly scheduling page as fallback.

    Args:
        adapter: The CalendlyAdapter instance.
        tenant_id: The tenant ID.

    Returns:
        A message with the scheduling URL or an error message.
    """
    try:
        health = await adapter.health_check(tenant_id)
        if health.success and health.data:
            scheduling_url = health.data.get("scheduling_url", "")
            if scheduling_url:
                return (
                    f"Hier ist die allgemeine Buchungsseite:\n"
                    f"{scheduling_url}\n\n"
                    "Dort findest du alle verfügbaren Terminarten."
                )
    except Exception as e:
        logger.warning("calendly_tool.fallback_failed", error=str(e))

    return (
        "Leider konnte ich gerade keinen Buchungslink abrufen. "
        "Bitte kontaktiere uns direkt, um einen Termin zu vereinbaren."
    )
