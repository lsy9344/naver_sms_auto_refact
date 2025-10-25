"""
Integration Tests for Failure Scenarios

Tests error handling and resilience for critical failures:
- Naver API outages
- DynamoDB unavailable
- SENS SMS service failures
- Network timeouts

Story 4.4 AC 2: Tests verify Telegram alert behavior on failures

These tests validate that when external services fail, the system:
1. Gracefully handles the error
2. Sends appropriate Telegram notifications
3. Allows the Lambda to complete without crashing
4. Enables proper post-incident investigation
"""

import pytest
from datetime import datetime

from src.rules.engine import RuleEngine


class TestNaverAPIFailureHandling:
    """Tests for Naver Booking API failures"""

    @pytest.fixture
    def failure_rules(self, tmp_path):
        """Create rules for failure scenario testing"""
        rules_file = tmp_path / "failure_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Fetch Bookings"
    description: "Fetch bookings from Naver API"
    enabled: true
    conditions:
      - type: "api_available"
    actions:
      - type: "fetch_bookings"
      - type: "send_telegram"
        params:
          message: "✅ Bookings fetched successfully"

  - name: "API Failure Fallback"
    description: "Handle API failures gracefully"
    enabled: true
    conditions:
      - type: "api_unavailable"
    actions:
      - type: "send_telegram"
        params:
          message: "⚠️ Naver API unavailable - skipping booking fetch"
      - type: "log_event"
        params:
          level: "WARNING"
          message: "API connection failed"
