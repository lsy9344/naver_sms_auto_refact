"""
Integration tests for action executors.

Tests verify that action executors work correctly with their dependencies
and that multiple actions can be chained together in a workflow.
"""

import pytest
from unittest.mock import Mock

from src.rules.actions import (
    ActionContext,
    ActionServicesBundle,
    send_sms,
    create_db_record,
    update_flag,
    send_telegram,
    send_slack,
    log_event,
    register_actions,
    TelegramTemplateLoader,
)
from src.domain.booking import Booking


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def booking():
    """Create a booking for testing."""
    return Booking(
        booking_num="1051707_12345",
        phone="010-1234-5678",
        name="Test Customer",
        booking_time="2025-10-20 14:00:00",
        biz_id="1051707",
        confirm_sms=False,
        remind_sms=False,
        option_sms=False,
        option_time="",
    )


@pytest.fixture
def mock_db_repo():
    """Create a mock BookingRepository that simulates DynamoDB behavior."""
    repo = Mock()

    # Simulate DynamoDB storage
    repo._storage = {}

    def create_booking(record):
        key = (record["booking_num"], record["phone"])
        repo._storage[key] = record
        return True

    def get_booking(prefix, phone):
        key = (prefix, phone)
        return repo._storage.get(key)

    def update_flag(prefix, phone, flag_name, value):
        key = (prefix, phone)
        if key in repo._storage:
            repo._storage[key][flag_name] = value
        return True

    repo.create_booking.side_effect = create_booking
    repo.get_booking.side_effect = get_booking
    repo.update_flag.side_effect = update_flag

    return repo


@pytest.fixture
def mock_sms_service():
    """Create a mock SMS service."""
    service = Mock()
    service.send_confirm_sms = Mock()
    service.send_guide_sms = Mock()
    service.send_event_sms = Mock()
    return service


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = Mock()
    logger.logger.name = "test_logger"
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def mock_slack_service():
    """Create a mock Slack service."""
    service = Mock()
    service._dispatch = Mock()
    return service


@pytest.fixture
def mock_slack_template_loader():
    """Create a mock Slack template loader."""
    loader = Mock()
    loader.render.return_value = "Rendered template message"
    return loader


@pytest.fixture
def mock_telegram_template_loader():
    """Create a mock Telegram template loader."""
    loader = Mock()
    loader.render.return_value = {"text": "Rendered Telegram message", "parse_mode": "Markdown"}
    return loader


@pytest.fixture
def mock_telegram_service():
    """Create a mock Telegram service."""
    service = Mock()
    service.send_message = Mock()
    service.send_notification = Mock()
    return service


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
    """Create a services bundle for integration testing."""
    return ActionServicesBundle(
        db_repo=mock_db_repo,
        sms_service=mock_sms_service,
        settings_dict={"slack_enabled": False},
        logger=mock_logger,
        slack_service=mock_slack_service,
        slack_template_loader=mock_slack_template_loader,
        telegram_template_loader=mock_telegram_template_loader,
        telegram_service=mock_telegram_service,
    )


@pytest.fixture
def action_context(booking, services_bundle):
    """Create an ActionContext for testing."""
    return ActionContext(
        booking=booking,
        settings_dict=services_bundle.settings_dict,
        db_repo=services_bundle.db_repo,
        sms_service=services_bundle.sms_service,
        slack_service=services_bundle.slack_service,
        slack_template_loader=services_bundle.slack_template_loader,
        telegram_template_loader=services_bundle.telegram_template_loader,
        telegram_service=services_bundle.telegram_service,
        logger=services_bundle.logger,
    )


# ============================================================================
# Integration Tests: Workflow Scenarios
# ============================================================================


