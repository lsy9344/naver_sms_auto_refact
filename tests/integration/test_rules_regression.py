"""
Regression Test Harness for Rules Configuration

Verifies that the new YAML-based rule engine produces identical results
to the legacy SMS automation logic.

Test Strategy:
1. Load rules.yaml configuration
2. Load booking fixtures with expected outcomes
3. For each booking fixture:
   - Process through new rule engine
   - Compare action sequences against baseline
   - Assert 100% match (same actions, same parameters, same order)
4. Generate regression report

Acceptance Criteria Coverage:
- AC7: Rule engine comparison harness processes legacy booking fixtures
- AC7: Confirms identical action sequences (SMS type, DB updates, notifications)
- AC7: Results recorded in VALIDATION.md
"""

from unittest.mock import Mock

from src.domain.booking import Booking

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import pytest

# Add src directory to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from domain.booking import Booking

from config.settings import Settings
from rules.engine import RuleEngine
from rules.conditions import (
    booking_not_in_db,
    time_before_booking,
    flag_not_set,
    current_hour,
    booking_status,
    has_option_keyword,
    has_multiple_options,
    date_range,
)
from rules.actions import (
    send_sms,
    create_db_record,
    update_flag,
    send_telegram,
    send_slack,
    log_event,
    register_actions,
    ActionServicesBundle,
)

logger = logging.getLogger(__name__)


class InMemoryBookingRepository:
    """In-memory replacement for BookingRepository to support regression tests."""

    def __init__(self) -> None:
        """Initialise repository store."""
        self.records: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def seed_record(self, booking_num: str, phone: str, record: Dict[str, Any]) -> None:
        """Seed repository with an existing booking record."""
        base = {
            "booking_num": booking_num,
            "phone": phone,
            "confirm_sms": bool(record.get("confirm_sms", False)),
            "remind_sms": bool(record.get("remind_sms", False)),
            "option_sms": bool(record.get("option_sms", False)),
            "option_time": record.get("option_time", ""),
        }
        self.records[(booking_num, phone)] = {**base, **record}

    def remove_record(self, booking_num: str, phone: str) -> None:
        """Remove record if present."""
        self.records.pop((booking_num, phone), None)

    def create_booking(self, record: Dict[str, Any]) -> bool:
        """Create a new booking record."""
        booking_num = record["booking_num"]
        phone = record["phone"]
        self.seed_record(booking_num, phone, record)
        return True

    def get_booking(self, prefix: str, phone: str) -> Dict[str, Any] | None:
        """Fetch booking if it exists."""
        return self.records.get((prefix, phone))

    def update_flag(self, *, prefix: str, phone: str, flag_name: str, value: bool) -> bool:
        """Update flag and persist value."""
        record = self.records.setdefault(
            (prefix, phone),
            {
                "booking_num": prefix,
                "phone": phone,
                "confirm_sms": False,
                "remind_sms": False,
                "option_sms": False,
            },
        )
        record[flag_name] = value
        return True


