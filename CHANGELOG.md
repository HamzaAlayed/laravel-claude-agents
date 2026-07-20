# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.15.0] - 2026-07-20

The pack stops taking its own word for it. After five releases of scaffolding around the
agents, this one measures the agents themselves: a real eval harness that runs them headless
against a deliberately flawed Laravel app — plus the first speed pass on the delivery
pipeline, informed by what the timing data feeds back.

### Added

- **Fixture app** (`tests/fixture-app/`) — a small Laravel 13 blog (PHP 8.3, Pest 4) with five planted flaws:
  an N+1 in the posts index (Blade loop reading `user` + `comments` with no eager load), an
  unguarded `update` route (no Policy, no `authorize()`), mass assignment (`$guarded = []`
  + `$request->all()`), a fat `store()` (inline validation, slug loop, mail fan-out, stats
  bookkeeping), and zero test coverage on the `posts.*` routes. The answer key deliberately
  lives in `tests/eval/README.md`, **not** in the fixture — agents under evaluation can't
  read what they're being graded on.
- **Eval harness** (`tests/eval/run-evals.sh`) — four cases (`n-plus-one`, `policy`,
  `action`, `tests`), each: copy the fixture to a throwaway workdir, install the pack into
  it, run one headless `claude -p "/<command> …"`, assert against the answer key (agent
  output *and* files on disk). Every run is timed; results, diffs, and the
  `agents-board.jsonl` per-agent event stream land in a gitignored results dir. Manual by
  design — every case is a real billed agent run — with a `--list` mode, per-case selection,
  timeout, and `KEEP_WORKDIR=1` inspection. CI shellchecks it (`tests/eval/*.sh` added to
  the strict pass).
- **First eval findings** at `docs/evals/` — what the agents caught, what they missed, and
  where the wall-clock went, feeding the next speed pass.

### Changed

- **Coordinator fast path.** A single-specialist, no-checkpoint ask that lands on
  `delivery-coordinator` no longer pays for the pipeline: one precise brief, relay the
  stage return, done — no board, no delivery log. The description now advertises this so
  auto-delegation stops treating the coordinator as mandatory overhead.
- **`/make-feature` pipeline parallelized.** Database stage still leads (everything reads
  its schema), but backend + frontend now run **in parallel** against the migration's field
  list + planned route names as contract (they touch disjoint paths), and tech-lead review
  runs **in parallel with** qa-engineer's test stage (review needs the implementation diff,
  not the tests). Worst-case five sequential stages become three.
- **Full suite runs once.** Coordinator verification uses filtered tests + `pint --test
  --dirty` per stage; the full suite runs a single time at final integration — the
  per-stage full-suite rerun was the biggest wall-clock sink in a multi-stage delivery.

### Fixed

- Stray characters (`drtdd`) before the doctype in `scripts/board.html` rendered as
  visible text at the top of the `/board` dashboard.

## [1.14.0] - 2026-07-09

The guild gets names. Every agent is now a character you can address directly — named after
the Laravel-ecosystem tool closest to its craft.

### Added

- **Guild names for all 17 agents.** Artisan (backend), Blade (frontend), Eloquent (database),
  Dusk (QA), Forge (DevOps), Octane (performance), Fortify (security), Telescope (tech lead),
  Scribe (technical writer), Pulse (scrum master), Envoy (delivery coordinator), Scout
  (business analyst), Horizon (product owner), Blueprint (solution architect), Breeze
  (UI/UX designer), Passport (mobile), Composer (packages). Each agent body now opens with its
  identity line (`You are **Dusk** — the Guild's QA engineer.`) and each `description` is
  prefixed with the name, so name-addressed delegation ("have Artisan add an idempotency key")
  routes to the right specialist.
- **"Meet the Guild" roster in the README** — name ↔ agent ↔ namesake table, plus names in the
  file-tree annotations.

### Changed

- **`/board` dashboard shows guild names.** Runs render as "Dusk · qa-engineer" (name bold,
  slug muted), avatars use the guild name's first two letters, and agent lookups now strip a
  plugin namespace prefix (`laravel-team:qa-engineer`) before resolving colors/names — fixing
  fallback-gray avatars when installed as a plugin.
- `docs/authoring-agents.md` records the convention: new agents pick an unused ecosystem name
  and register it in the README roster and `board.html`'s `GUILD` map.

## [1.13.0] - 2026-07-08

The 1.12.0 progress board, upgraded from text to glass: a live HTML dashboard you can leave
open on a second screen while the team works.

### Added

