"""
Streamlit UI for Ragebait Critic.

Run:

    streamlit run main.py

The UI supports:
- raw text input
- file upload
- URL input
- local project path input
- input preview
- domain/language detection
- full audit through configured LiteLLM provider
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st
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
from ragebait_critic.schemas import AuditRequest, FormattedReport, ProcessedInput

APP_TITLE = "Ragebait Critic"
APP_SUBTITLE = "Get your work destroyed before the real world does it for free."


def run_async(coro: Any) -> Any:
    """
    Run async code safely from Streamlit's synchronous execution model.
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


@st.cache_resource
def get_config() -> RagebaitConfig:
    return RagebaitConfig.from_env()


@st.cache_resource
def get_critic(use_llm_domain_detection: bool) -> RagebaitCritic:
    config = get_config()
    configure_logging(config.log_level)
    return RagebaitCritic(
        config=config,
        use_llm_domain_detection=use_llm_domain_detection,
    )


def page_config() -> None:
    st.set_page_config(
        page_title="Ragebait Critic",
        page_icon="🔥",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_header() -> None:
    st.title(f"🔥 {APP_TITLE}")
    st.caption(APP_SUBTITLE)

    st.markdown(
        """
Ragebait Critic is an open-source AI audit engine for code, project repositories,
design briefs, academic writing, SEO content, PR copy, and product ideas.

It is designed to be harsh, evidence-based, and useful — not a motivational sticker dispenser.
"""
    )


def render_sidebar(config: RagebaitConfig) -> dict[str, Any]:
    st.sidebar.header("Audit Settings")

    domain = st.sidebar.selectbox(
        "Domain",
        options=sorted(VALID_DOMAINS),
        index=sorted(VALID_DOMAINS).index(config.default_domain),
        help="Use auto unless you already know the correct audit domain.",
    )

    language = st.sidebar.text_input(
        "Output Language",
        value=config.default_language,
        help="Use auto to match detected input language. Examples: English, Turkish, Finnish.",
    )

    intensity = st.sidebar.selectbox(
        "Intensity",
        options=sorted(VALID_INTENSITIES),
        index=sorted(VALID_INTENSITIES).index(config.default_intensity),
    )

    roast_style = st.sidebar.selectbox(
        "Roast Style",
        options=sorted(VALID_ROAST_STYLES),
        index=sorted(VALID_ROAST_STYLES).index(config.default_roast_style),
    )

    bully_shortcut = st.sidebar.checkbox(
        "Bully Mode",
        value=roast_style == "bully",
        help="Opt-in stand-up bully roast style. Jokes stay tied to the submitted flaws.",
    )

    if bully_shortcut:
        roast_style = "bully"

    output_format = st.sidebar.selectbox(
        "Output Format",
        options=sorted(VALID_OUTPUT_FORMATS),
        index=sorted(VALID_OUTPUT_FORMATS).index(config.default_output_format),
    )

    model = st.sidebar.text_input(
        "Model Override",
        value=config.default_model,
        help=(
            "LiteLLM model name. Example: openai/gpt-4o-mini, "
            "gemini/gemini-1.5-flash, ollama/llama3.1"
        ),
    )

    use_llm_domain_detection = st.sidebar.checkbox(
        "Use LLM domain detection",
        value=False,
        help="Off by default. Heuristic detection does not require an LLM call.",
    )

    st.sidebar.divider()

    action = st.sidebar.radio(
        "Action",
        options=[
            "Preview Input",
            "Detect Only",
            "Run Full Audit",
        ],
        index=0,
        help="Preview and Detect Only do not call the audit LLM.",
    )

    return {
        "domain": domain,
        "language": language,
        "intensity": intensity,
        "roast_style": roast_style,
        "output_format": output_format,
        "model": model.strip() or None,
        "use_llm_domain_detection": use_llm_domain_detection,
        "action": action,
    }


def render_input_section() -> dict[str, Any]:
    st.header("Input")

    input_mode = st.tabs(
        [
            "Paste Text",
            "Upload File",
            "URL",
            "Local Project Path",
        ]
    )

    state: dict[str, Any] = {
        "input_text": None,
        "input_path": None,
        "input_url": None,
        "temp_file_path": None,
    }

    with input_mode[0]:
        text = st.text_area(
            "Paste text to audit",
            height=260,
            placeholder=(
                "Paste landing page copy, PR text, thesis excerpt, "
                "product idea, code snippet..."
            ),
        )
        if text.strip():
            state["input_text"] = text

    with input_mode[1]:
        uploaded = st.file_uploader(
            "Upload a file",
            type=[
                "txt",
                "md",
                "markdown",
                "py",
                "js",
                "jsx",
                "ts",
                "tsx",
                "html",
                "htm",
                "css",
                "json",
                "xml",
                "csv",
                "yaml",
                "yml",
                "toml",
                "ini",
                "cfg",
                "pdf",
                "docx",
                "png",
                "jpg",
                "jpeg",
                "webp",
                "bmp",
                "gif",
                "tiff",
                "tif",
            ],
        )

        if uploaded is not None:
            temp_path = save_uploaded_file(uploaded)
            state["input_path"] = str(temp_path)
            state["temp_file_path"] = str(temp_path)
            st.info(f"Temporary file saved for processing: `{temp_path}`")

    with input_mode[2]:
        url = st.text_input(
            "URL to audit",
            placeholder="https://example.com",
        )
        if url.strip():
            state["input_url"] = url.strip()

    with input_mode[3]:
        local_path = st.text_input(
            "Local project directory path",
            placeholder=r"D:\ragebait-critic\examples\messy_saas_project",
            help=(
                "This works only when Streamlit is running on the same machine "
                "that has the project folder."
            ),
        )
        if local_path.strip():
            state["input_path"] = local_path.strip()

    return state


def save_uploaded_file(uploaded_file: Any) -> Path:
    suffix = Path(uploaded_file.name).suffix
    temp_dir = Path(tempfile.gettempdir()) / "ragebait_critic_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(uploaded_file.name).name
    temp_path = temp_dir / safe_name

    if temp_path.exists():
        temp_path = temp_dir / f"{temp_path.stem}_{next(tempfile._get_candidate_names())}{suffix}"

    temp_path.write_bytes(uploaded_file.getbuffer())
    return temp_path


def build_request(input_state: dict[str, Any], settings: dict[str, Any]) -> AuditRequest:
    provided = [
        bool(input_state.get("input_text")),
        bool(input_state.get("input_path")),
        bool(input_state.get("input_url")),
    ]

    if sum(provided) != 1:
        raise ValueError(
            "Provide exactly one input source: pasted text, uploaded file, URL, "
            "or local project path."
        )

    return AuditRequest(
        input_text=input_state.get("input_text"),
        input_path=input_state.get("input_path"),
        input_url=input_state.get("input_url"),
        domain=settings["domain"],
        language=settings["language"],
        intensity=settings["intensity"],
        roast_style=settings["roast_style"],
        output_format=settings["output_format"],
        model=settings["model"],
    )


def render_processed_input(processed: ProcessedInput) -> None:
    st.subheader("Processed Input")

    meta = {
        "input_type": processed.input_type,
        "content_type": processed.content_type,
        "source": processed.source.model_dump(mode="json"),
    }

    st.json(meta)

    if processed.content_type == "project":
        st.subheader("Project Summary")
        st.code(processed.text, language="markdown")

        st.subheader("Project Manifest")
        manifest_rows = [
            {
                "path": item.path,
                "extension": item.extension,
                "byte_size": item.byte_size,
                "selected": item.selected,
                "reason": item.reason,
            }
            for item in processed.project_manifest
        ]
        st.dataframe(manifest_rows, use_container_width=True)

        st.subheader("Selected Files")
        selected_rows = [
            {
                "path": item.path,
                "extension": item.extension,
                "byte_size": item.byte_size,
                "char_count": item.char_count,
                "truncated": item.truncated,
            }
            for item in processed.selected_files
        ]
        st.dataframe(selected_rows, use_container_width=True)

        with st.expander("Selected File Contents"):
            for item in processed.selected_files:
                st.markdown(f"### `{item.path}`")
                st.code(item.content[:5000], language="text")
                if len(item.content) > 5000:
                    st.caption("Preview truncated in UI.")

    else:
        st.subheader("Text Preview")
        st.code(processed.text[:8000], language="text")

        if len(processed.text) > 8000:
            st.caption("Preview truncated in UI.")

        if processed.image_base64:
            st.info("Image base64 payload exists and is ready for a vision-capable model.")


def render_formatted_report(formatted: FormattedReport, output_format: str) -> None:
    st.subheader("Audit Report")

    if output_format == "json":
        json_text = formatted.json_text or formatted.report.model_dump_json(indent=2)
        st.code(json_text, language="json")
        st.download_button(
            label="Download JSON Report",
            data=json_text,
            file_name="ragebait_report.json",
            mime="application/json",
        )
        return

    markdown = formatted.markdown or ""
    st.markdown(markdown)

    st.download_button(
        label="Download Markdown Report",
        data=markdown,
        file_name="ragebait_report.md",
        mime="text/markdown",
    )

    json_text = formatted.report.model_dump_json(indent=2)
    st.download_button(
        label="Download Raw JSON",
        data=json_text,
        file_name="ragebait_report.json",
        mime="application/json",
    )


def render_error(exc: Exception) -> None:
    st.error(str(exc))

    with st.expander("Technical details"):
        st.exception(exc)


def main() -> None:
    page_config()
    render_header()

    config = get_config()
    settings = render_sidebar(config)
    input_state = render_input_section()

    st.divider()

    run_button = st.button(
        settings["action"],
        type="primary",
        use_container_width=True,
    )

    if not run_button:
        st.info("Choose an input source, select an action, then run.")
        return

    try:
        request = build_request(input_state, settings)
    except (ValueError, ValidationError) as exc:
        render_error(exc)
        return

    critic = get_critic(settings["use_llm_domain_detection"])

    try:
        if settings["action"] == "Preview Input":
            with st.spinner("Processing input..."):
                processed = run_async(critic.prepare_input(request))
            render_processed_input(processed)
            return

        if settings["action"] == "Detect Only":
            with st.spinner("Processing input and detecting domain/language..."):
                detection = run_async(critic.detect_only(request))
            st.subheader("Detection Result")
            st.json(detection.model_dump(mode="json"))
            return

        with st.spinner("Running full audit through configured LLM provider..."):
            formatted = run_async(critic.audit(request))
        render_formatted_report(formatted, settings["output_format"])

    except RagebaitCriticError as exc:
        render_error(exc)
    except Exception as exc:
        render_error(exc)


if __name__ == "__main__":
    main()