class TestNewBookingWorkflow:
    """Test complete new booking workflow."""

    def test_new_booking_creates_record_and_sends_sms(self, booking, services_bundle):
        """Test creating booking and sending SMS."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        # Step 1: Create booking record
        create_db_record(context)

        # Verify booking was created
        retrieved = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert retrieved is not None
        assert retrieved["booking_num"] == booking.booking_num
        assert retrieved["confirm_sms"] is False

        # Step 2: Send confirmation SMS
        send_sms(context, template="confirm")

        # Verify SMS was sent
        services_bundle.sms_service.send_confirm_sms.assert_called_once_with(
            phone=booking.phone, store_id=None
        )

        # Step 3: Update confirmation flag
        update_flag(context, flag_name="confirm_sms", flag_value=True)

        # Verify flag was updated
        retrieved = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert retrieved["confirm_sms"] is True


class TestReminderWorkflow:
    """Test reminder SMS workflow."""

    def test_send_guide_sms_and_update_flag(self, booking, services_bundle):
        """Test sending guide SMS and updating reminder flag."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        # Create booking first
        create_db_record(context)

        # Send guide SMS
        send_sms(context, template="guide", store_specific=True)

        services_bundle.sms_service.send_guide_sms.assert_called_once_with(
            store_id="1051707",
            phone=booking.phone,
        )

        # Update reminder flag
        update_flag(context, flag_name="remind_sms", flag_value=True)

        # Verify flag was updated
        retrieved = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert retrieved["remind_sms"] is True


class TestEventSMSWorkflow:
    """Test event SMS workflow."""

    def test_send_event_sms_and_update_flag(self, booking, services_bundle):
        """Test sending event SMS and updating flag."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        # Create booking
        create_db_record(context)

        # Send event SMS
        send_sms(context, template="event")

        services_bundle.sms_service.send_event_sms.assert_called_once_with(
            phone=booking.phone, store_id=None
        )

        # Update option flag
        update_flag(context, flag_name="option_sms", flag_value=True)

        # Verify flag was updated
        retrieved = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert retrieved["option_sms"] is True


class TestMultipleActionsSequence:
    """Test executing multiple actions in sequence."""

    def test_complete_booking_lifecycle(self, booking, services_bundle):
        """Test complete booking lifecycle with all actions."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        # 1. Create booking
        create_db_record(context)
        record = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert record is not None

        # 2. Send confirmation
        send_sms(context, template="confirm")
        assert services_bundle.sms_service.send_confirm_sms.called

        # 3. Update confirmation flag
        update_flag(context, flag_name="confirm_sms", flag_value=True)

        # 4. Send guide
        send_sms(context, template="guide", store_specific=True)
        assert services_bundle.sms_service.send_guide_sms.called

        # 5. Update reminder flag
        update_flag(context, flag_name="remind_sms", flag_value=True)

        # 6. Send event SMS
        send_sms(context, template="event")
        assert services_bundle.sms_service.send_event_sms.called

        # 7. Update option flag
        update_flag(context, flag_name="option_sms", flag_value=True)

        # Verify final state
        final_record = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert final_record["confirm_sms"] is True
        assert final_record["remind_sms"] is True
        assert final_record["option_sms"] is True


class TestActionErrorRecovery:
    """Test error handling and recovery."""

    def test_error_in_one_action_does_not_prevent_others(self, booking, services_bundle):
        """Test that errors don't cascade."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        # Create booking
        create_db_record(context)

        # Make SMS fail
        services_bundle.sms_service.send_confirm_sms.side_effect = Exception("API error")

        # SMS action should fail
        with pytest.raises(Exception):
            send_sms(context, template="confirm")

        # But database actions should still work
        update_flag(context, flag_name="confirm_sms", flag_value=True)

        # Verify flag was still updated
        retrieved = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert retrieved["confirm_sms"] is True


class TestIdempotencyWithMultipleUpdates:
    """Test idempotency of update operations."""

    def test_multiple_flag_updates_are_idempotent(self, booking, services_bundle):
        """Test that repeated updates don't cause issues."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        # Create booking
        create_db_record(context)

        # Update flag multiple times
        update_flag(context, flag_name="confirm_sms", flag_value=True)
        update_flag(context, flag_name="confirm_sms", flag_value=True)
        update_flag(context, flag_name="confirm_sms", flag_value=True)

        # Should still be True
        retrieved = services_bundle.db_repo.get_booking(
            prefix=booking.booking_num, phone=booking.phone
        )
        assert retrieved["confirm_sms"] is True


