"""
Comparison Testing - Parity Validation Suite

Story 4.2 Task 2, Task 3: Implements AC 2, 3, 4, 8
- Replays production workloads through both implementations
- Compares SMS, DynamoDB, Telegram outputs
- Validates parity with structured diff artifacts
- Integrates into pytest CI workflow
"""

import json
import logging
import pytest
import os
from datetime import datetime

from tests.comparison.comparison_factory import ComparisonFactory
from tests.comparison.output_normalizer import OutputNormalizer
from tests.comparison.diff_reporter import DiffReporter
from tests.comparison.parity_validator import ParityValidator

logger = logging.getLogger(__name__)

# Initialize factory and reporter
FACTORY = ComparisonFactory()
REPORTER = DiffReporter()
VALIDATOR = ParityValidator()

# Get container digest from environment for audit trail (AC 6: production tracking)
CONTAINER_DIGEST = os.environ.get(
    "CONTAINER_DIGEST", os.environ.get("GITHUB_SHA", "local-development")
)
DATASET_VERSION = os.environ.get("DATASET_VERSION", "1.0")


class TestOutputParity:
    """
    Parametrized pytest suite for parity validation.

    Implements AC 4, 8:
    - AC 4: Implement parity suite as tests/comparison/test_output_parity.py
    - AC 8: Automated checks ensure masking, parity checks integrate into CI
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        logger.info("Starting parity test")
        yield
        logger.info("Completed parity test")

    @staticmethod
    def _update_report_with_container_metadata(booking_id: str):
        """Update JSON report with container digest for audit trail (AC 6)."""
        json_path = REPORTER.output_dir / f"{booking_id.replace('/', '_')}.json"
        if json_path.exists():
            try:
                with json_path.open("r", encoding="utf-8") as f:
                    report = json.load(f)
                report["metadata"]["container_digest"] = CONTAINER_DIGEST
                report["metadata"]["dataset_version"] = DATASET_VERSION
                report["metadata"]["parity_run_timestamp"] = datetime.now().isoformat()
                with json_path.open("w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2)
                logger.debug(f"Updated container metadata for {booking_id}")
            except Exception as e:
                logger.warning(f"Could not update container metadata: {e}")

    @pytest.mark.parametrize(
        "booking_id", FACTORY.list_all_scenarios(), ids=lambda x: x  # Use booking_id as test ID
    )
    def test_parity_new_booking_confirmation(self, booking_id: str):
        """Test parity for new booking confirmation scenarios."""
        if "new_booking" not in booking_id.lower() and "case1" not in booking_id:
            pytest.skip("Not a new booking scenario")

        self._test_scenario_parity(booking_id)

    @pytest.mark.parametrize("booking_id", FACTORY.list_all_scenarios(), ids=lambda x: x)
    def test_parity_two_hour_reminder(self, booking_id: str):
        """Test parity for two-hour reminder scenarios."""
        if "two_hour" not in booking_id.lower() and "case2" not in booking_id:
            pytest.skip("Not a two-hour scenario")

        self._test_scenario_parity(booking_id)

    @pytest.mark.parametrize("booking_id", FACTORY.list_all_scenarios(), ids=lambda x: x)
    def test_parity_option_keyword_8pm(self, booking_id: str):
        """Test parity for option keyword at 8 PM scenarios."""
        if "option" not in booking_id.lower() and "case3" not in booking_id:
            pytest.skip("Not an option scenario")

        self._test_scenario_parity(booking_id)

    @pytest.mark.parametrize("booking_id", FACTORY.list_all_scenarios(), ids=lambda x: x)
    def test_parity_cookie_expiry(self, booking_id: str):
        """Test parity for cookie expiry scenarios."""
        if "cookie" not in booking_id.lower() and "case4" not in booking_id:
            pytest.skip("Not a cookie scenario")

        self._test_scenario_parity(booking_id)

    @pytest.mark.parametrize("booking_id", FACTORY.list_all_scenarios(), ids=lambda x: x)
    def test_parity_empty_response(self, booking_id: str):
        """Test parity for empty booking response scenarios."""
        if "empty" not in booking_id.lower() and "case5" not in booking_id:
            pytest.skip("Not an empty response scenario")

        self._test_scenario_parity(booking_id)

    @pytest.mark.parametrize("booking_id", FACTORY.list_all_scenarios(), ids=lambda x: x)
    def test_parity_high_volume(self, booking_id: str):
        """Test parity for high-volume processing scenarios."""
        if "volume" not in booking_id.lower() and "case6" not in booking_id:
            pytest.skip("Not a high-volume scenario")

        self._test_scenario_parity(booking_id)

    def test_all_scenarios_parity(self):
        """
        Comprehensive test - run all scenarios and collect aggregate results.

        Implements AC 8: Parity suite integrates into CI gating
        """
        scenarios = FACTORY.build_scenario_contexts()
        all_stats = []
        critical_failures = []

        for scenario in scenarios:
            booking_id = scenario.get("booking_id")
            logger.info(f"Testing parity for {booking_id}")

            try:
                # Execute both handlers
                legacy_outputs, refactored_outputs, errors = VALIDATOR.compare_scenario(scenario)

                # Normalize outputs
                canonical_legacy, canonical_refactored = OutputNormalizer.canonicalize_all_outputs(
                    legacy_outputs, refactored_outputs
                )

                # Compare
                expected_outputs = FACTORY.get_expected_output(booking_id)
                mismatches, stats = REPORTER.compare_outputs(
                    booking_id, canonical_legacy, canonical_refactored, expected_outputs
                )

                all_stats.append(stats)

                # Write reports with container metadata for audit trail (AC 6)
                REPORTER.write_reports(
                    booking_id,
                    scenario.get("scenario"),
                    mismatches,
                    stats,
                    canonical_legacy,
                    canonical_refactored,
                )

                # Update with container metadata for audit trail
                TestOutputParity._update_report_with_container_metadata(booking_id)

                # Track critical failures
                if stats["critical_mismatches"] > 0:
                    critical_failures.append((booking_id, stats["critical_mismatches"]))

            except Exception as e:
                logger.error(f"Failed to test parity for {booking_id}: {e}")
                critical_failures.append((booking_id, f"Execution error: {e}"))

        # Write aggregate summary
        REPORTER.write_aggregate_summary(all_stats)

        # Assert no critical failures
        if critical_failures:
            failure_summary = "\n".join([f"  - {bid}: {count}" for bid, count in critical_failures])
            pytest.fail(f"Parity validation failed with critical mismatches:\n{failure_summary}")

        # Assert minimum pass rate
        passed = sum(1 for s in all_stats if s["parity_status"] == "PASS")
        pass_rate = (passed / len(all_stats) * 100) if all_stats else 0

        logger.info(
            f"Parity validation complete: {passed}/{len(all_stats)} passed ({pass_rate:.1f}%)"
        )
        assert pass_rate >= 80, f"Pass rate {pass_rate:.1f}% below 80% threshold"

    def test_masking_enforcement(self):
        """
        Validate that comparison artifacts never store raw PII.

        Implements AC 7: Automated checks ensure masking
        """
        # Load generated JSON reports
        results_dir = REPORTER.output_dir

        if not results_dir.exists():
            pytest.skip("No comparison results generated yet")

        json_files = list(results_dir.glob("*.json"))

        if not json_files:
            pytest.skip("No JSON reports found")

        pii_patterns = {
            "phone": r"01\d[-\s]?\d{3,4}[-\s]?\d{4}",  # Korean phone pattern
            "name_korean": r"[가-힣]{2,}",  # Korean characters
        }

        for json_file in json_files:
            with json_file.open("r", encoding="utf-8") as f:
                content = f.read()

            # Check for raw phone numbers
            import re

            for pattern_name, pattern in pii_patterns.items():
                matches = re.findall(pattern, content)
                assert not matches, f"Found {pattern_name} in {json_file.name}: {matches}"

        logger.info(f"Masking enforcement passed for {len(json_files)} reports")

    def test_determinism(self):
        """
        Validate that handler execution is deterministic.

        Implements AC 2: Deterministic execution for both implementations
        """
        scenarios = FACTORY.build_scenario_contexts()[:3]  # Test first 3 scenarios

        for scenario in scenarios:
            booking_id = scenario.get("booking_id")
            is_deterministic, message = VALIDATOR.validate_determinism(scenario, num_runs=3)

            assert is_deterministic, f"{booking_id}: {message}"
            logger.info(f"{booking_id}: {message}")

    def test_idempotency(self):
        """
        Validate that handler execution is idempotent.

        Running same scenario twice should not create duplicate effects.
        """
        scenarios = FACTORY.build_scenario_contexts()[:3]  # Test first 3 scenarios

        for scenario in scenarios:
            booking_id = scenario.get("booking_id")
            is_idempotent, message = VALIDATOR.validate_idempotency(scenario)

            assert is_idempotent, f"{booking_id}: {message}"
            logger.info(f"{booking_id}: {message}")

    def _test_scenario_parity(self, booking_id: str):
        """
        Test parity for a single scenario.

        Args:
            booking_id: ID of booking to test
        """
        # Get scenario context
        scenario_contexts = FACTORY.build_scenario_contexts()
        scenario = None
        for ctx in scenario_contexts:
            if ctx["booking_id"] == booking_id:
                scenario = ctx
                break

        assert scenario is not None, f"Scenario {booking_id} not found"

        # Execute both handlers
        legacy_outputs, refactored_outputs, errors = VALIDATOR.compare_scenario(scenario)

        # Should not have errors
        if errors:
            logger.warning(f"Execution errors for {booking_id}: {errors}")

        # Normalize outputs
        canonical_legacy, canonical_refactored = OutputNormalizer.canonicalize_all_outputs(
            legacy_outputs, refactored_outputs
        )

        # Compare outputs
        expected_outputs = FACTORY.get_expected_output(booking_id)
        mismatches, stats = REPORTER.compare_outputs(
            booking_id, canonical_legacy, canonical_refactored, expected_outputs
        )

        # Write reports
        REPORTER.write_reports(
            booking_id,
            scenario.get("scenario"),
            mismatches,
            stats,
            canonical_legacy,
            canonical_refactored,
        )

        # Update with container metadata for audit trail (AC 6)
        TestOutputParity._update_report_with_container_metadata(booking_id)

        # Assert parity
        if stats["critical_mismatches"] > 0:
            critical_mismatches = [m for m in mismatches if m.severity == "critical"]
            mismatch_details = "\n".join(
                [
                    f"  - {m.field}: {m.legacy_value} vs {m.refactored_value}"
                    for m in critical_mismatches
                ]
            )
            pytest.fail(f"Parity validation failed for {booking_id}:\n{mismatch_details}")

        # Assert pass status
        assert stats["parity_status"] == "PASS", f"Parity check failed for {booking_id}"


class TestComparisonFixtures:
    """Test suite for comparison fixtures and data integrity."""

    def test_fixtures_load_successfully(self):
        """Test that all fixtures load without errors."""
        bookings = FACTORY.load_bookings_fixture()
        expected_outputs = FACTORY.load_expected_outputs_fixture()

        assert len(bookings["bookings"]) > 0, "No bookings loaded"
        assert len(expected_outputs["expected_outputs"]) > 0, "No expected outputs loaded"

    def test_fixture_coverage(self):
        """Test that fixtures cover all required edge cases."""
        bookings_fixture = FACTORY.load_bookings_fixture()
        required_edge_cases = {
            "new booking confirmation",
            "two-hour window reminder",
            "option keyword trigger at 8 pm",
            "cookie expiry",
            "empty booking response",
            "high-volume processing",
        }

        scenario_names = " ".join([b["scenario"].lower() for b in bookings_fixture["bookings"]])

        for edge_case in required_edge_cases:
            assert edge_case.lower() in scenario_names, f"Missing edge case: {edge_case}"

    def test_fixture_data_integrity(self):
        """Test that fixture data has required fields."""
        bookings = FACTORY.load_bookings_fixture()
        required_fields = [
            "booking_id",
            "biz_id",
            "book_id",
            "customer_phone",
            "customer_name",
            "store_name",
            "booking_time",
            "status",
        ]

        for booking in bookings["bookings"]:
            for field in required_fields:
                assert field in booking, f"Missing field {field} in {booking.get('booking_id')}"
