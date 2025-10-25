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

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, cast

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

try:
    from src.notifications.slack_service import SlackWebhookClient, SlackServiceError
except ImportError:
    # For testing purposes
    SlackWebhookClient = None  # type: ignore
    SlackServiceError = Exception  # type: ignore

try:
    from src.notifications.telegram_service import TelegramBotClient, TelegramServiceError
except ImportError:
    # For testing purposes
    TelegramBotClient = None  # type: ignore
    TelegramServiceError = Exception  # type: ignore

try:
    import jinja2
except ImportError:
    jinja2 = None  # type: ignore


_TEMPLATE_PARAM_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")
_PARSE_MODE_UNSET = object()


def _lookup_context_value(path: str, context: Dict[str, Any]) -> Any:
    """
    Resolve dot-delimited path from rule context.

    Supports dictionary lookups and attribute access (for Booking objects).
    """
    value: Any = context

    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)

        if value is None:
            break

    return value


def _resolve_template_params(raw_params: Any, context: Dict[str, Any]) -> Any:
    """
    Resolve template parameters that reference rule context placeholders.

    Allows YAML configs to specify values such as "{{ bookings_with_expert_correction }}".
    """
    if isinstance(raw_params, dict):
        return {key: _resolve_template_params(value, context) for key, value in raw_params.items()}

    if isinstance(raw_params, list):
        return [_resolve_template_params(item, context) for item in raw_params]

    if isinstance(raw_params, str):
        match = _TEMPLATE_PARAM_PATTERN.fullmatch(raw_params.strip())
        if match:
            resolved = _lookup_context_value(match.group(1), context)
            return resolved
        return raw_params

    return raw_params


# ============================================================================
# Template Loader (AC 3)
# ============================================================================


class SlackTemplateLoader:
    """
    Loader for Slack message templates from YAML configuration.

    Supports Jinja2 template rendering with variable substitution.
    Templates are cached in memory after first load.
    """

    def __init__(
        self,
        template_path: str = "config/slack_templates.yaml",
        logger: Optional[StructuredLogger] = None,
    ):
        """
        Initialize template loader.

        Args:
            template_path: Path to slack_templates.yaml file
            logger: Optional structured logger instance
        """
        self.template_path = template_path
        self.logger = logger
        self._templates: Dict[str, str] = {}
        self._loaded = False

    def load_templates(self) -> None:
        """Load all templates from YAML file."""
        if self._loaded:
            return

        try:
            import yaml

            with open(self.template_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
                self._templates = content
                self._loaded = True
                if self.logger:
                    self.logger.debug(
                        f"Loaded {len(self._templates)} Slack templates",
                        operation="load_slack_templates",
                    )
        except FileNotFoundError as e:
            if self.logger:
                self.logger.error(
                    f"Slack templates file not found: {self.template_path}",
                    operation="load_slack_templates",
                    error=str(e),
                )
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "Failed to load Slack templates",
                    operation="load_slack_templates",
                    error=str(e),
                )
            raise

    def render(self, template_name: str, **context: Any) -> str:
        """
        Render a template with context variables.

        Args:
            template_name: Name of template (key in slack_templates.yaml)
            **context: Variables to inject into template

        Returns:
            Rendered template string

        Raises:
            ValueError: If template not found
            jinja2.TemplateError: If template rendering fails
        """
        if not self._loaded:
            self.load_templates()

        if template_name not in self._templates:
            raise ValueError(
                f"Template '{template_name}' not found. Available: {list(self._templates.keys())}"
            )

        if not jinja2:
            raise RuntimeError("jinja2 is required for template rendering")

        template_str = self._templates[template_name]
        try:
            template = jinja2.Template(template_str)
            return template.render(**context)
        except jinja2.TemplateError as e:
            if self.logger:
                self.logger.error(
                    f"Failed to render Slack template '{template_name}'",
                    operation="render_slack_template",
                    error=str(e),
                )
            raise

    def get_template_names(self) -> list:
        """Get list of available template names."""
        if not self._loaded:
            self.load_templates()
        return list(self._templates.keys())


