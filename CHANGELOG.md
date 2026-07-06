# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2026-07-06

Skills for every role: 7 new on-demand cookbooks join `laravel-conventions`, and every agent can now actually invoke them.

### Fixed

- **No agent could use skills at all.** Every agent has an explicit `tools:` allowlist, and none included the `Skill` tool — so even the pack's own `laravel-conventions` skill was uninvokable by the team it ships with. All 17 agents now carry `Skill`.

### Added

- **7 new skills**, each a deep procedural cookbook in house voice: `laravel-testing` (fakes assertion syntax, Pest v4 browser testing, factories, time control), `eloquent-performance` (EXPLAIN reading, N+1 recipes, caching decision tree), `laravel-security` (STRIDE-on-Laravel, advisory lookup, finding format), `laravel-deploy` (zero-downtime checklist, worker/scheduler topology, rollback drill), `delivery-templates` (requirements/story/RICE/sprint/retro/health-report/delivery-log shapes), `accessibility-design` (WCAG 2.2 AA thresholds, Livewire/Inertia focus management, mobile a11y), `docs-authoring` (changelog/release-notes/runbook/endpoint-reference templates).
- **Every agent maps to at least one skill** via a terse "Skill on demand: `name` when <trigger>" body line — planning, security, devops, docs, and design roles included, not just builders.
- README **Skills** section: the skill → agent map, the preload-vs-on-demand cost rationale, and the complementary official plugins (`laravel@laravel`, `laravel-cloud`, `laravel-nightwatch`, `document-skills@anthropic-agent-skills`).

### Notes

- **Deliberately no `skills:` frontmatter preloads** — per Claude Code docs the field injects full skill content into the subagent on every invocation; on-demand invocation via the `Skill` tool costs zero until a task needs the cookbook. Authoring guide updated to warn contributors.
- Both generators copy `skills/` wholesale, so all 8 skills ship in the Gemini and Codex targets automatically.

## [1.6.0] - 2026-07-06

MCP integration: the agents now know how to use the MCP servers a Laravel team actually attaches — and degrade gracefully when they're absent.

### Added

- **Role-matched MCP grants** in agent frontmatter (server-level, e.g. `mcp__laravel-boost` — robust to vendors renaming individual tools): Laravel Boost (backend, database, qa, performance, security, tech-lead, technical-writer), Context7 (backend, frontend, mobile, package, solution-architect), Playwright (frontend, qa, ui-ux-designer), Sentry (devops, performance, security), Linear + Atlassian/Jira (business-analyst, product-owner, scrum-master, delivery-coordinator), Figma Dev Mode (frontend, mobile, ui-ux-designer). Grants verified against the Claude Code subagents docs; they are inert when a server isn't connected.
- **Conditional usage lines in every body** ("MCP exposed → prefer it; absent → existing fallback"), in house voice: Boost `search-docs` for version-true framework answers, `database-schema`/`database-query` for live schema + `EXPLAIN`, `last-error`/`read-log-entries` for prod-bug reproduction; Playwright to drive routes headless in self-test; tracker MCPs for live sprint/backlog state; Figma file-node specs instead of eyeballed screenshots.
- **README "MCP servers" section** — expected server names, attach commands, per-agent usage map, and the read-only-extends-to-MCP note for reviewer agents.

### Notes

- Read-only reviewers state explicitly that read-only discipline applies to MCP too.
- Gemini mirror: MCP grants are intentionally dropped by the generator (Gemini CLI configures MCP in its own settings); the conditional body instructions port unchanged.

## [1.5.1] - 2026-07-06

### Fixed

- **Plugin hooks failed to load** ("Duplicate hooks file detected"). Claude Code auto-loads the standard `hooks/hooks.json`, and `plugin.json` *also* referenced it via `manifest.hooks` — the duplicate registration aborted the entire hooks load, silently disabling the prod-SQL / prod-artisan / `.env` guardrails. Removed the redundant `"hooks"` key from the Claude and Cursor manifests (`manifest.hooks` is only for *additional* hook files beyond the standard path).

