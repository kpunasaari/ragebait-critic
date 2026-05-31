from __future__ import annotations

import pytest

from ragebait_critic.engine import RagebaitCritic
from ragebait_critic.schemas import AuditRequest


@pytest.mark.asyncio
async def test_engine_prepare_input_for_file(test_config, sample_code_file) -> None:
    critic = RagebaitCritic(config=test_config)

    request = AuditRequest(input_path=str(sample_code_file))
    processed = await critic.prepare_input(request)

    assert processed.input_type == "file"
    assert processed.content_type == "text"
    assert "def hello" in processed.text


@pytest.mark.asyncio
async def test_engine_detect_only_for_project(test_config, sample_project_dir) -> None:
    critic = RagebaitCritic(config=test_config)

    request = AuditRequest(input_path=str(sample_project_dir))
    detection = await critic.detect_only(request)

    assert detection.domain == "project"
    assert detection.confidence == 0.95