class TestNotificationActions:
    """Test notification action executors."""

    def test_telegram_and_slack_notifications(self, booking, services_bundle):
        """Test sending Telegram and Slack notifications."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
            telegram_template_loader=services_bundle.telegram_template_loader,
            telegram_service=services_bundle.telegram_service,
            logger=services_bundle.logger,
        )

        # Send Telegram notification
        send_telegram(context, message="Test booking confirmed")
        services_bundle.telegram_service.send_message.assert_called_once_with(
            text="Test booking confirmed",
            parse_mode="Markdown",
        )
        assert services_bundle.logger.info.called

        # Send Slack notification (disabled by default)
        context.settings_dict["slack_enabled"] = False
        send_slack(context, message="Test booking event")

        # Should have called debug for disabled check
        assert services_bundle.logger.debug.called

        # Enable Slack and try again
        services_bundle.logger.reset_mock()
        context.settings_dict["slack_enabled"] = True
        send_slack(context, message="Test booking event")

        # Should now call info
        assert services_bundle.logger.info.called

    def test_telegram_template_rendering_with_real_loader(
        self,
        booking,
        mock_telegram_service,
        mock_logger,
    ):
        """Ensure Telegram templates render with real loader configuration."""
        loader = TelegramTemplateLoader(logger=mock_logger)
        context = ActionContext(
            booking=booking,
            settings_dict={"slack_enabled": False},
            db_repo=Mock(),
            sms_service=Mock(),
            slack_service=None,
            slack_template_loader=None,
            telegram_template_loader=loader,
            telegram_service=mock_telegram_service,
            logger=mock_logger,
        )

        send_telegram(
            context,
            template_name="sms_confirmation",
            template_params={
                "customer_name": booking.name,
                "customer_phone": booking.phone,
                "booking_number": booking.booking_num,
            },
        )

        mock_telegram_service.send_message.assert_called_once()
        call_kwargs = mock_telegram_service.send_message.call_args.kwargs
        assert "예약 확인 문자 발송 완료" in call_kwargs["text"]
        assert booking.phone in call_kwargs["text"]


class TestLoggingActions:
    """Test logging action executor."""

    def test_log_event_captures_metadata(self, booking, services_bundle):
        """Test that log_event captures all metadata."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        # Log event
        log_event(
            context,
            rule_name="New Booking Handler",
            action_name="send_sms",
            status="success",
            message="SMS sent successfully",
        )

        # Verify logging was called
        assert services_bundle.logger.info.called

    def test_log_event_with_different_statuses(self, booking, services_bundle):
        """Test logging with various status values."""
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            logger=services_bundle.logger,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
        )

        statuses = ["success", "failure", "skipped", "retry"]

        for status in statuses:
            services_bundle.logger.reset_mock()

            log_event(
                context,
                rule_name="Test Rule",
                action_name="test_action",
                status=status,
                message=f"Action {status}",
            )

            assert services_bundle.logger.info.called


class TestRegisterActionsIntegration:
    """Test register_actions helper integration."""

    def test_register_actions_creates_working_wrappers(self, booking, services_bundle):
        """Test that registered actions work correctly."""
        mock_engine = Mock()

        # Register actions
        register_actions(mock_engine, services_bundle)

        # Get the send_sms wrapper
        send_sms_wrapper = mock_engine.register_action.call_args_list[0][0][1]

        # Call wrapper
        rule_context = {"booking": booking}
        send_sms_wrapper(rule_context, template="confirm")

        # Verify SMS service was called
        assert services_bundle.sms_service.send_confirm_sms.called

    def test_all_six_actions_registered(self, services_bundle):
        """Test that all 6 actions are registered."""
        mock_engine = Mock()

        register_actions(mock_engine, services_bundle)

        registered_names = {
            call_args[0][0] for call_args in mock_engine.register_action.call_args_list
        }

        expected = {
            "send_sms",
            "create_db_record",
            "update_flag",
            "send_telegram",
            "send_slack",
            "log_event",
        }

        assert registered_names == expected


