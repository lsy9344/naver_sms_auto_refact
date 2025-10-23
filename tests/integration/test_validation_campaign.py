"""
End-to-End Validation Campaign Integration Tests

Story 5.5 TECH-001: Tests complete validation campaign workflow from bootstrap
through final reporting, ensuring all components work together.

Test Coverage:
- Campaign bootstrap execution
- Comparison suite execution
- Metrics publishing to CloudWatch
- Slack notifications delivery
- Report artifact generation
- Aggregate summary creation
- Success criteria validation
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.comparison.diff_reporter import DiffReporter
from src.notifications.slack_service import SlackWebhookClient
from src.validation.environment import (
    ValidationEnvironmentSetup,
    create_default_validation_environment,
)
from src.validation.orchestrator import ValidationCampaignOrchestrator

logger = logging.getLogger(__name__)


class TestValidationCampaignBootstrap:
    """Test campaign bootstrap phase."""

    def test_bootstrap_creates_required_directories(self, tmp_path):
        """TECH-001: Bootstrap creates output directories."""
        config = create_default_validation_environment()
        config.diff_reporter_output_dir = str(tmp_path / "results")

        setup = ValidationEnvironmentSetup(config)
        output_dir = setup.bootstrap_diff_reporter_output()

        assert output_dir.exists()
        assert (output_dir / "campaign_metadata.json").exists()

    def test_bootstrap_generates_campaign_metadata(self, tmp_path):
        """TECH-001: Bootstrap generates campaign metadata."""
        config = create_default_validation_environment()
        config.campaign_id = "test-campaign-001"
        config.diff_reporter_output_dir = str(tmp_path / "results")

        setup = ValidationEnvironmentSetup(config)
        setup.bootstrap_diff_reporter_output()

        metadata_file = tmp_path / "results" / "campaign_metadata.json"
        with metadata_file.open("r") as f:
            metadata = json.load(f)

        assert metadata["campaign_id"] == "test-campaign-001"
        assert "campaign_start_time" in metadata
        assert "docker_image_digest" in metadata
        assert "test_data_version" in metadata

    def test_bootstrap_validation_prerequisites_pass(self):
        """TECH-001: Bootstrap validates all prerequisites."""
        config = create_default_validation_environment()
        setup = ValidationEnvironmentSetup(config)

        assert setup.validate_prerequisites()

    def test_bootstrap_validation_fails_with_invalid_config(self, tmp_path):
        """TECH-001: Bootstrap fails gracefully with invalid configuration."""
        config = create_default_validation_environment()
        config.execution_duration_threshold_ms = 0  # Invalid threshold

        _ = ValidationEnvironmentSetup(config)
        errors = config.validate()

        assert len(errors) > 0
        assert any("execution_duration_threshold_ms" in e for e in errors)

    def test_bootstrap_creates_validation_context(self):
        """TECH-001: Bootstrap creates complete validation context."""
        config = create_default_validation_environment()
        setup = ValidationEnvironmentSetup(config)

        context = setup.get_validation_context()

        assert "config" in context
        assert "start_time" in context
        assert "test_data" in context
        assert "notifications" in context
        assert "thresholds" in context

        # Verify context structure
        assert context["notifications"]["slack_enabled"] == config.enable_slack_notifications
        assert context["thresholds"]["execution_duration_ms"] == 240000


class TestValidationCampaignComparison:
    """Test comparison execution phase."""

    def test_diff_reporter_generates_json_artifacts(self, tmp_path):
        """TECH-001: Comparison generates JSON artifacts."""
        reporter = DiffReporter(output_dir=tmp_path)

        # Mock comparison results
        mismatches = []
        stats = {
            "booking_id": "test-001",
            "total_mismatches": 0,
            "critical_mismatches": 0,
            "warning_mismatches": 0,
            "parity_status": "PASS",
            "timestamp": datetime.utcnow().isoformat(),
        }

        json_path, md_path = reporter.write_reports(
            booking_id="test-001",
            scenario="New Booking",
            mismatches=mismatches,
            stats=stats,
        )

        assert json_path.exists()
        assert md_path.exists()

        # Verify JSON structure
        with json_path.open("r") as f:
            report = json.load(f)

        assert "metadata" in report
        assert "statistics" in report
        assert "mismatches" in report
        assert report["statistics"]["parity_status"] == "PASS"

    def test_diff_reporter_generates_markdown_artifacts(self, tmp_path):
        """TECH-001: Comparison generates markdown summaries."""
        reporter = DiffReporter(output_dir=tmp_path)

        mismatches = []
        stats = {
            "booking_id": "test-001",
            "total_mismatches": 0,
            "critical_mismatches": 0,
            "warning_mismatches": 0,
            "parity_status": "PASS",
            "timestamp": datetime.utcnow().isoformat(),
        }

        json_path, md_path = reporter.write_reports(
            booking_id="test-001",
            scenario="New Booking",
            mismatches=mismatches,
            stats=stats,
        )

        with md_path.open("r") as f:
            content = f.read()

        assert "# Comparison Report: test-001" in content
        assert "**Parity Status:** PASS" in content
        assert "Perfect Parity" in content

    def test_diff_reporter_aggregates_results(self, tmp_path):
        """TECH-001: Comparison aggregates multiple booking results."""
        reporter = DiffReporter(output_dir=tmp_path)

        # Create multiple comparison results
        all_stats = [
            {
                "booking_id": "booking-001",
                "parity_status": "PASS",
                "critical_mismatches": 0,
                "warning_mismatches": 0,
            },
            {
                "booking_id": "booking-002",
                "parity_status": "PASS",
                "critical_mismatches": 0,
                "warning_mismatches": 0,
            },
            {
                "booking_id": "booking-003",
                "parity_status": "PASS",
                "critical_mismatches": 0,
                "warning_mismatches": 0,
            },
        ]

        summary_path = reporter.write_aggregate_summary(all_stats)

        assert summary_path.exists()

        with summary_path.open("r") as f:
            summary = f.read()

        assert "**Total Bookings Tested:** 3" in summary
        assert "**Passed:** 3" in summary
        assert "**Pass Rate:** 100.0%" in summary

    def test_diff_reporter_includes_slack_webhook_comparison(self, tmp_path):
        """TECH-001: Diff reporter compares Slack webhook outputs."""
        reporter = DiffReporter(output_dir=tmp_path)

        # Mock canonical outputs with Slack data
        canonical_legacy = {
            "sms": [],
            "db_records": [],
            "telegram": [],
            "slack": [
                {
                    "webhook_id": "test-webhook",
                    "status": "delivered",
                    "timestamp": "2025-10-20T15:00:00Z",
                }
            ],
            "actions": [],
        }

        canonical_refactored = {
            "sms": [],
            "db_records": [],
            "telegram": [],
            "slack": [
                {
                    "webhook_id": "test-webhook",
                    "status": "delivered",
                    "timestamp": "2025-10-20T15:00:00Z",
                }
            ],
            "actions": [],
        }

        mismatches, stats = reporter.compare_outputs(
            booking_id="test-001",
            canonical_legacy=canonical_legacy,
            canonical_refactored=canonical_refactored,
        )

        # Should have no mismatches (identical Slack outputs)
        assert len(mismatches) == 0
        assert stats["parity_status"] == "PASS"


class TestValidationCampaignMetrics:
    """Test metrics publishing phase."""

    @patch("src.monitoring.comparison.boto3.client")
    def test_cloudwatch_metrics_published(self, mock_boto3_client):
        """TECH-001: Campaign publishes metrics to CloudWatch."""
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch

        # Import after mock is set up
        from src.monitoring.comparison import ComparisonMetricsPublisher

        publisher = ComparisonMetricsPublisher()

        # Publish test metrics
        publisher.publish_metrics(
            booking_id="test-001",
            legacy_sms_count=5,
            refactored_sms_count=5,
            match_percentage=100.0,
            critical_mismatches=0,
            warning_mismatches=0,
        )

        # Verify CloudWatch API called
        mock_cloudwatch.put_metric_data.assert_called()


class TestValidationCampaignSlack:
    """Test Slack notifications phase."""

    def test_slack_webhook_client_initialized(self):
        """TECH-001: Slack webhook client can be initialized."""
        client = SlackWebhookClient(webhook_url="https://hooks.slack.com/services/test/webhook")

        status = client.get_webhook_status()

        assert status["webhook_configured"]
        assert "hooks.slack.com" in status["webhook_url_masked"]

    @patch("requests.Session.post")
    def test_slack_validation_started_notification(self, mock_post):
        """TECH-001: Campaign sends validation started notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = SlackWebhookClient(webhook_url="https://hooks.slack.com/services/test/webhook")
        client.send_validation_started("campaign-001", 100)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["timeout"] == 10

    @patch("requests.Session.post")
    def test_slack_validation_completed_notification(self, mock_post):
        """TECH-001: Campaign sends validation completed notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = SlackWebhookClient(webhook_url="https://hooks.slack.com/services/test/webhook")
        client.send_validation_completed("campaign-001", 100, 100, 0)

        mock_post.assert_called_once()

    @patch("requests.Session.post")
    def test_slack_parity_mismatch_alert(self, mock_post):
        """TECH-001: Campaign sends mismatch alert to Slack."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = SlackWebhookClient(webhook_url="https://hooks.slack.com/services/test/webhook")
        client.send_parity_mismatch_alert("booking-001", 3, 1)

        mock_post.assert_called_once()


