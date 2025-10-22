"""
Comparison Telemetry Module

Implements structured logging and CloudWatch metrics publishing for
comparison validation between old and new Lambda implementations.

Supports Story 5.4: Implement Monitoring Infrastructure
- AC 1: Structured comparison logs with SMS counts, DB operations, Telegram events
- AC 2: Custom metrics publishing to naver-sms/comparison/* namespace
- AC 3: Character-by-character SMS payload comparisons and parity checks
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

import boto3


def _get_iso_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ComparisonStatus(Enum):
    """Comparison status codes."""

    MATCH = "match"
    MISMATCH = "mismatch"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class SMSComparison:
    """SMS payload comparison result."""

    sms_id: str
    booking_id: str
    store_id: str
    phone_masked: str
    template_type: str  # "confirmation", "guide", "event"
    old_payload: Optional[str] = None
    new_payload: Optional[str] = None
    match: bool = False
    mismatch_details: str = ""
    character_diff_count: int = 0
    timestamp: str = field(default_factory=_get_iso_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class DatabaseOperationComparison:
    """DynamoDB operation comparison result."""

    operation_id: str
    booking_id: str
    operation_type: str  # "put_item", "update_item"
    table_name: str
    old_result: Optional[Dict[str, Any]] = None
    new_result: Optional[Dict[str, Any]] = None
    match: bool = False
    mismatch_details: str = ""
    timestamp: str = field(default_factory=_get_iso_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class TelegramEventComparison:
    """Telegram notification comparison result."""

    event_id: str
    booking_id: str
    event_type: str  # "summary", "error"
    old_sent: bool = False
    new_sent: bool = False
    old_message: Optional[str] = None
    new_message: Optional[str] = None
    match: bool = False
    mismatch_details: str = ""
    timestamp: str = field(default_factory=_get_iso_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ComparisonSummary:
    """Overall comparison run summary."""

    run_id: str
    lambda_version: str  # "legacy" or "new"
    invocation_time: str
    bookings_processed: int = 0
    sms_comparisons: List[SMSComparison] = field(default_factory=list)
    db_comparisons: List[DatabaseOperationComparison] = field(default_factory=list)
    telegram_comparisons: List[TelegramEventComparison] = field(default_factory=list)
    total_mismatches: int = 0
    match_percentage: float = 0.0
    error_count: int = 0
    processing_duration_ms: float = 0.0
    sms_sent_count: int = 0
    db_operations_count: int = 0
    telegram_events_count: int = 0

    def calculate_match_percentage(self) -> float:
        """Calculate overall match percentage."""
        total_comparisons = (
            len(self.sms_comparisons) + len(self.db_comparisons) + len(self.telegram_comparisons)
        )
        if total_comparisons == 0:
            return 100.0

        matched = (
            sum(1 for c in self.sms_comparisons if c.match)
            + sum(1 for c in self.db_comparisons if c.match)
            + sum(1 for c in self.telegram_comparisons if c.match)
        )

        return (matched / total_comparisons) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert nested dataclass instances to dicts
        data["sms_comparisons"] = [c.to_dict() for c in self.sms_comparisons]
        data["db_comparisons"] = [c.to_dict() for c in self.db_comparisons]
        data["telegram_comparisons"] = [c.to_dict() for c in self.telegram_comparisons]
        data["match_percentage"] = self.calculate_match_percentage()
        return data


class ComparisonMetricsPublisher:
    """
    Publishes comparison metrics to CloudWatch.

    Implements AC 2: Custom metrics for operational visibility
    - SMS sent counts (old vs new)
    - Match percentage
    - Discrepancy count
    - Error rates
    """

    NAMESPACE = "naver-sms/comparison"

    def __init__(self, region_name: str = "ap-northeast-2"):
        """
        Initialize metrics publisher.

        Args:
            region_name: AWS region for CloudWatch
        """
        self.region_name = region_name
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=region_name)
        self.logger = logging.getLogger(__name__)

    def publish_comparison_summary(self, summary: ComparisonSummary) -> None:
        """
        Publish comparison summary metrics to CloudWatch.

        Publishes:
        - sms_sent_old: SMS sent by old Lambda
        - sms_sent_new: SMS sent by new Lambda
        - match_percentage: Overall match percentage
        - discrepancies: Number of mismatches
        - error_count: Number of errors

        Args:
            summary: ComparisonSummary instance with results

        Raises:
            Exception: If CloudWatch publish fails (will be logged but not raised)
        """
        try:
            match_percentage = summary.calculate_match_percentage()
            timestamp = datetime.now(timezone.utc)

            metric_data = [
                {
                    "MetricName": "sms_sent_old",
                    "Value": summary.sms_sent_count,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {"Name": "LambdaVersion", "Value": "legacy"},
                        {"Name": "ComparisonRun", "Value": summary.run_id},
                    ],
                },
                {
                    "MetricName": "sms_sent_new",
                    "Value": summary.sms_sent_count,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {"Name": "LambdaVersion", "Value": "new"},
                        {"Name": "ComparisonRun", "Value": summary.run_id},
                    ],
                },
                {
                    "MetricName": "match_percentage",
                    "Value": match_percentage,
                    "Unit": "Percent",
                    "Timestamp": timestamp,
                    "Dimensions": [{"Name": "ComparisonRun", "Value": summary.run_id}],
                },
                {
                    "MetricName": "discrepancies",
                    "Value": summary.total_mismatches,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [{"Name": "ComparisonRun", "Value": summary.run_id}],
                },
                {
                    "MetricName": "error_count",
                    "Value": summary.error_count,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [{"Name": "ComparisonRun", "Value": summary.run_id}],
                },
                {
                    "MetricName": "processing_duration_ms",
                    "Value": summary.processing_duration_ms,
                    "Unit": "Milliseconds",
                    "Timestamp": timestamp,
                    "Dimensions": [{"Name": "ComparisonRun", "Value": summary.run_id}],
                },
            ]

            # Publish in batches (CloudWatch limit: 20 metrics per request)
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i : i + 20]
                self.cloudwatch_client.put_metric_data(Namespace=self.NAMESPACE, MetricData=batch)
                self.logger.debug(f"Published {len(batch)} metrics to CloudWatch")

            self.logger.info(
                f"Comparison metrics published: match_percentage={match_percentage:.1f}%, "
                f"discrepancies={summary.total_mismatches}, sms_sent={summary.sms_sent_count}"
            )

        except Exception as e:
            self.logger.error(f"Failed to publish comparison metrics: {e}")
            # Don't raise - metrics publishing should not fail the Lambda

    def publish_metrics(
        self,
        booking_id: str,
        legacy_sms_count: int,
        refactored_sms_count: int,
        match_percentage: float,
        critical_mismatches: int,
        warning_mismatches: int,
    ) -> None:
        """
        Publish individual booking comparison metrics to CloudWatch.

        Args:
            booking_id: Unique booking identifier
            legacy_sms_count: SMS count from legacy Lambda
            refactored_sms_count: SMS count from new Lambda
            match_percentage: Percentage of matching outputs
            critical_mismatches: Count of critical discrepancies
            warning_mismatches: Count of warning discrepancies
        """
        try:
            timestamp = datetime.now(timezone.utc)

            metric_data = [
                {
                    "MetricName": "sms_sent_old",
                    "Value": legacy_sms_count,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {"Name": "LambdaVersion", "Value": "legacy"},
                        {"Name": "BookingId", "Value": booking_id},
                    ],
                },
                {
                    "MetricName": "sms_sent_new",
                    "Value": refactored_sms_count,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [
                        {"Name": "LambdaVersion", "Value": "new"},
                        {"Name": "BookingId", "Value": booking_id},
                    ],
                },
                {
                    "MetricName": "match_percentage",
                    "Value": match_percentage,
                    "Unit": "Percent",
                    "Timestamp": timestamp,
                    "Dimensions": [{"Name": "BookingId", "Value": booking_id}],
                },
                {
                    "MetricName": "critical_mismatches",
                    "Value": critical_mismatches,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [{"Name": "BookingId", "Value": booking_id}],
                },
                {
                    "MetricName": "warning_mismatches",
                    "Value": warning_mismatches,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                    "Dimensions": [{"Name": "BookingId", "Value": booking_id}],
                },
            ]

            self.cloudwatch_client.put_metric_data(Namespace=self.NAMESPACE, MetricData=metric_data)
            self.logger.debug(f"Published metrics for booking {booking_id}")

        except Exception as e:
            self.logger.error(f"Failed to publish metrics for booking {booking_id}: {e}")
            # Don't raise - metrics publishing should not fail the Lambda


class ComparisonLogger:
    """
    Structured logger for comparison telemetry.

    Implements AC 1: Structured logs queryable through CloudWatch Logs Insights
    - Fields: booking_id, store_id, sms_type, match_status, mismatch_details
    - Supports AC 6: Integration with existing CloudWatch queries
    """

    def __init__(self, run_id: str, lambda_version: str = "new"):
        """
        Initialize comparison logger.

        Args:
            run_id: Unique identifier for this comparison run
            lambda_version: "legacy" or "new"
        """
        self.run_id = run_id
        self.lambda_version = lambda_version
        self.logger = logging.getLogger(__name__)

    def log_sms_comparison(self, comparison: SMSComparison) -> None:
        """
        Log SMS comparison result.

        Implements AC 1 & 3: Character-by-character comparisons with mismatch details

        Args:
            comparison: SMSComparison instance
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": "INFO",
            "run_id": self.run_id,
            "lambda_version": self.lambda_version,
            "event_type": "sms_comparison",
            "booking_id": comparison.booking_id,
            "store_id": comparison.store_id,
            "phone_masked": comparison.phone_masked,
            "template_type": comparison.template_type,
            "match": comparison.match,
            "character_diff_count": comparison.character_diff_count,
            "mismatch_details": comparison.mismatch_details,
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))

    def log_db_operation_comparison(self, comparison: DatabaseOperationComparison) -> None:
        """
        Log DynamoDB operation comparison result.

        Implements AC 1: Structured DynamoDB mutation tracking

        Args:
            comparison: DatabaseOperationComparison instance
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": "INFO",
            "run_id": self.run_id,
            "lambda_version": self.lambda_version,
            "event_type": "db_operation_comparison",
            "booking_id": comparison.booking_id,
            "operation_type": comparison.operation_type,
            "table_name": comparison.table_name,
            "match": comparison.match,
            "mismatch_details": comparison.mismatch_details,
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))

    def log_telegram_event_comparison(self, comparison: TelegramEventComparison) -> None:
        """
        Log Telegram event comparison result.

        Implements AC 1: Telegram notification tracking

        Args:
            comparison: TelegramEventComparison instance
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": "INFO",
            "run_id": self.run_id,
            "lambda_version": self.lambda_version,
            "event_category": "telegram_comparison",
            "booking_id": comparison.booking_id,
            "event_type": comparison.event_type,
            "old_sent": comparison.old_sent,
            "new_sent": comparison.new_sent,
            "match": comparison.match,
            "mismatch_details": comparison.mismatch_details,
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))

    def log_summary(self, summary: ComparisonSummary) -> None:
        """
        Log comparison run summary.

        Implements AC 1: High-level summary for operations dashboard

        Args:
            summary: ComparisonSummary instance
        """
        match_percentage = summary.calculate_match_percentage()
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": "INFO",
            "run_id": summary.run_id,
            "lambda_version": summary.lambda_version,
            "event_type": "comparison_summary",
            "bookings_processed": summary.bookings_processed,
            "sms_comparisons_count": len(summary.sms_comparisons),
            "db_comparisons_count": len(summary.db_comparisons),
            "telegram_comparisons_count": len(summary.telegram_comparisons),
            "total_mismatches": summary.total_mismatches,
            "match_percentage": round(match_percentage, 2),
            "error_count": summary.error_count,
            "processing_duration_ms": round(summary.processing_duration_ms, 2),
            "sms_sent_count": summary.sms_sent_count,
            "db_operations_count": summary.db_operations_count,
            "telegram_events_count": summary.telegram_events_count,
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))


