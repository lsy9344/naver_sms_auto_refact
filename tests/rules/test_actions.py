"""
Unit tests for action executors.

Tests cover success cases, failure cases, error wrapping, idempotency,
and immutability of ActionContext. Uses mocks/stubs for all services.
"""

import pytest
from unittest.mock import Mock
from src.rules.actions import (
    ActionContext,
    ActionServicesBundle,
    ActionExecutionError,
    send_sms,
    create_db_record,
    update_flag,
    send_telegram,
    send_slack,
    log_event,
    register_actions,
)
from src.domain.booking import Booking
from src.notifications.sms_service import SmsServiceError


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_booking():
    """Create a mock booking for testing."""
    return Booking(
        booking_num="1051707_12345",
        phone="010-1234-5678",
        name="Test Customer",
        booking_time="2025-10-20 14:00:00",
        confirm_sms=False,
        remind_sms=False,
        option_sms=False,
        option_time="",
    )


@pytest.fixture
def mock_db_repo():
    """Create a mock BookingRepository."""
    repo = Mock()
    repo.get_booking.return_value = {
        "booking_num": "1051707_12345",
        "phone": "010-1234-5678",
        "confirm_sms": False,
        "remind_sms": False,
        "option_sms": False,
    }
    repo.create_booking.return_value = True
    repo.update_flag.return_value = True
    return repo


@pytest.fixture
def mock_sms_service():
    """Create a mock SensSmsClient."""
    service = Mock()
    service.send_confirm_sms.return_value = None
    service.send_guide_sms.return_value = None
    service.send_event_sms.return_value = None
    return service


@pytest.fixture
def mock_logger():
    """Create a mock StructuredLogger."""
    logger = Mock()
    logger.logger.name = "test_logger"
    logger.debug.return_value = None
    logger.info.return_value = None
    logger.warning.return_value = None
    logger.error.return_value = None
    return logger


@pytest.fixture
def mock_slack_service():
    """Create a mock SlackWebhookClient."""
    service = Mock()
    service._dispatch.return_value = None
    return service


@pytest.fixture
def mock_slack_template_loader():
    """Create a mock SlackTemplateLoader."""
    loader = Mock()
    loader.render.return_value = "Rendered template message"
    return loader


@pytest.fixture
def mock_telegram_service():
    """Create a mock TelegramBotClient."""
    service = Mock()
    service.send_message.return_value = None
    service.send_notification.return_value = None
    return service


@pytest.fixture
def mock_telegram_template_loader():
    """Create a mock TelegramTemplateLoader."""
    loader = Mock()
    loader.render.return_value = {"text": "Rendered Telegram message", "parse_mode": "Markdown"}
    return loader


@pytest.fixture
def action_context(
    mock_booking,
    mock_db_repo,
    mock_sms_service,
    mock_logger,
    mock_slack_service,
    mock_slack_template_loader,
    mock_telegram_service,
    mock_telegram_template_loader,
):
    """Create an ActionContext for testing."""
    return ActionContext(
        booking=mock_booking,
        settings_dict={"slack_enabled": False},
        db_repo=mock_db_repo,
        sms_service=mock_sms_service,
        slack_service=mock_slack_service,
        slack_template_loader=mock_slack_template_loader,
        telegram_template_loader=mock_telegram_template_loader,
        telegram_service=mock_telegram_service,
        logger=mock_logger,
    )


@pytest.fixture
def services_bundle(
    mock_db_repo,
    mock_sms_service,
    mock_logger,
    mock_slack_service,
    mock_slack_template_loader,
    mock_telegram_service,
    mock_telegram_template_loader,
):
    """Create an ActionServicesBundle for testing."""
    return ActionServicesBundle(
        db_repo=mock_db_repo,
        sms_service=mock_sms_service,
        slack_service=mock_slack_service,
        slack_template_loader=mock_slack_template_loader,
        telegram_template_loader=mock_telegram_template_loader,
        telegram_service=mock_telegram_service,
        logger=mock_logger,
        settings_dict={"slack_enabled": False},
    )


# ============================================================================
# Tests: send_sms
# ============================================================================


