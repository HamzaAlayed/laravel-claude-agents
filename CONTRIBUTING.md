# Contributing

Thanks for helping improve **The 16-Agent Claude Code Team for Laravel**. This is a drop-in pack of Claude Code subagents, slash commands, and guardrail hook scripts for Laravel projects. Contributions that sharpen the agents, add commands, or harden the guardrails are all welcome.

Read this whole file before opening a PR. For a deep dive on writing agents in this pack's voice, see [`docs/authoring-agents.md`](docs/authoring-agents.md).

## Repository layout

```
agents/              Subagent definitions — one .md file per agent, with YAML frontmatter
commands/            Slash command definitions — one .md file per command, with YAML frontmatter
scripts/             Guardrail bash hooks (PreToolUse / etc.) — block dangerous operations
CLAUDE.md.template   The project-rules template a consumer drops into their repo
install.sh           One-click installer that copies the pack into a target project
tests/               Zero-dependency test harness covering the guardrail scripts
```

- **agents/** — Each `.md` file is one subagent. Frontmatter declares its identity and capabilities; the body is the prompt that defines its behavior.
- **commands/** — Each `.md` file is one slash command. Commands orchestrate; they delegate the actual building to specialist agents.
- **scripts/** — Defensive bash hooks. They read a tool invocation as JSON on stdin and exit `0` to allow or `2` to block. Keep them dependency-light and POSIX-friendly.
- **CLAUDE.md.template** — The per-project rule sheet consumers customize. Update it when a convention the agents rely on changes.
- **install.sh** — Keep it idempotent and non-destructive.

## Adding a new agent

Create `agents/<name>.md`. Start from the frontmatter, then write the body in the house style.

### Frontmatter fields

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | kebab-case, matches the filename (e.g. `backend-developer`) |
| `description` | yes | One dense paragraph. Say what it does, when to use it *proactively*, and which Laravel tools/packages it knows. This is what the orchestrator routes on — be specific. |
| `tools` | yes | Comma-separated allowlist (e.g. `Read, Write, Edit, Bash, Grep, Glob`). Grant only what the role needs. |
| `model` | yes | `opus`, `sonnet`, or `haiku` — see [Model selection](#model-selection). |
| `color` | yes | Display color (e.g. `green`, `cyan`, `red`). |
| `isolation: worktree` | optional | Builders that edit code. Runs the agent in an isolated git worktree so parallel work doesn't collide. |
| `memory: project` | optional | Roles that accumulate durable, project-specific knowledge (architects, leads, security, data layer, orchestration). |
| `disallowedTools` | optional | Explicitly deny tools even if otherwise implied. Reviewers deny `Edit, Write` — they report, they do not rewrite. |
| `skills` | optional | Skills the agent may invoke. |

### House style

The agents are deliberately terse. Match it.

- **Terse and fragment-heavy.** Drop articles and filler. "Skinny controllers. Logic in Actions. Never in models." not "Controllers should be kept thin and the business logic should live in Action classes."
- **Imperative.** Tell the agent what to do, in order.
- **Laravel-specific and concrete.** Name real primitives: Form Request, API Resource, Policy, `lockForUpdate()`, `Http::fake()`, `chunkById()`, `ShouldBeUnique`. Vague advice is worthless; concrete advice is the whole point.
- **Reviewers refuse antipatterns; they don't edit.** Review and security roles report findings with `path/to/file.php:line` and rationale. They never silently rewrite another agent's code.
- **Builders run in worktrees.** Any agent that edits code declares `isolation: worktree`.

### Sections every agent should have

1. **A one-line role statement** at the top of the body (before the first heading).
2. **Principles** — the non-negotiable beliefs that shape every decision.
3. **When invoked** — the ordered procedure the agent follows.
4. **Anti-patterns** — concrete things the agent refuses to ship.
5. **Handoffs** — which other agents it hands off to, and for what.
6. **Human checkpoint** — the changes that require explicit human sign-off (see below).

Builders may add **Security checklist**, **Observability**, **Performance**, and **Pre-merge checklist** sections — see `agents/backend-developer.md` as the reference.

## Adding a new command

Create `commands/<name>.md`.

### Frontmatter fields

| Field | Required | Notes |
|-------|----------|-------|
| `description` | yes | One sentence on what the command scaffolds or orchestrates. |
| `argument-hint` | yes | The argument shape shown to the user (e.g. `<feature-name> [--inertia\|--livewire\|--api\|--blade]`). |
| `allowed-tools` | yes | Tools the command itself may use — usually read-only (`Read, Bash, Grep, Glob`), since it delegates the writing. |

### Conventions

- Use `{{args}}` to interpolate the user's arguments into the body.
- **Commands orchestrate; specialists build.** A command detects context, then delegates each layer to the right specialist agent (e.g. `database-developer`, then `backend-developer`, then `qa-engineer`, then `tech-lead` for review). The command itself should not be doing builder work.
- Include a **Guardrails** section (match the project's conventions, don't import new patterns) and an **Output** section (summarize files, routes, tests, and any human checkpoints surfaced). See `commands/make-feature.md`.

## Model selection

- **Opus** — deep-reasoning and review roles where analysis quality matters most (e.g. `tech-lead`, solution architecture).
- **Haiku** — aggregation and status roles that summarize or coordinate cheaply.
- **Sonnet** — the default for everything else, including most builders.

## Adding or changing a guardrail script

- Hooks read the tool invocation as JSON on stdin, `exit 0` to allow and `exit 2` to block, and print explanations to stderr.
- Start with `set -euo pipefail`. Degrade gracefully if a dependency like `jq` is missing.
- Be conservative: prefer a soft warn over a hard block when a legitimate local-dev workflow could trip the rule. Document the choice inline.

## Testing changes

Before opening a PR:

```sh
./tests/guardrails.test.sh        # run the guardrail test harness (zero dependencies)
shellcheck scripts/*.sh tests/*.sh   # lint the guardrail hooks + harness
shellcheck install.sh             # lint the installer
```

`tests/guardrails.test.sh` is a pure-bash harness — no `bats`, no install step — so it runs identically on your laptop and in CI. It covers every guardrail script, including the no-`jq`/no-`python3` fallback path. If you change a script's behavior, add or update its assertion. If you add a script, add tests for it. CI (`.github/workflows/ci.yml`) runs the same harness twice: once normally, once with `jq` removed.

## Commits and pull requests

- **Conventional commits.** Prefix with `feat:`, `fix:`, or `docs:` (e.g. `feat: add caching-strategist agent`, `fix: harden prod-artisan guardrail regex`).
- **One logical change per PR.** A new agent, a guardrail fix, or a docs update — not all three at once. Smaller PRs review faster.
- Keep the agent voice consistent with the rest of the pack. When in doubt, read [`docs/authoring-agents.md`](docs/authoring-agents.md).
