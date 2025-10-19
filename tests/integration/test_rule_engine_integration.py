"""
Integration Tests for Rule Engine

Tests end-to-end rule processing with realistic scenarios.

AC11: Integration tests validate end-to-end rule execution
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.rules.engine import RuleEngine
from src.rules.context import build_context


class TestRealWorldRuleScenarios:
    """Test realistic rule engine scenarios matching business requirements"""

    @pytest.fixture
    def realistic_rules(self, tmp_path):
        """Create realistic rules matching current system behavior"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "New Booking Confirmation"
    description: "Send confirmation SMS to new bookings"
    enabled: true
    conditions:
      - type: "booking_not_in_db"
    actions:
      - type: "create_db_record"
      - type: "send_sms"
        params:
          template: "confirmation"

  - name: "Two Hour Reminder"
    description: "Send guide SMS 2 hours before reservation"
    enabled: true
    conditions:
      - type: "time_before_booking"
        params:
          hours: 2
      - type: "flag_not_set"
        params:
          flag: "remind_sms"
    actions:
      - type: "send_sms"
        params:
          template: "guide"
      - type: "update_flag"
        params:
          flag: "remind_sms"

  - name: "Evening Event SMS"
    description: "Send event SMS at 8 PM for completed bookings with options"
    enabled: true
    conditions:
      - type: "current_hour"
        params:
          hour: 20
      - type: "booking_status"
        params:
          status: "RC08"
      - type: "flag_not_set"
        params:
          flag: "option_sms"
      - type: "has_option_keyword"
    actions:
      - type: "send_sms"
        params:
          template: "event"
      - type: "update_flag"
        params:
          flag: "option_sms"