def compare_sms_payloads(old_payload: str, new_payload: str) -> Tuple[bool, int, str]:
    """
    Compare SMS payloads character by character.

    Implements AC 3: Character-by-character SMS payload comparisons

    Args:
        old_payload: SMS content from old Lambda
        new_payload: SMS content from new Lambda

    Returns:
        Tuple of (match: bool, diff_count: int, details: str)
    """
    if old_payload == new_payload:
        return True, 0, ""

    # Character-by-character comparison
    diff_count = 0
    diff_positions: list[str] = []
    max_samples = 10  # Increased from 5 to capture more context for debugging

    for i, (old_char, new_char) in enumerate(zip(old_payload, new_payload)):
        if old_char != new_char:
            diff_count += 1
            if len(diff_positions) < max_samples:
                diff_positions.append(f"pos{i}: '{old_char}' → '{new_char}'")

    # Handle length differences
    if len(old_payload) != len(new_payload):
        diff_count += abs(len(old_payload) - len(new_payload))
        diff_positions.append(f"length: {len(old_payload)} → {len(new_payload)}")

    details = (
        f"Differences found: {diff_count} chars. Details: {', '.join(diff_positions[:max_samples])}"
    )
    return False, diff_count, details


def compare_db_records(old_record: Dict[str, Any], new_record: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Compare DynamoDB records for parity.

    Implements AC 3: DynamoDB parity checks

    Args:
        old_record: Record from old Lambda
        new_record: Record from new Lambda

    Returns:
        Tuple of (match: bool, details: str)
    """
    if old_record == new_record:
        return True, ""

    mismatches = []
    all_keys = set(old_record.keys()) | set(new_record.keys())

    for key in all_keys:
        old_value = old_record.get(key)
        new_value = new_record.get(key)
        if old_value != new_value:
            mismatches.append(f"{key}: {old_value} → {new_value}")

    details = f"Mismatches: {', '.join(mismatches[:5])}"
    return False, details
