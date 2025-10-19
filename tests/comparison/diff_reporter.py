"""
Diff Reporter - Generate structured comparison results and markdown summaries

Story 4.2 Task 2: Implements AC 3 (Framework emits structured artifacts)
"""

import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ComparisonMismatch:
    """Represents a single parity mismatch"""
    
    category: str  # "sms", "db_records", "telegram", "actions"
    field: str
    legacy_value: Any
    refactored_value: Any
    severity: str  # "critical", "warning"
    message: str


class DiffReporter:
    """
    Generate structured comparison artifacts (JSON + Markdown).
    
    Responsibilities:
    - Compare canonical outputs field-by-field
    - Generate JSON diff artifacts
    - Generate markdown summary with mismatch highlighting
    - Calculate statistics and severity levels
    """

    def __init__(self, output_dir: Path = None):
        """
        Initialize reporter.
        
        Args:
            output_dir: Directory for writing comparison results
        """
        if output_dir is None:
            output_dir = (
                Path(__file__).resolve().parents[1] / "comparison" / "results"
            )
        
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def compare_outputs(
        self,
        booking_id: str,
        canonical_legacy: Dict[str, Any],
        canonical_refactored: Dict[str, Any],
        expected_outputs: Dict[str, Any] = None
    ) -> Tuple[List[ComparisonMismatch], Dict[str, Any]]:
        """
        Compare canonical outputs from both implementations.
        
        Args:
            booking_id: ID of the booking being compared
            canonical_legacy: Canonical legacy output
            canonical_refactored: Canonical refactored output
            expected_outputs: Expected outputs for reference
            
        Returns:
            Tuple of (mismatches, stats)
        """
        mismatches: List[ComparisonMismatch] = []

        # Compare SMS outputs
        sms_mismatches = self._compare_lists(
            "sms",
            canonical_legacy.get("sms", []),
            canonical_refactored.get("sms", [])
        )
        mismatches.extend(sms_mismatches)

        # Compare DB records
        db_mismatches = self._compare_lists(
            "db_records",
            canonical_legacy.get("db_records", []),
            canonical_refactored.get("db_records", [])
        )
        mismatches.extend(db_mismatches)

        # Compare Telegram outputs
        telegram_mismatches = self._compare_lists(
            "telegram",
            canonical_legacy.get("telegram", []),
            canonical_refactored.get("telegram", [])
        )
        mismatches.extend(telegram_mismatches)

        # Compare action results
        action_mismatches = self._compare_lists(
            "actions",
            canonical_legacy.get("actions", []),
            canonical_refactored.get("actions", [])
        )
        mismatches.extend(action_mismatches)

        # Calculate statistics
        stats = {
            "booking_id": booking_id,
            "total_mismatches": len(mismatches),
            "critical_mismatches": len([m for m in mismatches if m.severity == "critical"]),
            "warning_mismatches": len([m for m in mismatches if m.severity == "warning"]),
            "parity_status": "PASS" if len(mismatches) == 0 else "FAIL",
            "timestamp": datetime.now().isoformat(),
        }

        return mismatches, stats

    def _compare_lists(
        self,
        category: str,
        legacy_list: List[Dict[str, Any]],
        refactored_list: List[Dict[str, Any]]
    ) -> List[ComparisonMismatch]:
        """
        Compare two lists of items (SMS, DB records, etc).
        
        Args:
            category: Category name (sms, db_records, etc)
            legacy_list: List from legacy implementation
            refactored_list: List from refactored implementation
            
        Returns:
            List of mismatches
        """
        mismatches: List[ComparisonMismatch] = []

        # Check list length
        if len(legacy_list) != len(refactored_list):
            mismatches.append(
                ComparisonMismatch(
                    category=category,
                    field="count",
                    legacy_value=len(legacy_list),
                    refactored_value=len(refactored_list),
                    severity="critical",
                    message=f"Item count mismatch: {len(legacy_list)} vs {len(refactored_list)}"
                )
            )

        # Compare each item
        for i, (legacy_item, refactored_item) in enumerate(
            zip(legacy_list, refactored_list)
        ):
            if isinstance(legacy_item, dict) and isinstance(refactored_item, dict):
                item_mismatches = self._compare_dicts(
                    category, i, legacy_item, refactored_item
                )
                mismatches.extend(item_mismatches)

        return mismatches

    def _compare_dicts(
        self,
        category: str,
        index: int,
        legacy_dict: Dict[str, Any],
        refactored_dict: Dict[str, Any]
    ) -> List[ComparisonMismatch]:
        """
        Compare two dictionaries field by field.
        
        Args:
            category: Category name
            index: Index in list
            legacy_dict: Dict from legacy
            refactored_dict: Dict from refactored
            
        Returns:
            List of field mismatches
        """
        mismatches: List[ComparisonMismatch] = []

        all_keys = set(legacy_dict.keys()) | set(refactored_dict.keys())

        for key in all_keys:
            legacy_value = legacy_dict.get(key)
            refactored_value = refactored_dict.get(key)

            if legacy_value != refactored_value:
                # Determine severity
                critical_fields = ["phone", "booking_num", "action_type", "success"]
                severity = "critical" if key in critical_fields else "warning"

                mismatches.append(
                    ComparisonMismatch(
                        category=category,
                        field=f"[{index}].{key}",
                        legacy_value=legacy_value,
                        refactored_value=refactored_value,
                        severity=severity,
                        message=f"Field mismatch: {key} = {legacy_value} vs {refactored_value}"
                    )
                )

        return mismatches

    def generate_json_report(
        self,
        booking_id: str,
        mismatches: List[ComparisonMismatch],
        stats: Dict[str, Any],
        canonical_legacy: Dict[str, Any] = None,
        canonical_refactored: Dict[str, Any] = None,
        container_digest: str = None,
        dataset_version: str = "1.0"
    ) -> str:
        """
        Generate JSON report for a booking comparison.

        Args:
            booking_id: ID of booking
            mismatches: List of mismatches
            stats: Statistics dict
            canonical_legacy: Legacy canonical output (optional)
            canonical_refactored: Refactored canonical output (optional)
            container_digest: Docker container SHA256 digest (optional)
            dataset_version: Version of test dataset (optional)

        Returns:
            JSON string
        """
        report = {
            "metadata": {
                "booking_id": booking_id,
                "generated_at": datetime.now().isoformat(),
                "version": "1.0",
                "container_digest": container_digest or "local-development",
                "dataset_version": dataset_version,
                "parity_run_timestamp": datetime.now().isoformat(),
            },
            "statistics": stats,
            "mismatches": [asdict(m) for m in mismatches],
            "canonical_outputs": {
                "legacy": canonical_legacy or {},
                "refactored": canonical_refactored or {},
            }
        }

        return json.dumps(report, indent=2, default=str)

    def generate_markdown_summary(
        self,
        booking_id: str,
        scenario: str,
        mismatches: List[ComparisonMismatch],
        stats: Dict[str, Any]
    ) -> str:
        """
        Generate markdown summary with mismatch highlighting.
        
        Args:
            booking_id: ID of booking
            scenario: Scenario description
            mismatches: List of mismatches
            stats: Statistics dict
            
        Returns:
            Markdown string
        """
        md_lines = [
            f"# Comparison Report: {booking_id}",
            f"**Scenario:** {scenario}",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Status",
            f"**Parity Status:** {stats['parity_status']}",
            f"**Total Mismatches:** {stats['total_mismatches']}",
            f"  - Critical: {stats['critical_mismatches']}",
            f"  - Warnings: {stats['warning_mismatches']}",
            "",
        ]

        if len(mismatches) == 0:
            md_lines.extend([
                "## Result",
                "✅ **Perfect Parity** - Legacy and refactored implementations match!",
            ])
        else:
            md_lines.extend([
                "## Mismatches",
                "",
            ])

            # Group by category
            by_category = {}
            for mismatch in mismatches:
                if mismatch.category not in by_category:
                    by_category[mismatch.category] = []
                by_category[mismatch.category].append(mismatch)

            for category in sorted(by_category.keys()):
                items = by_category[category]
                md_lines.append(f"### {category.upper()}")
                md_lines.append("")

                for item in items:
                    severity_emoji = "🚨" if item.severity == "critical" else "⚠️"
                    md_lines.append(
                        f"{severity_emoji} **{item.field}** [{item.severity.upper()}]"
                    )
                    md_lines.append(f"  - Legacy: `{item.legacy_value}`")
                    md_lines.append(f"  - Refactored: `{item.refactored_value}`")
                    md_lines.append(f"  - {item.message}")
                    md_lines.append("")

        md_lines.extend([
            "",
            "---",
            f"*Generated by Comparison Testing Framework v1.0*",
        ])

        return "\n".join(md_lines)

    def write_reports(
        self,
        booking_id: str,
        scenario: str,
        mismatches: List[ComparisonMismatch],
        stats: Dict[str, Any],
        canonical_legacy: Dict[str, Any] = None,
        canonical_refactored: Dict[str, Any] = None
    ) -> Tuple[Path, Path]:
        """
        Write both JSON and Markdown reports to disk.
        
        Args:
            booking_id: ID of booking
            scenario: Scenario description
            mismatches: List of mismatches
            stats: Statistics dict
            canonical_legacy: Legacy outputs (optional)
            canonical_refactored: Refactored outputs (optional)
            
        Returns:
            Tuple of (json_path, markdown_path)
        """
        # Generate reports
        json_report = self.generate_json_report(
            booking_id, mismatches, stats, canonical_legacy, canonical_refactored
        )
        markdown_report = self.generate_markdown_summary(
            booking_id, scenario, mismatches, stats
        )

        # Write files
        safe_booking_id = booking_id.replace("/", "_")
        json_path = self.output_dir / f"{safe_booking_id}.json"
        md_path = self.output_dir / f"{safe_booking_id}.md"

        with json_path.open("w", encoding="utf-8") as f:
            f.write(json_report)

        with md_path.open("w", encoding="utf-8") as f:
            f.write(markdown_report)

        logger.info(f"Wrote comparison reports for {booking_id}")
        logger.info(f"  JSON: {json_path}")
        logger.info(f"  Markdown: {md_path}")

        return json_path, md_path

    def generate_aggregate_summary(
        self,
        all_stats: List[Dict[str, Any]]
    ) -> str:
        """
        Generate aggregate summary across all bookings.
        
        Args:
            all_stats: List of stats dicts from all comparisons
            
        Returns:
            Markdown summary string
        """
        total_bookings = len(all_stats)
        passed = sum(1 for s in all_stats if s["parity_status"] == "PASS")
        failed = total_bookings - passed
        total_critical = sum(s["critical_mismatches"] for s in all_stats)
        total_warnings = sum(s["warning_mismatches"] for s in all_stats)

        md_lines = [
            "# Comparison Testing - Aggregate Summary",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Overall Results",
            f"- **Total Bookings Tested:** {total_bookings}",
            f"- **Passed:** {passed} ✅",
            f"- **Failed:** {failed} ❌",
            f"- **Pass Rate:** {(passed/total_bookings*100):.1f}%",
            "",
            "## Mismatch Summary",
            f"- **Critical Mismatches:** {total_critical} 🚨",
            f"- **Warnings:** {total_warnings} ⚠️",
            "",
            "## Detailed Results",
            "",
        ]

        # Add pass/fail by booking
        for stat in sorted(all_stats, key=lambda s: s["booking_id"]):
            status_emoji = "✅" if stat["parity_status"] == "PASS" else "❌"
            md_lines.append(
                f"{status_emoji} **{stat['booking_id']}** "
                f"(Critical: {stat['critical_mismatches']}, "
                f"Warnings: {stat['warning_mismatches']})"
            )

        md_lines.extend([
            "",
            "---",
            f"*Comparison Testing Framework v1.0*",
        ])

        return "\n".join(md_lines)

    def write_aggregate_summary(self, all_stats: List[Dict[str, Any]]) -> Path:
        """
        Write aggregate summary to disk.
        
        Args:
            all_stats: List of stats from all comparisons
            
        Returns:
            Path to written file
        """
        summary = self.generate_aggregate_summary(all_stats)
        summary_path = self.output_dir / "SUMMARY.md"

        with summary_path.open("w", encoding="utf-8") as f:
            f.write(summary)

        logger.info(f"Wrote aggregate summary: {summary_path}")
        return summary_path
