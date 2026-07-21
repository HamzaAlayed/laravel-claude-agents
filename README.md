# Laravel Guild — the 17-Agent Claude Code Team for Laravel

**A guild of 17 master craftspeople for your Laravel codebase.** A production-grade, drop-in team of Claude Code subagents purpose-built for **Laravel** projects. Covers the full lifecycle — discovery, prioritization, architecture, design, frontend (Blade / Livewire / Inertia / Filament), backend (Eloquent / Form Requests / Policies / API Resources), database, mobile, QA (Pest / PHPUnit / Dusk), DevOps (Forge / Vapor / Envoyer / Kamal), security, performance, technical writing, tech leadership, scrum, package development, and end-to-end delivery coordination.

Installable as a **Claude Code plugin** (one command), a **Cursor plugin**, a **Gemini CLI extension**, or a **Codex CLI** target, or via the classic `install.sh`. Guardrail hooks are tested in CI.

Every agent now knows what "good" looks like in a Laravel codebase. Reviewers refuse antipatterns (`env()` outside config, N+1, mass-assignment gaps, missing Policies, `migrate:fresh` anywhere near production). Builders default to idiomatic Laravel.

---

## What's in here

```
.claude/
├── agents/
│   ├── business-analyst.md       # "Scout" — discovery & requirements (Sonnet, project memory)
│   ├── product-owner.md          # "Horizon" — backlog & prioritization (Sonnet, project memory)
│   ├── ui-ux-designer.md         # "Breeze" — paradigm-aware design specs (Sonnet, worktree, project memory)
│   ├── frontend-developer.md     # "Blade" — Blade/Livewire/Inertia/Filament (Sonnet, worktree)
│   ├── backend-developer.md      # "Artisan" — APIs, services, Eloquent (Sonnet, worktree)
│   ├── database-developer.md     # "Eloquent" — migrations, indexes, factories (Sonnet, worktree, project memory)
│   ├── package-developer.md      # "Composer" — Laravel package authoring (Sonnet, worktree, project memory) ★ NEW
│   ├── qa-engineer.md            # "Dusk" — Pest/PHPUnit/Dusk, fakes (Sonnet, worktree)
│   ├── devops-engineer.md        # "Forge" — Forge/Cloud/Octane/Horizon (Sonnet, worktree)
│   ├── scrum-master.md           # "Pulse" — delivery rhythm & blockers (Haiku, project memory)
│   ├── solution-architect.md     # "Blueprint" — system design & ADRs (Opus, project memory)
│   ├── security-engineer.md      # "Fortify" — STRIDE + Laravel hardening (Opus, project memory, no Edit/Write)
│   ├── technical-writer.md       # "Scribe" — Scribe, route:list-driven docs (Haiku)
│   ├── tech-lead.md              # "Telescope" — code review w/ Laravel checklist (Sonnet, project memory, no Edit/Write)
│   ├── performance-engineer.md   # "Octane" — profiling, N+1, caching, Octane, CWV (Sonnet, project memory, no Edit/Write) ★ NEW
│   ├── mobile-developer.md       # "Passport" — iOS/Android consuming Laravel APIs (Sonnet, worktree)
│   └── delivery-coordinator.md   # "Envoy" — orchestrator main-thread agent (Sonnet, project memory)
│
└── commands/
    ├── audit-n-plus-one.md       # Audit a route/component for N+1, hand fixes to backend
    ├── make-feature.md           # End-to-end feature scaffold across DB → API → UI → QA → review
    ├── add-policy.md             # Add a Policy + patch all touch points + tests
    ├── refactor-to-action.md     # Extract a fat controller method into an Action class
    ├── ship-checklist.md         # Pre-release verification → SHIP / HOLD / CONDITIONAL verdict
    ├── add-test.md               # Generate a test plan + tests for a class/route/component ★ NEW
    ├── review-pr.md              # Layered diff review → tech-lead + security + QA + perf ★ NEW
    ├── optimize-query.md         # Diagnose a slow query/endpoint, route fixes to owners
    ├── upgrade-laravel.md        # Staged Laravel version-upgrade plan
    ├── teach.md                  # Record a user-taught rule all agents apply from then on
    └── board.md                  # Open the live agents dashboard (serves board.html) ★ NEW

scripts/
├── block-prod-destructive-sql.sh # Block DROP/TRUNCATE/unscoped DELETE/UPDATE
├── block-prod-artisan.sh         # Block migrate:fresh, db:wipe, tinker, etc. against prod
├── enforce-reviewer-readonly.sh  # Block file-mutating Bash from the read-only reviewers
├── enforce-sail.sh               # Redirect bare php/composer through ./vendor/bin/sail on Sail projects
├── emit-agent-events.sh          # Stream subagent start/finish to .claude/agents-board.jsonl ★ NEW
├── board.html                    # Self-contained live dashboard rendering that feed ★ NEW
└── protect-env-files.sh          # Block writes to .env, .env.production, secrets paths

skills/                           # 8 on-demand cookbooks (see the Skills section) ★ NEW
├── laravel-conventions/          # Which primitive to reach for, which antipattern to refuse
├── laravel-testing/              # Fakes syntax, Pest v4 browser tests, factories, time control
├── eloquent-performance/         # EXPLAIN reading, N+1 recipes, caching decision tree
├── laravel-security/             # STRIDE-on-Laravel checklist, advisory lookup, finding format
├── laravel-deploy/               # Zero-downtime releases, worker topology, rollback drill
├── delivery-templates/           # Requirements / RICE / sprint / retro / delivery-log shapes
├── accessibility-design/         # WCAG 2.2 AA thresholds, Livewire/Inertia focus, mobile a11y
└── docs-authoring/               # Changelog / release-notes / runbook / API-reference templates

hooks/hooks.json                  # Plugin hook manifest (5 guardrails + the agents-board observer)
tests/guardrails.test.sh          # Zero-dependency test harness for the guardrails
.github/workflows/ci.yml          # shellcheck + guardrail tests + manifest validation
```

