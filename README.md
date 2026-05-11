# The 16-Agent Claude Code Team for Laravel

A production-grade, drop-in team of Claude Code subagents purpose-built for **Laravel** projects. Covers the full lifecycle — discovery, prioritization, architecture, design, frontend (Blade / Livewire / Inertia / Filament), backend (Eloquent / Form Requests / Policies / API Resources), database, mobile, QA (Pest / PHPUnit / Dusk), DevOps (Forge / Vapor / Envoyer / Kamal), security, technical writing, tech leadership, scrum, package development, and end-to-end delivery coordination.

Every agent now knows what "good" looks like in a Laravel codebase. Reviewers refuse anti-patterns (`env()` outside config, N+1, mass-assignment gaps, missing Policies, `migrate:fresh` anywhere near production). Builders default to idiomatic Laravel.

---

## What's in here

```
.claude/
├── agents/
│   ├── business-analyst.md       # Discovery & requirements (Sonnet, project memory, read-only)
│   ├── product-owner.md          # Backlog & prioritization (Sonnet, project memory)
│   ├── ui-ux-designer.md         # Paradigm-aware design specs (Sonnet, frontend-design skill)
│   ├── frontend-developer.md     # Blade/Livewire/Inertia/Filament (Sonnet, worktree, frontend-design)
│   ├── backend-developer.md      # APIs, services, Eloquent (Sonnet, worktree)
│   ├── database-developer.md     # Migrations, indexes, factories (Sonnet, worktree, project memory)
│   ├── package-developer.md      # Laravel package authoring (Sonnet, worktree, project memory) ★ NEW
│   ├── qa-engineer.md            # Pest/PHPUnit/Dusk, fakes (Sonnet)
│   ├── devops-engineer.md        # Forge/Vapor/Octane/Horizon (Sonnet)
│   ├── scrum-master.md           # Delivery rhythm & blockers (Haiku, project memory)
│   ├── solution-architect.md     # System design & ADRs (Opus, project memory)
│   ├── security-engineer.md      # STRIDE + Laravel hardening (Sonnet, project memory, no Edit/Write)
│   ├── technical-writer.md       # Scribe, route:list-driven docs (Sonnet)
│   ├── tech-lead.md              # Code review w/ Laravel checklist (Opus, project memory, no Edit/Write)
│   ├── mobile-developer.md       # iOS/Android consuming Laravel APIs (Sonnet, worktree)
│   └── delivery-coordinator.md   # Orchestrator main-thread agent (Sonnet, project memory)
│
└── commands/
    ├── audit-n-plus-one.md       # Audit a route/component for N+1, hand fixes to backend
    ├── make-feature.md           # End-to-end feature scaffold across DB → API → UI → QA → review
    ├── add-policy.md             # Add a Policy + patch all touch points + tests
    ├── refactor-to-action.md     # Extract a fat controller method into an Action class
    └── ship-checklist.md         # Pre-release verification → SHIP / HOLD / CONDITIONAL verdict

scripts/
├── block-prod-destructive-sql.sh # Block DROP/TRUNCATE/unscoped DELETE/UPDATE
├── block-prod-artisan.sh         # Block migrate:fresh, db:wipe, tinker, etc. against prod
└── protect-env-files.sh          # Block writes to .env, .env.production, secrets paths
```

---

## Design choices, and why

**Model selection is opinionated, not uniform.**
- **Opus** for `solution-architect` and `tech-lead` — these reason deeply about long-lived consequences and review work end-to-end.
- **Haiku** for `scrum-master` — aggregation and status work. Faster + cheaper without quality loss.
- **Sonnet** for everyone else — the right default for builders and reviewers.

**Reviewers cannot edit code.** `tech-lead` and `security-engineer` have `disallowedTools: Edit, Write`. They produce findings; builders apply changes. This keeps review trustworthy and prevents reviewer drift.

**Builders run in isolated worktrees.** `backend-developer`, `frontend-developer`, `database-developer`, `mobile-developer`, and `package-developer` use `isolation: worktree` so parallel changes don't collide.

**Project memory where it earns its keep.** Architects, leads, security, the data layer, and orchestration roles persist context (ADRs, conventions, the threat model, schema decisions) across sessions.

**Laravel-aware, not Laravel-flavored.** Every applicable agent references concrete Laravel primitives — Form Requests, API Resources, Policies, Eloquent relationships, Pint, Larastan, Pest, Horizon, Octane, Sanctum, Filament — and names the anti-patterns they refuse to ship.

