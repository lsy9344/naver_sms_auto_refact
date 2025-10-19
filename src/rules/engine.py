"""
Rule Engine Core Module

Implements a flexible, extensible rule engine that:
- Loads and validates rules from YAML configuration
- Provides pluggable condition/action registry system
- Evaluates conditions with AND logic
- Executes actions with error handling
- Returns structured results

Acceptance Criteria Coverage:
- AC1: Loads rules from config/rules.yaml
- AC2: Validates rule schema on load
- AC3: Evaluates all conditions with AND logic
- AC4: Executes all actions in sequence
- AC5: Error handling (log and continue)
- AC6: Registries for dynamic extension
- AC7: Context provides all data for evaluation
- AC8: Returns structured results
- AC9: Performance <100ms per rule
"""

from dataclasses import dataclass, field
from typing import List, Dict, Callable, Any, Optional
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConditionConfig:
    """Configuration for a single condition."""

    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionConfig:
    """Configuration for a single action."""

    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleConfig:
    """Configuration for a complete rule."""

    name: str
    enabled: bool
    conditions: List[ConditionConfig]
    actions: List[ActionConfig]
    description: Optional[str] = None


@dataclass
class ActionResult:
    """Result of executing an action."""

    rule_name: str
    action_type: str
    success: bool
    message: str
    error: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)


