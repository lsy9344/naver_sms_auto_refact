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

from typing import Any, Dict, Optional
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

        # Get configured keyword list from settings
        if settings:
            keyword_list = getattr(settings, "option_keywords", [])
        else:
            # Default keyword list matching legacy behavior
            keyword_list = ["네이버", "인스타", "원본"]

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

    Reference:
        Integration pattern: docs/brownfield-architecture.md:1070-1145
    """
    engine.register_condition("booking_not_in_db", booking_not_in_db)
    engine.register_condition("time_before_booking", time_before_booking)
    engine.register_condition("flag_not_set", flag_not_set)
    engine.register_condition("current_hour", current_hour)
    engine.register_condition("booking_status", booking_status)
    engine.register_condition("has_option_keyword", has_option_keyword)

    logger.info(
        "Registered 6 condition evaluators with RuleEngine: "
        "booking_not_in_db, time_before_booking, flag_not_set, "
        "current_hour, booking_status, has_option_keyword"
    )
