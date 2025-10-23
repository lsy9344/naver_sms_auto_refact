"""Diff Reporter - Generate structured comparison results and markdown summaries."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "tests" / "comparison" / "results"


@dataclass
class ComparisonMismatch:
    """Represents a single parity mismatch."""

    category: str
    field: str
    legacy_value: Any
    refactored_value: Any
    severity: str
    message: str


class DiffReporter:
    """Generate structured comparison artifacts (JSON + Markdown)."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir is not None else DEFAULT_RESULTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def compare_outputs(
        self,
        booking_id: str,
        canonical_legacy: Dict[str, Any],
        canonical_refactored: Dict[str, Any],
        expected_outputs: Dict[str, Any] | None = None,
    ) -> Tuple[List[ComparisonMismatch], Dict[str, Any]]:
        mismatches: List[ComparisonMismatch] = []

        sms_mismatches = self._compare_lists(
            "sms", canonical_legacy.get("sms", []), canonical_refactored.get("sms", [])
        )
        mismatches.extend(sms_mismatches)

        db_mismatches = self._compare_lists(
            "db_records",
            canonical_legacy.get("db_records", []),
            canonical_refactored.get("db_records", []),
        )
        mismatches.extend(db_mismatches)

        telegram_mismatches = self._compare_lists(
            "telegram",
            canonical_legacy.get("telegram", []),
            canonical_refactored.get("telegram", []),
        )
        mismatches.extend(telegram_mismatches)

        action_mismatches = self._compare_lists(
            "actions",
            canonical_legacy.get("actions", []),
            canonical_refactored.get("actions", []),
        )
        mismatches.extend(action_mismatches)

        slack_mismatches = self._compare_lists(
            "slack",
            canonical_legacy.get("slack", []),
            canonical_refactored.get("slack", []),
        )
        mismatches.extend(slack_mismatches)

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
        refactored_list: List[Dict[str, Any]],
    ) -> List[ComparisonMismatch]:
        mismatches: List[ComparisonMismatch] = []

        if len(legacy_list) != len(refactored_list):
            mismatches.append(
                ComparisonMismatch(
                    category=category,
                    field="count",
                    legacy_value=len(legacy_list),
                    refactored_value=len(refactored_list),
                    severity="critical",
                    message=f"Item count mismatch: {len(legacy_list)} vs {len(refactored_list)}",
                )
            )

        for index, (legacy_item, refactored_item) in enumerate(zip(legacy_list, refactored_list)):
            if isinstance(legacy_item, dict) and isinstance(refactored_item, dict):
                mismatches.extend(
                    self._compare_dicts(category, index, legacy_item, refactored_item)
                )

        return mismatches

    def _compare_dicts(
        self,
        category: str,
        index: int,
        legacy_dict: Dict[str, Any],
        refactored_dict: Dict[str, Any],
    ) -> List[ComparisonMismatch]:
        mismatches: List[ComparisonMismatch] = []
        all_keys = set(legacy_dict.keys()) | set(refactored_dict.keys())

        for key in all_keys:
            legacy_value = legacy_dict.get(key)
            refactored_value = refactored_dict.get(key)

            if legacy_value != refactored_value:
                critical_fields = ["phone", "booking_num", "action_type", "success"]
                severity = "critical" if key in critical_fields else "warning"
                mismatches.append(
                    ComparisonMismatch(
                        category=category,
                        field=f"[{index}].{key}",
                        legacy_value=legacy_value,
                        refactored_value=refactored_value,
                        severity=severity,
                        message=f"Field mismatch: {key} = {legacy_value} vs {refactored_value}",
                    )
                )

        return mismatches

    def generate_json_report(
        self,
        booking_id: str,
        mismatches: List[ComparisonMismatch],
        stats: Dict[str, Any],
        canonical_legacy: Dict[str, Any] | None = None,
        canonical_refactored: Dict[str, Any] | None = None,
    ) -> str:
        report = {
            "metadata": {
                "booking_id": booking_id,
                "generated_at": datetime.now().isoformat(),
            },
            "statistics": stats,
            "mismatches": [asdict(mismatch) for mismatch in mismatches],
        }

        if canonical_legacy is not None:
            report["legacy_output"] = canonical_legacy
        if canonical_refactored is not None:
            report["refactored_output"] = canonical_refactored

        return json.dumps(report, indent=2, default=str)

    def generate_markdown_summary(
        self,
        booking_id: str,
        scenario: str,
        mismatches: List[ComparisonMismatch],
        stats: Dict[str, Any],
    ) -> str:
        md_lines = [
            f"# Comparison Report: {booking_id}",
            f"**Scenario:** {scenario}",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Summary",
            f"- **Total Mismatches:** {stats['total_mismatches']}",
            f"- **Critical:** {stats['critical_mismatches']} 🚨",
            f"- **Warnings:** {stats['warning_mismatches']} ⚠️",
            f"- **Parity Status:** {stats['parity_status']}",
            "",
        ]

        if mismatches:
            md_lines.append("## Detailed Mismatches")
            md_lines.append("")
            for mismatch in mismatches:
                md_lines.append(
                    f"- **{mismatch.category.upper()}** {mismatch.field}: {mismatch.message}"
                )
        else:
            md_lines.append("Perfect Parity ✅")

        md_lines.extend(
            [
                "",
                "---",
                "*Generated by Comparison Testing Framework v1.0*",
            ]
        )

        return "\n".join(md_lines)

    def write_reports(
        self,
        booking_id: str,
        scenario: str,
        mismatches: List[ComparisonMismatch],
        stats: Dict[str, Any],
        canonical_legacy: Dict[str, Any] | None = None,
        canonical_refactored: Dict[str, Any] | None = None,
    ) -> Tuple[Path, Path]:
        json_report = self.generate_json_report(
            booking_id, mismatches, stats, canonical_legacy, canonical_refactored
        )
        markdown_report = self.generate_markdown_summary(booking_id, scenario, mismatches, stats)

        safe_booking_id = booking_id.replace("/", "_")
        json_path = self.output_dir / f"{safe_booking_id}.json"
        md_path = self.output_dir / f"{safe_booking_id}.md"

        json_path.write_text(json_report, encoding="utf-8")
        md_path.write_text(markdown_report, encoding="utf-8")

        logger.info("Wrote comparison reports for %s", booking_id)
        logger.info("  JSON: %s", json_path)
        logger.info("  Markdown: %s", md_path)

        return json_path, md_path

    def generate_aggregate_summary(self, all_stats: List[Dict[str, Any]]) -> str:
        total_bookings = len(all_stats)
        passed = sum(1 for stat in all_stats if stat["parity_status"] == "PASS")
        failed = total_bookings - passed
        total_critical = sum(stat["critical_mismatches"] for stat in all_stats)
        total_warnings = sum(stat["warning_mismatches"] for stat in all_stats)

        md_lines = [
            "# Comparison Testing - Aggregate Summary",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Overall Results",
            f"- **Total Bookings Tested:** {total_bookings}",
            f"- **Passed:** {passed} ✅",
            f"- **Failed:** {failed} ❌",
            f"- **Pass Rate:** {(passed / total_bookings * 100):.1f}%",
            "",
            "## Mismatch Summary",
            f"- **Critical Mismatches:** {total_critical} 🚨",
            f"- **Warnings:** {total_warnings} ⚠️",
            "",
            "## Detailed Results",
            "",
        ]

        for stat in sorted(all_stats, key=lambda item: item["booking_id"]):
            status_emoji = "✅" if stat["parity_status"] == "PASS" else "❌"
            md_lines.append(
                f"{status_emoji} **{stat['booking_id']}** (Critical: {stat['critical_mismatches']}, "
                f"Warnings: {stat['warning_mismatches']})"
            )

        md_lines.extend(
            [
                "",
                "---",
                "*Comparison Testing Framework v1.0*",
            ]
        )

        return "\n".join(md_lines)

    def write_aggregate_summary(self, all_stats: List[Dict[str, Any]]) -> Path:
        summary = self.generate_aggregate_summary(all_stats)
        summary_path = self.output_dir / "SUMMARY.md"
        summary_path.write_text(summary, encoding="utf-8")
        logger.info("Wrote aggregate summary: %s", summary_path)
        return summary_path