class TelegramTemplateLoader:
    """
    Loader for Telegram message templates from YAML configuration.

    Supports optional parse mode configuration per template and Jinja2 rendering.
    Templates are cached in memory after first load to minimise file I/O.
    """

    def __init__(
        self,
        template_path: str = "config/telegram_templates.yaml",
        logger: Optional[StructuredLogger] = None,
    ):
        """Initialize template loader."""
        self.template_path = template_path
        self.logger = logger
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def load_templates(self) -> None:
        """Load templates from YAML file."""
        if self._loaded:
            return

        try:
            import yaml

            with open(self.template_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}

            normalised: Dict[str, Dict[str, Any]] = {}
            for name, definition in content.items():
                if isinstance(definition, str):
                    normalised[name] = {"text": definition, "parse_mode": None}
                elif isinstance(definition, dict) and "text" in definition:
                    normalised[name] = {
                        "text": definition["text"],
                        "parse_mode": definition.get("parse_mode"),
                    }
                else:
                    raise ValueError(
                        f"Invalid template definition for '{name}'. Expected string or mapping with 'text'."
                    )

            self._templates = normalised
            self._loaded = True

            if self.logger:
                self.logger.debug(
                    f"Loaded {len(self._templates)} Telegram templates",
                    operation="load_telegram_templates",
                )
        except FileNotFoundError as e:
            if self.logger:
                self.logger.error(
                    f"Telegram templates file not found: {self.template_path}",
                    operation="load_telegram_templates",
                    error=str(e),
                )
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "Failed to load Telegram templates",
                    operation="load_telegram_templates",
                    error=str(e),
                )
            raise

    def render(self, template_name: str, **context: Any) -> Dict[str, Any]:
        """
        Render a Telegram template.

        Returns a dict with keys:
            - text: rendered message string
            - parse_mode: optional Telegram parse mode override
        """
        if not self._loaded:
            self.load_templates()

        if template_name not in self._templates:
            raise ValueError(
                f"Template '{template_name}' not found. Available: {list(self._templates.keys())}"
            )

        if not jinja2:
            raise RuntimeError("jinja2 is required for template rendering")

        template_def = self._templates[template_name]
        template_str = template_def["text"]
        try:
            template = jinja2.Template(template_str)
            rendered = template.render(**context)
            return {"text": rendered, "parse_mode": template_def.get("parse_mode")}
        except jinja2.TemplateError as e:
            if self.logger:
                self.logger.error(
                    f"Failed to render Telegram template '{template_name}'",
                    operation="render_telegram_template",
                    error=str(e),
                )
            raise

    def get_template_names(self) -> list:
        """Return list of available template names."""
        if not self._loaded:
            self.load_templates()
        return list(self._templates.keys())


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
        slack_service: SlackWebhookClient for Slack notifications (AC 1, 2)
        slack_template_loader: SlackTemplateLoader for message templates (AC 3)
        telegram_template_loader: TelegramTemplateLoader for Telegram templates
        telegram_service: TelegramBotClient for Telegram notifications
        logger: StructuredLogger for logging operations
    """

    booking: Booking
    settings_dict: Dict[str, Any]
    db_repo: BookingRepository
    sms_service: SensSmsClient
    logger: StructuredLogger
    slack_service: Optional[Any] = None
    slack_template_loader: Optional[Any] = None
    telegram_template_loader: Optional[Any] = None
    telegram_service: Optional[Any] = None


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
        slack_service: SlackWebhookClient for Slack notifications (AC 1, 2)
        slack_template_loader: SlackTemplateLoader for message templates (AC 3)
        telegram_template_loader: TelegramTemplateLoader for Telegram templates
        telegram_service: TelegramBotClient for Telegram notifications
        logger: StructuredLogger for structured logging with redaction
        settings_dict: Configuration dictionary
    """

    db_repo: BookingRepository
    sms_service: SensSmsClient
    logger: StructuredLogger
    settings_dict: Dict[str, Any]
    slack_service: Optional[Any] = None
    slack_template_loader: Optional[Any] = None
    telegram_template_loader: Optional[Any] = None
    telegram_service: Optional[Any] = None


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

        delivered = False
        # Route to correct SMS method based on template
        # Accept both "confirm" and "confirmation" as aliases
        if template in ("confirm", "confirmation"):
            delivered = context.sms_service.send_confirm_sms(
                phone=booking.phone,
                store_id=None,  # Confirmation SMS not store-specific
            )
        elif template == "guide":
            # Extract store_id from booking_num (format: "{biz_id}_{book_id}")
            store_id = booking.booking_num.split("_")[0]
            delivered = context.sms_service.send_guide_sms(
                store_id=store_id,
                phone=booking.phone,
            )
        elif template == "event":
            delivered = context.sms_service.send_event_sms(
                phone=booking.phone,
                store_id=None,  # Event SMS not store-specific
            )
        else:
            raise ValueError(f"Unknown template type: {template}")

        if delivered:
            logger.info(
                f"{template} SMS sent successfully",
                operation=operation,
                context=log_context,
            )
        else:
            skip_context = dict(log_context)
            skip_reason = getattr(context.sms_service, "last_skip_reason", None)
            if skip_reason:
                skip_context["reason"] = skip_reason
            logger.info(
                "SMS delivery skipped",
                operation=operation,
                context=skip_context,
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
    flag: Optional[str] = None,
    value: Optional[bool] = None,
    *,
    flag_name: Optional[str] = None,
    flag_value: Optional[bool] = None,
) -> None:
    """
    Update a single DynamoDB boolean flag on a booking.

    Implements idempotency by checking current state first - if flag already
    set to desired value, returns without updating. This matches legacy
    update_item behavior at lambda_function.py:163, 167, 190.

    Args:
        context: ActionContext with booking and db_repo
        flag: Flag to update (schema-aligned name, e.g., "remind_sms")
        value: New flag value (default True when omitted)
        flag_name: Backwards-compatible alias for `flag`
        flag_value: Backwards-compatible alias for `value`

    Raises:
        ActionExecutionError: Wraps DynamoDB exceptions with context
        ValueError: If flag_name is invalid

    Example:
        context = ActionContext(...)
        update_flag(context, "confirm_sms", True)  # positional usage
        update_flag(context, flag="remind_sms", value=True)  # YAML schema usage
        update_flag(context, flag_name="option_sms", flag_value=False)  # legacy alias support
    """
    booking = context.booking
    logger = context.logger
    db_repo = context.db_repo

    effective_flag: Optional[str] = flag_name or flag
    desired_value: bool = (
        flag_value if flag_value is not None else value if value is not None else True
    )

    operation = "update_flag"
    log_context = {
        "booking_id": booking.booking_num,
        "phone_masked": context.logger.logger.name,
        "flag": effective_flag,
        "value": desired_value,
    }

    try:
        if effective_flag is None:
            raise ValueError("update_flag requires `flag` (or `flag_name`) parameter")

        # Validate flag name
        valid_flags = {"confirm_sms", "remind_sms", "option_sms"}
        if effective_flag not in valid_flags:
            raise ValueError(f"Invalid flag name '{effective_flag}'. Must be one of: {valid_flags}")

        logger.debug(
            f"Updating {effective_flag} flag",
            operation=operation,
            context=log_context,
        )

        # Fetch current record to check idempotency
        current = db_repo.get_booking(booking.booking_num, booking.phone)

        # If record doesn't exist, can't update - this is an error
        if current is None:
            raise ValueError(f"Cannot update flag on non-existent booking {booking.booking_num}")

        # Extract flag value from current record (handle both dict and Booking types)
        if isinstance(current, dict):
            current_value = current.get(effective_flag, False)
        else:
            current_value = getattr(current, effective_flag, False)

        # Idempotency check: if already set to desired value, skip update
        if current_value == desired_value:
            logger.debug(
                f"Flag {effective_flag} already set to {desired_value}, skipping update",
                operation=operation,
                context=log_context,
            )
            return

        # Update the flag
        db_repo.update_flag(
            prefix=booking.booking_num,
            phone=booking.phone,
            flag_name=effective_flag,
            value=desired_value,
        )

        logger.info(
            f"Flag {effective_flag} updated to {desired_value}",
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
            context_data={"flag": effective_flag, "value": desired_value},
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
            context_data={"flag": effective_flag, "value": desired_value},
        ) from e