class RuleEngine:
    """
    Core rule engine that evaluates conditions and executes actions.

    Features:
    - Loads rules from YAML configuration
    - Pluggable condition and action registries
    - AND logic for condition evaluation
    - Sequential action execution
    - Graceful error handling
    - Structured result tracking
    """

    def __init__(self, rules_config_path: str):
        """
        Initialize rule engine and load rules.

        Args:
            rules_config_path: Path to rules.yaml configuration file

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If rule schema is invalid
        """
        self.rules: List[RuleConfig] = []
        self.condition_evaluators: Dict[str, Callable] = {}
        self.action_executors: Dict[str, Callable] = {}
        self.load_rules(rules_config_path)

    def load_rules(self, config_path: str) -> None:
        """
        Load rules from YAML configuration file.

        Args:
            config_path: Path to rules.yaml

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If rule schema is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Rules configuration file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in rules configuration: {e}")
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

        if not config or "rules" not in config:
            logger.warning(f"No rules found in configuration: {config_path}")
            return

        # Parse and validate each rule
        for rule_idx, rule_data in enumerate(config.get("rules", [])):
            try:
                rule = self._parse_rule(rule_data)
                self.rules.append(rule)
                logger.debug(f"Loaded rule [{rule_idx}]: {rule.name}")
            except ValueError as e:
                logger.error(f"Failed to parse rule [{rule_idx}]: {e}")
                raise

        logger.info(f"Successfully loaded {len(self.rules)} rules from {config_path}")

    def _parse_rule(self, rule_data: Dict[str, Any]) -> RuleConfig:
        """
        Parse and validate a single rule from YAML data.

        Args:
            rule_data: Dictionary from YAML

        Returns:
            RuleConfig object

        Raises:
            ValueError: If rule schema is invalid
        """
        # Validate required fields
        if "name" not in rule_data:
            raise ValueError("Rule missing required field: 'name'")
        if "conditions" not in rule_data:
            raise ValueError(
                f"Rule '{rule_data['name']}' missing required field: 'conditions'"
            )
        if "actions" not in rule_data:
            raise ValueError(
                f"Rule '{rule_data['name']}' missing required field: 'actions'"
            )

        name = rule_data["name"]

        # Validate conditions is a list
        if not isinstance(rule_data["conditions"], list):
            raise ValueError(f"Rule '{name}': 'conditions' must be a list")

        # Validate actions is a list
        if not isinstance(rule_data["actions"], list):
            raise ValueError(f"Rule '{name}': 'actions' must be a list")

        # Parse conditions
        conditions = []
        for cond_idx, cond_data in enumerate(rule_data["conditions"]):
            if not isinstance(cond_data, dict):
                raise ValueError(
                    f"Rule '{name}': condition [{cond_idx}] must be a dictionary"
                )
            if "type" not in cond_data:
                raise ValueError(
                    f"Rule '{name}': condition [{cond_idx}] missing 'type' field"
                )

            conditions.append(
                ConditionConfig(
                    type=cond_data["type"],
                    params=cond_data.get("params", {}),
                )
            )

        # Parse actions
        actions = []
        for action_idx, action_data in enumerate(rule_data["actions"]):
            if not isinstance(action_data, dict):
                raise ValueError(
                    f"Rule '{name}': action [{action_idx}] must be a dictionary"
                )
            if "type" not in action_data:
                raise ValueError(
                    f"Rule '{name}': action [{action_idx}] missing 'type' field"
                )

            actions.append(
                ActionConfig(
                    type=action_data["type"],
                    params=action_data.get("params", {}),
                )
            )

        return RuleConfig(
            name=name,
            enabled=rule_data.get("enabled", True),
            conditions=conditions,
            actions=actions,
            description=rule_data.get("description"),
        )

    def register_condition(self, name: str, evaluator: Callable) -> None:
        """
        Register a condition evaluator function.

        Args:
            name: Condition type name (e.g., "booking_not_in_db")
            evaluator: Callable that takes (context, **params) -> bool

        Raises:
            TypeError: If evaluator is not callable
        """
        if not callable(evaluator):
            raise TypeError(
                f"Condition evaluator must be callable, got {type(evaluator)}"
            )

        self.condition_evaluators[name] = evaluator
        logger.debug(f"Registered condition evaluator: {name}")

    def register_action(self, name: str, executor: Callable) -> None:
        """
        Register an action executor function.

        Args:
            name: Action type name (e.g., "send_sms")
            executor: Callable that takes (context, **params) -> None

        Raises:
            TypeError: If executor is not callable
        """
        if not callable(executor):
            raise TypeError(f"Action executor must be callable, got {type(executor)}")

        self.action_executors[name] = executor
        logger.debug(f"Registered action executor: {name}")

    def evaluate_rule(self, rule: RuleConfig, context: Dict[str, Any]) -> bool:
        """
        Evaluate all conditions for a rule (AND logic).

        All conditions must pass for the rule to match.

        Args:
            rule: RuleConfig to evaluate
            context: Context dict with booking, db_record, current_time, etc.

        Returns:
            True if rule is enabled and all conditions met, False otherwise
        """
        # Disabled rules never match
        if not rule.enabled:
            logger.debug(f"Rule '{rule.name}' is disabled")
            return False

        # Evaluate each condition (AND logic)
        for condition in rule.conditions:
            evaluator = self.condition_evaluators.get(condition.type)

            # Unknown condition type fails the rule
            if not evaluator:
                logger.error(
                    f"Unknown condition type in rule '{rule.name}': {condition.type}"
                )
                return False

            try:
                params = condition.params or {}
                result = evaluator(context, **params)

                # Short-circuit on first failing condition
                if not result:
                    logger.debug(
                        f"Rule '{rule.name}' condition '{condition.type}' evaluated to False"
                    )
                    return False

            except Exception as e:
                logger.error(
                    f"Error evaluating condition '{condition.type}' in rule '{rule.name}': {e}",
                    exc_info=True,
                )
                return False

        # All conditions passed
        logger.info(f"Rule '{rule.name}' conditions all met")
        return True

    def execute_rule(
        self, rule: RuleConfig, context: Dict[str, Any]
    ) -> List[ActionResult]:
        """
        Execute all actions for a rule in sequence.

        Errors in individual actions don't prevent subsequent actions from running.

        Args:
            rule: RuleConfig to execute
            context: Context dict

        Returns:
            List of ActionResult objects
        """
        results: List[ActionResult] = []

        for action in rule.actions:
            executor = self.action_executors.get(action.type)

            # Unknown action type is recorded as failure
            if not executor:
                logger.error(
                    f"Unknown action type in rule '{rule.name}': {action.type}"
                )
                results.append(
                    ActionResult(
                        rule_name=rule.name,
                        action_type=action.type,
                        success=False,
                        message=f"Unknown action type: {action.type}",
                        error=f"No executor registered for '{action.type}'",
                    )
                )
                continue

            try:
                params = action.params or {}
                executor(context, **params)

                results.append(
                    ActionResult(
                        rule_name=rule.name,
                        action_type=action.type,
                        success=True,
                        message=f"Action '{action.type}' executed successfully",
                        params=params,
                    )
                )

                logger.debug(
                    f"Action '{action.type}' in rule '{rule.name}' executed successfully"
                )

            except Exception as e:
                logger.error(
                    f"Error executing action '{action.type}' in rule '{rule.name}': {e}",
                    exc_info=True,
                )

                results.append(
                    ActionResult(
                        rule_name=rule.name,
                        action_type=action.type,
                        success=False,
                        message=f"Action '{action.type}' failed",
                        error=str(e),
                        params=params,
                    )
                )

        return results

    def process_booking(self, context: Dict[str, Any]) -> List[ActionResult]:
        """
        Main entry point: process a booking through all rules.

        Iterates through all enabled rules, evaluates conditions,
        and executes actions for matched rules.

        Args:
            context: Context dict with booking, db_record, current_time, etc.

        Returns:
            List of ActionResult objects from all matched rules
        """
        all_results: List[ActionResult] = []

        for rule in self.rules:
            try:
                # Evaluate rule conditions
                if self.evaluate_rule(rule, context):
                    # Execute rule actions
                    results = self.execute_rule(rule, context)
                    all_results.extend(results)

            except Exception as e:
                logger.error(
                    f"Unexpected error processing rule '{rule.name}': {e}",
                    exc_info=True,
                )

        logger.info(
            f"Processed booking through {len(self.rules)} rules, "
            f"matched actions: {len(all_results)}"
        )
        return all_results
