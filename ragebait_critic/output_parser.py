"""
Output parsing and validation for Ragebait Critic.

The LLM is instructed to return strict JSON, but production-quality tools cannot
trust that instruction. This parser extracts JSON from messy model output,
attempts conservative repairs, and validates the result against AuditReport.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from ragebait_critic.exceptions import OutputParsingError, SchemaValidationError
from ragebait_critic.schemas import AuditReport

logger = logging.getLogger(__name__)


class OutputParser:
    """
    Parses LLM output into a validated AuditReport.
    """

    def parse(self, raw_output: str) -> AuditReport:
        """
        Parse raw model output into an AuditReport.
        """
        if not raw_output or not raw_output.strip():
            raise OutputParsingError("Cannot parse empty LLM output.")

        json_text = self.extract_json_text(raw_output)
        data = self._loads_with_repair(json_text)

        try:
            return AuditReport.model_validate(data)
        except ValidationError as exc:
            logger.error("AuditReport schema validation failed: %s", exc)
            raise SchemaValidationError(
                f"LLM output did not match AuditReport schema: {exc}"
            ) from exc

    def extract_json_text(self, raw_output: str) -> str:
        """
        Extract JSON object text from model output.

        Handles:
        - pure JSON
        - fenced JSON
        - accidental text before/after JSON
        """
        cleaned = raw_output.strip()

        unfenced = self._strip_code_fence(cleaned)

        if unfenced.startswith("{") and unfenced.endswith("}"):
            return unfenced

        extracted = self._extract_first_json_object(unfenced)

        if extracted is None:
            raise OutputParsingError("No JSON object found in LLM output.")

        return extracted

    def _strip_code_fence(self, text: str) -> str:
        """
        Remove surrounding markdown fences if the whole output is fenced.

        This does not try to parse nested JSON with regex. It only strips the
        outer fence and then balanced-brace extraction handles the JSON object.
        """
        cleaned = text.strip()

        if not cleaned.startswith("```"):
            return cleaned

        lines = cleaned.splitlines()

        if len(lines) < 3:
            return cleaned

        first_line = lines[0].strip().lower()
        last_line = lines[-1].strip()

        if first_line in {"```", "```json"} and last_line == "```":
            return "\n".join(lines[1:-1]).strip()

        return cleaned

    def _extract_first_json_object(self, text: str) -> str | None:
        """
        Extract the first balanced top-level JSON object from text.

        Regex alone is unreliable for nested JSON, so this uses brace counting
        while respecting JSON strings.
        """
        start = text.find("{")

        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for index in range(start, len(text)):
            char = text[index]

            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                depth += 1
                continue

            if char == "}":
                depth -= 1

                if depth == 0:
                    return text[start : index + 1]

        return None

    def _loads_with_repair(self, json_text: str) -> dict[str, Any]:
        """
        Load JSON with conservative repair attempts.

        Repairs are intentionally limited. Aggressive repair can silently corrupt
        audit reports, which is worse than failing loudly.
        """
        try:
            loaded = json.loads(json_text)
        except json.JSONDecodeError as first_error:
            repaired = self._repair_common_json_issues(json_text)

            try:
                loaded = json.loads(repaired)
            except json.JSONDecodeError as second_error:
                raise OutputParsingError(
                    "Failed to parse LLM output as JSON. "
                    f"First error: {first_error}. Repair error: {second_error}."
                ) from second_error

        if not isinstance(loaded, dict):
            raise OutputParsingError("Parsed JSON must be an object.")

        return loaded

    def _repair_common_json_issues(self, text: str) -> str:
        """
        Conservative JSON cleanup.

        Handles:
        - UTF-8 BOM
        - trailing commas before } or ]
        - smart quotes
        """
        repaired = text.strip().lstrip("\ufeff")
        repaired = repaired.replace("“", '"').replace("”", '"')
        repaired = repaired.replace("‘", "'").replace("’", "'")
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        return repaired


def parse_audit_report(raw_output: str) -> AuditReport:
    """
    Convenience function for one-off report parsing.
    """
    return OutputParser().parse(raw_output)