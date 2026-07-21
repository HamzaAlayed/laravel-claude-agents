# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.21.0] - 2026-07-21

### Added

- **`/team-hygiene` — the 12th command.** Sweeps the `docs/team/` ledger for the four
  rot classes (duplicates, conflicts, facts whose **Verify** command fails, dead
  scopes), delegates the scan to scrum-master (cheap, has Bash for Verify), and
  proposes one keep/merge/evict table — **nothing applies without an approved row**;
  headless runs output the table only. Evictions append a line to `decisions.md` so
  the removal itself is remembered. Coordinator's delivery-end eviction now delegates
  to this sweep; proposal-table template added to delivery-templates.
- **Fifth eval case (`hygiene`).** The harness seeds a rotten ledger (UUID duplicate
  pair, Pest-vs-PHPUnit conflict, stale `LegacyPayments` Verify) and asserts the
  proposal table catches all three while the ledger stays untouched.
- **README: eval scorecard + fail-closed positioning.** "Proven against a planted-flaw
  app" section with the three-run results table, and a design-choices paragraph on why
  the guardrails failing closed (tested parser-fallback chain, CI runs the suite with
  and without jq) is the pack's posture — versus harnesses gating autonomous shell
  behind fail-open hooks.
- Inventory checker now also covers `.cursor-plugin/marketplace.json` and the README's
  eval-case count (derived from `ALL_CASES`). Command-count claims updated everywhere
  (12 / gemini 11); a stale "11 slash commands" claim in the README's Gemini section
  (should have been 10) was caught and fixed in the process.

## [1.20.0] - 2026-07-21

### Added

- **Delegation tree on the board.** `emit-agent-events.sh` now records `parent` — the
  hook stdin's top-level `agent_type` identifies the calling agent when a spawn happens
  inside another subagent (verified against the hooks docs; absent from the main
  thread). `board.html` indents child lanes under their spawner with a `↳ parent` tag.
- **Async-launched agents are visible.** New `SubagentStop` hook registration (plugin
  `hooks.json` + `install.sh` merge list): fires on completion of sync AND async
  subagents, carrying `duration` — the completion signal async agents never had
  (PostToolUse fires at launch with `status: async_launched` and null ms/tokens; eval
  run 3 finding). The board now keeps an async lane open at launch (tagged background)
  and closes it with real duration on `subagent_stop`; a `subagent_stop` with no open
  lane (sync run already closed by PostToolUse) never creates a ghost lane.
- Four new guardrail tests (82 total): nested-spawn parent capture, top-level parent
  null, SubagentStop→end mapping with `ms` from `duration`, SubagentStop twin dedupe.
  Both parser branches (jq / python3 fallback) verified.

## [1.19.0] - 2026-07-21

### Added

- **`NOT-CHECKED` in the stage-return contract.** Every specialist return now names the
  surfaces it deliberately did not examine (≤3 lines) alongside evidence-backed
  `VERIFIED` — a Ship/Approve verdict without its gaps named is uncalibrated. The
  coordinator re-briefs an incomplete return exactly once (naming the missing fields
  verbatim), then surfaces it to the human; never silently accepts. Applied to the
  coordinator's shape, the four reviewer bodies (qa: Ship gates + "suite not run — no
  vendor/" moves from VERIFIED to NOT-CHECKED; tech-lead: verdict; security: report;
  performance: distilled numbers), all nine orchestrating commands' Interface line, and
  the README. Inspired by jcode's swarm deep-mode completion contract
  (docs/plans/2026-07-21-jcode-inspired-improvements.md).
- **Ratchet budgets in CI** (new `budgets` job). `scripts/check_body_budget.py` +
  committed `body_budget.json` freeze every agent body's line count, description
  length, and skill size at current +10% — growth fails CI, deliberate changes reseed
  via `--reseed`. `scripts/check_inventory_sync.py` verifies every count claim (README,
  all four manifests, the gemini build script) against disk, encoding the deliberate
  offsets (gemini = commands −1 for board.md; codex = its PreToolUse hook subset) —
  the 1.10.0 stale-counts class of bug is now structural, not remembered.
