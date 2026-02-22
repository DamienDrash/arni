"""Unit tests for MagiclineClient integration."""
import pytest
from unittest.mock import MagicMock, patch
from app.integrations.magicline.client import MagiclineClient
from requests import HTTPError

@pytest.fixture
def client():
    return MagiclineClient(
        base_url="https://api.example.com",
        api_key="test-api-key"
    )

def test_init_sets_headers(client):
    assert client.session.headers["x-api-key"] == "test-api-key"
    assert client.session.headers["Accept"] == "application/json"
    assert client.base_url == "https://api.example.com"

@patch("app.integrations.magicline.client.requests.Session.get")
def test_customer_get(mock_get, client):
    # Setup mock
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 123, "firstName": "Test"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # Call
    result = client.customer_get(123)

    # Verify
    mock_get.assert_called_once_with(
        "https://api.example.com/v1/customers/123",
        params=None,
        timeout=20
    )
    assert result["id"] == 123

@patch("app.integrations.magicline.client.requests.Session.get")
def test_class_list_params(mock_get, client):
    mock_get.return_value.json.return_value = {"result": []}
    
    client.class_list(slice_size=50, offset="abcdef")
    
    mock_get.assert_called_once_with(
        "https://api.example.com/v1/classes",
        params={"sliceSize": 50, "offset": "abcdef"},
        timeout=20
    )

@patch("app.integrations.magicline.client.requests.Session.get")
def test_appointment_slots(mock_get, client):
    mock_get.return_value.json.return_value = []
    
    client.appointment_get_slots(
        bookable_id=999,
        customer_id=123,
        days_ahead=5,  # Should be clamped to 3
        slot_window_start_date="2026-01-01"
    )
    
    expected_params = {
        "customerId": 123,
        "daysAhead": 3,  # Clamped
        "slotWindowStartDate": "2026-01-01"
    }
    mock_get.assert_called_once_with(
        "https://api.example.com/v1/appointments/bookable/999/slots",
        params=expected_params,
        timeout=20
    )

@patch("app.integrations.magicline.client.requests.Session.post")
def test_appointment_book(mock_post, client):
    mock_post.return_value.json.return_value = {"bookingId": 777}
    
    client.appointment_book(
        bookable_id=10,
        customer_id=20,
        start_dt="2026-02-15T10:00:00",
        end_dt="2026-02-15T11:00:00"
    )
    
    expected_body = {
        "bookableAppointmentId": 10,
        "customerId": 20,
        "startDateTime": "2026-02-15T10:00:00",
        "endDateTime": "2026-02-15T11:00:00"
    }
    mock_post.assert_called_once_with(
        "https://api.example.com/v1/appointments/booking/book",
        json=expected_body,
        timeout=20
    )

@patch("app.integrations.magicline.client.requests.Session.get")
def test_error_handling(mock_get, client):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = HTTPError("404 Client Error")
    mock_response.text = "Not Found"
    mock_get.return_value = mock_response
    
    with pytest.raises(HTTPError) as excinfo:
        client.customer_get(999)
    
    assert "Body: Not Found" in str(excinfo.value)
