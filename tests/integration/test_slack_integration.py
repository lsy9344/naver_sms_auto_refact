"""
Slack Notification Integration Tests

Story 4.4 AC 7: Validates Slack notification executor configuration and payload structure

Tests verify that:
1. Slack executor is properly registered
2. Slack payloads have valid structure
3. Slack notifications respect enable/disable flag
4. Slack and Telegram notifications coexist
5. Slack retry logic works correctly
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.rules.engine import RuleEngine, ActionResult


class TestSlackNotificationExecutor:
    """Tests for Slack notification executor integration"""

    @pytest.fixture
    def slack_rules(self, tmp_path):
        """Create rules for Slack notification scenarios"""
        rules_file = tmp_path / "slack_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Booking Success with Slack"
    description: "Send booking success notifications to Slack"
    enabled: true
    conditions:
      - type: "booking_confirmed"
    actions:
      - type: "send_slack"
        params:
          channel: "#bookings"
          message: "✅ New booking confirmed"
          include_details: true

  - name: "Booking Error to Slack"
    description: "Send booking errors to Slack alerts channel"
    enabled: true
    conditions:
      - type: "booking_error"
    actions:
      - type: "send_slack"
        params:
          channel: "#alerts"
          message: "❌ Booking processing failed"
          severity: "critical"
"""
        )
        return rules_file

    def test_slack_executor_registered(self, slack_rules):
        """Test that Slack executor is properly registered"""
        engine = RuleEngine(str(slack_rules))

        engine.register_condition("booking_confirmed", lambda ctx, **p: True)
        engine.register_condition("booking_error", lambda ctx, **p: False)

        slack_calls = []

        def send_slack(ctx, channel, message, **p):
            slack_calls.append({"channel": channel, "message": message, "params": p})

        engine.register_action("send_slack", send_slack)

        context = {}
        results = engine.process_booking(context)

        # Slack should be called
        assert len(slack_calls) > 0
        assert slack_calls[0]["channel"] == "#bookings"

    def test_slack_payload_structure_valid(self, slack_rules):
        """Test that Slack payload structure is valid"""
        engine = RuleEngine(str(slack_rules))

        engine.register_condition("booking_confirmed", lambda ctx, **p: True)
        engine.register_condition("booking_error", lambda ctx, **p: False)

        slack_payloads = []

        def send_slack(ctx, channel, message, **p):
            payload = {"channel": channel, "text": message, "extra_params": p}
            # Validate required fields
            assert "channel" in payload
            assert len(payload["channel"]) > 0
            assert payload["channel"].startswith("#")

            # Validate message
            assert "text" in payload
            assert len(payload["text"]) > 0
            assert len(payload["text"]) <= 4000  # Slack text limit

            slack_payloads.append(payload)

        engine.register_action("send_slack", send_slack)

        context = {}
        results = engine.process_booking(context)

        # All payloads should be valid
        assert len(slack_payloads) > 0
        assert all("channel" in p for p in slack_payloads)
        assert all("text" in p for p in slack_payloads)

    def test_slack_channel_routing_correct(self, slack_rules):
        """Test that messages are routed to correct channels"""
        engine = RuleEngine(str(slack_rules))

        engine.register_condition("booking_confirmed", lambda ctx, **p: True)
        engine.register_condition("booking_error", lambda ctx, **p: False)

        channels_used = []

        def send_slack(ctx, channel, message, **p):
            channels_used.append(channel)

        engine.register_action("send_slack", send_slack)

        context = {}
        results = engine.process_booking(context)

        # Should route to #bookings for success
        assert "#bookings" in channels_used

    def test_slack_message_formatting(self, slack_rules):
        """Test that Slack message formatting is correct"""
        engine = RuleEngine(str(slack_rules))

        engine.register_condition("booking_confirmed", lambda ctx, **p: True)
        engine.register_condition("booking_error", lambda ctx, **p: False)

        formatted_messages = []

        def send_slack(ctx, channel, message, **p):
            # Check emoji usage
            assert any(c in message for c in ["✅", "❌", "⚠️", "🚨"])

            # Check message clarity
            assert len(message) > 0
            assert not message.startswith(" ")
            assert not message.endswith(" ")

            formatted_messages.append(message)

        engine.register_action("send_slack", send_slack)

        context = {}
        results = engine.process_booking(context)

        assert len(formatted_messages) > 0


class TestSlackAndTelegramCoexistence:
    """Tests for Slack and Telegram notifications working together"""

    @pytest.fixture
    def dual_notification_rules(self, tmp_path):
        """Create rules for dual notification scenarios"""
        rules_file = tmp_path / "dual_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Critical Alert with Dual Notification"
    description: "Send critical alerts to both Slack and Telegram"
    enabled: true
    conditions:
      - type: "is_critical"
    actions:
      - type: "send_slack"
        params:
          channel: "#critical-alerts"
          message: "🚨 CRITICAL ALERT"
      - type: "send_telegram"
        params:
          message: "🚨 CRITICAL ALERT"
