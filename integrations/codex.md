# Ragebait Critic — Codex Usage Guide

Ragebait Critic can be used as a local quality gate before asking Codex or another coding agent to modify a repository.

The best workflow is:

1. Run Ragebait Critic.
2. Save the JSON report.
3. Ask Codex to fix the highest-impact findings.
4. Run tests.
5. Re-run Ragebait Critic.
6. Compare before/after results.

---

## Full Project Audit

Use this command for a complete project or SaaS repository:

```bash
python cli.py --input ./my-project --domain project --intensity nuclear --roast-style bully --format json --output ragebait_report.json