class ActionContext:
    """Wrapper to provide attribute-based access to context dict for action executors."""

    def __init__(self, context_dict: Dict[str, Any]):
        """Initialize with context dict."""
        self._dict = context_dict
        # Add logger attribute
        self.logger = logging.getLogger("ActionContext")

    def __getattr__(self, name: str) -> Any:
        """Get attribute from dict if not found in object."""
        if name in ("_dict", "logger"):
            return object.__getattribute__(self, name)
        return self._dict.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attribute in dict if exists, otherwise in object."""
        if name in ("_dict", "logger"):
            object.__setattr__(self, name, value)
        else:
            self._dict[name] = value


class RegressionTestFixture:
    """Load and manage test fixtures."""

    def __init__(self, fixtures_dir: Path):
        """Initialize fixture loader."""
        self.fixtures_dir = fixtures_dir
        self.bookings = []
        self.expected_actions = {}
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        """Load booking and expected action fixtures."""
        # Load bookings
        bookings_file = self.fixtures_dir / "legacy_bookings.json"
        with open(bookings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.bookings = data.get("bookings", [])

        # Load expected actions
        expected_file = self.fixtures_dir / "legacy_expected_actions.json"
        with open(expected_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.expected_actions = data.get("expected_actions", {})

        logger.info(f"Loaded {len(self.bookings)} booking fixtures")
        logger.info(f"Loaded expected actions for {len(self.expected_actions)} bookings")

    def get_bookings(self) -> List[Dict[str, Any]]:
        """Get all booking fixtures."""
        return self.bookings

    def get_expected_actions(self, booking_id: str) -> List[Dict[str, Any]]:
        """Get expected actions for a booking."""
        result = self.expected_actions.get(booking_id, {})
        return result.get("actions", [])

    def get_expected_rules(self, booking_id: str) -> List[str]:
        """Get expected matching rules for a booking."""
        booking = next((b for b in self.bookings if b["id"] == booking_id), None)
        if booking:
            return booking.get("expected_rule_matches", [])
        return []


class RegressionTestRunner:
    """Run regression tests against rule engine."""

    def __init__(
        self,
        rule_engine: RuleEngine,
        fixtures: RegressionTestFixture,
        *,
        artifact_dir: Optional[Path] = None,
    ):
        """Initialize test runner."""
        self.engine = rule_engine
        self.fixtures = fixtures
        self.results = []
        self.db_repo = getattr(rule_engine, "_db_repo_for_tests", None)
        self.artifact_dir = (
            artifact_dir
            if artifact_dir is not None
            else Path(__file__).parent / "artifacts" / "rule_engine_regression"
        )
        self.summary_path = self.artifact_dir / "summary.json"

    def _artifact_path(self, booking_id: str) -> Path:
        """Compute path for a booking-specific artifact."""
        safe_id = booking_id.replace("/", "_")
        return self.artifact_dir / f"{safe_id}.json"

    def _ensure_artifact_dir(self) -> None:
        """Ensure artifact directory exists."""
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def _write_failure_artifact(self, booking_id: str, payload: Dict[str, Any]) -> str:
        """Persist mismatch details for later inspection."""
        self._ensure_artifact_dir()
        artifact_path = self._artifact_path(booking_id)
        with open(artifact_path, "w", encoding="utf-8") as artifact_file:
            json.dump(payload, artifact_file, ensure_ascii=False, indent=2)
        return str(artifact_path)

    def _remove_artifact(self, booking_id: str) -> None:
        """Remove stale artifact for passing bookings."""
        artifact_path = self._artifact_path(booking_id)
        if artifact_path.exists():
            artifact_path.unlink()

    def _write_summary(self) -> None:
        """Write summary file when mismatches detected."""
        failed_results = [r for r in self.results if not r["success"]]
        if not failed_results:
            self._remove_summary()
            return

        self._ensure_artifact_dir()
        summary_payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(self.results),
            "failed": len(failed_results),
            "failed_bookings": [
                {
                    "booking_id": r["booking_id"],
                    "booking_name": r["booking_name"],
                    "artifact_path": r.get("artifact_path"),
                    "differences": r.get("differences", []),
                    "error": r.get("error"),
                }
                for r in failed_results
            ],
        }
        with open(self.summary_path, "w", encoding="utf-8") as summary_file:
            json.dump(summary_payload, summary_file, ensure_ascii=False, indent=2)

    def _remove_summary(self) -> None:
        """Remove summary file and clean directory if empty."""
        if self.summary_path.exists():
            self.summary_path.unlink()
        try:
            # Remove artifact directory if it exists and is now empty
            self.artifact_dir.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            # Directory not empty - keep artifacts in place
            pass

    def build_context(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """Build execution context from booking fixture, converting to domain objects."""

        def parse_datetime(value: str) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                normalized = value.replace(" ", "T")
                try:
                    return datetime.fromisoformat(normalized)
                except ValueError:
                    return None

        current_time = parse_datetime(booking.get("current_time", ""))

        # Convert fixture booking dict to Booking dataclass
        # Extract and prepare booking data from fixture
        booking_data = booking.get("booking", {})

        # Generate booking_num from store_id and fixture ID
        store_id = booking_data.get("store_id", "1051707")  # Default store
        fixture_id = booking.get("id", "unknown_booking")
        booking_num = f"{store_id}_{fixture_id}"

        # Map fixture fields to Booking dataclass fields
        booking_dict = {
            "booking_num": booking_num,
            "phone": booking_data.get("customer_phone", ""),
            "name": booking_data.get("customer_name", ""),
            "booking_time": booking_data.get("booking_time", ""),
            "confirm_sms": False,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }

        # Add any extra fields from fixture booking
        extra_fields = {
            k: v
            for k, v in booking_data.items()
            if k not in ["customer_phone", "customer_name", "booking_time", "status", "option"]
        }

        # Store fixture data in extra_fields for action executors
        if "status" in booking_data:
            extra_fields["status"] = booking_data["status"]
        if "option" in booking_data:
            extra_fields["option"] = booking_data["option"]
        if "store_id" in booking_data:
            extra_fields["store_id"] = booking_data["store_id"]

        # Create Booking object
        booking_obj = Booking(**booking_dict)
        if extra_fields:
            booking_obj.extra_fields = extra_fields

        reserve_at = parse_datetime(booking_data.get("booking_time", ""))
        if reserve_at:
            booking_obj.reserve_at = reserve_at

        option_value = booking_data.get("option")
        if option_value:
            # Preserve raw option value and seed keywords for matcher
            booking_obj.option = option_value
            booking_obj.option_keywords = (
                [option_value] if isinstance(option_value, str) else option_value
            )
        elif booking_data.get("option_keywords"):
            booking_obj.option_keywords = booking_data["option_keywords"]

        # Get DB record if present
        db_record = booking.get("db_record")
        if db_record:
            # Update booking flags from DB record
            if "confirm_sms" in db_record:
                booking_obj.confirm_sms = db_record["confirm_sms"]
            if "remind_sms" in db_record:
                booking_obj.remind_sms = db_record["remind_sms"]
            if "option_sms" in db_record:
                booking_obj.option_sms = db_record["option_sms"]

        return {
            "booking": booking_obj,
            "db_record": db_record,
            "current_time": current_time,
        }

    def test_booking(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single booking fixture."""
        booking_id = booking.get("id", "unknown")
        booking_name = booking.get("name", "unknown")

        logger.info(f"Testing booking {booking_id}: {booking_name}")

        # Build context - pass dict directly to engine (not wrapped)
        context_dict = self.build_context(booking)

        # Seed repository for update_flag parity
        if self.db_repo is not None:
            booking_obj: Booking = context_dict["booking"]
            db_record = context_dict.get("db_record")
            if db_record:
                seed_record = {
                    "booking_num": booking_obj.booking_num,
                    "phone": booking_obj.phone,
                    **db_record,
                }
                self.db_repo.seed_record(booking_obj.booking_num, booking_obj.phone, seed_record)
            else:
                self.db_repo.remove_record(booking_obj.booking_num, booking_obj.phone)

        # Execute rules
        try:
            results = self.engine.process_booking(context_dict)
            success = True
            error = None
        except Exception as e:
            logger.error(f"Error processing booking {booking_id}: {e}", exc_info=True)
            success = False
            error = str(e)
            results = []

        # Get expected actions
        expected_actions = self.fixtures.get_expected_actions(booking_id)

        # Compare results in detail
        actual_actions = []
        differences: List[Dict[str, Any]] = []

        for r in results:
            action_entry: Dict[str, Any] = {
                "rule_name": r.rule_name,
                "action_type": r.action_type,
                "success": r.success,
                "message": r.message,
                "params": getattr(r, "params", {}),
            }
            if r.error:
                action_entry["error"] = r.error
            actual_actions.append(action_entry)

        if len(actual_actions) != len(expected_actions):
            differences.append(
                {
                    "type": "count_mismatch",
                    "expected": len(expected_actions),
                    "actual": len(actual_actions),
                }
            )

        compare_count = min(len(actual_actions), len(expected_actions))
        for idx in range(compare_count):
            expected_action = expected_actions[idx]
            actual_action = actual_actions[idx]

            for field in ("rule_name", "action_type", "success"):
                if actual_action.get(field) != expected_action.get(field):
                    differences.append(
                        {
                            "type": "field_mismatch",
                            "index": idx,
                            "field": field,
                            "expected": expected_action.get(field),
                            "actual": actual_action.get(field),
                        }
                    )

            expected_params = expected_action.get("params", {})
            actual_params = actual_action.get("params", {})
            if expected_params != actual_params:
                differences.append(
                    {
                        "type": "params_mismatch",
                        "index": idx,
                        "expected": expected_params,
                        "actual": actual_params,
                    }
                )

        result = {
            "booking_id": booking_id,
            "booking_name": booking_name,
            "success": success and not differences,
            "error": error,
            "expected_action_count": len(expected_actions),
            "actual_action_count": len(actual_actions),
            "actual_actions": actual_actions,
            "expected_actions": expected_actions,
            "differences": differences,
        }

        artifact_payload = {
            "booking_id": booking_id,
            "booking_name": booking_name,
            "error": error,
            "differences": differences,
            "expected_actions": expected_actions,
            "actual_actions": actual_actions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if differences:
            logger.error("Action parity mismatch for %s: %s", booking_id, differences)
            result["artifact_path"] = self._write_failure_artifact(booking_id, artifact_payload)
        elif not success:
            logger.error("Error processing booking %s: %s", booking_id, error)
            result["artifact_path"] = self._write_failure_artifact(booking_id, artifact_payload)
        else:
            self._remove_artifact(booking_id)
            result["artifact_path"] = None

        self.results.append(result)
        return result

    def run_all(self) -> Dict[str, Any]:
        """Run tests for all bookings."""
        bookings = self.fixtures.get_bookings()

        for booking in bookings:
            self.test_booking(booking)

        # Calculate summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed

        self._write_summary()

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed/total*100):.1f}%" if total > 0 else "N/A",
            "results": self.results,
        }


