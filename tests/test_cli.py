from __future__ import annotations

import subprocess
import sys


def test_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, "cli.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Ragebait Critic" in result.stdout
    assert "--input" in result.stdout
    assert "--detect-only" in result.stdout


def test_cli_detect_only_text() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "--text",
            "We are excited to announce our revolutionary AI-powered platform.",
            "--domain",
            "auto",
            "--language",
            "auto",
            "--detect-only",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"domain"' in result.stdout
    assert '"used_llm": false' in result.stdout