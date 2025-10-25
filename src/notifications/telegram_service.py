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
        """
        self.logger = logger or get_logger(__name__)
        self.http_client = http_client or requests.Session()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

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
    ) -> None:
        """
        Send a text message to Telegram.

        Args:
            text: Message text to send
            parse_mode: Telegram parse mode ("Markdown", "HTML", or None)
            chat_id: Optional override for target chat ID

        Raises:
            TelegramServiceError: If message delivery fails
        """
        if not self.api_url:
            self.logger.debug("Telegram not configured; skipping message")
            return

        target_chat_id = chat_id or self.chat_id

        payload = {
            "chat_id": target_chat_id,
            "text": text,
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        self._dispatch(payload, action="send_message")

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
    ) -> None:
        """Send payload to Telegram Bot API with retry handling."""
        if not self.api_url:
            self.logger.debug(
                "Telegram API not configured; skipping notification",
                operation=action,
            )
            return

        max_retries = max_retries or self.max_retries
        body = json.dumps(payload)

        for attempt in range(1, max_retries + 1):
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
                    self.logger.warning(
                        "Telegram rate limited",
                        operation=action,
                        context={
                            "status": "rate_limited",
                            "attempt": attempt,
                            "retry_after": retry_after,
                        },
                    )
                    if attempt < max_retries:
                        time.sleep(min(retry_after, self.retry_delay_seconds * attempt))
                        continue
                    raise TelegramServiceError(f"Rate limited; retry after {retry_after}s")

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
                    },
                )
                return

            except Exception as exc:  # noqa: BLE001
                if attempt >= max_retries:
                    self.logger.error(
                        "Telegram delivery failed",
                        operation=action,
                        context={
                            "status": "failed",
                            "attempt": attempt,
                        },
                        error=str(exc),
                    )
                    # Note: Telegram delivery failures are NOT critical path blockers
                    # Log but don't raise - allow processing to continue
                    return

                self.logger.warning(
                    "Retrying Telegram delivery",
                    operation=action,
                    context={
                        "status": "retry",
                        "attempt": attempt,
                    },
                    error=str(exc),
                )
                time.sleep(self.retry_delay_seconds * attempt)

    def get_client_status(self) -> Dict[str, Any]:
        """Return client configuration status."""
        return {
            "bot_configured": self.bot_token is not None,
            "chat_id_configured": self.chat_id is not None,
            "api_url": self.api_url if self.api_url else None,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
        }
