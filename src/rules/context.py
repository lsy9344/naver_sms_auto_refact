"""
Context Builder for Rule Engine

Provides utilities to build evaluation contexts for rule processing.
Contexts contain all data needed for condition evaluation and action execution.

AC7: Context object provides all data needed for evaluation
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

from src.utils.timezone import now_kst

logger = logging.getLogger(__name__)


def build_context(
    booking: Any,
    db_record: Optional[Any],
    current_time: Optional[datetime] = None,
    settings: Optional[Any] = None,
    db_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build context object for rule evaluation.

    Assembles all data needed for condition evaluation and action execution
    into a single context dictionary.

    Args:
        booking: Booking domain object with attributes (id, phone, biz_id, reserve_at, option, etc.)
        db_record: DynamoDB booking record (None if new booking)
        current_time: Current datetime for evaluation (defaults to now)
        settings: Application settings object
        db_client: DynamoDB client for action execution

    Returns:
        Dict with all data needed for rule evaluation:
        - booking: The booking object
        - db_record: The DynamoDB record (or None)
        - current_time: Current datetime for time-based conditions
        - settings: Application settings
        - db_client: DynamoDB client for actions

    Example:
        >>> context = build_context(booking, db_record, now_kst(), settings, db_client)
        >>> rule_results = engine.process_booking(context)
    """
    if current_time is None:
        current_time = now_kst()

    context = {
        "booking": booking,
        "db_record": db_record,
        "current_time": current_time,
        "settings": settings,
        "db_client": db_client,
    }

    logger.debug(f"Built context for booking: {getattr(booking, 'id', 'unknown')}")
    return context
