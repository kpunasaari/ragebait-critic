from __future__ import annotations

import pytest

from ragebait_critic.domain_detector import DomainDetector
from ragebait_critic.file_processor import FileProcessor
from ragebait_critic.project_scanner import ProjectScanner
from ragebait_critic.schemas import AuditRequest


@pytest.mark.asyncio
async def test_detect_code_domain(test_config, sample_code_file) -> None:
    processor = FileProcessor(config=test_config)
    processed = await processor.process_file(sample_code_file)

    request = AuditRequest(input_path=str(sample_code_file), domain="auto", language="auto")
    detector = DomainDetector(config=test_config)

    result = await detector.detect(request=request, processed_input=processed)

    assert result.domain == "code"
    assert result.used_llm is False


@pytest.mark.asyncio
async def test_detect_project_domain(test_config, sample_project_dir) -> None:
    scanner = ProjectScanner(config=test_config)
    processed = await scanner.scan(sample_project_dir)

    request = AuditRequest(input_path=str(sample_project_dir), domain="auto", language="auto")
    detector = DomainDetector(config=test_config)

    result = await detector.detect(request=request, processed_input=processed)

    assert result.domain == "project"
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_manual_override_domain_and_language(test_config) -> None:
    processor = FileProcessor(config=test_config)
    processed = await processor.process_raw_text("This could be anything.")

    request = AuditRequest(
        input_text=processed.text,
        domain="seo",
        language="Turkish",
    )
    detector = DomainDetector(config=test_config)

    result = await detector.detect(request=request, processed_input=processed)

    assert result.domain == "seo"
    assert result.language == "Turkish"
    assert result.confidence == 1.0
    assert "explicit_domain" in result.signals
    assert "explicit_language" in result.signals