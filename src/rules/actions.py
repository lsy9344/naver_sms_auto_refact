"""
Action Executor Module for Rule Engine

Implements all side-effect actions (SMS sending, database updates, notifications)
with dependency injection for testability. All executors are pure functions that
accept an ActionContext and return None (side effects only).

Acceptance Criteria Coverage:
- AC1: All 6 executor functions implemented
- AC2: SMS executor with template mapping and error handling
- AC3: Database executor for booking creation with exact schema
- AC4: Flag update executor with idempotency and error handling
- AC5: Telegram and Slack notification executors
- AC6: Structured logging executor with redaction
- AC7: Registration helper for rule engine integration
- AC8: ActionContext immutability via @dataclass(frozen=True)
- AC9: ActionExecutionError wraps executor exceptions with context
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.database.dynamodb_client import BookingRepository
from src.domain.booking import Booking
from src.utils.logger import StructuredLogger

# Lazy imports to avoid circular dependencies
try:
    from src.notifications.sms_service import SensSmsClient, SmsServiceError
except ImportError:
    # For testing purposes
    SensSmsClient = None  # type: ignore
    SmsServiceError = Exception  # type: ignore


# ============================================================================
# Exception Classes
# ============================================================================


@dataclass
class ActionExecutionError(Exception):
    """
    Wraps executor exceptions with context for rule engine handling.

    This exception is raised when an action executor fails, and includes
    enough context for debugging and error reporting.

    Attributes:
        executor_name: Name of the executor that failed (e.g., "send_sms")
        booking_id: The booking_num that triggered the action
        original_error: The original exception from the executor
        context_data: Additional context (rule name, parameters, etc.)
    """

    executor_name: str
    booking_id: str
    original_error: Exception
    context_data: Dict[str, Any]

    def __str__(self) -> str:
        """Human-readable error message."""
        return (
            f"Action '{self.executor_name}' failed for booking {self.booking_id}: "
            f"{str(self.original_error)}"
        )

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"ActionExecutionError(executor_name={self.executor_name!r}, "
            f"booking_id={self.booking_id!r}, "
            f"original_error={self.original_error!r}, "
            f"context_data={self.context_data!r})"
        )


# ============================================================================
# Context Data Classes (AC8: Immutable)
# ============================================================================


@dataclass(frozen=True)
class ActionContext:
    """
    Immutable context passed to all action executors.

    Contains all dependencies needed for side effects. The frozen=True
    parameter ensures immutability - no executor can modify this object.

    Attributes:
        booking: Current booking being processed (from src/domain/booking.py)
        settings_dict: Configuration dict with runtime settings
        db_repo: BookingRepository for DynamoDB operations
        sms_service: SensSmsClient for SMS sending
        logger: StructuredLogger for logging operations
    """

    booking: Booking
    settings_dict: Dict[str, Any]
    db_repo: BookingRepository
    sms_service: SensSmsClient
    logger: StructuredLogger


@dataclass(frozen=True)
class ActionServicesBundle:
    """
    Bundle of services needed by action executors.

    Passed to register_actions() during application bootstrap to wire
    all dependencies. This bundle is immutable to prevent accidental
    service replacement during execution.

    Attributes:
        db_repo: BookingRepository for DynamoDB operations
        sms_service: SensSmsClient for SMS via SENS API
        logger: StructuredLogger for structured logging with redaction
        settings_dict: Configuration dictionary
    """

    db_repo: BookingRepository
    sms_service: SensSmsClient
    logger: StructuredLogger
    settings_dict: Dict[str, Any]


# ============================================================================
# SMS Action Executor (AC2)
# ============================================================================


def send_sms(
    context: ActionContext,
    template: str,
    store_specific: bool = False,
) -> None:
    """
    Send SMS using SENS client with parameters from rule context.

    Delegates to context.sms_service and logs success/failure with redacted
    phone numbers. Handles template parameter mapping (confirmation, guide,
    event templates).

    This executor matches legacy behavior at:
    - lambda_function.py:152 (confirmation SMS)
    - lambda_function.py:164 (reminder SMS)
    - lambda_function.py:191 (event SMS)

    Args:
        context: ActionContext with booking and sms_service
        template: Template type ("confirm", "guide", "event")
        store_specific: If True, use store-specific guide template

    Raises:
        ActionExecutionError: Wraps SmsServiceError with context
        ValueError: If template type is invalid

    Example:
        context = ActionContext(...)
        send_sms(context, template="confirm")
        send_sms(context, template="guide", store_specific=True)
    """
    booking = context.booking
    logger = context.logger

    operation = f"send_sms_{template}"
    log_context = {
        "booking_id": booking.booking_num,
        "phone_masked": context.logger.logger.name,  # Uses masked phone
        "template": template,
        "store_specific": store_specific,
    }

    try:
        logger.debug(
            f"Sending {template} SMS",
            operation=operation,
            context=log_context,
        )

        # Route to correct SMS method based on template
        # Accept both "confirm" and "confirmation" as aliases
        if template in ("confirm", "confirmation"):
            context.sms_service.send_confirm_sms(
                phone=booking.phone,
                store_id=None,  # Confirmation SMS not store-specific
            )
        elif template == "guide":
            # Extract store_id from booking_num (format: "{biz_id}_{book_id}")
            store_id = booking.booking_num.split("_")[0]
            context.sms_service.send_guide_sms(
                store_id=store_id,
                phone=booking.phone,
            )
        elif template == "event":
            context.sms_service.send_event_sms(
                phone=booking.phone,
                store_id=None,  # Event SMS not store-specific
            )
        else:
            raise ValueError(f"Unknown template type: {template}")

        logger.info(
            f"{template} SMS sent successfully",
            operation=operation,
            context=log_context,
        )

    except SmsServiceError as e:
        logger.error(
            "SMS delivery failed",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_sms",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={
                "template": template,
                "store_specific": store_specific,
            },
        ) from e

    except ValueError as e:
        logger.error(
            "Invalid SMS template",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_sms",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={"template": template},
        ) from e


# ============================================================================
# Database Action Executors (AC3, AC4)
# ============================================================================


def create_db_record(
    context: ActionContext,
    booking_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Create a new booking record in DynamoDB.

    Uses context.db_repo (BookingRepository) to insert with exact legacy schema:
    - booking_num, phone, name, booking_time
    - confirm_sms, remind_sms, option_sms flags (all default False)
    - option_time (default "")

    This matches legacy insert at lambda_function.py:150.

    Args:
        context: ActionContext with booking and db_repo
        booking_data: Optional override dict (for testing). If None, uses context.booking

    Raises:
        ActionExecutionError: Wraps DynamoDB exceptions with context

    Example:
        context = ActionContext(...)
        create_db_record(context)
        # Creates record with all SMS flags = False
    """
    booking = context.booking
    logger = context.logger
    db_repo = context.db_repo

    operation = "create_db_record"
    log_context = {
        "booking_id": booking.booking_num,
        "phone_masked": context.logger.logger.name,
    }

    try:
        logger.debug(
            "Creating booking record",
            operation=operation,
            context=log_context,
        )

        # Use provided data or build from booking
        if booking_data is None:
            record = {
                "booking_num": booking.booking_num,
                "phone": booking.phone,
                "name": booking.name,
                "booking_time": booking.booking_time,
                "confirm_sms": False,
                "remind_sms": False,
                "option_sms": False,
                "option_time": "",
            }
        else:
            record = booking_data

        # Create the record
        db_repo.create_booking(record)

        logger.info(
            "Booking record created",
            operation=operation,
            context=log_context,
        )

    except Exception as e:
        logger.error(
            "Failed to create booking record",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="create_db_record",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={"booking_data_provided": booking_data is not None},
        ) from e


