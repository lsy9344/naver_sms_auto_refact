#!/usr/bin/env python3
"""
Verification script to print loaded rules configuration.

Usage:
    python scripts/print_rules.py

Output:
    Summary of rules configuration including:
    - Total rule count
    - Enabled/disabled rule breakdown
    - Condition types used
    - Action types used
"""

import sys
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_rules_summary(settings: Settings) -> None:
    """Print summary of loaded rules configuration."""
    print("\n" + "=" * 80)
    print("RULES CONFIGURATION SUMMARY")
    print("=" * 80)

    total_rules = len(settings.rules)
    enabled_rules = sum(1 for rule in settings.rules if rule.get("enabled", True))
    disabled_rules = total_rules - enabled_rules

    print(f"\nTotal Rules: {total_rules}")
    print(f"  - Enabled:  {enabled_rules}")
    print(f"  - Disabled: {disabled_rules}")

    # Collect condition and action types
    condition_types = set()
    action_types = set()

    print("\n" + "-" * 80)
    print("RULES DETAIL")
    print("-" * 80)

    for idx, rule in enumerate(settings.rules, 1):
        name = rule.get("name", "Unknown")
        enabled = rule.get("enabled", True)
        status = "✓ ENABLED" if enabled else "✗ DISABLED"
        description = rule.get("description", "No description")
        tags = rule.get("tags", [])

        print(f"\n[{idx}] {name} [{status}]")
        print(f"    Description: {description}")
        if tags:
            print(f"    Tags: {', '.join(tags)}")

        # Conditions
        conditions = rule.get("conditions", [])
        print(f"    Conditions ({len(conditions)}):")
        for cond in conditions:
            cond_type = cond.get("type", "unknown")
            condition_types.add(cond_type)
            params = cond.get("params", {})
            if params:
                params_str = ", ".join(f"{k}={v}" for k, v in params.items())
                print(f"      - {cond_type} ({params_str})")
            else:
                print(f"      - {cond_type}")

        # Actions
        actions = rule.get("actions", [])
        print(f"    Actions ({len(actions)}):")
        for action in actions:
            action_type = action.get("type", "unknown")
            action_types.add(action_type)
            params = action.get("params", {})
            if params:
                params_str = ", ".join(f"{k}={v}" for k, v in params.items())
                print(f"      - {action_type} ({params_str})")
            else:
                print(f"      - {action_type}")

    # Summary statistics
    print("\n" + "-" * 80)
    print("CONFIGURATION STATISTICS")
    print("-" * 80)
    print(f"\nCondition Types Used ({len(condition_types)}):")
    for cond_type in sorted(condition_types):
        count = sum(
            1
            for rule in settings.rules
            for cond in rule.get("conditions", [])
            if cond.get("type") == cond_type
        )
        print(f"  - {cond_type}: {count} occurrence(s)")

    print(f"\nAction Types Used ({len(action_types)}):")
    for action_type in sorted(action_types):
        count = sum(
            1
            for rule in settings.rules
            for action in rule.get("actions", [])
            if action.get("type") == action_type
        )
        print(f"  - {action_type}: {count} occurrence(s)")

    print("\n" + "=" * 80)
    print("✓ Rules configuration loaded successfully")
    print("=" * 80 + "\n")


def main() -> int:
    """Main entry point."""
    try:
        # Determine paths
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        rules_config = project_root / "config" / "rules.yaml"
        rules_schema = project_root / "src" / "config" / "rules.schema.json"

        logger.info(f"Loading rules from: {rules_config}")
        logger.info(f"Using schema: {rules_schema}")

        # Load settings and rules
        settings = Settings()
        settings.load_rules(str(rules_config), str(rules_schema))

        # Print summary
        print_rules_summary(settings)

        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
