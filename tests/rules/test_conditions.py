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
- AC9: Immutability and no external state changes
- AC10: >85% coverage for src/rules/conditions.py
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytz

from src.rules.conditions import (
    booking_not_in_db,
    time_before_booking,
    flag_not_set,
    current_hour,
    booking_status,
    has_option_keyword,
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
        booking = Mock(
            option=False, option_keywords=["일반예약", "네이버", "인스타그램"]
        )
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


class TestRegisterConditions:
    """Test registry helper function"""

    def test_register_all_conditions(self):
        """Test: Registers all 6 condition evaluators"""
        engine = Mock()
        register_conditions(engine)

        # Verify all 6 conditions registered
        assert engine.register_condition.call_count == 6

        # Verify correct names registered
        calls = [call[0][0] for call in engine.register_condition.call_args_list]
        assert "booking_not_in_db" in calls
        assert "time_before_booking" in calls
        assert "flag_not_set" in calls
        assert "current_hour" in calls
        assert "booking_status" in calls
        assert "has_option_keyword" in calls

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

    def test_register_with_settings(self):
        """Test: Accepts settings parameter"""
        engine = Mock()
        settings = Mock()
        # Should not raise
        register_conditions(engine, settings)
        assert engine.register_condition.call_count == 6

    def test_register_without_settings(self):
        """Test: Works without settings parameter"""
        engine = Mock()
        # Should not raise
        register_conditions(engine)
        assert engine.register_condition.call_count == 6