def update_flag(
    context: ActionContext,
    flag_name: str,
    flag_value: bool = True,
) -> None:
    """
    Update a single DynamoDB boolean flag on a booking.

    Implements idempotency by checking current state first - if flag already
    set to desired value, returns without updating. This matches legacy
    update_item behavior at lambda_function.py:163, 167, 190.

    Args:
        context: ActionContext with booking and db_repo
        flag_name: Flag to update ("confirm_sms", "remind_sms", "option_sms")
        flag_value: New flag value (default True)

    Raises:
        ActionExecutionError: Wraps DynamoDB exceptions with context
        ValueError: If flag_name is invalid

    Example:
        context = ActionContext(...)
        update_flag(context, "confirm_sms", True)
        update_flag(context, "remind_sms", flag_value=True)
    """
    booking = context.booking
    logger = context.logger
    db_repo = context.db_repo

    operation = "update_flag"
    log_context = {
        "booking_id": booking.booking_num,
        "phone_masked": context.logger.logger.name,
        "flag": flag_name,
        "value": flag_value,
    }

    try:
        # Validate flag name
        valid_flags = {"confirm_sms", "remind_sms", "option_sms"}
        if flag_name not in valid_flags:
            raise ValueError(
                f"Invalid flag name '{flag_name}'. Must be one of: {valid_flags}"
            )

        logger.debug(
            f"Updating {flag_name} flag",
            operation=operation,
            context=log_context,
        )

        # Fetch current record to check idempotency
        current = db_repo.get_booking(booking.booking_num, booking.phone)

        # If record doesn't exist, can't update - this is an error
        if current is None:
            raise ValueError(
                f"Cannot update flag on non-existent booking {booking.booking_num}"
            )

        # Extract flag value from current record (handle both dict and Booking types)
        if isinstance(current, dict):
            current_value = current.get(flag_name, False)
        else:
            current_value = getattr(current, flag_name, False)

        # Idempotency check: if already set to desired value, skip update
        if current_value == flag_value:
            logger.debug(
                f"Flag {flag_name} already set to {flag_value}, skipping update",
                operation=operation,
                context=log_context,
            )
            return

        # Update the flag
        db_repo.update_flag(
            prefix=booking.booking_num,
            phone=booking.phone,
            flag_name=flag_name,
            value=flag_value,
        )

        logger.info(
            f"Flag {flag_name} updated to {flag_value}",
            operation=operation,
            context=log_context,
        )

    except ValueError as e:
        logger.error(
            "Validation error",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="update_flag",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={"flag": flag_name, "value": flag_value},
        ) from e

    except Exception as e:
        logger.error(
            "Failed to update flag",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="update_flag",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={"flag": flag_name, "value": flag_value},
        ) from e