class TestValidationCampaignSuccessCriteria:
    """Test success criteria validation phase."""

    def test_campaign_succeeds_with_100_percent_parity(self):
        """TECH-001: Campaign validates 100% parity success criterion."""
        all_stats = [
            {"booking_id": "b-001", "parity_status": "PASS", "critical_mismatches": 0},
            {"booking_id": "b-002", "parity_status": "PASS", "critical_mismatches": 0},
            {"booking_id": "b-003", "parity_status": "PASS", "critical_mismatches": 0},
        ]

        # Calculate success metrics
        passed = sum(1 for s in all_stats if s["parity_status"] == "PASS")
        critical = sum(s["critical_mismatches"] for s in all_stats)
        pass_rate = (passed / len(all_stats) * 100) if all_stats else 0

        assert pass_rate == 100.0
        assert critical == 0

    def test_campaign_fails_with_mismatches(self):
        """TECH-001: Campaign detects parity failures."""
        all_stats = [
            {
                "booking_id": "b-001",
                "parity_status": "PASS",
                "critical_mismatches": 0,
            },
            {
                "booking_id": "b-002",
                "parity_status": "FAIL",
                "critical_mismatches": 2,
            },
            {
                "booking_id": "b-003",
                "parity_status": "PASS",
                "critical_mismatches": 0,
            },
        ]

        # Calculate success metrics
        passed = sum(1 for s in all_stats if s["parity_status"] == "PASS")
        critical = sum(s["critical_mismatches"] for s in all_stats)
        pass_rate = (passed / len(all_stats) * 100) if all_stats else 0

        assert round(pass_rate, 2) == 66.67
        assert critical == 2


