"""
Automated Readiness Gate Validator

Story 5.5 OPS-001: Automated validation of go/no-go decision criteria.

Validates that:
- 100% parity across all notification channels (SMS, DynamoDB, Telegram, Slack)
- Zero critical mismatches detected
- All success criteria met per PRD
- MSC1 compliance confirmed
- Slack webhook integration working
- Automated go/no-go recommendation generated
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

import pytest

from src.validation.readiness import (
    GoNoGoDecision,
    ReadinessCriteria,
    ReadinessReport,
    ReadinessValidator,
)

logger = logging.getLogger(__name__)


class TestReadinessValidator:
    """Tests for automated readiness validator."""

    def test_validator_initialization(self):
        """OPS-001: Validator can be initialized."""
        validator = ReadinessValidator()

        assert validator is not None

    def test_all_criteria_pass_results_in_go_decision(self):
        """OPS-001: All passing criteria results in GO decision."""
        validator = ReadinessValidator()

        comparison_stats = [
            {"booking_id": "b-001", "parity_status": "PASS", "critical_mismatches": 0},
            {"booking_id": "b-002", "parity_status": "PASS", "critical_mismatches": 0},
            {"booking_id": "b-003", "parity_status": "PASS", "critical_mismatches": 0},
        ]

        slack_metrics = {
            "webhooks_configured": 2,
            "webhooks_tested": 2,
            "webhook_failures": 0,
        }

        cloudwatch_metrics = {
            "metrics_published": 50,
            "metrics_failed": 0,
            "dashboard_verified": True,
        }

        report = validator.validate_campaign(
            campaign_id="test-campaign",
            comparison_stats=comparison_stats,
            slack_metrics=slack_metrics,
            cloudwatch_metrics=cloudwatch_metrics,
        )

        assert report.decision == GoNoGoDecision.GO
        assert report.confidence_level == 1.0

    def test_critical_mismatch_results_in_no_go_decision(self):
        """OPS-001: Critical mismatches result in NO_GO decision."""
        validator = ReadinessValidator()

        comparison_stats = [
            {"booking_id": "b-001", "parity_status": "PASS", "critical_mismatches": 0},
            {"booking_id": "b-002", "parity_status": "FAIL", "critical_mismatches": 2},
            {"booking_id": "b-003", "parity_status": "PASS", "critical_mismatches": 0},
        ]

        slack_metrics = {
            "webhooks_configured": 2,
            "webhooks_tested": 2,
            "webhook_failures": 0,
        }

        cloudwatch_metrics = {
            "metrics_published": 50,
            "metrics_failed": 0,
            "dashboard_verified": True,
        }

        report = validator.validate_campaign(
            campaign_id="test-campaign",
            comparison_stats=comparison_stats,
            slack_metrics=slack_metrics,
            cloudwatch_metrics=cloudwatch_metrics,
        )

        assert report.decision == GoNoGoDecision.NO_GO
        assert report.confidence_level < 1.0

    def test_readiness_report_can_be_serialized_to_json(self):
        """OPS-001: Readiness report serializes to valid JSON."""
        validator = ReadinessValidator()

        comparison_stats = [
            {"booking_id": "b-001", "parity_status": "PASS", "critical_mismatches": 0},
        ]

        slack_metrics = {
            "webhooks_configured": 1,
            "webhooks_tested": 1,
            "webhook_failures": 0,
        }

        cloudwatch_metrics = {
            "metrics_published": 10,
            "metrics_failed": 0,
            "dashboard_verified": True,
        }

        report = validator.validate_campaign(
            campaign_id="test-campaign",
            comparison_stats=comparison_stats,
            slack_metrics=slack_metrics,
            cloudwatch_metrics=cloudwatch_metrics,
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)

        assert parsed["campaign_id"] == "test-campaign"
        assert parsed["decision"] == "GO"
        assert "criteria" in parsed
        assert len(parsed["criteria"]) > 0

    def test_readiness_report_includes_recommendations(self):
        """OPS-001: Readiness report includes actionable recommendations."""
        validator = ReadinessValidator()

        comparison_stats = [
            {"booking_id": "b-001", "parity_status": "PASS", "critical_mismatches": 0},
        ]

        slack_metrics = {
            "webhooks_configured": 1,
            "webhooks_tested": 1,
            "webhook_failures": 0,
        }

        cloudwatch_metrics = {
            "metrics_published": 10,
            "metrics_failed": 0,
            "dashboard_verified": True,
        }

        report = validator.validate_campaign(
            campaign_id="test-campaign",
            comparison_stats=comparison_stats,
            slack_metrics=slack_metrics,
            cloudwatch_metrics=cloudwatch_metrics,
        )

        assert len(report.recommendations) > 0
        assert any("cutover" in r.lower() for r in report.recommendations)
