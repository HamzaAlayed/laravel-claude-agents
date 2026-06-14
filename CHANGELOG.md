# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.2.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.2.0
[1.1.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.1.0
[1.0.0]: https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v1.0.0
