"""Performance simulation utilities for validation campaigns."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Performance metrics for a campaign run."""

    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.peak_memory_mb = 0
        self.comparison_count = 0
        self.cloudwatch_publishes = 0
        self.slack_notifications = 0
        self.errors: list[str] = []

    @property
    def execution_duration_ms(self) -> int:
        if self.start_time is not None and self.end_time is not None:
            return int((self.end_time - self.start_time) * 1000)
        return 0

    def set_simulated_duration_ms(self, duration_ms: int) -> None:
        """Record a simulated execution duration without real sleeping."""
        self.start_time = 0.0
        self.end_time = duration_ms / 1000.0

    def meets_execution_threshold(self, threshold_ms: int = 240000) -> bool:
        return self.execution_duration_ms <= threshold_ms

    def meets_memory_threshold(self, threshold_mb: int = 512) -> bool:
        return self.peak_memory_mb <= threshold_mb

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_duration_ms": self.execution_duration_ms,
            "peak_memory_mb": self.peak_memory_mb,
            "comparison_count": self.comparison_count,
            "cloudwatch_publishes": self.cloudwatch_publishes,
            "slack_notifications": self.slack_notifications,
            "errors": self.errors,
        }


class CampaignPerformanceSimulator:
    """Simulates campaign execution and measures performance deterministically."""

    EXECUTION_TIME_PER_BOOKING_MS = 1200
    NETWORK_DELAY_INTERVAL = 10
    NETWORK_DELAY_MS = 10
    BASE_OVERHEAD_MS = 250

    MEMORY_BASELINE_MB = 20
    MEMORY_PER_BOOKING_MB = 2
    CLOUDWATCH_PUBLISHES_PER_BOOKING = 3
    SLACK_NOTIFICATIONS_PER_CAMPAIGN = 2

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def simulate_campaign(
        self, booking_count: int, simulate_delay: bool = False
    ) -> PerformanceMetrics:
        metrics = PerformanceMetrics()
        simulated_elapsed_ms = 0

        for booking_index in range(booking_count):
            simulated_elapsed_ms += self._process_booking(booking_index, metrics, simulate_delay)

            if (
                simulate_delay
                and booking_index > 0
                and booking_index % self.NETWORK_DELAY_INTERVAL == 0
            ):
                simulated_elapsed_ms += self.NETWORK_DELAY_MS

        metrics.cloudwatch_publishes += 1
        metrics.slack_notifications += self.SLACK_NOTIFICATIONS_PER_CAMPAIGN

        simulated_elapsed_ms += self.BASE_OVERHEAD_MS
        metrics.set_simulated_duration_ms(simulated_elapsed_ms)

        return metrics

    def _process_booking(
        self,
        booking_id: int,
        metrics: PerformanceMetrics,
        simulate_delay: bool,
    ) -> int:
        simulated_duration_ms = 0

        if simulate_delay:
            simulated_duration_ms += self.EXECUTION_TIME_PER_BOOKING_MS
        else:
            simulated_duration_ms += int(self.EXECUTION_TIME_PER_BOOKING_MS * 0.25)

        metrics.comparison_count += 1
        metrics.peak_memory_mb = max(
            metrics.peak_memory_mb,
            self.MEMORY_BASELINE_MB + metrics.comparison_count * self.MEMORY_PER_BOOKING_MB,
        )
        metrics.cloudwatch_publishes += self.CLOUDWATCH_PUBLISHES_PER_BOOKING

        if booking_id % 10 == 0 and booking_id > 0:
            metrics.slack_notifications += 1

        return simulated_duration_ms
