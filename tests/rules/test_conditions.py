"""
Unit Tests for Condition Evaluators

Tests validate that condition evaluators replicate legacy SMS automation logic.

Coverage Targets:
- AC1: booking_not_in_db
- AC2: time_before_booking
- AC3: flag_not_set
- AC4: current_hour
- AC5: booking_status
- AC6: has_option_keyword
- AC7: date_range (Story 6.3)
- AC9: Immutability and no external state changes
- AC10: >85% coverage for src/rules/conditions.py
"""

from datetime import datetime, timedelta, date
from unittest.mock import Mock

import pytz

from src.rules.conditions import (
    booking_not_in_db,
    time_before_booking,
    flag_not_set,
    current_hour,
    booking_status,
    has_option_keyword,
    has_multiple_options,
    date_range,
    register_conditions,
)


KST = pytz.timezone("Asia/Seoul")


class TestBookingNotInDb:
    """AC1: booking_not_in_db - Check if booking is new (not in database)"""

    def test_new_booking_no_db_record(self):
        """Test: Returns True when db_record is None (new booking)"""
        context = {"db_record": None, "booking": Mock()}
        assert booking_not_in_db(context) is True

    def test_existing_booking_has_db_record(self):
        """Test: Returns False when db_record exists (booking in database)"""
        db_record = Mock()
        context = {"db_record": db_record, "booking": Mock()}
        assert booking_not_in_db(context) is False

    def test_existing_booking_with_dict_record(self):
        """Test: Returns False when db_record is a dict (existing booking)"""
        db_record = {
            "confirm_sms": True,
            "remind_sms": False,
            "option_sms": False,
        }
        context = {"db_record": db_record, "booking": Mock()}
        assert booking_not_in_db(context) is False

    def test_missing_db_record_key(self):
        """Test: Handles missing db_record key gracefully"""
        context = {"booking": Mock()}
        assert booking_not_in_db(context) is True

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        context = {"db_record": None, "booking": Mock()}
        original_keys = set(context.keys())
        booking_not_in_db(context)
        assert set(context.keys()) == original_keys


