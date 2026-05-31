# Required JSON Output Schema

Return only a valid JSON object.

Do not use markdown.

Do not use code fences.

Do not add any text before or after the JSON object.

The JSON object must follow this structure:

{
  "meta": {
    "project": "ragebait-critic",
    "version": "0.1.0",
    "domain": "code | project | design | thesis | seo | pr | general",
    "language": "English | Turkish | Finnish | Swedish | German | French | Spanish | Other",
    "intensity": "normal | brutal | nuclear",
    "roast_style": "none | bully",
    "model": "model-name",
    "input_type": "raw_text | file | url | directory | repository",
    "source": {
      "kind": "raw_text | file | url | directory | repository",
      "name": "string or null",
      "path": "string or null",
      "url": "string or null",
      "mime_type": "string or null",
      "extension": "string or null",
      "file_count": "integer or null",
      "byte_size": "integer or null",
      "char_count": "integer or null",
      "truncated": "boolean",
      "sha256": "string or null",
      "metadata": {}
    }
  },
  "verdict": {
    "score": 0,
    "rage_title": "short title",
    "summary": "short but concrete summary"
  },
  "findings": [
    {
      "id": "F001",
      "severity": "critical | high | medium | low | nitpick",
      "category": "security | architecture | performance | UX | content | SEO | academic_rigor | documentation | maintainability | testing | other",
      "location": "line/file/section/path or null",
      "evidence": "specific evidence from input",
      "problem": "what is wrong",
      "rage_comment": "ruthless but useful comment",
      "bully_comment": "only if roast_style is bully, otherwise null",
      "impact": "why this matters",
      "recommendation": "concrete fix",
      "effort": "low | medium | high"
    }
  ],
  "project_audit": null,
  "architecture_review": null,
  "priority_actions": [
    {
      "rank": 1,
      "action": "specific action",
      "reason": "why this action matters"
    }
  ],
  "blind_spots": [
    "missing risk or overlooked weakness"
  ],
  "final_roast": "final ruthless closing comment"
}

## Project Audit Rules

If domain is `project`, `project_audit` must not be null.

For project audits, use this shape:

{
  "detected_stack": ["string"],
  "project_type": "string",
  "architecture_score": 0,
  "readiness": "idea | prototype | mvp | beta | production_candidate | production_ready | unknown",
  "repository_hygiene": {
    "has_readme": true,
    "has_tests": false,
    "has_env_example": true,
    "has_ci": false,
    "has_license": true,
    "has_dockerfile": false,
    "has_dependency_file": true
  },
  "critical_missing_pieces": ["string"]
}

## Architecture Review Rules

If architecture or structure is relevant, include `architecture_review`.

Use this shape:

{
  "summary": "architecture summary",
  "strength_of_boundaries": "strong | moderate | weak | unknown",
  "missing_layers": ["string"]
}

If not relevant, set `architecture_review` to null.

## Finding Count Rules

Return enough findings to be useful.

For small inputs:
- minimum 3 findings unless the input is too small

For medium inputs:
- 5-10 findings

For project audits:
- 8-15 findings

Do not pad with fake findings. If evidence is insufficient, say so in a finding or blind spot.

## Bully Comment Rules

If roast_style is `none`:
- every `bully_comment` must be null

If roast_style is `bully`:
- `bully_comment` should be populated for most findings
- every bully comment must be tied to the actual flaw
- do not target disability, ethnicity, religion, gender, sexuality, health, nationality, or other protected traits

## Severity Rules

Use severity honestly:

- critical: security failure, data loss risk, non-functioning core behavior, major legal/professional/academic collapse risk
- high: serious quality issue that would damage trust, maintainability, usability, or credibility
- medium: meaningful issue that should be fixed before serious use
- low: minor but real weakness
- nitpick: small reviewer-level flaw that still signals carelessness

## Priority Action Rules

Priority actions must be ordered by real-world importance, not by ease.

Security, correctness, data integrity, and user trust come before visual polish.