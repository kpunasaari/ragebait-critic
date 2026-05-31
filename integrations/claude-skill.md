# Ragebait Critic — Claude Skill Integration Guide

Ragebait Critic is a local AI audit tool for reviewing code, project repositories, documents, copy, SEO content, academic text, design briefs, and product ideas.

It is designed to produce ruthless, evidence-based audit reports that can be consumed by humans or by coding agents.

The preferred integration mode for Claude is CLI JSON output.

---

## Primary Use Case

Use Ragebait Critic before refactoring, shipping, rewriting, or expanding a project.

It is especially useful when the user asks:

- "Review this project brutally."
- "Find hidden issues before I publish this."
- "Audit this SaaS repo."
- "Tell me what is wrong with this code."
- "Give me a harsh project quality report."
- "Use the Ragebait Critic report as the basis for fixes."

---

## Recommended Workflow

1. Run Ragebait Critic against the target file, text, URL, or project.
2. Save the report as JSON.
3. Read the JSON report.
4. Extract critical and high severity findings.
5. Build a concrete implementation plan.
6. Fix issues in priority order.
7. Run tests and linters.
8. Re-run Ragebait Critic.
9. Compare before/after results.

---

## Full Project Audit

Use this command when reviewing a complete repository or SaaS project:

```bash
python cli.py --input ./my-project --domain project --intensity nuclear --roast-style bully --format json --output ragebait_report.json