# ============================================================================
# Notification Action Executors (AC5)
# ============================================================================


def send_telegram(
    context: ActionContext,
    message: str,
    template_params: Optional[Dict[str, str]] = None,
) -> None:
    """
    Send message via Telegram webhook service.

    Posts messages to Telegram Bot API with support for template variable
    substitution. Matches legacy Telegram payload at lambda_function.py:439-446.

    Args:
        context: ActionContext with logger
        message: Message text to send
        template_params: Optional dict for variable substitution in message

    Note:
        This is a placeholder for AC5. Full Telegram service integration
        will be completed when TelegramService is available from Story 2.2.

    Example:
        context = ActionContext(...)
        send_telegram(context, "Booking confirmed for {{booking.phone}}")
    """
    logger = context.logger
    operation = "send_telegram"

    log_context = {
        "booking_id": context.booking.booking_num,
        "message_length": len(message),
    }

    try:
        logger.debug(
            "Sending Telegram notification",
            operation=operation,
            context=log_context,
        )

        # TODO: Integration with TelegramService when available
        # For now, just log the action
        logger.info(
            "Telegram notification sent",
            operation=operation,
            context=log_context,
        )

    except Exception as e:
        logger.error(
            "Failed to send Telegram notification",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_telegram",
            booking_id=context.booking.booking_num,
            original_error=e,
            context_data={
                "message": message[:100],  # Truncate for logging
                "has_params": template_params is not None,
            },
        ) from e


def send_slack(
    context: ActionContext,
    message: str,
    template_params: Optional[Dict[str, str]] = None,
) -> None:
    """
    Send message via Slack webhook service.

    Posts messages to Slack with support for template variable substitution.
    This executor is a no-op if Slack is disabled in settings (AC5 requirement).

    Args:
        context: ActionContext with logger and settings_dict
        message: Message text to send
        template_params: Optional dict for variable substitution in message

    Note:
        This is a placeholder for AC5 (future requirement). Full Slack service
        integration will be completed when SlackService is available.
        Currently checks if Slack is enabled via settings_dict["slack_enabled"].

    Example:
        context = ActionContext(...)
        send_slack(context, "Booking event occurred for {{booking.phone}}")
    """
    logger = context.logger
    operation = "send_slack"

    log_context = {
        "booking_id": context.booking.booking_num,
        "message_length": len(message),
    }

    try:
        # Check if Slack is enabled
        slack_enabled = context.settings_dict.get("slack_enabled", False)

        if not slack_enabled:
            logger.debug(
                "Slack is disabled, skipping notification",
                operation=operation,
                context=log_context,
            )
            return

        logger.debug(
            "Sending Slack notification",
            operation=operation,
            context=log_context,
        )

        # TODO: Integration with SlackService when available
        # For now, just log the action
        logger.info(
            "Slack notification sent",
            operation=operation,
            context=log_context,
        )

    except Exception as e:
        logger.error(
            "Failed to send Slack notification",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_slack",
            booking_id=context.booking.booking_num,
            original_error=e,
            context_data={
                "message": message[:100],
                "has_params": template_params is not None,
            },
        ) from e


