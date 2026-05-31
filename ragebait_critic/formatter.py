"""
Report formatting for Ragebait Critic.

The canonical output is AuditReport JSON. Markdown is a rendered view for humans.
"""

from __future__ import annotations

import json

from ragebait_critic.exceptions import FormattingError
from ragebait_critic.schemas import AuditReport, Finding, FormattedReport


class ReportFormatter:
    """
    Converts AuditReport objects into Markdown or JSON strings.
    """

    def format(self, report: AuditReport, output_format: str = "markdown") -> FormattedReport:
        normalized = output_format.lower().strip()

        if normalized == "json":
            return FormattedReport(
                report=report,
                markdown=None,
                json_text=self.to_json(report),
            )

        if normalized == "markdown":
            return FormattedReport(
                report=report,
                markdown=self.to_markdown(report),
                json_text=None,
            )

        raise FormattingError(
            f"Unsupported output format: {output_format}. Allowed values: markdown, json."
        )

    def to_json(self, report: AuditReport) -> str:
        return json.dumps(
            report.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        )

    def to_markdown(self, report: AuditReport) -> str:
        try:
            sections = [
                self._header(report),
                self._verdict(report),
                self._project_audit(report),
                self._architecture_review(report),
                self._findings(report),
                self._priority_actions(report),
                self._blind_spots(report),
                self._final_roast(report),
            ]

            return "\n\n".join(section for section in sections if section.strip()).strip()

        except Exception as exc:
            raise FormattingError(f"Failed to format report as Markdown: {exc}") from exc

    def _header(self, report: AuditReport) -> str:
        meta = report.meta

        lines = [
            "# Ragebait Critic Audit Report",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Domain | `{meta.domain}` |",
            f"| Language | `{meta.language}` |",
            f"| Intensity | `{meta.intensity}` |",
            f"| Roast Style | `{meta.roast_style}` |",
            f"| Model | `{meta.model}` |",
            f"| Input Type | `{meta.input_type}` |",
        ]

        if meta.source.name:
            lines.append(f"| Source | `{meta.source.name}` |")

        if meta.source.path:
            lines.append(f"| Path | `{meta.source.path}` |")

        if meta.source.url:
            lines.append(f"| URL | `{meta.source.url}` |")

        if meta.source.file_count is not None:
            lines.append(f"| File Count | `{meta.source.file_count}` |")

        if meta.source.truncated:
            lines.append("| Truncated | `true` |")

        return "\n".join(lines)

    def _verdict(self, report: AuditReport) -> str:
        verdict = report.verdict

        return "\n".join(
            [
                "## Verdict",
                "",
                f"**Score:** `{verdict.score}/100`",
                "",
                f"**{verdict.rage_title}**",
                "",
                verdict.summary,
            ]
        )

    def _project_audit(self, report: AuditReport) -> str:
        if report.project_audit is None:
            return ""

        audit = report.project_audit
        hygiene = audit.repository_hygiene

        lines = [
            "## Project Audit",
            "",
            f"**Project Type:** `{audit.project_type}`",
            f"**Readiness:** `{audit.readiness}`",
            f"**Architecture Score:** `{audit.architecture_score}/100`",
            "",
            "### Detected Stack",
        ]

        if audit.detected_stack:
            lines.extend(f"- {item}" for item in audit.detected_stack)
        else:
            lines.append("- Unknown")

        lines.extend(
            [
                "",
                "### Repository Hygiene",
                "",
                "| Signal | Present |",
                "|---|---|",
                f"| README | `{hygiene.has_readme}` |",
                f"| Tests | `{hygiene.has_tests}` |",
                f"| .env.example | `{hygiene.has_env_example}` |",
                f"| CI | `{hygiene.has_ci}` |",
                f"| License | `{hygiene.has_license}` |",
                f"| Dockerfile | `{hygiene.has_dockerfile}` |",
                f"| Dependency File | `{hygiene.has_dependency_file}` |",
                "",
                "### Critical Missing Pieces",
            ]
        )

        if audit.critical_missing_pieces:
            lines.extend(f"- {item}" for item in audit.critical_missing_pieces)
        else:
            lines.append("- None detected")

        return "\n".join(lines)

    def _architecture_review(self, report: AuditReport) -> str:
        if report.architecture_review is None:
            return ""

        review = report.architecture_review

        lines = [
            "## Architecture Review",
            "",
            f"**Boundary Strength:** `{review.strength_of_boundaries}`",
            "",
            review.summary or "No architecture summary provided.",
            "",
            "### Missing Layers",
        ]

        if review.missing_layers:
            lines.extend(f"- {item}" for item in review.missing_layers)
        else:
            lines.append("- None detected")

        return "\n".join(lines)

    def _findings(self, report: AuditReport) -> str:
        if not report.findings:
            return "\n".join(
                [
                    "## Findings",
                    "",
                    "No concrete findings were returned. That usually means the model "
                    "failed to do its job properly.",
                ]
            )

        lines = ["## Findings"]

        severity_order = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
            "nitpick": 4,
        }

        sorted_findings = sorted(
            report.findings,
            key=lambda finding: (
                severity_order.get(finding.severity, 99),
                finding.id,
            ),
        )

        for finding in sorted_findings:
            lines.extend(self._finding_block(finding, report.meta.roast_style))

        return "\n".join(lines)

    def _finding_block(self, finding: Finding, roast_style: str) -> list[str]:
        lines = [
            "",
            f"### {finding.id} — {finding.severity.upper()} — {finding.category}",
            "",
        ]

        if finding.location:
            lines.append(f"**Location:** `{finding.location}`")
            lines.append("")

        lines.extend(
            [
                "**Evidence**",
                "",
                self._quote_or_text(finding.evidence),
                "",
                "**Problem**",
                "",
                finding.problem,
                "",
                "**Rage Comment**",
                "",
                f"> {finding.rage_comment}",
            ]
        )

        if roast_style == "bully" and finding.bully_comment:
            lines.extend(
                [
                    "",
                    "**Bully Comment**",
                    "",
                    f"> {finding.bully_comment}",
                ]
            )

        lines.extend(
            [
                "",
                "**Impact**",
                "",
                finding.impact,
                "",
                "**Recommendation**",
                "",
                finding.recommendation,
                "",
                f"**Effort:** `{finding.effort}`",
            ]
        )

        return lines

    def _priority_actions(self, report: AuditReport) -> str:
        if not report.priority_actions:
            return ""

        lines = ["## Priority Actions"]

        for action in sorted(report.priority_actions, key=lambda item: item.rank):
            lines.extend(
                [
                    "",
                    f"### {action.rank}. {action.action}",
                    "",
                    action.reason,
                ]
            )

        return "\n".join(lines)

    def _blind_spots(self, report: AuditReport) -> str:
        if not report.blind_spots:
            return ""

        lines = ["## Blind Spots", ""]
        lines.extend(f"- {item}" for item in report.blind_spots)

        return "\n".join(lines)

    def _final_roast(self, report: AuditReport) -> str:
        return "\n".join(
            [
                "## Final Roast",
                "",
                f"> {report.final_roast}",
            ]
        )

    def _quote_or_text(self, value: str) -> str:
        cleaned = value.strip()

        if "\n" in cleaned:
            return f"```text\n{cleaned}\n```"

        return cleaned


def format_report(report: AuditReport, output_format: str = "markdown") -> FormattedReport:
    """
    Convenience function for one-off report formatting.
    """
    return ReportFormatter().format(report, output_format=output_format)


def report_to_json(report: AuditReport) -> str:
    """
    Convenience function for JSON rendering.
    """
    return ReportFormatter().to_json(report)


def report_to_markdown(report: AuditReport) -> str:
    """
    Convenience function for Markdown rendering.
    """
    return ReportFormatter().to_markdown(report)
