from __future__ import annotations

import pytest

from ragebait_critic.project_scanner import ProjectScanner


@pytest.mark.asyncio
async def test_project_scanner_returns_project_input(test_config, sample_project_dir) -> None:
    scanner = ProjectScanner(config=test_config)

    result = await scanner.scan(sample_project_dir)

    assert result.input_type == "directory"
    assert result.content_type == "project"
    assert result.source.kind == "directory"
    assert result.source.file_count is not None
    assert result.source.file_count > 0
    assert result.project_manifest
    assert result.selected_files


@pytest.mark.asyncio
async def test_project_scanner_ignores_real_env_file(test_config, sample_project_dir) -> None:
    scanner = ProjectScanner(config=test_config)

    result = await scanner.scan(sample_project_dir)

    all_text = result.text + "\n" + "\n".join(item.content for item in result.selected_files)

    assert "SECRET_DATABASE_PASSWORD" not in all_text
    assert "OPENAI_API_KEY=secret" not in all_text
    assert ".env.example" in all_text


@pytest.mark.asyncio
async def test_project_scanner_detects_hygiene_and_stack(test_config, sample_project_dir) -> None:
    scanner = ProjectScanner(config=test_config)

    result = await scanner.scan(sample_project_dir)

    hygiene = result.source.metadata["repository_hygiene"]
    stack = result.source.metadata["detected_stack"]

    assert hygiene["has_readme"] is True
    assert hygiene["has_env_example"] is True
    assert hygiene["has_ci"] is True
    assert hygiene["has_dependency_file"] is True

    assert "Next.js" in stack
    assert "React" in stack
    assert "TypeScript" in stack