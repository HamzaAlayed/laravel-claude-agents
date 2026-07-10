# Authoring Laravel agents

This is the deep-dive on writing agents for this pack. The agents are not generic prompts — they are opinionated, Laravel-literate specialists with a deliberate voice. The goal of this guide is to help your agent fit in: read like it was written by the same hand, know the same primitives, and refuse the same mistakes.

If you just need the rules-at-a-glance, see [`CONTRIBUTING.md`](../CONTRIBUTING.md). This document explains the *why*.

## Anatomy of an agent file

An agent is a single Markdown file in `agents/`. It has two parts: YAML frontmatter that tells Claude Code *what the agent is and what it may touch*, and a Markdown body that *is the agent's system prompt*.

```yaml
---
name: backend-developer          # kebab-case, matches the filename
description: Expert Laravel backend. HTTP, Eloquent, queues, events...
                                 # dense, specific, says when to use it PROACTIVELY
tools: Read, Write, Edit, Bash, Grep, Glob   # only what the role needs
model: sonnet                    # opus | sonnet | haiku
color: green                     # display color
isolation: worktree              # builders that edit code — isolated git worktree
# memory: project                # roles that accumulate project knowledge
# disallowedTools: Edit, Write   # reviewers: explicitly forbidden from editing
# skills: ...                    # AVOID — preloads full skill content on every invocation.
#                                # Instead: put Skill in tools + a "Skill on demand: `name` when <trigger>" body line.
---

Expert Laravel engineer. Think contracts, invariants, failure modes,
concurrency. Use Laravel idioms. Code must survive traffic spikes, flaky
APIs, partial failures.

## Principles
- ...

## When invoked
1. ...

## Anti-patterns (refuse to ship)
- ...

## Handoffs
- **Database Developer** — migrations, indexes, query plans
- ...

**Human checkpoint required:** authn, authz, billing, PII, tenant isolation, money.
```

