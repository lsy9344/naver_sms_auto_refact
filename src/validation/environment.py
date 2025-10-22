"""Production modules for validation environment bootstrap."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = PROJECT_ROOT / "tests"


@dataclass
class ValidationEnvironmentConfig:
    """Configuration for validation campaign environment."""

    # Campaign metadata
    campaign_id: str
    campaign_start_time: str
    test_environment: str  # "local-development" | "staging" | "production"

    # Tool versions
    python_version: str
    pytest_version: str
    docker_image_digest: str
    aws_region: str
    aws_account_id: str

    # Data snapshots
    test_data_version: str
    fixture_location: str
    golden_dataset_location: str

    # Secrets Manager configuration
    secrets_manager_region: str
    secrets_manager_enabled: bool
    naver_credentials_secret: str
    sens_credentials_secret: str
    telegram_credentials_secret: str
    slack_webhook_secret: Optional[str] = None

    # Slack webhook configuration
    slack_webhook_url: Optional[str] = None
    slack_webhook_url_test: Optional[str] = None
    slack_validation_channel: Optional[str] = None
    slack_alerts_channel: Optional[str] = None

    # Diff reporter output
    diff_reporter_output_dir: str = ""

    # Performance thresholds
    execution_duration_threshold_ms: int = 240000
    cold_start_threshold_ms: int = 10000
    memory_threshold_mb: int = 512
    dynamodb_latency_threshold_ms: int = 100

    # Feature flags
    enable_slack_notifications: bool = False
    enable_performance_monitoring: bool = True
    enable_comparison_artifacts: bool = True
    dry_run_mode: bool = False

    def to_dict(self) -> Dict[str, object]:
        """Convert configuration to a serialisable dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    def validate(self) -> List[str]:
        """Validate configuration completeness. Returns list of errors."""
        errors: List[str] = []

        if not self.campaign_id:
            errors.append("campaign_id is required")
        if not self.docker_image_digest:
            errors.append("docker_image_digest is required")
        if not self.aws_account_id:
            errors.append("aws_account_id is required")

        if self.enable_slack_notifications:
            if not self.slack_webhook_url:
                errors.append("slack_webhook_url required when enable_slack_notifications=true")
            if not self.slack_webhook_url_test:
                errors.append(
                    "slack_webhook_url_test required when enable_slack_notifications=true"
                )

        if not Path(self.fixture_location).exists():
            errors.append(f"fixture_location does not exist: {self.fixture_location}")
        if not Path(self.golden_dataset_location).exists():
            errors.append(f"golden_dataset_location does not exist: {self.golden_dataset_location}")

        if self.execution_duration_threshold_ms <= 0:
            errors.append("execution_duration_threshold_ms must be > 0")
        if self.memory_threshold_mb <= 0:
            errors.append("memory_threshold_mb must be > 0")

        return errors


def _default_fixture_location() -> str:
    return str(TESTS_ROOT / "fixtures")


def _default_golden_dataset_location() -> str:
    return str(TESTS_ROOT / "fixtures" / "golden_datasets")


