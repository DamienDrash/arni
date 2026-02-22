"""ARIIA v1.4 – WhatsApp Native Flows (Stub).

@BACKEND: Sprint 3, Task 3.9
JSON schemas for WhatsApp Interactive Messages (Buttons, Lists).
Full integration planned for Sprint 4.
"""

from typing import Any


def booking_confirmation_buttons(
    course_name: str,
    time_slot: str,
    date: str,
    studio_name: str = "ARIIA",
) -> dict[str, Any]:
    """Generate WhatsApp interactive button for booking confirmation.

    Returns interactive message payload for send_interactive().
    """
    return {
        "type": "button",
        "header": {
            "type": "text",
            "text": "📋 Buchungsbestätigung",
        },
        "body": {
            "text": f"Kurs: {course_name}\n📅 {date}\n🕐 {time_slot}\n\nMöchtest du buchen?",
        },
        "footer": {
            "text": studio_name,
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {"id": "book_confirm", "title": "✅ Ja, buchen!"},
                },
                {
                    "type": "reply",
                    "reply": {"id": "book_cancel", "title": "❌ Nein, danke"},
                },
            ],
        },
    }


def time_slot_list(
    available_slots: list[dict[str, str]],
    course_name: str,
    studio_name: str = "ARIIA",
) -> dict[str, Any]:
    """Generate WhatsApp interactive list for time slot selection.

    Args:
        available_slots: List of dicts with 'id', 'time', 'spots' keys.
        course_name: Name of the course.

    Returns:
        Interactive list message payload.
    """
    rows = []
    for slot in available_slots[:10]:  # WhatsApp max 10 rows
        rows.append({
            "id": slot.get("id", ""),
            "title": slot.get("time", ""),
            "description": f"{slot.get('spots', '?')} Plätze frei",
        })

    return {
        "type": "list",
        "header": {
            "type": "text",
            "text": f"🏋️ {course_name}",
        },
        "body": {
            "text": "Wähle deinen Wunschtermin:",
        },
        "footer": {
            "text": studio_name,
        },
        "action": {
            "button": "🗓️ Termine anzeigen",
            "sections": [
                {
                    "title": "Verfügbare Termine",
                    "rows": rows,
                },
            ],
        },
    }


def cancellation_confirmation() -> dict[str, Any]:
    """Generate One-Way-Door confirmation for cancellation.

    Per AGENTS.md §1 – Type 2 action requires explicit confirmation.
    """
    return {
        "type": "button",
        "body": {
            "text": (
                "⚠️ **Bist du sicher?**\n\n"
                "Eine Kündigung ist eine unwiderrufliche Aktion. "
                "Wir haben auch Alternativen:\n"
                "• ⏸️ Pause-Modus\n"
                "• ⬇️ Downgrade\n"
                "• 🎁 Bonus-Monat\n\n"
                "Was möchtest du?"
            ),
        },
        "footer": {
            "text": "Bezos One-Way-Door Principle",
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {"id": "cancel_confirm", "title": "🚪 Ja, kündigen"},
                },
                {
                    "type": "reply",
                    "reply": {"id": "cancel_alternatives", "title": "🔄 Alternativen"},
                },
                {
                    "type": "reply",
                    "reply": {"id": "cancel_abort", "title": "✅ Doch bleiben"},
                },
            ],
        },
    }