@pytest.fixture(scope="module")
def fixtures_dir():
    """Get fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module")
def settings(fixtures_dir):
    """Load settings and rules."""
    project_root = Path(__file__).parent.parent.parent
    rules_config = project_root / "config" / "rules.yaml"
    rules_schema = project_root / "src" / "config" / "rules.schema.json"

    settings = Settings()
    settings.load_rules(str(rules_config), str(rules_schema))
    return settings


@pytest.fixture(scope="module")
def rule_engine(settings):
    """Initialize rule engine with registered conditions and actions."""
    from unittest.mock import Mock
    from src.utils.logger import StructuredLogger

    engine = RuleEngine(str(Path(__file__).parent.parent.parent / "config" / "rules.yaml"))

    # Register condition evaluators
    engine.register_condition("booking_not_in_db", booking_not_in_db)
    engine.register_condition("time_before_booking", time_before_booking)
    engine.register_condition("flag_not_set", flag_not_set)
    engine.register_condition("current_hour", current_hour)
    engine.register_condition("booking_status", booking_status)
    engine.register_condition("has_option_keyword", has_option_keyword)
    engine.register_condition("date_range", date_range)
    engine.register_condition("has_multiple_options", has_multiple_options)

    # Create services for action executors
    db_repo = InMemoryBookingRepository()

    mock_sms_service = Mock()
    mock_sms_service.send_confirm_sms.return_value = None
    mock_sms_service.send_guide_sms.return_value = None
    mock_sms_service.send_event_sms.return_value = None

    mock_logger = Mock(spec=StructuredLogger)
    mock_logger.logger = Mock()
    mock_logger.logger.name = "test_logger"
    mock_logger.debug = Mock()
    mock_logger.info = Mock()
    mock_logger.warning = Mock()
    mock_logger.error = Mock()

    services = ActionServicesBundle(
        db_repo=db_repo,
        sms_service=mock_sms_service,
        slack_service=None,
        slack_template_loader=None,
        logger=mock_logger,
        settings_dict={"slack_enabled": False},
    )

    # Register action executors using register_actions
    register_actions(engine, services)
    engine._db_repo_for_tests = db_repo

    return engine


@pytest.fixture(scope="module")
def test_fixtures(fixtures_dir):
    """Load test fixtures."""
    return RegressionTestFixture(fixtures_dir)


@pytest.fixture(scope="module")
def test_runner(rule_engine, test_fixtures):
    """Create regression test runner."""
    return RegressionTestRunner(rule_engine, test_fixtures)


class TestRulesRegression:
    """Regression test suite for rules configuration."""

    def test_regression_suite(self, test_runner):
        """
        Run full regression test suite.

        Validates that new rule engine produces identical results to legacy system.
        """
        results = test_runner.run_all()

        # Log results
        logger.info("=" * 80)
        logger.info("REGRESSION TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {results['total']}")
        logger.info(f"Passed: {results['passed']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Pass Rate: {results['pass_rate']}")
        logger.info("=" * 80)

        # Print individual results
        for result in results["results"]:
            status = "✓ PASS" if result["success"] else "✗ FAIL"
            logger.info(f"{status}: {result['booking_id']} - {result['booking_name']}")
            if not result["success"]:
                logger.info(
                    f"  Expected {result['expected_action_count']} actions, "
                    f"got {result['actual_action_count']}"
                )
                if result["error"]:
                    logger.error(f"  Error: {result['error']}")

        # Assert all tests passed
        assert (
            results["failed"] == 0
        ), f"Regression tests failed: {results['failed']} of {results['total']} failed"

    def test_booking_001_new_confirmation(self, test_runner, test_fixtures):
        """Test booking 001: New Booking Confirmation."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_001")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 001 failed: {result}"

    def test_booking_002_two_hour_reminder(self, test_runner, test_fixtures):
        """Test booking 002: Two-Hour Reminder."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_002")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 002 failed: {result}"

    def test_booking_003_evening_option_sms(self, test_runner, test_fixtures):
        """Test booking 003: Evening Option SMS."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_003")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 003 failed: {result}"

    def test_booking_004_all_flags_set(self, test_runner, test_fixtures):
        """Test booking 004: All Flags Set - No rules match."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_004")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 004 failed: {result}"

    def test_booking_005_no_keyword(self, test_runner, test_fixtures):
        """Test booking 005: No Option Keyword - No Option SMS."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_005")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 005 failed: {result}"

    def test_booking_006_date_range_within(self, test_runner, test_fixtures):
        """Test booking 006: Date Range - Booking within date range (Story 6.3)."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_006")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 006 failed: {result}"

    def test_booking_007_date_range_before(self, test_runner, test_fixtures):
        """Test booking 007: Date Range - Booking before date range (Story 6.3)."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_007")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 007 failed: {result}"

    def test_booking_008_date_range_after(self, test_runner, test_fixtures):
        """Test booking 008: Date Range - Booking after date range (Story 6.3)."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_008")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 008 failed: {result}"

    def test_booking_009_expert_correction_slack_digest(self, test_runner, test_fixtures):
        """Test booking 009: Expert Correction Slack Digest (Story 6.1, AC1) - Rule matches but Slack disabled."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_009")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 009 failed: {result}"
        # Note: send_slack action does not execute because slack_enabled=False in test fixture

    def test_booking_010_holiday_event_customer_list(self, test_runner, test_fixtures):
        """Test booking 010: Holiday Event Customer List (Story 6.1, AC3) - Rule disabled."""
        booking = next(b for b in test_fixtures.get_bookings() if b["id"] == "booking_010")
        result = test_runner.test_booking(booking)
        assert result["success"], f"Booking 010 failed: {result}"
        # Note: Holiday Event rule is disabled in config, so it does not match

    def test_has_multiple_options_sufficient_matches(self):
        """Story 6.4: has_multiple_options - Sufficient keyword matches."""
        booking = Booking(
            booking_num="test_multi_001",
            phone="01012345678",
            name="Test User",
            booking_time="2025-10-20 10:00:00",
            reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=timezone.utc),
            status="RC03",
            biz_id="1051707",
            extra_fields={"option_keywords": ["네이버 Pay", "원본 방식"]},
        )
        # Add option_keywords to booking instance
        booking.option_keywords = ["네이버 Pay", "원본 방식"]

        context = {
            "booking": booking,
            "db_record": None,
            "current_time": datetime(2025, 10, 20, 8, 0, tzinfo=timezone.utc),
        }
        # 2 keywords match against 2 required minimum
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=2)
        assert result is True

    def test_has_multiple_options_insufficient_matches(self):
        """Story 6.4: has_multiple_options - Insufficient keyword matches."""
        booking = Booking(
            booking_num="test_multi_002",
            phone="01012345678",
            name="Test User",
            booking_time="2025-10-20 10:00:00",
            reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=timezone.utc),
            status="RC03",
            biz_id="1051707",
        )
        # Add option_keywords to booking instance
        booking.option_keywords = ["네이버 Pay"]

        context = {
            "booking": booking,
            "db_record": None,
            "current_time": datetime(2025, 10, 20, 8, 0, tzinfo=timezone.utc),
        }
        # Only 1 keyword matches but 2 required
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=2)
        assert result is False

    def test_has_multiple_options_no_matches(self):
        """Story 6.4: has_multiple_options - No keyword matches."""
        booking = Booking(
            booking_num="test_multi_003",
            phone="01012345678",
            name="Test User",
            booking_time="2025-10-20 10:00:00",
            reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=timezone.utc),
            status="RC03",
            biz_id="1051707",
        )
        # Add option_keywords to booking instance
        booking.option_keywords = ["일반 방식"]

        context = {
            "booking": booking,
            "db_record": None,
            "current_time": datetime(2025, 10, 20, 8, 0, tzinfo=timezone.utc),
        }
        result = has_multiple_options(context, keywords=["네이버", "원본"], min_count=1)
        assert result is False

    def test_has_multiple_options_multiple_options_single_keyword(self):
        """Story 6.4: has_multiple_options - Multiple option objects match single keyword."""
        booking = Booking(
            booking_num="test_multi_004",
            phone="01012345678",
            name="Test User",
            booking_time="2025-10-20 10:00:00",
            reserve_at=datetime(2025, 10, 20, 10, 0, tzinfo=timezone.utc),
            status="RC03",
            biz_id="1051707",
        )
        # Add option_keywords to booking instance
        booking.option_keywords = ["네이버 Pay", "네이버 보험", "인스타"]

        context = {
            "booking": booking,
            "db_record": None,
            "current_time": datetime(2025, 10, 20, 8, 0, tzinfo=timezone.utc),
        }
        # 2 options match "네이버" keyword + 1 "인스타" = 3 matches
        result = has_multiple_options(context, keywords=["네이버", "인스타"], min_count=3)
        assert result is True


