#!/usr/bin/env python3
"""
Bootstrap validation campaign for Story 5.5.

Prepares test environment, validates prerequisites, and initializes
the validation campaign with Slack notifications enabled.

Usage:
  python scripts/bootstrap_validation_campaign.py [--dry-run] [--slack-test]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.validation_environment import (
    ValidationEnvironmentSetup,
    create_default_validation_environment,
)
from src.notifications.slack_service import SlackWebhookClient


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for bootstrap script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def validate_environment(setup: ValidationEnvironmentSetup) -> bool:
    """
    Validate all environment prerequisites.

    Returns:
        True if all prerequisites met, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("VALIDATION ENVIRONMENT BOOTSTRAP")
    logger.info("=" * 80)

    logger.info("\n1️⃣  Validating prerequisites...")
    if not setup.validate_prerequisites():
        logger.error("❌ Validation environment prerequisites not met")
        return False

    logger.info("✅ All prerequisites validated")
    return True


def bootstrap_environment(setup: ValidationEnvironmentSetup) -> bool:
    """
    Bootstrap the validation environment.

    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info("\n2️⃣  Bootstrapping validation environment...")

    try:
        output_dir = setup.bootstrap_diff_reporter_output()
        logger.info(f"✅ Diff reporter output directory ready: {output_dir}")

        validation_context = setup.get_validation_context()
        logger.info(f"✅ Validation context prepared")
        logger.debug(f"Context: {json.dumps(validation_context, indent=2, default=str)}")

        return True
    except Exception as e:
        logger.error(f"❌ Bootstrap failed: {e}")
        return False


def test_slack_webhook(
    config, dry_run: bool = False
) -> bool:
    """
    Test Slack webhook configuration.

    Returns:
        True if webhook is valid, False otherwise
    """
    logger = logging.getLogger(__name__)

    if not config.enable_slack_notifications:
        logger.info("⏭️  Slack notifications disabled (skipping webhook test)")
        return True

    logger.info("\n3️⃣  Testing Slack webhook configuration...")

    if not config.slack_webhook_url:
        logger.error("❌ Slack webhook URL not configured")
        return False

    try:
        client = SlackWebhookClient(webhook_url=config.slack_webhook_url)

        # Get webhook status
        status = client.get_webhook_status()
        logger.info(f"Webhook Status: {json.dumps(status, indent=2)}")

        if not dry_run:
            logger.info("Sending test notification to Slack...")
            masked_url = SlackWebhookClient._mask_url(config.slack_webhook_url)
            client.send_slack_webhook_test(masked_url, "success")
            logger.info("✅ Test notification sent to Slack")
        else:
            logger.info("⏭️  Skipping actual Slack notification (dry-run mode)")

        return True
    except Exception as e:
        logger.error(f"❌ Slack webhook test failed: {e}")
        return False


def print_summary(setup: ValidationEnvironmentSetup, success: bool) -> None:
    """Print validation summary."""
    logger = logging.getLogger(__name__)

    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION BOOTSTRAP SUMMARY")
    logger.info("=" * 80)

    if success:
        logger.info("✅ VALIDATION ENVIRONMENT READY FOR TESTING")
    else:
        logger.error("❌ VALIDATION BOOTSTRAP FAILED - See errors above")

    logger.info(f"\nCampaign Configuration:")
    logger.info(f"  Campaign ID: {setup.config.campaign_id}")
    logger.info(f"  Environment: {setup.config.test_environment}")
    logger.info(f"  Docker Image: {setup.config.docker_image_digest}")
    logger.info(f"  Test Data Version: {setup.config.test_data_version}")
    logger.info(f"  Slack Notifications: {'Enabled' if setup.config.enable_slack_notifications else 'Disabled'}")
    logger.info(f"  Performance Monitoring: {'Enabled' if setup.config.enable_performance_monitoring else 'Disabled'}")
    logger.info(f"  Comparison Artifacts: {'Enabled' if setup.config.enable_comparison_artifacts else 'Disabled'}")

    logger.info(f"\nOutput Directories:")
    logger.info(f"  Diff Reporter: {setup.config.diff_reporter_output_dir}")
    logger.info(f"  Test Fixtures: {setup.config.fixture_location}")
    logger.info(f"  Golden Datasets: {setup.config.golden_dataset_location}")

    logger.info(f"\nPerformance Thresholds:")
    logger.info(f"  Execution Duration: {setup.config.execution_duration_threshold_ms}ms (4 min)")
    logger.info(f"  Cold Start: {setup.config.cold_start_threshold_ms}ms (10 sec)")
    logger.info(f"  Memory: {setup.config.memory_threshold_mb}MB")
    logger.info(f"  DynamoDB Latency: {setup.config.dynamodb_latency_threshold_ms}ms")

    logger.info("\n" + "=" * 80)
    if success:
        logger.info("Next: Run validation test suite with:")
        logger.info("  pytest tests/comparison/test_output_parity.py -v -m parity")
    logger.info("=" * 80 + "\n")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bootstrap validation campaign for Story 5.5"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual Slack webhook send (just test URL format)",
    )
    parser.add_argument(
        "--slack-test",
        action="store_true",
        help="Test Slack webhook connectivity",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Create environment setup
        config = create_default_validation_environment()
        setup = ValidationEnvironmentSetup(config)

        # Validate prerequisites
        if not validate_environment(setup):
            print_summary(setup, False)
            return 1

        # Bootstrap environment
        if not bootstrap_environment(setup):
            print_summary(setup, False)
            return 1

        # Test Slack webhook if requested
        if args.slack_test:
            if not test_slack_webhook(config, dry_run=args.dry_run):
                print_summary(setup, False)
                return 1

        # Print summary
        print_summary(setup, True)
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
