"""
Project scanner for Ragebait Critic.

This module scans local project directories and converts them into ProcessedInput
objects suitable for project/repository audits.

It deliberately avoids reading dangerous or noisy content such as:
- .env files
- .git internals
- node_modules
- virtual environments
- build outputs
- caches
- binary assets
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
from pathlib import Path

from ragebait_critic.config import RagebaitConfig
from ragebait_critic.exceptions import EmptyInputError, ProjectScanError, UnsafeInputError
from ragebait_critic.schemas import ProcessedInput, ProjectFileContent, ProjectFileInfo, SourceInfo

logger = logging.getLogger(__name__)


class ProjectScanner:
    """
    Scans a local project directory and extracts high-signal files for audit.
    """

    IGNORED_DIR_NAMES: set[str] = {
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".cache",
        ".next",
        ".nuxt",
        ".svelte-kit",
        "node_modules",
        "bower_components",
        "vendor",
        ".venv",
        "venv",
        "env",
        "ENV",
        "dist",
        "build",
        "out",
        "coverage",
        "htmlcov",
        "target",
        ".turbo",
        ".parcel-cache",
        "logs",
        "tmp",
        "temp",
    }

    IGNORED_FILE_NAMES: set[str] = {
        ".env",
        ".env.local",
        ".env.development",
        ".env.production",
        ".env.test",
        ".env.staging",
        "npm-debug.log",
        "yarn-error.log",
        "pnpm-debug.log",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
    }

    IMPORTANT_FILE_NAMES: set[str] = {
        "README.md",
        "README.rst",
        "README.txt",
        "LICENSE",
        "LICENSE.md",
        "COPYING",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        ".env.example",
        ".env.sample",
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "package.json",
        "tsconfig.json",
        "jsconfig.json",
        "next.config.js",
        "next.config.mjs",
        "vite.config.js",
        "vite.config.ts",
        "tailwind.config.js",
        "tailwind.config.ts",
        "postcss.config.js",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        "vercel.json",
        "netlify.toml",
        "supabase/config.toml",
        "prisma/schema.prisma",
        "alembic.ini",
        "pytest.ini",
        "ruff.toml",
        ".prettierrc",
        ".eslintrc",
        ".eslintrc.json",
        ".eslintrc.js",
        "eslint.config.js",
        "mypy.ini",
    }

    IMPORTANT_DIR_PARTS: set[str] = {
        "src",
        "app",
        "pages",
        "api",
        "routes",
        "router",
        "server",
        "backend",
        "frontend",
        "components",
        "lib",
        "utils",
        "services",
        "models",
        "schemas",
        "db",
        "database",
        "migrations",
        "prisma",
        "supabase",
        "auth",
        "middleware",
        "hooks",
        "store",
        "state",
        "prompts",
        "agents",
        "tools",
        "tests",
        "test",
        "__tests__",
        ".github",
        "workflows",
        "docs",
        "examples",
        "config",
    }

    TEXT_EXTENSIONS: set[str] = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".md",
        ".mdx",
        ".txt",
        ".rst",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".env.example",
        ".sample",
        ".sql",
        ".prisma",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".dockerfile",
        ".gitignore",
        ".gitattributes",
        ".xml",
    }

    BINARY_EXTENSIONS: set[str] = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".rar",
        ".mp3",
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".dylib",
        ".exe",
    }

    STACK_PATTERNS: dict[str, list[str]] = {
        "Python": ["pyproject.toml", "requirements.txt", "setup.py", ".py"],
        "FastAPI": ["fastapi", "uvicorn"],
        "Django": ["django", "manage.py"],
        "Flask": ["flask"],
        "JavaScript": ["package.json", ".js"],
        "TypeScript": ["tsconfig.json", ".ts", ".tsx"],
        "React": ["react", "jsx", "tsx"],
        "Next.js": ["next.config.js", "next.config.mjs", "next"],
        "Vite": ["vite.config.js", "vite.config.ts", "vite"],
        "Tailwind": ["tailwind.config.js", "tailwind.config.ts", "tailwindcss"],
        "Supabase": ["supabase", "@supabase"],
        "Prisma": ["prisma/schema.prisma", "prisma"],
        "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
        "Streamlit": ["streamlit"],
        "LiteLLM": ["litellm"],
        "Pydantic": ["pydantic"],
    }

    def __init__(self, config: RagebaitConfig | None = None) -> None:
        self.config = config or RagebaitConfig.from_env()

    async def scan(self, path: str | Path) -> ProcessedInput:
        """
        Scan a local project directory and return ProcessedInput.
        """
        root = Path(path).expanduser().resolve()

        if not root.exists():
            raise ProjectScanError(f"Project directory does not exist: {root}")

        if not root.is_dir():
            raise ProjectScanError(f"Path is not a directory: {root}")

        logger.info("Scanning project directory: %s", root)

        manifest = self._build_manifest(root)

        if not manifest:
            raise EmptyInputError(f"No usable files found in project directory: {root}")

        selected_manifest = self._select_files(manifest)
        selected_contents = self._read_selected_files(root, selected_manifest)

        if not selected_contents:
            raise EmptyInputError(
                "Project scan found files, but none could be safely selected for audit."
            )

        project_summary = self._build_project_summary(
            root=root,
            manifest=manifest,
            selected_contents=selected_contents,
        )

        digest_source = "\n".join(item.path for item in manifest).encode(
            "utf-8",
            errors="replace",
        )
        digest = hashlib.sha256(digest_source).hexdigest()

        truncated = (
            len(manifest) > self.config.max_project_files
            or sum(item.char_count for item in selected_contents)
            >= self.config.max_project_total_chars
        )

        return ProcessedInput(
            input_type="directory",
            content_type="project",
            source=SourceInfo(
                kind="directory",
                name=root.name,
                path=str(root),
                file_count=len(manifest),
                char_count=(
                    len(project_summary)
                    + sum(item.char_count for item in selected_contents)
                ),
                truncated=truncated,
                sha256=digest,
                metadata={
                    "selected_file_count": len(selected_contents),
                    "max_project_files": self.config.max_project_files,
                    "max_project_file_size_kb": self.config.max_project_file_size_kb,
                    "max_project_total_chars": self.config.max_project_total_chars,
                    "repository_hygiene": self._repository_hygiene_flags(manifest),
                    "detected_stack": self._detect_stack(manifest, selected_contents),
                },
            ),
            text=project_summary,
            project_manifest=manifest,
            selected_files=selected_contents,
        )

    def _build_manifest(self, root: Path) -> list[ProjectFileInfo]:
        manifest: list[ProjectFileInfo] = []

        for file_path in root.rglob("*"):
            if len(manifest) >= self.config.max_project_files:
                logger.info(
                    "Project file manifest limit reached: %s",
                    self.config.max_project_files,
                )
                break

            if not file_path.is_file():
                continue

            if self._should_ignore_path(file_path, root):
                continue

            try:
                byte_size = file_path.stat().st_size
            except OSError as exc:
                logger.warning("Cannot stat file: %s error=%s", file_path, exc)
                continue

            relative_path = self._relative_posix(file_path, root)
            extension = self._extension_for_path(file_path)

            manifest.append(
                ProjectFileInfo(
                    path=relative_path,
                    extension=extension,
                    byte_size=byte_size,
                    selected=False,
                    reason=None,
                )
            )

        manifest.sort(key=lambda item: item.path.lower())
        return manifest

    def _select_files(self, manifest: list[ProjectFileInfo]) -> list[ProjectFileInfo]:
        selected: list[ProjectFileInfo] = []

        for item in manifest:
            reason = self._selection_reason(item)

            if reason is None:
                continue

            if item.byte_size > self.config.max_project_file_size_bytes:
                reason = f"{reason}; selected but will be truncated due to file size"

            selected.append(
                ProjectFileInfo(
                    path=item.path,
                    extension=item.extension,
                    byte_size=item.byte_size,
                    selected=True,
                    reason=reason,
                )
            )

        selected.sort(key=self._selection_priority)

        max_selected = min(len(selected), self.config.max_project_files)
        return selected[:max_selected]

    def _read_selected_files(
        self,
        root: Path,
        selected_manifest: list[ProjectFileInfo],
    ) -> list[ProjectFileContent]:
        contents: list[ProjectFileContent] = []
        total_chars = 0

        for item in selected_manifest:
            if total_chars >= self.config.max_project_total_chars:
                logger.info(
                    "Project total char limit reached: %s",
                    self.config.max_project_total_chars,
                )
                break

            path = (root / item.path).resolve()

            if not self._is_relative_to(path, root):
                raise UnsafeInputError(f"Refusing to read path outside project root: {path}")

            if not path.exists() or not path.is_file():
                continue

            if self._is_secret_file(path):
                logger.warning("Refusing to read secret-like file: %s", path)
                continue

            if self._is_binary_or_unsupported(path):
                continue

            try:
                raw_bytes = path.read_bytes()
            except OSError as exc:
                logger.warning("Failed to read file: %s error=%s", path, exc)
                continue

            decoded = self._decode_bytes(raw_bytes)
            cleaned = self._clean_text(decoded)

            if not cleaned:
                continue

            if self._extension_for_path(path) in {
                ".py",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".css",
                ".html",
                ".htm",
            }:
                cleaned = self._add_line_numbers(cleaned)

            remaining_chars = self.config.max_project_total_chars - total_chars
            max_chars_for_file = min(self.config.max_project_file_size_bytes, remaining_chars)

            truncated_content, truncated = self._truncate_text(cleaned, max_chars_for_file)

            contents.append(
                ProjectFileContent(
                    path=item.path,
                    extension=item.extension,
                    content=truncated_content,
                    byte_size=len(raw_bytes),
                    char_count=len(truncated_content),
                    truncated=truncated,
                )
            )

            total_chars += len(truncated_content)

        return contents

    def _build_project_summary(
        self,
        root: Path,
        manifest: list[ProjectFileInfo],
        selected_contents: list[ProjectFileContent],
    ) -> str:
        hygiene = self._repository_hygiene_flags(manifest)
        stack = self._detect_stack(manifest, selected_contents)

        top_level_dirs = sorted(
            {
                item.path.split("/")[0]
                for item in manifest
                if "/" in item.path and item.path.split("/")[0]
            }
        )

        top_level_files = sorted(item.path for item in manifest if "/" not in item.path)
        extension_counts = self._extension_counts(manifest)
        selected_paths = [item.path for item in selected_contents]

        summary_sections = [
            "# Project Scan Summary",
            f"project_name: {root.name}",
            f"project_path: {root}",
            f"total_manifest_files: {len(manifest)}",
            f"selected_files_for_audit: {len(selected_contents)}",
            "",
            "## Detected Stack Signals",
            "\n".join(f"- {item}" for item in stack) if stack else "- unknown",
            "",
            "## Repository Hygiene Signals",
            "\n".join(f"- {key}: {value}" for key, value in hygiene.items()),
            "",
            "## Top-Level Directories",
            "\n".join(f"- {item}" for item in top_level_dirs) if top_level_dirs else "- none",
            "",
            "## Top-Level Files",
            "\n".join(f"- {item}" for item in top_level_files) if top_level_files else "- none",
            "",
            "## Extension Counts",
            "\n".join(f"- {key}: {value}" for key, value in extension_counts.items())
            if extension_counts
            else "- none",
            "",
            "## Selected Files",
            "\n".join(f"- {item}" for item in selected_paths) if selected_paths else "- none",
        ]

        return "\n".join(summary_sections).strip()

    def _should_ignore_path(self, file_path: Path, root: Path) -> bool:
        relative_parts = file_path.relative_to(root).parts

        for part in relative_parts[:-1]:
            if part in self.IGNORED_DIR_NAMES:
                return True

        name = file_path.name

        if name in self.IGNORED_FILE_NAMES:
            return True

        if self._is_secret_file(file_path):
            return True

        return self._is_binary_or_unsupported(file_path)

    def _is_secret_file(self, file_path: Path) -> bool:
        name = file_path.name.lower()

        if (name == ".env" or name.startswith(".env.")) and name not in {
            ".env.example",
            ".env.sample",
        }:
            return True

        secret_name_patterns = [
            "id_rsa",
            "id_dsa",
            "id_ecdsa",
            "id_ed25519",
            "private_key",
            "secret",
            "secrets",
            "credentials",
            "service-account",
            "service_account",
        ]

        return any(pattern in name for pattern in secret_name_patterns)

    def _is_binary_or_unsupported(self, file_path: Path) -> bool:
        extension = self._extension_for_path(file_path)
        name = file_path.name

        if extension in self.BINARY_EXTENSIONS:
            return True

        if name in {"Dockerfile", ".gitignore", ".gitattributes"}:
            return False

        if name in self.IMPORTANT_FILE_NAMES:
            return False

        if extension in self.TEXT_EXTENSIONS:
            return False

        mime_type = mimetypes.guess_type(str(file_path))[0] or ""

        return not mime_type.startswith("text/")

    def _selection_reason(self, item: ProjectFileInfo) -> str | None:
        path = item.path
        name = Path(path).name
        lower_path = path.lower()
        extension = item.extension or ""

        if name in self.IMPORTANT_FILE_NAMES:
            return "important root/config/documentation file"

        if lower_path.startswith(".github/workflows/"):
            return "ci workflow file"

        if extension in {".py", ".js", ".jsx", ".ts", ".tsx"} and self._path_contains_important_dir(
            path
        ):
            return "source code in important project directory"

        if extension in {".md", ".mdx", ".rst"} and (
            self._path_contains_important_dir(path) or name.lower().startswith("readme")
        ):
            return "documentation or markdown project context"

        if extension in {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg"} and (
            self._path_contains_important_dir(path) or "/" not in path
        ):
            return "configuration or structured metadata"

        if extension in {".sql", ".prisma"}:
            return "database schema or migration signal"

        if extension in {".html", ".css", ".scss", ".sass"} and self._path_contains_important_dir(
            path
        ):
            return "frontend/UI implementation signal"

        if extension in {".sh", ".bash", ".zsh", ".ps1"} and (
            "/" not in path or self._path_contains_important_dir(path)
        ):
            return "script or automation file"

        return None

    def _selection_priority(self, item: ProjectFileInfo) -> tuple[int, int, str]:
        path = item.path
        name = Path(path).name

        if name in {"README.md", "README.rst", "README.txt"}:
            return (0, item.byte_size, path)

        if name in {"package.json", "pyproject.toml", "requirements.txt"}:
            return (1, item.byte_size, path)

        if name in {".env.example", ".env.sample"}:
            return (2, item.byte_size, path)

        if name in {"LICENSE", "LICENSE.md", "Dockerfile"}:
            return (3, item.byte_size, path)

        if path.startswith(".github/workflows/"):
            return (4, item.byte_size, path)

        if self._path_contains_any(
            path,
            {"auth", "api", "server", "backend", "middleware", "db", "database"},
        ):
            return (5, item.byte_size, path)

        if self._path_contains_any(path, {"src", "app", "lib", "services", "schemas"}):
            return (6, item.byte_size, path)

        if self._path_contains_any(path, {"tests", "test", "__tests__"}):
            return (7, item.byte_size, path)

        if self._path_contains_any(path, {"docs", "examples", "prompts"}):
            return (8, item.byte_size, path)

        return (9, item.byte_size, path)

    def _repository_hygiene_flags(self, manifest: list[ProjectFileInfo]) -> dict[str, bool]:
        paths = {item.path for item in manifest}
        lower_paths = {item.path.lower() for item in manifest}
        names = {Path(item.path).name for item in manifest}
        lower_names = {name.lower() for name in names}

        return {
            "has_readme": any(name.startswith("readme") for name in lower_names),
            "has_tests": any(
                path.startswith(("tests/", "test/"))
                or "/tests/" in path
                or "/test/" in path
                or "/__tests__/" in path
                for path in lower_paths
            ),
            "has_env_example": any(
                name in {".env.example", ".env.sample"} for name in lower_names
            ),
            "has_ci": any(path.startswith(".github/workflows/") for path in lower_paths),
            "has_license": any(
                name in {"license", "license.md", "copying"} for name in lower_names
            ),
            "has_dockerfile": "Dockerfile" in names or "dockerfile" in lower_names,
            "has_dependency_file": any(
                file_name in paths
                for file_name in {
                    "requirements.txt",
                    "pyproject.toml",
                    "package.json",
                    "Pipfile",
                    "setup.py",
                    "setup.cfg",
                }
            ),
        }

    def _detect_stack(
        self,
        manifest: list[ProjectFileInfo],
        selected_contents: list[ProjectFileContent],
    ) -> list[str]:
        haystack_parts: list[str] = []

        for item in manifest:
            haystack_parts.append(item.path.lower())
            if item.extension:
                haystack_parts.append(item.extension.lower())

        for content in selected_contents:
            haystack_parts.append(content.path.lower())
            haystack_parts.append(content.content[:20_000].lower())

        haystack = "\n".join(haystack_parts)

        detected: list[str] = []

        for stack_name, signals in self.STACK_PATTERNS.items():
            for signal in signals:
                if signal.lower() in haystack:
                    detected.append(stack_name)
                    break

        return sorted(set(detected))

    def _extension_counts(self, manifest: list[ProjectFileInfo]) -> dict[str, int]:
        counts: dict[str, int] = {}

        for item in manifest:
            key = item.extension or "[no extension]"
            counts[key] = counts.get(key, 0) + 1

        return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))

    def _path_contains_important_dir(self, path: str) -> bool:
        return self._path_contains_any(path, self.IMPORTANT_DIR_PARTS)

    def _path_contains_any(self, path: str, parts: set[str]) -> bool:
        lowered_parts = {part.lower() for part in Path(path).parts}
        normalized = path.replace("\\", "/").lower()
        split_parts = set(normalized.split("/"))
        return bool(lowered_parts.intersection(parts) or split_parts.intersection(parts))

    def _extension_for_path(self, path: Path) -> str | None:
        name = path.name

        if name == "Dockerfile":
            return ".dockerfile"

        if name in {".gitignore", ".gitattributes"}:
            return name

        suffix = path.suffix.lower()

        if name in {".env.example", ".env.sample"}:
            return name

        return suffix or None

    def _relative_posix(self, file_path: Path, root: Path) -> str:
        return file_path.relative_to(root).as_posix()

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

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
            f"{str(index).rjust(width)} | {line}"
            for index, line in enumerate(lines, start=1)
        )

    def _truncate_text(self, text: str, max_chars: int) -> tuple[str, bool]:
        if max_chars <= 0:
            return "", True

        if len(text) <= max_chars:
            return text, False

        if max_chars < 1000:
            return text[:max_chars], True

        head_chars = int(max_chars * 0.7)
        tail_chars = max_chars - head_chars

        truncated = (
            text[:head_chars]
            + "\n\n--- FILE CONTENT TRUNCATED DUE TO PROJECT SCAN LIMIT ---\n\n"
            + text[-tail_chars:]
        )

        return truncated, True


async def scan_project(path: str | Path) -> ProcessedInput:
    """
    Convenience function for one-off project scanning.
    """
    scanner = ProjectScanner()
    return await scanner.scan(path)