**One frontend agent, paradigm-aware.** Rather than splitting Blade/Livewire/Inertia/Filament into separate agents, `frontend-developer` detects the project's paradigm from composer.json + the codebase and behaves accordingly. Filament is treated as a first-class paradigm, not a Blade add-on.

---

## What's actually new vs. the original spec

If you're coming from the generic 15-agent version, here's what changed:

1. **Every agent rewritten with Laravel-specific guidance.** Concrete patterns to follow, concrete anti-patterns to refuse. No more "use the framework's conventions" hand-waving.
2. **New `package-developer` agent.** Composer.json hygiene, service providers, Testbench, semver, Packagist release flow. Real gap for anyone shipping packages.
3. **Five slash commands** in `commands/` for the most common Laravel workflows. They delegate to the right specialists rather than doing work themselves.
4. **Two new guardrail scripts** alongside the existing SQL guard. Production artisan commands and env files are now actively protected.
5. **`CLAUDE.md.template` rewritten for Laravel.** Captures stack (PHP/Laravel/frontend paradigm/queue/runtime/auth/search/hosting), conventions, hard constraints, and useful commands.
6. **`install.sh` hardened.** Argparse, Laravel detection, idempotent overwrites with timestamped `.bak` backups, optional `--global` install.

---

## Slash commands

Each is a thin orchestrator that hands work to the right specialist agent.

| Command | What it does |
|---|---|
| `/audit-n-plus-one <route or component>` | Profiles the request, finds eager-load gaps, hands a fix-list to `backend-developer`. |
| `/make-feature <name>` | Routes through `database-developer` → `backend-developer` → `frontend-developer` → `qa-engineer` → `tech-lead`. Detects the frontend paradigm. |
| `/add-policy <Model>` | Creates/audits the Policy, patches controllers + Livewire + Filament + Form Requests, adds allowed/denied tests. |
| `/refactor-to-action <Controller@method>` | Extracts the method into an Action class with a single `handle()` and a test. |
| `/ship-checklist` | Produces `docs/qa/release-<version>.md` with verdict: SHIP / HOLD / CONDITIONAL. |

---

## Guardrail scripts

Wire these as Claude Code `PreToolUse` hooks for `Bash` and `Write|Edit`. They exit `2` to block and print a clear reason.

| Script | Blocks |
|---|---|
| `block-prod-destructive-sql.sh` | `DROP`, `TRUNCATE`, unscoped `DELETE` / `UPDATE` |
| `block-prod-artisan.sh` | `migrate:fresh`, `db:wipe`, `migrate:reset`, `tinker`, `queue:flush`, etc., against `--env=production` or `.env.production` |
| `protect-env-files.sh` | Writes to `.env`, `.env.production`, `.env.prod`, `.env.live`, `.env.staging`, `.env.local`, and credential-looking paths |

Example hook config (`.claude/settings.json`):
```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "command": "./scripts/block-prod-destructive-sql.sh" },
      { "matcher": "Bash", "command": "./scripts/block-prod-artisan.sh" },
      { "matcher": "Write|Edit", "command": "./scripts/protect-env-files.sh" }
    ]
  }
}
```

---

## Install

From the root of your Laravel project:

```bash
git clone https://github.com/HamzaAlayed/laravel-claude-agents.git /tmp/lca
cd /tmp/lca && ./install.sh
```

Flags:
- `-g`, `--global` — install to `~/.claude/` instead of `./.claude/`
- `--no-confirm` — overwrite without prompting (still creates `.bak` backups)
- positional path — install to a project other than the current directory

The installer will:
1. Check that the target is a Laravel project (warns and prompts if not — useful for fresh starts).
2. Copy agents to `<target>/.claude/agents/`.
3. Copy slash commands to `<target>/.claude/commands/`.
4. Copy guardrail scripts to `<target>/scripts/` and `chmod +x` them.
5. Drop `CLAUDE.md.template` next to your `CLAUDE.md` if one doesn't exist yet.
6. Make timestamped `.bak` copies before overwriting anything.

---

## Usage in Claude Code

These are subagents, so you invoke them via the `Agent` tool or directly by name. The `delivery-coordinator` is the main-thread orchestrator — it's the one you talk to for cross-cutting work and it delegates onward.

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

## CLAUDE.md.template

A starter `CLAUDE.md` tailored for Laravel. Fill in the stack block (PHP version, Laravel version, frontend paradigm, queue driver, runtime, auth, search, mobile, hosting, CI, observability), and the rest is already there: repo layout, conventions, hard constraints, useful commands. Agents read this first when they pick up work, so the more accurate it is, the better they'll behave.

---

## License

MIT. Use it, fork it, ship with it.
