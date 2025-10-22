"""
Automated Evidence Packaging

Story 5.5 BUS-001: Automates validation evidence collection and VALIDATION.md updates.

Validates that:
- All test reports collected and archived
- CloudWatch metrics exported
- Alarm logs captured
- Slack notification history gathered
- Evidence manifest generated
- VALIDATION.md automatically updated with links
- Completeness checker validates all sections present
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.validation.evidence import (
    EvidenceArtifact,
    EvidenceCollector,
    EvidencePackage,
    EvidencePackager,
)

logger = logging.getLogger(__name__)


class TestEvidenceCollection:
    """Tests for evidence collection."""

    def test_collector_collects_test_reports(self, tmp_path):
        """BUS-001: Collector gathers test report artifacts."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        # Create mock test reports
        json_report = campaign_dir / "booking_001.json"
        json_report.write_text('{"status": "PASS"}')

        md_report = campaign_dir / "booking_001.md"
        md_report.write_text("# Report\n\nTest passed.")

        collector = EvidenceCollector(campaign_dir)
        artifacts = collector.collect_test_reports()

        assert len(artifacts) == 2
        assert any(a.filename == "booking_001.json" for a in artifacts)
        assert any(a.filename == "booking_001.md" for a in artifacts)

    def test_collector_collects_aggregate_summary(self, tmp_path):
        """BUS-001: Collector gathers aggregate summary."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        # Create mock summary
        summary = campaign_dir / "SUMMARY.md"
        summary.write_text("# Summary\n\nAll tests passed.")

        collector = EvidenceCollector(campaign_dir)
        artifact = collector.collect_aggregate_summary()

        assert artifact is not None
        assert artifact.filename == "SUMMARY.md"

    def test_collector_generates_cloudwatch_export(self, tmp_path):
        """BUS-001: Collector generates CloudWatch metrics export."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        collector = EvidenceCollector(campaign_dir)
        artifact = collector.collect_cloudwatch_metrics_export()

        assert artifact is not None
        assert artifact.artifact_type == "metric_export"
        assert artifact.path.endswith("cloudwatch_metrics_export.json")

    def test_collector_generates_alarm_logs(self, tmp_path):
        """BUS-001: Collector generates alarm transition logs."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        collector = EvidenceCollector(campaign_dir)
        artifact = collector.collect_alarm_logs()

        assert artifact is not None
        assert artifact.artifact_type == "alarm_log"

    def test_collector_generates_slack_history(self, tmp_path):
        """BUS-001: Collector generates Slack notification history."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        collector = EvidenceCollector(campaign_dir)
        artifact = collector.collect_slack_history()

        assert artifact is not None
        assert artifact.artifact_type == "slack_history"


class TestEvidencePackaging:
    """Tests for evidence packaging."""

    def test_packager_creates_evidence_package(self, tmp_path):
        """BUS-001: Packager creates complete evidence package."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        # Create mock artifacts
        (campaign_dir / "booking_001.json").write_text('{"status": "PASS"}')
        (campaign_dir / "SUMMARY.md").write_text("# Summary")

        validation_md = tmp_path / "VALIDATION.md"
        validation_md.write_text("# Validation\n\n")

        packager = EvidencePackager(campaign_dir, validation_md)
        package = packager.package_evidence(
            campaign_id="test-campaign",
            readiness_report={"decision": "GO"},
        )

        assert package.campaign_id == "test-campaign"
        assert len(package.artifacts) > 0
        assert package.manifest["artifact_count"] == len(package.artifacts)

    def test_packager_validates_completeness(self, tmp_path):
        """BUS-001: Packager validates evidence completeness."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        validation_md = tmp_path / "VALIDATION.md"
        validation_md.write_text("# Validation\n\n")

        packager = EvidencePackager(campaign_dir, validation_md)
        package = packager.package_evidence(
            campaign_id="test-campaign",
            readiness_report={"decision": "GO"},
        )

        # Should have COMPLETE or WARNINGS status (has required artifacts)
        assert package.completeness_status in ["COMPLETE", "WARNINGS"]

    def test_packager_updates_validation_md(self, tmp_path):
        """BUS-001: Packager updates VALIDATION.md with evidence links."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        (campaign_dir / "booking_001.json").write_text('{"status": "PASS"}')

        validation_md = tmp_path / "VALIDATION.md"
        original_content = "# Validation Report\n\nInitial content.\n"
        validation_md.write_text(original_content)

        packager = EvidencePackager(campaign_dir, validation_md)
        package = packager.package_evidence(
            campaign_id="test-campaign",
            readiness_report={"decision": "GO"},
        )

        success = packager.update_validation_md(package)

        assert success
        assert validation_md.exists()

        # Verify content was appended
        with validation_md.open("r") as f:
            content = f.read()

        assert "test-campaign" in content
        assert "Evidence Artifacts" in content

    def test_evidence_package_serializes_to_json(self, tmp_path):
        """BUS-001: Evidence package serializes to valid JSON."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()

        validation_md = tmp_path / "VALIDATION.md"
        validation_md.write_text("# Validation\n\n")

        packager = EvidencePackager(campaign_dir, validation_md)
        package = packager.package_evidence(
            campaign_id="test-campaign",
            readiness_report={"decision": "GO"},
        )

        json_str = package.to_json()
        parsed = json.loads(json_str)

        assert parsed["campaign_id"] == "test-campaign"
        assert "artifacts" in parsed
        assert "manifest" in parsed
        assert "completeness_status" in parsed


class TestEvidenceIntegration:
    """Integration tests for evidence packaging workflow."""

    def test_full_evidence_packaging_workflow(self, tmp_path):
        """BUS-001: Full evidence collection and packaging workflow."""
        # Setup
        campaign_dir = tmp_path / "campaign" / "results"
        campaign_dir.mkdir(parents=True)

        validation_md = tmp_path / "VALIDATION.md"
        validation_md.write_text("# Validation Report\n\nCampaign execution results:\n\n")

        # Create mock artifacts
        (campaign_dir / "booking_001.json").write_text(
            json.dumps(
                {
                    "booking_id": "001",
                    "parity_status": "PASS",
                    "critical_mismatches": 0,
                }
            )
        )
        (campaign_dir / "SUMMARY.md").write_text("# Summary\n\n100% parity achieved.")

        # Execute packaging
        packager = EvidencePackager(campaign_dir, validation_md)

        readiness_report = {
            "campaign_id": "story-5.5-validation",
            "decision": "GO",
            "confidence": 1.0,
        }

        package = packager.package_evidence(
            campaign_id="story-5.5-validation",
            readiness_report=readiness_report,
        )

        # Update VALIDATION.md
        success = packager.update_validation_md(package)

        # Verify results
        assert success
        assert package.completeness_status in ["COMPLETE", "WARNINGS"]
        assert len(package.artifacts) >= 5

        # Verify VALIDATION.md updated
        with validation_md.open("r") as f:
            content = f.read()

        assert "story-5.5-validation" in content
        assert "Evidence Artifacts" in content
        assert "test_report" in content