def create_default_validation_environment() -> ValidationEnvironmentConfig:
    """Create default validation environment configuration."""
    now = datetime.utcnow().isoformat()

    return ValidationEnvironmentConfig(
        campaign_id=os.getenv("VALIDATION_CAMPAIGN_ID", f"validation-{now[:19]}"),
        campaign_start_time=now,
        test_environment=os.getenv("TEST_ENVIRONMENT", "local-development"),
        python_version=os.getenv("PYTHON_VERSION", "3.11"),
        pytest_version=os.getenv("PYTEST_VERSION", "7.4.3"),
        docker_image_digest=os.getenv("DOCKER_IMAGE_DIGEST", "local-development"),
        aws_region=os.getenv("AWS_REGION", "ap-northeast-2"),
        aws_account_id=os.getenv("AWS_ACCOUNT_ID", "654654307503"),
        test_data_version=os.getenv("TEST_DATA_VERSION", "1.0"),
        fixture_location=os.getenv("FIXTURE_LOCATION", _default_fixture_location()),
        golden_dataset_location=os.getenv(
            "GOLDEN_DATASET_LOCATION", _default_golden_dataset_location()
        ),
        secrets_manager_region=os.getenv("SECRETS_MANAGER_REGION", "ap-northeast-2"),
        secrets_manager_enabled=os.getenv("SECRETS_MANAGER_ENABLED", "false") == "true",
        naver_credentials_secret=os.getenv(
            "NAVER_CREDENTIALS_SECRET", "naver-sms-automation/naver-credentials"
        ),
        sens_credentials_secret=os.getenv(
            "SENS_CREDENTIALS_SECRET", "naver-sms-automation/sens-credentials"
        ),
        telegram_credentials_secret=os.getenv(
            "TELEGRAM_CREDENTIALS_SECRET", "naver-sms-automation/telegram-credentials"
        ),
        slack_webhook_secret=os.getenv(
            "SLACK_WEBHOOK_SECRET", "naver-sms-automation/slack-webhook"
        ),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        slack_webhook_url_test=os.getenv("SLACK_WEBHOOK_URL_TEST"),
        slack_validation_channel=os.getenv("SLACK_VALIDATION_CHANNEL", "validation-alerts"),
        slack_alerts_channel=os.getenv("SLACK_ALERTS_CHANNEL", "sms-automation-alerts"),
        diff_reporter_output_dir=os.getenv(
            "DIFF_REPORTER_OUTPUT_DIR",
            str(TESTS_ROOT / "comparison" / "results"),
        ),
        execution_duration_threshold_ms=int(os.getenv("EXECUTION_DURATION_THRESHOLD_MS", "240000")),
        cold_start_threshold_ms=int(os.getenv("COLD_START_THRESHOLD_MS", "10000")),
        memory_threshold_mb=int(os.getenv("MEMORY_THRESHOLD_MB", "512")),
        dynamodb_latency_threshold_ms=int(os.getenv("DYNAMODB_LATENCY_THRESHOLD_MS", "100")),
        enable_slack_notifications=os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false") == "true",
        enable_performance_monitoring=os.getenv("ENABLE_PERFORMANCE_MONITORING", "true") == "true",
        enable_comparison_artifacts=os.getenv("ENABLE_COMPARISON_ARTIFACTS", "true") == "true",
        dry_run_mode=os.getenv("DRY_RUN_MODE", "false") == "true",
    )


class ValidationEnvironmentSetup:
    """Setup and bootstrap validation environment for Story 5.5."""

    def __init__(self, config: Optional[ValidationEnvironmentConfig] = None):
        self.config = config or create_default_validation_environment()
        self.logger = logging.getLogger(__name__)

    def validate_prerequisites(self) -> bool:
        """Validate all environment prerequisites."""
        self.logger.info("Validating validation environment prerequisites...")

        errors = self.config.validate()
        if errors:
            for error in errors:
                self.logger.error(f"Configuration error: {error}")
            return False

        dirs_to_check = [
            self.config.fixture_location,
            self.config.golden_dataset_location,
            self.config.diff_reporter_output_dir,
        ]

        for dir_path in dirs_to_check:
            path = Path(dir_path)
            if not path.exists():
                self.logger.warning(f"Creating missing directory: {dir_path}")
                path.mkdir(parents=True, exist_ok=True)

        if self.config.enable_slack_notifications and not self._validate_slack_webhook():
            self.logger.error("Slack webhook validation failed")
            return False

        self.logger.info("✅ All validation prerequisites met")
        return True

    def bootstrap_diff_reporter_output(self) -> Path:
        """Bootstrap diff reporter output directory."""
        output_dir = Path(self.config.diff_reporter_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "campaign_id": self.config.campaign_id,
            "campaign_start_time": self.config.campaign_start_time,
            "test_environment": self.config.test_environment,
            "docker_image_digest": self.config.docker_image_digest,
            "test_data_version": self.config.test_data_version,
        }

        metadata_path = output_dir / "campaign_metadata.json"
        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2)

        self.logger.info("Bootstrapped diff reporter output: %s", output_dir)
        return output_dir

    def _validate_slack_webhook(self) -> bool:
        if not self.config.slack_webhook_url:
            self.logger.warning("Slack webhook URL not configured")
            return False

        self.logger.info("Slack webhook URL configured (validation skipped in dry-run)")
        return True

    def get_validation_context(self) -> Dict[str, object]:
        """Return complete validation context for test execution."""
        return {
            "config": self.config.to_dict(),
            "start_time": datetime.utcnow().isoformat(),
            "test_data": {
                "fixture_location": self.config.fixture_location,
                "golden_dataset_location": self.config.golden_dataset_location,
                "version": self.config.test_data_version,
            },
            "notifications": {
                "slack_enabled": self.config.enable_slack_notifications,
                "slack_validation_channel": self.config.slack_validation_channel,
                "slack_alerts_channel": self.config.slack_alerts_channel,
            },
            "thresholds": {
                "execution_duration_ms": self.config.execution_duration_threshold_ms,
                "cold_start_ms": self.config.cold_start_threshold_ms,
                "memory_mb": self.config.memory_threshold_mb,
                "dynamodb_latency_ms": self.config.dynamodb_latency_threshold_ms,
            },
        }