class TestSlackEnabledRegression:
    """Regression tests for Slack-enabled rules (Story 6.1, AC4)."""

    @pytest.fixture
    def slack_enabled_engine(self, settings):
        """Initialize rule engine with Slack enabled for regression testing."""
        from unittest.mock import Mock
        from src.utils.logger import StructuredLogger

        engine = RuleEngine(
            str(Path(__file__).parent.parent.parent / "config" / "rules.yaml")
        )

        # Register condition evaluators
        engine.register_condition("booking_not_in_db", booking_not_in_db)
        engine.register_condition("time_before_booking", time_before_booking)
        engine.register_condition("flag_not_set", flag_not_set)
        engine.register_condition("current_hour", current_hour)
        engine.register_condition("booking_status", booking_status)
        engine.register_condition("has_option_keyword", has_option_keyword)
        engine.register_condition("has_multiple_options", has_multiple_options)
        engine.register_condition("date_range", date_range)

        # Create services for action executors
        db_repo = InMemoryBookingRepository()

        mock_sms_service = Mock()
        mock_sms_service.send_confirm_sms.return_value = None
        mock_sms_service.send_guide_sms.return_value = None
        mock_sms_service.send_event_sms.return_value = None

        mock_slack_service = Mock()
        mock_slack_service._dispatch.return_value = None

        mock_slack_template_loader = Mock()
        mock_slack_template_loader.render.return_value = "Rendered Slack template"

        mock_logger = Mock(spec=StructuredLogger)
        mock_logger.logger = Mock()
        mock_logger.logger.name = "test_logger"
        mock_logger.debug = Mock()
        mock_logger.info = Mock()
        mock_logger.warning = Mock()
        mock_logger.error = Mock()

        # KEY CHANGE: slack_enabled set to True for Slack-enabled tests (AC4)
        services = ActionServicesBundle(
            db_repo=db_repo,
            sms_service=mock_sms_service,
            slack_service=mock_slack_service,
            slack_template_loader=mock_slack_template_loader,
            logger=mock_logger,
            settings_dict={"slack_enabled": True},  # AC4: Enable Slack for regression
        )

        # Register action executors using register_actions
        register_actions(engine, services)
        engine._db_repo_for_tests = db_repo

        return engine

    @pytest.fixture
    def slack_enabled_runner(self, slack_enabled_engine, test_fixtures):
        """Create regression test runner with Slack enabled."""
        return RegressionTestRunner(slack_enabled_engine, test_fixtures)

    def test_booking_009_slack_enabled_expert_correction(self, slack_enabled_runner, test_fixtures):
        """Test booking 009 with Slack enabled: Expert Correction Slack Digest (Story 6.1, AC1, AC4).

        Regression evidence for AC4: Demonstrates that send_slack action executes
        when Slack is enabled and rule matches via has_option_keyword condition.
        """
        booking = next(
            (b for b in test_fixtures.get_bookings() if b["id"] == "booking_009_slack_enabled"),
            None,
        )
        assert booking is not None, "Fixture booking_009_slack_enabled not found"

        result = slack_enabled_runner.test_booking(booking)
        assert result["success"], (
            f"Booking 009 (Slack enabled) failed: Expected send_slack action, "
            f"got {result['actual_action_count']} actions. Differences: {result['differences']}"
        )
        # Verify send_slack was called
        assert (
            result["actual_action_count"] > 0
        ), "Expected at least one action (send_slack) for Expert Correction rule"
        assert any(
            action["action_type"] == "send_slack" for action in result["actual_actions"]
        ), "Expected send_slack action in Expert Correction rule execution"

    def test_booking_010_slack_enabled_holiday_event(self, slack_enabled_runner, test_fixtures):
        """Test booking 010 with Slack enabled: Holiday Event Customer List (Story 6.1, AC3, AC4).

        Regression evidence for AC4: Demonstrates that send_slack action executes
        when Slack is enabled and rule matches via date_range and has_multiple_options conditions.
        """
        booking = next(
            (b for b in test_fixtures.get_bookings() if b["id"] == "booking_010_slack_enabled"),
            None,
        )
        assert booking is not None, "Fixture booking_010_slack_enabled not found"

        result = slack_enabled_runner.test_booking(booking)
        assert result["success"], (
            f"Booking 010 (Slack enabled) failed: Expected send_slack action, "
            f"got {result['actual_action_count']} actions. Differences: {result['differences']}"
        )
        # Verify send_slack was called
        assert (
            result["actual_action_count"] > 0
        ), "Expected at least one action (send_slack) for Holiday Event rule"
        assert any(
            action["action_type"] == "send_slack" for action in result["actual_actions"]
        ), "Expected send_slack action in Holiday Event rule execution"
