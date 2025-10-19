"""
Unit Tests for Rule Engine Core

Tests cover:
- AC1: Rule loading from YAML
- AC2: Rule schema validation
- AC3: Condition evaluation with AND logic
- AC4: Action execution in sequence
- AC5: Error handling
- AC6: Registry system
- AC8: Structured results
- AC10: >80% test coverage
"""

import pytest
from unittest.mock import Mock

from src.rules.engine import (
    RuleEngine,
    ActionResult,
)


class TestRuleLoading:
    """AC1: Rule loading from YAML files"""

    def test_load_rules_from_valid_yaml(self, tmp_path):
        """Test loading valid rules from YAML file"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    description: "Test description"
    conditions:
      - type: "test_condition"
        params:
          value: 42
    actions:
      - type: "test_action"
        params:
          message: "hello"
"""
        )

        engine = RuleEngine(str(rules_file))

        assert len(engine.rules) == 1
        assert engine.rules[0].name == "Test Rule"
        assert engine.rules[0].enabled is True
        assert engine.rules[0].description == "Test description"
        assert len(engine.rules[0].conditions) == 1
        assert engine.rules[0].conditions[0].type == "test_condition"
        assert engine.rules[0].conditions[0].params == {"value": 42}

    def test_load_multiple_rules(self, tmp_path):
        """Test loading multiple rules"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Rule 1"
    enabled: true
    conditions:
      - type: "cond1"
    actions:
      - type: "action1"
  - name: "Rule 2"
    enabled: false
    conditions:
      - type: "cond2"
    actions:
      - type: "action2"
"""
        )

        engine = RuleEngine(str(rules_file))
        assert len(engine.rules) == 2
        assert engine.rules[0].name == "Rule 1"
        assert engine.rules[1].name == "Rule 2"
        assert engine.rules[1].enabled is False

    def test_load_rules_file_not_found(self):
        """Test error when rules file doesn't exist"""
        with pytest.raises(FileNotFoundError):
            RuleEngine("/nonexistent/path/rules.yaml")

    def test_load_rules_invalid_yaml(self, tmp_path):
        """Test error on invalid YAML syntax"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: Test
    invalid: [unclosed bracket
"""
        )

        with pytest.raises(ValueError, match="Invalid YAML"):
            RuleEngine(str(rules_file))

    def test_load_rules_empty_file(self, tmp_path):
        """Test handling empty YAML file"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("")

        engine = RuleEngine(str(rules_file))
        assert len(engine.rules) == 0

    def test_load_rules_no_rules_key(self, tmp_path):
        """Test handling YAML with no 'rules' key"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
version: 1
description: "Config without rules"
"""
        )

        engine = RuleEngine(str(rules_file))
        assert len(engine.rules) == 0


class TestRuleValidation:
    """AC2: Rule schema validation"""

    def test_rule_missing_name(self, tmp_path):
        """Test validation of missing rule name"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - enabled: true
    conditions: []
    actions: []
"""
        )

        with pytest.raises(ValueError, match="missing required field: 'name'"):
            RuleEngine(str(rules_file))

    def test_rule_missing_conditions(self, tmp_path):
        """Test validation of missing conditions"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Bad Rule"
    enabled: true
    actions: []
"""
        )

        with pytest.raises(ValueError, match="missing required field: 'conditions'"):
            RuleEngine(str(rules_file))

    def test_rule_missing_actions(self, tmp_path):
        """Test validation of missing actions"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Bad Rule"
    enabled: true
    conditions: []
"""
        )

        with pytest.raises(ValueError, match="missing required field: 'actions'"):
            RuleEngine(str(rules_file))

    def test_rule_conditions_not_list(self, tmp_path):
        """Test validation when conditions is not a list"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Bad Rule"
    enabled: true
    conditions: "not a list"
    actions: []
"""
        )

        with pytest.raises(ValueError, match="'conditions' must be a list"):
            RuleEngine(str(rules_file))

    def test_rule_actions_not_list(self, tmp_path):
        """Test validation when actions is not a list"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Bad Rule"
    enabled: true
    conditions: []
    actions: "not a list"