# ============================================================================
# Notification Action Executors (AC5)
# ============================================================================


def send_telegram(
    context: ActionContext,
    message: Optional[str] = None,
    template_name: Optional[str] = None,
    template_params: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] | object = _PARSE_MODE_UNSET,
) -> None:
    """
    Send message via Telegram Bot API.

    Supports two modes:
      1. Direct messages via `message` parameter with optional simple substitutions
      2. Template-based messages via `template_name` + optional params

    Args:
        context: ActionContext with telegram_service and logger
        message: Message text to send (if template_name not provided)
        template_name: Name of template to render from config/telegram_templates.yaml
        template_params: Optional dict for variable substitution in message/template
        parse_mode: Optional Telegram parse mode override (Markdown, HTML, or None)

    Raises:
        ActionExecutionError: Wraps TelegramServiceError/ValueError with context

    Example:
        context = ActionContext(...)
        send_telegram(context, message="Booking confirmed")
        send_telegram(context, template_name="booking_summary", template_params={"name": "홍길동"})
    """
    logger = context.logger
    booking = context.booking
    operation = "send_telegram"

    template_params = template_params or {}
    final_message: Optional[str] = None

    try:
        # Determine final message text
        template_render_parse_mode: Optional[str] = None
        if template_name:
            if not context.telegram_template_loader:
                raise RuntimeError("TelegramTemplateLoader not configured in ActionContext")

            rendered = context.telegram_template_loader.render(template_name, **template_params)
            final_message = rendered["text"]
            template_render_parse_mode = rendered.get("parse_mode")
        else:
            if not message:
                raise ValueError("Either 'message' or 'template_name' must be provided")

            final_message = message
            if template_params:
                for key, value in template_params.items():
                    pattern = re.compile(r"\{\{\s*" + re.escape(str(key)) + r"\s*\}\}")
                    final_message = pattern.sub(str(value), final_message)

        if not isinstance(final_message, str) or final_message == "":
            raise ValueError("Telegram message must be a non-empty string")

        # Check if Telegram service is configured
        if not context.telegram_service:
            logger.warning(
                "Telegram service not configured; skipping notification",
                operation=operation,
                context={
                    "booking_id": booking.booking_num,
                    "template_name": template_name,
                },
            )
            return

        # Determine parse mode precedence: explicit override > template > default
        if parse_mode is not _PARSE_MODE_UNSET:
            final_parse_mode = cast(Optional[str], parse_mode)
        else:
            if template_name:
                final_parse_mode = template_render_parse_mode
            else:
                final_parse_mode = "Markdown"

        log_context = {
            "booking_id": booking.booking_num,
            "message_length": len(final_message),
            "has_params": bool(template_params),
            "template_name": template_name,
            "parse_mode": final_parse_mode,
        }

        logger.debug(
            "Sending Telegram notification",
            operation=operation,
            context=log_context,
        )

        context.telegram_service.send_message(
            text=final_message,
            parse_mode=final_parse_mode,
        )

        logger.info(
            "Telegram notification sent",
            operation=operation,
            context=log_context,
        )

    except ValueError as e:
        logger.error(
            "Validation error in send_telegram",
            operation=operation,
            context={
                "booking_id": booking.booking_num,
                "template_name": template_name,
            },
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_telegram",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={
                "template_name": template_name,
                "has_message": message is not None,
            },
        ) from e

    except RuntimeError as e:
        logger.error(
            "Runtime error in send_telegram",
            operation=operation,
            context={
                "booking_id": booking.booking_num,
                "template_name": template_name,
            },
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_telegram",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={"template_name": template_name},
        ) from e

    except TelegramServiceError as e:
        logger.error(
            "Telegram delivery failed",
            operation=operation,
            context={
                "booking_id": booking.booking_num,
                "template_name": template_name,
            },
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_telegram",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={
                "template_name": template_name,
                "message_preview": final_message[:100] if final_message else None,
            },
        ) from e

    except Exception as e:
        logger.error(
            "Unexpected error in send_telegram",
            operation=operation,
            context={
                "booking_id": booking.booking_num,
                "template_name": template_name,
            },
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_telegram",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={
                "template_name": template_name,
                "message_preview": final_message[:100] if final_message else None,
            },
        ) from e


