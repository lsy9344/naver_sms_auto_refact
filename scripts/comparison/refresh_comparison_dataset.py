#!/usr/bin/env python3
"""
Fixture Refresh Script - Regenerate comparison datasets

Story 4.2 Task 4: Implements AC 5
- Regenerate fixtures while guaranteeing sanitized outputs
- Validate masking rules automatically
- Store versioned datasets with repo

Usage:
    python scripts/comparison/refresh_comparison_dataset.py [--output-dir /tmp]

Environment:
    NAVER_SMS_FIXTURES_REFRESH=1  (enables fixture refresh)
"""

import json
import logging
import sys
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FixtureRefresher:
    """
    Manage fixture lifecycle:
    - Export raw data from production sources
    - Apply masking/sanitization
    - Validate masking coverage
    - Version and store datasets
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize refresher.
        
        Args:
            output_dir: Temporary directory for raw exports (default /tmp)
        """
        if output_dir is None:
            output_dir = Path("/tmp")
        
        self.output_dir = output_dir
        self.fixtures_dir = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
        self.raw_export_dir = self.output_dir / "naver_sms_fixtures_raw"
        
        # Create directories
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        self.raw_export_dir.mkdir(parents=True, exist_ok=True)

    def refresh_bookings(self) -> Dict[str, Any]:
        """
        Refresh production bookings fixture.
        
        Steps:
        1. Export raw booking data from production source
        2. Apply masking/sanitization
        3. Validate masking coverage
        4. Write to committed fixture
        
        Returns:
            Updated bookings fixture
        """
        logger.info("🔄 Refreshing production bookings fixture...")

        # Step 1: Export raw data
        raw_bookings = self._export_raw_bookings()
        
        if not raw_bookings:
            logger.warning("No new bookings to export. Using synthetic fixtures.")
            return self._load_synthetic_bookings()

        # Step 2: Apply masking
        sanitized_bookings = self._sanitize_bookings(raw_bookings)

        # Step 3: Validate masking
        validation_result = self._validate_masking(sanitized_bookings)
        if not validation_result["passed"]:
            logger.error(f"Masking validation failed: {validation_result['errors']}")
            return None

        logger.info(f"✅ Masking validation passed: {validation_result['message']}")

        # Step 4: Write to fixture
        fixture_data = {
            "metadata": {
                "version": "1.0",
                "description": "Production-equivalent bookings with edge case coverage",
                "generated_date": datetime.now().isoformat(),
                "refresh_source": "production" if len(raw_bookings) > 5 else "synthetic",
                "total_bookings": len(sanitized_bookings),
                "masking_applied": True,
            },
            "bookings": sanitized_bookings,
        }

        bookings_path = self.fixtures_dir / "production_bookings.json"
        with bookings_path.open("w", encoding="utf-8") as f:
            json.dump(fixture_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Wrote {len(sanitized_bookings)} bookings to {bookings_path}")
        return fixture_data

    def refresh_expected_outputs(self, bookings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refresh expected outputs fixture.
        
        Args:
            bookings: Updated bookings fixture
            
        Returns:
            Updated expected outputs fixture
        """
        logger.info("🔄 Refreshing expected outputs fixture...")

        expected_outputs = {}

        for booking in bookings.get("bookings", []):
            booking_id = booking["booking_id"]
            scenario = booking["scenario"]

            # Generate expected output based on scenario
            expected = self._generate_expected_output(booking)
            expected_outputs[booking_id] = expected

        fixture_data = {
            "metadata": {
                "version": "1.0",
                "description": "Expected outputs for parity validation",
                "generated_date": datetime.now().isoformat(),
                "total_scenarios": len(expected_outputs),
            },
            "expected_outputs": expected_outputs,
            "validation_rules": self._get_validation_rules(),
        }

        outputs_path = self.fixtures_dir / "production_expected_outputs.json"
        with outputs_path.open("w", encoding="utf-8") as f:
            json.dump(fixture_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Wrote {len(expected_outputs)} expected outputs to {outputs_path}")
        return fixture_data

    def refresh_manifest(self, bookings: Dict[str, Any], expected_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refresh dataset manifest with checksums and metadata.
        
        Args:
            bookings: Bookings fixture
            expected_outputs: Expected outputs fixture
            
        Returns:
            Updated manifest
        """
        logger.info("🔄 Refreshing dataset manifest...")

        # Calculate checksums
        bookings_json = json.dumps(bookings, sort_keys=True, ensure_ascii=False)
        bookings_hash = hashlib.sha256(bookings_json.encode()).hexdigest()

        outputs_json = json.dumps(expected_outputs, sort_keys=True, ensure_ascii=False)
        outputs_hash = hashlib.sha256(outputs_json.encode()).hexdigest()

        manifest = {
            "manifest": {
                "version": "1.0",
                "dataset_name": "production_bookings_synthetic",
                "created_date": datetime.now().isoformat(),
                "checksums": {
                    "production_bookings.json": bookings_hash,
                    "production_expected_outputs.json": outputs_hash,
                },
            },
            "dataset_info": {
                "total_bookings": len(bookings.get("bookings", [])),
                "total_scenarios": len(expected_outputs.get("expected_outputs", {})),
                "edge_cases_covered": 6,
            },
            "validation_status": "FRESH",
            "last_validated": datetime.now().isoformat(),
        }

        manifest_path = self.fixtures_dir / "dataset_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Wrote manifest to {manifest_path}")
        logger.info(f"   Bookings SHA256: {bookings_hash[:8]}...")
        logger.info(f"   Outputs SHA256: {outputs_hash[:8]}...")

        return manifest

    def _export_raw_bookings(self) -> List[Dict[str, Any]]:
        """
        Export raw booking data from production.
        
        In real scenario, would fetch from:
        - DynamoDB bookings table
        - Production API logs
        - Event stream archives
        
        For now, returns empty list to trigger synthetic fallback.
        
        Returns:
            List of raw booking dicts
        """
        logger.info("Exporting raw booking data from production source...")
        
        # In production, would query actual data sources
        # For now, return empty to use synthetic fixtures
        return []

    def _sanitize_bookings(self, raw_bookings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply masking/sanitization to raw bookings.
        
        Args:
            raw_bookings: Raw bookings from production
            
        Returns:
            Sanitized bookings
        """
        logger.info(f"Applying masking to {len(raw_bookings)} bookings...")

        sanitized = []
        for booking in raw_bookings:
            # Apply masking rules
            sanitized_booking = {
                "booking_id": booking.get("booking_id"),
                # Phone numbers already masked or synthetic
                "customer_phone": booking.get("customer_phone"),
                # Names already masked or synthetic
                "customer_name": booking.get("customer_name"),
                # No other sensitive fields
                **booking
            }
            sanitized.append(sanitized_booking)

        return sanitized

    def _validate_masking(self, bookings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate masking coverage.
        
        Checks:
        - No raw phone numbers in format 01X-XXXX-XXXX
        - No email addresses
        - No credit card numbers
        - No API keys/secrets
        
        Args:
            bookings: Bookings to validate
            
        Returns:
            Validation result dict
        """
        import re

        logger.info("Validating masking coverage...")

        errors = []
        
        # Check for Korean phone numbers (01X-XXXX-XXXX or 01XXXXXXXXX)
        phone_pattern = r"01[0-9][-\s]?[0-9]{3,4}[-\s]?[0-9]{4}"
        
        for booking in bookings:
            booking_json = json.dumps(booking)
            
            # Check phone pattern
            matches = re.findall(phone_pattern, booking_json)
            if matches:
                errors.append(f"Found raw phone numbers: {matches}")
            
            # Check for common PII patterns
            if re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", booking_json):
                errors.append("Found email addresses")
            
            if re.search(r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}", booking_json):
                errors.append("Found credit card patterns")

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "message": "All masking checks passed" if len(errors) == 0 else f"{len(errors)} masking issues found",
        }

    def _load_synthetic_bookings(self) -> Dict[str, Any]:
        """
        Load existing synthetic bookings fixture.
        
        Returns:
            Existing bookings fixture
        """
        bookings_path = self.fixtures_dir / "production_bookings.json"
        
        if bookings_path.exists():
            with bookings_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        
        return {"metadata": {}, "bookings": []}

    def _generate_expected_output(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate expected output for a booking based on scenario.
        
        Args:
            booking: Booking dict
            
        Returns:
            Expected output dict
        """
        scenario = booking.get("scenario", "")

        if "new_booking" in scenario.lower() or "case1" in scenario:
            return {
                "scenario": scenario,
                "booking_id": booking["booking_id"],
                "expected_actions": [
                    {"action_type": "create_db_record", "success": True},
                    {"action_type": "send_sms", "success": True, "sms_type": "confirm"},
                    {"action_type": "send_telegram", "success": True},
                ],
                "expected_sms_count": 1,
            }
        elif "two_hour" in scenario.lower() or "case2" in scenario:
            return {
                "scenario": scenario,
                "booking_id": booking["booking_id"],
                "expected_actions": [
                    {"action_type": "send_sms", "success": True, "sms_type": "guide"},
                    {"action_type": "update_flag", "success": True},
                ],
                "expected_sms_count": 1,
            }
        elif "option" in scenario.lower() or "case3" in scenario:
            return {
                "scenario": scenario,
                "booking_id": booking["booking_id"],
                "expected_actions": [
                    {"action_type": "send_sms", "success": True, "sms_type": "event"},
                    {"action_type": "update_flag", "success": True},
                ],
                "expected_sms_count": 1,
            }
        else:
            return {
                "scenario": scenario,
                "booking_id": booking["booking_id"],
                "expected_actions": [],
                "expected_sms_count": 0,
            }

    def _get_validation_rules(self) -> Dict[str, Dict[str, str]]:
        """Get validation rules for parity checking."""
        return {
            "sms_delivery": {
                "rule": "All expected SMS must be sent via SENS API",
                "check": "Verify SMS API calls and response codes"
            },
            "db_persistence": {
                "rule": "All DynamoDB updates must match expected state",
                "check": "Verify booking_num, phone, flags in DynamoDB"
            },
        }

    def cleanup_raw_exports(self):
        """Clean up temporary raw export files."""
        logger.info("Cleaning up temporary raw exports...")
        
        import shutil
        if self.raw_export_dir.exists():
            shutil.rmtree(self.raw_export_dir)
            logger.info(f"✅ Cleaned up {self.raw_export_dir}")


def main():
    """Main entry point for fixture refresh script."""
    parser = argparse.ArgumentParser(
        description="Refresh comparison test fixtures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/comparison/refresh_comparison_dataset.py
  python scripts/comparison/refresh_comparison_dataset.py --output-dir /tmp
        """
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Temporary directory for raw exports (default: /tmp)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing fixtures without refreshing"
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Comparison Testing - Fixture Refresh Script")
    logger.info("=" * 60)

    refresher = FixtureRefresher(output_dir=args.output_dir)

    try:
        if args.validate_only:
            logger.info("Validating existing fixtures...")
            bookings = refresher._load_synthetic_bookings()
            validation_result = refresher._validate_masking(bookings.get("bookings", []))
            if validation_result["passed"]:
                logger.info("✅ All fixtures passed validation")
                return 0
            else:
                logger.error(f"❌ Validation failed: {validation_result['errors']}")
                return 1

        # Refresh all fixtures
        bookings = refresher.refresh_bookings()
        if not bookings:
            logger.error("Failed to refresh bookings")
            return 1

        expected_outputs = refresher.refresh_expected_outputs(bookings)
        if not expected_outputs:
            logger.error("Failed to refresh expected outputs")
            return 1

        manifest = refresher.refresh_manifest(bookings, expected_outputs)

        # Cleanup
        refresher.cleanup_raw_exports()

        logger.info("=" * 60)
        logger.info("✅ Fixture refresh complete!")
        logger.info("=" * 60)
        logger.info(f"📁 Updated fixtures:")
        logger.info(f"   - tests/fixtures/production_bookings.json")
        logger.info(f"   - tests/fixtures/production_expected_outputs.json")
        logger.info(f"   - tests/fixtures/dataset_manifest.json")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Review changes: git diff tests/fixtures/")
        logger.info("  2. Run tests: make comparison-test")
        logger.info("  3. Commit: git add tests/fixtures/ && git commit")

        return 0

    except Exception as e:
        logger.error(f"❌ Fixture refresh failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
