"""Evidence collection and packaging utilities for validation campaigns."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EvidenceArtifact:
    """Individual evidence artifact."""

    artifact_type: str
    filename: str
    description: str
    timestamp: str
    path: str
    size_bytes: int
    checksum: str


@dataclass
class EvidencePackage:
    """Complete validation evidence package."""

    campaign_id: str
    generated_at: str
    artifacts: List[EvidenceArtifact]
    manifest: Dict[str, Any]
    validation_md_updated: bool
    completeness_status: str
    completeness_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "generated_at": self.generated_at,
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
            "manifest": self.manifest,
            "validation_md_updated": self.validation_md_updated,
            "completeness_status": self.completeness_status,
            "completeness_notes": self.completeness_notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class EvidenceCollector:
    """Collects validation evidence artifacts."""

    def __init__(self, campaign_dir: Path):
        self.campaign_dir = Path(campaign_dir)
        self.logger = logging.getLogger(__name__)

    def collect_test_reports(self) -> List[EvidenceArtifact]:
        artifacts: List[EvidenceArtifact] = []

        for json_file in self.campaign_dir.glob("*.json"):
            if json_file.name == "campaign_metadata.json":
                continue
            artifacts.append(
                self._build_artifact(json_file, "test_report", "Comparison test result")
            )

        for md_file in self.campaign_dir.glob("*.md"):
            if md_file.name == "SUMMARY.md":
                continue
            artifacts.append(self._build_artifact(md_file, "test_report", "Comparison summary"))

        return artifacts

    def collect_aggregate_summary(self) -> Optional[EvidenceArtifact]:
        summary_path = self.campaign_dir / "SUMMARY.md"
        if not summary_path.exists():
            return None
        return self._build_artifact(
            summary_path, "test_report", "Aggregate validation campaign summary"
        )

    def collect_readiness_report(self, readiness_report: Dict[str, Any]) -> EvidenceArtifact:
        report_path = self.campaign_dir / "readiness_report.json"
        if not report_path.exists():
            with report_path.open("w", encoding="utf-8") as file:
                json.dump(readiness_report, file, indent=2, default=str)
        return self._build_artifact(
            report_path, "readiness_report", "Automated readiness gate validation report"
        )

    def collect_cloudwatch_metrics_export(self) -> Optional[EvidenceArtifact]:
        metrics_path = self.campaign_dir / "cloudwatch_metrics_export.json"
        if not metrics_path.exists():
            self.logger.warning(
                f"CloudWatch metrics export not found: {metrics_path}. "
                "Run a real validation campaign to generate this artifact."
            )
            return None
        return self._build_artifact(
            metrics_path, "metric_export", "CloudWatch metrics snapshot during validation campaign"
        )

    def collect_alarm_logs(self) -> Optional[EvidenceArtifact]:
        alarms_path = self.campaign_dir / "cloudwatch_alarm_logs.json"
        if not alarms_path.exists():
            self.logger.warning(
                f"CloudWatch alarm logs not found: {alarms_path}. "
                "Run a real validation campaign to generate this artifact."
            )
            return None
        return self._build_artifact(
            alarms_path, "alarm_log", "CloudWatch alarm transition history during campaign"
        )

    def collect_slack_history(self) -> Optional[EvidenceArtifact]:
        slack_path = self.campaign_dir / "slack_notification_history.json"
        if not slack_path.exists():
            self.logger.warning(
                f"Slack notification history not found: {slack_path}. "
                "Run a real validation campaign to generate this artifact."
            )
            return None
        return self._build_artifact(
            slack_path, "slack_history", "Slack webhook notification delivery history"
        )

    def _build_artifact(
        self, file_path: Path, artifact_type: str, default_description: str
    ) -> EvidenceArtifact:
        description = default_description
        if default_description == "Comparison test result":
            description = f"Comparison test result for {file_path.stem}"
        elif default_description == "Comparison summary":
            description = f"Comparison summary for {file_path.stem}"

        return EvidenceArtifact(
            artifact_type=artifact_type,
            filename=file_path.name,
            description=description,
            timestamp=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            path=str(file_path),
            size_bytes=file_path.stat().st_size,
            checksum=self._calculate_checksum(file_path),
        )

    @staticmethod
    def _calculate_checksum(file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as file:
            for byte_block in iter(lambda: file.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]


class EvidencePackager:
    """Packages evidence and updates VALIDATION.md."""

    def __init__(self, campaign_dir: Path, validation_md_path: Path):
        self.campaign_dir = Path(campaign_dir)
        self.validation_md_path = Path(validation_md_path)
        self.collector = EvidenceCollector(campaign_dir)
        self.logger = logging.getLogger(__name__)

    def package_evidence(
        self, campaign_id: str, readiness_report: Dict[str, Any]
    ) -> EvidencePackage:
        artifacts: List[EvidenceArtifact] = []

        artifacts.extend(self.collector.collect_test_reports())

        summary = self.collector.collect_aggregate_summary()
        if summary:
            artifacts.append(summary)

        readiness = self.collector.collect_readiness_report(readiness_report)
        artifacts.append(readiness)

        metrics = self.collector.collect_cloudwatch_metrics_export()
        if metrics:
            artifacts.append(metrics)

        alarms = self.collector.collect_alarm_logs()
        if alarms:
            artifacts.append(alarms)

        slack = self.collector.collect_slack_history()
        if slack:
            artifacts.append(slack)

        manifest = {
            "campaign_id": campaign_id,
            "generated_at": datetime.utcnow().isoformat(),
            "artifact_count": len(artifacts),
            "by_type": self._group_artifacts_by_type(artifacts),
            "total_size_bytes": sum(artifact.size_bytes for artifact in artifacts),
        }

        completeness_status, completeness_notes = self._validate_completeness(artifacts)

        return EvidencePackage(
            campaign_id=campaign_id,
            generated_at=datetime.utcnow().isoformat(),
            artifacts=artifacts,
            manifest=manifest,
            validation_md_updated=False,
            completeness_status=completeness_status,
            completeness_notes=completeness_notes,
        )

    def update_validation_md(self, evidence_package: EvidencePackage) -> bool:
        if not self.validation_md_path.exists():
            self.logger.warning("VALIDATION.md not found at %s", self.validation_md_path)
            return False

        existing_content = self.validation_md_path.read_text(encoding="utf-8")
        evidence_section = self._generate_evidence_section(evidence_package)
        updated_content = f"{existing_content}\n\n{evidence_section}"
        self.validation_md_path.write_text(updated_content, encoding="utf-8")
        self.logger.info("Updated VALIDATION.md with evidence links")
        return True

    @staticmethod
    def _group_artifacts_by_type(artifacts: List[EvidenceArtifact]) -> Dict[str, int]:
        grouped: Dict[str, int] = {}
        for artifact in artifacts:
            grouped[artifact.artifact_type] = grouped.get(artifact.artifact_type, 0) + 1
        return grouped

    def _validate_completeness(self, artifacts: List[EvidenceArtifact]) -> Tuple[str, List[str]]:
        required_types = [
            "test_report",
            "readiness_report",
            "metric_export",
            "alarm_log",
            "slack_history",
        ]

        artifact_types = {artifact.artifact_type for artifact in artifacts}
        notes: List[str] = []

        missing_types = [
            artifact_type for artifact_type in required_types if artifact_type not in artifact_types
        ]

        if not missing_types:
            status = "COMPLETE"
        elif len(missing_types) <= 2:
            status = "WARNINGS"
            notes.extend(f"Missing artifact type: {missing}" for missing in missing_types)
        else:
            status = "INCOMPLETE"
            notes.extend(f"Missing artifact type: {missing}" for missing in missing_types)

        test_reports = [
            artifact for artifact in artifacts if artifact.artifact_type == "test_report"
        ]
        if len(test_reports) < 2:
            status = "WARNINGS"
            notes.append("Few test reports collected")

        return status, notes

    @staticmethod
    def _generate_evidence_section(evidence_package: EvidencePackage) -> str:
        lines: List[str] = [
            "---",
            "",
            f"# Validation Campaign: {evidence_package.campaign_id}",
            "",
            f"**Generated**: {evidence_package.generated_at}",
            f"**Completeness**: {evidence_package.completeness_status}",
            "",
            "## Evidence Artifacts",
            "",
        ]

        by_type: Dict[str, List[EvidenceArtifact]] = {}
        for artifact in evidence_package.artifacts:
            by_type.setdefault(artifact.artifact_type, []).append(artifact)

        for artifact_type in sorted(by_type.keys()):
            artifacts = by_type[artifact_type]
            readable_name = artifact_type.replace("_", " ").title()
            lines.append(f"### {readable_name} ({artifact_type})")
            lines.append("")
            lines.append("| Artifact | Description | Timestamp |")
            lines.append("|----------|-------------|-----------|")

            for artifact in artifacts:
                try:
                    rel_path = Path(artifact.path).relative_to(Path.cwd())
                except ValueError:
                    rel_path = Path(artifact.path)

                lines.append(
                    f"| [{artifact.filename}]({rel_path}) | {artifact.description} | {artifact.timestamp} |"
                )

            lines.append("")

        lines.append("## Evidence Manifest")
        lines.append("")
        lines.append(f"- **Total Artifacts**: {len(evidence_package.artifacts)}")
        lines.append(f"- **Total Size**: {evidence_package.manifest['total_size_bytes']:,} bytes")
        lines.append(f"- **Campaign ID**: {evidence_package.campaign_id}")
        lines.append("")

        if evidence_package.completeness_notes:
            lines.append("## Completeness Notes")
            lines.append("")
            lines.extend(f"- {note}" for note in evidence_package.completeness_notes)
            lines.append("")

        return "\n".join(lines)
