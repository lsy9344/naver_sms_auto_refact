"""
Structured JSON Logger for CloudWatch Integration

Provides:
- JSON-formatted log output for CloudWatch ingestion
- Correlation field injection (request_id, rule_name, action_type, status)
- PII redaction (phone numbers, secret values)
- Structured logging with custom fields
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class PiiRedactor:
    """Redacts personally identifiable information from log output."""

    # Phone number pattern (10-digit Korean mobile)
    PHONE_PATTERN = re.compile(r"01[016-9]-\d{3,4}-\d{4}")

    @staticmethod
    def redact_phone_number(text: str) -> str:
        """
        Redact phone numbers to format: 010-****-5678 (keep last 4 digits visible).

        Args:
            text: Text potentially containing phone numbers

        Returns:
            Text with phone numbers redacted
        """
        def mask_phone(match):
            phone = match.group()
            # Keep first 4 chars (010-) and last 4 digits (-5678), mask middle
            parts = phone.split("-")
            if len(parts) == 3:
                return f"{parts[0]}-****-{parts[2]}"
            return phone

        return PiiRedactor.PHONE_PATTERN.sub(mask_phone, text)

    @staticmethod
    def redact_secrets(text: str, secret_patterns: Optional[Dict[str, str]] = None) -> str:
        """
        Redact secret values from text.

        Args:
            text: Text potentially containing secrets
            secret_patterns: Dict of secret_name -> secret_value to redact

        Returns:
            Text with secrets redacted as ***REDACTED***
        """
        if not secret_patterns:
            return text

        redacted = text
        for secret_value in secret_patterns.values():
            if isinstance(secret_value, str) and len(secret_value) > 3:
                redacted = redacted.replace(secret_value, "***REDACTED***")

        return redacted

    @staticmethod
    def redact_value(value: Any, secret_patterns: Optional[Dict[str, str]] = None) -> Any:
        """
        Recursively redact PII and secrets from a value.

        Args:
            value: Value to redact (str, dict, list, or other)
            secret_patterns: Optional dict of secrets to redact

        Returns:
            Redacted value
        """
        if isinstance(value, str):
            redacted = PiiRedactor.redact_phone_number(value)
            redacted = PiiRedactor.redact_secrets(redacted, secret_patterns)
            return redacted
        elif isinstance(value, dict):
            return {
                k: PiiRedactor.redact_value(v, secret_patterns)
                for k, v in value.items()
            }
        elif isinstance(value, (list, tuple)):
            return type(value)(
                PiiRedactor.redact_value(item, secret_patterns)
                for item in value
            )
        else:
            return value


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def __init__(self, secret_patterns: Optional[Dict[str, str]] = None):
        """
        Initialize JSON formatter.

        Args:
            secret_patterns: Optional dict of secrets to redact
        """
        super().__init__()
        self.secret_patterns = secret_patterns

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record

        Returns:
            JSON-formatted log line
        """
        # Get message and redact PII
        message = record.getMessage()
        message = PiiRedactor.redact_phone_number(message)
        message = PiiRedactor.redact_secrets(message, self.secret_patterns)

        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }

        # Add correlation fields if present in extra
        if hasattr(record, "fields"):
            for key, value in record.fields.items():
                log_obj[key] = PiiRedactor.redact_value(value, self.secret_patterns)

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


class StructuredLogger:
    """Structured logger with correlation fields and PII redaction."""

    def __init__(
        self,
        name: str,
        log_level: Optional[str] = None,
        secret_patterns: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            secret_patterns: Optional dict of secrets to redact
        """
        self.logger = logging.getLogger(name)

        # Set log level from env or parameter
        log_level_str = log_level or os.getenv("LOG_LEVEL", "INFO")
        self.logger.setLevel(log_level_str.upper())

        # Remove existing handlers
        self.logger.handlers = []

        # Create stream handler with JSON formatter
        handler = logging.StreamHandler()
        formatter = JsonFormatter(secret_patterns=secret_patterns)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Store for use in logging methods
        self.secret_patterns = secret_patterns

    def _log(
        self,
        level: int,
        message: str,
        request_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Log with correlation fields.

        Args:
            level: Log level
            message: Log message
            request_id: Request correlation ID
            rule_name: Name of rule (if applicable)
            action_type: Type of action (e.g., send_sms, login)
            status: Status (e.g., success, failure)
            **kwargs: Additional fields to include in log
        """
        extra_fields = {
            "fields": {
                **kwargs,
            }
        }

        # Add correlation fields if provided
        if request_id:
            extra_fields["fields"]["request_id"] = request_id
        if rule_name:
            extra_fields["fields"]["rule_name"] = rule_name
        if action_type:
            extra_fields["fields"]["action_type"] = action_type
        if status:
            extra_fields["fields"]["status"] = status

        self.logger.log(level, message, extra=extra_fields)

    def debug(
        self,
        message: str,
        request_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log at DEBUG level with correlation fields."""
        self._log(
            logging.DEBUG,
            message,
            request_id=request_id,
            rule_name=rule_name,
            action_type=action_type,
            status=status,
            **kwargs,
        )

    def info(
        self,
        message: str,
        request_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log at INFO level with correlation fields."""
        self._log(
            logging.INFO,
            message,
            request_id=request_id,
            rule_name=rule_name,
            action_type=action_type,
            status=status,
            **kwargs,
        )

    def warning(
        self,
        message: str,
        request_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log at WARNING level with correlation fields."""
        self._log(
            logging.WARNING,
            message,
            request_id=request_id,
            rule_name=rule_name,
            action_type=action_type,
            status=status,
            **kwargs,
        )

    def error(
        self,
        message: str,
        request_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log at ERROR level with correlation fields."""
        self._log(
            logging.ERROR,
            message,
            request_id=request_id,
            rule_name=rule_name,
            action_type=action_type,
            status=status,
            **kwargs,
        )

    def critical(
        self,
        message: str,
        request_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log at CRITICAL level with correlation fields."""
        self._log(
            logging.CRITICAL,
            message,
            request_id=request_id,
            rule_name=rule_name,
            action_type=action_type,
            status=status,
            **kwargs,
        )


# Module-level convenience function
def get_logger(name: str) -> StructuredLogger:
    """
    Get or create a structured logger.

    Args:
        name: Logger name

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)
