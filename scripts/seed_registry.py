"""ARIIA v2.0 – Integration Registry Seed Script.

@ARCH: Phase 2, Meilenstein 2.4 – Integration & Skills
Seeds the Integration Registry with:
  1. IntegrationDefinitions (Magicline as first reference integration)
  2. CapabilityDefinitions (all abstract capabilities)
  3. IntegrationCapability links
  4. Optionally: TenantIntegration for existing tenants

Usage:
    python -m scripts.seed_registry
    # or from within the container:
    python scripts/seed_registry.py
"""

from __future__ import annotations

import os
import sys

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog

logger = structlog.get_logger()


# ─── Integration Definitions ─────────────────────────────────────────────────

INTEGRATION_DEFINITIONS = [
    {
        "id": "magicline",
        "name": "Magicline",
        "description": "Fitness-Studio CRM und Buchungssystem. Ermöglicht Mitgliederverwaltung, Kurs- und Terminbuchungen, Check-in-Tracking und Vertragsmanagement.",
        "category": "fitness",
        "auth_type": "api_key",
        "config_schema": {
            "type": "object",
            "properties": {
                "api_url": {"type": "string", "description": "Magicline API Base URL"},
                "api_key": {"type": "string", "description": "Magicline API Key"},
                "studio_id": {"type": "string", "description": "Magicline Studio ID"},
            },
            "required": ["api_url", "api_key"],
        },
        "adapter_class": "app.integrations.adapters.magicline_adapter.MagiclineAdapter",
        "skill_file": "crm/magicline.SKILL.md",
        "is_public": True,
        "min_plan": "professional",
        "version": "1.0.0",
    },
    {
        "id": "manual_crm",
        "name": "Manuelle Kundenverwaltung",
        "description": "Basis-CRM-Funktionalität direkt in ARIIA. Ermöglicht die manuelle Pflege von Kundendaten ohne externe Integration.",
        "category": "crm",
        "auth_type": "none",
        "config_schema": None,
        "adapter_class": None,  # Will be implemented in Phase 3+
        "skill_file": None,
        "is_public": True,
        "min_plan": "starter",
        "version": "1.0.0",
    },
    {
        "id": "whatsapp",
        "name": "WhatsApp Business",
        "description": "WhatsApp Business API Integration für Kundenkommunikation über WhatsApp.",
        "category": "messaging",
        "auth_type": "api_key",
        "config_schema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["qr", "api"], "description": "Connection mode"},
                "phone_number_id": {"type": "string", "description": "Phone Number ID (API mode)"},
                "access_token": {"type": "string", "description": "Access Token (API mode)"},
                "verify_token": {"type": "string", "description": "Verify Token (API mode)"},
                "app_secret": {"type": "string", "description": "App Secret (API mode)"},
            },
        },
        "adapter_class": None,
        "skill_file": None,
        "is_public": True,
        "min_plan": "starter",
        "version": "1.0.0",
    },
    {
        "id": "telegram",
        "name": "Telegram",
        "description": "Telegram Bot Integration für Kundenkommunikation über Telegram.",
        "category": "messaging",
        "auth_type": "api_key",
        "config_schema": {
            "type": "object",
            "properties": {
                "bot_token": {"type": "string", "description": "Telegram Bot Token"},
                "admin_chat_id": {"type": "string", "description": "Admin Chat ID (optional)"},
            },
            "required": ["bot_token"],
        },
        "adapter_class": None,
        "skill_file": None,
        "is_public": True,
        "min_plan": "starter",
        "version": "1.0.0",
    },
]


# ─── Capability Definitions ──────────────────────────────────────────────────