"""
        )
        return rules_file

    def test_new_booking_flow(self, realistic_rules):
        """Test complete new booking flow"""
        engine = RuleEngine(str(realistic_rules))

        # Setup condition evaluators
        engine.register_condition(
            "booking_not_in_db", lambda ctx, **p: ctx["db_record"] is None
        )
        engine.register_condition(
            "time_before_booking", lambda ctx, hours, **p: True
        )  # Won't match for new bookings
        engine.register_condition("current_hour", lambda ctx, hour, **p: False)
        engine.register_condition("booking_status", lambda ctx, status, **p: False)
        engine.register_condition("flag_not_set", lambda ctx, flag, **p: False)
        engine.register_condition("has_option_keyword", lambda ctx, **p: False)

        # Setup action executors
        db_record_created = []
        sms_sent = []

        def create_db_record(ctx, **p):
            db_record_created.append(ctx["booking"])

        def send_sms(ctx, template, **p):
            sms_sent.append({"template": template, "booking": ctx["booking"]})

        def update_flag(ctx, flag, **p):
            pass

        engine.register_action("create_db_record", create_db_record)
        engine.register_action("send_sms", send_sms)
        engine.register_action("update_flag", update_flag)

        # Create booking context (new booking - no DB record)
        booking = Mock()
        booking.id = "123"
        booking.phone = "010-1234-5678"

        context = build_context(
            booking=booking,
            db_record=None,  # New booking
            current_time=datetime.now(),
        )

        # Process through rules
        results = engine.process_booking(context)

        # Verify results
        assert len(results) == 2  # create_db_record + send_sms
        assert all(r.success for r in results)
        assert len(db_record_created) == 1
        assert len(sms_sent) == 1
        assert sms_sent[0]["template"] == "confirmation"

    def test_existing_booking_reminder_flow(self, realistic_rules):
        """Test existing booking reminder flow"""
        engine = RuleEngine(str(realistic_rules))

        # Setup conditions
        engine.register_condition(
            "booking_not_in_db", lambda ctx, **p: False
        )  # Existing booking

        def time_before_booking(ctx, hours, **p):
            # Booking is within the time window
            time_until = ctx["booking"].reserve_at - ctx["current_time"]
            return time_until <= timedelta(hours=hours)

        engine.register_condition("time_before_booking", time_before_booking)
        engine.register_condition("current_hour", lambda ctx, hour, **p: False)
        engine.register_condition("booking_status", lambda ctx, status, **p: False)

        def flag_not_set(ctx, flag, **p):
            # remind_sms flag is not set (False)
            return not ctx["db_record"].get(flag, False)

        engine.register_condition("flag_not_set", flag_not_set)
        engine.register_condition("has_option_keyword", lambda ctx, **p: False)

        # Setup actions
        actions_executed = []

        def send_sms(ctx, template, **p):
            actions_executed.append({"action": "send_sms", "template": template})

        def update_flag(ctx, flag, **p):
            actions_executed.append({"action": "update_flag", "flag": flag})

        engine.register_action("send_sms", send_sms)
        engine.register_action("update_flag", update_flag)
        engine.register_action("create_db_record", lambda ctx, **p: None)

        # Create existing booking within 2-hour window
        booking = Mock()
        booking.id = "456"
        booking.reserve_at = datetime.now() + timedelta(minutes=90)

        db_record = Mock()
        db_record.get = lambda key, default=None: {
            "remind_sms": False,
            "confirm_sms": True,
        }.get(key, default)

        context = build_context(
            booking=booking,
            db_record=db_record,
            current_time=datetime.now(),
        )

        # Process through rules
        results = engine.process_booking(context)

        # Should match "Two Hour Reminder" rule
        assert len(results) == 2  # send_sms + update_flag
        assert len(actions_executed) == 2
        assert actions_executed[0]["action"] == "send_sms"
        assert actions_executed[0]["template"] == "guide"
        assert actions_executed[1]["action"] == "update_flag"

    def test_evening_event_sms_flow(self, realistic_rules):
        """Test evening event SMS at 8 PM"""
        engine = RuleEngine(str(realistic_rules))

        # Setup conditions for 8 PM event
        engine.register_condition("booking_not_in_db", lambda ctx, **p: False)
        engine.register_condition("time_before_booking", lambda ctx, hours, **p: False)

        def current_hour(ctx, hour, **p):
            return ctx["current_time"].hour == hour

        engine.register_condition("current_hour", current_hour)

        def booking_status(ctx, status, **p):
            return ctx["booking"].status == status

        engine.register_condition("booking_status", booking_status)

        def flag_not_set(ctx, flag, **p):
            return not ctx["db_record"].get(flag, False)

        engine.register_condition("flag_not_set", flag_not_set)

        def has_option_keyword(ctx, **p):
            return ctx["booking"].option is True

        engine.register_condition("has_option_keyword", has_option_keyword)

        # Setup actions
        actions_taken = []

        def send_sms(ctx, template, **p):
            actions_taken.append(template)

        def update_flag(ctx, flag, **p):
            actions_taken.append(f"flag_{flag}")

        engine.register_action("send_sms", send_sms)
        engine.register_action("update_flag", update_flag)
        engine.register_action("create_db_record", lambda ctx, **p: None)

        # Create completed booking with option at 8 PM
        booking = Mock()
        booking.id = "789"
        booking.status = "RC08"  # Completed
        booking.option = True

        db_record = Mock()
        db_record.get = lambda key, default=None: {"option_sms": False}.get(
            key, default
        )

        # Create 8 PM context
        now_8pm = datetime.now().replace(hour=20, minute=0, second=0)

        context = build_context(
            booking=booking,
            db_record=db_record,
            current_time=now_8pm,
        )

        # Process through rules
        results = engine.process_booking(context)

        # Should match "Evening Event SMS" rule
        assert len(results) == 2  # send_sms + update_flag
        assert len(actions_taken) == 2
        assert actions_taken[0] == "event"
        assert actions_taken[1] == "flag_option_sms"

    def test_no_rules_match_scenario(self, realistic_rules):
        """Test scenario where no rules match"""
        engine = RuleEngine(str(realistic_rules))

        # Setup conditions - all fail
        engine.register_condition("booking_not_in_db", lambda ctx, **p: False)
        engine.register_condition(
            "time_before_booking", lambda ctx, hours, **p: False
        )  # Outside time window
        engine.register_condition(
            "current_hour", lambda ctx, hour, **p: False
        )  # Not 8 PM
        engine.register_condition("booking_status", lambda ctx, status, **p: False)
        engine.register_condition("flag_not_set", lambda ctx, flag, **p: False)
        engine.register_condition("has_option_keyword", lambda ctx, **p: False)

        # Setup dummy actions
        engine.register_action("send_sms", lambda ctx, **p: None)
        engine.register_action("update_flag", lambda ctx, **p: None)
        engine.register_action("create_db_record", lambda ctx, **p: None)

        # Create booking that matches nothing
        booking = Mock()
        booking.id = "999"
        booking.reserve_at = datetime.now() + timedelta(days=10)  # Far future

        db_record = Mock()
        db_record.get = lambda key, default=None: True  # All flags already set

        context = build_context(
            booking=booking,
            db_record=db_record,
            current_time=datetime.now(),
        )

        # Process through rules
        results = engine.process_booking(context)

        # No rules should match
        assert len(results) == 0

    def test_multiple_rules_match_same_booking(self, tmp_path):
        """Test scenario where multiple rules match the same booking"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Rule A"
    enabled: true
    conditions:
      - type: "is_new_booking"
    actions:
      - type: "action_a"
  - name: "Rule B"
    enabled: true
    conditions:
      - type: "is_new_booking"
    actions:
      - type: "action_b"