The body opens with the guild identity line (`You are **<Name>** — the Guild's <role>.`), then a one-line role statement (no heading), then the standard sections. Every agent has a guild name — the Laravel-ecosystem tool closest to its craft (see the README roster); when authoring a new agent, pick an unused ecosystem name and add it to the README table and `scripts/board.html`'s `GUILD` map. The `description` is load-bearing: it is what the orchestrator routes on, so it must state the role *and* the conditions under which the agent should fire proactively — and it opens with the same guild name (`<Name> — the Guild's <role>. …`) so name-addressed delegation ("have Artisan …") routes correctly.

## The house voice

The agents are terse, fragment-heavy, imperative, and relentlessly concrete. Every line should either state a belief or issue an instruction. Cut articles, hedges, and throat-clearing. Name the actual Laravel primitive instead of describing it.

**Before (verbose):**

> When you are building an endpoint, you should make sure that the controller stays thin and that the business logic is placed in a dedicated class. It is generally a good idea to validate the incoming request and to make sure that the user is authorized to perform the action.

**After (house style):**

> Skinny controllers. `input → action → response`. Logic in Actions (`App\Actions\...`), never controllers. Validate in a `FormRequest`. Authorize via Policy + `$this->authorize()` — no ad-hoc ownership checks.

**Before:**

> Be careful about the N+1 query problem, which can cause performance issues if you are not eager loading your relationships properly.

**After:**

> N+1: zero tolerance. Eager-load list endpoints with `with()` / `withCount`. `preventLazyLoading()` in non-prod. Fix at source.

The second version of each is shorter *and* more useful, because it names the exact tool the agent should reach for. Vague advice the agent already knows; concrete advice is the value you add.

## Choosing tools

Grant the minimum. A role's tool list is also a statement of intent.

- **Builders** (backend, frontend, database, mobile, package) get `Read, Write, Edit, Bash, Grep, Glob` — they write code and run it.
- **Reviewers** (`tech-lead`, `security-engineer`) get `Read, Bash, Grep, Glob` and explicitly set `disallowedTools: Edit, Write`. This is not a formality. A review that quietly rewrites the code it reviews destroys the paper trail and the author's learning. Reviewers **report findings** with exact `path/to/file.php:line` references and rationale; the responsible builder applies the fix. Security fixes in particular need explicit human awareness — a silent patch hides the vulnerability instead of surfacing it.
- Add `WebFetch` / `WebSearch` only when the role genuinely needs external lookup (e.g. security CVE research).

## `isolation: worktree`

Set this on any agent that **edits code**. It runs the agent in an isolated git worktree, so multiple builders can work in parallel without stepping on each other's files, and a half-finished change never pollutes the main working tree. In this pack the builders — `backend-developer`, `frontend-developer`, `database-developer`, `mobile-developer`, `package-developer` — all use it. Read-only reviewers do not need it.

## `memory: project`

Set this on roles whose value compounds across sessions — they should remember project-specific conventions, recurring anti-patterns, prior decisions, and tech-debt items. In this pack that is the **architects, leads, security, the data layer, and the orchestration/coordination roles** (`solution-architect`, `tech-lead`, `security-engineer`, `database-developer`, `product-owner`, `business-analyst`, `scrum-master`, `delivery-coordinator`, and design). Give these agents a short **## Memory** section telling them what is worth retaining (e.g. "coding conventions enforced enough to be canon, recurring anti-patterns and the comments that addressed them, tech-debt items and their estimated cost"). Builders generally don't carry project memory — they detect the stack fresh each time.

## The taught-rules ledger

Per-agent memory is private and Claude-only; what the user teaches must reach **every** agent, including the memoryless builders and the Gemini/Codex mirrors. That's `docs/team/conventions.md` — user-taught rules in a Rule / Why / Scope / Source shape, written by the `/teach` command or the `delivery-coordinator` when the human corrects an approach mid-delivery. Every agent's first principle ("Taught rules win") makes it read the ledger before starting and treat its entries as overrides. When authoring a new agent, keep that principle as the first bullet — a taught rule the agent doesn't read is a correction the user gets to repeat.

## Handoffs

No agent owns the whole pipeline. The **Handoffs** section names the other agents this one defers to and for what — it is how a feature flows from data layer to backend to frontend to QA to review. Be specific about the *trigger*:

```
## Handoffs
- **Database Developer** — migrations, indexes, query plans, backfills, partitioning
- **QA Engineer** — feature, contract, load tests
- **Security Engineer** — authn, authz, PII, billing, uploads, rate limits
- **Tech Lead** — non-trivial architecture review
```

Handoffs keep each agent in its lane and make the orchestration legible. A backend agent that designs its own indexes, or a builder that signs off on its own auth change, is a smell.

## Human checkpoints

Some changes are too consequential to be merged on an agent's say-so. Every agent declares a **Human checkpoint** line listing the categories where it must stop and require explicit human sign-off:

> **Human checkpoint required:** authn, authz, billing, PII, money, tenant isolation.

These are the irreversible-or-expensive-to-get-wrong surfaces: **authentication, authorization, billing, personally identifiable information (PII), anything moving money, and tenant isolation** (plus, for some roles, data residency, audit logging, mass-mail, and framework major-version migrations). The agent may design, implement, and test these changes — but a human must consciously approve before they ship. Declaring the checkpoint in the agent body is what makes the agent actually pause.

## Checklist for a good agent

Before you open the PR, confirm your agent:

- [ ] **Names concrete Laravel primitives.** Form Request, API Resource, Policy, `lockForUpdate()`, `Http::fake()`, `chunkById()`, `ShouldBeUnique`, Pennant, Horizon — not "validation", "authorization", "caching".
- [ ] **Lists the anti-patterns it refuses.** A concrete "refuse to ship" list (`$guarded = []` without reason, N+1 in list endpoints, `env()` outside `config/*.php`, returning models from APIs).
- [ ] **Has clear handoffs.** Names the downstream agents and the trigger for each.
- [ ] **Declares its human checkpoints.** The auth/authz/billing/PII/money/tenant surfaces it won't ship without sign-off.
- [ ] **Reads in the house voice.** Terse, imperative, fragment-heavy. No filler.
- [ ] **Grants minimal tools.** Reviewers set `disallowedTools: Edit, Write`. Builders set `isolation: worktree`.
- [ ] **Sets `memory: project`** if it's an architect, lead, security, data-layer, or orchestration role.
- [ ] **Has the standard sections.** Role line, Principles, When invoked, Anti-patterns, Handoffs, Human checkpoint.
- [ ] **Opens Principles with "Taught rules win."** Reads `docs/team/conventions.md` when present and treats its entries as overrides.

Use `agents/backend-developer.md` (a builder), `agents/tech-lead.md` (a reviewer), and `agents/security-engineer.md` (report-only) as your reference implementations.