"""
        )

        with pytest.raises(ValueError, match="'actions' must be a list"):
            RuleEngine(str(rules_file))

    def test_condition_missing_type(self, tmp_path):
        """Test validation when condition missing type"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Bad Rule"
    enabled: true
    conditions:
      - params:
          value: 1
    actions: []
"""
        )

        with pytest.raises(ValueError, match="condition.*missing 'type' field"):
            RuleEngine(str(rules_file))

    def test_action_missing_type(self, tmp_path):
        """Test validation when action missing type"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Bad Rule"
    enabled: true
    conditions: []
    actions:
      - params:
          value: 1
"""
        )

        with pytest.raises(ValueError, match="action.*missing 'type' field"):
            RuleEngine(str(rules_file))


class TestRegistry:
    """AC6: Condition and action registries"""

    def test_register_condition(self, tmp_path):
        """Test registering a condition evaluator"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("rules: []")

        engine = RuleEngine(str(rules_file))

        def test_condition(context, **params):
            return True

        engine.register_condition("test_cond", test_condition)
        assert "test_cond" in engine.condition_evaluators
        assert engine.condition_evaluators["test_cond"] == test_condition

    def test_register_action(self, tmp_path):
        """Test registering an action executor"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("rules: []")

        engine = RuleEngine(str(rules_file))

        def test_action(context, **params):
            pass

        engine.register_action("test_action", test_action)
        assert "test_action" in engine.action_executors
        assert engine.action_executors["test_action"] == test_action

    def test_register_non_callable_condition(self, tmp_path):
        """Test error when registering non-callable condition"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("rules: []")

        engine = RuleEngine(str(rules_file))

        with pytest.raises(TypeError, match="must be callable"):
            engine.register_condition("bad", "not callable")

    def test_register_non_callable_action(self, tmp_path):
        """Test error when registering non-callable action"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("rules: []")

        engine = RuleEngine(str(rules_file))

        with pytest.raises(TypeError, match="must be callable"):
            engine.register_action("bad", 123)


class TestConditionEvaluation:
    """AC3: Condition evaluation with AND logic"""

    def test_evaluate_rule_single_condition_pass(self, tmp_path):
        """Test rule evaluation when single condition passes"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "always_true"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)

        context = {"booking": Mock()}
        assert engine.evaluate_rule(engine.rules[0], context) is True

    def test_evaluate_rule_single_condition_fail(self, tmp_path):
        """Test rule evaluation when single condition fails"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "always_false"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_false", lambda ctx, **p: False)

        context = {"booking": Mock()}
        assert engine.evaluate_rule(engine.rules[0], context) is False

    def test_evaluate_rule_multiple_conditions_all_pass(self, tmp_path):
        """Test AND logic when all conditions pass"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "cond1"
      - type: "cond2"
      - type: "cond3"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("cond1", lambda ctx, **p: True)
        engine.register_condition("cond2", lambda ctx, **p: True)
        engine.register_condition("cond3", lambda ctx, **p: True)

        context = {"booking": Mock()}
        assert engine.evaluate_rule(engine.rules[0], context) is True

    def test_evaluate_rule_multiple_conditions_one_fails(self, tmp_path):
        """Test AND logic when one condition fails"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "cond1"
      - type: "cond2"
      - type: "cond3"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("cond1", lambda ctx, **p: True)
        engine.register_condition("cond2", lambda ctx, **p: False)
        engine.register_condition("cond3", lambda ctx, **p: True)

        context = {"booking": Mock()}
        assert engine.evaluate_rule(engine.rules[0], context) is False

    def test_evaluate_rule_disabled(self, tmp_path):
        """Test that disabled rules never match"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Disabled Rule"
    enabled: false
    conditions:
      - type: "always_true"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)

        context = {"booking": Mock()}
        assert engine.evaluate_rule(engine.rules[0], context) is False

    def test_evaluate_rule_unknown_condition_type(self, tmp_path):
        """Test error when condition type not registered"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "unknown_condition"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))

        context = {"booking": Mock()}
        assert engine.evaluate_rule(engine.rules[0], context) is False

    def test_evaluate_rule_condition_raises_exception(self, tmp_path):
        """AC5: Test error handling when condition raises exception"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "error_condition"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))

        def error_condition(ctx, **p):
            raise RuntimeError("Condition error")

        engine.register_condition("error_condition", error_condition)

        context = {"booking": Mock()}
        assert engine.evaluate_rule(engine.rules[0], context) is False

    def test_evaluate_rule_with_params(self, tmp_path):
        """Test condition evaluation with parameters"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "param_check"
        params:
          expected: 42
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))

        def param_check(ctx, expected, **p):
            return ctx.get("value") == expected

        engine.register_condition("param_check", param_check)

        context = {"value": 42}
        assert engine.evaluate_rule(engine.rules[0], context) is True

        context = {"value": 99}
        assert engine.evaluate_rule(engine.rules[0], context) is False

    def test_evaluate_rule_short_circuit_evaluation(self, tmp_path):
        """Test that evaluation stops at first failing condition"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "cond1"
      - type: "cond2"
      - type: "cond3"
    actions: []
