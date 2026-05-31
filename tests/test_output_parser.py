from __future__ import annotations

import pytest

from ragebait_critic.exceptions import OutputParsingError, SchemaValidationError
from ragebait_critic.output_parser import OutputParser


def test_parse_valid_audit_json(valid_audit_json: str) -> None:
    report = OutputParser().parse(valid_audit_json)

    assert report.meta.domain == "code"
    assert report.verdict.score == 35
    assert len(report.findings) == 1


def test_parse_fenced_json(valid_audit_json: str) -> None:
    raw = f"```json\n{valid_audit_json}\n```"

    report = OutputParser().parse(raw)

    assert report.meta.domain == "code"
    assert report.findings[0].id == "F001"


def test_rejects_non_json_output() -> None:
    with pytest.raises(OutputParsingError):
        OutputParser().parse("This is not JSON.")


def test_rejects_bully_comment_when_roast_style_none(valid_audit_json: str) -> None:
    broken = valid_audit_json.replace(
        '"bully_comment": null',
        '"bully_comment": "This should fail."',
    )

    with pytest.raises(SchemaValidationError):
        OutputParser().parse(broken)