"""
Rule engine evaluation tests focused on original flag/SMS sequencing.
"""

from datetime import datetime
from pathlib import Path

from src.rules.engine import RuleEngine
from src.rules.conditions import register_conditions
from src.rules.context import build_context
from src.domain.booking import Booking


def _load_rule(engine: RuleEngine, name: str):
    return next(rule for rule in engine.rules if rule.name == name)


def test_new_booking_within_two_hours_triggers_confirm_and_reminder():
    """
    Mirrors legacy logic: a brand-new booking inside the 2-hour window
    must send both confirmation and reminder SMS messages.
    """
    project_root = Path(__file__).resolve().parents[2]
    rules_path = project_root / "config" / "rules.yaml"
    engine = RuleEngine(str(rules_path))
    register_conditions(engine)

    booking = Booking(
        booking_num="1051707_9999",
        phone="010-1234-5678",
        name="테스트 고객",
        booking_time="2025-11-01 02:00:00",
        confirm_sms=False,
        remind_sms=False,
        option_sms=False,
        reserve_at=datetime(2025, 11, 1, 2, 0, 0),
        biz_id="1051707",
    )

    context = build_context(
        booking=booking,
        db_record=None,
        current_time=datetime(2025, 11, 1, 1, 39, 0),
        settings=None,
        db_client=None,
    )

    confirm_rule = _load_rule(engine, "New Booking Confirmation")
    reminder_rule = _load_rule(engine, "Two-Hour Reminder")

    assert engine.evaluate_rule(confirm_rule, context) is True
    assert engine.evaluate_rule(reminder_rule, context) is True