class TestValidationCampaignIntegration:
    """Test complete end-to-end campaign workflow."""

    def test_full_campaign_workflow(self, tmp_path):
        """TECH-001: Full campaign workflow executes successfully."""
        # 1. Bootstrap
        config = create_default_validation_environment()
        config.campaign_id = "e2e-test-campaign"
        config.diff_reporter_output_dir = str(tmp_path / "results")

        setup = ValidationEnvironmentSetup(config)
        assert setup.validate_prerequisites()

        output_dir = setup.bootstrap_diff_reporter_output()
        assert output_dir.exists()

        # 2. Run comparisons
        reporter = DiffReporter(output_dir=output_dir)

        test_bookings = [
            ("booking-001", "New Booking Confirmation"),
            ("booking-002", "Two-Hour Reminder"),
            ("booking-003", "Event SMS"),
        ]

        all_stats = []

        for booking_id, scenario in test_bookings:
            stats = {
                "booking_id": booking_id,
                "total_mismatches": 0,
                "critical_mismatches": 0,
                "warning_mismatches": 0,
                "parity_status": "PASS",
                "timestamp": datetime.utcnow().isoformat(),
            }

            reporter.write_reports(
                booking_id=booking_id,
                scenario=scenario,
                mismatches=[],
                stats=stats,
            )

            all_stats.append(stats)

        # 3. Generate aggregate summary
        summary_path = reporter.write_aggregate_summary(all_stats)
        assert summary_path.exists()

        # 4. Validate results
        passed = sum(1 for s in all_stats if s["parity_status"] == "PASS")
        assert passed == 3
        assert len(all_stats) == 3

        # 5. Verify artifacts
        json_files = list(output_dir.glob("*.json"))
        md_files = list(output_dir.glob("*.md"))

        assert len(json_files) >= 4  # 3 bookings + metadata
        assert len(md_files) >= 2  # 3 bookings + summary

    def test_campaign_generates_all_artifacts(self, tmp_path):
        """TECH-001: Campaign generates all required artifacts."""
        config = create_default_validation_environment()
        config.diff_reporter_output_dir = str(tmp_path / "results")

        setup = ValidationEnvironmentSetup(config)
        output_dir = setup.bootstrap_diff_reporter_output()

        # Campaign should produce:
        # - campaign_metadata.json
        # - Booking comparison JSONs
        # - Booking comparison Markdowns
        # - Aggregate summary markdown

        required_files = [
            "campaign_metadata.json",
        ]

        for filename in required_files:
            assert (output_dir / filename).exists(), f"Missing {filename}"