class TestTimeBeforeBooking:
    """AC2: time_before_booking - Time window validation"""

    def test_within_two_hour_window(self):
        """Test: Returns True when current time is within 2-hour window"""
        now = datetime(2025, 10, 19, 18, 30, tzinfo=KST)
        reserve_at = datetime(2025, 10, 19, 20, 0, tzinfo=KST)

        booking = Mock(reserve_at=reserve_at)
        context = {"current_time": now, "booking": booking}

        assert time_before_booking(context, hours=2) is True

    def test_at_window_start(self):
        """Test: Returns True when current time equals window start (inclusive)"""
        reserve_at = datetime(2025, 10, 19, 20, 0, tzinfo=KST)
        now = reserve_at - timedelta(hours=2)  # Exactly at start

        booking = Mock(reserve_at=reserve_at)
        context = {"current_time": now, "booking": booking}

        assert time_before_booking(context, hours=2) is True

    def test_before_window_start(self):
        """Test: Returns False when current time is before window start"""
        now = datetime(2025, 10, 19, 17, 59, tzinfo=KST)
        reserve_at = datetime(2025, 10, 19, 20, 0, tzinfo=KST)

        booking = Mock(reserve_at=reserve_at)
        context = {"current_time": now, "booking": booking}

        assert time_before_booking(context, hours=2) is False

    def test_at_window_end(self):
        """Test: Returns False when current time equals reservation (exclusive at end)"""
        reserve_at = datetime(2025, 10, 19, 20, 0, tzinfo=KST)
        now = reserve_at

        booking = Mock(reserve_at=reserve_at)
        context = {"current_time": now, "booking": booking}

        assert time_before_booking(context, hours=2) is False

    def test_after_window_end(self):
        """Test: Returns False when current time is after reservation"""
        reserve_at = datetime(2025, 10, 19, 20, 0, tzinfo=KST)
        now = reserve_at + timedelta(minutes=1)

        booking = Mock(reserve_at=reserve_at)
        context = {"current_time": now, "booking": booking}

        assert time_before_booking(context, hours=2) is False

    def test_different_hour_offset(self):
        """Test: Supports different hour offsets"""
        now = datetime(2025, 10, 19, 18, 0, tzinfo=KST)
        reserve_at = datetime(2025, 10, 19, 21, 0, tzinfo=KST)

        booking = Mock(reserve_at=reserve_at)
        context = {"current_time": now, "booking": booking}

        # Within 3-hour window
        assert time_before_booking(context, hours=3) is True
        # Not within 2-hour window
        assert time_before_booking(context, hours=2) is False

    def test_missing_current_time(self):
        """Test: Short-circuits on missing current_time"""
        context = {"booking": Mock(reserve_at=datetime.now(KST))}
        assert time_before_booking(context, hours=2) is False

    def test_missing_booking(self):
        """Test: Short-circuits on missing booking"""
        context = {"current_time": datetime.now(KST)}
        assert time_before_booking(context, hours=2) is False

    def test_booking_without_reserve_at(self):
        """Test: Short-circuits when booking has no reserve_at"""
        context = {
            "current_time": datetime.now(KST),
            "booking": Mock(spec=[]),  # No reserve_at attribute
        }
        assert time_before_booking(context, hours=2) is False

    def test_exception_handling(self):
        """Test: Gracefully handles exceptions"""
        context = {
            "current_time": datetime.now(KST),
            "booking": Mock(side_effect=Exception("Mock error")),
        }
        assert time_before_booking(context, hours=2) is False

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        context = {
            "current_time": datetime.now(KST),
            "booking": Mock(reserve_at=datetime.now(KST)),
        }
        original_keys = set(context.keys())
        time_before_booking(context, hours=2)
        assert set(context.keys()) == original_keys