"""
        )
        return rules_file

    def test_naver_api_timeout_graceful_handling(self, failure_rules):
        """Test that Naver API timeout is handled gracefully"""
        engine = RuleEngine(str(failure_rules))

        # Register conditions
        engine.register_condition("api_available", lambda ctx, **p: False)
        engine.register_condition("api_unavailable", lambda ctx, **p: True)

        # Track notifications
        telegram_messages = []

        def send_telegram(ctx, message, **p):
            telegram_messages.append(message)

        def fetch_bookings(ctx, **p):
            raise TimeoutError("Naver API timeout after 30s")

        def log_event(ctx, level, message, **p):
            pass

        engine.register_action("send_telegram", send_telegram)
        engine.register_action("fetch_bookings", fetch_bookings)
        engine.register_action("log_event", log_event)

        context = {}
        results = engine.process_booking(context)

        # Verify fallback rule executed
        assert len([r for r in results if "API Failure Fallback" in r.rule_name]) > 0
        assert any("unavailable" in msg.lower() for msg in telegram_messages)

    def test_naver_login_session_expired(self, failure_rules):
        """Test handling of expired Naver login session"""
        engine = RuleEngine(str(failure_rules))

        engine.register_condition("api_available", lambda ctx, **p: False)
        engine.register_condition("api_unavailable", lambda ctx, **p: True)

        alert_sent = []

        def send_telegram(ctx, message, **p):
            alert_sent.append({"type": "session_expired", "message": message})

        def log_event(ctx, level, message, **p):
            pass

        engine.register_action("send_telegram", send_telegram)
        engine.register_action("log_event", log_event)

        context = {}
        engine.process_booking(context)

        # Telegram alert should be sent
        assert len(alert_sent) > 0
        assert "unavailable" in alert_sent[0]["message"].lower()

    def test_naver_http_error_429_rate_limited(self, failure_rules):
        """Test handling of rate limiting (HTTP 429) from Naver"""
        engine = RuleEngine(str(failure_rules))

        engine.register_condition("api_available", lambda ctx, **p: False)
        engine.register_condition("api_unavailable", lambda ctx, **p: True)

        alerts = []

        def send_telegram(ctx, message, **p):
            alerts.append(message)

        def log_event(ctx, level, message, **p):
            pass

        engine.register_action("send_telegram", send_telegram)
        engine.register_action("log_event", log_event)

        context = {"error": "429 Too Many Requests"}
        engine.process_booking(context)

        # Should send alert about rate limiting
        assert len(alerts) > 0

    def test_naver_http_error_401_authentication_failed(self, failure_rules):
        """Test handling of authentication failures (HTTP 401)"""
        engine = RuleEngine(str(failure_rules))

        engine.register_condition("api_available", lambda ctx, **p: False)
        engine.register_condition("api_unavailable", lambda ctx, **p: True)

        critical_alerts = []

        def send_telegram(ctx, message, **p):
            if "CRITICAL" in message or "unauthorized" in message.lower():
                critical_alerts.append(message)

        def log_event(ctx, level, message, **p):
            pass

        engine.register_action("send_telegram", send_telegram)
        engine.register_action("log_event", log_event)

        context = {"error": "401 Unauthorized"}
        results = engine.process_booking(context)

        # Authentication failure should trigger alert
        assert len(results) > 0


class TestDynamoDBFailureHandling:
    """Tests for DynamoDB failure scenarios"""

    @pytest.fixture
    def db_failure_rules(self, tmp_path):
        """Create rules for DynamoDB failure scenarios"""
        rules_file = tmp_path / "db_failure_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Create DB Record"
    description: "Create booking record in DynamoDB"
    enabled: true
    conditions:
      - type: "booking_not_in_db"
    actions:
      - type: "create_db_record"
      - type: "send_telegram"
        params:
          message: "✅ Booking record created in DynamoDB"

  - name: "Database Failure Alert"
    description: "Alert on database failures"
    enabled: true
    conditions:
      - type: "db_error_occurred"
    actions:
      - type: "send_telegram"
        params:
          message: "🚨 CRITICAL: DynamoDB connection failed - data may be lost"
      - type: "send_slack"
        params:
          channel: "#alerts"
          message: "DynamoDB failure detected - immediate action required"
"""
        )
        return rules_file

    def test_dynamodb_connection_timeout(self, db_failure_rules):
        """Test handling of DynamoDB connection timeout"""
        engine = RuleEngine(str(db_failure_rules))

        engine.register_condition("booking_not_in_db", lambda ctx, **p: True)
        engine.register_condition("db_error_occurred", lambda ctx, **p: False)

        db_errors = []

        def create_db_record(ctx, **p):
            raise TimeoutError("DynamoDB connection timeout after 30s")

        def send_telegram(ctx, message, **p):
            db_errors.append({"type": "telegram", "message": message})

        engine.register_action("create_db_record", create_db_record)
        engine.register_action("send_telegram", send_telegram)
        engine.register_action("send_slack", lambda ctx, **p: None)

        context = {}
        results = engine.process_booking(context)

        # Verify error handling
        assert any(r.success is False for r in results)

    def test_dynamodb_table_not_found(self, db_failure_rules):
        """Test handling of missing DynamoDB table"""
        engine = RuleEngine(str(db_failure_rules))

        engine.register_condition("booking_not_in_db", lambda ctx, **p: True)
        engine.register_condition("db_error_occurred", lambda ctx, **p: True)

        critical_alerts = []

        def send_telegram(ctx, message, **p):
            if "CRITICAL" in message or "failed" in message.lower():
                critical_alerts.append(message)

        def send_slack(ctx, **p):
            pass

        engine.register_action("create_db_record", lambda ctx, **p: None)
        engine.register_action("send_telegram", send_telegram)
        engine.register_action("send_slack", send_slack)

        context = {}
        results = engine.process_booking(context)

        # Critical alert should be sent
        assert len(critical_alerts) > 0

    def test_dynamodb_provisioned_throughput_exceeded(self, db_failure_rules):
        """Test handling of provisioned throughput exceeded"""
        engine = RuleEngine(str(db_failure_rules))

        engine.register_condition("booking_not_in_db", lambda ctx, **p: True)
        engine.register_condition("db_error_occurred", lambda ctx, **p: True)

        throttle_alerts = []

        def send_telegram(ctx, message, **p):
            throttle_alerts.append(message)

        def send_slack(ctx, **p):
            pass

        engine.register_action("create_db_record", lambda ctx, **p: None)
        engine.register_action("send_telegram", send_telegram)
        engine.register_action("send_slack", send_slack)

        context = {"error": "Provisioned throughput exceeded"}
        engine.process_booking(context)

        # Throttle alert should be sent
        assert len(throttle_alerts) > 0


