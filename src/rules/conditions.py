"""
Condition Evaluators for Rule Engine

Implements 6 condition evaluators that mirror legacy SMS automation logic,
enabling rule engine to make identical booking decisions as the monolithic Lambda.

Acceptance Criteria:
- AC1: booking_not_in_db - Check if booking exists in DynamoDB
- AC2: time_before_booking - Time window validation (hours before booking)
- AC3: flag_not_set - SMS flag guards (confirm, remind, option)
- AC4: current_hour - Time-of-day gating (20:00 for option SMS)
- AC5: booking_status - RC03/RC08 status code matching
- AC6: has_option_keyword - Option keyword detection
- AC7: Registry helper for integration with RuleEngine
- AC9: Immutability - No context mutations or external state changes

All evaluators are pure functions with no side effects.
Reference: docs/brownfield-architecture.md:1070-1145
"""

from typing import Any, Dict, List, Optional
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def booking_not_in_db(context: Dict[str, Any], **params) -> bool:
    """
    Evaluate if a booking does not exist in the database.

    Returns True only when the booking is new (context['db_record'] is None).
    Returns False if the booking already exists in DynamoDB.

    Args:
        context: Dictionary containing:
            - db_record: Booking from DynamoDB or None for new bookings
            - booking: Current booking object
        **params: Additional parameters (unused)

    Returns:
        bool: True if booking is new (db_record is None), False otherwise

    Reference:
        Legacy: original_code/lambda_function.py:135-154 (new booking branch)

    Example:
        >>> context = {'db_record': None, 'booking': new_booking}
        >>> booking_not_in_db(context)
        True
        >>> context = {'db_record': existing_record, 'booking': existing_booking}
        >>> booking_not_in_db(context)
        False
    """
    db_record = context.get("db_record")
    result = db_record is None
    logger.debug(f"booking_not_in_db: db_record={db_record}, result={result}")
    return result


def time_before_booking(context: Dict[str, Any], hours: int = 2, **params) -> bool:
    """
    Evaluate if current time is within specified hours before a booking.

    Reproduces legacy window check: reserve_at - timedelta(hours=X) <= now < reserve_at

    Args:
        context: Dictionary containing:
            - current_time: Current datetime (timezone-aware, KST)
            - booking: Booking object with reserve_at datetime
        hours: Number of hours before booking (default: 2)
        **params: Additional parameters (unused)

    Returns:
        bool: True if within the time window, False otherwise

    Reference:
        Legacy: original_code/lambda_function.py:137-169

    Example:
        >>> now = datetime(2025, 10, 19, 18, 30, tzinfo=pytz.timezone('Asia/Seoul'))
        >>> booking = Mock(reserve_at=datetime(2025, 10, 19, 20, 30, tzinfo=...))
        >>> context = {'current_time': now, 'booking': booking}
        >>> time_before_booking(context, hours=2)
        True  # Within 2-hour window
    """
    try:
        current_time = context.get("current_time")
        booking = context.get("booking")

        # Short-circuit on missing inputs
        if not current_time or not booking:
            logger.debug("time_before_booking: Missing current_time or booking")
            return False

        reserve_at = getattr(booking, "reserve_at", None)
        if not reserve_at:
            logger.debug("time_before_booking: Booking has no reserve_at")
            return False

        # Calculate window: (reserve_at - hours) to reserve_at
        window_start = reserve_at - timedelta(hours=hours)
        window_end = reserve_at

        # Check if current_time is within [window_start, window_end)
        result = window_start <= current_time < window_end

        logger.debug(
            f"time_before_booking(hours={hours}): "
            f"current={current_time}, reserve={reserve_at}, "
            f"window=[{window_start}, {window_end}), result={result}"
        )
        return result

    except Exception as e:
        logger.error(f"time_before_booking error: {e}", exc_info=True)
        return False


