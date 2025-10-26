"""
Slack webhook notifications client.

Provides real-time validation notifications and cross-team alerting
for the naver-sms-automation system.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import requests

from src.utils.logger import get_logger, StructuredLogger


class SlackServiceError(Exception):
    """Raised when the Slack service fails to deliver a message."""


def _default_timestamp_provider() -> str:
    """Return millisecond epoch timestamp as string."""
    return str(int(time.time() * 1000))


class SlackWebhookClient:
    """
    Client for sending notifications through Slack webhooks.

    Attributes:
        webhook_url: Slack incoming webhook URL
        logger: Structured logger instance
        max_retries: Number of retry attempts
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        http_client: Optional[requests.Session] = None,
        logger: Optional[StructuredLogger] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.5,
    ) -> None:
        """
        Initialize the Slack webhook client.

        Args:
            webhook_url: Slack incoming webhook URL (from environment if None)
            http_client: Optional requests-like session (useful for testing)
            logger: Optional structured logger instance
            max_retries: Number of attempts when sending messages
            retry_delay_seconds: Base delay between retries (linear backoff)
        """
        self.logger = logger or get_logger(__name__)
        self.http_client = http_client or requests.Session()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

        import os

        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            self.logger.warning("Slack webhook URL not configured; Slack notifications disabled")
            self.webhook_url = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def send_validation_started(self, campaign_id: str, test_count: int) -> None:
        """Send notification that validation campaign has started."""
        if not self.webhook_url:
            return

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🚀 *Validation Campaign Started*\n"
                        f"Campaign ID: `{campaign_id}`\n"
                        f"Tests to run: `{test_count}`",
                    },
                }
            ]
        }
        self._dispatch(payload, action="send_validation_started")

    def send_validation_completed(
        self, campaign_id: str, total_tests: int, passed: int, failed: int
    ) -> None:
        """Send notification that validation campaign has completed."""
        if not self.webhook_url:
            return

        pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        status_emoji = "✅" if failed == 0 else "⚠️"

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *Validation Campaign Completed*\n"
                        f"Campaign ID: `{campaign_id}`\n"
                        f"Results: `{passed}/{total_tests}` passed ({pass_rate:.1f}%)\n"
                        f"Failures: `{failed}`",
                    },
                }
            ]
        }
        self._dispatch(payload, action="send_validation_completed")

    def send_parity_mismatch_alert(
        self, booking_id: str, mismatch_count: int, critical_count: int
    ) -> None:
        """Send alert for detected parity mismatches."""
        if not self.webhook_url:
            return

        severity_emoji = "🚨" if critical_count > 0 else "⚠️"

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{severity_emoji} *Parity Mismatch Detected*\n"
                        f"Booking ID: `{booking_id}`\n"
                        f"Total mismatches: `{mismatch_count}`\n"
                        f"Critical: `{critical_count}`",
                    },
                }
            ]
        }
        self._dispatch(payload, action="send_parity_mismatch_alert")

    def send_performance_alert(self, phase_name: str, duration_ms: int, threshold_ms: int) -> None:
        """Send alert for performance threshold breach."""
        if not self.webhook_url:
            return

        breach_percent = (duration_ms - threshold_ms) / threshold_ms * 100

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⚡ *Performance Alert*\n"
                        f"Phase: `{phase_name}`\n"
                        f"Duration: `{duration_ms}ms` (threshold: `{threshold_ms}ms`)\n"
                        f"Breach: `+{breach_percent:.1f}%`",
                    },
                }
            ]
        }
        self._dispatch(payload, action="send_performance_alert")

    def send_slack_webhook_test(self, webhook_url_masked: str, status: str) -> None:
        """Send test notification for Slack webhook validation."""
        if not self.webhook_url:
            return

        status_emoji = "✅" if status == "success" else "❌"

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *Slack Webhook Test*\n"
                        f"Webhook: `{webhook_url_masked}`\n"
                        f"Status: `{status}`\n"
                        f"Timestamp: `{int(time.time())}`",
                    },
                }
            ]
        }
        self._dispatch(payload, action="send_slack_webhook_test")

    def send_rate_limit_alert(self, reset_time: int, retry_after_seconds: int) -> None:
        """Send alert for Slack rate limiting."""
        if not self.webhook_url:
            return

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⏱️ *Rate Limit Alert*\n"
                        f"Retry after: `{retry_after_seconds}` seconds\n"
                        f"Reset time: `{reset_time}`",
                    },
                }
            ]
        }
        # Don't retry on rate limit - just log and return
        self._dispatch(payload, action="send_rate_limit_alert", max_retries=1)

    def send_text(self, text: str, channel: Optional[str] = None) -> None:
        """Send a simple plaintext message via Slack webhook."""
        if not self.webhook_url:
            return

        payload: Dict[str, Any] = {"text": text}
        if channel:
            payload["channel"] = channel

        self._dispatch(payload, action="send_text")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _dispatch(
        self,
        payload: Dict[str, Any],
        action: str,
        max_retries: Optional[int] = None,
    ) -> None:
        """Send payload to Slack webhook with retry handling."""
        if not self.webhook_url:
            self.logger.debug(
                "Slack webhook not configured; skipping notification",
                operation=action,
            )
            return

        max_retries = max_retries or self.max_retries
        body = json.dumps(payload)

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.debug(
                    "Sending Slack notification",
                    operation=action,
                    context={
                        "status": "attempt",
                        "attempt": attempt,
                    },
                )

                response = self.http_client.post(
                    self.webhook_url,
                    headers={"Content-Type": "application/json"},
                    data=body,
                    timeout=10,
                )

                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self.logger.warning(
                        "Slack rate limited",
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
                    raise SlackServiceError(f"Rate limited; retry after {retry_after}s")

                if response.status_code >= 400:
                    raise SlackServiceError(
                        f"Slack responded with {response.status_code}: {response.text}"
                    )

                self.logger.debug(
                    "Slack notification delivered",
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
                        "Slack delivery failed",
                        operation=action,
                        context={
                            "status": "failed",
                            "attempt": attempt,
                        },
                        error=str(exc),
                    )
                    # Note: Slack delivery failures are NOT critical path blockers
                    # Log but don't raise - allow validation to continue
                    return

                self.logger.warning(
                    "Retrying Slack delivery",
                    operation=action,
                    context={
                        "status": "retry",
                        "attempt": attempt,
                    },
                    error=str(exc),
                )
                time.sleep(self.retry_delay_seconds * attempt)

    def get_webhook_status(self) -> Dict[str, Any]:
        """Return webhook configuration status."""
        return {
            "webhook_configured": self.webhook_url is not None,
            "webhook_url_masked": (self._mask_url(self.webhook_url) if self.webhook_url else None),
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
        }

    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask webhook URL for logging."""
        if not url or len(url) < 20:
            return url
        return f"{url[:30]}...{url[-10:]}"
