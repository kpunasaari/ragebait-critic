"""
Ragebait Critic.

An open-source AI audit engine that reviews code, project repositories,
design briefs, academic writing, SEO content, PR copy, and product ideas
with ruthless, evidence-based criticism.
"""

from ragebait_critic.config import RagebaitConfig
from ragebait_critic.domain_detector import DomainDetector, DomainDetectorOptions
from ragebait_critic.engine import RagebaitCritic
from ragebait_critic.file_processor import FileProcessor
from ragebait_critic.formatter import ReportFormatter
from ragebait_critic.llm_client import LLMClient, LLMResponse
from ragebait_critic.output_parser import OutputParser
from ragebait_critic.project_scanner import ProjectScanner
from ragebait_critic.schemas import (
    ArchitectureReview,
    AuditReport,
    AuditRequest,
    DomainDetectionResult,
    Finding,
    FormattedReport,
    ProcessedInput,
    ProjectAudit,
    RepositoryHygiene,
    SourceInfo,
    Verdict,
)

__all__ = [
    "RagebaitConfig",
    "RagebaitCritic",
    "FileProcessor",
    "ProjectScanner",
    "DomainDetector",
    "DomainDetectorOptions",
    "LLMClient",
    "LLMResponse",
    "OutputParser",
    "ReportFormatter",
    "AuditRequest",
    "AuditReport",
    "FormattedReport",
    "ArchitectureReview",
    "DomainDetectionResult",
    "Finding",
    "ProcessedInput",
    "ProjectAudit",
    "RepositoryHygiene",
    "SourceInfo",
    "Verdict",
]

__version__ = "0.1.0"