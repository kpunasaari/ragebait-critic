from __future__ import annotations

import pytest
from pydantic import ValidationError

from ragebait_critic.schemas import AuditRequest


def test_audit_request_requires_exactly_one_input() -> None:
    request = AuditRequest(input_text="hello")
    assert request.input_text == "hello"


def test_audit_request_rejects_multiple_inputs() -> None:
    with pytest.raises(ValidationError):
        AuditRequest(input_text="hello", input_url="https://example.com")


def test_audit_request_rejects_no_input() -> None:
    with pytest.raises(ValidationError):
        AuditRequest()