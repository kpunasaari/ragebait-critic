"""
File, URL, image, and raw text processing for Ragebait Critic.

This module normalizes supported user inputs into the shared ProcessedInput
schema used by the engine, prompt builder, CLI, Streamlit UI, and tool mode.

It intentionally does not scan full project directories. Project scanning is
handled by project_scanner.py.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

import docx2txt
import httpx
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from ragebait_critic.config import RagebaitConfig
from ragebait_critic.exceptions import (
    EmptyInputError,
    FileProcessingError,
    InputTooLargeError,
    UnsupportedFileTypeError,
    URLFetchError,
)
from ragebait_critic.schemas import ProcessedInput, SourceInfo

logger = logging.getLogger(__name__)


class FileProcessor:
    """
    Normalizes raw text, local files, URLs, and image files.

    The output is always a ProcessedInput object.
    """

    TEXT_EXTENSIONS: set[str] = {
        ".txt",
        ".md",
        ".markdown",
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
        ".csv",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".log",
    }

    DOCUMENT_EXTENSIONS: set[str] = {
        ".pdf",
        ".docx",
    }

    IMAGE_EXTENSIONS: set[str] = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".gif",
        ".tiff",
        ".tif",
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
    }

    def __init__(self, config: RagebaitConfig | None = None) -> None:
        self.config = config or RagebaitConfig.from_env()

    async def process_input(self, value: str | Path) -> ProcessedInput:
        """
        Auto-detect and process a raw text block, local file path, or URL.

        Directory handling is intentionally not supported here. Use
        ProjectScanner for project folders.
        """
        if isinstance(value, Path):
            return await self.process_file(value)

        if not isinstance(value, str):
            raise TypeError("Input value must be a string or pathlib.Path.")

        stripped = value.strip()

        if not stripped:
            raise EmptyInputError("Input is empty.")

        if self._is_url(stripped):
            return await self.process_url(stripped)

        possible_path = Path(stripped).expanduser()

        if possible_path.exists():
            if possible_path.is_dir():
                raise UnsupportedFileTypeError(
                    "Directory input is not handled by FileProcessor. "
                    "Use ProjectScanner for project audits."
                )

            if possible_path.is_file():
                return await self.process_file(possible_path)

        return await self.process_raw_text(stripped)

    async def process_raw_text(
        self,
        text: str,
        source_name: str = "inline_text",
    ) -> ProcessedInput:
        """
        Process user-pasted raw text.
        """
        cleaned = self._clean_text(text)

        if not cleaned:
            raise EmptyInputError("Raw text is empty after cleaning.")

        truncated_text, truncated = self._truncate_text(cleaned, self.config.max_extracted_chars)
        encoded = truncated_text.encode("utf-8", errors="replace")

        return ProcessedInput(
            input_type="raw_text",
            content_type="text",
            source=SourceInfo(
                kind="raw_text",
                name=source_name,
                char_count=len(truncated_text),
                byte_size=len(encoded),
                truncated=truncated,
                sha256=self._sha256_bytes(encoded),
                metadata={
                    "original_char_count": len(cleaned),
                    "processed_char_count": len(truncated_text),
                },
            ),
            text=truncated_text,
        )

    async def process_file(self, path: str | Path) -> ProcessedInput:
        """
        Process a supported local file.

        Supported:
        - text/code files
        - PDF
        - DOCX
        - common image formats
        """
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            raise FileProcessingError(f"File does not exist: {file_path}")

        if not file_path.is_file():
            raise FileProcessingError(f"Path is not a file: {file_path}")

        byte_size = file_path.stat().st_size

        if byte_size > self.config.max_file_size_bytes:
            raise InputTooLargeError(
                f"File is too large: {byte_size} bytes. "
                f"Maximum allowed size is {self.config.max_file_size_bytes} bytes."
            )

        extension = file_path.suffix.lower()
        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        logger.info(
            "Processing file: path=%s extension=%s mime_type=%s byte_size=%s",
            file_path,
            extension,
            mime_type,
            byte_size,
        )

        if extension in self.TEXT_EXTENSIONS:
            return await self._process_text_file(file_path, extension, mime_type, byte_size)

        if extension == ".pdf":
            return await self._process_pdf(file_path, extension, mime_type, byte_size)

        if extension == ".docx":
            return await self._process_docx(file_path, extension, mime_type, byte_size)

        if extension in self.IMAGE_EXTENSIONS:
            return await self._process_image(file_path, extension, mime_type, byte_size)

        raise UnsupportedFileTypeError(
            f"Unsupported file extension '{extension}'. "
            f"Supported extensions: {self.supported_extensions_string()}"
        )

    async def process_url(self, url: str) -> ProcessedInput:
        """
        Fetch a single URL and extract readable text from it.

        This is not a crawler. It fetches exactly one URL.
        """
        cleaned_url = url.strip()

        if not self._is_url(cleaned_url):
            raise URLFetchError(f"Invalid URL: {url}")

        logger.info("Fetching URL: %s", cleaned_url)

        headers = {
            "User-Agent": (
                "RagebaitCritic/0.1.0 "
                "(single-page AI audit fetcher; no crawling)"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "text/plain;q=0.8,*/*;q=0.5"
            ),
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.config.request_timeout_seconds,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = await client.get(cleaned_url)
                response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning("URL returned HTTP error: url=%s status=%s", cleaned_url, status_code)
            raise URLFetchError(f"URL returned HTTP {status_code}: {cleaned_url}") from exc

        except httpx.RequestError as exc:
            logger.warning("URL request failed: url=%s error=%s", cleaned_url, exc)
            raise URLFetchError(f"Failed to fetch URL '{cleaned_url}': {exc}") from exc

        raw_bytes = response.content

        if len(raw_bytes) > self.config.max_url_response_bytes:
            raise InputTooLargeError(
                f"URL response is too large: {len(raw_bytes)} bytes. "
                f"Maximum allowed size is {self.config.max_url_response_bytes} bytes."
            )

        content_type_header = response.headers.get("content-type", "")
        mime_type = content_type_header.split(";")[0].strip().lower() or "text/html"

        if not self._is_supported_url_mime_type(mime_type):
            raise URLFetchError(
                f"URL content type is not supported for text extraction: {mime_type}"
            )

        page_text = response.text

        if "html" in mime_type or "<html" in page_text.lower():
            extracted = await asyncio.to_thread(
                self._extract_text_from_html,
                page_text,
                cleaned_url,
            )
        else:
            extracted = page_text

        cleaned = self._clean_text(extracted)

        if not cleaned:
            raise EmptyInputError(f"No usable text could be extracted from URL: {cleaned_url}")

        truncated_text, truncated = self._truncate_text(cleaned, self.config.max_extracted_chars)

        return ProcessedInput(
            input_type="url",
            content_type="text",
            source=SourceInfo(
                kind="url",
                name=cleaned_url,
                url=cleaned_url,
                mime_type=mime_type,
                byte_size=len(raw_bytes),
                char_count=len(truncated_text),
                truncated=truncated,
                sha256=self._sha256_bytes(raw_bytes),
                metadata={
                    "final_url": str(response.url),
                    "status_code": response.status_code,
                    "original_char_count": len(cleaned),
                    "processed_char_count": len(truncated_text),
                },
            ),
            text=truncated_text,
        )

    async def _process_text_file(
        self,
        file_path: Path,
        extension: str,
        mime_type: str,
        byte_size: int,
    ) -> ProcessedInput:
        raw_bytes = await asyncio.to_thread(file_path.read_bytes)
        decoded = self._decode_bytes(raw_bytes)

        if extension in {".html", ".htm"}:
            extracted = await asyncio.to_thread(
                self._extract_text_from_html,
                decoded,
                str(file_path),
            )
        else:
            extracted = decoded

        cleaned = self._clean_text(extracted)

        if not cleaned:
            raise EmptyInputError(f"No usable text extracted from file: {file_path}")

        if extension in self.CODE_EXTENSIONS:
            cleaned = self._add_line_numbers(cleaned)

        truncated_text, truncated = self._truncate_text(cleaned, self.config.max_extracted_chars)

        return ProcessedInput(
            input_type="file",
            content_type="text",
            source=SourceInfo(
                kind="file",
                name=file_path.name,
                path=str(file_path),
                mime_type=mime_type,
                extension=extension,
                byte_size=byte_size,
                char_count=len(truncated_text),
                truncated=truncated,
                sha256=self._sha256_bytes(raw_bytes),
                metadata={
                    "original_char_count": len(cleaned),
                    "processed_char_count": len(truncated_text),
                    "line_numbers_added": extension in self.CODE_EXTENSIONS,
                },
            ),
            text=truncated_text,
        )

    async def _process_pdf(
        self,
        file_path: Path,
        extension: str,
        mime_type: str,
        byte_size: int,
    ) -> ProcessedInput:
        raw_bytes = await asyncio.to_thread(file_path.read_bytes)

        def extract_pdf_text() -> tuple[str, int]:
            try:
                reader = PdfReader(str(file_path))
            except Exception as exc:
                raise FileProcessingError(f"Failed to open PDF: {file_path}") from exc

            pages: list[str] = []

            for index, page in enumerate(reader.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                except Exception as exc:
                    logger.warning(
                        "Failed to extract text from PDF page: file=%s page=%s error=%s",
                        file_path,
                        index,
                        exc,
                    )
                    page_text = ""

                if page_text.strip():
                    pages.append(f"\n\n--- PDF PAGE {index} ---\n{page_text}")

            return "\n".join(pages), len(reader.pages)

        extracted, page_count = await asyncio.to_thread(extract_pdf_text)
        cleaned = self._clean_text(extracted)

        if not cleaned:
            raise EmptyInputError(
                f"No extractable text found in PDF: {file_path}. "
                "This may be a scanned/image-only PDF. OCR is not included in v0.1.0."
            )

        truncated_text, truncated = self._truncate_text(cleaned, self.config.max_extracted_chars)

        return ProcessedInput(
            input_type="file",
            content_type="text",
            source=SourceInfo(
                kind="file",
                name=file_path.name,
                path=str(file_path),
                mime_type=mime_type,
                extension=extension,
                byte_size=byte_size,
                char_count=len(truncated_text),
                truncated=truncated,
                sha256=self._sha256_bytes(raw_bytes),
                metadata={
                    "page_count": page_count,
                    "original_char_count": len(cleaned),
                    "processed_char_count": len(truncated_text),
                    "ocr_supported": False,
                },
            ),
            text=truncated_text,
        )

    async def _process_docx(
        self,
        file_path: Path,
        extension: str,
        mime_type: str,
        byte_size: int,
    ) -> ProcessedInput:
        raw_bytes = await asyncio.to_thread(file_path.read_bytes)

        def extract_docx_text() -> str:
            try:
                return docx2txt.process(str(file_path)) or ""
            except Exception as exc:
                raise FileProcessingError(f"Failed to extract DOCX text: {file_path}") from exc

        extracted = await asyncio.to_thread(extract_docx_text)
        cleaned = self._clean_text(extracted)

        if not cleaned:
            raise EmptyInputError(f"No usable text extracted from DOCX file: {file_path}")

        truncated_text, truncated = self._truncate_text(cleaned, self.config.max_extracted_chars)

        return ProcessedInput(
            input_type="file",
            content_type="text",
            source=SourceInfo(
                kind="file",
                name=file_path.name,
                path=str(file_path),
                mime_type=mime_type,
                extension=extension,
                byte_size=byte_size,
                char_count=len(truncated_text),
                truncated=truncated,
                sha256=self._sha256_bytes(raw_bytes),
                metadata={
                    "original_char_count": len(cleaned),
                    "processed_char_count": len(truncated_text),
                },
            ),
            text=truncated_text,
        )

    async def _process_image(
        self,
        file_path: Path,
        extension: str,
        mime_type: str,
        byte_size: int,
    ) -> ProcessedInput:
        raw_bytes = await asyncio.to_thread(file_path.read_bytes)

        def inspect_image() -> tuple[str, int, int]:
            try:
                with Image.open(file_path) as image:
                    image_format = image.format or extension.replace(".", "").upper()
                    width, height = image.size
                    image.verify()
                    return image_format, width, height
            except UnidentifiedImageError as exc:
                raise FileProcessingError(f"Invalid image file: {file_path}") from exc
            except Exception as exc:
                raise FileProcessingError(f"Failed to inspect image: {file_path}") from exc

        image_format, width, height = await asyncio.to_thread(inspect_image)
        encoded = base64.b64encode(raw_bytes).decode("ascii")

        descriptor = "\n".join(
            [
                "IMAGE_ASSET_FOR_VISION_MODEL",
                f"filename: {file_path.name}",
                f"mime_type: {mime_type}",
                f"extension: {extension}",
                f"format: {image_format}",
                f"width: {width}",
                f"height: {height}",
                f"byte_size: {byte_size}",
                "",
                "The base64 image payload is available in image_base64.",
                "Do not claim visual inspection occurred unless this payload is "
                "sent to a vision-capable model.",
            ]
        )

        return ProcessedInput(
            input_type="file",
            content_type="image",
            source=SourceInfo(
                kind="file",
                name=file_path.name,
                path=str(file_path),
                mime_type=mime_type,
                extension=extension,
                byte_size=byte_size,
                char_count=len(descriptor),
                truncated=False,
                sha256=self._sha256_bytes(raw_bytes),
                metadata={
                    "image_format": image_format,
                    "image_width": width,
                    "image_height": height,
                    "vision_payload_ready": True,
                },
            ),
            text=descriptor,
            image_base64=encoded,
        )

    def _extract_text_from_html(self, html: str, source: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(
            [
                "script",
                "style",
                "noscript",
                "template",
                "svg",
                "canvas",
                "iframe",
                "nav",
                "footer",
            ]
        ):
            tag.decompose()

        title = soup.title.get_text(" ", strip=True) if soup.title else ""

        meta_description = ""
        meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        if meta and meta.get("content"):
            meta_description = str(meta["content"]).strip()

        headings: list[str] = []
        for tag_name in ["h1", "h2", "h3"]:
            for heading in soup.find_all(tag_name):
                heading_text = heading.get_text(" ", strip=True)
                if heading_text:
                    headings.append(f"{tag_name.upper()}: {heading_text}")

        body_text = soup.get_text(separator="\n", strip=True)

        parts = [
            f"SOURCE: {source}",
            f"TITLE: {title}" if title else "",
            f"META_DESCRIPTION: {meta_description}" if meta_description else "",
            "\n".join(headings),
            body_text,
        ]

        return "\n\n".join(part for part in parts if part.strip())

    def _decode_bytes(self, raw_bytes: bytes) -> str:
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]

        for encoding in encodings:
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw_bytes.decode("utf-8", errors="replace")

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""

        cleaned = text.replace("\x00", "")
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
        cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())

        return cleaned.strip()

    def _add_line_numbers(self, text: str) -> str:
        lines = text.splitlines()
        width = max(3, len(str(len(lines))))

        return "\n".join(
            f"{str(index).zfill(width)} | {line}"
            for index, line in enumerate(lines, start=1)
        )

    def _truncate_text(self, text: str, max_chars: int) -> tuple[str, bool]:
        if len(text) <= max_chars:
            return text, False

        head_chars = int(max_chars * 0.7)
        tail_chars = max_chars - head_chars

        truncated = (
            text[:head_chars]
            + "\n\n--- CONTENT TRUNCATED DUE TO SIZE LIMIT ---\n\n"
            + text[-tail_chars:]
        )

        return truncated, True

    def _is_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _is_supported_url_mime_type(self, mime_type: str) -> bool:
        return (
            mime_type.startswith("text/")
            or mime_type in {"application/xhtml+xml", "application/xml"}
        )

    def _sha256_bytes(self, raw_bytes: bytes) -> str:
        return hashlib.sha256(raw_bytes).hexdigest()

    def supported_extensions_string(self) -> str:
        extensions = sorted(
            self.TEXT_EXTENSIONS
            | self.DOCUMENT_EXTENSIONS
            | self.IMAGE_EXTENSIONS
        )
        return ", ".join(extensions)


async def process_input(value: str | Path) -> ProcessedInput:
    """
    Convenience function for one-off input processing.
    """
    processor = FileProcessor()
    return await processor.process_input(value)


async def process_raw_text(text: str) -> ProcessedInput:
    """
    Convenience function for raw text processing.
    """
    processor = FileProcessor()
    return await processor.process_raw_text(text)


async def process_file(path: str | Path) -> ProcessedInput:
    """
    Convenience function for file processing.
    """
    processor = FileProcessor()
    return await processor.process_file(path)


async def process_url(url: str) -> ProcessedInput:
    """
    Convenience function for URL processing.
    """
    processor = FileProcessor()
    return await processor.process_url(url)
