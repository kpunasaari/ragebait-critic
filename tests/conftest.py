"""
Shared pytest fixtures for Ragebait Critic tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ragebait_critic.config import RagebaitConfig


@pytest.fixture()
def test_config() -> RagebaitConfig:
    return RagebaitConfig(
        default_model="test-model",
        default_domain="auto",
        default_language="auto",
        default_intensity="brutal",
        default_roast_style="none",
        default_output_format="markdown",
        max_file_size_mb=25,
        max_url_response_mb=10,
        max_extracted_chars=250_000,
        max_project_files=250,
        max_project_file_size_kb=512,
        max_project_total_chars=400_000,
        request_timeout_seconds=30.0,
        max_retries=0,
        log_level="INFO",
    )


@pytest.fixture()
def sample_code_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "bad_code.py"
    file_path.write_text(
        """
def hello(name):
    print("Hello " + name)

hello("Kai")
""".strip(),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture()
def sample_markdown_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "weak_pr.md"
    file_path.write_text(
        """
# Weak PR Example

We are excited to announce our revolutionary AI-powered platform that creates synergy.
""".strip(),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture()
def sample_project_dir(tmp_path: Path) -> Path:
    root = tmp_path / "messy_saas_project"

    (root / "src" / "api").mkdir(parents=True)
    (root / "src" / "components").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)

    (root / "README.md").write_text(
        """
# Messy SaaS Project

This is a revolutionary AI-powered SaaS platform.

## Setup

Run the app.

## Production

Ready for production.
""".strip(),
        encoding="utf-8",
    )

    (root / "package.json").write_text(
        """
{
  "name": "messy-saas-project",
  "version": "0.1.0",
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "@supabase/supabase-js": "^2.0.0",
    "tailwindcss": "^3.4.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}
""".strip(),
        encoding="utf-8",
    )

    (root / ".env.example").write_text(
        """
NEXT_PUBLIC_SUPABASE_URL=your_url_here
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key_here
""".strip(),
        encoding="utf-8",
    )

    (root / ".env").write_text(
        """
SECRET_DATABASE_PASSWORD=do_not_read_this
OPENAI_API_KEY=secret
""".strip(),
        encoding="utf-8",
    )

    (root / "src" / "api" / "auth.ts").write_text(
        """
export async function POST(req: Request) {
  const body = await req.json()
  const query = "SELECT * FROM users WHERE email = '" + body.email + "'"
  return Response.json({ query })
}
""".strip(),
        encoding="utf-8",
    )

    (root / "src" / "components" / "Dashboard.tsx").write_text(
        """
export function Dashboard(props: any) {
  const users = props.users

  return (
    <div>
      <h1>Dashboard</h1>
      {users.map((user: any) => (
        <div>
          <span>{user.name}</span>
          <button onClick={() => alert(user.email)}>Open</button>
        </div>
      ))}
    </div>
  )
}
""".strip(),
        encoding="utf-8",
    )

    (root / ".github" / "workflows" / "ci.yml").write_text(
        """
name: CI

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "No tests yet"
""".strip(),
        encoding="utf-8",
    )

    return root


@pytest.fixture()
def valid_audit_json() -> str:
    return """
{
  "meta": {
    "project": "ragebait-critic",
    "version": "0.1.0",
    "domain": "code",
    "language": "English",
    "intensity": "brutal",
    "roast_style": "none",
    "model": "test-model",
    "input_type": "raw_text",
    "source": {
      "kind": "raw_text",
      "name": "inline_text",
      "path": null,
      "url": null,
      "mime_type": null,
      "extension": null,
      "file_count": null,
      "byte_size": null,
      "char_count": 100,
      "truncated": false,
      "sha256": null,
      "metadata": {}
    }
  },
  "verdict": {
    "score": 35,
    "rage_title": "A tiny function pretending to be engineering",
    "summary": "The snippet is small, but it still shows weak discipline."
  },
  "findings": [
    {
      "id": "F001",
      "severity": "medium",
      "category": "maintainability",
      "location": "inline_text",
      "evidence": "The function has no input validation.",
      "problem": "The implementation lacks defensive structure.",
      "rage_comment": "This is less engineering and more a keyboard warm-up.",
      "bully_comment": null,
      "impact": "The pattern does not scale.",
      "recommendation": "Define input expectations and add testable behavior.",
      "effort": "low"
    }
  ],
  "project_audit": null,
  "architecture_review": null,
  "priority_actions": [
    {
      "rank": 1,
      "action": "Add explicit input expectations.",
      "reason": "Even small functions need clear contracts."
    }
  ],
  "blind_spots": [
    "No test context was provided."
  ],
  "final_roast": "Tiny code, tiny ambition, still enough room for mistakes."
}
""".strip()