def flag_not_set(context: Dict[str, Any], flag: str, **params) -> bool:
    """
    Evaluate if an SMS flag is not set (missing or False).

    Returns True when the flag is missing or explicitly False.
    Returns False when the flag is True.

    Guards against duplicate SMS sending for confirm, remind, and option messages.

    Args:
        context: Dictionary containing:
            - db_record: Booking record from DynamoDB (dict or dataclass)
            - booking: Current booking object
        flag: Flag name ('confirm_sms', 'remind_sms', 'option_sms')
        **params: Additional parameters (unused)

    Returns:
        bool: True if flag is not set or False, False if flag is True

    Reference:
        Legacy: original_code/lambda_function.py:160-194 (flag checks)

    Example:
        >>> db_record = {'confirm_sms': False, 'remind_sms': True}
        >>> context = {'db_record': db_record, 'booking': booking}
        >>> flag_not_set(context, flag='confirm_sms')
        True  # confirm_sms is False
        >>> flag_not_set(context, flag='remind_sms')
        False  # remind_sms is True
    """
    try:
        db_record = context.get("db_record")

        # New bookings have no db_record, so flag is not set
        if db_record is None:
            logger.debug(f"flag_not_set({flag}): No db_record (new booking)")
            return True

        # Try to get flag value from db_record
        # Handle both dict and dataclass formats
        if isinstance(db_record, dict):
            flag_value = db_record.get(flag, False)
        else:
            flag_value = getattr(db_record, flag, False)

        # Flag is not set if it's missing (False) or explicitly False
        result = not flag_value

        logger.debug(f"flag_not_set({flag}): flag_value={flag_value}, result={result}")
        return result

    except Exception as e:
        logger.error(f"flag_not_set error: {e}", exc_info=True)
        return False


def current_hour(context: Dict[str, Any], hour: int, **params) -> bool:
    """
    Evaluate if the current hour matches a specific hour.

    Compares 24-hour integer against context['current_time'].hour using project timezone.

    Used to gate option SMS sending at 20:00 (8 PM).

    Args:
        context: Dictionary containing:
            - current_time: Current datetime (timezone-aware, KST - Asia/Seoul)
        hour: 24-hour integer (0-23)
        **params: Additional parameters (unused)

    Returns:
        bool: True if current hour matches, False otherwise

    Reference:
        Legacy: original_code/lambda_function.py:176-186 (option SMS 20:00 gating)

    Example:
        >>> now = datetime(2025, 10, 19, 20, 30, tzinfo=pytz.timezone('Asia/Seoul'))
        >>> context = {'current_time': now}
        >>> current_hour(context, hour=20)
        True  # Current hour is 20
        >>> current_hour(context, hour=19)
        False
    """
    try:
        current_time = context.get("current_time")

        if not current_time:
            logger.debug("current_hour: Missing current_time")
            return False

        current_h = current_time.hour
        result = current_h == hour

        logger.debug(f"current_hour({hour}): current_time.hour={current_h}, result={result}")
        return result

    except Exception as e:
        logger.error(f"current_hour error: {e}", exc_info=True)
        return False


def booking_status(context: Dict[str, Any], status: str, **params) -> bool:
    """
    Evaluate if booking status matches expected status code.

    Supports RC03 (confirmed) and RC08 (completed) status codes from Naver API.

    Args:
        context: Dictionary containing:
            - booking: Booking object with status attribute
        status: Expected status code ('RC03', 'RC08', etc.)
        **params: Additional parameters (unused)

    Returns:
        bool: True if booking status matches, False otherwise

    Reference:
        Legacy: docs/brownfield-architecture.md:1000-1035 (status codes)
        get_items() uses RC03 for confirmed, RC08 for completed

    Example:
        >>> booking = Mock(status='RC08')
        >>> context = {'booking': booking}
        >>> booking_status(context, status='RC08')
        True  # Status matches
        >>> booking_status(context, status='RC03')
        False
    """
    try:
        booking = context.get("booking")

        if not booking:
            logger.debug("booking_status: Missing booking")
            return False

        booking_status_code = getattr(booking, "status", None)

        if booking_status_code is None:
            logger.debug("booking_status: Booking has no status attribute")
            return False

        result = booking_status_code == status

        logger.debug(
            f"booking_status({status}): booking.status={booking_status_code}, " f"result={result}"
        )
        return result

    except Exception as e:
        logger.error(f"booking_status error: {e}", exc_info=True)
        return False