class TestSendSms:
    """Tests for send_sms action executor."""

    def test_send_sms_confirm_success(self, action_context, mock_sms_service):
        """Test successful confirmation SMS sending."""
        send_sms(action_context, template="confirm")

        mock_sms_service.send_confirm_sms.assert_called_once_with(
            phone="010-1234-5678",
            store_id=None,
        )

    def test_send_sms_guide_success(self, action_context, mock_sms_service):
        """Test successful guide SMS sending with store_specific flag."""
        send_sms(action_context, template="guide", store_specific=True)

        mock_sms_service.send_guide_sms.assert_called_once_with(
            store_id="1051707",
            phone="010-1234-5678",
        )

    def test_send_sms_event_success(self, action_context, mock_sms_service):
        """Test successful event SMS sending."""
        send_sms(action_context, template="event")

        mock_sms_service.send_event_sms.assert_called_once_with(
            phone="010-1234-5678",
            store_id=None,
        )

    def test_send_sms_invalid_template(self, action_context):
        """Test that invalid template raises ActionExecutionError."""
        with pytest.raises(ActionExecutionError) as exc_info:
            send_sms(action_context, template="invalid")

        error = exc_info.value
        assert error.executor_name == "send_sms"
        assert error.booking_id == "1051707_12345"
        assert isinstance(error.original_error, ValueError)

    def test_send_sms_service_error(self, action_context, mock_sms_service):
        """Test that SmsServiceError is wrapped in ActionExecutionError."""
        mock_sms_service.send_confirm_sms.side_effect = SmsServiceError("SENS API failed")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_sms(action_context, template="confirm")

        error = exc_info.value
        assert error.executor_name == "send_sms"
        assert error.booking_id == "1051707_12345"
        assert isinstance(error.original_error, SmsServiceError)
        assert error.context_data["template"] == "confirm"


# ============================================================================
# Tests: create_db_record
# ============================================================================


class TestCreateDbRecord:
    """Tests for create_db_record action executor."""

    def test_create_db_record_success(self, action_context, mock_db_repo):
        """Test successful booking record creation."""
        create_db_record(action_context)

        mock_db_repo.create_booking.assert_called_once()
        call_args = mock_db_repo.create_booking.call_args[0][0]

        # Verify record schema
        assert call_args["booking_num"] == "1051707_12345"
        assert call_args["phone"] == "010-1234-5678"
        assert call_args["name"] == "Test Customer"
        assert call_args["booking_time"] == "2025-10-20 14:00:00"
        assert call_args["confirm_sms"] is False
        assert call_args["remind_sms"] is False
        assert call_args["option_sms"] is False
        assert call_args["option_time"] == ""

    def test_create_db_record_with_custom_data(self, action_context, mock_db_repo):
        """Test booking creation with custom data override."""
        custom_data = {
            "booking_num": "999_99999",
            "phone": "010-9999-9999",
            "name": "Custom Name",
            "booking_time": "2025-10-20 15:00:00",
            "confirm_sms": True,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }

        create_db_record(action_context, booking_data=custom_data)

        mock_db_repo.create_booking.assert_called_once_with(custom_data)

    def test_create_db_record_db_error(self, action_context, mock_db_repo):
        """Test that DynamoDB errors are wrapped in ActionExecutionError."""
        mock_db_repo.create_booking.side_effect = Exception("DynamoDB error")

        with pytest.raises(ActionExecutionError) as exc_info:
            create_db_record(action_context)

        error = exc_info.value
        assert error.executor_name == "create_db_record"
        assert error.booking_id == "1051707_12345"
        assert isinstance(error.original_error, Exception)


# ============================================================================
# Tests: update_flag
# ============================================================================