- **Eval timing baseline** (`tests/eval/baseline.json`): per-case duration ceilings
  from sequential runs 1–2. `run-evals.sh` prints within/REGRESSED per case on
  sequential runs — soft warning only, never a failure; parallel runs skip it
  (contention inflates 2–6×). The `tests` eval case now also asserts the return
  includes `NOT-CHECKED`.

## [1.18.0] - 2026-07-21

### Changed

- **Human names for the Guild.** Every agent's persona is now a human first name instead of a
  Laravel-ecosystem tool name — Artisan→Adam, Blade→Bella, Eloquent→Elena, Dusk→Dina,
  Forge→Farid, Octane→Omar, Fortify→Felix, Telescope→Tariq, Scribe→Sofia, Pulse→Petra,
  Envoy→Emre, Scout→Sara, Horizon→Hana, Blueprint→Bilal, Breeze→Bruno, Passport→Pablo,
  Composer→Clara. Each new name keeps the old name's initial, so `/board` initials and
  name-addressed habits carry over. Agent slugs (`backend-developer`, …) are unchanged —
  no routing or install-path breakage. Updated: all 17 agent bodies + descriptions, README
  roster (with a "Formerly" column), `scripts/board.html` `GUILD` map,
  `docs/authoring-agents.md` naming rule, regenerated gemini/ and codex/ trees.

## [1.17.0] - 2026-07-21

### Added

- **Parallel eval mode.** `EVAL_PARALLEL=1 ./tests/eval/run-evals.sh` runs all cases
  concurrently — safe because every case owns an isolated throwaway workdir. Console output
  buffers per case and prints in launch order as cases finish. Run 3 taught us the honest
  caveat (now in `tests/eval/README.md`): concurrent sessions contend for the same API limits,
  inflating per-case durations 2–6× — parallel is for pass/fail smoke, sequential for timing.
- **Third eval run + findings** (`docs/evals/2026-07-21-run-3.md`). 4/4 cases, 14/14 checks
  against the released 1.16.0 bodies — three runs, zero quality regressions. Lever scorecard:
  qa scope rule **worked** (`tests` case qa stage 448s/108.6k tok → 130s/50k); static-mode
  detection killed the retry-flailing (write cases now deliberately `composer install` and
  ship real passing suites instead); event dedupe had a race (below).

### Fixed