def has_option_keyword(context: Dict[str, Any], **params) -> bool:
    """
    Evaluate if booking has option keywords.

    Inspects booking's option keywords against configured keyword list.
    Matches legacy nested-loop behavior with early exit on first match.

    Option keywords are used to identify bookings that offer special options
    (e.g., via 네이버 Pay, Instagram, original method).

    Args:
        context: Dictionary containing:
            - booking: Booking object with option or option_keywords attribute
            - settings: Settings object with option_keywords configuration
        **params: Additional parameters (unused)

    Returns:
        bool: True if booking has any option keywords, False otherwise

    Reference:
        Legacy: original_code/lambda_function.py:255-366 (option keyword matching)
        Legacy keyword list: ['네이버', '인스타', '원본']

    Example:
        >>> booking = Mock(option=True, option_keywords=['네이버'])
        >>> settings = Mock(option_keywords=['네이버', '인스타', '원본'])
        >>> context = {'booking': booking, 'settings': settings}
        >>> has_option_keyword(context)
        True
    """
    try:
        booking = context.get("booking")
        settings = context.get("settings")
        keywords_param = params.get("keywords")

        if not booking:
            logger.debug("has_option_keyword: Missing booking")
            return False

        # Check simple 'option' flag first (faster path)
        option_flag = getattr(booking, "option", False)
        if option_flag is True:
            logger.debug("has_option_keyword: booking.option=True")
            return True

        # Get option keywords from booking (nested loop like legacy)
        booking_options = getattr(booking, "option_keywords", [])

        if not booking_options:
            logger.debug("has_option_keyword: No option_keywords on booking")
            return False

        # Determine keyword list priority: explicit params > settings > defaults
        keyword_list: List[str]
        if keywords_param is not None:
            if isinstance(keywords_param, str):
                keyword_list = [keywords_param]
            else:
                keyword_list = [str(keyword) for keyword in list(keywords_param)]
            logger.debug(f"has_option_keyword: Using keywords from params {keyword_list}")
        elif settings and getattr(settings, "option_keywords", None):
            keyword_list = list(getattr(settings, "option_keywords"))
            logger.debug(f"has_option_keyword: Using keywords from settings {keyword_list}")
        else:
            # Default keyword list matching legacy behavior
            keyword_list = ["네이버", "인스타", "원본"]
            logger.debug(f"has_option_keyword: Using default keyword list {keyword_list}")

        # Nested loop: check each option against keyword list (early exit on match)
        for option in booking_options:
            # Handle both string, dict, and object option formats
            if isinstance(option, str):
                option_name = option
            elif isinstance(option, dict):
                option_name = option.get("name", "")
            else:
                option_name = getattr(option, "name", "")

            for keyword in keyword_list:
                if keyword in option_name:
                    logger.debug(
                        f"has_option_keyword: Matched keyword '{keyword}' "
                        f"in option '{option_name}'"
                    )
                    return True

        logger.debug("has_option_keyword: No keywords matched")
        return False

    except Exception as e:
        logger.error(f"has_option_keyword error: {e}", exc_info=True)
        return False