---

## Meet the Guild

Every agent answers to a guild name — the Laravel-ecosystem tool closest to its craft. Address them either way: `@backend-developer` or "have **Artisan** add an idempotency key". The names show up on the `/board` live dashboard and in every agent's report.

| Guild name    | Agent                  | Named after                                              |
| ------------- | ---------------------- | -------------------------------------------------------- |
| **Artisan**   | `backend-developer`    | `php artisan` — the master craftsman of the codebase     |
| **Blade**     | `frontend-developer`   | Blade templates — everything the user sees               |
| **Eloquent**  | `database-developer`   | Eloquent ORM — schema, indexes, relationships            |
| **Dusk**      | `qa-engineer`          | Laravel Dusk — hunts defects before dark                 |
| **Forge**     | `devops-engineer`      | Laravel Forge — servers, pipelines, deploys              |
| **Octane**    | `performance-engineer` | Laravel Octane — obsessed with speed                     |
| **Fortify**   | `security-engineer`    | Laravel Fortify — hardens the walls                      |
| **Telescope** | `tech-lead`            | Laravel Telescope — inspects everything, misses nothing  |
| **Scribe**    | `technical-writer`     | Scribe — the guild's record-keeper                       |
| **Pulse**     | `scrum-master`         | Laravel Pulse — keeps a finger on the team's rhythm      |
| **Envoy**     | `delivery-coordinator` | Laravel Envoy — orchestrates tasks across the fleet      |
| **Scout**     | `business-analyst`     | Laravel Scout — sent ahead to discover the real problem  |
| **Horizon**   | `product-owner`        | Laravel Horizon — eyes always on what's next             |
| **Blueprint** | `solution-architect`   | Laravel Blueprint — designs the system from a spec       |
| **Breeze**    | `ui-ux-designer`       | Laravel Breeze — interfaces that feel effortless         |
| **Passport**  | `mobile-developer`     | Laravel Passport — credentials for clients on the move   |
| **Composer**  | `package-developer`    | Composer — ships reusable packages to the ecosystem      |

---

## Design choices, and why

**Model selection is opinionated, not uniform.**
- **Opus** for `solution-architect` and `tech-lead` — these reason deeply about long-lived consequences and review work end-to-end.
- **Haiku** for `scrum-master` — aggregation and status work. Faster and cheaper without quality loss.
- **Sonnet** for everyone else — the right default for builders and reviewers.

**Reviewers cannot edit code.** `tech-lead`, `security-engineer`, and `performance-engineer` are read-only (`disallowedTools: Edit, Write`). They return findings; the `delivery-coordinator` persists the reports and builders apply the changes. This keeps reviews trustworthy and prevents reviewer drift. (On the residual `Bash` write-vector and how to fully sandbox a reviewer, see [docs/read-only-by-design.md](docs/read-only-by-design.md).)

**You can see the team working.** The `delivery-coordinator` and all nine orchestrating commands print a progress board after planning and after every stage (`✔ done / ▶ running / · queued / ✖ failed / ⏸ checkpoint`), demand one stage-return shape from every specialist (`STATUS / DID / VERIFIED / FLAGS / NEXT` — evidence required, claims rejected), and present human checkpoints as numbered options with a recommended default (via `AskUserQuestion` when running main-thread). And `/board` opens a live HTML dashboard — the `emit-agent-events` hook streams every subagent start/finish (agent, task, duration, tokens) to `.claude/agents-board.jsonl` deterministically, so the board fills up no matter which command or agent is orchestrating. A multi-agent run reads like a dashboard, not a silence.

**Writers run in isolated worktrees.** `backend-developer`, `frontend-developer`, `database-developer`, `mobile-developer`, `package-developer`, `devops-engineer`, and `ui-ux-designer` use `isolation: worktree` so parallel changes don't collide.

**Project memory where it earns its keep.** Writing roles — the architect, data layer, product, discovery, and orchestration agents — persist context (ADRs, conventions, schema decisions, requirements) across sessions. Read-only reviewers keep memory for cross-session recall but never write it; the orchestrator persists their findings.

**The team keeps a knowledge base — in your repo, not in a hidden store.** Three files under `docs/team/`, all human-readable, PR-reviewable, and deletable: `conventions.md` (rules you teach via `/teach` — every agent applies them as overrides), `stack.md` (verified project facts + where-things-live; every fact carries a **Verify** command so agents trust-but-verify instead of re-deriving configs each invocation), and `decisions.md` (approaches tried and rejected, with why — the one thing neither git nor the code can tell an agent). The coordinator harvests all three at delivery end and flags stale entries for *you* to remove — agents propose, the human approves, the repo remembers. The design rule: store what the repo can't answer (intent, taste, rejections); derive what it can (hot paths, naming, current state).

**Laravel-aware, not Laravel-flavored.** Every applicable agent references concrete Laravel primitives — Form Requests, API Resources, Policies, Eloquent relationships, Pint, Larastan, Pest, Horizon, Octane, Sanctum, Filament — and names the antipatterns they refuse to ship.

**One frontend agent, paradigm-aware.** Rather than splitting Blade/Livewire/Inertia/Filament into separate agents, `frontend-developer` detects the project's paradigm from composer.json + the codebase and behaves accordingly. Filament is treated as a first-class paradigm, not a Blade add-on.

---

## What's actually new vs. the original spec

If you're coming from the generic 15-agent version, here's what changed:

1. **Every agent is rewritten with Laravel-specific guidance.** Concrete patterns to follow, concrete antipatterns to refuse. No more "use the framework's conventions" hand-waving.
2. **New `package-developer` agent.** Composer.json hygiene, service providers, Testbench, semver, Packagist release flow. Real gap for anyone shipping packages.
3. **Five slash commands** in `commands/` for the most common Laravel workflows. They delegate to the right specialists rather than doing work themselves.
4. **Two new guardrail scripts** alongside the existing SQL guard. Production artisan commands and env files are now actively protected.
5. **`CLAUDE.md.template` rewritten for Laravel.** Captures stack (PHP/Laravel/frontend paradigm/queue/runtime/auth/search/hosting), conventions, hard constraints, and useful commands.
6. **`install.sh` hardened.** Argparse, Laravel detection, idempotent overwrites with timestamped `.bak` backups, optional `--global` install.

