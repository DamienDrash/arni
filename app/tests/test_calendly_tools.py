"""CAL-1/CAL-2: Tests for Calendly tool module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.swarm.tools.calendly_tools import (
    get_booking_link,
    list_event_types,
    _find_best_match,
)


# ─── Mock Data ────────────────────────────────────────────────────────────────

MOCK_EVENT_TYPES = [
    {
        "name": "Erstgespräch",
        "duration": 30,
        "scheduling_url": "https://calendly.com/studio/erstgespraech",
        "active": True,
        "description_plain": "Kostenloses Erstgespräch für neue Interessenten",
    },
    {
        "name": "Personal Training",
        "duration": 60,
        "scheduling_url": "https://calendly.com/studio/personal-training",
        "active": True,
        "description_plain": "Individuelles Training mit einem Trainer",
    },
    {
        "name": "Beratungstermin",
        "duration": 45,
        "scheduling_url": "https://calendly.com/studio/beratung",
        "active": True,
        "description_plain": "Allgemeine Beratung zu Mitgliedschaft und Angeboten",
    },
]


# ─── Tests: _find_best_match ─────────────────────────────────────────────────


class TestFindBestMatch:
    """Test the event type matching logic."""

    def test_exact_match(self):
        result = _find_best_match("Erstgespräch", MOCK_EVENT_TYPES)
        assert result is not None
        assert result["name"] == "Erstgespräch"

    def test_partial_match(self):
        result = _find_best_match("Training", MOCK_EVENT_TYPES)
        assert result is not None
        assert result["name"] == "Personal Training"

    def test_case_insensitive(self):
        result = _find_best_match("erstgespräch", MOCK_EVENT_TYPES)
        assert result is not None
        assert result["name"] == "Erstgespräch"

    def test_word_match(self):
        result = _find_best_match("Beratung", MOCK_EVENT_TYPES)
        assert result is not None
        assert result["name"] == "Beratungstermin"

    def test_no_match(self):
        result = _find_best_match("Schwimmen", MOCK_EVENT_TYPES)
        assert result is None

    def test_empty_query(self):
        result = _find_best_match("", MOCK_EVENT_TYPES)
        assert result is None

    def test_empty_event_types(self):
        result = _find_best_match("Erstgespräch", [])
        assert result is None


# ─── Tests: get_booking_link ─────────────────────────────────────────────────


class TestGetBookingLink:
    """Test the get_booking_link tool function."""

    @pytest.mark.asyncio
    async def test_specific_event_type(self):
        """Should return a booking link for a specific event type."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = MOCK_EVENT_TYPES

        with patch(
            "app.integrations.adapters.calendly_adapter.CalendlyAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.execute = AsyncMock(return_value=mock_result)

            result = await get_booking_link("Erstgespräch", tenant_id=1)

            assert "Erstgespräch" in result
            assert "calendly.com" in result
            assert "erstgespraech" in result

    @pytest.mark.asyncio
    async def test_single_event_type(self):
        """Should return the only event type's link when there's just one."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = [MOCK_EVENT_TYPES[0]]

        with patch(
            "app.integrations.adapters.calendly_adapter.CalendlyAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.execute = AsyncMock(return_value=mock_result)

            result = await get_booking_link("", tenant_id=1)

            assert "Erstgespräch" in result
            assert "calendly.com" in result

    @pytest.mark.asyncio
    async def test_multiple_event_types_no_match(self):
        """Should list all event types when no specific match is found."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = MOCK_EVENT_TYPES

        with patch(
            "app.integrations.adapters.calendly_adapter.CalendlyAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.execute = AsyncMock(return_value=mock_result)

            result = await get_booking_link("", tenant_id=1)

            assert "Terminarten" in result
            assert "Erstgespräch" in result
            assert "Personal Training" in result
            assert "Beratungstermin" in result

    @pytest.mark.asyncio
    async def test_api_error_fallback(self):
        """Should return fallback message when API fails."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "API Error"

        mock_health = MagicMock()
        mock_health.success = True
        mock_health.data = {
            "scheduling_url": "https://calendly.com/studio",
            "status": "CONNECTED",
        }

        with patch(
            "app.integrations.adapters.calendly_adapter.CalendlyAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.execute = AsyncMock(return_value=mock_result)
            instance.health_check = AsyncMock(return_value=mock_health)

            result = await get_booking_link("Termin", tenant_id=1)

            assert "calendly.com/studio" in result

    @pytest.mark.asyncio
    async def test_complete_failure(self):
        """Should return error message when everything fails."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "API Error"

        mock_health = MagicMock()
        mock_health.success = False
        mock_health.data = None

        with patch(
            "app.integrations.adapters.calendly_adapter.CalendlyAdapter"
        ) as MockAdapter:
            instance = MockAdapter.return_value
            instance.execute = AsyncMock(return_value=mock_result)
            instance.health_check = AsyncMock(return_value=mock_health)

            result = await get_booking_link("Termin", tenant_id=1)

            assert "kontaktiere" in result.lower() or "leider" in result.lower()