- **Agent-event dedupe race.** The 1.16.0 twin suppression compared against the feed's last
  line — but the twin hook invocations run *concurrently*, so both read before either wrote
  and the compare never fired (run 3 evidence: same-second duplicate lines). The emitter now
  serializes through an atomic `mkdir` lock (stale locks stolen after ~2s, fail-open — the
  dashboard never blocks delivery). Concurrent-twin regression test added (guardrails #78).
- **Eval watchdog drift.** The per-case timeout counted `sleep 5`s instead of reading a
  clock and drifted 601s past the cap under parallel load (`policy` at 2401s vs an 1800s
  limit). Now a wall-clock deadline, with TERM→KILL escalation after a 30s grace.
- **Fixture-app realism gaps** that taxed every write case with identical bootstrap work:
  `mockery/mockery` added to require-dev (a real Laravel 13 skeleton ships it; without it the
  test suite cannot boot, and every eval agent added it and flagged a phantom dependency
  approval), `.env.example` added, standard `storage/` + `bootstrap/cache/` directory
  skeletons added, and the `site_stats.posts_total` row is now seeded by its migration.

## [1.16.0] - 2026-07-21

The first release driven by the eval harness's own findings: run 2 confirmed 4/4 quality
across the rewritten 1.15.0 bodies and named three speed/correctness levers — all three land
here.

### Added

- **Second eval run + findings** (`docs/evals/2026-07-20-run-2.md`). Quality held at 4/4 with
  zero regressions after both 1.15.0 sweeps. `n-plus-one` got 4× faster (385s → 96s — the
  doomed dynamic-verification subagent is gone); `action` produced a bigger, better diff and
  overran the default timeout (checks still passed); qa-engineer confirmed as the token hog
  (108k tokens writing unrequested tests).
- **Static-mode detection.** performance-engineer, qa-engineer, and the `eloquent-performance`
  skill now decide run-vs-static in **one `vendor/` probe**: unrunnable app → declare static
  analysis and stop attempting execution. Run 1 lost 5+ minutes per case to retry-flailing
  `artisan` against an app with no dependencies installed.
- **qa-engineer scope rule.** Test the brief's scenarios; further scenarios go in `NEXT`, not
  the diff — more tests ≠ more value when the brief already named the risks.
- **Team knowledge base** — the taught-rules ledger grows into a three-file, repo-committed
  KB under `docs/team/`, designed from a two-track research pass (Claude Code native memory
  docs + the 2025–26 agent-memory literature: Cline/Cursor/Windsurf/Aider patterns,
  Letta/Reflexion, the Sandelin controlled benchmark). Findings that shaped it: memory pays
  22–32% on complex tasks *only by skipping re-discovery*, per-agent runtime memory is
  agent-isolated (17 silos) and unverified for plugins, and stale facts followed with perfect
  compliance are worse than nothing. Hence: `stack.md` — orientation layer of verified facts,
  each with a **Verify** command (trust-but-verify, never re-derive); `decisions.md` —
  rejected approaches with why (undiscoverable from code; prevents re-litigation);
  `conventions.md` — as before, plus a **Verify** field for facts vs preferences. All 17
  agents start oriented from the KB; the coordinator persists the stack snapshot, records
  rejections from FLAGS, and evicts stale entries at delivery end (flag-to-human, never
  silent delete). Storage rule: store what the repo can't answer (intent, taste, rejections);
  derive what it can (hot paths via `git log`, naming via siblings). Agents propose — the
  human approves — the repo remembers.

### Fixed

- **Doubled agent events on dual installs.** Installed both as a plugin and via `install.sh`,
  the emit-agent-events hook registers under two different command strings
  (`${CLAUDE_PLUGIN_ROOT}/scripts/…` vs `./scripts/…`), which escapes Claude Code's
  identical-command hook dedupe — every subagent start/end wrote twice and `/board` rendered
  duplicate lanes. The emitter now suppresses the twin (identical modulo timestamp, ≤2s
  apart), `board.html` dedupes older feeds defensively, and a regression test guards it in
  `tests/guardrails.test.sh`.
- Backfilled the missing `v1.14.0` git tag (releases v1.13.0 → v1.15.0 had a tag gap).

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

- **Laravel 13 verification sweep.** Five parallel auditors checked every Laravel-specific
  claim in the pack (~290 claims across 8 skills, 17 agent bodies, 4 commands) against a
  local checkout of the official `laravel/docs` 13.x branch. Doc-backed upgrades landed
  across the board: `#[Authorize]`/`#[Middleware]`/`#[UsePolicy]` as first-class authz
  surfaces (reviewers no longer flag attribute-based coverage as missing), queue attribute
  forms (`#[Tries]`/`#[Backoff]`/`#[Timeout]`/`#[DebounceFor]`) + `Queue::route()` central
  routing, JSON:API resources, the `Context` facade for trace propagation, `Concurrency::run()`
  (with `Octane::concurrently` correctly scoped to Swoole), `Cache::memo()`/`Cache::touch()`,
  automatic relationship autoloading as an N+1 net, `->online()` index creation, vector
  columns + `whereVectorSimilarTo`, the first-party AI SDK (`laravel/ai`) as the
  build-vs-buy baseline, `php artisan reload`, `schedule:interrupt`, `queue:pause`,
  Precognition for live form validation, Sanctum expiration checks, and `APP_PREVIOUS_KEYS`
  key rotation.

- **Field-expertise sweep — every agent leveled up to its craft's current canon.** Eight
  parallel researchers audited all 17 agent bodies against the authoritative sources of each
  role's *field* (verified current as of 2026) and ~90 accepted, cited practices landed:
  - **Builders:** money as integer minor units / `brick/money`, backed-enum state, retry with
    exponential backoff + jitter, circuit breakers, guard-clause style (backend); composite
    index column order, covering/partial/invisible indexes, HypoPG, `lock_timeout`,
    gh-ost/pt-osc escalation, isolation-level defaults, PgBouncer caveats (database);
    spatie/laravel-package-tools, Workbench, `roave/backward-compatibility-check`, runtime
    deprecations, SECURITY.md (package).
  - **Reviewers:** Google's code-review canon — "better, not perfect" bar, one-business-day
    SLA, stacked-PR splits, Praise findings, conventions → Pest arch tests, debt registry,
    vertical slicing with INVEST/SPIDR (tech-lead); OWASP Top 10:2025 + CWE tagging,
    KEV → EPSS → CVSS triage, ASVS 5.0 depth levels, four-question threat framing + abuse
    cases, fail-closed checks, security-headers baseline, Composer supply-chain hardening,
    OIDC in CI (security); static-analysis layer zero, RCRCRC, contract + mutation testing,
    flaky-test quarantine, SBTM charters, named go/no-go gates (qa).
  - **Perf/infra:** open-vs-closed load models (coordinated omission), percentile arithmetic,
    USE/RED, Little's Law, CWV field-vs-lab discipline, PHP 8.4 JIT default change, OPcache
    verification (performance); DORA five, deploy≠release, OIDC federation, SLSA attestation,
    burn-rate alerting, SEV ladder + blameless postmortems, production OTel for PHP, FPM
    container standards, policy-as-code (devops).
  - **Frontend/UX/mobile:** CWV budgets + Baseline gating + view transitions, DTCG token
    layering, form-UX canon (frontend); EU Accessibility Act enforcement, WCAG 3.0 status pin,
    Nielsen's 10 as named instrument, design-system governance + component API contracts
    (ui-ux); Material 3 Expressive, Liquid Glass/iOS 26, Swift 6 + `@Observable`, Compose
    stability, store release trains, Play API-36 floor, named offline conflict strategies,
    Accessibility Nutrition Labels (mobile).
  - **Delivery:** EARS + Example Mapping + Specification by Example + event storming + impact
    mapping (analyst); Opportunity Solution Trees, product-vs-business outcomes, North Star
    laddering, RICE confidence tiers, Now/Next/Later roadmaps, EBM lenses, OKR discipline,
    Shape Up awareness (product); four flow metrics with work-item aging, SLEs, Monte Carlo
    forecasting, forecast-not-commitment wording, Corry retro anti-patterns, team-scoped
    health checks, DORA signals (scrum); handoff-loss economics, 2–3 lane WIP cap,
    critical-chain checkpoint batching, lane aging (coordinator).
  - **Architecture/docs:** fitness functions, MADR 4.0 (decision drivers + confirmation), C4
    levels 1–2 discipline, quality-attribute scenarios, transactional outbox + saga shapes,
    PACELC, build-vs-buy scoring (architect); Diátaxis, Google style fallback, Vale + link
    checking, OpenAPI 3.2, Keep a Changelog 2.0.0, freshness stamps, standard-readme (writer).

### Fixed

- **Field-canon contradictions caught by the expertise sweep.** devops recommended mutable
  `@v2` action tags while its own anti-pattern list demanded SHA pinning (both files now
  SHA-pin); backend's pre-merge checklist listed bare host commands its own Sail guard hook
  blocks; React Native's Legacy Architecture described as "non-default" when it is removed
  (RN 0.82+/Expo SDK 55); date-based quarterly roadmap as PO default (now Now/Next/Later);
  "sprint commitments" wording (Scrum 2020: forecast); CVSS 3.1 → 4.0; PSR-12 → PER-CS;
  fixed-interval HTTP retry → backoff + jitter; delivery-log path mismatch between the
  coordinator and the delivery-templates skill.
- **Doc-verification drift (Laravel 13 sweep).** `$this->authorize()` recommended on
  controllers without the trait → `Gate::authorize()`/`#[Authorize]`; `validateCsrfTokens`
  → renamed `preventRequestForgery` (middleware `VerifyCsrfToken` → `PreventRequestForgery`,
  now origin-aware via `Sec-Fetch-Site`); "APP_KEY rotation requires re-encrypting" →
  `APP_PREVIOUS_KEYS` graceful fallback; hand-rolled `CREATE INDEX CONCURRENTLY` advice →
  L13 `->online()` modifier; ship-checklist's chained `config:cache route:cache view:cache
  event:cache` line (errors out — artisan takes one command) → `php artisan optimize`;
  schedule location corrected to `routes/console.php`; Envoy/Envoyer platform detection
  unconflated; undocumented APIs (`shouldBeStrict`, `LazilyRefreshDatabase`,
  `DatabaseTransactions`, `factory()->raw()`, per-second limiters, Octane
  `OperationTerminated` listeners) replaced with their doc-backed equivalents — noted as
  undocumented rather than falsely called nonexistent where they still exist.
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