"""
        )

        engine = RuleEngine(str(rules_file))

        call_count = {}
        call_count["cond1"] = 0
        call_count["cond2"] = 0
        call_count["cond3"] = 0

        def cond1(ctx, **p):
            call_count["cond1"] += 1
            return True

        def cond2(ctx, **p):
            call_count["cond2"] += 1
            return False

        def cond3(ctx, **p):
            call_count["cond3"] += 1
            return True

        engine.register_condition("cond1", cond1)
        engine.register_condition("cond2", cond2)
        engine.register_condition("cond3", cond3)

        context = {"booking": Mock()}
        engine.evaluate_rule(engine.rules[0], context)

        # cond3 should not be called since cond2 failed
        assert call_count["cond1"] == 1
        assert call_count["cond2"] == 1
        assert call_count["cond3"] == 0


class TestActionExecution:
    """AC4: Action execution in sequence"""

    def test_execute_rule_single_action(self, tmp_path):
        """Test executing single action"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions: []
    actions:
      - type: "test_action"
        params:
          key: "value"
"""
        )

        engine = RuleEngine(str(rules_file))

        executed = []

        def test_action(ctx, **params):
            executed.append(params)

        engine.register_action("test_action", test_action)

        context = {"booking": Mock()}
        results = engine.execute_rule(engine.rules[0], context)

        assert len(executed) == 1
        assert executed[0] == {"key": "value"}
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].action_type == "test_action"

    def test_execute_rule_multiple_actions_sequence(self, tmp_path):
        """Test actions execute in order"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions: []
    actions:
      - type: "action1"
      - type: "action2"
      - type: "action3"
"""
        )

        engine = RuleEngine(str(rules_file))

        execution_order = []

        def action1(ctx, **p):
            execution_order.append(1)

        def action2(ctx, **p):
            execution_order.append(2)

        def action3(ctx, **p):
            execution_order.append(3)

        engine.register_action("action1", action1)
        engine.register_action("action2", action2)
        engine.register_action("action3", action3)

        context = {}
        engine.execute_rule(engine.rules[0], context)

        assert execution_order == [1, 2, 3]

    def test_execute_rule_unknown_action_type(self, tmp_path):
        """Test handling unknown action type"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions: []
    actions:
      - type: "unknown_action"
"""
        )

        engine = RuleEngine(str(rules_file))

        context = {}
        results = engine.execute_rule(engine.rules[0], context)

        assert len(results) == 1
        assert results[0].success is False
        assert "unknown_action" in results[0].error

    def test_execute_rule_action_raises_exception(self, tmp_path):
        """AC5: Test error handling when action raises exception"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions: []
    actions:
      - type: "error_action"
      - type: "next_action"
