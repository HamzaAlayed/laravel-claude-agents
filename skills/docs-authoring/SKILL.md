---
name: docs-authoring
description: "Documentation templates + style rules — changelog (Keep a Changelog), release notes, runbook (Symptoms → Triage → Resolve), API endpoint reference block, onboarding guide. Use when writing or restructuring any docs surface so every page lands in a proven shape with tested examples and cited sources."
---

# Docs Authoring

Source of truth is code, schemas, merged PRs — read those, not memory. Cite `path:line` / route / PR # for every non-obvious claim; can't locate it → `TODO`, never a guess.

## Changelog — Keep a Changelog (2.0.0: mark breaking entries `**Breaking:**` + migration step; Security entries lead with CVE id; never auto-convert commits)

`## [x.y.z] - YYYY-MM-DD`, then only the sections that apply: **Added / Changed / Deprecated / Removed / Fixed / Security**. Entries are user-consequences, not commit messages ("Uploads over 10 MB are rejected with a 422" beats "refactor upload validation"). Unreleased section at top; semver discipline: breaking → major, feature → minor, fix → patch.

## Release notes

For humans who don't read diffs: **What's new** (outcome per item, one line, link to docs) · **Breaking changes** (what breaks, exact migration step, deadline) · **Fixes** (symptom users saw, now gone). Lead with the most-requested item. No internal jargon, no PR numbers without titles.

## Runbook — `Symptoms → Triage → Resolve`

- **Symptoms**: what the responder sees — alert name, error message verbatim, affected surface.
- **Triage**: ordered checks with exact commands + what each result means (`php artisan horizon:status` → "inactive means…"). Decision points explicit.
- **Resolve**: numbered steps, copy-pasteable, each with its verification. Rollback path included. **Escalate when**: named condition + who.
- Test the commands against a real system before publishing; note last-verified date. devops-engineer owns the technical steps — structure and clarity live here.

## API endpoint reference block

Per endpoint, always the same order: `METHOD /path` · auth (guard + required Sanctum abilities / scopes) · request schema (from the Form Request — name types, required, defaults) · response schema + example (from the API Resource) · error codes (401/403/404/422/429 with the envelope shape) · rate limit · idempotency behavior if any. Generated (Scribe / Scramble) sections marked clearly so regeneration can't eat handwritten notes.

## Onboarding guide

Outcome-titled ("Ship your first PR", not "Development setup"). Smallest working path first — every command copy-pasteable in order, each with its expected output. Prerequisites explicit with versions. Troubleshooting appendix from real first-week failures, not imagined ones.

## Style rules

- Every page answers one question; can't title it as a question → split it.
- One idea per sentence. Consistent terminology (one name per concept, ever). No interpolated sentence fragments — breaks localisation.
- Code examples tested or labeled illustrative. Show `.env` requirements + artisan commands a reader needs.
- Match the project's existing voice, tense, and person; docs read as one author.