class TestUpdateFlag:
    """Tests for update_flag action executor."""

    def test_update_flag_success_schema_params(self, action_context, mock_db_repo):
        """Test successful flag update using schema-aligned parameters."""
        mock_db_repo.get_booking.return_value = {
            "booking_num": "1051707_12345",
            "confirm_sms": False,
        }

        update_flag(action_context, flag="confirm_sms", value=True)

        mock_db_repo.update_flag.assert_called_once_with(
            prefix="1051707_12345",
            phone="010-1234-5678",
            flag_name="confirm_sms",
            value=True,
        )

    def test_update_flag_success_legacy_alias(self, action_context, mock_db_repo):
        """Test backwards compatibility with legacy flag_name/flag_value kwargs."""
        mock_db_repo.get_booking.return_value = {
            "booking_num": "1051707_12345",
            "confirm_sms": False,
        }

        update_flag(action_context, flag_name="confirm_sms", flag_value=True)

        mock_db_repo.update_flag.assert_called_once_with(
            prefix="1051707_12345",
            phone="010-1234-5678",
            flag_name="confirm_sms",
            value=True,
        )

    def test_update_flag_idempotency(self, action_context, mock_db_repo):
        """Test that idempotency skips update if flag already set."""
        mock_db_repo.get_booking.return_value = {
            "booking_num": "1051707_12345",
            "confirm_sms": True,
        }

        update_flag(action_context, flag="confirm_sms", value=True)

        # Should NOT call update_flag since it's already True
        mock_db_repo.update_flag.assert_not_called()

    def test_update_flag_invalid_flag(self, action_context):
        """Test that invalid flag name raises ActionExecutionError."""
        with pytest.raises(ActionExecutionError) as exc_info:
            update_flag(action_context, flag="invalid_flag", value=True)

        error = exc_info.value
        assert error.executor_name == "update_flag"
        assert isinstance(error.original_error, ValueError)

    def test_update_flag_nonexistent_booking(self, action_context, mock_db_repo):
        """Test that updating non-existent booking raises error."""
        mock_db_repo.get_booking.return_value = None

        with pytest.raises(ActionExecutionError) as exc_info:
            update_flag(action_context, flag="confirm_sms", value=True)

        error = exc_info.value
        assert error.executor_name == "update_flag"
        assert isinstance(error.original_error, ValueError)
        assert "non-existent" in str(error.original_error)

    def test_update_flag_db_error(self, action_context, mock_db_repo):
        """Test that DynamoDB errors are wrapped in ActionExecutionError."""
        mock_db_repo.get_booking.return_value = {
            "booking_num": "1051707_12345",
            "confirm_sms": False,
        }
        mock_db_repo.update_flag.side_effect = Exception("DynamoDB error")

        with pytest.raises(ActionExecutionError) as exc_info:
            update_flag(action_context, flag="confirm_sms", value=True)

        error = exc_info.value
        assert error.executor_name == "update_flag"
        assert isinstance(error.original_error, Exception)

    def test_update_flag_missing_flag_parameter(self, action_context):
        """Test that missing flag parameter raises wrapped ActionExecutionError."""
        with pytest.raises(ActionExecutionError) as exc_info:
            update_flag(action_context)

        error = exc_info.value
        assert error.executor_name == "update_flag"
        assert isinstance(error.original_error, ValueError)


# ============================================================================
# Tests: send_telegram
# ============================================================================


class TestSendTelegram:
    """Tests for send_telegram action executor."""

    def test_send_telegram_success(self, action_context):
        """Test successful Telegram notification."""
        # Should not raise any exception
        send_telegram(action_context, message="Test message")

        action_context.telegram_service.send_message.assert_called_once_with(
            text="Test message",
            parse_mode="Markdown",
        )
        action_context.logger.info.assert_called_once()

    def test_send_telegram_with_params(self, action_context):
        """Test Telegram notification with template parameters."""
        params = {"booking_id": "123", "status": "confirmed"}
        send_telegram(action_context, message="Booking {{booking_id}}", template_params=params)

        action_context.telegram_service.send_message.assert_called_once_with(
            text="Booking 123",
            parse_mode="Markdown",
        )
        action_context.logger.info.assert_called_once()

    def test_send_telegram_error_handling(self, action_context):
        """Test error handling in send_telegram."""
        action_context.logger.info.side_effect = Exception("Telegram API error")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_telegram(action_context, message="Test")

        error = exc_info.value
        assert error.executor_name == "send_telegram"


# ============================================================================
# Tests: send_slack
# ============================================================================


class TestSendSlack:
    """Tests for send_slack action executor."""

    def test_send_slack_enabled(self, action_context):
        """Test Slack notification when enabled."""
        action_context.settings_dict["slack_enabled"] = True

        send_slack(action_context, message="Test message")

        action_context.logger.info.assert_called_once()

    def test_send_slack_disabled(self, action_context):
        """Test that Slack notification is skipped when disabled."""
        action_context.settings_dict["slack_enabled"] = False

        send_slack(action_context, message="Test message")

        # Should only call debug, not info
        action_context.logger.debug.assert_called_once()
        action_context.logger.info.assert_not_called()

    def test_send_slack_no_config(self, action_context):
        """Test Slack notification when config key missing (defaults to disabled)."""
        action_context.settings_dict.pop("slack_enabled", None)

        send_slack(action_context, message="Test message")

        action_context.logger.debug.assert_called_once()