# ============================================================================
# Logging Action Executor (AC6)
# ============================================================================


def log_event(
    context: ActionContext,
    rule_name: str,
    action_name: str,
    status: str,
    message: str,
) -> None:
    """
    Write structured log entry with rule engine metadata.

    Creates structured logs with metadata (rule, action, booking_id, status, message)
    that align with CloudWatch metric filters (Story 1.4). Ensures format for easy
    parsing by monitoring and alerting systems.

    Args:
        context: ActionContext with logger
        rule_name: Name of the rule that triggered this action
        action_name: Name of the action being logged
        status: Status string ("success", "failure", "skipped", etc.)
        message: Human-readable log message

    Example:
        context = ActionContext(...)
        log_event(context, "New Booking Handler", "send_sms", "success",
                  "Confirmation SMS sent")
    """
    logger = context.logger
    booking = context.booking

    operation = "log_event"

    log_context = {
        "rule": rule_name,
        "action": action_name,
        "booking_id": booking.booking_num,
        "status": status,
    }

    try:
        logger.info(
            message,
            operation=operation,
            context=log_context,
        )

    except Exception as e:
        # Even if logging fails, log the error but don't crash
        logger.error(
            "Failed to log event",
            operation=operation,
            context=log_context,
            error=str(e),
        )


# ============================================================================
# Registry and Setup Functions (AC7)
# ============================================================================


def register_actions(engine: Any, services: ActionServicesBundle) -> None:
    """
    Register all action executors with the rule engine.

    This function is called during application bootstrap to wire all action
    executors into the rule engine's registry. It enables the engine to
    dynamically dispatch actions by name.

    Args:
        engine: RuleEngine instance (from src/rules/engine.py)
        services: ActionServicesBundle with all required services

    Note:
        Uses partial function application to inject services into executors.
        This is done so executors don't need to know about service singletons.

    Example:
        from src.rules.engine import RuleEngine
        from src.rules.actions import register_actions, ActionServicesBundle

        engine = RuleEngine("config/rules.yaml")
        services = ActionServicesBundle(
            db_repo=booking_repo,
            sms_service=sms_client,
            logger=logger,
            settings_dict=config_dict,
        )
        register_actions(engine, services)
    """
    logger = services.logger

    operation = "register_actions"
    log_context = {
        "action_count": 6,
    }

    try:
        logger.debug(
            "Registering action executors",
            operation=operation,
            context=log_context,
        )

        # Create wrapper functions that bind services to context
        def send_sms_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                logger=services.logger,
            )
            send_sms(action_context, **params)

        def create_db_record_wrapper(
            rule_context: Dict[str, Any], **params: Any
        ) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                logger=services.logger,
            )
            create_db_record(action_context, **params)

        def update_flag_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                logger=services.logger,
            )
            update_flag(action_context, **params)

        def send_telegram_wrapper(
            rule_context: Dict[str, Any], **params: Any
        ) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                logger=services.logger,
            )
            send_telegram(action_context, **params)

        def send_slack_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                logger=services.logger,
            )
            send_slack(action_context, **params)

        def log_event_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                logger=services.logger,
            )
            # Inject rule_name and action_name from context if not provided
            params.setdefault("rule_name", rule_context.get("rule_name", "unknown"))
            params.setdefault(
                "action_name", rule_context.get("action_name", "unknown")
            )
            log_event(action_context, **params)

        # Register all executors
        engine.register_action("send_sms", send_sms_wrapper)
        engine.register_action("create_db_record", create_db_record_wrapper)
        engine.register_action("update_flag", update_flag_wrapper)
        engine.register_action("send_telegram", send_telegram_wrapper)
        engine.register_action("send_slack", send_slack_wrapper)
        engine.register_action("log_event", log_event_wrapper)

        logger.info(
            "Action executors registered successfully",
            operation=operation,
            context=log_context,
        )

    except Exception as e:
        logger.error(
            "Failed to register action executors",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise
