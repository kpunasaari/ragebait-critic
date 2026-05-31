"""
Configuration management for Ragebait Critic.

Configuration is loaded from environment variables, optionally populated by
a local .env file through python-dotenv.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

from ragebait_critic.exceptions import ConfigurationError

load_dotenv()


DomainName = Literal[
    "auto",
    "code",
    "project",
    "design",
    "thesis",
    "seo",
    "pr",
    "general",
]

IntensityName = Literal[
    "normal",
    "brutal",
    "nuclear",
]

RoastStyleName = Literal[
    "none",
    "bully",
]

OutputFormatName = Literal[
    "markdown",
    "json",
]


VALID_DOMAINS: set[str] = {
    "auto",
    "code",
    "project",
    "design",
    "thesis",
    "seo",
    "pr",
    "general",
}

VALID_INTENSITIES: set[str] = {
    "normal",
    "brutal",
    "nuclear",
}

VALID_ROAST_STYLES: set[str] = {
    "none",
    "bully",
}

VALID_OUTPUT_FORMATS: set[str] = {
    "markdown",
    "json",
}

VALID_LOG_LEVELS: set[str] = {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


@dataclass(frozen=True)
class RagebaitConfig:
    """
    Application-wide configuration.

    The defaults are intentionally conservative. Expensive or risky behavior
    should be opt-in rather than silently enabled.
    """

    default_model: str
    default_domain: DomainName
    default_language: str
    default_intensity: IntensityName
    default_roast_style: RoastStyleName
    default_output_format: OutputFormatName

    max_file_size_mb: int
    max_url_response_mb: int
    max_extracted_chars: int

    max_project_files: int
    max_project_file_size_kb: int
    max_project_total_chars: int

    request_timeout_seconds: float
    max_retries: int

    log_level: str

    @classmethod
    def from_env(cls) -> RagebaitConfig:
        """
        Build configuration from environment variables.
        """
        config = cls(
            default_model=_get_str("DEFAULT_MODEL", "openai/gpt-4o-mini"),
            default_domain=_get_domain("DEFAULT_DOMAIN", "auto"),
            default_language=_get_str("DEFAULT_LANGUAGE", "auto"),
            default_intensity=_get_intensity("DEFAULT_INTENSITY", "brutal"),
            default_roast_style=_get_roast_style("DEFAULT_ROAST_STYLE", "none"),
            default_output_format=_get_output_format("DEFAULT_OUTPUT_FORMAT", "markdown"),
            max_file_size_mb=_get_int("MAX_FILE_SIZE_MB", 25, minimum=1),
            max_url_response_mb=_get_int("MAX_URL_RESPONSE_MB", 10, minimum=1),
            max_extracted_chars=_get_int("MAX_EXTRACTED_CHARS", 250_000, minimum=10_000),
            max_project_files=_get_int("MAX_PROJECT_FILES", 250, minimum=1),
            max_project_file_size_kb=_get_int("MAX_PROJECT_FILE_SIZE_KB", 512, minimum=1),
            max_project_total_chars=_get_int(
                "MAX_PROJECT_TOTAL_CHARS",
                400_000,
                minimum=10_000,
            ),
            request_timeout_seconds=_get_float(
                "REQUEST_TIMEOUT_SECONDS",
                30.0,
                minimum=1.0,
            ),
            max_retries=_get_int("MAX_RETRIES", 2, minimum=0),
            log_level=_get_log_level("LOG_LEVEL", "INFO"),
        )

        config.validate()
        return config

    def validate(self) -> None:
        """
        Validate internally consistent configuration.
        """
        if not self.default_model.strip():
            raise ConfigurationError("DEFAULT_MODEL cannot be empty.")

        if self.max_project_total_chars < self.max_extracted_chars:
            logging.getLogger(__name__).debug(
                "MAX_PROJECT_TOTAL_CHARS is smaller than MAX_EXTRACTED_CHARS. "
                "This is allowed, but project audits may be truncated more aggressively."
            )

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_url_response_bytes(self) -> int:
        return self.max_url_response_mb * 1024 * 1024

    @property
    def max_project_file_size_bytes(self) -> int:
        return self.max_project_file_size_kb * 1024


def configure_logging(level: str) -> None:
    """
    Configure root logging for CLI/UI runs.

    Libraries should not call this automatically. Entry points should call it.
    """
    normalized = level.upper()

    if normalized not in VALID_LOG_LEVELS:
        raise ConfigurationError(
            f"Invalid log level: {level}. Allowed values: {sorted(VALID_LOG_LEVELS)}"
        )

    logging.basicConfig(
        level=getattr(logging, normalized),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name, default)
    return value.strip()


def _get_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.getenv(name)

    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be an integer. Received: {raw}") from exc

    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}. Received: {value}")

    return value


def _get_float(name: str, default: float, minimum: float | None = None) -> float:
    raw = os.getenv(name)

    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = float(raw)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be a number. Received: {raw}") from exc

    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}. Received: {value}")

    return value


def _get_domain(name: str, default: str) -> DomainName:
    value = _get_str(name, default).lower()

    if value not in VALID_DOMAINS:
        raise ConfigurationError(
            f"{name} must be one of {sorted(VALID_DOMAINS)}. Received: {value}"
        )

    return value  # type: ignore[return-value]


def _get_intensity(name: str, default: str) -> IntensityName:
    value = _get_str(name, default).lower()

    if value not in VALID_INTENSITIES:
        raise ConfigurationError(
            f"{name} must be one of {sorted(VALID_INTENSITIES)}. Received: {value}"
        )

    return value  # type: ignore[return-value]


def _get_roast_style(name: str, default: str) -> RoastStyleName:
    value = _get_str(name, default).lower()

    if value not in VALID_ROAST_STYLES:
        raise ConfigurationError(
            f"{name} must be one of {sorted(VALID_ROAST_STYLES)}. Received: {value}"
        )

    return value  # type: ignore[return-value]


def _get_output_format(name: str, default: str) -> OutputFormatName:
    value = _get_str(name, default).lower()

    if value not in VALID_OUTPUT_FORMATS:
        raise ConfigurationError(
            f"{name} must be one of {sorted(VALID_OUTPUT_FORMATS)}. Received: {value}"
        )

    return value  # type: ignore[return-value]


def _get_log_level(name: str, default: str) -> str:
    value = _get_str(name, default).upper()

    if value not in VALID_LOG_LEVELS:
        raise ConfigurationError(
            f"{name} must be one of {sorted(VALID_LOG_LEVELS)}. Received: {value}"
        )

    return value