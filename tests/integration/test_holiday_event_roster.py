"""
Holiday Event Roster Keyword Filtering Tests

AC3 Fix: Validates that the holiday event roster correctly filters bookings
by keywords from the has_multiple_options condition.

This test ensures:
1. Keywords are extracted from rule configuration
2. Bookings are filtered based on keyword criteria
3. Only bookings with matching keywords are included in the roster
"""

from datetime import datetime
from typing import List
from unittest.mock import Mock

from src.domain.booking import Booking
from src.main import _build_holiday_event_roster, _get_holiday_event_rule_window
from src.rules.engine import RuleEngine


class TestGetHolidayEventRuleWindow:
    """Test extraction of date range and keywords from Holiday Event rule."""

    def test_extracts_keywords_from_has_multiple_options(self):
        """Verify that keywords are extracted from has_multiple_options condition."""
        # Setup mock rule with keywords
        mock_rule = Mock()
        mock_rule.name = "Holiday Event Customer List"

        # Create mock conditions
        date_condition = Mock()
        date_condition.type = "date_range"
        date_condition.params = {
            "start_date": "2024-12-01",
            "end_date": "2024-12-31",
        }

        keyword_condition = Mock()
        keyword_condition.type = "has_multiple_options"
        keyword_condition.params = {
            "min_count": 2,
            "keywords": ["네이버", "인스타"],
        }

        mock_rule.conditions = [date_condition, keyword_condition]

        mock_engine = Mock(spec=RuleEngine)
        mock_engine.rules = [mock_rule]

        # Execute
        window = _get_holiday_event_rule_window(mock_engine)

        # Verify
        assert window is not None
        assert "keywords" in window
        assert window["keywords"] == ["네이버", "인스타"]
        assert window["min_count"] == 2
        assert window["start_date"] == "2024-12-01"
        assert window["end_date"] == "2024-12-31"

    def test_returns_none_when_rule_not_found(self):
        """Verify None is returned when Holiday Event rule is not found."""
        mock_engine = Mock(spec=RuleEngine)
        mock_engine.rules = []

        window = _get_holiday_event_rule_window(mock_engine)

        assert window is None

    def test_extracts_without_keywords_when_not_present(self):
        """Verify extraction works when keywords are not in condition params."""
        mock_rule = Mock()
        mock_rule.name = "Holiday Event Customer List"

        condition = Mock()
        condition.type = "has_multiple_options"
        condition.params = {"min_count": 2}

        mock_rule.conditions = [condition]

        mock_engine = Mock(spec=RuleEngine)
        mock_engine.rules = [mock_rule]

        window = _get_holiday_event_rule_window(mock_engine)

        assert window is not None
        assert "keywords" not in window
        assert window["min_count"] == 2