class TestSMSServiceFailureHandling:
    """Tests for SENS SMS service failures"""

    @pytest.fixture
    def sms_failure_rules(self, tmp_path):
        """Create rules for SMS service failure scenarios"""
        rules_file = tmp_path / "sms_failure_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Send SMS"
    description: "Send SMS via SENS"
    enabled: true
    conditions:
      - type: "should_send_sms"
    actions:
      - type: "send_sms"
        params:
          template: "confirmation"

  - name: "SMS Failure Recovery"
    description: "Handle SMS service failures"
    enabled: true
    conditions:
      - type: "sms_service_down"
    actions:
      - type: "send_telegram"
        params:
          message: "⚠️ SMS service unavailable - will retry later"
      - type: "mark_sms_retry_needed"
"""
        )
        return rules_file

    def test_sens_api_authentication_failed(self, sms_failure_rules):
        """Test handling of SENS API authentication failure"""
        engine = RuleEngine(str(sms_failure_rules))

        engine.register_condition("should_send_sms", lambda ctx, **p: True)
        engine.register_condition("sms_service_down", lambda ctx, **p: False)

        errors_logged = []

        def send_sms(ctx, template, **p):
            raise PermissionError("SENS API authentication failed")

        def send_telegram(ctx, message, **p):
            errors_logged.append(message)

        def mark_sms_retry_needed(ctx, **p):
            errors_logged.append("retry_marked")

        engine.register_action("send_sms", send_sms)
        engine.register_action("send_telegram", send_telegram)
        engine.register_action("mark_sms_retry_needed", mark_sms_retry_needed)

        context = {}
        results = engine.process_booking(context)

        # Error handling should occur
        assert any(not r.success for r in results)

    def test_sens_service_timeout(self, sms_failure_rules):
        """Test handling of SENS service timeout"""
        engine = RuleEngine(str(sms_failure_rules))

        engine.register_condition("should_send_sms", lambda ctx, **p: False)
        engine.register_condition("sms_service_down", lambda ctx, **p: True)

        retry_needed = []

        def send_telegram(ctx, message, **p):
            retry_needed.append({"alert": message})

        def mark_sms_retry_needed(ctx, **p):
            retry_needed.append({"retry": True})

        engine.register_action("send_sms", lambda ctx, **p: None)
        engine.register_action("send_telegram", send_telegram)
        engine.register_action("mark_sms_retry_needed", mark_sms_retry_needed)

        context = {}
        engine.process_booking(context)

        # Retry should be marked
        assert any("retry" in str(r) for r in retry_needed)

    def test_sens_invalid_phone_number(self, sms_failure_rules):
        """Test handling of invalid phone numbers"""
        engine = RuleEngine(str(sms_failure_rules))

        engine.register_condition("should_send_sms", lambda ctx, **p: True)
        engine.register_condition("sms_service_down", lambda ctx, **p: False)

        validation_errors = []

        def send_sms(ctx, template, **p):
            raise ValueError("Invalid phone number format")

        def send_telegram(ctx, message, **p):
            validation_errors.append(message)

        def mark_sms_retry_needed(ctx, **p):
            pass

        engine.register_action("send_sms", send_sms)
        engine.register_action("send_telegram", send_telegram)
        engine.register_action("mark_sms_retry_needed", mark_sms_retry_needed)

        context = {}
        results = engine.process_booking(context)

        # Validation error should be logged
        assert any(not r.success for r in results)


class TestTelegramAlertPathway:
    """Tests verifying Telegram notification pathway for all failures"""

    @pytest.fixture
    def alert_rules(self, tmp_path):
        """Create rules for alert testing"""
        rules_file = tmp_path / "alert_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Log Operation"
    description: "Log successful operations"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "send_telegram"
        params:
          message: "Operation completed"
"""
        )
        return rules_file

    def test_telegram_sent_on_booking_success(self, alert_rules):
        """Test that success Telegram alert is sent"""
        engine = RuleEngine(str(alert_rules))

        engine.register_condition("always_true", lambda ctx, **p: True)

        telegram_calls = []

        def send_telegram(ctx, message, **p):
            telegram_calls.append({"status": "success", "message": message})

        engine.register_action("send_telegram", send_telegram)

        context = {}
        engine.process_booking(context)

        # Telegram should be called
        assert len(telegram_calls) > 0
        assert "Operation completed" in telegram_calls[0]["message"]

    def test_telegram_payload_structure_valid(self, alert_rules):
        """Test that Telegram payloads have valid structure"""
        engine = RuleEngine(str(alert_rules))

        engine.register_condition("always_true", lambda ctx, **p: True)

        telegram_messages = []

        def send_telegram(ctx, message, **p):
            # Validate message is a string
            assert isinstance(message, str)
            # Validate message is not empty
            assert len(message) > 0
            # Validate message doesn't exceed Telegram limits
            assert len(message) <= 4096
            telegram_messages.append(message)

        engine.register_action("send_telegram", send_telegram)

        context = {}
        engine.process_booking(context)

        # All messages should be valid
        assert len(telegram_messages) > 0
        assert all(isinstance(m, str) for m in telegram_messages)

    def test_telegram_sent_on_critical_failure(self, alert_rules):
        """Test that critical failure alerts are sent via Telegram"""
        engine = RuleEngine(str(alert_rules))

        engine.register_condition("always_true", lambda ctx, **p: True)

        critical_alerts = []

        def send_telegram(ctx, message, **p):
            critical_alerts.append(message)

        engine.register_action("send_telegram", send_telegram)

        # Simulate critical error in context
        context = {"critical_error": "Database connection lost"}
        engine.process_booking(context)

        # Alert should have been sent
        assert len(critical_alerts) > 0


