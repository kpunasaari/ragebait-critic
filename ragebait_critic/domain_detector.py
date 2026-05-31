"""
Domain and language detection for Ragebait Critic.

This module detects the best audit domain and output language for a processed
input. It supports deterministic heuristic detection and optional LLM-assisted
classification through LiteLLM.

The detector must never become a hard dependency for the whole engine. If LLM
classification fails, heuristic fallback is used.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from litellm import acompletion

from ragebait_critic.config import RagebaitConfig
from ragebait_critic.exceptions import DomainDetectionError
from ragebait_critic.schemas import (
    AuditRequest,
    DomainDetectionResult,
    ProcessedInput,
    ResolvedDomainName,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainDetectorOptions:
    """
    Runtime options for domain detection.
    """

    use_llm: bool = False
    min_llm_confidence: float = 0.5
    max_detection_chars: int = 20_000


class DomainDetector:
    """
    Detects audit domain and output language.

    The detector respects explicit user choices:

    - If request.domain is not "auto", that domain wins.
    - If request.language is not "auto", that language wins.

    LLM classification is optional and non-fatal.
    """

    VALID_RESOLVED_DOMAINS: set[str] = {
        "code",
        "project",
        "design",
        "thesis",
        "seo",
        "pr",
        "general",
    }

    CODE_EXTENSIONS: set[str] = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".htm",
        ".css",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".sql",
        ".prisma",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
    }

    DESIGN_EXTENSIONS: set[str] = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".svg",
    }

    def __init__(
        self,
        config: RagebaitConfig | None = None,
        options: DomainDetectorOptions | None = None,
    ) -> None:
        self.config = config or RagebaitConfig.from_env()
        self.options = options or DomainDetectorOptions()

    async def detect(
        self,
        request: AuditRequest,
        processed_input: ProcessedInput,
    ) -> DomainDetectionResult:
        """
        Resolve domain and language for an audit request.
        """
        explicit_domain = request.domain != "auto"
        explicit_language = request.language.lower() != "auto"

        heuristic_result = self._detect_with_heuristics(processed_input)

        resolved_domain: ResolvedDomainName = (
            request.domain if explicit_domain else heuristic_result.domain  # type: ignore[assignment]
        )
        resolved_language = request.language if explicit_language else heuristic_result.language

        if explicit_domain and explicit_language:
            return DomainDetectionResult(
                domain=resolved_domain,
                language=resolved_language,
                confidence=1.0,
                reasoning="Domain and language were explicitly provided by the user.",
                signals=["explicit_domain", "explicit_language", *heuristic_result.signals],
                used_llm=False,
                model=None,
            )

        if not self.options.use_llm:
            return DomainDetectionResult(
                domain=resolved_domain,
                language=resolved_language,
                confidence=heuristic_result.confidence if not explicit_domain else 1.0,
                reasoning=self._manual_override_reason(
                    explicit_domain=explicit_domain,
                    explicit_language=explicit_language,
                    fallback_reason=heuristic_result.reasoning,
                ),
                signals=self._override_signals(
                    explicit_domain=explicit_domain,
                    explicit_language=explicit_language,
                    fallback_signals=heuristic_result.signals,
                ),
                used_llm=False,
                model=None,
            )

        try:
            llm_result = await self._detect_with_llm(
                request=request,
                processed_input=processed_input,
                heuristic_result=heuristic_result,
            )

            if llm_result.confidence < self.options.min_llm_confidence:
                logger.warning(
                    "LLM domain detection confidence too low. confidence=%s",
                    llm_result.confidence,
                )
                return DomainDetectionResult(
                    domain=resolved_domain,
                    language=resolved_language,
                    confidence=heuristic_result.confidence,
                    reasoning=(
                        "LLM detection confidence was too low; heuristic fallback was used. "
                        f"Fallback reason: {heuristic_result.reasoning}"
                    ),
                    signals=["llm_low_confidence", *heuristic_result.signals],
                    used_llm=False,
                    model=None,
                )

            if explicit_domain:
                llm_result.domain = resolved_domain

            if explicit_language:
                llm_result.language = resolved_language

            llm_result.signals.extend(
                self._override_signals(
                    explicit_domain=explicit_domain,
                    explicit_language=explicit_language,
                    fallback_signals=[],
                )
            )

            return llm_result

        except Exception as exc:
            logger.warning("LLM domain detection failed. Falling back. error=%s", exc)

            return DomainDetectionResult(
                domain=resolved_domain,
                language=resolved_language,
                confidence=heuristic_result.confidence,
                reasoning=(
                    "LLM domain detection failed; heuristic fallback was used. "
                    f"Fallback reason: {heuristic_result.reasoning}"
                ),
                signals=["llm_detection_failed", *heuristic_result.signals],
                used_llm=False,
                model=None,
            )

    def _detect_with_heuristics(self, processed_input: ProcessedInput) -> DomainDetectionResult:
        """
        Deterministic fallback classifier.
        """
        if processed_input.content_type == "project" or processed_input.input_type in {
            "directory",
            "repository",
        }:
            return DomainDetectionResult(
                domain="project",
                language=self._detect_language(processed_input.text),
                confidence=0.95,
                reasoning="Input is a project/repository scan.",
                signals=["content_type_project", "input_type_directory_or_repository"],
                used_llm=False,
                model=None,
            )

        if processed_input.content_type == "image":
            return DomainDetectionResult(
                domain="design",
                language="Unknown",
                confidence=0.88,
                reasoning="Input is an image payload, so the safest audit domain is design.",
                signals=["content_type_image", "vision_payload_ready"],
                used_llm=False,
                model=None,
            )

        text = processed_input.text or ""
        lower = text.lower()
        source = processed_input.source
        extension = (source.extension or "").lower()

        scores: dict[ResolvedDomainName, float] = {
            "code": 0.0,
            "project": 0.0,
            "design": 0.0,
            "thesis": 0.0,
            "seo": 0.0,
            "pr": 0.0,
            "general": 0.1,
        }
        signals: list[str] = []

        if extension in self.CODE_EXTENSIONS:
            scores["code"] += 0.45
            signals.append(f"code_extension:{extension}")

        if extension in self.DESIGN_EXTENSIONS:
            scores["design"] += 0.45
            signals.append(f"design_extension:{extension}")

        code_hits = self._count_regex_hits(
            patterns=[
                r"\bdef\s+\w+\s*\(",
                r"\bclass\s+\w+",
                r"\bfunction\s+\w*\s*\(",
                r"\bconst\s+\w+\s*=",
                r"\blet\s+\w+\s*=",
                r"\bvar\s+\w+\s*=",
                r"\bimport\s+",
                r"\bfrom\s+\w+(\.\w+)*\s+import\s+",
                r"console\.log\s*\(",
                r"\breturn\s+",
                r"\btry\s*:",
                r"\bexcept\s+",
                r"<html\b",
                r"<script\b",
                r"<style\b",
                r"\bSELECT\b.+\bFROM\b",
                r"\basync\s+function\b",
                r"\bexport\s+",
            ],
            text=text,
        )
        if code_hits:
            scores["code"] += min(0.55, code_hits * 0.06)
            signals.append(f"code_patterns:{code_hits}")

        project_hits = self._count_keyword_hits(
            keywords=[
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "dockerfile",
                "docker-compose",
                ".env.example",
                "readme.md",
                "src/",
                "components/",
                "api/",
                "tests/",
                "github/workflows",
                "project scan summary",
                "repository hygiene",
                "detected stack",
                "selected files",
                "next.js",
                "supabase",
                "prisma",
                "deployment",
                "ci",
            ],
            lower_text=lower,
        )
        if project_hits:
            scores["project"] += min(0.65, project_hits * 0.07)
            signals.append(f"project_keywords:{project_hits}")

        design_hits = self._count_keyword_hits(
            keywords=[
                "ui",
                "ux",
                "figma",
                "wireframe",
                "mockup",
                "prototype",
                "typography",
                "font",
                "color palette",
                "contrast",
                "layout",
                "spacing",
                "padding",
                "margin",
                "responsive",
                "wcag",
                "hero section",
                "landing page",
                "call to action",
                "cta",
                "visual hierarchy",
                "accessibility",
                "tasarım",
                "arayüz",
                "kullanıcı deneyimi",
                "käyttöliittymä",
                "käyttökokemus",
            ],
            lower_text=lower,
        )
        if design_hits:
            scores["design"] += min(0.55, design_hits * 0.06)
            signals.append(f"design_keywords:{design_hits}")

        thesis_hits = self._count_keyword_hits(
            keywords=[
                "abstract",
                "methodology",
                "literature review",
                "research question",
                "hypothesis",
                "sample size",
                "statistical significance",
                "references",
                "bibliography",
                "doi:",
                "et al.",
                "findings",
                "limitations",
                "özet",
                "yöntem",
                "literatür",
                "kaynakça",
                "araştırma sorusu",
                "tutkimus",
                "menetelmä",
                "lähteet",
            ],
            lower_text=lower,
        )
        if thesis_hits:
            scores["thesis"] += min(0.6, thesis_hits * 0.07)
            signals.append(f"academic_keywords:{thesis_hits}")

        seo_hits = self._count_keyword_hits(
            keywords=[
                "seo",
                "keyword",
                "keywords",
                "search intent",
                "meta description",
                "title tag",
                "canonical",
                "backlink",
                "serp",
                "h1",
                "h2",
                "h3",
                "alt text",
                "core web vitals",
                "organic traffic",
                "slug",
                "internal linking",
                "anahtar kelime",
                "arama niyeti",
                "meta açıklama",
                "hakukoneoptimointi",
            ],
            lower_text=lower,
        )
        if seo_hits:
            scores["seo"] += min(0.6, seo_hits * 0.07)
            signals.append(f"seo_keywords:{seo_hits}")

        pr_hits = self._count_keyword_hits(
            keywords=[
                "press release",
                "for immediate release",
                "media contact",
                "brand",
                "campaign",
                "launches",
                "announces",
                "value proposition",
                "pitch deck",
                "investor",
                "our mission",
                "revolutionary",
                "innovative",
                "synergy",
                "ai-powered",
                "basın bülteni",
                "marka",
                "kampanya",
                "yatırımcı",
                "julkistaa",
                "lehdistötiedote",
            ],
            lower_text=lower,
        )
        if pr_hits:
            scores["pr"] += min(0.55, pr_hits * 0.06)
            signals.append(f"pr_keywords:{pr_hits}")

        if extension in {".html", ".htm"} and seo_hits >= 2:
            scores["seo"] += 0.2
            signals.append("html_with_seo_signals")

        if extension in {".html", ".htm", ".css"} and design_hits >= 2:
            scores["design"] += 0.15
            signals.append("frontend_design_signals")

        domain = self._winning_domain(scores)
        confidence = self._score_to_confidence(scores, domain)

        if confidence < 0.35:
            domain = "general"
            confidence = 0.3
            signals.append("low_confidence_general_fallback")

        language = self._detect_language(text)

        return DomainDetectionResult(
            domain=domain,
            language=language,
            confidence=confidence,
            reasoning=(
                f"Heuristic classifier selected '{domain}' using extension, lexical, "
                "structural, and metadata signals."
            ),
            signals=signals,
            used_llm=False,
            model=None,
        )

    async def _detect_with_llm(
        self,
        request: AuditRequest,
        processed_input: ProcessedInput,
        heuristic_result: DomainDetectionResult,
    ) -> DomainDetectionResult:
        """
        Optional LLM classifier.

        This is intentionally conservative. It only returns a result if valid JSON
        and valid domain values are produced.
        """
        model = request.model or self.config.default_model
        clipped = self._clip_text(processed_input.text or "")

        system_prompt = (
            "You are a strict classifier for an AI audit engine. "
            "Return only valid JSON. Do not use markdown or code fences."
        )

        user_prompt = f"""