class TestBuildHolidayEventRoster:
    """Test keyword filtering in holiday event roster building."""

    def _create_booking(
        self,
        booking_num: str,
        name: str,
        phone: str,
        reserve_at: datetime,
        option_keywords: List[str],
    ) -> Booking:
        """Helper to create a mock Booking object."""
        booking = Mock(spec=Booking)
        booking.booking_num = booking_num
        booking.name = name
        booking.phone = phone
        booking.phone_masked = "010-****-1234"
        booking.reserve_at = reserve_at
        booking.option_keywords = option_keywords
        return booking

    def _create_mock_engine_with_keywords(
        self,
        start_date: str,
        end_date: str,
        min_count: int,
        keywords: List[str],
    ) -> RuleEngine:
        """Helper to create a mock engine with keyword configuration."""
        mock_rule = Mock()
        mock_rule.name = "Holiday Event Customer List"

        date_condition = Mock()
        date_condition.type = "date_range"
        date_condition.params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        keyword_condition = Mock()
        keyword_condition.type = "has_multiple_options"
        keyword_condition.params = {
            "min_count": min_count,
            "keywords": keywords,
        }

        mock_rule.conditions = [date_condition, keyword_condition]

        mock_engine = Mock(spec=RuleEngine)
        mock_engine.rules = [mock_rule]

        return mock_engine

    def test_filters_by_keywords_ac3_fix(self):
        """
        AC3 Fix Test: Verify bookings without matching keywords are excluded.

        This test validates the critical fix where bookings with multiple options
        are only included if they have at least one option keyword matching
        the configured keywords.
        """
        # Setup: Create bookings with different keyword combinations
        base_date = datetime(2024, 12, 15, 10, 0, 0)

        booking_with_matching_keyword = self._create_booking(
            "BK001",
            "John Doe",
            "010-1234-5678",
            base_date,
            ["네이버", "원본"],  # Has matching keyword
        )

        booking_without_matching_keyword = self._create_booking(
            "BK002",
            "Jane Smith",
            "010-2345-6789",
            base_date,
            ["기타", "상담"],  # No matching keywords - SHOULD BE EXCLUDED
        )

        booking_with_partial_match = self._create_booking(
            "BK003",
            "Bob Johnson",
            "010-3456-7890",
            base_date,
            ["인스타", "영상"],  # Has one matching keyword
        )

        bookings = [
            booking_with_matching_keyword,
            booking_without_matching_keyword,
            booking_with_partial_match,
        ]

        engine = self._create_mock_engine_with_keywords(
            start_date="2024-12-01",
            end_date="2024-12-31",
            min_count=2,
            keywords=["네이버", "인스타", "원본"],
        )

        # Execute
        roster = _build_holiday_event_roster(bookings, engine)

        # Verify AC3: Only bookings with matching keywords are included
        assert len(roster) == 2
        roster_names = {item["name"] for item in roster}
        assert "John Doe" in roster_names
        assert "Bob Johnson" in roster_names
        assert "Jane Smith" not in roster_names  # EXCLUDED due to AC3 fix

    def test_includes_all_with_empty_keywords(self):
        """Verify all bookings are included when keywords list is empty."""
        base_date = datetime(2024, 12, 15, 10, 0, 0)

        booking1 = self._create_booking(
            "BK001",
            "John Doe",
            "010-1234-5678",
            base_date,
            ["네이버"],
        )

        booking2 = self._create_booking(
            "BK002",
            "Jane Smith",
            "010-2345-6789",
            base_date,
            ["기타"],  # No matching keywords, but keywords list is empty
        )

        bookings = [booking1, booking2]

        engine = self._create_mock_engine_with_keywords(
            start_date="2024-12-01",
            end_date="2024-12-31",
            min_count=1,
            keywords=[],  # Empty keywords - no filtering
        )

        roster = _build_holiday_event_roster(bookings, engine)

        # Both should be included since keywords list is empty
        assert len(roster) == 2

    def test_respects_date_range_with_keywords(self):
        """Verify date range filtering works together with keyword filtering."""
        in_range_date = datetime(2024, 12, 15, 10, 0, 0)
        before_range_date = datetime(2024, 11, 30, 10, 0, 0)
        _ = datetime(2025, 1, 5, 10, 0, 0)  # after_range_date - kept for test clarity

        booking_in_range_with_keyword = self._create_booking(
            "BK001",
            "John Doe",
            "010-1234-5678",
            in_range_date,
            ["네이버"],
        )

        booking_before_range_with_keyword = self._create_booking(
            "BK002",
            "Jane Smith",
            "010-2345-6789",
            before_range_date,
            ["네이버"],  # Has keyword but outside date range
        )

        booking_in_range_without_keyword = self._create_booking(
            "BK003",
            "Bob Johnson",
            "010-3456-7890",
            in_range_date,
            ["기타"],  # In date range but no matching keyword
        )

        bookings = [
            booking_in_range_with_keyword,
            booking_before_range_with_keyword,
            booking_in_range_without_keyword,
        ]

        engine = self._create_mock_engine_with_keywords(
            start_date="2024-12-01",
            end_date="2024-12-31",
            min_count=1,
            keywords=["네이버"],
        )

        roster = _build_holiday_event_roster(bookings, engine)

        # Only booking_in_range_with_keyword should be included
        assert len(roster) == 1
        assert roster[0]["name"] == "John Doe"

    def test_respects_min_count_with_keywords(self):
        """Verify min_count filtering works together with keyword filtering."""
        base_date = datetime(2024, 12, 15, 10, 0, 0)

        booking_insufficient_options = self._create_booking(
            "BK001",
            "John Doe",
            "010-1234-5678",
            base_date,
            ["네이버"],  # Has keyword but only 1 option
        )

        booking_sufficient_options = self._create_booking(
            "BK002",
            "Jane Smith",
            "010-2345-6789",
            base_date,
            ["네이버", "인스타"],  # Has keywords and 2 options
        )

        bookings = [booking_insufficient_options, booking_sufficient_options]

        engine = self._create_mock_engine_with_keywords(
            start_date="2024-12-01",
            end_date="2024-12-31",
            min_count=2,  # Requires 2 or more options
            keywords=["네이버", "인스타"],
        )

        roster = _build_holiday_event_roster(bookings, engine)

        # Only booking with 2+ options should be included
        assert len(roster) == 1
        assert roster[0]["name"] == "Jane Smith"

    def test_empty_roster_when_no_matches(self):
        """Verify empty roster when no bookings match criteria."""
        base_date = datetime(2024, 12, 15, 10, 0, 0)

        booking = self._create_booking(
            "BK001",
            "John Doe",
            "010-1234-5678",
            base_date,
            ["기타"],  # No matching keywords
        )

        bookings = [booking]

        engine = self._create_mock_engine_with_keywords(
            start_date="2024-12-01",
            end_date="2024-12-31",
            min_count=1,
            keywords=["네이버", "인스타"],
        )

        roster = _build_holiday_event_roster(bookings, engine)

        assert len(roster) == 0

    def test_roster_includes_option_keywords(self):
        """Verify roster output includes option_keywords for reference."""
        base_date = datetime(2024, 12, 15, 10, 0, 0)

        booking = self._create_booking(
            "BK001",
            "John Doe",
            "010-1234-5678",
            base_date,
            ["네이버", "인스타"],
        )

        bookings = [booking]

        engine = self._create_mock_engine_with_keywords(
            start_date="2024-12-01",
            end_date="2024-12-31",
            min_count=2,
            keywords=["네이버", "인스타"],
        )

        roster = _build_holiday_event_roster(bookings, engine)

        assert len(roster) == 1
        assert roster[0]["option_keywords"] == ["네이버", "인스타"]
        assert roster[0]["reserve_at"] == "2024-12-15"