CAPABILITY_DEFINITIONS = [
    # CRM Capabilities
    {
        "id": "crm.customer.search",
        "name": "Kundensuche",
        "description": "Sucht nach einem Kunden anhand von E-Mail, Name oder Telefonnummer.",
        "category": "crm",
        "is_destructive": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "E-Mail-Adresse des Kunden"},
                "name": {"type": "string", "description": "Name des Kunden"},
                "phone": {"type": "string", "description": "Telefonnummer des Kunden"},
                "query": {"type": "string", "description": "Allgemeiner Suchbegriff"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "found": {"type": "boolean"},
                "customer": {"type": "object"},
            },
        },
    },
    {
        "id": "crm.customer.status",
        "name": "Kundenstatus",
        "description": "Ruft den vollständigen Status eines Kunden ab, einschließlich Vertragsinformationen.",
        "category": "crm",
        "is_destructive": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "user_identifier": {"type": "string", "description": "E-Mail oder Name des Kunden"},
            },
            "required": ["user_identifier"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "contract": {"type": "object"},
                "member_since": {"type": "string"},
            },
        },
    },
    # Booking Capabilities
    {
        "id": "booking.class.schedule",
        "name": "Kursplan anzeigen",
        "description": "Zeigt den Kursplan für ein bestimmtes Datum an.",
        "category": "booking",
        "is_destructive": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Datum im Format YYYY-MM-DD"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "classes": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
    {
        "id": "booking.class.book",
        "name": "Kurs buchen",
        "description": "Bucht einen Kursplatz für ein Mitglied.",
        "category": "booking",
        "is_destructive": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "integer", "description": "ID des Kursslots"},
                "user_identifier": {"type": "string", "description": "Mitglied-Identifier"},
            },
            "required": ["slot_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "booking_id": {"type": "integer"},
            },
        },
    },
    {
        "id": "booking.appointment.slots",
        "name": "Terminslots anzeigen",
        "description": "Zeigt verfügbare Terminslots an.",
        "category": "booking",
        "is_destructive": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Terminkategorie (z.B. personal_training, beratung, all)"},
                "days": {"type": "integer", "description": "Anzahl Tage vorausschauen (Standard: 3)"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "slots": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
    {
        "id": "booking.appointment.book",
        "name": "Termin buchen",
        "description": "Bucht einen Termin zu einer bestimmten Zeit.",
        "category": "booking",
        "is_destructive": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Terminkategorie"},
                "date": {"type": "string", "description": "Datum (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Uhrzeit (HH:MM)"},
                "user_identifier": {"type": "string", "description": "Mitglied-Identifier"},
            },
            "required": ["category", "date", "time"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "appointment_id": {"type": "integer"},
            },
        },
    },
    {
        "id": "booking.member.bookings",
        "name": "Buchungen anzeigen",
        "description": "Zeigt die aktuellen Buchungen eines Mitglieds an.",
        "category": "booking",
        "is_destructive": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "user_identifier": {"type": "string", "description": "Mitglied-Identifier"},
                "date": {"type": "string", "description": "Datum filtern (YYYY-MM-DD)"},
                "query": {"type": "string", "description": "Suchbegriff für Kursname"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "bookings": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
    {
        "id": "booking.member.cancel",
        "name": "Buchung stornieren",
        "description": "Storniert eine bestehende Buchung.",
        "category": "booking",
        "is_destructive": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "integer", "description": "ID der Buchung"},
                "booking_type": {"type": "string", "description": "Typ: class oder appointment"},
                "user_identifier": {"type": "string", "description": "Mitglied-Identifier"},
            },
            "required": ["booking_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
            },
        },
    },
    {
        "id": "booking.member.reschedule",
        "name": "Buchung umbuchen",
        "description": "Verschiebt eine Buchung auf den nächsten verfügbaren Slot.",
        "category": "booking",
        "is_destructive": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "integer", "description": "ID der Buchung"},
                "user_identifier": {"type": "string", "description": "Mitglied-Identifier"},
            },
            "required": ["booking_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "new_slot": {"type": "object"},
            },
        },
    },
    # Analytics Capabilities
    {
        "id": "analytics.checkin.history",
        "name": "Check-in-Verlauf",
        "description": "Zeigt die Check-in-Historie eines Mitglieds.",
        "category": "analytics",
        "is_destructive": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Anzahl Tage zurückschauen (Standard: 7)"},
                "user_identifier": {"type": "string", "description": "Mitglied-Identifier"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "checkins": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
    {
        "id": "analytics.checkin.stats",
        "name": "Check-in-Statistiken",
        "description": "Zeigt Check-in-Statistiken und Trends für ein Mitglied.",
        "category": "analytics",
        "is_destructive": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Zeitraum in Tagen (Standard: 90)"},
                "user_identifier": {"type": "string", "description": "Mitglied-Identifier"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "total_checkins": {"type": "integer"},
                "avg_per_week": {"type": "number"},
                "trend": {"type": "string"},
            },
        },
    },
]