def date_range(context: Dict[str, Any], start_date: str, end_date: str, **params) -> bool:
    """
    Evaluate if a booking falls within an inclusive date range.

    Checks if booking.reserve_at date falls within [start_date, end_date] (inclusive).
    Supports both naive and timezone-aware datetime objects.

    Args:
        context: Dictionary containing:
            - booking: Booking object with reserve_at datetime
            - current_time: Current datetime (optional, for reference)
        start_date: Start date as ISO string (YYYY-MM-DD)
        end_date: End date as ISO string (YYYY-MM-DD)
        **params: Additional parameters (unused)

    Returns:
        bool: True if booking.reserve_at.date() is within [start_date, end_date], False otherwise

    Reference:
        Story 6.3: Add Date-Range Condition Evaluator
        docs/epics/epic-6-post-mvp-enhancements.md#new-condition-evaluators

    Example:
        >>> from datetime import datetime
        >>> import pytz
        >>> booking = Mock(reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=pytz.timezone('Asia/Seoul')))
        >>> context = {'booking': booking}
        >>> date_range(context, start_date='2025-10-19', end_date='2025-10-21')
        True  # 2025-10-20 is within range
        >>> date_range(context, start_date='2025-10-21', end_date='2025-10-22')
        False  # 2025-10-20 is before start
    """
    try:
        from datetime import datetime as dt

        booking = context.get("booking")

        # Short-circuit on missing inputs
        if not booking:
            logger.debug("date_range: Missing booking")
            return False

        reserve_at = getattr(booking, "reserve_at", None)
        if not reserve_at:
            logger.debug("date_range: Booking has no reserve_at")
            return False

        # Parse start and end dates
        try:
            start_dt = dt.strptime(start_date, "%Y-%m-%d").date()
            end_dt = dt.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as e:
            logger.error(f"date_range: Invalid date format - {e}")
            return False

        # Convert reserve_at to date (handles both naive and timezone-aware)
        if hasattr(reserve_at, "date"):
            booking_date = reserve_at.date()
        else:
            logger.error(f"date_range: reserve_at is not a datetime object: {type(reserve_at)}")
            return False

        # Check if booking_date is within [start_dt, end_dt] (inclusive)
        result = start_dt <= booking_date <= end_dt

        logger.debug(
            f"date_range: start={start_date}, end={end_date}, "
            f"booking_date={booking_date}, result={result}"
        )
        return result

    except Exception as e:
        logger.error(f"date_range error: {e}", exc_info=True)
        return False


def has_multiple_options(
    context: Dict[str, Any], keywords: list, min_count: int = 1, **params
) -> bool:
    """
    Evaluate if booking has at least min_count matching option keywords.

    Inspects booking's option keywords against a provided keyword list and
    ensures at least min_count keywords match. Supports graceful handling of
    various option formats (string, dict, object).

    Args:
        context: Dictionary containing:
            - booking: Booking object with option_keywords attribute
            - settings: Settings object with configuration (optional)
        keywords: List of keywords to match against option keywords
        min_count: Minimum number of keywords to match (default: 1)
        **params: Additional parameters (unused)

    Returns:
        bool: True if at least min_count keywords match, False otherwise

    Reference:
        Story 6.4: Add Multi-Option Condition Evaluator
        docs/epics/epic-6-post-mvp-enhancements.md#new-condition-evaluators

    Example:
        >>> booking = Mock(option_keywords=['네이버', '원본'])
        >>> context = {'booking': booking}
        >>> has_multiple_options(context, keywords=['네이버', '인스타', '원본'], min_count=2)
        True  # Matched 2 keywords
        >>> has_multiple_options(context, keywords=['인스타'], min_count=1)
        False  # No matches
    """
    try:
        booking = context.get("booking")

        if not booking:
            logger.debug("has_multiple_options: Missing booking")
            return False

        # Validate min_count
        if not isinstance(min_count, int) or min_count < 1:
            logger.error(f"has_multiple_options: Invalid min_count={min_count}, must be >= 1")
            return False

        # Validate keywords list
        if not keywords or not isinstance(keywords, list):
            logger.debug("has_multiple_options: Invalid keywords parameter")
            return False

        # Get option keywords from booking
        booking_options = getattr(booking, "option_keywords", [])

        if not booking_options:
            logger.debug("has_multiple_options: No option_keywords on booking")
            return False

        # Count matches: iterate through booking options and check against keyword list
        match_count = 0
        for option in booking_options:
            # Handle both string, dict, and object option formats
            if isinstance(option, str):
                option_name = option
            elif isinstance(option, dict):
                option_name = option.get("name", "")
            else:
                option_name = getattr(option, "name", "")

            if not option_name:
                continue

            # Check if any keyword matches this option
            for keyword in keywords:
                if keyword in option_name:
                    match_count += 1
                    logger.debug(
                        f"has_multiple_options: Matched keyword '{keyword}' "
                        f"in option '{option_name}' (match_count={match_count})"
                    )
                    break  # Count each option only once per keyword match

        # Check if match count meets minimum threshold
        result = match_count >= min_count

        logger.debug(
            f"has_multiple_options: keywords={keywords}, min_count={min_count}, "
            f"match_count={match_count}, result={result}"
        )
        return result

    except Exception as e:
        logger.error(f"has_multiple_options error: {e}", exc_info=True)
        return False


