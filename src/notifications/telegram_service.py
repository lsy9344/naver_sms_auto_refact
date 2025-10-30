"""
Telegram Bot API notifications client.

Provides real-time notifications and alerting via Telegram Bot API
for the naver-sms-automation system.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import requests

from src.utils.logger import get_logger, StructuredLogger


class TelegramServiceError(Exception):
    """Raised when the Telegram service fails to deliver a message."""


class TelegramBotClient:
    """
    Client for sending notifications through Telegram Bot API.

    Attributes:
        bot_token: Telegram bot token from @BotFather
        chat_id: Target chat/channel ID
        logger: Structured logger instance
        max_retries: Number of retry attempts
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        http_client: Optional[requests.Session] = None,
        logger: Optional[StructuredLogger] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.5,
        throttle_seconds: float = 0.15,
    ) -> None:
        """
        Initialize the Telegram bot client.

        Args:
            bot_token: Telegram bot token (from environment if None)
            chat_id: Target chat ID (from environment if None)
            http_client: Optional requests-like session (useful for testing)
            logger: Optional structured logger instance
            max_retries: Number of attempts when sending messages
            retry_delay_seconds: Base delay between retries (exponential backoff)
            throttle_seconds: Delay after successful message to prevent rate limiting
        """
        self.logger = logger or get_logger(__name__)
        self.http_client = http_client or requests.Session()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds  # Used for exponential backoff
        self.throttle_seconds = throttle_seconds  # Delay after successful send

        import os

        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            self.logger.warning(
                "Telegram bot token or chat ID not configured; Telegram notifications disabled"
            )
            self.bot_token = None
            self.chat_id = None

        # Construct API URL
        if self.bot_token:
            # Handle case where bot_token may already include "bot" prefix
            token_part = (
                self.bot_token if self.bot_token.startswith("bot") else f"bot{self.bot_token}"
            )
            self.api_url = f"https://api.telegram.org/{token_part}/sendMessage"
        else:
            self.api_url = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        chat_id: Optional[str] = None,
    ) -> bool:
        """
        Send a text message to Telegram.

        Args:
            text: Message text to send
            parse_mode: Telegram parse mode ("Markdown", "HTML", or None)
            chat_id: Optional override for target chat ID

        Returns:
            True if message was delivered successfully, False otherwise

        Note:
            Does not raise exceptions - failures are logged and returned as False
        """
        if not self.api_url:
            self.logger.debug("Telegram not configured; skipping message")
            return False

        target_chat_id = chat_id or self.chat_id

        payload = {
            "chat_id": target_chat_id,
            "text": text,
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        return self._dispatch(payload, action="send_message")

    def send_notification(
        self,
        message: str,
        template_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send notification with optional template parameter substitution.

        Args:
            message: Message text (may contain {{variable}} placeholders)
            template_params: Optional dict for simple variable substitution

        Raises:
            TelegramServiceError: If message delivery fails
        """
        if not self.api_url:
            self.logger.debug("Telegram not configured; skipping notification")
            return

        # Simple template substitution (for basic use cases)
        final_message = message
        if template_params:
            for key, value in template_params.items():
                placeholder = f"{{{{{key}}}}}"
                final_message = final_message.replace(placeholder, str(value))

        self.send_message(final_message)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _dispatch(
        self,
        payload: Dict[str, Any],
        action: str,
        max_retries: Optional[int] = None,
        allow_parse_mode_fallback: bool = True,
    ) -> bool:
        """
        Send payload to Telegram Bot API with retry handling.

        Returns:
            True if message was delivered successfully, False otherwise
        """
        if not self.api_url:
            self.logger.debug(
                "Telegram API not configured; skipping notification",
                operation=action,
            )
            return False

        max_attempts = max_retries or self.max_retries
        attempt = 1

        while attempt <= max_attempts:
            body = json.dumps(payload)
            try:
                self.logger.debug(
                    "Sending Telegram notification",
                    operation=action,
                    context={
                        "status": "attempt",
                        "attempt": attempt,
                    },
                )

                response = self.http_client.post(
                    self.api_url,
                    headers={"Content-Type": "application/json"},
                    data=body,
                    timeout=10,
                )

                # Telegram Bot API returns 200 with JSON response
                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self.logger.error(
                        "Telegram rate limited by API - cannot retry within Lambda timeout",
                        operation=action,
                        context={
                            "status": "rate_limited",
                            "attempt": attempt,
                            "retry_after_seconds": retry_after,
                            "note": "Rate limit failures are not retried to avoid Lambda timeout",
                        },
                    )
                    # Rate limit failures should not be retried - the Retry-After
                    # period is typically 60+ seconds, which exceeds Lambda timeout
                    return False

                if response.status_code >= 400:
                    raise TelegramServiceError(
                        f"Telegram responded with {response.status_code}: {response.text}"
                    )

                # Check if API returned error in JSON
                try:
                    result = response.json()
                    if not result.get("ok", False):
                        error_desc = result.get("description", "Unknown error")
                        raise TelegramServiceError(f"Telegram API error: {error_desc}")
                except (ValueError, KeyError):
                    # Not JSON or missing fields - treat as success if 200
                    pass

                self.logger.debug(
                    "Telegram notification delivered",
                    operation=action,
                    context={
                        "status": "success",
                        "attempt": attempt,
                        "throttle_seconds": self.throttle_seconds,
                    },
                )
                # Add throttling delay after successful delivery to prevent rate limiting
                if self.throttle_seconds > 0:
                    time.sleep(self.throttle_seconds)
                return True

            except Exception as exc:  # noqa: BLE001
                error_message = str(exc)

                if (
                    allow_parse_mode_fallback
                    and payload.get("parse_mode")
                    and self._is_markdown_parse_error(error_message)
                ):
                    self.logger.warning(
                        "Telegram parse error detected; retrying without parse mode",
                        operation=action,
                        context={
                            "status": "parse_mode_fallback",
                            "attempt": attempt,
                        },
                        error=error_message,
                    )
                    payload = {k: v for k, v in payload.items() if k != "parse_mode"}
                    allow_parse_mode_fallback = False
                    continue

                if attempt >= max_attempts:
                    self.logger.error(
                        "Telegram delivery failed after all retries",
                        operation=action,
                        context={
                            "status": "failed",
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                        },
                        error=error_message,
                    )
                    # Note: Telegram delivery failures are NOT critical path blockers
                    # Return False to indicate failure - caller can decide how to handle
                    return False

                self.logger.warning(
                    "Retrying Telegram delivery",
                    operation=action,
                    context={
                        "status": "retry",
                        "attempt": attempt,
                    },
                    error=error_message,
                )
                time.sleep(self.retry_delay_seconds * attempt)
                attempt += 1

        # Should never reach here (all paths return), but satisfy mypy
        return False

    @staticmethod
    def _is_markdown_parse_error(error_message: str) -> bool:
        """Detect Markdown parse errors returned by Telegram."""
        normalized = error_message.lower().replace("\\'", "'")
        return "can't parse entities" in normalized or "can't find end of the entity" in normalized

    def get_client_status(self) -> Dict[str, Any]:
        """Return client configuration status."""
        return {
            "bot_configured": self.bot_token is not None,
            "chat_id_configured": self.chat_id is not None,
            "api_url": self.api_url if self.api_url else None,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "throttle_seconds": self.throttle_seconds,
        }
