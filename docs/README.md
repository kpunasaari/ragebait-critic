# Ragebait Critic

A ruthless, evidence-based AI audit engine for code, local projects, design briefs, academic writing, SEO content, PR copy, product ideas, and general written work.

Repository: https://github.com/kpunasaari/ragebait-critic

## What It Does

Ragebait Critic reviews submitted material with a direct, no-sugarcoating audit style. It is designed to identify real weaknesses, missing evidence, fragile assumptions, structural problems, implementation risks, and unclear decisions.

It is not a joke generator. It is not a generic chatbot wrapper. It is an audit engine that produces structured criticism backed by the submitted evidence.

Ragebait Critic can review:

- Source code
- Local project folders
- Product and startup ideas
- Design briefs
- Academic or thesis text
- SEO content
- PR and marketing copy
- General written material

## Why It Exists

Most AI review tools are too polite. They summarize, praise, and avoid hard conclusions.

Ragebait Critic exists because weak work does not improve through vague encouragement. It improves when problems are identified clearly, prioritized correctly, and explained with evidence.

The goal is simple:

Find what is broken, explain why it matters, and tell the user what to fix first.

## Supported Domains

Ragebait Critic supports the following audit domains:

- `code`
- `project`
- `design`
- `thesis`
- `seo`
- `pr`
- `general`

The domain can be selected manually or detected automatically depending on the input and workflow.

## Intensity Levels

The audit intensity controls how direct and aggressive the critique should be.

Available levels:

- `normal` — direct but controlled
- `brutal` — sharper, more confrontational, still evidence-based
- `nuclear` — maximum severity for serious flaws, still bound by safety rules

Intensity affects tone and strictness, not factual standards.

## Roast Style

Available roast styles:

- `none` — serious audit only
- `bully` — optional harsh comedic framing

The `bully` style is not allowed to invent flaws, attack protected traits, or replace evidence-based critique with insults. It only changes the presentation layer.

## Installation

Clone the repository:

```bash
git clone https://github.com/kpunasaari/ragebait-critic.git
cd ragebait-critic