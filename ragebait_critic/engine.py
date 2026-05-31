"""
Core engine for Ragebait Critic.

This module wires together:
- file/raw text/URL/project processing
- domain and language detection
- prompt building
- LLM completion
- output parsing
- report formatting
"""

from __future__ import annotations

import logging
from pathlib import Path

from ragebait_critic.config import RagebaitConfig
from ragebait_critic.domain_detector import DomainDetector, DomainDetectorOptions
from ragebait_critic.exceptions import RagebaitCriticError
from ragebait_critic.file_processor import FileProcessor
from ragebait_critic.formatter import ReportFormatter
from ragebait_critic.llm_client import LLMClient
from ragebait_critic.output_parser import OutputParser
from ragebait_critic.project_scanner import ProjectScanner
from ragebait_critic.prompt_builder import PromptBuilder
from ragebait_critic.schemas import AuditReport, AuditRequest, FormattedReport, ProcessedInput

logger = logging.getLogger(__name__)


class RagebaitCritic:
    """
    Main application engine.

    This class is the public Python API for the project.
    """

    def __init__(
        self,
        config: RagebaitConfig | None = None,
        use_llm_domain_detection: bool = False,
    ) -> None:
        self.config = config or RagebaitConfig.from_env()

        self.file_processor = FileProcessor(config=self.config)
        self.project_scanner = ProjectScanner(config=self.config)
        self.domain_detector = DomainDetector(
            config=self.config,
            options=DomainDetectorOptions(use_llm=use_llm_domain_detection),
        )
        self.prompt_builder = PromptBuilder(config=self.config)
        self.llm_client = LLMClient(config=self.config)
        self.output_parser = OutputParser()
        self.formatter = ReportFormatter()

    async def audit(self, request: AuditRequest) -> FormattedReport:
        """
        Run a complete audit and return formatted output.

        This method performs the actual LLM call.
        """
        try:
            processed_input = await self._process_request_input(request)
            detection = await self.domain_detector.detect(
                request=request,
                processed_input=processed_input,
            )

            model_name = request.model or self.config.default_model

            prompt = self.prompt_builder.build(
                request=request,
                processed_input=processed_input,
                resolved_domain=detection.domain,
                resolved_language=detection.language,
                model_name=model_name,
            )

            llm_response = await self.llm_client.complete(
                prompt=prompt,
                model=model_name,
            )

            report = self.output_parser.parse(llm_response.content)
            report = self._normalize_report_metadata(
                report=report,
                request=request,
                processed_input=processed_input,
                resolved_domain=detection.domain,
                resolved_language=detection.language,
                model_name=llm_response.model,
            )

            return self.formatter.format(report, output_format=request.output_format)

        except RagebaitCriticError:
            raise
        except Exception as exc:
            logger.exception("Unexpected Ragebait Critic engine failure.")
            raise RagebaitCriticError(f"Unexpected engine failure: {exc}") from exc

    async def audit_text(
        self,
        text: str,
        domain: str | None = None,
        language: str | None = None,
        intensity: str | None = None,
        roast_style: str | None = None,
        output_format: str | None = None,
        model: str | None = None,
    ) -> FormattedReport:
        """
        Convenience method for raw text audits.
        """
        request = AuditRequest(
            input_text=text,
            domain=domain or self.config.default_domain,
            language=language or self.config.default_language,
            intensity=intensity or self.config.default_intensity,
            roast_style=roast_style or self.config.default_roast_style,
            output_format=output_format or self.config.default_output_format,
            model=model,
        )
        return await self.audit(request)

    async def audit_path(
        self,
        path: str | Path,
        domain: str | None = None,
        language: str | None = None,
        intensity: str | None = None,
        roast_style: str | None = None,
        output_format: str | None = None,
        model: str | None = None,
    ) -> FormattedReport:
        """
        Convenience method for file or local project directory audits.
        """
        request = AuditRequest(
            input_path=str(path),
            domain=domain or self.config.default_domain,
            language=language or self.config.default_language,
            intensity=intensity or self.config.default_intensity,
            roast_style=roast_style or self.config.default_roast_style,
            output_format=output_format or self.config.default_output_format,
            model=model,
        )
        return await self.audit(request)

    async def audit_url(
        self,
        url: str,
        domain: str | None = None,
        language: str | None = None,
        intensity: str | None = None,
        roast_style: str | None = None,
        output_format: str | None = None,
        model: str | None = None,
    ) -> FormattedReport:
        """
        Convenience method for URL audits.
        """
        request = AuditRequest(
            input_url=url,
            domain=domain or self.config.default_domain,
            language=language or self.config.default_language,
            intensity=intensity or self.config.default_intensity,
            roast_style=roast_style or self.config.default_roast_style,
            output_format=output_format or self.config.default_output_format,
            model=model,
        )
        return await self.audit(request)

    async def prepare_input(self, request: AuditRequest) -> ProcessedInput:
        """
        Process input without calling the LLM.

        Useful for debugging, CLI previews, and tests.
        """
        return await self._process_request_input(request)

    async def detect_only(self, request: AuditRequest):
        """
        Process input and detect domain/language without calling the LLM.
        """
        processed_input = await self._process_request_input(request)
        return await self.domain_detector.detect(
            request=request,
            processed_input=processed_input,
        )

    def format_report(
        self,
        report: AuditReport,
        output_format: str = "markdown",
    ) -> FormattedReport:
        """
        Format an already parsed AuditReport.
        """
        return self.formatter.format(report, output_format=output_format)

    async def _process_request_input(self, request: AuditRequest) -> ProcessedInput:
        if request.input_text is not None:
            return await self.file_processor.process_raw_text(request.input_text)

        if request.input_url is not None:
            return await self.file_processor.process_url(request.input_url)

        if request.input_path is not None:
            path = Path(request.input_path).expanduser().resolve()

            if path.exists() and path.is_dir():
                return await self.project_scanner.scan(path)

            return await self.file_processor.process_file(path)

        raise RagebaitCriticError("No valid input source was provided.")

    def _normalize_report_metadata(
        self,
        report: AuditReport,
        request: AuditRequest,
        processed_input: ProcessedInput,
        resolved_domain: str,
        resolved_language: str,
        model_name: str,
    ) -> AuditReport:
        """
        Force metadata to match the real runtime context.

        The model is asked to return metadata, but the engine should not blindly
        trust model-generated metadata.
        """
        data = report.model_dump(mode="json")

        data["meta"]["project"] = "ragebait-critic"
        data["meta"]["version"] = "0.1.0"
        data["meta"]["domain"] = resolved_domain
        data["meta"]["language"] = resolved_language
        data["meta"]["intensity"] = request.intensity
        data["meta"]["roast_style"] = request.roast_style
        data["meta"]["model"] = model_name
        data["meta"]["input_type"] = processed_input.input_type
        data["meta"]["source"] = processed_input.source.model_dump(mode="json")

        return AuditReport.model_validate(data)
