"""Unit tests for Magicline Tools Logic."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from app.swarm.tools import magicline

@patch("app.swarm.tools.magicline.get_client")
@patch("app.swarm.tools.magicline.persistence.get_session_by_user_id")
def test_get_member_status_search(mock_get_session, mock_get_client):
    # Setup mock client
    client = MagicMock()
    mock_get_client.return_value = client
    mock_get_session.return_value = SimpleNamespace(member_id="999", email=None)

    client.customer_get_by.return_value = {"id": 999, "firstName": "David", "lastName": "Frigewski"}
    # Mock contracts
    client.customer_contracts.return_value = [{"rateName": "Premium", "endDate": "2026-12-31"}]

    # Exec
    result = magicline.get_member_status("user-1")

    # Verify
    assert "Mitglied David Frigewski: Aktiv (Premium)" in result
    client.customer_get_by.assert_called_once_with(customer_number="999")
    client.customer_contracts.assert_called_once_with(999, status="ACTIVE")

@patch("app.swarm.tools.magicline.get_client")
@patch("app.swarm.tools.magicline.persistence.get_session_by_user_id")
def test_get_checkin_history_search(mock_get_session, mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    mock_get_session.return_value = SimpleNamespace(member_id="888", email=None)

    client.customer_get_by.return_value = {"id": 888, "firstName": "David"}
    client.customer_checkins.return_value = [
        {"checkInDateTime": "2026-02-14T10:00:00"}
    ]

    result = magicline.get_checkin_history(7, user_identifier="user-1")

    assert "Check-ins von David" in result
    assert "2026-02-14" in result
    client.customer_get_by.assert_called_once_with(customer_number="888")
    client.customer_checkins.assert_called_once()

@patch("app.swarm.tools.magicline.get_client")
def test_get_class_schedule(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    
    client.class_list_all_slots.return_value = [
        {
            "startDateTime": "2026-02-15T10:00:00",
            "classDetails": {"name": "Yoga"},
            "instructor": {"firstName": "Guru"},
            "availableSlots": 5
        }
    ]
    
    result = magicline.get_class_schedule("2026-02-15")
    
    assert "Yoga" in result
    assert "Guru" in result
    client.class_list_all_slots.assert_called_once()