def register_conditions(engine: Any, settings: Optional[Any] = None) -> None:
    """
    Register all condition evaluators with the rule engine.

    Wires condition evaluators into RuleEngine registry for use in rules.yaml.
    Called during Lambda startup to enable declarative rule composition.

    Args:
        engine: RuleEngine instance from src/rules/engine.py
        settings: Settings object with configuration (optional)

    Returns:
        None (registers conditions in-place)

    Example:
        >>> from src.rules.engine import RuleEngine
        >>> from src.rules.conditions import register_conditions
        >>> engine = RuleEngine('config/rules.yaml')
        >>> register_conditions(engine, settings)
        # Now evaluators are available for use in rules

    Registered Evaluators:
        - booking_not_in_db: True if booking is new (not in DynamoDB)
        - time_before_booking: True if within X hours of booking
        - flag_not_set: True if SMS flag not sent
        - current_hour: True if current hour matches
        - booking_status: True if booking status matches code
        - has_option_keyword: True if booking has option keywords
        - has_multiple_options: True if booking has minimum matching option keywords
        - date_range: True if booking falls within date range
        - has_pro_edit_option: True if booking has professional edit option

    Reference:
        Integration pattern: docs/brownfield-architecture.md:1070-1145
    """
    engine.register_condition("booking_not_in_db", booking_not_in_db)
    engine.register_condition("time_before_booking", time_before_booking)
    engine.register_condition("flag_not_set", flag_not_set)
    engine.register_condition("current_hour", current_hour)
    engine.register_condition("booking_status", booking_status)
    engine.register_condition("has_option_keyword", has_option_keyword)
    engine.register_condition("has_multiple_options", has_multiple_options)
    engine.register_condition("date_range", date_range)
    engine.register_condition("has_pro_edit_option", has_pro_edit_option)

    logger.info(
        "Registered 9 condition evaluators with RuleEngine: "
        "booking_not_in_db, time_before_booking, flag_not_set, "
        "current_hour, booking_status, has_option_keyword, "
        "has_multiple_options, date_range, has_pro_edit_option"
    )


def has_pro_edit_option(context: Dict[str, Any], **params) -> bool:
    """
    Evaluate if the booking has the professional edit option.

    Args:
        context: Dictionary containing:
            - booking: Booking object with has_pro_edit_option attribute
        **params: Additional parameters (unused)

    Returns:
        bool: True if booking.has_pro_edit_option is True, False otherwise
    """
    try:
        booking = context.get("booking")

        if not booking:
            logger.debug("has_pro_edit_option: Missing booking")
            return False

        has_option = getattr(booking, "has_pro_edit_option", False)
        result = has_option is True

        logger.debug(
            f"has_pro_edit_option: booking.has_pro_edit_option={has_option}, result={result}"
        )
        return result

    except Exception as e:
        logger.error(f"has_pro_edit_option error: {e}", exc_info=True)
        return False
