"""
Timezone utilities for the Naver SMS automation project.

Provides helpers to obtain the current time in Korea Standard Time (KST)
so that rule evaluation remains consistent when code runs in environments
with different default timezones (e.g., AWS Lambda uses UTC).
"""

from datetime import datetime, timedelta, timezone

# Reusable timezone instance for KST (UTC+9)
KST = timezone(timedelta(hours=9))


def now_kst(aware: bool = False) -> datetime:
    """
    Return the current time in Korea Standard Time (KST).

    Args:
        aware: When True, returns a timezone-aware datetime. When False (default),
            returns a naive datetime stripped of tzinfo to match existing Booking.reserve_at values.

    Returns:
        datetime: Current time in KST.
    """
    current = datetime.now(timezone.utc).astimezone(KST)
    return current if aware else current.replace(tzinfo=None)
