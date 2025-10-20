"""
Unit tests for comparison monitoring module.

Story 5.4: Implement Monitoring Infrastructure
- AC 1: Structured comparison logs
- AC 2: CloudWatch metrics publishing
- AC 3: Payload comparison functions
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock, call

from src.monitoring.comparison import (
    ComparisonStatus,
    SMSComparison,
    DatabaseOperationComparison,
    TelegramEventComparison,
    ComparisonSummary,
    ComparisonMetricsPublisher,
    ComparisonLogger,
    compare_sms_payloads,
    compare_db_records,
)


class TestSMSComparison:
    """Test SMSComparison dataclass."""

    def test_sms_comparison_creation(self):
        """Test creating SMS comparison instance."""
        sms = SMSComparison(
            sms_id="sms_001",
            booking_id="booking_123",
            store_id="store_456",
            phone_masked="***1234",
            template_type="confirmation",
        )
        assert sms.sms_id == "sms_001"
        assert sms.template_type == "confirmation"
        assert sms.match is False
        assert sms.character_diff_count == 0

    def test_sms_comparison_to_dict(self):
        """Test SMS comparison serialization."""
        sms = SMSComparison(
            sms_id="sms_001",
            booking_id="booking_123",
            store_id="store_456",
            phone_masked="***1234",
            template_type="confirmation",
            match=True,
        )
        data = sms.to_dict()
        assert data["sms_id"] == "sms_001"
        assert data["match"] is True
        assert "timestamp" in data


class TestComparisonSummary:
    """Test ComparisonSummary dataclass."""

    def test_calculate_match_percentage_perfect_match(self):
        """Test 100% match calculation."""
        summary = ComparisonSummary(
            run_id="run_001",
            lambda_version="new",
            invocation_time=datetime.now(timezone.utc).isoformat(),
        )
        # Add matching comparisons
        summary.sms_comparisons = [
            SMSComparison(
                sms_id="sms_001",
                booking_id="booking_123",
                store_id="store_456",
                phone_masked="***1234",
                template_type="confirmation",
                match=True,
            ),
            SMSComparison(
                sms_id="sms_002",
                booking_id="booking_123",
                store_id="store_456",
                phone_masked="***1234",
                template_type="confirmation",
                match=True,
            ),
        ]
        match_pct = summary.calculate_match_percentage()
        assert match_pct == 100.0

    def test_calculate_match_percentage_partial_match(self):
        """Test partial match percentage calculation."""
        summary = ComparisonSummary(
            run_id="run_001",
            lambda_version="new",
            invocation_time=datetime.now(timezone.utc).isoformat(),
        )
        # Add 3 matching, 1 mismatching
        for i in range(3):
            summary.sms_comparisons.append(
                SMSComparison(
                    sms_id=f"sms_{i}",
                    booking_id="booking_123",
                    store_id="store_456",
                    phone_masked="***1234",
                    template_type="confirmation",
                    match=True,
                )
            )
        summary.sms_comparisons.append(
            SMSComparison(
                sms_id="sms_mismatch",
                booking_id="booking_123",
                store_id="store_456",
                phone_masked="***1234",
                template_type="confirmation",
                match=False,
            )
        )
        match_pct = summary.calculate_match_percentage()
        assert match_pct == 75.0

    def test_calculate_match_percentage_no_comparisons(self):
        """Test 100% match when no comparisons (edge case)."""
        summary = ComparisonSummary(
            run_id="run_001",
            lambda_version="new",
            invocation_time=datetime.now(timezone.utc).isoformat(),
        )
        match_pct = summary.calculate_match_percentage()
        assert match_pct == 100.0


class TestCompareSMSPayloads:
    """Test SMS payload comparison function."""

    def test_identical_payloads(self):
        """Test comparison of identical payloads."""
        payload = "Hello, your booking is confirmed!"
        match, diff_count, details = compare_sms_payloads(payload, payload)
        assert match is True
        assert diff_count == 0
        assert details == ""

    def test_different_payloads_single_char(self):
        """Test comparison with single character difference."""
        old = "Hello, your booking is confirmed!"
        new = "Hello, your booking is confirmedX"
        match, diff_count, details = compare_sms_payloads(old, new)
        assert match is False
        assert diff_count == 1
        assert "pos32" in details or "length" in details  # ! at pos 32 changed to X

    def test_different_payloads_multiple_chars(self):
        """Test comparison with multiple character differences."""
        old = "Hello world"
        new = "Hallo werld"
        match, diff_count, details = compare_sms_payloads(old, new)
        assert match is False
        assert diff_count == 2
        assert "pos1" in details  # e→a
        assert "pos7" in details  # o→e

    def test_different_length_payloads(self):
        """Test comparison of different length payloads."""
        old = "Short"
        new = "Much longer string"
        match, diff_count, details = compare_sms_payloads(old, new)
        assert match is False
        assert diff_count > 0
        assert "length" in details

    def test_empty_payloads(self):
        """Test comparison of empty payloads."""
        match, diff_count, details = compare_sms_payloads("", "")
        assert match is True
        assert diff_count == 0


class TestCompareDBRecords:
    """Test DynamoDB record comparison function."""

    def test_identical_records(self):
        """Test comparison of identical records."""
        record = {"id": "123", "name": "test", "status": "active"}
        match, details = compare_db_records(record, record)
        assert match is True
        assert details == ""

    def test_different_record_values(self):
        """Test comparison with different values."""
        old = {"id": "123", "name": "old_name", "status": "active"}
        new = {"id": "123", "name": "new_name", "status": "active"}
        match, details = compare_db_records(old, new)
        assert match is False
        assert "name" in details
        assert "old_name" in details
        assert "new_name" in details

    def test_different_keys_old_has_extra(self):
        """Test comparison when old record has extra key."""
        old = {"id": "123", "name": "test", "deprecated": "value"}
        new = {"id": "123", "name": "test"}
        match, details = compare_db_records(old, new)
        assert match is False
        assert "deprecated" in details

    def test_different_keys_new_has_extra(self):
        """Test comparison when new record has extra key."""
        old = {"id": "123", "name": "test"}
        new = {"id": "123", "name": "test", "new_field": "value"}
        match, details = compare_db_records(old, new)
        assert match is False
        assert "new_field" in details


class TestComparisonLogger:
    """Test structured comparison logging."""

    def test_logger_initialization(self):
        """Test logger creation."""
        logger = ComparisonLogger(run_id="run_001", lambda_version="new")
        assert logger.run_id == "run_001"
        assert logger.lambda_version == "new"

    @patch("logging.getLogger")
    def test_log_sms_comparison(self, mock_get_logger):
        """Test SMS comparison logging."""
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        logger = ComparisonLogger(run_id="run_001", lambda_version="new")
        sms = SMSComparison(
            sms_id="sms_001",
            booking_id="booking_123",
            store_id="store_456",
            phone_masked="***1234",
            template_type="confirmation",
            match=True,
        )
        logger.log_sms_comparison(sms)

        # Verify logger.info was called with JSON
        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        log_data = json.loads(call_args)
        assert log_data["event_type"] == "sms_comparison"
        assert log_data["booking_id"] == "booking_123"
        assert log_data["match"] is True

    @patch("logging.getLogger")
    def test_log_telegram_event_comparison_field_naming(self, mock_get_logger):
        """Test Telegram logging uses correct field names (event_category and event_type)."""
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        logger = ComparisonLogger(run_id="run_001", lambda_version="new")
        telegram = TelegramEventComparison(
            event_id="evt_001",
            booking_id="booking_123",
            event_type="summary",
            old_sent=True,
            new_sent=True,
            match=True,
        )
        logger.log_telegram_event_comparison(telegram)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        log_data = json.loads(call_args)
        assert log_data["event_category"] == "telegram_comparison"
        assert log_data["event_type"] == "summary"
        assert log_data["match"] is True

    @patch("logging.getLogger")
    def test_log_summary(self, mock_get_logger):
        """Test comparison run summary logging."""
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance

        summary = ComparisonSummary(
            run_id="run_001",
            lambda_version="new",
            invocation_time=datetime.now(timezone.utc).isoformat(),
            bookings_processed=10,
            total_mismatches=0,
            error_count=0,
            processing_duration_ms=1234.5,
            sms_sent_count=15,
        )
        logger = ComparisonLogger(run_id="run_001", lambda_version="new")
        logger.log_summary(summary)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        log_data = json.loads(call_args)
        assert log_data["event_type"] == "comparison_summary"
        assert log_data["bookings_processed"] == 10
        assert log_data["match_percentage"] == 100.0


class TestComparisonMetricsPublisher:
    """Test CloudWatch metrics publishing."""

    @patch("boto3.client")
    def test_publisher_initialization(self, mock_boto_client):
        """Test metrics publisher creation."""
        publisher = ComparisonMetricsPublisher(region_name="ap-northeast-2")
        assert publisher.region_name == "ap-northeast-2"
        mock_boto_client.assert_called_once_with("cloudwatch", region_name="ap-northeast-2")

    @patch("boto3.client")
    def test_publish_comparison_summary(self, mock_boto_client):
        """Test publishing comparison metrics to CloudWatch."""
        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw

        publisher = ComparisonMetricsPublisher(region_name="ap-northeast-2")
        summary = ComparisonSummary(
            run_id="run_001",
            lambda_version="new",
            invocation_time=datetime.now(timezone.utc).isoformat(),
            bookings_processed=10,
            total_mismatches=0,
            error_count=0,
            processing_duration_ms=1234.5,
            sms_sent_count=15,
        )
        publisher.publish_comparison_summary(summary)

        # Verify put_metric_data was called
        mock_cw.put_metric_data.assert_called()
        call_args = mock_cw.put_metric_data.call_args
        assert call_args[1]["Namespace"] == "naver-sms/comparison"
        metrics = call_args[1]["MetricData"]
        assert len(metrics) == 6  # 6 metrics

    @patch("boto3.client")
    def test_publish_handles_errors(self, mock_boto_client):
        """Test metrics publishing handles CloudWatch errors gracefully."""
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = Exception("CloudWatch error")
        mock_boto_client.return_value = mock_cw

        publisher = ComparisonMetricsPublisher(region_name="ap-northeast-2")
        summary = ComparisonSummary(
            run_id="run_001",
            lambda_version="new",
            invocation_time=datetime.now(timezone.utc).isoformat(),
            bookings_processed=1,
            total_mismatches=0,
            error_count=0,
            processing_duration_ms=100.0,
            sms_sent_count=1,
        )
        # Should not raise exception
        publisher.publish_comparison_summary(summary)

    @patch("boto3.client")
    def test_publish_batches_metrics(self, mock_boto_client):
        """Test metrics are published in batches of 20."""
        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw

        publisher = ComparisonMetricsPublisher(region_name="ap-northeast-2")
        summary = ComparisonSummary(
            run_id="run_001",
            lambda_version="new",
            invocation_time=datetime.now(timezone.utc).isoformat(),
            bookings_processed=100,
            total_mismatches=0,
            error_count=0,
            processing_duration_ms=100.0,
            sms_sent_count=100,
        )
        publisher.publish_comparison_summary(summary)

        # Verify batching (6 metrics should fit in 1 call)
        assert mock_cw.put_metric_data.call_count == 1
        metrics = mock_cw.put_metric_data.call_args[1]["MetricData"]
        assert len(metrics) == 6


class TestComparisonStatus:
    """Test ComparisonStatus enum."""

    def test_status_values(self):
        """Test comparison status enum values."""
        assert ComparisonStatus.MATCH.value == "match"
        assert ComparisonStatus.MISMATCH.value == "mismatch"
        assert ComparisonStatus.ERROR.value == "error"
        assert ComparisonStatus.PENDING.value == "pending"