# ─── Integration ↔ Capability Links ─────────────────────────────────────────

INTEGRATION_CAPABILITY_LINKS = {
    "magicline": [
        "crm.customer.search",
        "crm.customer.status",
        "booking.class.schedule",
        "booking.class.book",
        "booking.appointment.slots",
        "booking.appointment.book",
        "booking.member.bookings",
        "booking.member.cancel",
        "booking.member.reschedule",
        "analytics.checkin.history",
        "analytics.checkin.stats",
    ],
    "manual_crm": [
        "crm.customer.search",
        "crm.customer.status",
    ],
}


# ─── Seed Function ───────────────────────────────────────────────────────────


def seed_registry(db_session=None):
    """Seed the Integration Registry with initial data.

    Args:
        db_session: Optional SQLAlchemy session. If None, creates one.
    """
    from app.core.db import SessionLocal
    from app.core.integration_models import (
        CapabilityDefinition,
        IntegrationCapability,
        IntegrationDefinition,
    )

    db = db_session or SessionLocal()
    created_integrations = 0
    created_capabilities = 0
    created_links = 0

    try:
        # Seed Integration Definitions
        for integ_data in INTEGRATION_DEFINITIONS:
            existing = db.get(IntegrationDefinition, integ_data["id"])
            if existing:
                logger.info("seed.integration_exists", id=integ_data["id"])
                continue
            integ = IntegrationDefinition(**integ_data)
            db.add(integ)
            created_integrations += 1
            logger.info("seed.integration_created", id=integ_data["id"])

        db.flush()

        # Seed Capability Definitions
        for cap_data in CAPABILITY_DEFINITIONS:
            existing = db.get(CapabilityDefinition, cap_data["id"])
            if existing:
                logger.info("seed.capability_exists", id=cap_data["id"])
                continue
            cap = CapabilityDefinition(**cap_data)
            db.add(cap)
            created_capabilities += 1
            logger.info("seed.capability_created", id=cap_data["id"])

        db.flush()

        # Seed Integration ↔ Capability Links
        for integ_id, cap_ids in INTEGRATION_CAPABILITY_LINKS.items():
            for cap_id in cap_ids:
                from sqlalchemy import select
                existing = db.execute(
                    select(IntegrationCapability)
                    .where(IntegrationCapability.integration_id == integ_id)
                    .where(IntegrationCapability.capability_id == cap_id)
                ).scalar_one_or_none()
                if existing:
                    continue
                link = IntegrationCapability(integration_id=integ_id, capability_id=cap_id)
                db.add(link)
                created_links += 1

        db.commit()
        logger.info(
            "seed.registry_complete",
            integrations=created_integrations,
            capabilities=created_capabilities,
            links=created_links,
        )
        print(f"\n✅ Registry seeded: {created_integrations} integrations, {created_capabilities} capabilities, {created_links} links")

    except Exception as e:
        db.rollback()
        logger.error("seed.registry_failed", error=str(e))
        print(f"\n❌ Seed failed: {e}")
        raise
    finally:
        if not db_session:
            db.close()


if __name__ == "__main__":
    seed_registry()