"""
        )

        engine = RuleEngine(str(rules_file))

        # Both rules match
        engine.register_condition("is_new_booking", lambda ctx, **p: True)

        actions = []
        engine.register_action("action_a", lambda ctx, **p: actions.append("a"))
        engine.register_action("action_b", lambda ctx, **p: actions.append("b"))

        context = {}
        results = engine.process_booking(context)

        # Both rules execute
        assert len(results) == 2
        assert "a" in actions
        assert "b" in actions

    def test_error_recovery_flow(self, tmp_path):
        """Test that errors in one rule don't prevent others from executing"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Rule 1"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "failing_action"
  - name: "Rule 2"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "working_action"
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)

        def failing_action(ctx, **p):
            raise RuntimeError("This action fails")

        def working_action(ctx, **p):
            ctx["worked"] = True

        engine.register_action("failing_action", failing_action)
        engine.register_action("working_action", working_action)

        context = {}
        results = engine.process_booking(context)

        # Both rules should have results
        assert len(results) == 2
        # First action failed
        assert results[0].success is False
        # Second action succeeded
        assert results[1].success is True
        # Context was modified by working_action
        assert context.get("worked") is True

    def test_rule_ordering_matters(self, tmp_path):
        """Test that rules execute in the order they are defined"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "First Rule"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "action_1"
  - name: "Second Rule"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "action_2"
  - name: "Third Rule"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "action_3"
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)

        execution_order = []
        engine.register_action("action_1", lambda ctx, **p: execution_order.append(1))
        engine.register_action("action_2", lambda ctx, **p: execution_order.append(2))
        engine.register_action("action_3", lambda ctx, **p: execution_order.append(3))

        context = {}
        engine.process_booking(context)

        # Verify execution order
        assert execution_order == [1, 2, 3]

    def test_context_builder_integration(self):
        """Test context builder with rule engine"""
        booking = Mock()
        booking.id = "123"
        booking.phone = "010-1234-5678"

        db_record = {"confirm_sms": True}
        settings = Mock()
        db_client = Mock()

        context = build_context(
            booking=booking,
            db_record=db_record,
            current_time=datetime.now(),
            settings=settings,
            db_client=db_client,
        )

        # Verify context has all required fields
        assert context["booking"] == booking
        assert context["db_record"] == db_record
        assert "current_time" in context
        assert context["settings"] == settings
        assert context["db_client"] == db_client

    def test_disabled_rule_never_executes(self, tmp_path):
        """Test that disabled rules never execute"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Enabled Rule"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "action_1"
  - name: "Disabled Rule"
    enabled: false
    conditions:
      - type: "always_true"
    actions:
      - type: "action_2"
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)

        actions_executed = []
        engine.register_action("action_1", lambda ctx, **p: actions_executed.append(1))
        engine.register_action("action_2", lambda ctx, **p: actions_executed.append(2))

        context = {}
        results = engine.process_booking(context)

        # Only enabled rule executes
        assert len(results) == 1
        assert results[0].rule_name == "Enabled Rule"
        assert actions_executed == [1]

    def test_complex_condition_logic(self, tmp_path):
        """Test complex conditions with multiple AND logic"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Complex Rule"
    enabled: true
    conditions:
      - type: "cond_a"
      - type: "cond_b"
      - type: "cond_c"
      - type: "cond_d"
    actions:
      - type: "action"
"""
        )

        engine = RuleEngine(str(rules_file))

        # Test: All conditions pass
        engine.register_condition("cond_a", lambda ctx, **p: ctx.get("a") is True)
        engine.register_condition("cond_b", lambda ctx, **p: ctx.get("b") is True)
        engine.register_condition("cond_c", lambda ctx, **p: ctx.get("c") is True)
        engine.register_condition("cond_d", lambda ctx, **p: ctx.get("d") is True)

        actions = []
        engine.register_action("action", lambda ctx, **p: actions.append("executed"))

        # All conditions true - rule should match
        context = {"a": True, "b": True, "c": True, "d": True}
        results = engine.process_booking(context)
        assert len(results) == 1
        assert results[0].success is True

        # One condition false - rule should not match
        actions.clear()
        context = {"a": True, "b": False, "c": True, "d": True}
        results = engine.process_booking(context)
        assert len(results) == 0
        assert len(actions) == 0

    def test_action_parameters_passed_correctly(self, tmp_path):
        """Test that action parameters are passed correctly"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Param Test"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "parameterized_action"
        params:
          template: "confirmation"
          store_id: "1051707"
          retry: 3
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)

        received_params = []

        def parameterized_action(ctx, **params):
            received_params.append(params)

        engine.register_action("parameterized_action", parameterized_action)

        context = {}
        results = engine.process_booking(context)

        assert len(results) == 1
        assert results[0].success is True
        assert received_params[0] == {
            "template": "confirmation",
            "store_id": "1051707",
            "retry": 3,
        }