class TestMessageTemplateVariableResolution:
    """Test that template variables in message parameters are resolved correctly.

    This tests the fix for the issue where messages like
    "예약확정 {{ store.alias }} {{ booking.name }} {{ booking.phone_masked }}"
    were being sent with template variables unresolved.
    """

    def test_telegram_message_variable_resolution_from_rule_context(self, booking, services_bundle):
        """Test that Telegram message variables are resolved from booking in rule context."""
        # Create action context
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
            telegram_template_loader=services_bundle.telegram_template_loader,
            telegram_service=services_bundle.telegram_service,
            logger=services_bundle.logger,
        )

        # Call send_telegram with a message containing template variables
        send_telegram(
            context,
            message="예약확정 {{ booking.name }} {{ booking.phone_masked }}",
            parse_mode="Markdown",
        )

        # Verify telegram service was called with resolved message
        services_bundle.telegram_service.send_message.assert_called_once()
        call_args = services_bundle.telegram_service.send_message.call_args
        sent_text = call_args[1]["text"]

        # Message should have template variable resolved
        assert sent_text == "예약확정 Test Customer 010-****-5678"
        assert "{{ booking.name }}" not in sent_text
        assert "{{ booking.phone_masked }}" not in sent_text

    def test_slack_message_variable_resolution_from_rule_context(self, booking, services_bundle):
        """Test that Slack message variables are resolved from booking in rule context."""
        # Enable Slack for this test
        services_bundle.settings_dict["slack_enabled"] = True

        # Create action context
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
            telegram_template_loader=services_bundle.telegram_template_loader,
            telegram_service=services_bundle.telegram_service,
            logger=services_bundle.logger,
        )

        # Call send_slack with a message containing template variables
        send_slack(context, message="[상세안내] {{ booking.name }}")

        # Verify slack service was called with resolved message
        services_bundle.slack_service.send_text.assert_called_once()
        call_args = services_bundle.slack_service.send_text.call_args
        sent_text = call_args[0][0]

        # Message should have template variable resolved
        assert sent_text == "[상세안내] Test Customer"
        assert "{{ booking.name }}" not in sent_text

    def test_message_variable_resolution_through_rule_engine_wrapper(
        self, booking, services_bundle
    ):
        """Test template variable resolution when called through register_actions wrappers.

        This simulates the actual flow: rules.yaml -> rule engine -> action wrapper -> send_telegram.
        """
        # Create a mock rule engine
        mock_engine = Mock()
        action_wrappers = {}

        def capture_action_wrapper(action_name):
            def capture(executor_func):
                action_wrappers[action_name] = executor_func
                return executor_func

            return capture

        mock_engine.register_action.side_effect = lambda name, func: action_wrappers.update(
            {name: func}
        )

        # Register actions
        register_actions(mock_engine, services_bundle)

        # Get the send_telegram_wrapper that was registered
        assert "send_telegram" in action_wrappers
        send_telegram_wrapper = action_wrappers["send_telegram"]

        # Simulate rule engine calling the wrapper with rule context
        # (This is what happens in engine.py execute_rule when a send_telegram action runs)
        rule_context = {
            "booking": booking,
            "store": {
                "alias": "테스트점",
                "id": "1051707",
            },
        }
        params = {
            "message": "예약확정 {{ store.alias }} {{ booking.name }} {{ booking.phone_masked }}"
        }

        send_telegram_wrapper(rule_context, **params)

        # Verify telegram service was called with resolved message
        services_bundle.telegram_service.send_message.assert_called_once()
        call_args = services_bundle.telegram_service.send_message.call_args
        sent_text = call_args[1]["text"]

        # Message should have template variable resolved
        assert sent_text == "예약확정 테스트점 Test Customer 010-****-5678"
        assert "{{" not in sent_text

    def test_multiple_template_variables_in_message(self, services_bundle):
        """Test that multiple template variables in a single message are all resolved."""
        # Create a booking with Korean name
        booking = Booking(
            booking_num="1051707_99999",
            phone="010-9999-9999",
            name="홍길동",
            booking_time="2025-10-20 14:00:00",
        )

        # Create action context
        context = ActionContext(
            booking=booking,
            settings_dict=services_bundle.settings_dict,
            db_repo=services_bundle.db_repo,
            sms_service=services_bundle.sms_service,
            slack_service=services_bundle.slack_service,
            slack_template_loader=services_bundle.slack_template_loader,
            telegram_template_loader=services_bundle.telegram_template_loader,
            telegram_service=services_bundle.telegram_service,
            logger=services_bundle.logger,
        )

        # Send message with multiple template variables
        send_telegram(
            context,
            message="예약자: {{ booking.name }}, 예약번호: {{ booking.booking_num }}",
            parse_mode="Markdown",
        )

        # Verify both variables were resolved
        services_bundle.telegram_service.send_message.assert_called_once()
        call_args = services_bundle.telegram_service.send_message.call_args
        sent_text = call_args[1]["text"]

        # Both variables should be resolved
        assert sent_text == "예약자: 홍길동, 예약번호: 1051707_99999"
        assert "{{" not in sent_text
        assert "}}" not in sent_text