"""
        )

        engine = RuleEngine(str(rules_file))

        def error_action(ctx, **p):
            raise RuntimeError("Action failed")

        def next_action(ctx, **p):
            ctx["executed"] = True

        engine.register_action("error_action", error_action)
        engine.register_action("next_action", next_action)

        context = {}
        results = engine.execute_rule(engine.rules[0], context)

        # Both actions should have results
        assert len(results) == 2
        # First action failed
        assert results[0].success is False
        # Second action still executed (AC5: continue to next action)
        assert results[1].success is True
        assert context["executed"] is True


class TestResultTracking:
    """AC8: Structured result tracking"""

    def test_action_result_success(self, tmp_path):
        """Test successful action result structure"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions: []
    actions:
      - type: "test_action"
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_action("test_action", lambda ctx, **p: None)

        context = {}
        results = engine.execute_rule(engine.rules[0], context)

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, ActionResult)
        assert result.rule_name == "Test Rule"
        assert result.action_type == "test_action"
        assert result.success is True
        assert result.error is None
        assert "successfully" in result.message

    def test_action_result_failure(self, tmp_path):
        """Test failed action result structure"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions: []
    actions:
      - type: "error_action"
"""
        )

        engine = RuleEngine(str(rules_file))

        def error_action(ctx, **p):
            raise ValueError("Test error")

        engine.register_action("error_action", error_action)

        context = {}
        results = engine.execute_rule(engine.rules[0], context)

        assert len(results) == 1
        result = results[0]
        assert result.success is False
        assert "Test error" in result.error

    def test_process_booking_collects_all_results(self, tmp_path):
        """Test that all matched rules' results are collected"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Rule 1"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "action1"
  - name: "Rule 2"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "action2"
      - type: "action3"
  - name: "Rule 3"
    enabled: true
    conditions:
      - type: "always_false"
    actions:
      - type: "action4"
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)
        engine.register_condition("always_false", lambda ctx, **p: False)
        engine.register_action("action1", lambda ctx, **p: None)
        engine.register_action("action2", lambda ctx, **p: None)
        engine.register_action("action3", lambda ctx, **p: None)
        engine.register_action("action4", lambda ctx, **p: None)

        context = {}
        results = engine.process_booking(context)

        # Rule 1 has 1 action, Rule 2 has 2 actions, Rule 3 didn't match
        assert len(results) == 3
        assert results[0].rule_name == "Rule 1"
        assert results[1].rule_name == "Rule 2"
        assert results[2].rule_name == "Rule 2"


class TestProcessBooking:
    """Integration tests for process_booking entry point"""

    def test_process_booking_no_matched_rules(self, tmp_path):
        """Test processing when no rules match"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Rule 1"
    enabled: true
    conditions:
      - type: "always_false"
    actions:
      - type: "action1"
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_false", lambda ctx, **p: False)
        engine.register_action("action1", lambda ctx, **p: None)

        context = {}
        results = engine.process_booking(context)

        assert len(results) == 0

    def test_process_booking_multiple_matched_rules(self, tmp_path):
        """Test processing with multiple matching rules"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Rule A"
    enabled: true
    conditions:
      - type: "check_booking"
    actions:
      - type: "action_a"
  - name: "Rule B"
    enabled: true
    conditions:
      - type: "check_booking"
    actions:
      - type: "action_b"
"""
        )

        engine = RuleEngine(str(rules_file))
        engine.register_condition("check_booking", lambda ctx, **p: True)
        engine.register_action("action_a", lambda ctx, **p: None)
        engine.register_action("action_b", lambda ctx, **p: None)

        context = {"booking_id": 123}
        results = engine.process_booking(context)

        assert len(results) == 2
        assert any(r.rule_name == "Rule A" for r in results)
        assert any(r.rule_name == "Rule B" for r in results)

    def test_process_booking_handles_rule_exception(self, tmp_path):
        """AC5: Test that exception in one rule doesn't stop others"""
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Rule 1"
    enabled: true
    conditions:
      - type: "bad_condition"
    actions:
      - type: "action1"
  - name: "Rule 2"
    enabled: true
    conditions:
      - type: "good_condition"
    actions:
      - type: "action2"
"""
        )

        engine = RuleEngine(str(rules_file))

        def bad_condition(ctx, **p):
            raise RuntimeError("Unexpected error")

        engine.register_condition("bad_condition", bad_condition)
        engine.register_condition("good_condition", lambda ctx, **p: True)
        engine.register_action("action1", lambda ctx, **p: None)
        engine.register_action("action2", lambda ctx, **p: None)

        context = {}
        results = engine.process_booking(context)

        # Rule 2 should still execute
        assert len(results) == 1
        assert results[0].rule_name == "Rule 2"
