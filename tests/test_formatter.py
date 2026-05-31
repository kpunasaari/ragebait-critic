from __future__ import annotations

from ragebait_critic.formatter import ReportFormatter
from ragebait_critic.output_parser import OutputParser


def test_markdown_formatter(valid_audit_json: str) -> None:
    report = OutputParser().parse(valid_audit_json)
    formatted = ReportFormatter().format(report, output_format="markdown")

    assert formatted.markdown is not None
    assert "# Ragebait Critic Audit Report" in formatted.markdown
    assert "## Verdict" in formatted.markdown
    assert "F001" in formatted.markdown


def test_json_formatter(valid_audit_json: str) -> None:
    report = OutputParser().parse(valid_audit_json)
    formatted = ReportFormatter().format(report, output_format="json")

    assert formatted.json_text is not None
    assert '"domain": "code"' in formatted.json_text
    assert formatted.markdown is None