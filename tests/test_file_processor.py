from __future__ import annotations

import pytest

from ragebait_critic.exceptions import EmptyInputError
from ragebait_critic.file_processor import FileProcessor


@pytest.mark.asyncio
async def test_process_raw_text(test_config) -> None:
    processor = FileProcessor(config=test_config)

    result = await processor.process_raw_text("This is a weak landing page.")

    assert result.input_type == "raw_text"
    assert result.content_type == "text"
    assert result.source.kind == "raw_text"
    assert "weak landing page" in result.text


@pytest.mark.asyncio
async def test_process_empty_raw_text_rejected(test_config) -> None:
    processor = FileProcessor(config=test_config)

    with pytest.raises(EmptyInputError):
        await processor.process_raw_text("   ")


@pytest.mark.asyncio
async def test_process_code_file_adds_line_numbers(test_config, sample_code_file) -> None:
    processor = FileProcessor(config=test_config)

    result = await processor.process_file(sample_code_file)

    assert result.input_type == "file"
    assert result.content_type == "text"
    assert result.source.extension == ".py"
    assert result.source.metadata["line_numbers_added"] is True
    assert "001 |" in result.text
    assert "def hello" in result.text


@pytest.mark.asyncio
async def test_process_markdown_file(test_config, sample_markdown_file) -> None:
    processor = FileProcessor(config=test_config)

    result = await processor.process_file(sample_markdown_file)

    assert result.input_type == "file"
    assert result.content_type == "text"
    assert result.source.extension == ".md"
    assert "Weak PR Example" in result.text