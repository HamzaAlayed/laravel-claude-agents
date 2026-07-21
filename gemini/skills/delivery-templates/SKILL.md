---
name: delivery-templates
description: "Artifact templates for the planning + coordination roles — requirements doc, user story + acceptance criteria, RICE / WSJF scoring, sprint plan, retro, team-health report, stakeholder update, delivery log. Use when producing any docs/requirements, docs/backlog, docs/roadmap, or docs/sprints artifact, so every document lands in the same shape at the expected path."
---

# Delivery Artifact Templates

One shape per artifact type. Consistent paths — downstream agents and humans navigate by convention.

## Requirements doc — `docs/requirements/<slug>.md`

Sections, in order: **Problem** (one paragraph, evidence-anchored) · **Evidence** (tickets, quotes, telemetry, code paths — cite each) · **Stakeholders** · **In scope / Out of scope** (explicit non-goals) · **User stories + acceptance criteria** · **Risks + open questions** (each with owner + blocking status; guesses labeled `ASSUMPTION — unconfirmed`) · **Traceability** (affected models / routes / jobs). Close with the stakeholder sign-off line.

## User story + acceptance criteria

```
As a <role>, I need <capability> so that <outcome>.

Given <precondition>
When  <action>
Then  <observable result>        # one behavior per criterion, each testable
```

Untestable words banned in criteria: fast, intuitive, user-friendly, robust — replace with a measurable threshold or cut.

## Scoring — one framework per backlog, declared at top

RICE: `(Reach × Impact × Confidence) / Effort` — Reach in users/period, Impact 0.25–3, Confidence as %, Effort in person-weeks from tech-lead sizing.
WSJF: `(Business Value + Time Criticality + Risk Reduction) / Job Size`, relative Fibonacci.
Every number gets a one-sentence justification. Missing input → item marked `provisional`, routed to the owner (Effort/Job Size → tech-lead; Reach/Impact evidence → business-analyst). Never manufacture a score.

Backlog row (`docs/backlog/backlog.md`): `rank | id | title | score (shown math) | owner | status | outcome metric`.

## Sprint plan — `docs/sprints/<sprint-id>.md`

**Goal** (one sentence) · **Capacity** (from measured historical throughput, not vibes) · **Committed stories** (id, owner, dependencies) · **Risks** · **Carry-over** from last sprint with reason.

## Retro — `docs/sprints/<sprint-id>-retro.md`

**Signals** (PR churn, build failures, missed estimates — measured) · **Themes** (clustered) · **Experiments** (1–3 max, each: hypothesis, owner, due date, success signal) · **Prior action items** (done / not done / dropped-with-reason). Systems, not people — no names attached to failures.

## Team-health report — `docs/sprints/health-<yyyy>-W<ww>.md`

Cycle time (PR open → merge, p50/p85) · throughput (merged PRs or completed stories) · blocker count + oldest-blocker age · action-item closure rate. Numbers from git history / PR timestamps / tracker exports only; missing data reported as `insufficient data — need <X>`, never estimated.

## Stakeholder update

Lead with outcomes, not activity: **Shipped + observed effect** · **In flight + expected date** · **Blocked + what unblocks it** · **Decisions needed from you** (each with a recommendation + deadline). One screen. Plain language — no story IDs without titles.

## Stack snapshot — `docs/team/stack.md` (coordinator persists; every agent reads first)

The orientation layer: verified project facts that kill discovery turns. **Store what the
repo can't answer instantly; derive what it can** (hot paths → `git log`, naming → read
siblings). Every fact carries a Verify command — a stale fact followed with perfect
compliance is worse than nothing. Hard cap ~40 lines; over it, you're storing derivables.

```markdown
# Stack — verified facts (refresh: run Verify before relying)

| Fact | Value | Verify |
| ---- | ----- | ------ |
| Laravel | 13.x | `php artisan --version` |
| Runner | Sail | `test -x vendor/bin/sail && ls compose.yaml` |
| Tests | Pest 4 | `grep pestphp/pest composer.json` |
| Queue | Redis + Horizon | `grep -l horizon config/` |

## Where things live
- <one line each: domains, key configs, entry points — only the non-obvious>

## Command quirks
- <exact invocations that differ from defaults, each with why>
```

## Decisions ledger — `docs/team/decisions.md` (coordinator)

Rejected approaches only — the one thing neither git nor code can tell an agent. One
entry per rejection; ADR-worthy decisions go to `docs/adr/` instead, linked from here.

```markdown
## <approach, imperative — e.g. "Cache invoice totals in Redis">
- **Rejected:** <YYYY-MM-DD> — <one-line why (measured result, constraint, human call)>
- **Instead:** <what the team does instead, one line>
```

## Delivery log — `docs/delivery/<feature>/log.md` (coordinator)

Per stage: specialist engaged · brief given (one line) · artifact path returned · verification run + result · human checkpoints flagged/cleared. This is the paper trail — append, never rewrite history.

## Hygiene proposal — `/team-hygiene` output (scrum-master)

Exceptions only, never an inventory; nothing applies without an approved row number.

```markdown
| # | Entry | File | Class | Evidence | Proposal |
|---|-------|------|-------|----------|----------|
| 1 | <entry title> | conventions.md | duplicate / conflict / stale-fact / dead-scope | <twin title · failing Verify output · missing path> | keep / merge into #N / evict / rewrite: <line> |
```

Evictions append `evicted: <title> — <class>, <date>` to decisions.md — the removal is remembered.
