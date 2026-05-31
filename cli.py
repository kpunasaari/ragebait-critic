"""
Command-line interface for Ragebait Critic.

Examples:

    python cli.py --text "My landing page copy..." --domain pr

    python cli.py --input examples/bad_code.py --domain code --intensity brutal

    python cli.py --input examples/messy_saas_project \
        --domain project --intensity nuclear --roast-style bully

    python cli.py --url https://example.com --domain seo --format markdown

    python cli.py --input examples/messy_saas_project --format json --output report.json

Debug utilities:

    python cli.py --input examples/messy_saas_project --preview-input

    python cli.py --input examples/messy_saas_project --detect-only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from ragebait_critic.config import (
    VALID_DOMAINS,
    VALID_INTENSITIES,
    VALID_OUTPUT_FORMATS,
    VALID_ROAST_STYLES,
    RagebaitConfig,
    configure_logging,
)
from ragebait_critic.engine import RagebaitCritic
from ragebait_critic.exceptions import RagebaitCriticError
from ragebait_critic.schemas import AuditRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ragebait",
        description=(
            "Ragebait Critic — ruthless AI audits for code, projects, design briefs, "
            "academic writing, SEO content, PR copy, and product ideas."
        ),
    )

    input_group = parser.add_mutually_exclusive_group(required=True)

    input_group.add_argument(
        "--input",
        "-i",
        dest="input_path",
        help="Path to a local file or project directory.",
    )

    input_group.add_argument(
        "--text",
        "-t",
        dest="input_text",
        help="Raw text to audit.",
    )

    input_group.add_argument(
        "--url",
        "-u",
        dest="input_url",
        help="URL to fetch and audit.",
    )

    parser.add_argument(
        "--domain",
        "-d",
        default=None,
        choices=sorted(VALID_DOMAINS),
        help="Audit domain. Default comes from .env. Use 'auto' for detection.",
    )

    parser.add_argument(
        "--language",
        "-l",
        default=None,
        help="Output language. Default comes from .env. Use 'auto' to match input.",
    )

    parser.add_argument(
        "--intensity",
        default=None,
        choices=sorted(VALID_INTENSITIES),
        help="Critique intensity.",
    )

    parser.add_argument(
        "--roast-style",
        default=None,
        choices=sorted(VALID_ROAST_STYLES),
        help="Optional roast style.",
    )

    parser.add_argument(
        "--bully",
        action="store_true",
        help="Shortcut for --roast-style bully.",
    )

    parser.add_argument(
        "--format",
        dest="output_format",
        default=None,
        choices=sorted(VALID_OUTPUT_FORMATS),
        help="Output format.",
    )

    parser.add_argument(
        "--output",
        "-o",
        dest="output_path",
        help="Write output to a file instead of printing only to stdout.",
    )

    parser.add_argument(
        "--model",
        default=None,
        help="Override the configured LiteLLM model.",
    )

    parser.add_argument(
        "--use-llm-domain-detection",
        action="store_true",
        help="Use LLM-assisted domain/language detection. Heuristic detection is used by default.",
    )

    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Only process input and detect domain/language. Does not call the audit LLM.",
    )

    parser.add_argument(
        "--preview-input",
        action="store_true",
        help=(
            "Only process and print normalized input metadata/content preview. "
            "Does not call the audit LLM."
        ),
    )

    parser.add_argument(
        "--log-level",
        default=None,
        help="Override LOG_LEVEL from .env.",
    )

    return parser


def request_from_args(args: argparse.Namespace, config: RagebaitConfig) -> AuditRequest:
    roast_style = args.roast_style or config.default_roast_style

    if args.bully:
        roast_style = "bully"

    return AuditRequest(
        input_text=args.input_text,
        input_path=args.input_path,
        input_url=args.input_url,
        domain=args.domain or config.default_domain,
        language=args.language or config.default_language,
        intensity=args.intensity or config.default_intensity,
        roast_style=roast_style,
        output_format=args.output_format or config.default_output_format,
        model=args.model,
    )


async def run_preview_input(critic: RagebaitCritic, request: AuditRequest) -> int:
    processed = await critic.prepare_input(request)

    print("Ragebait Critic Input Preview")
    print("=" * 40)
    print(f"input_type: {processed.input_type}")
    print(f"content_type: {processed.content_type}")
    print(f"source_kind: {processed.source.kind}")
    print(f"source_name: {processed.source.name}")
    print(f"source_path: {processed.source.path}")
    print(f"source_url: {processed.source.url}")
    print(f"extension: {processed.source.extension}")
    print(f"mime_type: {processed.source.mime_type}")
    print(f"file_count: {processed.source.file_count}")
    print(f"char_count: {processed.source.char_count}")
    print(f"truncated: {processed.source.truncated}")
    print(f"metadata: {processed.source.metadata}")

    if processed.content_type == "project":
        print()
        print("Project Manifest")
        print("=" * 40)
        for item in processed.project_manifest[:100]:
            selected = "selected" if item.selected else "not_selected"
            print(f"{item.path} | {item.extension} | {item.byte_size} bytes | {selected}")

        if len(processed.project_manifest) > 100:
            print(f"... {len(processed.project_manifest) - 100} more files omitted from preview")

        print()
        print("Selected Files")
        print("=" * 40)
        for item in processed.selected_files:
            print(f"{item.path} | {item.char_count} chars | truncated={item.truncated}")

    else:
        print()
        print("Text Preview")
        print("=" * 40)
        print(processed.text[:4000])

        if len(processed.text) > 4000:
            print("\n--- preview truncated ---")

    return 0


async def run_detect_only(critic: RagebaitCritic, request: AuditRequest) -> int:
    detection = await critic.detect_only(request)

    print(detection.model_dump_json(indent=2))
    return 0


async def run_audit(
    critic: RagebaitCritic,
    request: AuditRequest,
    output_path: str | None,
) -> int:
    formatted = await critic.audit(request)

    output = formatted.json_text if request.output_format == "json" else formatted.markdown

    if output is None:
        raise RagebaitCriticError("Formatter returned no output.")

    if output_path:
        path = Path(output_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
        print(f"Report written to: {path}")
    else:
        print(output)

    return 0


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = RagebaitConfig.from_env()
    configure_logging(args.log_level or config.log_level)

    try:
        request = request_from_args(args, config)

    except ValidationError as exc:
        print("Invalid audit request:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2

    critic = RagebaitCritic(
        config=config,
        use_llm_domain_detection=args.use_llm_domain_detection,
    )

    try:
        if args.preview_input:
            return await run_preview_input(critic, request)

        if args.detect_only:
            return await run_detect_only(critic, request)

        return await run_audit(
            critic=critic,
            request=request,
            output_path=args.output_path,
        )

    except RagebaitCriticError as exc:
        print(f"Ragebait Critic error: {exc}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
