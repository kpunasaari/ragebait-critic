"""
Pydantic schemas for Ragebait Critic.

These schemas are the contract between:
- file/project processors,
- domain detector,
- prompt builder,
- LLM client,
- output parser,
- CLI,
- Streamlit UI,
- external tool integrations.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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

ResolvedDomainName = Literal[
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

InputTypeName = Literal[
    "raw_text",
    "file",
    "url",
    "directory",
    "repository",
]

ContentTypeName = Literal[
    "text",
    "image",
    "project",
]

SeverityName = Literal[
    "critical",
    "high",
    "medium",
    "low",
    "nitpick",
]

EffortName = Literal[
    "low",
    "medium",
    "high",
]

ReadinessName = Literal[
    "idea",
    "prototype",
    "mvp",
    "beta",
    "production_candidate",
    "production_ready",
    "unknown",
]


class AuditRequest(BaseModel):
    """
    User-facing audit request.

    Exactly one primary input should normally be provided:
    - input_text
    - input_path
    - input_url
    """

    input_text: str | None = None
    input_path: str | None = None
    input_url: str | None = None

    domain: DomainName = "auto"
    language: str = "auto"
    intensity: IntensityName = "brutal"
    roast_style: RoastStyleName = "none"
    output_format: OutputFormatName = "markdown"

    model: str | None = None

    @model_validator(mode="after")
    def validate_single_input(self) -> AuditRequest:
        provided = [
            self.input_text is not None and self.input_text.strip() != "",
            self.input_path is not None and self.input_path.strip() != "",
            self.input_url is not None and self.input_url.strip() != "",
        ]

        if sum(provided) != 1:
            raise ValueError(
                "Exactly one input source must be provided: input_text, input_path, or input_url."
            )

        return self

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            return "auto"

        return cleaned


class SourceInfo(BaseModel):
    """
    Information about the submitted source.
    """

    kind: InputTypeName
    name: str | None = None
    path: str | None = None
    url: str | None = None
    mime_type: str | None = None
    extension: str | None = None

    file_count: int | None = None
    byte_size: int | None = None
    char_count: int | None = None

    truncated: bool = False
    sha256: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessedInput(BaseModel):
    """
    Normalized input after file, URL, raw text, or project processing.
    """

    input_type: InputTypeName
    content_type: ContentTypeName

    source: SourceInfo

    text: str = ""
    image_base64: str | None = None

    project_manifest: list[ProjectFileInfo] = Field(default_factory=list)
    selected_files: list[ProjectFileContent] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class ProjectFileInfo(BaseModel):
    """
    Metadata for a file discovered during project scanning.
    """

    path: str
    extension: str | None = None
    byte_size: int
    selected: bool = False
    reason: str | None = None


class ProjectFileContent(BaseModel):
    """
    Extracted content from an important project file.
    """

    path: str
    extension: str | None = None
    content: str
    byte_size: int
    char_count: int
    truncated: bool = False


class DomainDetectionResult(BaseModel):
    """
    Result of domain and language detection.
    """

    domain: ResolvedDomainName
    language: str = "Unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    signals: list[str] = Field(default_factory=list)
    used_llm: bool = False
    model: str | None = None


class Verdict(BaseModel):
    """
    Top-level judgment of the submitted work.
    """

    score: int = Field(ge=0, le=100)
    rage_title: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class Finding(BaseModel):
    """
    Single concrete flaw discovered in the submitted work.
    """

    id: str = Field(min_length=1)
    severity: SeverityName
    category: str = Field(min_length=1)
    location: str | None = None

    evidence: str = Field(min_length=1)
    problem: str = Field(min_length=1)

    rage_comment: str = Field(min_length=1)
    bully_comment: str | None = None

    impact: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    effort: EffortName = "medium"

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().upper()


class PriorityAction(BaseModel):
    """
    Ranked action item for improving the submitted work.
    """

    rank: int = Field(ge=1)
    action: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RepositoryHygiene(BaseModel):
    """
    Repository-level hygiene indicators for project audits.
    """

    has_readme: bool = False
    has_tests: bool = False
    has_env_example: bool = False
    has_ci: bool = False
    has_license: bool = False
    has_dockerfile: bool = False
    has_dependency_file: bool = False


class ProjectAudit(BaseModel):
    """
    Project-specific audit section.

    This is included when the input is a directory/repository or when the
    resolved domain is project.
    """

    detected_stack: list[str] = Field(default_factory=list)
    project_type: str = "unknown"
    architecture_score: int = Field(default=0, ge=0, le=100)
    readiness: ReadinessName = "unknown"
    repository_hygiene: RepositoryHygiene = Field(default_factory=RepositoryHygiene)
    critical_missing_pieces: list[str] = Field(default_factory=list)


class ArchitectureReview(BaseModel):
    """
    Optional architecture-specific review section.
    """

    summary: str = ""
    strength_of_boundaries: Literal["strong", "moderate", "weak", "unknown"] = "unknown"
    missing_layers: list[str] = Field(default_factory=list)


class AuditMeta(BaseModel):
    """
    Metadata included in every final report.
    """

    project: str = "ragebait-critic"
    version: str = "0.1.0"

    domain: ResolvedDomainName
    language: str
    intensity: IntensityName
    roast_style: RoastStyleName

    model: str
    input_type: InputTypeName
    source: SourceInfo


class AuditReport(BaseModel):
    """
    Final structured report.

    This is the canonical output contract. Markdown is only a rendered view
    of this structure.
    """

    meta: AuditMeta
    verdict: Verdict
    findings: list[Finding] = Field(default_factory=list)

    project_audit: ProjectAudit | None = None
    architecture_review: ArchitectureReview | None = None

    priority_actions: list[PriorityAction] = Field(default_factory=list)
    blind_spots: list[str] = Field(default_factory=list)

    final_roast: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bully_comments(self) -> AuditReport:
        if self.meta.roast_style == "none":
            for finding in self.findings:
                if finding.bully_comment:
                    raise ValueError(
                        "bully_comment must not be populated when roast_style is 'none'."
                    )

        return self

    @model_validator(mode="after")
    def validate_project_sections(self) -> AuditReport:
        if self.meta.domain == "project" and self.project_audit is None:
            raise ValueError("project_audit is required when domain is 'project'.")

        return self


class FormattedReport(BaseModel):
    """
    Rendered report output.
    """

    report: AuditReport
    markdown: str | None = None
    json_text: str | None = None


ProcessedInput.model_rebuild()