# ============================================================================
# Tests: send_telegram
# ============================================================================


class TestSendTelegramDetailed:
    """Detailed tests for send_telegram action executor."""

    def test_send_telegram_success(self, action_context, mock_telegram_service):
        """Test successful Telegram message sending."""
        send_telegram(action_context, message="Test notification")

        mock_telegram_service.send_message.assert_called_once_with(
            text="Test notification",
            parse_mode="Markdown",
        )
        action_context.logger.info.assert_called_once()

    def test_send_telegram_with_template_name(
        self,
        action_context,
        mock_telegram_service,
        mock_telegram_template_loader,
    ):
        """Test Telegram message rendering via template loader."""
        mock_telegram_template_loader.render.return_value = {
            "text": "Rendered Telegram message",
            "parse_mode": "HTML",
        }

        send_telegram(
            action_context,
            template_name="booking_notification",
            template_params={"customer": "홍길동"},
        )

        mock_telegram_template_loader.render.assert_called_once_with(
            "booking_notification", customer="홍길동"
        )
        mock_telegram_service.send_message.assert_called_once_with(
            text="Rendered Telegram message",
            parse_mode="HTML",
        )

    def test_send_telegram_parse_mode_override(self, action_context, mock_telegram_service):
        """Test explicit parse mode override."""
        send_telegram(action_context, message="Plain text", parse_mode=None)

        mock_telegram_service.send_message.assert_called_once_with(
            text="Plain text",
            parse_mode=None,
        )

    def test_send_telegram_requires_message_or_template(self, action_context):
        """Ensure validation triggers when neither message nor template provided."""
        with pytest.raises(ActionExecutionError) as exc_info:
            send_telegram(action_context)

        assert isinstance(exc_info.value.original_error, ValueError)

    def test_send_telegram_template_loader_missing(self, action_context, mock_telegram_service):
        """Ensure missing template loader raises runtime error."""
        action_context = ActionContext(
            booking=action_context.booking,
            settings_dict=action_context.settings_dict,
            db_repo=action_context.db_repo,
            sms_service=action_context.sms_service,
            slack_service=action_context.slack_service,
            slack_template_loader=action_context.slack_template_loader,
            telegram_template_loader=None,
            telegram_service=action_context.telegram_service,
            logger=action_context.logger,
        )

        with pytest.raises(ActionExecutionError) as exc_info:
            send_telegram(action_context, template_name="booking_notification")

        assert isinstance(exc_info.value.original_error, RuntimeError)

    def test_send_telegram_missing_template(
        self,
        action_context,
        mock_telegram_template_loader,
    ):
        """Ensure missing template raises wrapped ValueError."""
        mock_telegram_template_loader.render.side_effect = ValueError("Template not found")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_telegram(action_context, template_name="unknown_template")

        assert isinstance(exc_info.value.original_error, ValueError)

    def test_send_telegram_when_not_configured(self, action_context):
        """Test that send_telegram skips when service not configured."""
        action_context = ActionContext(
            booking=action_context.booking,
            settings_dict=action_context.settings_dict,
            db_repo=action_context.db_repo,
            sms_service=action_context.sms_service,
            slack_service=action_context.slack_service,
            slack_template_loader=action_context.slack_template_loader,
            telegram_template_loader=action_context.telegram_template_loader,
            telegram_service=None,
            logger=action_context.logger,
        )

        send_telegram(action_context, message="Test message")

        action_context.logger.warning.assert_called_once()

    def test_send_telegram_service_error(self, action_context, mock_telegram_service):
        """Test handling of TelegramServiceError."""
        from src.notifications.telegram_service import TelegramServiceError

        mock_telegram_service.send_message.side_effect = TelegramServiceError("API error")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_telegram(action_context, message="Test message")

        assert exc_info.value.executor_name == "send_telegram"
        assert exc_info.value.booking_id == "1051707_12345"
        action_context.logger.error.assert_called_once()

    def test_send_telegram_unexpected_error(self, action_context, mock_telegram_service):
        """Test handling of unexpected errors."""
        mock_telegram_service.send_message.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(ActionExecutionError) as exc_info:
            send_telegram(action_context, message="Test message")

        assert exc_info.value.executor_name == "send_telegram"
        action_context.logger.error.assert_called()


# ============================================================================
# Tests: log_event
# ============================================================================