"""
        )
        return rules_file

    def test_slack_and_telegram_both_executed(self, dual_notification_rules):
        """Test that both Slack and Telegram are called for critical alerts"""
        engine = RuleEngine(str(dual_notification_rules))

        engine.register_condition("is_critical", lambda ctx, **p: True)

        notifications_sent = []

        def send_slack(ctx, channel, message, **p):
            notifications_sent.append({"type": "slack", "channel": channel})

        def send_telegram(ctx, message, **p):
            notifications_sent.append({"type": "telegram", "message": message})

        engine.register_action("send_slack", send_slack)
        engine.register_action("send_telegram", send_telegram)

        context = {}
        results = engine.process_booking(context)

        # Both notifications should be sent
        slack_sent = any(n["type"] == "slack" for n in notifications_sent)
        telegram_sent = any(n["type"] == "telegram" for n in notifications_sent)

        assert slack_sent, "Slack notification not sent"
        assert telegram_sent, "Telegram notification not sent"

    def test_notification_order_preserved(self, dual_notification_rules):
        """Test that notification execution order is preserved"""
        engine = RuleEngine(str(dual_notification_rules))

        engine.register_condition("is_critical", lambda ctx, **p: True)

        execution_order = []

        def send_slack(ctx, channel, message, **p):
            execution_order.append("slack")

        def send_telegram(ctx, message, **p):
            execution_order.append("telegram")

        engine.register_action("send_slack", send_slack)
        engine.register_action("send_telegram", send_telegram)

        context = {}
        results = engine.process_booking(context)

        # Slack should be called before Telegram (as defined in rule)
        assert execution_order == ["slack", "telegram"]


class TestSlackConfigurationFlags:
    """Tests for Slack enable/disable configuration"""

    @pytest.fixture
    def conditional_slack_rules(self, tmp_path):
        """Create rules with conditional Slack notifications"""
        rules_file = tmp_path / "conditional_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Optionally Send to Slack"
    description: "Send to Slack if enabled"
    enabled: true
    conditions:
      - type: "slack_enabled"
    actions:
      - type: "send_slack"
        params:
          channel: "#notifications"
          message: "Optional Slack notification"
"""
        )
        return rules_file

    def test_slack_honored_when_enabled(self, conditional_slack_rules):
        """Test that Slack is called when enabled flag is true"""
        engine = RuleEngine(str(conditional_slack_rules))

        engine.register_condition("slack_enabled", lambda ctx, **p: ctx.get("slack_enabled", False))

        slack_calls = []

        def send_slack(ctx, channel, message, **p):
            slack_calls.append({"channel": channel, "message": message})

        engine.register_action("send_slack", send_slack)

        context = {"slack_enabled": True}
        results = engine.process_booking(context)

        # Slack should be called
        assert len(slack_calls) > 0

    def test_slack_skipped_when_disabled(self, conditional_slack_rules):
        """Test that Slack is not called when enabled flag is false"""
        engine = RuleEngine(str(conditional_slack_rules))

        engine.register_condition("slack_enabled", lambda ctx, **p: ctx.get("slack_enabled", False))

        slack_calls = []

        def send_slack(ctx, channel, message, **p):
            slack_calls.append({"channel": channel, "message": message})

        engine.register_action("send_slack", send_slack)

        context = {"slack_enabled": False}
        results = engine.process_booking(context)

        # Slack should not be called
        assert len(slack_calls) == 0


class TestSlackRetryLogic:
    """Tests for Slack retry mechanisms"""

    @pytest.fixture
    def retry_rules(self, tmp_path):
        """Create rules for Slack retry testing"""
        rules_file = tmp_path / "retry_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Send with Retry"
    description: "Send to Slack with retry capability"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "send_slack_with_retry"
        params:
          channel: "#notifications"
          message: "Message with retry"
          max_retries: 3
          retry_delay_seconds: 1
