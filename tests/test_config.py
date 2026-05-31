from __future__ import annotations

import pytest

from ragebait_critic.config import RagebaitConfig
from ragebait_critic.exceptions import ConfigurationError


def test_config_from_fixture(test_config: RagebaitConfig) -> None:
    assert test_config.default_model == "test-model"
    assert test_config.default_domain == "auto"
    assert test_config.default_intensity == "brutal"
    assert test_config.default_roast_style == "none"
    assert test_config.max_file_size_bytes == 25 * 1024 * 1024


def test_config_rejects_empty_model(test_config: RagebaitConfig) -> None:
    broken = RagebaitConfig(
        default_model="",
        default_domain=test_config.default_domain,
        default_language=test_config.default_language,
        default_intensity=test_config.default_intensity,
        default_roast_style=test_config.default_roast_style,
        default_output_format=test_config.default_output_format,
        max_file_size_mb=test_config.max_file_size_mb,
        max_url_response_mb=test_config.max_url_response_mb,
        max_extracted_chars=test_config.max_extracted_chars,
        max_project_files=test_config.max_project_files,
        max_project_file_size_kb=test_config.max_project_file_size_kb,
        max_project_total_chars=test_config.max_project_total_chars,
        request_timeout_seconds=test_config.request_timeout_seconds,
        max_retries=test_config.max_retries,
        log_level=test_config.log_level,
    )

    with pytest.raises(ConfigurationError):
        broken.validate()