- **`scripts/emit-agent-events.sh` — the agents-board observer.** Wired as `PreToolUse` +
  `PostToolUse` on the subagent tool (matcher `Agent|Task` — verified against the hooks docs:
  the Task tool was renamed Agent in 2.1.63, the alias still matches, and `tool_response`
  carries `totalDurationMs` / `totalTokens` / `status`). Streams every subagent start / finish
  to `.claude/agents-board.jsonl` — deterministic, fires regardless of what the orchestrating
  model narrates. An observer, not a guard: always exits 0, fails open, bounds the feed at
  ~4000 events. Claude Code only.
- **`scripts/board.html` — self-contained live dashboard.** No CDN, no build step; polls the
  feed every 1.5s. Running agents pulse with a live elapsed timer; finished ones show duration
  + tokens; sessions grouped newest-first; per-agent colors matching the pack's frontmatter
  colors; dark/light via `prefers-color-scheme`. The observer drops it next to the feed on
  first event.
- **`/board [port]` (11th command):** serves `.claude/` over localhost and opens the dashboard.
  install.sh's hook merger now handles multiple hook events (was PreToolUse-only); 9 new
  observer cases in the guardrail harness (76 total).

### Changed

- Gemini target deliberately skips `board.md` and the observer hook — Gemini's hook input
  carries no subagent identity (same reasoning as `enforce-reviewer-readonly.sh`). Gemini
  stays at 10 commands; Claude/Cursor manifests now say 11.

## [1.12.0] - 2026-07-08

The working interface release: a multi-agent run used to be a silence between kickoff and
verdict — no live progress, checkpoint asks buried in prose, every specialist reporting in its
own shape.

### Added

- **Progress board:** `delivery-coordinator` (new "Working interface" section) and all 9
  orchestrating commands print a stage board after planning and after every stage —
  `✔ done / ▶ running / · queued / ✖ failed / ⏸ checkpoint`, owner, one-line result. The plan
  board prints *before* any agent burns tokens, so the human approves the shape of the work first.
- **Uniform stage return:** every specialist is briefed to reply in
  `STATUS / DID / VERIFIED / FLAGS / NEXT` (≤10 lines). An empty `VERIFIED` is treated as a
  claim, not a return.
- **Checkpoint prompts as decisions:** numbered options + recommended default + stated blast
  radius. `delivery-coordinator` gains the `AskUserQuestion` tool — verified against the Agent
  SDK docs: grantable in `tools:`, works main-thread (`claude --agent delivery-coordinator`),
  unavailable in subagents, so the body specifies the text fallback for subagent runs. The 9
  commands also carry it in `allowed-tools` (main-thread by nature).

## [1.11.0] - 2026-07-08

The team now learns from its users. A correction given to one agent used to die in that agent's
transcript — builders carry no memory, and per-agent memory never crosses roles or runtimes.

### Added