## [1.5.0] - 2026-07-06

A 57-subagent, adversarially-verified upgrade of all 17 agents on three axes: technical accuracy, mistake-reduction guardrails, and AI cost. Every finding was fact-checked against live Laravel / Claude Code docs before being applied (351 confirmed; ~⅓ of raw findings refuted).

### Fixed

- **Real factual errors that produced wrong output:** `$this->authorize()` fatals on fresh Laravel 11+ apps (empty base `Controller`) → `Gate::authorize()`; nonexistent `actions/setup-php` → `shivammathur/setup-php`; nonexistent `dedoc/scribe` → Scramble (`dedoc/scramble`); "no Octane on Vapor" (false since 2021); abandoned Enlightn removed from security tooling; `pulse:check` misuse (long-running daemon, not a diagnostic); `updateOrCreate()` event semantics; RFC 7807 → RFC 9457.
- **Stale version anchoring:** Livewire 4, Tailwind v4 (`@theme`, CSS-first tokens), Pest v4 browser testing (vs Dusk, detect-and-match), Laravel Cloud, Inertia `Inertia::defer()`, `#[Validate]`, Laravel 12+ online-DDL (`->instant()`). Hardcoded "Modern Laravel (11+)" sections replaced with detect-from-`composer.json` + verify-against-docs logic so guidance can't rot again.

### Changed

- **Model tiers re-priced by failure cost × invocation frequency:** `tech-lead` opus → sonnet (every-PR reviewer was the single largest cost line; prescriptive rubric runs fine on sonnet), `security-engineer` sonnet → opus (a missed vulnerability has no downstream gate — funded by the tech-lead downgrade, net opus spend falls), `technical-writer` sonnet → haiku (fixed-format docs from machine-readable sources, human-reviewed). The other 14 tiers were each explicitly justified and kept.
- **Output discipline pack-wide:** every agent now returns distilled findings/summaries to the orchestrator — never raw test/log/scanner/PR dumps (the largest hidden token leak). Duplicated rules cut from the heaviest bodies; soft body-size budgets adopted.
- **Descriptions sharpened for routing:** proactive triggers everywhere; overlap boundaries disambiguated (database-developer vs performance-engineer on slow queries, ui-ux-designer vs frontend-developer on "build the screen", scrum-master vs delivery-coordinator on orchestration).

### Added

- **"Anti-patterns (refuse to ship)" sections for the 9 agents missing them** — role-specific refuse-lists (QA: no weakening tests to go green; scrum-master: no invented metrics; tech-lead: no asserting checks that never ran).
- **Verify-before-assert guardrails on reviewers:** security-engineer must trace an exploit before reporting it (no fabricated CVE/CVSS); tech-lead's bare `git diff` replaced with a state-aware base-diff procedure; solution-architect verifies version/package/pricing facts via WebFetch before writing ADRs.
- **Failure paths and verification mechanics for `delivery-coordinator`:** a subagent's "done" is a claim — re-run the brief's success criteria (`php artisan test --filter`, `pint --test`, `route:list`) before advancing; re-brief once, then escalate.
- **`qa-engineer` gains `isolation: worktree`** (it edits test files but ran in the main tree); `scrum-master` and `technical-writer` gain read-only Bash for the data their bodies already demanded; canonical `**Human checkpoint required:**` label standardized across all 17 (PII gap on backend-developer closed).
- Missing `## Memory` sections for `package-developer` and `performance-engineer`; pre-merge checklists for `devops-engineer` and `mobile-developer`.

### Notes

- Mirrors (`gemini/`, `codex/`) regenerated from canonical sources; strict-YAML validation passes on all 34 frontmatter files; guardrail suite 32/32.

## [1.4.0] - 2026-06-16

