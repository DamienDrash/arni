"""Shared Magicline contact field helpers.

Centralizes the custom-field definitions that ARIIA persists for Magicline
contacts so sync, enrichment, UI and segment logic all operate on the same
slugs.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.contacts.repository import contact_repo

MAGICLINE_CUSTOM_FIELDS: tuple[dict[str, Any], ...] = (
    {
        "field_name": "Magicline Status",
        "field_slug": "magicline_status",
        "field_type": "select",
        "options": ["MEMBER", "PROSPECT", "FORMER_MEMBER"],
        "display_order": 799,
        "description": "Rohstatus des Kontakts in Magicline",
    },
    {
        "field_name": "Vertrag",
        "field_slug": "vertrag",
        "field_type": "text",
        "display_order": 800,
        "description": "Magicline Tarif-/Vertragsname",
    },
    {
        "field_name": "Vertragsstatus",
        "field_slug": "vertrag_status",
        "field_type": "select",
        "options": ["ACTIVE", "INACTIVE", "CANCELED", "PAUSED"],
        "display_order": 801,
        "description": "Aktueller Magicline Vertragsstatus",
    },
    {
        "field_name": "Vertragsstart",
        "field_slug": "vertrag_start",
        "field_type": "date",
        "display_order": 802,
        "description": "Startdatum des aktiven Vertrags",
    },
    {
        "field_name": "Vertragsende",
        "field_slug": "vertrag_ende",
        "field_type": "date",
        "display_order": 803,
        "description": "Enddatum des aktiven Vertrags",
    },
    {
        "field_name": "Vertrag gekündigt",
        "field_slug": "vertrag_gekuendigt",
        "field_type": "boolean",
        "display_order": 804,
        "description": "Ob der aktive Vertrag bereits gekündigt wurde",
    },
    {
        "field_name": "Pausiert",
        "field_slug": "pausiert",
        "field_type": "boolean",
        "display_order": 805,
        "description": "Ob die Mitgliedschaft aktuell pausiert ist",
    },
    {
        "field_name": "Pause bis",
        "field_slug": "pause_bis",
        "field_type": "date",
        "display_order": 806,
        "description": "Ende der aktuellen Pausierung",
    },
    {
        "field_name": "Pausegrund",
        "field_slug": "pause_grund",
        "field_type": "text",
        "display_order": 807,
        "description": "Von Magicline gemeldeter Pausegrund",
    },
    {
        "field_name": "Letzter Besuch",
        "field_slug": "letzter_besuch",
        "field_type": "date",
        "display_order": 808,
        "description": "Letzter bekannter Besuch oder Termin",
    },
    {
        "field_name": "Besuche 30 Tage",
        "field_slug": "besuche_30d",
        "field_type": "number",
        "display_order": 809,
        "description": "Anzahl Besuche in den letzten 30 Tagen",
    },
    {
        "field_name": "Besuche 90 Tage",
        "field_slug": "besuche_90d",
        "field_type": "number",
        "display_order": 810,
        "description": "Anzahl Besuche in den letzten 90 Tagen",
    },
    {
        "field_name": "Bevorzugte Trainingstage",
        "field_slug": "bevorzugte_trainingstage",
        "field_type": "text",
        "display_order": 811,
        "description": "Aus Check-ins/Bookings abgeleitete Trainingstage",
    },
    {
        "field_name": "Bevorzugte Tageszeit",
        "field_slug": "bevorzugte_tageszeit",
        "field_type": "select",
        "options": ["morning", "afternoon", "evening"],
        "display_order": 812,
        "description": "Typische Trainings-Tageszeit",
    },
    {
        "field_name": "Bevorzugte Sessions",
        "field_slug": "bevorzugte_sessions",
        "field_type": "text",
        "display_order": 813,
        "description": "Häufigste Kurs-/Sessiontypen",
    },
    {
        "field_name": "Nächster Termin",
        "field_slug": "naechster_termin",
        "field_type": "date",
        "display_order": 814,
        "description": "Nächster geplanter Termin",
    },
    {
        "field_name": "Churn Risiko",
        "field_slug": "churn_risk",
        "field_type": "select",
        "options": ["low", "medium", "high"],
        "display_order": 815,
        "description": "Abgeleitetes Abwanderungsrisiko",
    },
    {
        "field_name": "Churn Score",
        "field_slug": "churn_score",
        "field_type": "number",
        "display_order": 816,
        "description": "Abgeleiteter Churn-Score von 0 bis 100",
    },
)


def ensure_magicline_custom_field_definitions(db: Session, tenant_id: int) -> dict[str, Any]:
    """Ensure the tenant has the required Magicline custom-field definitions."""
    existing = {
        definition.field_slug: definition
        for definition in contact_repo.list_custom_field_definitions(db, tenant_id)
    }
    by_slug = dict(existing)
    for field in MAGICLINE_CUSTOM_FIELDS:
        slug = field["field_slug"]
        if slug in by_slug:
            continue
        payload = dict(field)
        options = payload.pop("options", None)
        if options:
            payload["options_json"] = json.dumps(options, ensure_ascii=False)
        definition = contact_repo.create_custom_field_definition(db, tenant_id, **payload)
        by_slug[slug] = definition
    return by_slug


def _guess_generic_field_definition(slug: str, value: Any) -> dict[str, Any]:
    field_type = "text"
    options = None
    if isinstance(value, bool):
        field_type = "boolean"
    elif isinstance(value, (int, float)):
        field_type = "number"
    elif isinstance(value, str) and len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
        field_type = "date"

    return {
        "field_name": slug.replace("_", " ").strip().title() or slug,
        "field_slug": slug,
        "field_type": field_type,
        "display_order": 900,
        "description": "Automatisch aus Magicline synchronisiert",
        "options": options,
    }


def normalize_magicline_custom_field_values(values: dict[str, Any]) -> dict[str, str]:
    """Normalize Magicline custom-field values to storage-safe strings."""
    normalized: dict[str, str] = {}
    for slug, raw in values.items():
        if raw is None:
            continue
        if isinstance(raw, bool):
            normalized[slug] = "true" if raw else "false"
        elif isinstance(raw, (int, float)):
            normalized[slug] = str(raw)
        elif isinstance(raw, list):
            items = [str(item).strip() for item in raw if str(item).strip()]
            if items:
                normalized[slug] = ", ".join(items)
        elif isinstance(raw, dict):
            if raw.get("start"):
                normalized[slug] = str(raw["start"])
            elif raw.get("title"):
                normalized[slug] = str(raw["title"])
            else:
                text = json.dumps(raw, ensure_ascii=False)
                if text not in ("{}", "[]"):
                    normalized[slug] = text
        else:
            text = str(raw).strip()
            if text:
                normalized[slug] = text
    return normalized


def set_magicline_custom_field_values(
    db: Session,
    tenant_id: int,
    contact_id: int,
    values: dict[str, Any],
) -> None:
    """Upsert a set of Magicline custom-field values for a contact."""
    definitions = ensure_magicline_custom_field_definitions(db, tenant_id)
    normalized = normalize_magicline_custom_field_values(values)
    for slug, value in normalized.items():
        definition = definitions.get(slug)
        if definition is None:
            payload = _guess_generic_field_definition(slug, values.get(slug))
            options = payload.pop("options", None)
            if options:
                payload["options_json"] = json.dumps(options, ensure_ascii=False)
            definition = contact_repo.create_custom_field_definition(db, tenant_id, **payload)
            definitions[slug] = definition
        contact_repo.set_custom_field_value(db, contact_id, definition.id, value)
