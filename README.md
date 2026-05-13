# The 16-Agent Claude Code Team for Laravel

A production-grade, drop-in team of Claude Code subagents purpose-built for **Laravel** projects. Covers the full lifecycle — discovery, prioritization, architecture, design, frontend (Blade / Livewire / Inertia / Filament), backend (Eloquent / Form Requests / Policies / API Resources), database, mobile, QA (Pest / PHPUnit / Dusk), DevOps (Forge / Vapor / Envoyer / Kamal), security, technical writing, tech leadership, scrum, package development, and end-to-end delivery coordination.

Every agent now knows what "good" looks like in a Laravel codebase. Reviewers refuse antipatterns (`env()` outside config, N+1, mass-assignment gaps, missing Policies, `migrate:fresh` anywhere near production). Builders default to idiomatic Laravel.

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
- **Haiku** for `scrum-master` — aggregation and status work. Faster and cheaper without quality loss.
- **Sonnet** for everyone else — the right default for builders and reviewers.

**Reviewers cannot edit code.** `tech-lead` and `security-engineer` have `disallowedTools: Edit, Write`. They produce findings; builders apply changes. This keeps the review trustworthy and prevents reviewer drift.

**Builders run in isolated worktrees.** `backend-developer`, `frontend-developer`, `database-developer`, `mobile-developer`, and `package-developer` use `isolation: worktree` so parallel changes don't collide.

**Project memory where it earns its keep.** Architects, leads, security, the data layer, and orchestration roles persist context (ADRs, conventions, the threat model, schema decisions) across sessions.

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

---

## Guardrail scripts

Wire these as Claude Code `PreToolUse` hooks for `Bash` and `Write|Edit`. They exit `2` to block and print a clear reason.

| Script                          | Blocks                                                                                                                      |
|---------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| `block-prod-destructive-sql.sh` | `DROP`, `TRUNCATE`, unscoped `DELETE` / `UPDATE`                                                                            |
| `block-prod-artisan.sh`         | `migrate:fresh`, `db:wipe`, `migrate:reset`, `tinker`, `queue:flush`, etc., against `--env=production` or `.env.production` |
| `protect-env-files.sh`          | Writes to `.env`, `.env.production`, `.env.prod`, `.env.live`, `.env.staging`, `.env.local`, and credential-looking paths   |

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
        "matcher": "Write|Edit",
        "hooks": [
          { "type": "command", "command": "./scripts/protect-env-files.sh" }
        ]
      }
    ]
  }
}
```

---

## Install

### One-click (recommended)

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

## CLAUDE.md.template

A starter `CLAUDE.md` tailored for Laravel. Fill in the stack block (PHP version, Laravel version, frontend paradigm, queue driver, runtime, auth, search, mobile, hosting, CI, observability), and the rest is already there: repo layout, conventions, hard constraints, useful commands. Agents read this first when they pick up work, so the more accurate it is, the better they'll behave.

---

## License

MIT. Use it, fork it, ship with it.