Fourth install target: a **Codex CLI** target alongside Claude Code, Cursor, and Gemini CLI.

### Added

- **Codex CLI "Core" target** under `codex/` (install via `codex/install-codex.sh <project>`, since Codex has no extension-install command): `AGENTS.md` (Codex's native context, from the template), the `laravel-conventions` skill (verbatim — Codex uses the same agentskills.io standard, under `.agents/skills/`), and the three guardrail hooks wired as `PreToolUse` in `.codex/hooks.json` (script paths resolved from the git root).
- **`scripts/build-codex-extension.py`** — deterministic generator for the Codex target (idempotent; keeps `codex/` in sync with the canonical template, skill, and guard scripts).
- **`scripts/codex-protect-env-files.sh`** — an `apply_patch`-aware `.env`/secrets guard. Codex delivers edits as a patch, so it extracts the target path from the `*** Add/Update/Delete File:` headers (never scans patch content, which would false-positive on files merely mentioning `.env`). `block-prod-*` port verbatim (same `.tool_input.command` / `exit 2` contract).
- Guardrail test harness gains 8 Codex cases (32 total), including "patch mentions .env in content → allowed" and the no-parser fallback. CI gains a `codex target` job (hooks.json validity + generator-in-sync) and shellcheck over the Codex scripts.

### Changed

- Bumped to **1.4.0** (VERSION + Claude/Cursor/Gemini manifests; CI keeps them in sync).

### Notes

- **Scope is "Core."** The 17 subagents are not ported — Codex's subagent model is a different `config.toml [agents]` schema. Codex Core ships the conventions skill + guardrails; the full team runs on Claude Code / Gemini CLI. Format verified against the official OpenAI Codex docs (hooks.json structure, `PreToolUse` deny-via-`exit 2`, git-root path resolution, trust-on-first-run).

## [1.3.0] - 2026-06-15

Third install target: the pack now ships as a **Gemini CLI extension** alongside the Claude Code plugin and Cursor plugin — one repo, three targets.

### Added

- **Gemini CLI extension** under `gemini/` (`gemini extensions install ./laravel-claude-agents/gemini`): `gemini-extension.json` manifest, `GEMINI.md` context, 17 subagents, 9 TOML commands, the `laravel-conventions` skill, and the guardrail hooks wired as `BeforeTool`.
- **`scripts/build-gemini-extension.py`** — a deterministic generator that produces the Gemini extension from the canonical Claude-format source, so the two never drift. Translates frontmatter automatically: tool-name mapping (`Bash`→`run_shell_command`, `Read`→`read_file`/`read_many_files`, `Edit`→`replace`, `Grep`→`search_file_content`, …), read-only reviewers re-expressed as a tools allowlist (Gemini has no `disallowedTools`), Markdown commands → TOML (`{{args}}` preserved verbatim — it's already Gemini's placeholder), `Agent(...)` roster dropped (delegation via `@name`), and `model`/`isolation`/`memory`/`color` dropped. Bodies are preserved byte-for-byte; Claude-isms (`CLAUDE.md`, `claude --agent`, model names, `(worktree)`) are rewritten for the Gemini target.
- **CI `gemini extension` job**: validates the manifest, all command TOML, agent frontmatter, asserts the read-only reviewers carry no write tool, and — key — fails if `gemini/` is out of sync with the generator. Versions across VERSION + all manifests (Claude/Cursor/Gemini) are kept in sync by CI.

### Changed

- `protect-env-files.sh` now also reads `tool_input.absolute_path` (Gemini's `write_file`/`replace` path field) in addition to `path`/`file_path` — backward-compatible.
- Bumped to **1.3.0**.

### Notes

- **The Gemini CLI format was verified against live Google docs**, including the load-bearing details: subagent `.md`+YAML frontmatter, `${extensionPath}` script references in `BeforeTool` hooks, and the `exit 2` block contract (identical to ours). What does **not** port: `isolation: worktree` (Gemini isolates context, not the git worktree), per-agent `memory`, and a fixed `Agent(...)` delegation roster.
- **Sunset:** Google sunsets Gemini CLI for consumer (Individual/AI Pro/AI Ultra) accounts on 2026-06-18 in favor of Antigravity (Standard/Enterprise unaffected). Installed extensions auto-migrate to Antigravity plugins — Skills, Hooks, Subagents, and `GEMINI.md` carry over. This pack has no Node-only APIs, so it migrates cleanly.

## [1.2.0] - 2026-06-14

A research-driven, one-by-one audit of all 17 agents for result quality and token economy. Best practices were gathered from official Claude Code / Anthropic docs, adversarially verified, and applied. Verified subagent mechanics drove a key course-correction (below).

### Fixed

- **Broken skill reference.** `frontend-developer` and `ui-ux-designer` declared `skills: [frontend-design]`, a skill that does not exist in the repo (it loaded nothing and warned at startup). Removed.
- **`business-analyst` could not write its own output.** It's instructed to produce `docs/requirements/<slug>.md` but lacked the `Write` tool (and its `memory: project` couldn't persist). Granted `Write, Edit`.
- **Read-only reviewers couldn't persist their reports.** `security-engineer` and `tech-lead` are told to produce `docs/**.md` yet carry `disallowedTools: Edit, Write`. Resolved by the **orchestrator-persists** model: reviewers now *return* their reports and the `delivery-coordinator` (granted `Write, Edit`) persists them.

### Changed

- **Reviewers are explicitly read-only**, including via `Bash`. `security-engineer`, `performance-engineer`, and `tech-lead` now state they must not modify files through `Bash` (`sed -i`, `git checkout`, redirects) and return distilled findings, not raw scanner/EXPLAIN/test dumps. New [docs/read-only-by-design.md](docs/read-only-by-design.md) documents the layered controls, the residual `Bash` write-vector, and an opt-in stricter policy.
- **WHEN-first `description` fields** on the highest-traffic routers (`backend-developer`, `frontend-developer`, `ui-ux-designer`, `delivery-coordinator`) — they now lead with delegation triggers, which is all the orchestrator selects on (and is loaded for every agent every session).
- **`isolation: worktree`** added to `devops-engineer` and `ui-ux-designer` (parallel-running writers).
- **Abstention / citation contracts** added to advisory roles: `business-analyst` and `product-owner` flag gaps instead of fabricating; `technical-writer` cites `path:line`/PR# or marks TODO; `database-developer` leads with the EXPLAIN verdict.
- Bumped to **1.2.0** (VERSION + both plugin manifests, kept in sync by CI).

### Investigated but deliberately NOT done

- **DID NOT "DRY" the shared conventions into the `laravel-conventions` skill via agent `skills:` frontmatter.** Verified against the docs: a subagent's `skills:` field **preloads the full SKILL.md (~1k tokens) into that agent at startup** — it is not progressive disclosure. Referencing the skill from ~7 agents would have *added* ~7k tokens, not saved ~560. The skill stays available on-demand to the main thread; agents keep their concise inline conventions. The real (small) token win is in-file de-duplication, applied conservatively to avoid regressing hand-tuned content.
- **DID NOT remove `memory: project` from the read-only reviewers.** Verified: memory degrades gracefully without `Write` (it still provides cross-session read recall) and the `disallowedTools: Edit, Write` line is **load-bearing** — it cancels the `Write`/`Edit` that `memory: project` auto-grants. Removing it would have silently made the reviewers writable.

## [1.1.0] - 2026-06-14

Alignment with Laravel's official [`laravel/agent-skills`](https://github.com/laravel/agent-skills) pack — adopt its primitives and conventions, defer to its tools, and position this team as a complement rather than a competitor.

### Added

- **Skills primitive.** New `skills/laravel-conventions/` skill (`SKILL.md` + `reference/antipatterns.md`) — an idiomatic-Laravel "which primitive, which antipattern" reference that auto-triggers on convention questions. Wired into both plugin manifests via `"skills": "./skills/"`.
- **Cursor support.** `.cursor-plugin/plugin.json` + `.cursor-plugin/marketplace.json` mirror the Claude manifests so the pack installs in Cursor too.
- **"Pairs with the official Laravel pack" README section** — recommends co-installing `laravel`, `laravel-cloud`, and `laravel-nightwatch`, and explains how the work divides (Boost owns framework bumps, `laravel-simplifier` owns after-the-fact cleanup, the official skills own Cloud/Nightwatch).
- **CI manifest checks** extended to validate the Cursor manifests, keep Claude/Cursor `name`+`version` in sync with `VERSION`, and lint `SKILL.md` frontmatter.

### Changed

- **`/upgrade-laravel` defers to Laravel Boost.** Recommends Boost's `/upgrade-laravel-v13`, `/upgrade-livewire-v4`, `/upgrade-inertia-v3` for the framework diff and scopes itself to the surrounding work (PHP runtime, package compat, structural 10 → 11 audit, verification).
- **Coding-standard alignment with `laravel-simplifier`.** `tech-lead` gains a "Clarity & simplification" review axis (no nested ternaries → `match`, explicit return types, early returns, clarity over brevity, behavior-preserving). `backend-developer` and `frontend-developer` pick up the matching antipatterns.
- Plugin/marketplace metadata enriched (`displayName`, `metadata.description`, per-plugin `author`/`category`); bumped to **1.1.0**.

## [1.0.0] - 2026-06-14

First tagged release. The pack is now installable as a Claude Code plugin, the
guardrail scripts are tested in CI, and the agent/command roster has grown.

### Added

- **Claude Code plugin packaging.** `.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` make the whole pack installable with
  `/plugin marketplace add HamzaAlayed/laravel-claude-agents` then
  `/plugin install laravel-team@laravel-claude-agents`. No more `curl | bash`
  required (the installer is still supported).
- **Plugin hooks manifest** (`hooks/hooks.json`) wiring the three guardrail
  scripts via `${CLAUDE_PLUGIN_ROOT}` so they resolve from the installed plugin
  directory.
- **`performance-engineer` agent** — profiling, N+1/query optimization, caching
  strategy, queue/Horizon throughput, Octane, OPcache, and Core Web Vitals.
  Measures first, hands fixes to the right builder, never optimizes on a hunch.
- **Four new slash commands:** `/add-test`, `/review-pr`, `/optimize-query`,
  `/upgrade-laravel`.
- **Zero-dependency test harness** (`tests/guardrails.test.sh`) covering all
  three guardrail scripts, including the no-`jq`/no-`python3` fallback path.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): shellcheck, the guardrail
  test harness (run twice — with and without `jq`), JSON manifest validation,
  and agent/command frontmatter linting.
- **Repo hygiene:** `LICENSE` (MIT), `VERSION`, `CONTRIBUTING.md`, `CHANGELOG.md`,
  and `docs/authoring-agents.md`.

### Changed

- **Guardrail scripts no longer fail open when `jq` is missing.** They now
  degrade `jq` → `python3` → raw-payload scan, so a missing JSON parser can no
  longer silently disable a security guard.
- **Broader destructive-SQL matching.** Multiline statements are flattened before
  matching, `UPDATE ... SET` now recognizes table aliases
  (`UPDATE orders AS o SET ...`), and `DROP` covers `TABLE`/`DATABASE`/`SCHEMA`/`INDEX`.
- **`protect-env-files.sh`** uses a boundary-aware regex that matches protected
  `.env*` files in both a clean path and the raw payload, while still allowing
  `.env.example`.

[1.4.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.4.0
[1.3.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.3.0
[1.2.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.2.0
[1.1.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.1.0
[1.0.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.0.0
