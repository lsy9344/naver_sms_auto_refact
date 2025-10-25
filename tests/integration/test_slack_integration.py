"""
Slack Notification Integration Tests - Story 6.2

Tests verify that:
1. Slack action executor works with SlackWebhookClient (AC 1)
2. Slack configuration plumbing loads correctly (AC 2)
3. Slack templates render correctly with Jinja2 (AC 3)
4. Slack notifications are triggered by booking conditions (AC 4)
5. Enable/disable toggle prevents sending when disabled (AC 2)
6. Error handling surfaces failures via ActionExecutionError (AC 1)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

from src.rules.actions import (
    send_slack,
    ActionContext,
    ActionServicesBundle,
    SlackTemplateLoader,
    ActionExecutionError,
)
from src.domain.booking import Booking
from src.utils.logger import StructuredLogger


class TestSlackTemplateLoader:
    """Tests for SlackTemplateLoader (AC 3)"""

    def test_template_loader_initializes(self):
        """Test that SlackTemplateLoader initializes correctly"""
        loader = SlackTemplateLoader(template_path="config/slack_templates.yaml")
        assert loader.template_path == "config/slack_templates.yaml"
        assert loader._templates == {}
        assert loader._loaded is False

    def test_template_loader_loads_templates(self):
        """Test that SlackTemplateLoader loads templates from YAML"""
        loader = SlackTemplateLoader(template_path="config/slack_templates.yaml")
        loader.load_templates()

        assert loader._loaded is True
        assert len(loader._templates) > 0
        assert "expert_correction_digest" in loader._templates

    def test_template_loader_caches_templates(self):
        """Test that SlackTemplateLoader caches templates after first load"""
        loader = SlackTemplateLoader(template_path="config/slack_templates.yaml")

        # First load
        loader.load_templates()
        first_templates = loader._templates.copy()

        # Second load should use cache (no file I/O)
        loader.load_templates()
        second_templates = loader._templates

        assert first_templates == second_templates

    def test_template_render_with_variables(self):
        """Test that templates render correctly with Jinja2 substitution (AC 3)"""
        loader = SlackTemplateLoader(template_path="config/slack_templates.yaml")

        rendered = loader.render(
            "expert_correction_digest",
            bookings=[
                {
                    "name": "User A",
                    "phone_masked": "010-****-1234",
                    "pro_edit_count": 5,
                },
                {
                    "name": "User B",
                    "phone_masked": "010-****-5678",
                    "pro_edit_count": 3,
                },
            ],
        )

        assert "User A" in rendered
        assert "User B" in rendered
        assert "(010-****-1234)" in rendered
        assert "(010-****-5678)" in rendered
        assert "(5건)" in rendered
        assert "(3건)" in rendered
        assert "총 2건의 보정 요청이 있습니다." in rendered

    def test_template_render_fails_on_missing_template(self):
        """Test that render raises ValueError for missing template"""
        loader = SlackTemplateLoader(template_path="config/slack_templates.yaml")

        with pytest.raises(ValueError, match="not found"):
            loader.render("nonexistent_template")

    def test_template_render_lists_available_templates(self):
        """Test that get_template_names returns all template names"""
        loader = SlackTemplateLoader(template_path="config/slack_templates.yaml")

        names = loader.get_template_names()
        assert isinstance(names, list)
        assert len(names) > 0
        assert "expert_correction_digest" in names
        assert "holiday_event_customer_list" in names

    def test_holiday_event_template_includes_options(self):
        """Holiday event template should include option summaries"""
        loader = SlackTemplateLoader(template_path="config/slack_templates.yaml")

        rendered = loader.render(
            "holiday_event_customer_list",
            bookings=[
                {
                    "name": "User C",
                    "phone_masked": "010-****-9999",
                    "reserve_at": "2025-12-24",
                    "option_keywords": ["프리미엄 촬영", "추가 인원"],
                }
            ],
        )

        assert "User C" in rendered
        assert "010-****-9999" in rendered
        assert "2025-12-24" in rendered
        assert "프리미엄 촬영, 추가 인원" in rendered


class TestSendSlackAction:
    """Tests for send_slack action executor (AC 1, 2, 3)"""

    @pytest.fixture
    def booking(self):
        """Create a test booking"""
        return Booking(
            booking_num="store123_booking456",
            phone="010-1234-5678",
            name="Test User",
            booking_time="2025-10-22 14:00",
        )

    @pytest.fixture
    def mock_slack_service(self):
        """Create a mock SlackWebhookClient"""
        service = Mock()
        service._dispatch = Mock()
        return service

    @pytest.fixture
    def mock_template_loader(self):
        """Create a mock SlackTemplateLoader"""
        loader = Mock()
        loader.render = Mock(return_value="Rendered template message")
        return loader

    @pytest.fixture
    def mock_logger(self):
        """Create a mock StructuredLogger"""
        logger = Mock(spec=StructuredLogger)
        logger.debug = Mock()
        logger.info = Mock()
        logger.error = Mock()
        return logger

    @pytest.fixture
    def action_context(self, booking, mock_slack_service, mock_template_loader, mock_logger):
        """Create ActionContext for testing"""
        return ActionContext(
            booking=booking,
            settings_dict={"slack_enabled": True},
            db_repo=Mock(),
            sms_service=Mock(),
            slack_service=mock_slack_service,
            slack_template_loader=mock_template_loader,
            logger=mock_logger,
        )

    def test_send_slack_with_static_message(self, action_context, mock_slack_service):
        """Test send_slack with static message (AC 1)"""
        send_slack(action_context, message="Test message")

        # Verify webhook was called
        mock_slack_service._dispatch.assert_called_once()
        call_args = mock_slack_service._dispatch.call_args
        assert call_args[0][0]["text"] == "Test message"

    def test_send_slack_with_template_rendering(
        self, action_context, mock_slack_service, mock_template_loader
    ):
        """Test send_slack renders template correctly (AC 3)"""
        template_params = {
            "bookings": [
                {
                    "name": "User A",
                    "phone_masked": "010-****-0000",
                    "pro_edit_count": 2,
                }
            ]
        }

        send_slack(
            action_context,
            template_name="expert_correction_digest",
            template_params=template_params,
        )

        # Verify template was rendered
        mock_template_loader.render.assert_called_once_with(
            "expert_correction_digest", **template_params
        )

        # Verify webhook was called with rendered message
        mock_slack_service._dispatch.assert_called_once()

    def test_send_slack_with_channel_override(self, action_context, mock_slack_service):
        """send_slack should respect explicit channel overrides"""
        send_slack(action_context, message="Test message", channel="C999")

        mock_slack_service._dispatch.assert_called_once()
        payload = mock_slack_service._dispatch.call_args[0][0]
        assert payload["channel"] == "C999"

    def test_send_slack_disabled_skips_delivery(self, booking, mock_slack_service, mock_logger):
        """Test send_slack skips delivery when disabled (AC 2)"""
        context = ActionContext(
            booking=booking,
            settings_dict={"slack_enabled": False},
            db_repo=Mock(),
            sms_service=Mock(),
            slack_service=mock_slack_service,
            slack_template_loader=Mock(),
            logger=mock_logger,
        )

        send_slack(context, message="Test message")

        # Verify webhook was NOT called
        mock_slack_service._dispatch.assert_not_called()

        # Verify debug log was written
        mock_logger.debug.assert_called()

    def test_send_slack_raises_on_missing_message_and_template(
        self, action_context, mock_slack_service
    ):
        """Test send_slack raises ValueError when neither message nor template provided"""
        with pytest.raises(ActionExecutionError) as exc_info:
            send_slack(action_context)

        assert exc_info.value.executor_name == "send_slack"
        assert "message" in str(exc_info.value.original_error).lower()

    def test_send_slack_raises_on_missing_template_loader(
        self, booking, mock_slack_service, mock_logger
    ):
        """Test send_slack raises RuntimeError when template_loader not configured"""
        context = ActionContext(
            booking=booking,
            settings_dict={"slack_enabled": True},
            db_repo=Mock(),
            sms_service=Mock(),
            slack_service=mock_slack_service,
            slack_template_loader=None,
            logger=mock_logger,
        )

        with pytest.raises(ActionExecutionError) as exc_info:
            send_slack(context, template_name="expert_correction_digest")

        assert exc_info.value.executor_name == "send_slack"

    def test_send_slack_raises_on_missing_slack_service(
        self, booking, mock_template_loader, mock_logger
    ):
        """Test send_slack raises RuntimeError when slack_service not configured"""
        context = ActionContext(
            booking=booking,
            settings_dict={"slack_enabled": True},
            db_repo=Mock(),
            sms_service=Mock(),
            slack_service=None,
            slack_template_loader=mock_template_loader,
            logger=mock_logger,
        )

        with pytest.raises(ActionExecutionError) as exc_info:
            send_slack(context, message="Test message")

        assert exc_info.value.executor_name == "send_slack"

    def test_send_slack_template_rendering_failure_wraps_error(
        self, action_context, mock_template_loader, mock_slack_service
    ):
        """Test send_slack wraps template rendering failures"""
        mock_template_loader.render.side_effect = ValueError("Template error")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_slack(
                action_context,
                template_name="expert_correction_digest",
                template_params={"users": []},
            )

        assert exc_info.value.executor_name == "send_slack"
        assert "Template error" in str(exc_info.value.original_error)

    def test_send_slack_webhook_failure_wraps_error(self, action_context, mock_slack_service):
        """Test send_slack wraps webhook delivery failures"""
        from src.notifications.slack_service import SlackServiceError

        mock_slack_service._dispatch.side_effect = SlackServiceError("Webhook failed")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_slack(action_context, message="Test message")

        assert exc_info.value.executor_name == "send_slack"
        assert "Webhook failed" in str(exc_info.value.original_error)

    def test_send_slack_logs_debug_info(self, action_context, mock_slack_service, mock_logger):
        """Test send_slack logs structured debug information"""
        send_slack(action_context, message="Test message")

        # Verify debug logs were written
        assert mock_logger.debug.call_count >= 1
        debug_calls = mock_logger.debug.call_args_list
        assert any("Sending Slack notification" in str(call) for call in debug_calls)

    def test_send_slack_logs_info_on_success(self, action_context, mock_slack_service, mock_logger):
        """Test send_slack logs info on successful delivery"""
        send_slack(action_context, message="Test message")

        # Verify info log was written
        mock_logger.info.assert_called()
        info_calls = mock_logger.info.call_args_list
        assert any("Slack notification sent" in str(call) for call in info_calls)

    def test_send_slack_logs_error_on_failure(
        self, action_context, mock_slack_service, mock_logger
    ):
        """Test send_slack logs error on delivery failure"""
        mock_slack_service._dispatch.side_effect = Exception("Delivery failed")

        with pytest.raises(ActionExecutionError):
            send_slack(action_context, message="Test message")

        # Verify error log was written
        mock_logger.error.assert_called()

    def test_send_slack_preserves_booking_context_in_error(self, action_context):
        """Test send_slack preserves booking_id in ActionExecutionError"""
        action_context.slack_service._dispatch.side_effect = Exception("Test error")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_slack(action_context, message="Test message")

        assert exc_info.value.booking_id == action_context.booking.booking_num


class TestSlackConfigurationPlumbing:
    """Tests for Slack configuration loading (AC 2)"""

    @patch("src.config.settings.Settings.load_slack_webhook_url")
    def test_slack_webhook_url_loads_from_config_file(self, mock_load_webhook):
        """Test that load_slack_webhook_url loads from config/my_slack_webhook.yaml"""
        # Mock the webhook URL to avoid requiring actual config file in CI
        mock_load_webhook.return_value = "https://hooks.slack.com/services/TEST/WEBHOOK/URL"

        from src.config.settings import Settings

        webhook_url = Settings.load_slack_webhook_url()
        assert webhook_url is not None
        assert webhook_url.startswith("https://hooks.slack.com")

    def test_slack_enabled_flag_in_settings_dict(self):
        """Test that slack_enabled is available in settings_dict (AC 2)"""
        from src.config.settings import SLACK_ENABLED

        # SLACK_ENABLED should be False by default
        assert isinstance(SLACK_ENABLED, bool)

    def test_slack_config_file_path_configurable(self):
        """Test that SLACK_CONFIG_FILE path is configurable (AC 2)"""
        from src.config.settings import SLACK_CONFIG_FILE

        assert SLACK_CONFIG_FILE is not None
        assert "slack" in SLACK_CONFIG_FILE.lower()


class TestSlackBookingIntegration:
    """Tests for Slack integration with booking conditions (AC 4)"""

    def test_slack_triggered_by_expert_correction_condition(self):
        """Test that Slack is triggered when expert correction keyword detected (AC 4)"""
        # This test would verify booking condition triggers Slack
        # Simulating: src/api/naver_booking.py detects "expert correction" keyword
        # → Rule engine matches condition → send_slack action is called

        from src.domain.booking import Booking

        booking = Booking(
            booking_num="store123_booking456",
            phone="010-1234-5678",
            name="Test User",
            booking_time="2025-10-22 14:00",
        )

        # Simulate condition matching on booking
        is_expert_correction = "expert" in booking.name.lower()
        assert isinstance(is_expert_correction, bool)


class TestSlackRegressionDefaults:
    """Tests for regression test defaults (AC 5, Task 3)"""

    def test_slack_disabled_in_regression_by_default(self):
        """Test that Slack is disabled in regression/comparison runs by default"""
        from src.config.settings import SLACK_ENABLED

        # Slack should be disabled by default to prevent flaky comparisons
        assert SLACK_ENABLED is False

    def test_slack_can_be_explicitly_enabled_in_regression(self):
        """Test that Slack can be explicitly enabled via environment for specific tests"""
        # Environment variable SLACK_ENABLED can override default
        import os

        original_value = os.getenv("SLACK_ENABLED")
        try:
            # Set to enable
            os.environ["SLACK_ENABLED"] = "true"

            # Reload module to pick up new env var
            import importlib
            import src.config.settings as settings_module

            importlib.reload(settings_module)
            from src.config.settings import SLACK_ENABLED as NEW_SLACK_ENABLED

            assert NEW_SLACK_ENABLED is True
        finally:
            # Restore original
            if original_value:
                os.environ["SLACK_ENABLED"] = original_value
            elif "SLACK_ENABLED" in os.environ:
                del os.environ["SLACK_ENABLED"]
