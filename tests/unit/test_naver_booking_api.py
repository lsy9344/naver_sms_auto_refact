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
    """
    Date range filters should be forwarded to both count and list APIs.

    After refactoring to match original lambda_function.py, dates are now
    passed through unchanged (no timezone normalization applied).
    """
    session = Mock(spec=requests.Session)
    session.get.side_effect = [
        _mock_response({"count": 1}),
        _mock_response(_build_payload()),
    ]

    client = NaverBookingAPIClient(session=session)
    # Use UTC format matching original lambda_function.py
    start = "2024-01-01T00:00:00.000Z"
    end = "2024-01-31T23:59:59.000Z"

    with patch("src.api.naver_booking.time.sleep"):
        client.get_bookings("1051707", status="RC08", start_date=start, end_date=end)

    count_params = session.get.call_args_list[0].kwargs["params"]
    bookings_params = session.get.call_args_list[1].kwargs["params"]

    # Dates are passed through unchanged
    assert count_params["startDateTime"] == start
    assert count_params["endDateTime"] == end
    assert bookings_params["startDateTime"] == start
    assert bookings_params["endDateTime"] == end


def test_build_query_params_preserves_timezone_offsets():
    """Datetime parameters already containing timezone offsets must remain unchanged."""
    session = Mock(spec=requests.Session)
    client = NaverBookingAPIClient(session=session)

    start = "2024-01-01T00:00:00+09:00"
    end = "2024-01-31T23:59:59+09:00"

    params = client._build_query_params("RC03", start, end, page=0, size=50)

    assert params["startDateTime"] == start
    assert params["endDateTime"] == end


def test_default_date_range_includes_timezone_suffix():
    """
    Default 31-day forward window should provide UTC format (.000Z) matching original lambda.

    After refactoring to match original lambda_function.py:117-120, dates are now
    formatted as UTC with .000Z suffix instead of KST with +09:00 offset.
    """
    session = Mock(spec=requests.Session)
    client = NaverBookingAPIClient(session=session)

    start, end = client._get_default_date_range()

    # Verify UTC format with .000Z suffix (original lambda_function.py format)
    assert start.endswith(".000Z"), f"Expected UTC format, got: {start}"
    assert end.endswith(".000Z"), f"Expected UTC format, got: {end}"
    assert "T" in start and "T" in end, "Expected ISO 8601 format with 'T' separator"


def test_normalize_naive_datetime_appends_kst_offset():
    """Naive ISO strings should gain KST offset to satisfy API expectations."""
    session = Mock(spec=requests.Session)
    client = NaverBookingAPIClient(session=session)

    normalized = client._normalize_datetime_param("2024-02-15T10:20:30")
    assert normalized == "2024-02-15T10:20:30+09:00"


def test_completed_bookings_clamps_date_range_to_31_days():
    """RC08 fetches must clamp date window to 31 days to prevent huge data pulls."""
    session = Mock(spec=requests.Session)
    booking_repo = Mock()
    booking_repo.scan_unnotified_options.return_value = {
        "1051707": {
            "start_time": "2024-01-01T00:00:00.000Z",
            "end_time": "2024-04-01T23:59:59.000Z",
        }
    }

    client = NaverBookingAPIClient(session=session, booking_repo=booking_repo)

    with patch.object(client, "get_bookings", return_value=[]) as mocked_get_bookings:
        client.get_all_completed_bookings(["1051707"])

    _, kwargs = mocked_get_bookings.call_args
    assert kwargs["start_date"] == "2024-01-01T00:00:00.000Z"
    assert kwargs["end_date"] == "2024-01-31T23:59:59.000Z"
