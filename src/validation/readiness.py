"""Automated readiness gate validator for validation campaigns."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class GoNoGoDecision(Enum):
    """Readiness decision for production cutover."""

    GO = "GO"
    NO_GO = "NO_GO"
    GO_WITH_CAUTION = "GO_WITH_CAUTION"


@dataclass
class ReadinessCriteria:
    """Individual readiness criterion evaluation."""

    name: str
    description: str
    required: bool
    status: bool
    evidence: str
    impact: str


@dataclass
class ReadinessReport:
    """Automated readiness report."""

    campaign_id: str
    generated_at: str
    decision: GoNoGoDecision
    confidence_level: float
    criteria_results: List[ReadinessCriteria]
    summary: str
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "generated_at": self.generated_at,
            "decision": self.decision.value,
            "confidence_level": self.confidence_level,
            "criteria": [
                {
                    "name": c.name,
                    "description": c.description,
                    "required": c.required,
                    "status": c.status,
                    "evidence": c.evidence,
                    "impact": c.impact,
                }
                for c in self.criteria_results
            ],
            "summary": self.summary,
            "recommendations": self.recommendations,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class ReadinessValidator:
    """Automated readiness gate validator (OPS-001)."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def validate_campaign(
        self,
        campaign_id: str,
        comparison_stats: List[Dict[str, Any]],
        slack_metrics: Dict[str, Any],
        cloudwatch_metrics: Dict[str, Any],
    ) -> ReadinessReport:
        criteria_results = []

        criteria_results.append(self._validate_parity_100_percent(comparison_stats))
        criteria_results.append(self._validate_zero_critical_mismatches(comparison_stats))
        criteria_results.append(self._validate_sms_channel(comparison_stats))
        criteria_results.append(self._validate_dynamodb_channel(comparison_stats))
        criteria_results.append(self._validate_telegram_channel(comparison_stats))
        criteria_results.append(self._validate_slack_webhook_integration(slack_metrics))
        criteria_results.append(self._validate_cloudwatch_metrics(cloudwatch_metrics))
        criteria_results.append(self._validate_comparison_mode_enabled())
        criteria_results.append(self._validate_msc1_criteria(comparison_stats, slack_metrics))

        decision = self._calculate_decision(criteria_results)
        confidence = self._calculate_confidence(criteria_results)
        summary = self._generate_summary(criteria_results, decision)
        recommendations = self._generate_recommendations(criteria_results, decision)

        return ReadinessReport(
            campaign_id=campaign_id,
            generated_at=datetime.utcnow().isoformat(),
            decision=decision,
            confidence_level=confidence,
            criteria_results=criteria_results,
            summary=summary,
            recommendations=recommendations,
        )

    def _validate_parity_100_percent(
        self, comparison_stats: List[Dict[str, Any]]
    ) -> ReadinessCriteria:
        total = len(comparison_stats)
        passed = sum(1 for stat in comparison_stats if stat.get("parity_status") == "PASS")
        parity_percent = (passed / total * 100) if total > 0 else 0

        status = parity_percent == 100.0
        return ReadinessCriteria(
            name="100% Parity Across All Bookings",
            description="All compared bookings show 100% parity between legacy and refactored Lambda",
            required=True,
            status=status,
            evidence=f"{passed}/{total} bookings passed ({parity_percent:.1f}%)",
            impact="If failed: Some bookings have mismatches; investigate before cutover",
        )

    def _validate_zero_critical_mismatches(
        self, comparison_stats: List[Dict[str, Any]]
    ) -> ReadinessCriteria:
        total_critical = sum(stat.get("critical_mismatches", 0) for stat in comparison_stats)
        status = total_critical == 0
        return ReadinessCriteria(
            name="Zero Critical Mismatches",
            description="No critical severity mismatches detected across all comparisons",
            required=True,
            status=status,
            evidence=f"{total_critical} critical mismatches found",
            impact="If failed: Critical issues must be remediated before cutover",
        )

    def _validate_sms_channel(self, comparison_stats: List[Dict[str, Any]]) -> ReadinessCriteria:
        # Inspect actual comparison data for mismatches
        total_critical = sum(stat.get("critical_mismatches", 0) for stat in comparison_stats)
        failed_bookings = sum(1 for stat in comparison_stats if stat.get("parity_status") == "FAIL")
        total_bookings = len(comparison_stats)

        status = total_critical == 0 and failed_bookings == 0
        evidence = (
            f"SMS channel: {failed_bookings}/{total_bookings} bookings failed, "
            f"{total_critical} critical mismatches across all channels"
        )
        return ReadinessCriteria(
            name="SMS Channel Parity",
            description="SMS notifications match between legacy and refactored Lambda",
            required=True,
            status=status,
            evidence=evidence,
            impact="If failed: SMS messages may not send correctly",
        )

    def _validate_dynamodb_channel(
        self, comparison_stats: List[Dict[str, Any]]
    ) -> ReadinessCriteria:
        # Inspect actual comparison data for mismatches
        total_critical = sum(stat.get("critical_mismatches", 0) for stat in comparison_stats)
        failed_bookings = sum(1 for stat in comparison_stats if stat.get("parity_status") == "FAIL")
        total_bookings = len(comparison_stats)

        status = total_critical == 0 and failed_bookings == 0
        evidence = (
            f"DynamoDB channel: {failed_bookings}/{total_bookings} bookings failed, "
            f"{total_critical} critical mismatches across all channels"
        )
        return ReadinessCriteria(
            name="DynamoDB Channel Parity",
            description="DynamoDB record writes match between legacy and refactored Lambda",
            required=True,
            status=status,
            evidence=evidence,
            impact="If failed: Booking state tracking may diverge",
        )

    def _validate_telegram_channel(
        self, comparison_stats: List[Dict[str, Any]]
    ) -> ReadinessCriteria:
        # Inspect actual comparison data for mismatches
        total_critical = sum(stat.get("critical_mismatches", 0) for stat in comparison_stats)
        failed_bookings = sum(1 for stat in comparison_stats if stat.get("parity_status") == "FAIL")
        total_bookings = len(comparison_stats)

        status = total_critical == 0 and failed_bookings == 0
        evidence = (
            f"Telegram channel: {failed_bookings}/{total_bookings} bookings failed, "
            f"{total_critical} critical mismatches across all channels"
        )
        return ReadinessCriteria(
            name="Telegram Channel Parity",
            description="Telegram notifications match between legacy and refactored Lambda",
            required=True,
            status=status,
            evidence=evidence,
            impact="If failed: Telegram alerts may not fire correctly",
        )

    def _validate_slack_webhook_integration(
        self, slack_metrics: Dict[str, Any]
    ) -> ReadinessCriteria:
        webhooks_configured = slack_metrics.get("webhooks_configured", 0)
        webhooks_tested = slack_metrics.get("webhooks_tested", 0)
        webhook_failures = slack_metrics.get("webhook_failures", 0)

        status = webhooks_configured > 0 and webhook_failures == 0
        return ReadinessCriteria(
            name="Slack Webhook Integration",
            description="Slack webhook endpoints configured and tested successfully",
            required=True,
            status=status,
            evidence=(
                "Webhooks: "
                f"{webhooks_configured} configured, {webhooks_tested} tested, {webhook_failures} failures"
            ),
            impact="If failed: Slack notifications may not deliver during campaign",
        )

    def _validate_cloudwatch_metrics(self, cloudwatch_metrics: Dict[str, Any]) -> ReadinessCriteria:
        metrics_published = cloudwatch_metrics.get("metrics_published", 0)
        metrics_failed = cloudwatch_metrics.get("metrics_failed", 0)
        dashboard_verified = cloudwatch_metrics.get("dashboard_verified", False)

        status = metrics_published > 0 and metrics_failed == 0 and dashboard_verified
        return ReadinessCriteria(
            name="CloudWatch Metrics Published",
            description="Campaign metrics successfully published to CloudWatch",
            required=True,
            status=status,
            evidence=(
                "Metrics: "
                f"{metrics_published} published, {metrics_failed} failures, dashboard verified: {dashboard_verified}"
            ),
            impact="If failed: Monitoring and alerting during campaign will not work",
        )

    def _validate_comparison_mode_enabled(self) -> ReadinessCriteria:
        # Read actual COMPARISON_MODE_ENABLED environment variable
        import os

        comparison_mode_value = os.getenv("COMPARISON_MODE_ENABLED", "false")
        comparison_mode_active = comparison_mode_value == "true"

        evidence = (
            f"COMPARISON_MODE_ENABLED={comparison_mode_value} "
            f"({'ACTIVE - SMS disabled' if comparison_mode_active else 'INACTIVE - SMS WILL SEND'})"
        )
        return ReadinessCriteria(
            name="Comparison Mode Enabled (No Production SMS)",
            description="Comparison mode is active and prevents production SMS sends",
            required=True,
            status=comparison_mode_active,
            evidence=evidence,
            impact="If failed: Validation campaign could send real SMS messages",
        )

    def _validate_msc1_criteria(
        self,
        comparison_stats: List[Dict[str, Any]],
        slack_metrics: Dict[str, Any],
    ) -> ReadinessCriteria:
        total = len(comparison_stats)
        passed = sum(1 for stat in comparison_stats if stat.get("parity_status") == "PASS")
        critical = sum(stat.get("critical_mismatches", 0) for stat in comparison_stats)
        slack_working = slack_metrics.get("webhooks_configured", 0) > 0

        msc1_met = passed == total and critical == 0 and slack_working
        return ReadinessCriteria(
            name="MSC1 Success Criteria Met",
            description="PRD MSC1: 100% parity, all channels working, zero critical mismatches",
            required=True,
            status=msc1_met,
            evidence=f"Parity: {passed}/{total}, Critical: {critical}, Slack: {slack_working}",
            impact="If failed: Story acceptance criteria not met; cannot cutover",
        )

    def _calculate_decision(self, criteria_results: List[ReadinessCriteria]) -> GoNoGoDecision:
        required_criteria = [criterion for criterion in criteria_results if criterion.required]
        required_passed = sum(1 for criterion in required_criteria if criterion.status)
        if required_passed == len(required_criteria):
            return GoNoGoDecision.GO
        return GoNoGoDecision.NO_GO

    def _calculate_confidence(self, criteria_results: List[ReadinessCriteria]) -> float:
        total = len(criteria_results)
        passed = sum(1 for criterion in criteria_results if criterion.status)
        if total == 0:
            return 0.0
        return passed / total

    def _generate_summary(
        self, criteria_results: List[ReadinessCriteria], decision: GoNoGoDecision
    ) -> str:
        required_criteria = [criterion for criterion in criteria_results if criterion.required]
        required_passed = sum(1 for criterion in required_criteria if criterion.status)

        if decision == GoNoGoDecision.GO:
            return (
                "✅ READY FOR PRODUCTION CUTOVER\n"
                f"All {len(required_criteria)} required readiness criteria met. "
                "100% functional parity confirmed across all channels. "
                "MSC1 success criteria satisfied."
            )

        failed_criteria = [
            criterion.name
            for criterion in criteria_results
            if not criterion.status and criterion.required
        ]
        return (
            "❌ NOT READY FOR PRODUCTION CUTOVER\n"
            f"{required_passed}/{len(required_criteria)} required criteria passed. "
            f"Failed criteria: {', '.join(failed_criteria)}. "
            "Issues must be remediated before cutover approval."
        )

    def _generate_recommendations(
        self, criteria_results: List[ReadinessCriteria], decision: GoNoGoDecision
    ) -> List[str]:
        recommendations: List[str] = []
        if decision == GoNoGoDecision.GO:
            recommendations.append("✅ Proceed with production cutover")
            recommendations.append("✅ Enable EventBridge trigger for new Lambda")
            recommendations.append("✅ Monitor new Lambda metrics for first 24 hours")
            recommendations.append("✅ Keep rollback procedure ready (< 15 minute SLA)")
            return recommendations

        failed_criteria = [
            criterion
            for criterion in criteria_results
            if not criterion.status and criterion.required
        ]
        for criterion in failed_criteria:
            recommendations.append(f"❌ Fix: {criterion.name}")
            recommendations.append(f"   Issue: {criterion.impact}")
        recommendations.append("Re-run validation campaign after fixes applied")
        return recommendations
