"""
Custom exceptions for Ragebait Critic.

The application should raise domain-specific exceptions instead of leaking
low-level implementation errors directly into the CLI, UI, or tool output.
"""


class RagebaitCriticError(Exception):
    """Base exception for all Ragebait Critic errors."""


class ConfigurationError(RagebaitCriticError):
    """Raised when configuration or environment settings are invalid."""


class FileProcessingError(RagebaitCriticError):
    """Raised when a file cannot be processed."""


class UnsupportedFileTypeError(FileProcessingError):
    """Raised when the user provides an unsupported file type."""


class InputTooLargeError(FileProcessingError):
    """Raised when the provided input exceeds configured limits."""


class EmptyInputError(FileProcessingError):
    """Raised when the provided input is empty or unusable."""


class URLFetchError(FileProcessingError):
    """Raised when a URL cannot be fetched or converted to text."""


class ProjectScanError(RagebaitCriticError):
    """Raised when a project directory cannot be scanned."""


class UnsafeInputError(RagebaitCriticError):
    """Raised when input violates safety or privacy constraints."""


class DomainDetectionError(RagebaitCriticError):
    """Raised when domain or language detection fails."""


class PromptBuildError(RagebaitCriticError):
    """Raised when the final LLM prompt cannot be built."""


class LLMClientError(RagebaitCriticError):
    """Raised when the configured LLM provider fails."""


class OutputParsingError(RagebaitCriticError):
    """Raised when the LLM response cannot be parsed into valid output."""


class SchemaValidationError(RagebaitCriticError):
    """Raised when generated audit output does not match the expected schema."""


class FormattingError(RagebaitCriticError):
    """Raised when a report cannot be formatted into the requested output type."""