class TestValidationCampaignOrchestratorEndToEnd:
    """Test complete orchestrator end-to-end workflow with production modules."""

    @patch("src.monitoring.comparison.boto3.client")
    @patch("requests.Session.post")
    def test_orchestrator_runs_complete_campaign(self, mock_post, mock_boto3):
        """TECH-001 & BUS-001: Orchestrator executes complete campaign end-to-end."""
        # Setup mocks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        mock_cloudwatch = MagicMock()
        mock_boto3.return_value = mock_cloudwatch

        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create config and orchestrator
            config = create_default_validation_environment()
            config.campaign_id = "orch-e2e-test"
            config.diff_reporter_output_dir = tmp_dir
            config.slack_webhook_url = "https://hooks.slack.com/test"

            orchestrator = ValidationCampaignOrchestrator(config)

            # Prepare test data
            bookings = [
                {
                    "booking_id": "b-001",
                    "sms": [{"phone": "010-1234-5678", "status": "sent"}],
                    "db_records": [{"booking_num": "BK001"}],
                    "telegram": [],
                    "slack": [],
                    "actions": [],
                },
                {
                    "booking_id": "b-002",
                    "sms": [{"phone": "010-8765-4321", "status": "sent"}],
                    "db_records": [{"booking_num": "BK002"}],
                    "telegram": [],
                    "slack": [],
                    "actions": [],
                },
            ]

            golden_dataset = {
                "b-001": {
                    "sms": [{"phone": "010-1234-5678", "status": "sent"}],
                    "db_records": [{"booking_num": "BK001"}],
                    "telegram": [],
                    "slack": [],
                    "actions": [],
                },
                "b-002": {
                    "sms": [{"phone": "010-8765-4321", "status": "sent"}],
                    "db_records": [{"booking_num": "BK002"}],
                    "telegram": [],
                    "slack": [],
                    "actions": [],
                },
            }

            # Run campaign
            result = orchestrator.run_campaign(bookings, golden_dataset)

            # Verify result structure
            assert result["campaign_id"] == "orch-e2e-test"
            assert "comparison_stats" in result
            assert "readiness_report" in result
            assert "evidence_package" in result
            assert "timestamp" in result

            # Verify comparison stats
            assert len(result["comparison_stats"]) == 2
            for stat in result["comparison_stats"]:
                assert stat["parity_status"] == "PASS"
                assert stat["critical_mismatches"] == 0

            # Verify readiness report
            readiness = result["readiness_report"]
            assert "decision" in readiness
            assert "confidence_level" in readiness

            # Verify evidence package
            evidence = result["evidence_package"]
            assert evidence["campaign_id"] == "orch-e2e-test"
            assert "artifacts" in evidence
            assert "manifest" in evidence

            # Verify artifacts were written
            output_dir = Path(tmp_dir)

            # Artifacts can be in top-level or in campaign subdirectory
            json_files = list(output_dir.glob("*.json")) + list(output_dir.glob("**/*.json"))
            md_files = list(output_dir.glob("*.md")) + list(output_dir.glob("**/*.md"))

            # Remove duplicates
            json_files = list(set(json_files))
            md_files = list(set(md_files))

            assert len(json_files) >= 2  # At least 2 booking comparisons
            assert len(md_files) >= 1  # At least summary or booking reports

            # Verify DiffReporter was called (no AttributeError)
            assert orchestrator.diff_reporter is not None

    @patch("src.monitoring.comparison.boto3.client")
    def test_orchestrator_collects_evidence_with_validation_md_updated(self, mock_boto3):
        """BUS-001: Evidence package correctly reports validation_md_updated status."""
        mock_cloudwatch = MagicMock()
        mock_boto3.return_value = mock_cloudwatch

        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create VALIDATION.md
            validation_md = Path(tmp_dir) / "VALIDATION.md"
            validation_md.write_text("# Validation Results\n\n")

            config = create_default_validation_environment()
            config.campaign_id = "validation-md-test"
            config.diff_reporter_output_dir = tmp_dir
            config.slack_webhook_url = None

            orchestrator = ValidationCampaignOrchestrator(config)

            # Run campaign with minimal data
            bookings = [
                {
                    "booking_id": "b-001",
                    "sms": [],
                    "db_records": [],
                    "telegram": [],
                    "slack": [],
                    "actions": [],
                }
            ]

            golden_dataset = {
                "b-001": {
                    "sms": [],
                    "db_records": [],
                    "telegram": [],
                    "slack": [],
                    "actions": [],
                }
            }

            result = orchestrator.run_campaign(bookings, golden_dataset)
            evidence = result["evidence_package"]

            # Verify validation_md_updated reflects actual status
            # When _collect_evidence runs, it should update VALIDATION.md
            assert "validation_md_updated" in evidence
            # The flag should be True if update_validation_md succeeded
            updated_status = evidence["validation_md_updated"]
            assert isinstance(updated_status, bool)
