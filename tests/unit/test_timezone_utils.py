"""
Unit tests for timezone utility helpers.
"""

from datetime import timezone, timedelta

from src.utils.timezone import now_kst, KST


def test_now_kst_returns_naive_by_default():
    """Default call should return naive datetime for compatibility."""
    current = now_kst()
    assert current.tzinfo is None


def test_now_kst_returns_timezone_aware_when_requested():
    """When aware=True, the result retains the KST timezone info."""
    current = now_kst(aware=True)
    assert current.tzinfo == KST
    # Confirm offset is +9 hours relative to UTC for clarity
    assert current.utcoffset() == timedelta(hours=9)
