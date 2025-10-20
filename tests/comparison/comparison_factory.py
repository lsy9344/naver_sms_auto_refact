"""
Comparison Factory - Build deterministic contexts for both implementations

Story 4.2 Task 2: Implements AC 2, 3 (Comparison Harness)
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ComparisonFactory:
    """
    Factory for building comparison test scenarios from fixtures.

    Responsibilities:
    - Load production_bookings.json fixtures
    - Build deterministic contexts for both legacy and refactored handlers
    - Ensure time consistency, settings injection, and DB state initialization
    """

    def __init__(self, fixtures_dir: Path = None):
        """
        Initialize factory with fixture directory.

        Args:
            fixtures_dir: Path to tests/fixtures directory
        """
        if fixtures_dir is None:
            fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"

        self.fixtures_dir = fixtures_dir
        self._bookings_cache = None
        self._expected_outputs_cache = None

    def load_bookings_fixture(self) -> Dict[str, Any]:
        """
        Load production_bookings.json fixture.

        Returns:
            dict: Bookings fixture with all test scenarios
        """
        if self._bookings_cache is not None:
            return self._bookings_cache

        bookings_path = self.fixtures_dir / "production_bookings.json"
        with bookings_path.open("r", encoding="utf-8") as f:
            self._bookings_cache = json.load(f)

        logger.info(f"Loaded {len(self._bookings_cache['bookings'])} bookings from fixture")
        return self._bookings_cache

    def load_expected_outputs_fixture(self) -> Dict[str, Any]:
        """
        Load production_expected_outputs.json fixture.

        Returns:
            dict: Expected outputs for all scenarios
        """
        if self._expected_outputs_cache is not None:
            return self._expected_outputs_cache

        outputs_path = self.fixtures_dir / "production_expected_outputs.json"
        with outputs_path.open("r", encoding="utf-8") as f:
            self._expected_outputs_cache = json.load(f)

        logger.info(
            f"Loaded {len(self._expected_outputs_cache['expected_outputs'])} expected outputs"
        )
        return self._expected_outputs_cache

    def build_scenario_contexts(self) -> List[Dict[str, Any]]:
        """
        Build contexts for each scenario.

        Each context includes:
        - Booking data
        - DB record state (if applicable)
        - Current time (for deterministic testing)
        - Settings

        Implements AC 4 from story (build rule-engine-ready contexts)

        Returns:
            List of scenario contexts ready for comparison
        """
        bookings_fixture = self.load_bookings_fixture()
        contexts = []

        for booking in bookings_fixture["bookings"]:
            context = {
                "booking_id": booking["booking_id"],
                "scenario": booking["scenario"],
                "booking": self._normalize_booking(booking),
                "db_record": booking.get("db_record"),
                "current_time": booking.get("current_time_for_test") or datetime.now().isoformat(),
                "session_expired": booking.get("session_expired", False),
            }
            contexts.append(context)

        logger.info(f"Built {len(contexts)} scenario contexts")
        return contexts

    def _normalize_booking(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize booking data for both implementations.

        Ensures consistent field names and types between fixture and handlers.

        Args:
            booking: Raw booking from fixture

        Returns:
            Normalized booking dict
        """
        return {
            "booking_id": booking.get("booking_id"),
            "biz_id": booking.get("biz_id"),
            "book_id": booking.get("book_id"),
            "customer_phone": booking.get("customer_phone"),
            "customer_name": booking.get("customer_name"),
            "store_name": booking.get("store_name"),
            "booking_time": booking.get("booking_time"),
            "status": booking.get("status"),
            "option": booking.get("option"),
        }

    def get_scenario_by_id(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific scenario by ID.

        Args:
            scenario_id: Booking ID or scenario name

        Returns:
            Scenario context or None if not found
        """
        bookings_fixture = self.load_bookings_fixture()

        for booking in bookings_fixture["bookings"]:
            if booking["booking_id"] == scenario_id:
                return self._normalize_booking(booking)

        return None

    def get_expected_output(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """
        Get expected output for a booking.

        Args:
            booking_id: ID of the booking

        Returns:
            Expected output dict or None if not found
        """
        expected_outputs = self.load_expected_outputs_fixture()
        return expected_outputs["expected_outputs"].get(booking_id)

    def get_validation_rules(self) -> Dict[str, Dict[str, str]]:
        """
        Get all validation rules for parity checking.

        Returns:
            Dictionary of validation rules
        """
        expected_outputs = self.load_expected_outputs_fixture()
        return expected_outputs.get("validation_rules", {})

    def list_all_scenarios(self) -> List[str]:
        """
        List all available scenario IDs.

        Returns:
            List of scenario IDs
        """
        bookings_fixture = self.load_bookings_fixture()
        return [b["booking_id"] for b in bookings_fixture["bookings"]]

    def get_scenarios_by_edge_case(self, edge_case_name: str) -> List[Dict[str, Any]]:
        """
        Get all scenarios for a specific edge case.

        Args:
            edge_case_name: Edge case name (e.g., "new_booking_confirmation")

        Returns:
            List of scenario contexts
        """
        contexts = self.build_scenario_contexts()
        return [c for c in contexts if edge_case_name.lower() in c["scenario"].lower()]

    def get_high_volume_scenarios(self, batch_size: int = 50) -> List[Dict[str, Any]]:
        """
        Get high-volume batch scenarios.

        Args:
            batch_size: Expected batch size (default 50)

        Returns:
            List of high-volume scenario contexts
        """
        return self.get_scenarios_by_edge_case("high-volume")