class TestLogEvent:
    """Tests for log_event action executor."""

    def test_log_event_success(self, action_context):
        """Test successful event logging."""
        log_event(
            action_context,
            rule_name="Test Rule",
            action_name="test_action",
            status="success",
            message="Test message",
        )

        action_context.logger.info.assert_called_once()
        call_args = action_context.logger.info.call_args
        assert "Test message" in str(call_args)

    def test_log_event_with_error_status(self, action_context):
        """Test event logging with error status."""
        log_event(
            action_context,
            rule_name="Test Rule",
            action_name="test_action",
            status="failed",
            message="Action failed",
        )

        action_context.logger.info.assert_called_once()

    def test_log_event_error_handling(self, action_context):
        """Test that log_event handles logger errors gracefully."""
        action_context.logger.info.side_effect = Exception("Logger error")

        # Should not raise exception
        log_event(
            action_context,
            rule_name="Test Rule",
            action_name="test_action",
            status="success",
            message="Test",
        )

        # Should have called error method
        action_context.logger.error.assert_called_once()


# ============================================================================
# Tests: ActionContext Immutability (AC8)
# ============================================================================


class TestActionContextImmutability:
    """Tests for ActionContext immutability."""

    def test_action_context_frozen(self, action_context):
        """Test that ActionContext is frozen (immutable)."""
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            action_context.booking = None

    def test_action_context_frozen_settings(self, action_context):
        """Test that settings_dict cannot be replaced."""
        with pytest.raises(Exception):
            action_context.settings_dict = {}

    def test_action_context_safe_concurrent_reuse(
        self,
        action_context,
        mock_booking,
        mock_db_repo,
        mock_sms_service,
        mock_slack_service,
        mock_slack_template_loader,
        mock_logger,
    ):
        """Test that ActionContext can be safely reused in concurrent scenarios."""
        # Create a second booking
        booking2 = Booking(
            booking_num="999_99999",
            phone="010-9999-9999",
            name="Another Customer",
            booking_time="2025-10-20 15:00:00",
            confirm_sms=False,
            remind_sms=False,
            option_sms=False,
        )

        # ActionContext is immutable, so original booking should remain unchanged
        original_booking = action_context.booking

        # Even if we create a new context, the original should be unmodified
        new_context = ActionContext(
            booking=booking2,
            settings_dict=action_context.settings_dict,
            db_repo=mock_db_repo,
            sms_service=mock_sms_service,
            slack_service=mock_slack_service,
            slack_template_loader=mock_slack_template_loader,
            logger=mock_logger,
        )

        assert action_context.booking == original_booking
        assert new_context.booking == booking2


# ============================================================================
# Tests: register_actions
# ============================================================================


class TestRegisterActions:
    """Tests for register_actions helper function."""

    def test_register_actions_registers_all_executors(self, services_bundle):
        """Test that register_actions registers all 6 executors."""
        mock_engine = Mock()

        register_actions(mock_engine, services_bundle)

        assert mock_engine.register_action.call_count == 6
        registered_names = [
            call_args[0][0] for call_args in mock_engine.register_action.call_args_list
        ]

        expected = {
            "send_sms",
            "create_db_record",
            "update_flag",
            "send_telegram",
            "send_slack",
            "log_event",
        }
        assert set(registered_names) == expected

    def test_register_actions_with_missing_booking(self, services_bundle):
        """Test that wrapper raises error if booking not in context."""
        mock_engine = Mock()

        register_actions(mock_engine, services_bundle)

        # Get the send_sms wrapper
        send_sms_wrapper = mock_engine.register_action.call_args_list[0][0][1]

        # Call with missing booking
        with pytest.raises(ValueError) as exc_info:
            send_sms_wrapper({})  # Empty context, no booking

        assert "Booking not found" in str(exc_info.value)

    def test_register_actions_send_sms_wrapper(self, services_bundle, mock_booking):
        """Test that send_sms wrapper correctly injects context."""
        mock_engine = Mock()

        register_actions(mock_engine, services_bundle)

        # Get the send_sms wrapper (first registration)
        send_sms_wrapper = mock_engine.register_action.call_args_list[0][0][1]

        rule_context = {"booking": mock_booking}

        # Call wrapper with template parameter
        send_sms_wrapper(rule_context, template="confirm")

        # Verify SMS service was called
        services_bundle.sms_service.send_confirm_sms.assert_called_once()
