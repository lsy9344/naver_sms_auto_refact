"""
Unit tests for NaverBookingAPIClient.

Ensures the refactored client preserves legacy API parameter behaviour
and pagination semantics from original lambda_function.py.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import requests

from src.api.naver_booking import NaverBookingAPIClient


def _mock_response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _build_payload():
    return [
        {
            "bookingId": 12345,
            "businessId": "1051707",
            "name": "홍길동",
            "phone": "01012345678",
            "bookingStatusCode": "RC03",
            "snapshotJson": {
                "startDateTime": "2025-10-19T11:30:00Z",
                "bookingOptionJson": [
                    {"name": "네이버 예약", "bookingCount": 1},
                ],
                "couponJson": [{"couponName": "블랙프라이데이"}],
            },
        }
    ]


def test_get_bookings_uses_legacy_params():
    """Count and bookings API calls must carry legacy parameters."""
    session = Mock(spec=requests.Session)
    session.get.side_effect = [
        _mock_response({"count": 1}),
        _mock_response(_build_payload()),
    ]

    client = NaverBookingAPIClient(session=session, option_keywords=["네이버"])

    with patch("src.api.naver_booking.time.sleep"):
        bookings = client.get_bookings("1051707", status="RC03")

    assert len(bookings) == 1
    booking = bookings[0]
    assert booking.booking_num == "1051707_12345"
    assert booking.option is True
    assert booking.reserve_at == datetime(2025, 10, 19, 20, 30)

    # Count API call assertions
    count_call = session.get.call_args_list[0]
    count_params = count_call.kwargs["params"]
    assert count_call.args[0].endswith("/bookings/count")
    assert count_params["size"] == str(NaverBookingAPIClient.PAGE_SIZE)
    assert count_params["page"] == "0"
    assert count_params["dateDropdownType"] == "ENTIRE"
    assert count_params["orderByStartDate"] == "ASC"
    assert "noCache" in count_params

    # Bookings API call assertions
    bookings_call = session.get.call_args_list[1]
    bookings_params = bookings_call.kwargs["params"]
    assert bookings_call.args[0].endswith("/bookings")
    assert bookings_params["size"] == str(NaverBookingAPIClient.PAGE_SIZE)
    assert bookings_params["page"] == "0"
    assert bookings_params["bookingStatusCodes"] == "RC03"
    assert bookings_params["dateFilter"] == "USEDATE"
    assert "noCache" in bookings_params


def test_get_bookings_includes_date_range():
    """Date range filters should be forwarded to both count and list APIs."""
    session = Mock(spec=requests.Session)
    session.get.side_effect = [
        _mock_response({"count": 1}),
        _mock_response(_build_payload()),
    ]

    client = NaverBookingAPIClient(session=session)
    start = "2024-01-01T00:00:00"
    end = "2024-01-31T23:59:59"

    with patch("src.api.naver_booking.time.sleep"):
        client.get_bookings("1051707", status="RC08", start_date=start, end_date=end)

    count_params = session.get.call_args_list[0].kwargs["params"]
    bookings_params = session.get.call_args_list[1].kwargs["params"]

    assert count_params["startDateTime"] == start
    assert count_params["endDateTime"] == end
    assert bookings_params["startDateTime"] == start
    assert bookings_params["endDateTime"] == end