def send_slack(
    context: ActionContext,
    message: Optional[str] = None,
    channel: Optional[str] = None,
    template_name: Optional[str] = None,
    template_params: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Send message via Slack webhook service with template support (AC 1, 2, 3).

    Posts messages to Slack webhook with optional Jinja2 template rendering.
    - If template_name is provided, renders template from config/slack_templates.yaml
    - Falls back to message parameter if template_name not provided
    - Short-circuits gracefully if Slack is disabled (AC 2)
    - Surfaces failures via ActionExecutionError (AC 1)

    Args:
        context: ActionContext with logger, slack_service, slack_template_loader, settings_dict
        message: Static message text (used if template_name not provided)
        channel: Optional Slack channel to post to (future use)
        template_name: Optional template name from config/slack_templates.yaml (AC 3)
        template_params: Optional dict for template variable substitution (AC 3)

    Raises:
        ActionExecutionError: Wraps failures with context (AC 1)
        ValueError: If neither message nor template_name provided, or template not found

    Example:
        # Using static message
        send_slack(context, message="Booking confirmed")

        # Using template rendering
        send_slack(context,
                   template_name="expert_correction_digest",
                   template_params={"users": [...], "today_date": "2025-10-22"})
    """
    logger = context.logger
    booking = context.booking
    operation = "send_slack"

    log_context = {
        "booking_id": booking.booking_num,
        "template_name": template_name,
        "has_params": template_params is not None,
    }

    try:
        # Check if Slack is enabled (AC 2)
        slack_enabled = context.settings_dict.get("slack_enabled", False)

        if not slack_enabled:
            logger.debug(
                "Slack is disabled, skipping notification",
                operation=operation,
                context=log_context,
            )
            return

        # Validate inputs
        if not message and not template_name:
            raise ValueError("Either 'message' or 'template_name' must be provided")

        # Render template if template_name provided (AC 3)
        final_message = message
        if template_name:
            if not context.slack_template_loader:
                raise RuntimeError("SlackTemplateLoader not configured in ActionContext")

            template_params = template_params or {}
            try:
                final_message = context.slack_template_loader.render(
                    template_name, **template_params
                )
                logger.debug(
                    f"Rendered Slack template '{template_name}'",
                    operation=operation,
                    context=log_context,
                )
            except (ValueError, Exception) as e:
                logger.error(
                    f"Failed to render template '{template_name}'",
                    operation=operation,
                    context=log_context,
                    error=str(e),
                )
                raise

        # Send via webhook client (AC 1)
        if not context.slack_service:
            raise RuntimeError("SlackWebhookClient not configured in ActionContext")

        logger.debug(
            "Sending Slack notification",
            operation=operation,
            context={**log_context, "message_length": len(final_message or "")},
        )

        # Build Slack payload (webhook format)
        payload = {"text": final_message}
        if channel:
            payload["channel"] = channel

        # Dispatch via webhook with retry handling
        context.slack_service._dispatch(payload, action="send_slack_from_rule_engine")

        logger.info(
            "Slack notification sent",
            operation=operation,
            context=log_context,
        )

    except ValueError as e:
        logger.error(
            "Validation error in send_slack",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_slack",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={
                "template_name": template_name,
                "has_message": message is not None,
            },
        ) from e

    except (RuntimeError, SlackServiceError) as e:
        logger.error(
            "Failed to send Slack notification",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_slack",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={
                "template_name": template_name,
                "message_preview": (final_message[:100] if final_message else None),
            },
        ) from e

    except Exception as e:
        logger.error(
            "Unexpected error in send_slack",
            operation=operation,
            context=log_context,
            error=str(e),
        )
        raise ActionExecutionError(
            executor_name="send_slack",
            booking_id=booking.booking_num,
            original_error=e,
            context_data={"template_name": template_name},
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
        from src.rules.actions import register_actions, ActionServicesBundle, SlackTemplateLoader
        from src.notifications.slack_service import SlackWebhookClient

        engine = RuleEngine("config/rules.yaml")
        slack_service = SlackWebhookClient(webhook_url=config_dict.get("slack_webhook_url"))
        slack_loader = SlackTemplateLoader(logger=logger)

        services = ActionServicesBundle(
            db_repo=booking_repo,
            sms_service=sms_client,
            slack_service=slack_service,
            slack_template_loader=slack_loader,
            logger=logger,
            settings_dict=config_dict,
        )
        register_actions(engine, services)
    """
    logger = services.logger

    operation = "register_actions"
    log_context = {
        "action_count": 6,
        "slack_enabled": services.settings_dict.get("slack_enabled", False),
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
                slack_service=services.slack_service,
                slack_template_loader=services.slack_template_loader,
                telegram_template_loader=services.telegram_template_loader,
                telegram_service=services.telegram_service,
                logger=services.logger,
            )
            send_sms(action_context, **params)

        def create_db_record_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                slack_service=services.slack_service,
                slack_template_loader=services.slack_template_loader,
                telegram_template_loader=services.telegram_template_loader,
                telegram_service=services.telegram_service,
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
                slack_service=services.slack_service,
                slack_template_loader=services.slack_template_loader,
                telegram_template_loader=services.telegram_template_loader,
                telegram_service=services.telegram_service,
                logger=services.logger,
            )
            update_flag(action_context, **params)

        def send_telegram_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                slack_service=services.slack_service,
                slack_template_loader=services.slack_template_loader,
                telegram_template_loader=services.telegram_template_loader,
                telegram_service=services.telegram_service,
                logger=services.logger,
            )
            resolved_params = dict(params)

            if "template_params" in resolved_params:
                resolved_params["template_params"] = _resolve_template_params(
                    resolved_params["template_params"], rule_context
                )

            send_telegram(action_context, **resolved_params)

        def send_slack_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                slack_service=services.slack_service,
                slack_template_loader=services.slack_template_loader,
                telegram_template_loader=services.telegram_template_loader,
                telegram_service=services.telegram_service,
                logger=services.logger,
            )
            resolved_params = dict(params)

            if "template_params" in resolved_params:
                resolved_params["template_params"] = _resolve_template_params(
                    resolved_params["template_params"], rule_context
                )

            if resolved_params.get("channel"):
                services.logger.debug(
                    "send_slack_wrapper: Using explicit Slack channel override",
                    context={"channel": resolved_params.get("channel")},
                )

            send_slack(action_context, **resolved_params)

        def log_event_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
            booking = rule_context.get("booking")
            if booking is None:
                raise ValueError("Booking not found in rule context")

            action_context = ActionContext(
                booking=booking,
                settings_dict=services.settings_dict,
                db_repo=services.db_repo,
                sms_service=services.sms_service,
                slack_service=services.slack_service,
                slack_template_loader=services.slack_template_loader,
                telegram_service=services.telegram_service,
                logger=services.logger,
            )
            # Inject rule_name and action_name from context if not provided
            params.setdefault("rule_name", rule_context.get("rule_name", "unknown"))
            params.setdefault("action_name", rule_context.get("action_name", "unknown"))
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