class TestFlagNotSet:
    """AC3: flag_not_set - SMS flag guards"""

    def test_new_booking_no_db_record(self):
        """Test: Returns True for new bookings (no db_record)"""
        context = {"db_record": None, "booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is True

    def test_flag_false_in_dict_record(self):
        """Test: Returns True when flag is False in dict record"""
        db_record = {"confirm_sms": False, "remind_sms": False, "option_sms": False}
        context = {"db_record": db_record, "booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is True

    def test_flag_true_in_dict_record(self):
        """Test: Returns False when flag is True in dict record"""
        db_record = {"confirm_sms": True, "remind_sms": False, "option_sms": False}
        context = {"db_record": db_record, "booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is False

    def test_flag_missing_in_dict_record(self):
        """Test: Returns True when flag is missing from dict record"""
        db_record = {}
        context = {"db_record": db_record, "booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is True

    def test_flag_false_in_dataclass_record(self):
        """Test: Returns True when flag is False in dataclass record"""
        db_record = Mock(confirm_sms=False, remind_sms=False)
        context = {"db_record": db_record, "booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is True

    def test_flag_true_in_dataclass_record(self):
        """Test: Returns False when flag is True in dataclass record"""
        db_record = Mock(confirm_sms=True, remind_sms=False)
        context = {"db_record": db_record, "booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is False

    def test_all_flag_types(self):
        """Test: Works with all SMS flag types"""
        db_record = {
            "confirm_sms": False,
            "remind_sms": True,
            "option_sms": False,
        }
        context = {"db_record": db_record, "booking": Mock()}

        assert flag_not_set(context, flag="confirm_sms") is True
        assert flag_not_set(context, flag="remind_sms") is False
        assert flag_not_set(context, flag="option_sms") is True

    def test_missing_db_record_key(self):
        """Test: Handles missing db_record key"""
        context = {"booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is True

    def test_exception_handling(self):
        """Test: Gracefully handles exceptions"""
        db_record = Mock(side_effect=Exception("Mock error"))
        context = {"db_record": db_record, "booking": Mock()}
        assert flag_not_set(context, flag="confirm_sms") is False

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        db_record = {"confirm_sms": False}
        context = {"db_record": db_record, "booking": Mock()}
        original_keys = set(context.keys())
        flag_not_set(context, flag="confirm_sms")
        assert set(context.keys()) == original_keys
        assert db_record == {"confirm_sms": False}  # db_record unchanged


class TestCurrentHour:
    """AC4: current_hour - Time-of-day gating"""

    def test_matching_hour(self):
        """Test: Returns True when current hour matches"""
        now = datetime(2025, 10, 19, 20, 30, tzinfo=KST)
        context = {"current_time": now}
        assert current_hour(context, hour=20) is True

    def test_non_matching_hour(self):
        """Test: Returns False when current hour doesn't match"""
        now = datetime(2025, 10, 19, 19, 30, tzinfo=KST)
        context = {"current_time": now}
        assert current_hour(context, hour=20) is False

    def test_midnight_hour(self):
        """Test: Works with midnight (hour=0)"""
        now = datetime(2025, 10, 19, 0, 30, tzinfo=KST)
        context = {"current_time": now}
        assert current_hour(context, hour=0) is True
        assert current_hour(context, hour=1) is False

    def test_last_hour_of_day(self):
        """Test: Works with hour 23"""
        now = datetime(2025, 10, 19, 23, 59, tzinfo=KST)
        context = {"current_time": now}
        assert current_hour(context, hour=23) is True
        assert current_hour(context, hour=22) is False

    def test_all_hours(self):
        """Test: Works for all 24 hours"""
        for h in range(24):
            now = datetime(2025, 10, 19, h, 0, tzinfo=KST)
            context = {"current_time": now}
            assert current_hour(context, hour=h) is True
            if h < 23:
                assert current_hour(context, hour=h + 1) is False

    def test_missing_current_time(self):
        """Test: Handles missing current_time"""
        context = {}
        assert current_hour(context, hour=20) is False

    def test_exception_handling(self):
        """Test: Gracefully handles exceptions"""
        context = {"current_time": Mock(side_effect=Exception("Mock error"))}
        assert current_hour(context, hour=20) is False

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        context = {"current_time": datetime(2025, 10, 19, 20, 0, tzinfo=KST)}
        original_keys = set(context.keys())
        current_hour(context, hour=20)
        assert set(context.keys()) == original_keys


class TestBookingStatus:
    """AC5: booking_status - Status code matching"""

    def test_rc03_confirmed_status(self):
        """Test: Matches RC03 (confirmed) status"""
        booking = Mock(status="RC03")
        context = {"booking": booking}
        assert booking_status(context, status="RC03") is True

    def test_rc08_completed_status(self):
        """Test: Matches RC08 (completed) status"""
        booking = Mock(status="RC08")
        context = {"booking": booking}
        assert booking_status(context, status="RC08") is True

    def test_non_matching_status(self):
        """Test: Returns False for non-matching status"""
        booking = Mock(status="RC03")
        context = {"booking": booking}
        assert booking_status(context, status="RC08") is False

    def test_case_sensitive_matching(self):
        """Test: Status matching is case-sensitive"""
        booking = Mock(status="rc03")
        context = {"booking": booking}
        assert booking_status(context, status="RC03") is False

    def test_other_status_codes(self):
        """Test: Supports any status code matching"""
        booking = Mock(status="RC99")
        context = {"booking": booking}
        assert booking_status(context, status="RC99") is True
        assert booking_status(context, status="RC98") is False

    def test_missing_booking(self):
        """Test: Handles missing booking"""
        context = {}
        assert booking_status(context, status="RC03") is False

    def test_booking_without_status(self):
        """Test: Handles booking without status attribute"""
        booking = Mock(spec=[])  # No status attribute
        context = {"booking": booking}
        assert booking_status(context, status="RC03") is False

    def test_none_status(self):
        """Test: Handles None status value"""
        booking = Mock(status=None)
        context = {"booking": booking}
        assert booking_status(context, status="RC03") is False

    def test_exception_handling(self):
        """Test: Gracefully handles exceptions"""
        booking = Mock(side_effect=Exception("Mock error"))
        context = {"booking": booking}
        assert booking_status(context, status="RC03") is False

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        booking = Mock(status="RC03")
        context = {"booking": booking}
        original_keys = set(context.keys())
        booking_status(context, status="RC03")
        assert set(context.keys()) == original_keys


class TestHasOptionKeyword:
    """AC6: has_option_keyword - Option keyword detection"""

    def test_option_flag_true(self):
        """Test: Returns True when booking.option is True"""
        booking = Mock(option=True, option_keywords=[])
        context = {"booking": booking}
        assert has_option_keyword(context) is True

    def test_option_flag_false(self):
        """Test: Returns False when booking.option is False"""
        booking = Mock(option=False, option_keywords=[])
        context = {"booking": booking}
        assert has_option_keyword(context) is False

    def test_keyword_match_in_list(self):
        """Test: Detects keyword in option_keywords list"""
        booking = Mock(option=False, option_keywords=["일반예약", "네이버", "인스타그램"])
        settings = Mock(option_keywords=["네이버", "인스타", "원본"])
        context = {"booking": booking, "settings": settings}
        assert has_option_keyword(context) is True

    def test_keyword_no_match(self):
        """Test: Returns False when no keywords match"""
        booking = Mock(option=False, option_keywords=["일반예약", "기타"])
        settings = Mock(option_keywords=["네이버", "인스타", "원본"])
        context = {"booking": booking, "settings": settings}
        assert has_option_keyword(context) is False

    def test_multiple_keywords_first_match(self):
        """Test: Returns True on first keyword match (early exit)"""
        booking = Mock(option=False, option_keywords=["네이버", "인스타그램", "원본"])
        settings = Mock(option_keywords=["네이버", "인스타", "원본"])
        context = {"booking": booking, "settings": settings}
        assert has_option_keyword(context) is True

    def test_default_keyword_list_no_settings(self):
        """Test: Uses default keyword list when settings not provided"""
        booking = Mock(option=False, option_keywords=["네이버"])
        context = {"booking": booking}  # No settings
        # Should use default ['네이버', '인스타', '원본']
        assert has_option_keyword(context) is True

    def test_empty_option_keywords(self):
        """Test: Returns False when booking has no option_keywords"""
        booking = Mock(option=False, option_keywords=[])
        context = {"booking": booking}
        assert has_option_keyword(context) is False

    def test_missing_option_keywords_attribute(self):
        """Test: Handles missing option_keywords attribute"""
        booking = Mock(spec=["option"])
        booking.option = False
        context = {"booking": booking}
        assert has_option_keyword(context) is False

    def test_option_keyword_case_sensitive(self):
        """Test: Keyword matching is case-sensitive"""
        booking = Mock(option=False, option_keywords=["Naver"])  # Capital N
        settings = Mock(option_keywords=["네이버", "인스타", "원본"])
        context = {"booking": booking, "settings": settings}
        assert has_option_keyword(context) is False

    def test_option_keywords_as_dicts(self):
        """Test: Handles option_keywords as dicts with 'name' field"""
        option1 = {"name": "일반예약"}
        option2 = {"name": "네이버"}
        booking = Mock(option=False, option_keywords=[option1, option2])
        settings = Mock(option_keywords=["네이버", "인스타", "원본"])
        context = {"booking": booking, "settings": settings}
        assert has_option_keyword(context) is True

    def test_keywords_override_params(self):
        """Test: Explicit keywords override settings/default list"""
        booking = Mock(option=False, option_keywords=["전문가 보정", "기타"])
        settings = Mock(option_keywords=["네이버", "인스타"])
        context = {"booking": booking, "settings": settings}
        assert has_option_keyword(context, keywords=["전문가 보정"]) is True

    def test_keywords_override_params_no_match(self):
        """Test: Explicit keywords list respected when no match"""
        booking = Mock(option=False, option_keywords=["네이버", "인스타"])
        settings = Mock(option_keywords=["네이버", "인스타"])
        context = {"booking": booking, "settings": settings}
        assert has_option_keyword(context, keywords=["전문가 보정"]) is False

    def test_missing_booking(self):
        """Test: Handles missing booking"""
        context = {}
        assert has_option_keyword(context) is False

    def test_exception_handling(self):
        """Test: Gracefully handles exceptions"""
        booking = Mock(side_effect=Exception("Mock error"))
        context = {"booking": booking}
        assert has_option_keyword(context) is False

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        booking = Mock(option=False, option_keywords=["네이버"])
        context = {"booking": booking}
        original_keys = set(context.keys())
        has_option_keyword(context)
        assert set(context.keys()) == original_keys


class TestDateRange:
    """AC7: date_range - Date range validation"""

    def test_booking_within_range(self):
        """Test: Returns True when booking date is within range"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is True

    def test_booking_at_start_boundary(self):
        """Test: Returns True when booking date equals start date (inclusive)"""
        booking = Mock(reserve_at=datetime(2025, 10, 19, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is True

    def test_booking_at_end_boundary(self):
        """Test: Returns True when booking date equals end date (inclusive)"""
        booking = Mock(reserve_at=datetime(2025, 10, 21, 23, 59, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is True

    def test_booking_before_range(self):
        """Test: Returns False when booking date is before start date"""
        booking = Mock(reserve_at=datetime(2025, 10, 18, 23, 59, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is False

    def test_booking_after_range(self):
        """Test: Returns False when booking date is after end date"""
        booking = Mock(reserve_at=datetime(2025, 10, 22, 0, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is False

    def test_single_day_range(self):
        """Test: Works with single-day range (start_date == end_date)"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 12, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-20", end_date="2025-10-20") is True
        assert date_range(context, start_date="2025-10-20", end_date="2025-10-21") is True
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-20") is True

    def test_naive_datetime(self):
        """Test: Works with naive (non-timezone-aware) datetime"""
        # Naive datetime (no timezone info)
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is True

    def test_timezone_aware_datetime(self):
        """Test: Works with timezone-aware datetime"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is True

    def test_different_timezones(self):
        """Test: Works regardless of timezone on reserve_at"""
        utc = pytz.UTC
        booking = Mock(reserve_at=datetime(2025, 10, 20, 1, 0, tzinfo=utc))  # 10:00 KST
        context = {"booking": booking}
        # Date comparison uses just the date part, so timezone doesn't affect comparison
        assert date_range(context, start_date="2025-10-20", end_date="2025-10-20") is True

    def test_invalid_start_date_format(self):
        """Test: Returns False when start_date format is invalid"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="20-10-2025", end_date="2025-10-21") is False
        assert date_range(context, start_date="2025/10/20", end_date="2025-10-21") is False

    def test_invalid_end_date_format(self):
        """Test: Returns False when end_date format is invalid"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="21-10-2025") is False

    def test_out_of_range_date_values(self):
        """Test: Returns False when date values are out of range"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        # Invalid month
        assert date_range(context, start_date="2025-13-01", end_date="2025-10-21") is False
        # Invalid day
        assert date_range(context, start_date="2025-02-30", end_date="2025-10-21") is False

    def test_missing_booking(self):
        """Test: Returns False when booking is missing"""
        context = {}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is False

    def test_booking_without_reserve_at(self):
        """Test: Returns False when booking has no reserve_at"""
        booking = Mock(spec=[])  # No reserve_at attribute
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is False

    def test_booking_with_none_reserve_at(self):
        """Test: Returns False when reserve_at is None"""
        booking = Mock(reserve_at=None)
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is False

    def test_reserve_at_not_datetime(self):
        """Test: Returns False when reserve_at is not a datetime"""
        booking = Mock(reserve_at="2025-10-20")  # String, not datetime
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is False

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        original_keys = set(context.keys())
        date_range(context, start_date="2025-10-19", end_date="2025-10-21")
        assert set(context.keys()) == original_keys

    def test_exception_handling(self):
        """Test: Gracefully handles unexpected exceptions"""
        booking = Mock(side_effect=Exception("Mock error"))
        context = {"booking": booking}
        assert date_range(context, start_date="2025-10-19", end_date="2025-10-21") is False

    def test_leap_year_date(self):
        """Test: Works with leap year dates (Feb 29)"""
        booking = Mock(reserve_at=datetime(2024, 2, 29, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2024-02-28", end_date="2024-03-01") is True
        assert date_range(context, start_date="2024-02-29", end_date="2024-02-29") is True

    def test_year_boundary(self):
        """Test: Works across year boundaries"""
        booking = Mock(reserve_at=datetime(2025, 1, 1, 0, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="2024-12-31", end_date="2025-01-01") is True
        assert date_range(context, start_date="2025-01-01", end_date="2025-01-02") is True

    def test_empty_string_dates(self):
        """Test: Returns False with empty string dates"""
        booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=KST))
        context = {"booking": booking}
        assert date_range(context, start_date="", end_date="2025-10-21") is False
        assert date_range(context, start_date="2025-10-19", end_date="") is False


class TestHasMultipleOptions:
    """Story 6.4: has_multiple_options - Check if booking has minimum matching option keywords"""

    def test_sufficient_keyword_matches(self):
        """Test: Returns True when match count >= min_count"""
        booking = Mock(option_keywords=["네이버 Pay", "원본 방식"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=2)
        assert result is True

    def test_exact_minimum_matches(self):
        """Test: Returns True when match count equals min_count"""
        booking = Mock(option_keywords=["네이버 Pay"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=1)
        assert result is True

    def test_insufficient_keyword_matches(self):
        """Test: Returns False when match count < min_count"""
        booking = Mock(option_keywords=["네이버 Pay"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=2)
        assert result is False

    def test_no_keyword_matches(self):
        """Test: Returns False when no keywords match"""
        booking = Mock(option_keywords=["일반 방식"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=1)
        assert result is False

    def test_empty_option_keywords(self):
        """Test: Returns False when booking has no option_keywords"""
        booking = Mock(option_keywords=[])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=1)
        assert result is False

    def test_missing_option_keywords_attribute(self):
        """Test: Returns False when booking has no option_keywords attribute"""
        booking = Mock(spec=[])  # No option_keywords attribute
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=1)
        assert result is False

    def test_dict_format_options(self):
        """Test: Handles dict-format options"""
        booking = Mock(option_keywords=[{"name": "네이버 Pay"}, {"name": "원본"}])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=2)
        assert result is True

    def test_mixed_format_options(self):
        """Test: Handles mixed format options (string, dict, object)"""
        option_obj = Mock()
        option_obj.name = "원본 방식"
        booking = Mock(option_keywords=["네이버 Pay", {"name": "인스타"}, option_obj])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버", "인스타", "원본"], min_count=3)
        assert result is True

    def test_higher_min_count(self):
        """Test: Supports higher min_count values"""
        booking = Mock(option_keywords=["네이버", "인스타", "원본"])
        context = {"booking": booking}
        assert (
            has_multiple_options(context, keywords=["네이버", "인스타", "원본"], min_count=3)
            is True
        )
        assert (
            has_multiple_options(context, keywords=["네이버", "인스타", "원본"], min_count=4)
            is False
        )

    def test_duplicate_option_names_counted_once(self):
        """Test: Each option is counted only once even if multiple keywords match"""
        booking = Mock(option_keywords=["네이버-원본-인스타"])
        context = {"booking": booking}
        # Only one option, should count as 1 even though 3 keywords match within it
        result = has_multiple_options(context, keywords=["네이버", "원본", "인스타"], min_count=1)
        assert result is True
        result = has_multiple_options(context, keywords=["네이버", "원본", "인스타"], min_count=2)
        assert result is False

    def test_missing_booking(self):
        """Test: Returns False when booking is missing from context"""
        context = {}
        result = has_multiple_options(context, keywords=["네이버"], min_count=1)
        assert result is False

    def test_invalid_min_count_zero(self):
        """Test: Returns False when min_count is 0"""
        booking = Mock(option_keywords=["네이버"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버"], min_count=0)
        assert result is False

    def test_invalid_min_count_negative(self):
        """Test: Returns False when min_count is negative"""
        booking = Mock(option_keywords=["네이버"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버"], min_count=-1)
        assert result is False

    def test_invalid_keywords_empty_list(self):
        """Test: Returns False when keywords list is empty"""
        booking = Mock(option_keywords=["네이버"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=[], min_count=1)
        assert result is False

    def test_invalid_keywords_none(self):
        """Test: Returns False when keywords is None"""
        booking = Mock(option_keywords=["네이버"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=None, min_count=1)
        assert result is False

    def test_case_sensitive_matching(self):
        """Test: Keyword matching is case-sensitive"""
        booking = Mock(option_keywords=["NAVER PAY"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버"], min_count=1)
        assert result is False

    def test_partial_string_matching(self):
        """Test: Keywords match as substring"""
        booking = Mock(option_keywords=["My네이버Service"])
        context = {"booking": booking}
        result = has_multiple_options(context, keywords=["네이버"], min_count=1)
        assert result is True

    def test_immutable_context(self):
        """Test: Does not mutate context dictionary"""
        booking = Mock(option_keywords=["네이버"])
        context = {"booking": booking}
        original_keys = set(context.keys())
        has_multiple_options(context, keywords=["네이버"], min_count=1)
        assert set(context.keys()) == original_keys


class TestRegisterConditions:
    """Test registry helper function"""

    def test_register_all_conditions(self):
        """Test: Registers all 9 condition evaluators"""
        engine = Mock()
        register_conditions(engine)

        # Verify all 9 conditions registered (including has_multiple_options)
        assert engine.register_condition.call_count == 9

        # Verify correct names registered
        calls = [call[0][0] for call in engine.register_condition.call_args_list]
        assert "booking_not_in_db" in calls
        assert "time_before_booking" in calls
        assert "flag_not_set" in calls
        assert "current_hour" in calls
        assert "booking_status" in calls
        assert "has_option_keyword" in calls
        assert "has_multiple_options" in calls
        assert "date_range" in calls
        assert "has_pro_edit_option" in calls

    def test_registered_functions_are_correct(self):
        """Test: Registered functions are the actual evaluators"""
        engine = Mock()
        register_conditions(engine)

        # Get registered functions
        calls = engine.register_condition.call_args_list
        registered = {call[0][0]: call[0][1] for call in calls}

        # Verify they're the right functions
        assert registered["booking_not_in_db"] == booking_not_in_db
        assert registered["time_before_booking"] == time_before_booking
        assert registered["flag_not_set"] == flag_not_set
        assert registered["current_hour"] == current_hour
        assert registered["booking_status"] == booking_status
        assert registered["has_option_keyword"] == has_option_keyword
        assert registered["has_multiple_options"] == has_multiple_options
        assert registered["date_range"] == date_range

    def test_register_with_settings(self):
        """Test: Accepts settings parameter"""
        engine = Mock()
        settings = Mock()
        # Should not raise
        register_conditions(engine, settings)
        assert engine.register_condition.call_count == 9

    def test_register_without_settings(self):
        """Test: Works without settings parameter"""
        engine = Mock()
        # Should not raise
        register_conditions(engine)
        assert engine.register_condition.call_count == 9