- **`docs/team/conventions.md` — the taught-rules ledger.** User-taught rules in a
  Rule / Why / Scope / Source shape. Chosen over widening per-agent `memory:` because the ledger
  reaches everyone: memoryless builders, all 17 roles at once, and the Gemini/Codex mirrors
  (agent bodies port verbatim; Claude-only memory doesn't).
- **`/teach` command (10th):** records a rule or preference into the ledger — checks for
  conflicts and updates in place rather than leaving two entries that disagree. With no args it
  harvests the current session's corrections and proposes entries. Points hard project
  constraints at `CLAUDE.md` instead of the ledger.
- **"Taught rules win" — first principle in all 17 agents:** read the ledger when present,
  treat entries as overrides of defaults, apply a mid-task correction immediately and flag it in
  the report so it gets recorded.
- **delivery-coordinator records what the human teaches:** new step 8 appends mid-delivery
  corrections (its own or ones flagged in specialist returns) to the ledger; briefs quote the
  taught rules that bind each stage so specialists don't burn a first attempt finding out.
- Authoring guide: taught-rules-ledger section + checklist item; `CLAUDE.md.template` documents
  the ledger under the agent delivery model.

### Fixed

- Stale inventory counts from 1.10.0: manifests and README now say 10 workflow commands and
  5 guardrail hooks.

## [1.10.0] - 2026-07-08

Field feedback release: agents on Sail projects kept reaching for host PHP, and multi-agent runs
re-derived the same stack facts at every hop. Both fixed.

### Added

- **`scripts/enforce-sail.sh` (5th guardrail):** on a project that actually runs on Sail
  (executable `vendor/bin/sail` **and** a compose file — the sail *dependency* alone, the
  Herd/Valet shape, is deliberately not enough), bare `php artisan`, `composer`, and
  `vendor/bin/{pint,pest,phpunit,phpstan,paratest}` are blocked with the exact
  `./vendor/bin/sail …` rewrite in the message, so the agent self-corrects in one turn instead
  of flailing against the wrong runtime. Opt out with `LARAVEL_AGENTS_SAIL=0`. Wired into all
  three hook homes (plugin manifest, `install.sh` merge list, README) plus the Gemini
  (`BeforeTool`) and Codex (`PreToolUse`) targets; 16 new cases in `tests/guardrails.test.sh`.
- **Sail-first principle in 10 agent bodies** — builders get the rewrite table
  (`sail artisan test`, `sail composer require`, `sail bin phpstan`), the read-only reviewers get
  the verification form (`sail pint --test`, `sail composer audit`), devops gets the
  local-vs-CI-runtime distinction, technical-writer documents the sail form when it's the
  project's dev runtime.

### Changed

- **Latency trims for multi-agent runs.** delivery-coordinator briefs now carry the stack
  snapshot (Laravel major, key packages, Sail or host PHP, test runner) forward after the first
  specialist reports it, and backend / frontend / database / qa specialists trust a snapshot-carrying
  brief instead of re-reading `composer.json` + configs on every invocation. backend-developer's
  pre-merge checklist runs `pint --dirty` and `--filter`ed tests while iterating, with the single
  full `--parallel` run reserved for the handoff.

The pack has a name: **Laravel Guild** — a guild of 17 master craftspeople for your Laravel codebase.

### Changed

- Display branding is now **Laravel Guild** across the README title and all four plugin/marketplace `displayName` fields. The repo slug, plugin `name` (`laravel-team`), and every install URL are unchanged — nothing breaks for existing installs.

### Added

- **skills.sh distribution channel:** the 8 skills install standalone into ~20 agent runtimes via `npx skills add HamzaAlayed/laravel-claude-agents` (verified end-to-end — the CLI resolves all 8 from `skills/`). Documented in the README install section; the skills.sh leaderboard listing builds from install telemetry.

## [1.8.2] - 2026-07-06

Docs-accuracy release: the front door catches up with 1.5.0–1.8.1.

### Fixed

- README "What's in here" tree: model tiers corrected (tech-lead **Sonnet**, security-engineer **Opus**, technical-writer **Haiku** — flipped in 1.5.0 but never updated here), the long-stale "frontend-design skill" annotation removed (skill deleted in 1.2.0), missing `worktree` markers added (qa, devops, ui-ux), all 8 skills listed (was 1), hook count 3 → 4, `enforce-reviewer-readonly.sh` added to the scripts tree.
- All four plugin/marketplace manifest descriptions and both generator description strings updated from "a conventions skill" to the real inventory: 9 commands, 8 skills, MCP grants, 4 guardrails. Codex `AGENTS.md` intro now names all 8 shipped skills.

## [1.8.1] - 2026-07-06

### Changed

- **Body slimming (deferred from 1.7.0):** qa-engineer and performance-engineer no longer inline the recipe detail their skills carry — fake-assertion syntax, Livewire/Inertia test chains, browser-test recipes point at `laravel-testing`; EXPLAIN red flags, chunking, and the caching decision tree point at `eloquent-performance`. Rules, verdict logic, and anti-patterns stay inline. security-engineer's static-review checklist deliberately kept whole — it is the agent's core function at the pack's highest failure cost, not cookbook detail.

### Added

- **`scripts/check-hook-sync.py` + CI step** — fails when the guardrail hook list drifts between its three homes (plugin `hooks/hooks.json`, the `install.sh` merge list, the README table), or when a named script is missing/not executable. The list was hand-synced twice in one day; now CI enforces it.

### Fixed

- Two `**Human checkpoint:**` labels (qa-engineer, security-engineer) missed by the 1.5.0 standardization to `**Human checkpoint required:**` — the grep-able audit label now really covers all 17.

## [1.8.0] - 2026-07-06

The read-only reviewer guarantee is now enforced, not just instructed.

### Added

- **`enforce-reviewer-readonly.sh`** — a fourth `PreToolUse` guardrail closing the documented Bash write-vector (docs/read-only-by-design.md). The hook input's `agent_type` field identifies the calling subagent, so the guard blocks file-mutating Bash **only** from `tech-lead`, `security-engineer`, and `performance-engineer` (plugin-prefixed names handled): `sed -i` / `perl -i`, output redirects, `tee`, mutating `git` subcommands, state-changing `artisan`, `composer`/`npm` installs, `pint` without `--test`, `rm`/`mv`/`cp`/`chmod`. Safe forms stay allowed: `2>&1`, `>/dev/null`, `/tmp` targets, `migrate:status`, `pint --test`, PHP `->` arrows. Builders, devops, and the main thread are untouched. 19 new harness cases (51 total) including both parser-less fallback directions.
- Wired everywhere Claude Code loads hooks: plugin `hooks/hooks.json` and the `install.sh` settings merge.

### Notes

- **Claude Code only.** Gemini CLI's hook input carries no agent identity (control there remains instruction + allowlist); Codex Core ships no subagents. docs/read-only-by-design.md updated — the former "opt-in stricter policy" is now defense-in-depth on top of an enforced default.

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