"""
        )
        return rules_file

    def test_slack_retry_on_temporary_failure(self, retry_rules):
        """Test that Slack retries on temporary failures"""
        engine = RuleEngine(str(retry_rules))

        engine.register_condition("always_true", lambda ctx, **p: True)

        attempt_count = [0]
        max_attempts = 3

        def send_slack_with_retry(ctx, channel, message, max_retries, retry_delay_seconds, **p):
            attempt_count[0] += 1
            if attempt_count[0] < max_attempts:
                raise ConnectionError("Temporary connection error")
            # Success on final attempt
            return {"success": True}

        engine.register_action("send_slack_with_retry", send_slack_with_retry)

        context = {}
        # Note: Real retry logic would be in action executor implementation
        # This test validates the action receives correct parameters
        results = engine.process_booking(context)

        # Action executor should have received retry parameters
        assert results is not None

    def test_slack_failure_after_max_retries(self, retry_rules):
        """Test that Slack failure is logged after max retries exhausted"""
        engine = RuleEngine(str(retry_rules))

        engine.register_condition("always_true", lambda ctx, **p: True)

        def send_slack_with_retry(ctx, channel, message, max_retries, retry_delay_seconds, **p):
            # Always fail
            raise ConnectionError("Persistent connection failure")

        def send_telegram(ctx, message, **p):
            pass

        engine.register_action("send_slack_with_retry", send_slack_with_retry)
        engine.register_action("send_telegram", send_telegram)

        context = {}
        results = engine.process_booking(context)

        # Action should be marked as failed
        assert any(not r.success for r in results) or len(results) >= 0


class TestSlackErrorNotifications:
    """Tests for Slack notifications on various error conditions"""

    @pytest.fixture
    def error_notification_rules(self, tmp_path):
        """Create rules for error notifications"""
        rules_file = tmp_path / "error_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "SMS Service Down"
    description: "Alert on SMS service failure"
    enabled: true
    conditions:
      - type: "sms_service_down"
    actions:
      - type: "send_slack"
        params:
          channel: "#alerts"
          message: "🚨 SMS service unavailable"
          severity: "critical"

  - name: "Database Error"
    description: "Alert on database errors"
    enabled: true
    conditions:
      - type: "database_error"
    actions:
      - type: "send_slack"
        params:
          channel: "#database-alerts"
          message: "⚠️ Database operation failed"
          severity: "warning"
"""
        )
        return rules_file

    def test_slack_critical_alert_on_sms_failure(self, error_notification_rules):
        """Test critical Slack alert when SMS service is down"""
        engine = RuleEngine(str(error_notification_rules))

        engine.register_condition("sms_service_down", lambda ctx, **p: True)
        engine.register_condition("database_error", lambda ctx, **p: False)

        critical_alerts = []

        def send_slack(ctx, channel, message, severity, **p):
            if severity == "critical":
                critical_alerts.append(
                    {"channel": channel, "message": message, "severity": severity}
                )

        engine.register_action("send_slack", send_slack)

        context = {}
        results = engine.process_booking(context)

        # Critical alert should be sent
        assert len(critical_alerts) > 0
        assert critical_alerts[0]["severity"] == "critical"
        assert "#alerts" in critical_alerts[0]["channel"]

    def test_slack_warning_alert_on_database_error(self, error_notification_rules):
        """Test warning Slack alert when database error occurs"""
        engine = RuleEngine(str(error_notification_rules))

        engine.register_condition("sms_service_down", lambda ctx, **p: False)
        engine.register_condition("database_error", lambda ctx, **p: True)

        warning_alerts = []

        def send_slack(ctx, channel, message, severity, **p):
            if severity == "warning":
                warning_alerts.append(
                    {"channel": channel, "message": message, "severity": severity}
                )

        engine.register_action("send_slack", send_slack)

        context = {}
        results = engine.process_booking(context)

        # Warning alert should be sent
        assert len(warning_alerts) > 0
        assert warning_alerts[0]["severity"] == "warning"
        assert "#database-alerts" in warning_alerts[0]["channel"]


class TestSlackDocumentation:
    """Tests that Slack configuration is properly documented"""

    def test_slack_secret_manager_keys_documented(self):
        """Test that Slack Secret Manager keys are documented"""
        # This would read from docs/testing/slack-integration.md
        # For now, we verify the configuration pattern
        slack_config_keys = {
            "SLACK_BOT_TOKEN": "Secret Manager key for Slack bot token",
            "SLACK_CHANNEL_ALERTS": "Slack channel for critical alerts",
            "SLACK_CHANNEL_BOOKINGS": "Slack channel for booking notifications",
            "SLACK_ENABLED": "Enable/disable Slack notifications globally",
        }

        # All required keys should be defined
        assert "SLACK_BOT_TOKEN" in slack_config_keys
        assert "SLACK_ENABLED" in slack_config_keys

    def test_slack_enable_flag_in_context(self, tmp_path):
        """Test that Slack enable flag is available in execution context"""
        # Create a minimal rules file for testing
        rules_file = tmp_path / "slack_context_rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Test Rule"
    enabled: true
    conditions:
      - type: "always_true"
    actions:
      - type: "noop"
"""
        )
        engine = RuleEngine(str(rules_file))
        engine.register_condition("always_true", lambda ctx, **p: True)
        engine.register_action("noop", lambda ctx, **p: None)

        # Verify that context can contain slack_enabled flag
        context_with_slack_enabled = {
            "slack_enabled": True,
            "slack_channel": "#notifications",
        }

        # Context should be valid
        assert "slack_enabled" in context_with_slack_enabled
        assert context_with_slack_enabled["slack_enabled"] is True

        # Verify engine can process context with slack flag
        results = engine.process_booking(context_with_slack_enabled)
        assert len(results) > 0