---

## Slash commands

Each is a thin orchestrator that hands work to the right specialist agent.

| Command                                   | What it does                                                                                                                                   |
|-------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| `/audit-n-plus-one <route or component>`  | Profiles the request, finds eager-load gaps, hands a fix-list to `backend-developer`.                                                          |
| `/make-feature <name>`                    | Routes through `database-developer` → `backend-developer` → `frontend-developer` → `qa-engineer` → `tech-lead`. Detects the frontend paradigm. |
| `/add-policy <Model>`                     | Creates/audits the Policy, patches controllers + Livewire + Filament + Form Requests, adds allowed/denied tests.                               |
| `/refactor-to-action <Controller@method>` | Extracts the method into an Action class with a single `handle()` and a test.                                                                  |
| `/ship-checklist`                         | Produces `docs/qa/release-<version>.md` with verdict: SHIP / HOLD / CONDITIONAL.                                                               |
| `/add-test <Class, route, or component>`  | Builds a test plan (happy path + failure modes + allowed/denied authz), detects Pest vs PHPUnit, hands implementation to `qa-engineer`.        |
| `/review-pr [base-branch]`                | Layered diff review — fans out to `tech-lead`, `security-engineer`, `qa-engineer`, `performance-engineer`; one verdict with Blocking/Should-fix/Nits. |
| `/optimize-query <route, query, method>`  | Captures the query + timing, diagnoses (index/N+1/`SELECT *`/unbounded), routes index fixes to `database-developer`, shape fixes to `backend-developer`. |
| `/upgrade-laravel <target-version>`       | Inventories breaking changes + first-party package compat, produces a staged upgrade plan with a verify checkpoint per stage.                  |
| `/teach <rule>`                           | Records a rule/preference in `docs/team/conventions.md` — every agent reads it before starting and applies it as an override. No args → harvests this session's corrections. Facts (commands, paths) carry a **Verify** command so they can't go silently stale. |
| `/board [port]`                           | Opens the live agents dashboard — serves `.claude/board.html` over localhost; running agents pulse with a live timer, finished ones show duration + tokens. Fed by the `emit-agent-events` hook. |

---

## Guardrail scripts

Wire these as Claude Code `PreToolUse` hooks for `Bash` and `Write|Edit`. They exit `2` to block and print a clear reason.

| Script                          | Blocks                                                                                                                      |
|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| `block-prod-destructive-sql.sh` | `DROP`, `TRUNCATE`, unscoped `DELETE` / `UPDATE`                                                                            |
| `block-prod-artisan.sh`         | `migrate:fresh`, `db:wipe`, `migrate:reset`, `tinker`, `queue:flush`, etc., against `--env=production` or `.env.production` |
| `protect-env-files.sh`          | Writes to `.env`, `.env.production`, `.env.prod`, `.env.live`, `.env.staging`, `.env.local`, and credential-looking paths   |
| `enforce-reviewer-readonly.sh`  | File-mutating Bash (`sed -i`, redirects, `tee`, mutating `git`/`artisan`/`composer`, `pint` without `--test`, `rm`/`mv`/`cp`) **from the read-only reviewers only** — scoped via the hook input's `agent_type`; builders and the main thread are untouched. Claude Code only. |
| `enforce-sail.sh`               | Bare `php artisan` / `composer` / `vendor/bin/{pint,pest,phpunit,phpstan}` on a **Sail** project — the block message carries the exact `./vendor/bin/sail …` rewrite, so the agent self-corrects in one turn. Active only when both `vendor/bin/sail` and a compose file exist (the sail *dependency* alone — the Herd/Valet shape — stays untouched). Opt out with `LARAVEL_AGENTS_SAIL=0`. |
| `emit-agent-events.sh`          | Nothing — an **observer**, not a guard: wired as `PreToolUse` **and** `PostToolUse` on the subagent tool (`Agent\|Task`), it streams every subagent start / finish (agent, task, duration, tokens) to `.claude/agents-board.jsonl` for the `/board` live dashboard. Always exits 0. Claude Code only. |