Classify the submitted asset.

Allowed domains:
- code
- project
- design
- thesis
- seo
- pr
- general

Rules:
- If the input is a full repository/project scan, choose project.
- If source code dominates, choose code.
- If UI/UX/design language or image payload dominates, choose design.
- If academic research structure dominates, choose thesis.
- If search optimization dominates, choose seo.
- If marketing, PR, pitch, announcement, or brand copy dominates, choose pr.
- If unclear, choose general.

Detect the dominant language:
- English
- Turkish
- Finnish
- Swedish
- German
- French
- Spanish
- Unknown
- or another language name

Return exactly this JSON shape:
{{
  "domain": "code|project|design|thesis|seo|pr|general",
  "language": "English|Turkish|Finnish|Swedish|German|French|Spanish|Unknown|Other",
  "confidence": 0.0,
  "reasoning": "short reason",
  "signals": ["signal1", "signal2"]
}}

Metadata:
input_type: {processed_input.input_type}
content_type: {processed_input.content_type}
source_name: {processed_input.source.name}
extension: {processed_input.source.extension}
mime_type: {processed_input.source.mime_type}
heuristic_domain: {heuristic_result.domain}
heuristic_language: {heuristic_result.language}
heuristic_signals: {heuristic_result.signals}

Submitted content:
{clipped}
""".strip()

        response = await acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=700,
            timeout=self.config.request_timeout_seconds,
        )

        content = response["choices"][0]["message"]["content"]
        parsed = self._parse_json_object(content)

        domain = str(parsed.get("domain", "")).strip().lower()
        if domain not in self.VALID_RESOLVED_DOMAINS:
            raise DomainDetectionError(f"LLM returned invalid domain: {domain}")

        language = str(parsed.get("language", "Unknown")).strip() or "Unknown"
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        signals = parsed.get("signals", [])
        if not isinstance(signals, list):
            signals = [str(signals)]

        return DomainDetectionResult(
            domain=domain,  # type: ignore[arg-type]
            language=self._normalize_language_name(language),
            confidence=confidence,
            reasoning=str(parsed.get("reasoning", "")),
            signals=[str(item) for item in signals],
            used_llm=True,
            model=model,
        )

    def _parse_json_object(self, raw: str) -> dict[str, Any]:
        if not raw or not raw.strip():
            raise DomainDetectionError("LLM returned an empty detection response.")

        cleaned = raw.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                raise DomainDetectionError(
                    "LLM response does not contain a JSON object."
                ) from exc

            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError as nested_exc:
                raise DomainDetectionError(
                    "LLM response contained a JSON-like object, but it could not be parsed."
                ) from nested_exc

        if not isinstance(parsed, dict):
            raise DomainDetectionError("LLM detection response must be a JSON object.")

        return parsed

    def _detect_language(self, text: str) -> str:
        if not text.strip():
            return "Unknown"

        lower = text.lower()

        turkish_chars = len(re.findall(r"[çğıöşüÇĞİÖŞÜ]", text))
        nordic_chars = len(re.findall(r"[äöåÄÖÅ]", text))

        scores = {
            "Turkish": self._language_word_score(
                lower,
                [
                    "ve",
                    "bir",
                    "bu",
                    "şu",
                    "için",
                    "olarak",
                    "değil",
                    "çünkü",
                    "ama",
                    "fakat",
                    "göre",
                    "kullanıcı",
                    "tasarım",
                    "metin",
                    "proje",
                    "kod",
                ],
            )
            + turkish_chars * 0.45,
            "English": self._language_word_score(
                lower,
                [
                    "the",
                    "and",
                    "that",
                    "with",
                    "this",
                    "for",
                    "from",
                    "not",
                    "function",
                    "class",
                    "design",
                    "research",
                    "marketing",
                    "project",
                    "user",
                ],
            ),
            "Finnish": self._language_word_score(
                lower,
                [
                    "ja",
                    "on",
                    "että",
                    "tämä",
                    "kanssa",
                    "mutta",
                    "käyttäjä",
                    "suunnittelu",
                    "tutkimus",
                    "projekti",
                    "hakemus",
                ],
            )
            + nordic_chars * 0.25,
            "Swedish": self._language_word_score(
                lower,
                [
                    "och",
                    "att",
                    "det",
                    "som",
                    "inte",
                    "för",
                    "med",
                    "användare",
                    "projekt",
                    "forskning",
                ],
            )
            + nordic_chars * 0.1,
            "German": self._language_word_score(
                lower,
                [
                    "und",
                    "der",
                    "die",
                    "das",
                    "nicht",
                    "mit",
                    "für",
                    "benutzer",
                    "projekt",
                    "forschung",
                ],
            ),
            "French": self._language_word_score(
                lower,
                [
                    "et",
                    "le",
                    "la",
                    "les",
                    "des",
                    "avec",
                    "pour",
                    "utilisateur",
                    "projet",
                    "recherche",
                ],
            ),
            "Spanish": self._language_word_score(
                lower,
                [
                    "y",
                    "el",
                    "la",
                    "los",
                    "las",
                    "con",
                    "para",
                    "usuario",
                    "proyecto",
                    "investigación",
                ],
            ),
        }

        language = max(scores, key=scores.get)
        score = scores[language]

        if score <= 1.0:
            return "Unknown"

        return language

    def _language_word_score(self, lower_text: str, words: list[str]) -> float:
        score = 0.0

        for word in words:
            pattern = r"(?<!\w)" + re.escape(word.lower()) + r"(?!\w)"
            matches = re.findall(pattern, lower_text, flags=re.IGNORECASE)
            score += min(len(matches), 5) * 0.4

        return score

    def _normalize_language_name(self, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            return "Unknown"

        aliases = {
            "auto": "Unknown",
            "unknown": "Unknown",
            "tr": "Turkish",
            "turkish": "Turkish",
            "türkçe": "Turkish",
            "en": "English",
            "english": "English",
            "fi": "Finnish",
            "finnish": "Finnish",
            "suomi": "Finnish",
            "sv": "Swedish",
            "swedish": "Swedish",
            "de": "German",
            "german": "German",
            "fr": "French",
            "french": "French",
            "es": "Spanish",
            "spanish": "Spanish",
        }

        return aliases.get(cleaned.lower(), cleaned[:1].upper() + cleaned[1:])

    def _count_regex_hits(self, patterns: list[str], text: str) -> int:
        hits = 0

        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
                hits += 1

        return hits

    def _count_keyword_hits(self, keywords: list[str], lower_text: str) -> int:
        hits = 0

        for keyword in keywords:
            if keyword.lower() in lower_text:
                hits += 1

        return hits

    def _winning_domain(self, scores: dict[ResolvedDomainName, float]) -> ResolvedDomainName:
        return max(scores, key=scores.get)

    def _score_to_confidence(
        self,
        scores: dict[ResolvedDomainName, float],
        domain: ResolvedDomainName,
    ) -> float:
        winning_score = scores[domain]
        ordered = sorted(scores.values(), reverse=True)
        second_score = ordered[1] if len(ordered) > 1 else 0.0
        margin = max(0.0, winning_score - second_score)

        confidence = 0.25 + min(0.55, winning_score) + min(0.2, margin)
        return round(max(0.0, min(0.95, confidence)), 2)

    def _clip_text(self, text: str) -> str:
        if len(text) <= self.options.max_detection_chars:
            return text

        head = int(self.options.max_detection_chars * 0.75)
        tail = self.options.max_detection_chars - head

        return (
            text[:head]
            + "\n\n--- DETECTION INPUT TRUNCATED ---\n\n"
            + text[-tail:]
        )

    def _manual_override_reason(
        self,
        explicit_domain: bool,
        explicit_language: bool,
        fallback_reason: str,
    ) -> str:
        if explicit_domain and explicit_language:
            return "Domain and language were explicitly provided by the user."

        if explicit_domain:
            return (
                "Domain was explicitly provided by the user. "
                f"Language used fallback detection. {fallback_reason}"
            )

        if explicit_language:
            return (
                "Language was explicitly provided by the user. "
                f"Domain used fallback detection. {fallback_reason}"
            )

        return fallback_reason

    def _override_signals(
        self,
        explicit_domain: bool,
        explicit_language: bool,
        fallback_signals: list[str],
    ) -> list[str]:
        signals = list(fallback_signals)

        if explicit_domain:
            signals.insert(0, "explicit_domain")

        if explicit_language:
            signals.insert(0, "explicit_language")

        return signals


async def detect_domain(
    request: AuditRequest,
    processed_input: ProcessedInput,
    use_llm: bool = False,
) -> DomainDetectionResult:
    """
    Convenience function for one-off domain detection.
    """
    detector = DomainDetector(options=DomainDetectorOptions(use_llm=use_llm))
    return await detector.detect(request=request, processed_input=processed_input)