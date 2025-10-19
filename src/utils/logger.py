"""
Structured logging utility for the application.

Provides JSON-formatted logging with built-in phone number masking,
context injection, and operation timing for CloudWatch integration.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps


def mask_phone(phone: str) -> str:
    """
    Mask phone number to preserve privacy in logs.

    Format: 010-XXXX-5678 (keeps last 4 digits, masks middle 4)

    Args:
        phone: Phone number in format "010-XXXX-XXXX" or "010XXXXXXXX"

    Returns:
        Masked phone number string

    Example:
        >>> mask_phone("010-1234-5678")
        "010-****-5678"
        >>> mask_phone("01012345678")
        "010-****-5678"
    """
    if not phone:
        return "unknown"

    # Normalize: remove hyphens
    clean_phone = phone.replace("-", "")

    if len(clean_phone) < 8:
        return "invalid"

    # Format: 010-****-XXXX (last 4 digits visible)
    return f"{clean_phone[:3]}-****-{clean_phone[-4:]}"


class StructuredLogger:
    """
    JSON-formatted logger with context injection and operation timing.

    All log output is JSON format for CloudWatch integration and easier parsing.
    """

    def __init__(self, name: str):
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically __name__ from calling module)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Create console handler with JSON formatting
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)

            # JSON formatter
            formatter = logging.Formatter("%(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _format_log(
        self,
        level: str,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> str:
        """
        Format log entry as JSON.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            message: Human-readable message
            operation: Operation name (e.g., "get_booking", "update_flag")
            context: Context dict with booking_id, store_id, etc.
            duration_ms: Operation duration in milliseconds
            error: Error message if applicable

        Returns:
            JSON-formatted log string
        """
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": level,
            "message": message,
        }

        if operation:
            log_entry["operation"] = operation

        if context:
            log_entry["context"] = context

        if duration_ms is not None:
            log_entry["duration_ms"] = round(duration_ms, 2)

        if error:
            log_entry["error"] = error

        return json.dumps(log_entry, ensure_ascii=False)

    def debug(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log debug message."""
        log_json = self._format_log("DEBUG", message, operation, context)
        self.logger.debug(log_json)

    def info(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ):
        """Log info message."""
        log_json = self._format_log("INFO", message, operation, context, duration_ms)
        self.logger.info(log_json)

    def warning(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """Log warning message."""
        log_json = self._format_log("WARNING", message, operation, context, error=error)
        self.logger.warning(log_json)

    def error(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ):
        """Log error message."""
        log_json = self._format_log(
            "ERROR", message, operation, context, duration_ms, error
        )
        self.logger.error(log_json)


def log_operation(operation_name: str):
    """
    Decorator to automatically log operation start, duration, and completion.

    Usage:
        @log_operation("get_booking")
        def get_booking(prefix, phone):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)

            # Build context from function signature
            context = {
                "function": func.__name__,
            }

            # Add booking_id/phone if available
            if len(args) > 0:
                context["arg_count"] = len(args)
            if "phone" in kwargs:
                context["phone_masked"] = mask_phone(kwargs["phone"])

            logger.debug(
                f"Starting {operation_name}", operation=operation_name, context=context
            )

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Completed {operation_name}",
                    operation=operation_name,
                    context=context,
                    duration_ms=duration_ms,
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Failed {operation_name}",
                    operation=operation_name,
                    context=context,
                    error=str(e),
                    duration_ms=duration_ms,
                )
                raise

        return wrapper

    return decorator


def get_logger(name: str) -> StructuredLogger:
    """
    Factory function to get a structured logger instance.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)