Example hook config (`.claude/settings.json`) — this is the shape `install.sh` auto-merges:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "./scripts/block-prod-destructive-sql.sh" }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "./scripts/block-prod-artisan.sh" }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "./scripts/enforce-reviewer-readonly.sh" }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "./scripts/enforce-sail.sh" }
        ]
      },
      {
        "matcher": "Write|Edit",
        "hooks": [
          { "type": "command", "command": "./scripts/protect-env-files.sh" }
        ]
      },
      {
        "matcher": "Agent|Task",
        "hooks": [
          { "type": "command", "command": "./scripts/emit-agent-events.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Agent|Task",
        "hooks": [
          { "type": "command", "command": "./scripts/emit-agent-events.sh" }
        ]
      }
    ]
  }
}
```

---

## Install

### As a Claude Code plugin (recommended)

Add the marketplace once, then install the plugin:

```
/plugin marketplace add HamzaAlayed/laravel-claude-agents
/plugin install laravel-team@laravel-claude-agents
```

That registers all 17 agents, the 11 slash commands, the `laravel-conventions` skill, and the five guardrail hooks (wired through `${CLAUDE_PLUGIN_ROOT}`). Update with `/plugin marketplace update laravel-claude-agents`. To share with a team, install at project scope:

```
/plugin install laravel-team@laravel-claude-agents --scope project
```

> The plugin does **not** drop a `CLAUDE.md` into your project — copy `CLAUDE.md.template` yourself, or use the `install.sh` path below which does it for you.

#### Cursor

This pack also ships a `.cursor-plugin/` manifest. Search for it in the [Cursor plugin marketplace](https://cursor.com/docs/plugins), or add the marketplace by repo URL — the same agents, commands, skill, and hooks load in Cursor.

#### Gemini CLI

The pack also ships as a **Gemini CLI extension** under [`gemini/`](gemini/) — auto-generated from the same source by `scripts/build-gemini-extension.py`. Gemini CLI installs from a repo root or local path (there's no subdirectory flag), so install it locally:

```bash
git clone https://github.com/HamzaAlayed/laravel-claude-agents
gemini extensions install ./laravel-claude-agents/gemini
```

It registers the 17 subagents (auto-delegated, or call `@backend-developer` etc.), the 11 slash commands, the `laravel-conventions` skill, and the guardrail hooks (wired as `BeforeTool` via `${extensionPath}`). The Claude-specific frontmatter is translated automatically: tool names mapped (`Bash`→`run_shell_command`, …), read-only reviewers expressed as a tools allowlist (Gemini has no `disallowedTools`), commands rewritten to TOML (`{{args}}` is already Gemini's token), and `model`/`isolation`/`memory` dropped (no Gemini equivalent).

> **Sunset notice:** Google sunsets Gemini CLI for consumer (Individual / AI Pro / AI Ultra) accounts on **June 18, 2026** in favor of [Antigravity](https://antigravity.google); Standard/Enterprise tiers are unaffected. Installed extensions **auto-migrate to Antigravity plugins** — Agent Skills, Hooks, Subagents, and `GEMINI.md` carry over. This pack is pure bash + markdown (no Node-only APIs), so it migrates cleanly.

#### Codex CLI

Codex has no one-command install, so the pack ships a **Codex Core** target under [`codex/`](codex/) — `AGENTS.md` (Codex's native context file), the `laravel-conventions` skill, and the 4 guardrail hooks as `PreToolUse`. Install it into your project:

```bash
git clone https://github.com/HamzaAlayed/laravel-claude-agents
./laravel-claude-agents/codex/install-codex.sh /path/to/your/laravel/project
```

It drops `AGENTS.md` (only if absent), `.agents/skills/laravel-conventions/`, and `.codex/hooks.json` + `.codex/hooks/*.sh` (hook paths resolve from the git root). On the next `codex` run you're asked to review and trust the hooks. The guard scripts use the same `.tool_input.command` / `exit 2` contract as Claude, with an `apply_patch`-aware `.env` guard that inspects the patch's target paths.

> **Scope:** the full 17-agent team is **not** ported to Codex — its subagent model is a different `config.toml` schema. Codex Core ships the conventions skill + guardrails; use Claude Code or Gemini CLI for the full team.

### Just the skills, on any agent (skills.sh)

The 8 cookbooks install standalone into ~20 agent runtimes (Claude Code, Cursor, Codex, Gemini CLI, Antigravity, Copilot, …) via the [skills.sh](https://skills.sh) CLI — no plugin needed:

```bash
npx skills add HamzaAlayed/laravel-claude-agents
```

You get the skills only; the 17 agents, commands, and guardrail hooks ship through the plugin/extension installs above.

### Pairs with the official Laravel pack

This team is the full delivery lifecycle (17 agents). It's designed to sit **alongside** Laravel's official [`laravel/agent-skills`](https://github.com/laravel/agent-skills), not replace it — install both:

```
/plugin marketplace add laravel/agent-skills
/plugin install laravel@laravel            # laravel-simplifier agent + starter-kit-upgrade skill
/plugin install laravel-cloud@laravel      # deploy/manage on Laravel Cloud
/plugin install laravel-nightwatch@laravel # Nightwatch config + MCP
```

How they divide the work:

- **Framework upgrades** → Laravel Boost's `/upgrade-laravel-v13`, `/upgrade-livewire-v4`, etc. Our `/upgrade-laravel` defers to Boost and owns the surrounding work (PHP runtime, package compat, structural audit, verification).
- **After-the-fact cleanup** → the official `laravel-simplifier`. Our `laravel-conventions` skill guides the choice of primitive *up front*; the agents enforce it during review.
- **Cloud / Nightwatch** → the official skills own those; we don't duplicate them.

### One-click installer (`curl | bash`)

From the root of your Laravel project:

```bash
curl -fsSL https://raw.githubusercontent.com/HamzaAlayed/laravel-claude-agents/main/install.sh | bash
```

That's it. The installer self-clones to a temp dir, copies everything into place, drops a `CLAUDE.md`, wires up the guardrail hooks in `.claude/settings.json`, and cleans up after itself.

Global install (available in every project):

```bash
curl -fsSL https://raw.githubusercontent.com/HamzaAlayed/laravel-claude-agents/main/install.sh | bash -s -- -g
```

### Local

Clone once, then run the installer from your Laravel project root (the installer's target is the current directory by default):

```bash
git clone https://github.com/HamzaAlayed/laravel-claude-agents.git /tmp/lca
cd /path/to/your/laravel/project
/tmp/lca/install.sh
```

Or pass the target explicitly from anywhere:

```bash
/tmp/lca/install.sh /path/to/your/laravel/project
```

### Flags

- `-g`, `--global` — install to `~/.claude/` instead of `./.claude/`
- `--interactive` — prompt before overwriting files (default is zero-prompt — see backup behavior below)
- `--no-hooks` — skip auto-wiring `.claude/settings.json`
- `--no-claudemd` — skip copying `CLAUDE.md.template`
- positional path — install to a project other than the current directory

### What the installer does

1. Bootstraps itself by cloning the repo when run via `curl | bash`.
2. Copies agents to `<target>/.claude/agents/`.
3. Copies slash commands to `<target>/.claude/commands/`.
4. Copies guardrail scripts to `<target>/scripts/` and `chmod +x` them.
5. Drops `CLAUDE.md` from the template if one doesn't exist yet (never overwrites an existing one).
6. Idempotently merges the three guardrail `PreToolUse` hooks into `<target>/.claude/settings.json` (the file is only rewritten when something actually changes).
7. Backup behavior: byte-identical files are skipped without backup. When a copied file differs from the destination, a timestamped `.bak` copy is created before overwriting. If `settings.json` exists but contains invalid JSON, the original is preserved as a timestamped `.bak` before the new file is written.

---

## MCP servers (optional, recommended)

The agents carry **server-level MCP grants** (`mcp__laravel-boost`, `mcp__context7`, …) in their `tools:` lists, matched to each role. The grants are inert when a server isn't attached — every MCP instruction in the agent bodies is conditional ("MCP exposed → prefer it"), so nothing breaks without them. Attach what you use; the agents get sharper with each one.

| Server (expected name) | Attach | Who uses it |
|---|---|---|
| `laravel-boost` | `composer require laravel/boost --dev && php artisan boost:install` (per Laravel project; registers the MCP server) | backend, database, qa, performance, security, tech-lead, technical-writer |
| `context7` | `claude mcp add --transport http context7 https://mcp.context7.com/mcp` | backend, frontend, mobile, package, solution-architect |
| `playwright` | `claude mcp add playwright -- npx -y @playwright/mcp@latest` | frontend, qa, ui-ux-designer |
| `sentry` | `claude mcp add --transport http sentry https://mcp.sentry.dev/mcp` (OAuth on first use) | devops, performance, security |
| `linear` | `claude mcp add --transport sse linear https://mcp.linear.app/sse` (OAuth) | business-analyst, product-owner, scrum-master, delivery-coordinator |
| `atlassian` (Jira) | `claude mcp add --transport sse atlassian https://mcp.atlassian.com/v1/sse` (OAuth) | business-analyst, product-owner, scrum-master, delivery-coordinator |
| `figma` | Enable the Dev Mode MCP server in the Figma desktop app, then `claude mcp add --transport sse figma http://127.0.0.1:3845/sse` | frontend, mobile, ui-ux-designer |

Remote-server URLs occasionally move — if an attach command fails, check the vendor's MCP docs. **Server names must match the table** (the grants are literal strings like `mcp__laravel-boost`); if you attach a server under a different name, either re-add it with the expected name or adjust the agent frontmatter.

Read-only reviewers (`tech-lead`, `security-engineer`, `performance-engineer`) state in their bodies that read-only discipline extends to MCP — they query docs, schema, logs, and traces but never mutate through a server.

Gemini CLI note: MCP grants don't port (Gemini configures MCP servers in its own `settings.json`; its subagents see them per that config). The conditional body instructions still apply as written.

---

## Skills

The pack ships **8 skills** — deep procedural cookbooks the agents invoke **on demand** via the `Skill` tool (every agent carries it), so the detail is paid for only when a task needs it, not on every invocation:

| Skill | Cookbook | Invoked by |
|---|---|---|
| `laravel-conventions` | which primitive to reach for, which antipattern to refuse | backend, frontend, database, package, tech-lead, solution-architect |
| `laravel-testing` | fakes assertion syntax, Pest v4 browser testing, factories, time control | qa, backend, frontend, package |
| `eloquent-performance` | EXPLAIN reading, N+1 recipes, caching decision tree, measurement discipline | performance, backend, database |
| `laravel-security` | STRIDE-on-Laravel checklist, advisory lookup, finding format | security, tech-lead |
| `laravel-deploy` | zero-downtime checklist, worker/scheduler topology, rollback drill | devops |
| `delivery-templates` | requirements / story / RICE / sprint / retro / health-report / delivery-log shapes | business-analyst, product-owner, scrum-master, delivery-coordinator |
| `accessibility-design` | WCAG 2.2 AA thresholds, Livewire/Inertia focus management, mobile a11y | ui-ux-designer, frontend, mobile |
| `docs-authoring` | changelog / release-notes / runbook / endpoint-reference templates | technical-writer |

Design note: agents deliberately do **not** use the `skills:` preload field — preloading injects the full skill into context on *every* invocation. On-demand invocation via the `Skill` tool keeps the per-call cost at zero until the task actually needs the cookbook. Installed as a plugin, skills are namespaced (`laravel-team:laravel-testing`); via `install.sh` they're bare names — agents reference them by bare name and Claude Code resolves either.

Pairs well with (install alongside, no overlap):

```
/plugin install laravel@laravel                          # laravel-simplifier + starter-kit-upgrade
/plugin install laravel-cloud@laravel                    # Laravel Cloud deploys
/plugin install laravel-nightwatch@laravel               # Nightwatch monitoring
/plugin install document-skills@anthropic-agent-skills   # docx/pdf/pptx/xlsx for BA/PO/writer deliverables
```

---

## Usage in Claude Code

These are subagents, so you invoke them via the `Agent` tool or directly by name. The `delivery-coordinator` is the main-thread orchestrator — it's the one you talk to for cross-cutting work, and it delegates onward.

```
> Use delivery-coordinator to ship a "team invites" feature: invite email,
  accept/decline, audit log entry. Use the make-feature command.
```

For point work, call a specialist directly:

```
> Have backend-developer add an idempotency key to POST /api/orders.
> Have tech-lead review the diff before merge.
```

---

## Usage in Gemini CLI

After `gemini extensions install ./laravel-claude-agents/gemini`, the 17 specialists load as Gemini subagents, the 10 commands as slash commands, the `laravel-conventions` skill, and the guardrail hooks.

**Invoke a specialist** — either let Gemini auto-delegate from your description, or target one explicitly with `@`:

```
> @delivery-coordinator ship a "team invites" feature: invite email,
  accept/decline, audit log entry.
> @backend-developer add an idempotency key to POST /api/orders.
> @tech-lead review the diff before merge.
```

**Run a workflow command** — the slash commands are invoked by name, with arguments after:

```
> /make-feature team invites
> /review-pr main
> /add-policy User
> /optimize-query "GET /orders"
```

**Skill + hooks are automatic.** The `laravel-conventions` skill surfaces when you ask the "right way" to do something in Laravel, and the `BeforeTool` hooks run on every shell / file-write — blocking `migrate:fresh` against production, destructive prod SQL, and writes to `.env*`. (Gemini prompts once at install to consent to the hooks.)

> Read-only reviewers (`@tech-lead`, `@security-engineer`, `@performance-engineer`) carry a read-only tool set in Gemini too — they report findings and hand fixes to the builders / the coordinator.

---

## Usage in Codex CLI

The **Codex Core** target shapes behavior through context, a skill, and guardrails rather than agents you invoke:

- **`AGENTS.md`** loads every session as project context (Laravel stack, conventions, hard constraints, definition-of-done).
- **`laravel-conventions`** auto-triggers when you ask the idiomatic "right way" to do something in Laravel.
- **`PreToolUse` hooks** block destructive prod SQL / `artisan` and writes to `.env*` / secret files. Codex asks you to trust them once, then they run on every tool call; a blocked call exits with the reason. The `.env` guard is `apply_patch`-aware — it inspects the patch's target paths, so a file that merely *mentions* `.env` in its content isn't blocked.

There are no Codex subagents or slash commands in this target — the full team lives on Claude Code / Gemini CLI (see the scope note in Install).

---

## CLAUDE.md.template

A starter `CLAUDE.md` tailored for Laravel. Fill in the stack block (PHP version, Laravel version, frontend paradigm, queue driver, runtime, auth, search, mobile, hosting, CI, observability), and the rest is already there: repo layout, conventions, hard constraints, useful commands. Agents read this first when they pick up work, so the more accurate it is, the better they'll behave.

---

## Development

The guardrail scripts are covered by a zero-dependency test harness — no `bats`, no install:

```bash
./tests/guardrails.test.sh        # 24 assertions incl. the no-jq/no-python3 fallback
```

CI (`.github/workflows/ci.yml`) runs `shellcheck`, the harness (with and without `jq`), JSON manifest validation, and agent/command frontmatter linting on every PR.

Adding an agent or command? See [CONTRIBUTING.md](CONTRIBUTING.md) and the deeper [docs/authoring-agents.md](docs/authoring-agents.md). Changes are tracked in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE). Use it, fork it, ship with it.
