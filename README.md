# Ragebait Critic

Get your work destroyed by AI before your users, clients, reviewers, investors, or competitors do it for free.

Ragebait Critic is an open-source AI audit engine that reviews code, local project repositories, design briefs, academic writing, SEO content, PR copy, and product ideas with ruthless, evidence-based criticism.

It is designed for developers, founders, students, writers, and builders who want to find hidden flaws before the real world finds them louder, meaner, and without giving them a JSON report.

---

## What It Does

Ragebait Critic takes one of the following inputs:

- raw text
- a local file
- a URL
- a local project directory

Then it produces a structured audit report containing:

- an unforgiving score
- concrete findings
- severity levels
- evidence
- impact analysis
- recommendations
- priority actions
- blind spots
- optional project/repository audit metadata
- optional bully-style roast comments

The canonical output is structured JSON. Markdown is a human-readable rendering of that JSON.

---

## Why This Exists

Most AI review tools are too polite.

They say things like:

> "This is a good start."

Ragebait Critic does not care about your emotional support needs.

It is built to answer:

- What is actually broken?
- What looks amateur?
- What would a harsh reviewer attack?
- What would a customer hate?
- What would a competitor mock?
- What would make this fail in production?
- What should be fixed first?

The roast is the packaging. The value is the evidence.

---

## Supported Audit Domains

Ragebait Critic supports the following domains:

| Domain | Use case |
|---|---|
| `code` | Source code and implementation files |
| `project` | Local project folders and SaaS repositories |
| `design` | UI/UX descriptions, design briefs, image payloads |
| `thesis` | Academic writing, research proposals, papers |
| `seo` | SEO pages, keyword content, HTML pages |
| `pr` | PR copy, marketing text, launch announcements, pitch text |
| `general` | Anything that does not fit cleanly elsewhere |

Use `auto` to let Ragebait Critic detect the domain.

---

## Intensity Levels

| Intensity | Description |
|---|---|
| `normal` | Direct, clinical, professionally unforgiving |
| `brutal` | Harsh, sarcastic, aggressively critical |
| `nuclear` | Maximum severity, hostile-reviewer mode |

---

## Optional Roast Style

Ragebait Critic supports an optional roast style:

| Roast style | Description |
|---|---|
| `none` | No extra bully comments |
| `bully` | Opt-in stand-up bully style with flaw-grounded roast comments |

Bully mode is not a replacement for the audit. It adds comedic pressure while keeping every joke tied to an actual flaw.

It does not target protected traits, disabilities, ethnicity, religion, gender, sexuality, health, nationality, or other sensitive personal attributes.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/kpunasaari/ragebait-critic.git
cd ragebait-critic