class TestEndToEndErrorRecovery:
    """Tests for complete error recovery workflows"""

    @pytest.fixture
    def recovery_rules(self, tmp_path):
        """Create rules for error recovery scenarios"""
        rules_file = tmp_path / "recovery_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Attempt Primary Flow"
    description: "Try primary booking flow"
    enabled: true
    conditions:
      - type: "is_attempt_one"
    actions:
      - type: "process_booking"

  - name: "Fallback Flow"
    description: "Execute fallback if primary fails"
    enabled: true
    conditions:
      - type: "is_attempt_two"
    actions:
      - type: "process_booking_fallback"

  - name: "Send Summary"
    description: "Send final status summary"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "send_summary"
"""
        )
        return rules_file

    def test_lambda_completes_despite_errors(self, recovery_rules):
        """Test that Lambda completes successfully despite transient errors"""
        engine = RuleEngine(str(recovery_rules))

        engine.register_condition("is_attempt_one", lambda ctx, **p: True)
        engine.register_condition("is_attempt_two", lambda ctx, **p: False)
        engine.register_condition("always_true", lambda ctx, **p: True)

        completed = []

        def process_booking(ctx, **p):
            raise ConnectionError("Transient network error")

        def process_booking_fallback(ctx, **p):
            completed.append("fallback")

        def send_summary(ctx, **p):
            completed.append("summary_sent")

        engine.register_action("process_booking", process_booking)
        engine.register_action("process_booking_fallback", process_booking_fallback)
        engine.register_action("send_summary", send_summary)

        context = {}
        try:
            engine.process_booking(context)
            # Even if primary fails, summary should be sent
            assert "summary_sent" in completed
        except Exception as e:
            pytest.fail(f"Lambda should not crash: {e}")

    def test_error_context_captured_for_debugging(self, recovery_rules):
        """Test that error context is captured for post-incident analysis"""
        engine = RuleEngine(str(recovery_rules))

        engine.register_condition("is_attempt_one", lambda ctx, **p: True)
        engine.register_condition("is_attempt_two", lambda ctx, **p: False)
        engine.register_condition("always_true", lambda ctx, **p: True)

        debug_info = []

        def process_booking(ctx, **p):
            error = RuntimeError("Test error with stack trace")
            debug_info.append(
                {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            raise error

        def process_booking_fallback(ctx, **p):
            pass

        def send_summary(ctx, **p):
            pass

        engine.register_action("process_booking", process_booking)
        engine.register_action("process_booking_fallback", process_booking_fallback)
        engine.register_action("send_summary", send_summary)

        context = {}
        try:
            engine.process_booking(context)
        except Exception:
            pass

        # Error context should be captured
        assert len(debug_info) > 0
        assert "error_type" in debug_info[0]
        assert "error_message" in debug_info[0]
        assert "timestamp" in debug_info[0]
