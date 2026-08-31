# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

`--adaptive` persists `stages/peer-router.md` after the router returns and
prints `handoff: <from> → <to>`. Spawn `peer-router` when a packet exists
(writer or coordinator fallback), not only when a writer has named one.
Default `/make-feature` stays Supervisor.

### Changed

- **Adaptive hop persist.** After `peer-router` returns, the coordinator
  Writes `docs/delivery/<name>/stages/peer-router.md`, then prints
  `handoff:`. On `valid`, Agent the `TO:`.
- **`peer-router` FLAG.** Spawn when `--adaptive` is on and a packet
  exists (writer or fallback). Still read-only. Never Agent a peer.

## [2.2.0] - 2026-08-27

Every delivery Writes `graph.md` after the plan, before the first
Agent. Coordinator must not spawn a type that is not a `NODES:`
entry. An `--adaptive` hop `TO:` must be a node. Default
`/make-feature` stays Supervisor. The billed `feature` run (run 21)
timed out at 1203s; graph labels, registered nodes, and close PASS
(13/13).

### Added

- **Default `graph.md`** at `docs/delivery/<name>/graph.md`. After
  the plan, before the first Agent, the first Write is a byte copy
  of `skills/delivery-templates/graph.md`, then Edit only after the
  colons (`NODES:` / `EDGES:` / `PARALLEL:` / `ON-FAIL:`). Nodes are
  registered agent types.

### Changed

- **Coordinator must not spawn off-graph.** A type that is not a
  `NODES:` entry is not Agent-spawned. An `--adaptive` hop `TO:`
  must be a node; fallback `TO:` is the next queued node. Default
  `/make-feature` stays Supervisor (2.0 Interface).

## [2.1.1] - 2026-08-26

`--adaptive` hops at least once. If writers do not file a packet, the
coordinator Writes one fallback. Default `/make-feature` stays
Supervisor. The billed `feature-adaptive` run (run 19) timed out at
1203s; Adaptive packet, `peer-router.md`, handoff, and close PASS.

### Changed

- **`--adaptive` hops at least once.** A writer may still Write a
  no-re-ask packet. If writers do not, the coordinator Writes one
  fallback packet (`FROM:` that writer, `TO:` the next queued
  specialist who has not returned, else `tech-lead`) — one fallback
  per run. `peer-router` validates; the coordinator Agent-spawns that
  peer, prints a handoff line, and counts the hop against the spawn
  cap. Specialists never Agent a peer. Default `/make-feature` stays
  Supervisor (2.0 Interface).

## [2.1.0] - 2026-08-24

Opt-in `--adaptive` on the nine pipeline commands. Default
`/make-feature` stays Supervisor (2.0 Interface). Adopters who never
pass the flag see 2.0. A writer may Write a no-re-ask packet; the
coordinator may hand that packet to a named peer. The billed
`feature-adaptive` run (run 18) timed out without a packet or
peer-router; the flag and agent still ship.

### Added

- **Opt-in `--adaptive`** on all nine pipeline commands. Default
  `/make-feature` stays Supervisor (2.0 Interface). Adopters who never
  pass the flag see 2.0.
- **No-re-ask packet** at
  `docs/delivery/<name>/packets/<from>-to-<peer>.md`. A writer may Write
  it from `skills/delivery-templates/packet.md`.
- **`peer-router`** — 18th agent, read-only. Validates the packet;
  spawned only with `--adaptive`. The coordinator then Agent-spawns the
  named peer with the packet as the brief, prints a handoff line, and
  counts hops against the spawn cap. Specialists never Agent a peer.

### Changed

- **Eighteen agents** (was 17). Read-only agents are four (was 3). Close
  file, harvest, and spawn cap are unchanged.

## [2.0.0] - 2026-08-21

The coordinator overwrites `close.md` after the plan and after every
stage. A killed run is scored from that file, not mid-board `$LOG` prose.
Dependents wait for their join; the board header states the spawn cap.
Humans still read the progress board — not the close file.

### Added

- **Close file on disk** at `docs/delivery/<name>/close.md`. The
  coordinator overwrites this file after the plan and after every stage
  (pass, fail, or checkpoint). Latest write wins; history stays in
  `log.md`. The opt-in `feature` eval reads `close.md` when the process
  is killed at timeout. Humans still see the progress board; this is not
  a `/console` feature.
- **Join-before-dependent** — a stage that depends on others does not
  `✔` until upstream stage files exist and verify. The coordinator must
  Read those files before starting the dependent stage.
- **Need-to-know briefs** — each specialist gets only goal, owned paths,
  success criteria, the exact stage path, and named stack facts. No paste
  of other specialists' diffs.
- **Spawn cap in the board header** — the progress board states
  `N stages · cap: M spawns · done when:` before any agent spends
  tokens. `M` defaults to stage count + 2. Hitting the cap without
  `done when:` → write `close.md` with `STATUS: stopped` and stop.

### Changed

- **The close file is a four-line labeled skeleton.** Writes start
  `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:` — do not rename
  those labels. `STATUS` is `running`, `done`, or `stopped`. A re-brief
  names the exact path `docs/delivery/<name>/stages/<agent>.md`.
- **After every specialist returns, the coordinator's next Write is
  `close.md`.** Labels start the line (`VERIFIED (` is a contract
  break).
- **First Write of `close.md` copies
  `skills/delivery-templates/close.md`.** Read-only persist copies
  `stage-return.md`; fill after the colons.
- **PreToolUse hook bounces `close.md` Writes that are not helper
  shape.** `enforce-close-file.sh` on the existing `Write|Edit` matcher
  denies journal payloads; helper labels still write.
- **Bash must not write `close.md`.** Use Write so the shape hook
  can see the payload.

### Breaking

- **This pack ships as 2.0.0.** Re-install from the new release; do not
  assume in-place upgrade from 1.x.
- **The Interface contract changed.** Close file, join checks,
  need-to-know briefs, and spawn cap are new Interface requirements.
  Re-read the shared Interface block after upgrade.

## [1.45.0] - 2026-08-20

Specialists persist six-field stage returns on disk. The coordinator
Reads that file before `✔`. Nested chat is no longer the measurement.

### Added

- **Six-field stage returns land on disk** at
  `docs/delivery/<name>/stages/`. Specialists persist `STATUS` / `DID` /
  `VERIFIED` / `NOT-CHECKED` / `FLAGS` / `NEXT`. The coordinator Reads
  that file before `✔`. The opt-in `feature` eval asserts the files.
  `$SUBAGENT_LOG` is still not an answer-key surface.

## [1.44.0] - 2026-08-19

`/console` is a two-act company floor. The call sheet starts a production;
the house fills with stations; a parked Bash prompt takes the stage. Same
Python server, same events.

### Added

- **A two-act company floor for `/console`** — call sheet, theater, and
  spotlight. Same Python server, same events. Act I is the start screen;
  a live run fills the house; a parked Bash prompt takes the stage.

### Changed

- **The approval bar is gone.** Decisions live in Spotlight on the main
  canvas; dismiss keeps a parked card so you can reopen. **Needs you** in
  the show header is the fallback when no station is marked.
- **Geist is out.** Display is Syne, body is Source Sans 3, mono is IBM
  Plex Mono.
- **The console board screenshot was recaptured** as the company floor
  (still fixture-driven, not a billed live `/console` run).

## [1.43.0] - 2026-08-19

Prove-it **Adoption**. The README leads with a five-minute path, the docs
corpus has an index, and `/console` has a real board screenshot plus the
held hover and CAN-RIDE console work.

### Added

- **A five-minute quickstart at the top of the README** — install, first
  command (`/make-feature` or `/console`), and what the progress board
  looks like. The rest of the README still explains the design; the new
  top shows the product.
- **A fixture-driven PNG of the Guild console pipeline board** — Adam +
  Dina, parked on a Bash approval. Caption says it is not a billed live
  `/console` run. Recapture harness lives under `console-ui/src/dev/` and
  is not the production Vite entry.
- **`docs/README.md`** — one-page map of the corpus: spec vs plan vs eval
  record, what is closed vs still open. The next project-state review
  should start there.
- **`docs/onboarding.md`** — adopting-team path: first delivery, teaching
  the first rule via `/teach`, reading an eval scorecard. The five-minute
  path is a link to the README; this page adds specialist order, harvest
  history, `/teach`, and how to read a scorecard.
- **Card-sprite hover** — elapsed time and the current tool (or
  `starting…`) on `sm` actors only. Nested tooltip trigger is a `span` so
  the card stays one button. Lane-panel `lg` sprites do not hover.
- **Eval `$SUBAGENT_LOG` / `--subagent-text`** — a dedicated extract of
  nested-agent text, exclusive of the main-thread `--text-only` /
  `--full-text` paths. A billed run 10 transcript was inspected: nested
  turns were `tool_use` only, so `check_subagent_log` stays commented.

### Changed

- **The README now leads with the product, then the design.** Install
  flavours, inventory counts, and the eval history are unchanged and
  still below the quickstart.
- **Console CAN-RIDE riders** — last selected lane stays mounted so the
  sheet can exit; `splitJsonKey` consumes escaped quotes; decision label
  is `{n} remaining` (hidden at 1); Target visible name matches
  `aria-label`; kind and mode are separate captions; dismiss restores
  focus to `#guild-launcher`; `ago()` clamps future timestamps; every
  `wfile` write uses `write_or_drop` so a dead SSE client does not
  traceback-and-die.

## [1.42.0] - 2026-08-18

### Added

- **`/audit-agents`** — a free, repeatable static check of the pack's own
  orchestration contract (Interface placement, tool-grant coverage,
  stage-return consistency, artifact routing, read-only enforcement).
  Diff-scoped against a base branch, or a full scan. Verdict is CLEAN or
  DRIFT-FOUND. Report-only; it never edits files.

### Fixed

- **Command-driven runs now refuse to build or patch, and they verify
  before marking a stage done.** The 2026-08-12 orchestration audit found
  three rules that bound only `delivery-coordinator.md` — a file
  `/make-feature` and its 8 siblings never load. Same shape as the harvest
  miss in v1.41.0. The shared Interface block now says: Write/Edit only
  under `docs/**`; never edit a specialist's files to "just fix it";
  re-run the brief's success criteria yourself — a specialist's
  `STATUS: done` is a claim, not a `✔`. A billed `feature` run
  (2026-08-18, $9.00, 1203s, timed out at EVAL_TIMEOUT) scored 10/10
  including harvest on disk. The run hit the timeout before a coordinator
  closing answer; cost and tokens exceeded the 2026-08-04 ceilings
  ($8.50 / 14.5M). Those ceilings were not raised in this release.

- **Coordinator routing table names the four specialist docs/ paths it
  was missing** (`docs/tech-debt.md`, `docs/db/<migration>.md`,
  `docs/design/system.md`, `docs/backlog/backlog.md`), and Working
  interface now states it is a deliberate superset of the shared
  Interface contract.

### Changed

- **The milestone's originally-planned Adoption release is renumbered
  v1.43.0.** v1.41.0 took the first slide (harvest); this release takes
  the second (audit contract repair). Adoption's content (README
  quickstart, docs index, onboarding guide) is unchanged.

## [1.41.0] - 2026-08-07

### Added

- **Harvest moves into the shared Interface block, and now genuinely
  fires.** v1.40.0's eval run 7 found that `/make-feature` and its 8
  sibling commands never load `agents/delivery-coordinator.md`, so the
  harvest steps promised there — persisting `docs/team/stack.md` and
  `docs/delivery/<name>/log.md` — never fired for any command-driven
  delivery. Same fix shape as v1.24.0 (`NOT-CHECKED`) and v1.36.0 (the
  stage-budget header): the requirement now lives in the shared,
  byte-identical Interface block all 9 commands carry, firing once a
  delivery has delegated to ≥2 specialists. A billed re-run confirmed it:
  `teach-delivery` scored 8/8, and `docs/team/stack.md` +
  `docs/delivery/donation/log.md` both exist with real, run-specific
  content, verified directly against the filesystem. Record:
  `docs/evals/2026-08-06-run-7.md`'s second addendum.
- **A guardrail ratchet, mutation-tested against the exact regression it
  guards.** All 9 commands' `allowed-tools` now grant `Write`/`Edit` —
  the harvest clause requires the command's own main thread to write two
  files, and the billed re-run that validated it ran under
  `--dangerously-skip-permissions`, which bypasses tool permission checks
  entirely. It proved the model complies; it could not prove harvest is
  reachable under a real user's default permissions. Caught by this
  release's own final whole-branch review before merge.

### Changed

- **The milestone's originally-planned Adoption release is renumbered
  v1.42.0.** This release took the v1.41.0 slot instead, since it fixes a
  real gap the milestone's own verification run exposed. Adoption's
  content (README quickstart, docs index, onboarding guide) is unchanged.

## [1.40.0] - 2026-08-06

### Added

- **Eval run 7 — the teach delivery.** Tested the pack's "team memory" claim
  (taught rules land in a ledger, a later delivery obeys them, the
  coordinator harvests without being asked) end to end for the first time.
  Two of three hold: `/teach` writes the ledger correctly, and a delivery
  visibly obeys taught rules where Laravel's own defaults point the other
  way (integer-cents money, ULID keys — confirmed by reading the produced
  migration, not the transcript's claim about it). Harvest does not: a
  billed re-run and a whole-branch review together traced this to
  `/make-feature` never loading `agents/delivery-coordinator.md`, the only
  file that promises harvest — the same command/agent-body scoping gap
  [run 6](docs/evals/2026-08-04-run-6.md) diagnosed for the stage-budget
  rule, recurring unrecognized. Total spend: $20.31 of the milestone's $30
  ceiling. Record: `docs/evals/2026-08-06-run-7.md`.
- **Two opt-in eval cases split the team-memory hypothesis** at the harness's
  one-prompt-per-case seam: `teach` (six artifact checks on the ledger
  contract `/teach` writes) and `teach-delivery` (a seeded two-rule ledger
  the delivery must obey where Laravel's defaults differ, plus the
  unprompted harvest: stack snapshot and delivery log). The audit tally
  moves 25 → 39, and is now a CLAIMS row counted from `run-evals.sh` rather
  than a hand-maintained number.
- **`docs/examples/team-memory/`** — the example instance the README claimed
  without evidence (2026-08-05 review, gap 4): the seeded ledger and the
  code that obeyed it, captured verbatim from run 7's workdir. Labeled
  honestly as partial — harvest isn't there, and the page says so.
- **`check_log_anywhere`**, a harness fix: a check asserting on the
  progress board's stage-budget header (printed early, before any agent
  spends tokens) was reading `$LOG`, which the harness rebuilds from only
  the closing turn — structurally unable to see an earlier one. Two cases
  scored false negatives on a header they had, in fact, printed correctly.
  Fixed by persisting every main-thread turn to a new `$FULL_LOG` artifact.

### Changed

- **Waivers on the coordinator-hash gate must carry a date and a reason** —
  the error message always promised both; now a bare-sha waiver doesn't
  count, and one consisting only of whitespace doesn't either.
- **`agents/delivery-coordinator.md`** now requires parallel lanes to be
  awaited together, never narrated as backgrounded for a later turn — good
  guidance for interactive `claude --agent delivery-coordinator` sessions.
  Note precisely what this is: it shipped from a mis-diagnosis of run 7's
  harvest failure (caught and corrected by this release's own final
  review) and is unvalidated by anything in the current eval suite, since
  none of the commands that exercise it actually load this file. The real
  fix — moving the harvest requirement where the commands can see it,
  matching the precedent this same file's stage-budget rule set in
  v1.24.0/v1.36.0 — is scoped for 1.41.

## [1.39.0] - 2026-08-06

### Added

- **A deterministic trigger for the opt-in `feature` eval case.** "Run it when
  coordinator behaviour changes" had no named judge and would silently never
  fire. A sha256 over the delegation-steering surfaces — the coordinator body
  plus the nine commands' shared Interface line — is now pinned in
  `tests/eval/baseline.json`; `check_inventory_sync` fails CI on drift until a
  human records a re-run or a dated waiver. Seeded honestly: the pin notes that
  no billed run has measured exactly the current content, and the next billed
  run retires the note.
- **`docs/evals/2026-08-06-check-audit.md`** — all 25 answer-key checks
  classified by evidence source (16 artifact, 5 fixture-noun, 2
  format-contract, and 2 formerly free-prose — now **hardened-prose**:
  synonym-widened and ratchet-pinned, the class reserved for report-only
  cases with no artifact to inspect). The sound greps are documented as sound
  so nobody "fixes" them; the classification rules bind future checks.
- **`docs/evals/2026-08-06-run-7-scope.md`** — run 7 named a question before
  being run: does teach → override → harvest work end to end on the fixture
  app? Scope, composition, spend, and what is deliberately not re-tested.

### Fixed

- **The answer key's last two free-prose greps.** `hygiene`'s
  `check_log 'duplicate'` and `check_log 'conflict'` failed runs that
  classified the planted items correctly in different words ("identical",
  "contradicts") — the same disease `check_update_guarded` fixed in v1.37.0.
  Both now accept the model's synonyms; the vocabularies are additive-only and
  ratchet-pinned.

### Changed

- **`max_usd` is the cost metric of record.** When the three ceilings disagree,
  dollars win: token totals are >99% cache reads and wall clock measures the
  experience, not the bill. Documented in `baseline.json`'s `_metrics` and the
  README's eval section; the bimodal `policy`/`action` exception is unchanged.

## [1.38.1] - 2026-08-06

### Fixed

- **The approval bar's Review button is reachable while a transcript panel is
  open.** The bar is sticky at `z-30` with Review right-aligned; the lane panel is
  pinned right at 28rem, full height, `z-50` — so an open panel covered exactly
  that button, in this order only: park a decision, dismiss the sheet, open a card,
  reach for Review. Escape always recovered it, and the bar's text stayed visible
  throughout, so a run never looked silent — but the button was unreachable by
  mouse. Known and held since 2026-08-04 because every candidate fix was a layout
  judgment; the bar now reserves the panel's width on its own trailing edge, which
  leaves the panel's proportions and the board's clickability behind it alone. It
  is `sm`-only, because below that the panel is full-width and nothing can be kept
  clear. Verified in a browser against the built bundle by driving the exact repro:
  `elementFromPoint` at Review's centre returns Review, and a real pointer click —
  the one that used to time out on the panel intercepting it — opens the decision
  sheet.

### Changed

- `docs/evals/2026-08-04-run-6.md` corrects a stale line that called the opt-in
  `feature` case's ceilings null. They were seeded the same day (1900s / $8.50 /
  14.5M from 1456s, $6.55, 11.2M measured). The correction is marked rather than
  edited away, because the line read as a to-do and nearly bought a $6.55
  re-measurement of behaviour that had not changed — `git log v1.36.0..HEAD --
  agents/ commands/ skills/` is empty.

## [1.38.0] - 2026-08-05

### Added

- **Every specialist in the console is now an animated actor.** The agent card's
  24px avatar was two letters and a spinner: it told you which agent and that it
  was busy, never what it was doing. It now holds a sprite posed from the events
  the console already emits — reasoning bobs with its head tilted, a tool call
  leans in and works, assistant text nods and reports, a failed tool result
  flinches and slumps, a parked lane raises a hand, a finished one closes its
  eyes. One rig serves all seventeen agents and colour is the only per-agent art,
  so **no animation runtime ships for it**: every pose is CSS keyed off
  `data-pose`, at a cost of +1.5 KB of JS and +3.4 KB of CSS. The Lottie question
  that prompted this stays deliberately unopened, because at this fidelity CSS
  answers it.
- **A specialist's instrument, where there is room for it.** Optional per-agent
  props — a padlock for the security engineer, a clipboard for QA, a stopwatch for
  performance — drawn **only in the lane panel at 2×**. At card size they do not
  read: a browser check against the built bundle found the author unable to tell
  his own three drawings apart at nine pixels, with the propless cards beside them
  looking cleaner. So the board stays dense and looking closer is what earns the
  detail. A craft with no unmistakable silhouette gets no prop rather than a vague
  one, which is what keeps a newly added agent from looking unfinished.
- `docs/design/2026-08-05-actor-study.html` — the live study the design was chosen
  from: three treatments (bespoke instruments, the character rig, a pulsing ring
  around the existing chip) running the same event stream on the same clock, with
  each one's cost and risk stated. Kept so the reasoning does not have to be
  re-derived, and updated to record what actually shipped.

### Changed

- **A running lane no longer carries a spinner.** The actor is the running
  indicator; two moving glyphs in one row both said "busy" while neither said
  what. `Check`, `AlertTriangle` and `Pause` return for done, error and parked —
  the states where the answer is settled.
- **The board's parked-lane rule moved to `lib/parkedLanes.ts`** and gained its
  first tests. It was written inside `Board`, and the lane panel needed the same
  answer to pose its actor; a second copy of "a guessed attribution marks nothing"
  is how the two surfaces would have drifted apart.

### Fixed

- `api_retry` deliberately gets no pose. The engine reports it on the run, not a
  lane, so posing every lane as retrying would have claimed something false about
  agents that were working fine.

## [1.37.0] - 2026-08-05

### Fixed

- **The `policy` case no longer scores a correct run as a failure.** Its
  authorization assertion was `check_log 'update'` — a grep for one word in the
  final answer. A targeted delegating run closed the hole properly (`PostPolicy`
  ownership check, the update path guarded by `UpdatePostRequest::authorize()`
  calling `can('update', …)`, and a feature test asserting a non-owner PUT gets
  403) and simply never used the word "update" in its closing prose. The rubric
  judge scored that run 5/5 and **disagreed with the key** — correctly. This is
  the exact antipattern the 2026-07-29 literature audit named, citing this exact
  check. Replaced with `check_update_guarded`, which inspects the code and accepts
  either idiomatic placement: inline in the controller's `update()`, or in the
  `authorize()` of the Form Request that `update()` type-hints. It also rejects a
  Form Request whose `authorize()` just `return true`, because a guard that
  authorizes everything is not a guard.
- **`claude-opus-4-8[1m]` is now priced explicitly.** The bracketed 1M-context
  variant appears only in the result line's `modelUsage` ledger, missed the rate
  table, and defaulted to Opus 5's rate — correct purely because both are $5/$25,
  so a real long-context premium would have been absorbed in silence. An
  unpriceable model in the ledger now also blocks a clean `agrees`, so the
  reconciliation can no longer pass on a defaulted guess.

### Changed

- **`policy`'s security-engineer stage is intended cost, not a lever** — the last
  question open since run 5, now answered. A targeted run caught the case
  delegating (1560s, $7.18, 4 agents) and priced the stage: `security-engineer` is
  1,330,714 tokens across 25 tool calls, the **smallest lane by tokens** and ~17%
  of attributed spend, against `main`'s 55%. Run 5 read its 526s of 994s as the
  driver; it is 53% of the wall clock and a sixth of the bill, because it runs Opus
  5 where the builders run Sonnet. Time and money point at different lanes.
- **Both bimodal cases now cover their delegating mode.** `policy` runs 3.3× more
  expensive delegating ($7.18) than fast-pathed ($2.19) on an identical prompt, so
  `policy` is reseeded to 1900s / $9.00 / 14.5M and `feature` seeded to
  1900s / $8.50 / 14.5M. The agent list in `<case>.cost.json` — not the ceiling —
  is what tells you which mode ran.
- **Sonnet 5's 2026-08-31 introductory-rate expiry is retired as a risk.** Solving
  the CLI's own per-model `costUSD` for the implied input rate lands on exactly
  $3.00/MTok at the 5m cache tier in three independent cases, and the $2/$10 intro
  rate would require a cache-write multiplier of 3.8–4.1 when only 1.25 and 2.0
  exist. Billing is at list price, so the expiry moves nothing here.

## [1.36.0] - 2026-08-04

### Fixed

- **The stage budget now actually binds — it never fired before.** v1.31.0 added
  the tranche's stage-budget rule to `agents/delivery-coordinator.md`, and the
  opt-in `feature` case's first billed run proved that put it somewhere it could
  never take effect: `/make-feature` is driven by the main thread, so
  `delivery-coordinator` is **never spawned** (the run's board feed names
  database-developer, backend-developer, qa-engineer and tech-lead, and no
  coordinator). A rule written into an agent body cannot govern work the main
  thread does inline through a command.

  The run scored 5/6, and the single miss was the stage-budget assertion — with
  the rubric judge reaching the same conclusion independently while *disagreeing
  with the regex verdict*: *"the stage table appears only as a closing summary —
  evidence shows 6 owned stages but no up-front stage count or stated observable
  end condition before the agents spent tokens."*

  This is the v1.24.0 finding recurring, and it gets the v1.24.0 fix: the shared
  `Interface` block — byte-identical across all 9 pipeline commands — now requires
  the board's header to state the stage count and the observable completion
  condition **before** any agent spends tokens, and to reprint it when the budget
  grows. Ratcheted at 9.

### Changed

- **Run 6's finding 6 corrected.** "No case exceeded its stage budget" was true
  only because no case was ever bound by one. The claim was vacuous, and is now
  labelled as such.
- **The opt-in `feature` case has ceilings**, seeded from its first accepted run:
  1456s across four specialists, $6.55, 11.2M tokens — the most expensive case in
  the suite, which is why it stays opt-in.

## [1.35.0] - 2026-08-04

### Fixed

- **`qa-engineer` no longer contradicts itself on unauthorized endpoints.** Its
  authorization rule prescribed marking the secure-outcome assertion `->todo()`,
  while its own anti-patterns section three paragraphs later demanded that same
  test "asserts the secure outcome **and fails loudly**". A `->todo()` does not
  fail loudly, so the body asked for two incompatible things — and
  [run 6](docs/evals/2026-08-04-run-6.md)'s rubric judge caught the consequence:
  *"the IDOR is documented rather than demonstrated, and CI stays green with the
  flaw live."*

### Changed

- **The run/don't-run choice on a known-vulnerable endpoint is now explicit, and
  must be stated.** v1.24.0's actual point is kept — assert the *secure* outcome,
  never pin the hole as expected behaviour — but the marking is no longer a
  default. Leave the test **failing** when the flaw is in-scope work and CI should
  block on it; mark it incomplete when the flaw is pre-existing and out of scope,
  because a red pipeline you did not cause blocks everyone else too. Either way,
  FLAGS must name the endpoint, say the vulnerability is live, and say the suite
  will not catch it. "Loudly" is now defined as *the human hears it* — which a
  marked test plus a FLAGS entry satisfies, and a marked test alone does not.

## [1.34.0] - 2026-08-04

### Added

- **An opt-in `feature` eval case — the only one that must delegate.** Nothing in
  the suite proved delegation happened, and that made the coordinator's own rules
  unmeasurable: `policy` and `action` each ran *both* ways across runs 5 and 6 —
  one across four specialists, the other alone on the main thread via the fast
  path — and the answer key could not tell the difference either time.
  `/make-feature Tag --api` is parallel by construction, so it always delegates.
  Run it by name: `./tests/eval/run-evals.sh feature`.
- **A `check_delegated` assertion**, which reads the board feed and requires ≥2
  distinct agents. It is negative-controlled: a stub that scaffolds a *correct*
  Tag feature entirely inline passes five of six checks and fails exactly that
  one, so the check can distinguish the thing it claims to measure.

### Changed

- **The new case stays out of the default sweep, deliberately.** `action` — the
  closest comparable shape — billed $5.16 of run 6's $12.50, so adding a second
  case that size would raise the standing cost of every sweep by roughly half for
  a signal that only changes when coordinator behaviour changes. Keeping
  `ALL_CASES` at five also keeps the public scorecard's denominator, and runs 1–6,
  comparable with what follows. `--list` shows it under an opt-in heading so it is
  discoverable rather than hidden.
- The unseeded-ceiling ratchet now applies to the default sweep only — an opt-in
  case is legitimately unseeded until its first accepted run, and seeding it from
  a guess is what `baseline.json`'s own policy forbids. Rubric coverage, by
  contrast, was widened to include opt-in cases: excluded from the sweep is not
  excluded from needing a rubric.

## [1.33.0] - 2026-08-04

### Added

- **`KEEP_TRANSCRIPT=1` preserves an eval case's raw transcript.** Off by default
  (megabytes per case), but `<case>.cost.json` counts tool calls by *name* only,
  and [run 6](docs/evals/2026-08-04-run-6.md) could not explain why `n-plus-one`
  spent **25 Bash calls** on a read-only audit without seeing the commands
  themselves. Counting what an agent did turns out not to be enough to explain
  why it cost what it cost.

### Fixed

- **The eval evidence artifact no longer hides newly created files.** `git diff`
  omits untracked files, so `<case>.diff.patch` — the artifact the rubric judge is
  handed as evidence — contained no trace of a file the run had just created. On
  `action`, whose entire job is *creating* an Action class, the judge could confirm
  the class existed but never see a line of its body, and marked behaviour
  preservation unevidenced for exactly that reason. `run_case` now records
  intent-to-add before diffing, after the checks and after `status.txt`, so no
  verdict changes and `status.txt` still reports new files as `??` rather than `A`.

### Changed

- **Run 6's findings corrected on one point.** An earlier draft blamed
  `checks_action` for the untracked-file blindness. That was wrong: the checks read
  the filesystem directly (`find`, `grep`, and `git status --porcelain`, which does
  list untracked files) and were never blind to a new file. The blindness was in
  the diff artifact alone. The `n-plus-one` finding is likewise corrected —
  per-agent `effort` cannot be its lever, because that case delegates nothing, so
  no subagent frontmatter applies to it.

## [1.32.0] - 2026-08-04

### Added

- **`baseline.json` ratchets dollars as well as tokens and seconds.** Three
  ceilings, because each catches a regression the others miss: a sonnet → opus
  re-tier keeps token counts flat and triples the bill, while dollars drift with
  published prices and tokens do not. [Eval run 6](docs/evals/2026-08-04-run-6.md)
  made the case concrete — token totals came in at **>99% cache-read tokens** in
  all five cases, and cache reads bill at a tenth of input, so a token-only
  ceiling measures context volume far more than spend.
- **All three ceilings are now seeded** for all five cases, from run 6 — the first
  run in the project's history with a cost figure attached ($12.50 across five
  cases). `max_tokens` had shipped `null` by design because every earlier figure
  was contaminated; run 6 is the clean measurement it was waiting for.

### Fixed

- **Dated model ids are priced at their alias rate.** Transcripts report
  `claude-haiku-4-5-20251001` where the rate table and agent frontmatter use
  `claude-haiku-4-5`. The dated id missed the table, fell through to the default
  Opus rate, and priced `scrum-master` five times too high. The rate-table
  reconciliation caught it rather than reporting a wrong number quietly — the
  implied cache-write multiplier came out at 0.99, below the cheapest real tier.
  A test now asserts every model any agent pins is priceable, so a future re-tier
  fails a test instead of silently billing at the default rate.
- **No more phantom `unknown-agent` lane.** Any `task_started` line carrying a
  `tool_use_id` was treated as an agent launch with a fallback name, so three run-6
  cases that spawned no subagent at all still reported an `unknown-agent` — which
  the harness then announced as "launched but unmeasured (async?)", inventing a
  lane in the one report meant to be authoritative about lanes. A `task_started`
  without a `subagent_type` is not an agent launch and is skipped.

### Changed

- **Eval run 6 reported: 5/5 cases, 19/19 checks, and 5/5 judged PASS** — the
  first run with `EVAL_JUDGE=1` exercised against real output. It answers the
  question run 5 left open: `qa-engineer` is the largest lane because of
  **tool-call volume** — 73 calls in the `action` case, more than the other three
  agents combined, and it costs less per token than `tech-lead` (Opus 4.8) which
  used a fifth of the tokens for nearly the same dollars. The judge also found a
  real hole the regex answer key cannot see: `checks_action` greps `git diff`, and
  `git diff` does not show untracked files, so a case whose job is creating a new
  Action class never verifies that file's contents. Full findings, including the
  `n-plus-one` 3.1× latency creep and a run-7 checklist, are in
  [docs/evals/2026-08-04-run-6.md](docs/evals/2026-08-04-run-6.md).

## [1.31.1] - 2026-08-04

### Fixed

- **A transcript line that is valid JSON but not an object no longer costs the
  run its cost data.** A bare `42`, `null`, `"text"`, or `[]` reached
  `obj.get(...)` and raised, so one such line lost the whole summary. It is now
  treated as a parse error like any other unusable line. The 1.31.0 tests
  covered *invalid* JSON but never *valid non-object* JSON, which is how this
  shipped.
- **An async subagent no longer vanishes from the cost summary.** A
  background-launched subagent is named by a `task_started` line but contributes
  no turns to the transcript, and it was being omitted entirely — so a run where
  `policy` went fully async (runs 3 and 5 both did) reported as though the main
  thread had done all the work, which is the exact invisibility this instrument
  exists to end. Every launched agent now appears with its measured turn count,
  and the ones with no measured turns are named outright in both the summary
  (`launched_without_measured_turns`) and the harness's per-case output.

## [1.31.0] - 2026-08-04

### Added

- **The eval harness can price a run.** It measured correctness and latency and
  never cost, and the one cost signal it did emit carried no input/output split —
  which matters because output costs five times input on every tier. Each case
  now captures its full transcript, derives a per-agent summary (input, output
  and cache tokens; tool-call counts; dollars at the model that actually billed
  each turn), and discards the raw stream. `baseline.json` gains token ceilings
  beside its duration ones, so a cost regression surfaces the way a latency one
  already did. The ceilings start unseeded on purpose: every token figure from
  runs 1–5 is contaminated by committed fixture telemetry, and eval run 6 is the
  first honest measurement. The answer key is untouched — the transcript goes to
  its own file and the human-readable log is rebuilt from its `result` field,
  which is exactly what plain `claude -p` prints, so run 6 stays comparable to
  run 5.
- **Recording the wire format first paid for itself three times.** The parser was
  written against two captured transcripts (`tests/eval/fixtures/`) rather than
  an assumed shape, which is how 1.27.0 shipped a console that emitted zero
  events with a green suite. What the recording caught: cache tokens dominate
  input (4 raw tokens against 71k cached, so pricing input+output alone
  undercounts a run ~26×); the two cache-write tiers differ and *both* occur in
  one run, because the main thread writes 1-hour entries while subagents write
  5-minute ones; and there is no `agent` field to attribute spend by — it is
  `parent_tool_use_id` resolved through a `task_started` line. The rate table is
  re-checked against the CLI's own `total_cost_usd` on every run, so a price
  change fails a test instead of silently producing a wrong number.

### Changed

- **`NOT-CHECKED` now escalates.** Escalation fired on category alone — authn,
  authz, billing, PII, money, tenant isolation — while every stage return
  carried a `NOT-CHECKED` field that nothing consumed. A stage whose
  `NOT-CHECKED` swallowed the substance of its own brief advanced exactly like a
  verified one. It is now re-briefed once, then surfaced as a checkpoint; low
  confidence is a stop trigger in its own right, scoped to the brief's own
  substance so an honest disclaimer cannot stall a lane.
- **The board declares a stage budget.** Both existing caps were local — lanes
  ≤2–3, retries ≤1 — and nothing bounded a delivery's total stages. The board
  now states the expected count and the observable condition that ends it, and
  growing past it is a re-plan the human agrees to rather than a continuation.
- **Checkpoints persist resume state.** A blocking checkpoint wrote nothing, so a
  delivery resumed the next day rebuilt its board position, open lanes, and
  pending question from a transcript the new session no longer had. It now
  flushes that state to the delivery log first.
- **Reasoning effort is now declared per agent, where the pack has an opinion.**
  Verified against the Claude Code subagent docs: `effort` is a real frontmatter
  field, it overrides the session effort level, and it is the only per-agent
  depth control — subagents inherit the session's thinking configuration and no
  per-subagent thinking setting exists. `security-engineer` and
  `solution-architect` take `xhigh` (highest failure cost); `business-analyst`
  and `product-owner` take `low` (summarising artifacts others produced). Every
  other agent leaves it absent so your own `/effort` still governs the run.
  `scrum-master` is excluded because effort is unsupported on Haiku 4.5, and
  `technical-writer` because v1.23.0 chose docs quality over cost for it
  deliberately.

## [1.30.0] - 2026-08-04

### Changed

- **The console moves like one thing now.** A single motion vocabulary
  (`console-ui/src/lib/motion.ts`) drives every transition: banners and the
  final answer fade-rise instead of teleporting, a parked lane breathes its
  agent's color (the only looping attention animation — and a static colored
  border under `prefers-reduced-motion`), and the approval-queue badge pops
  when it grows. Reduced motion is honored end to end: the CSS guard covers
  the keyframes, and `MotionConfig reducedMotion="user"` covers the
  JavaScript-driven animations the CSS guard cannot reach.
- **The launcher explains itself.** A segmented Freeform / Command /
  Specialist control with a live caption, specialists listed by name and
  role, permission modes captioned in plain words, and Cmd/Ctrl+Enter to run.
- **The transcript is a slide-over, not a footnote.** Selecting a card opens
  a non-modal right panel — the board stays clickable, so another card swaps
  the panel in place; Escape dismisses it; and a decision always wins the
  screen, whether it arrives on its own or you press Review. One known edge,
  written up in `docs/plans/2026-08-04-console-motion-followups.md`: while the
  panel is open it covers the approval bar's Review button, and Escape is what
  frees it.
- **Smaller answers to constant questions.** A header chip answers "is it
  still running?" with a ticking elapsed time; the run picker says
  `make-feature · done · 12m ago` instead of a raw run id; the decision sheet
  says "Decision 1 of 3" when a queue is waiting.

## [1.29.0] - 2026-07-31

### Added

- **A finished run can be read back from the browser.** `snapshot()` has always
  served a run's whole history from `.claude/console/runs/<id>.jsonl` — for
  precisely the runs the console process no longer owns — and nothing in the UI
  ever called it, so every completed run was on disk and unreachable. A
  "Recorded runs…" picker in the console header lists what `GET /api/runs`
  reports and replays the chosen run through **the same reducer the live stream
  uses**, so the board, transcripts, final answer and error banner all render
  identically with no second code path to keep in step. This is also what makes
  the SSE 404 after a console restart stop being a dead end.
  Read-only by construction: the picker is disabled while a run is live (two runs
  sharing one view is how the abandoned-run bug looked), and a recorded run's
  pending queue is **emptied** rather than its approval bar hidden — a `prompt`
  with no `prompt_resolved` means the process died holding that decision, so
  offering an answer that can never land would be a lie.
- **One blessed node version for the committed bundle.** `scripts/console/dist/`
  is committed and CI fails if it drifts from source, but nothing declared which
  toolchain produces it; the bundle is byte-identical on node 22 and 26.5.0
  today, which is luck rather than a guarantee. `.nvmrc` now declares it, CI's
  `setup-node` reads it via `node-version-file` instead of a hardcoded string,
  and three ratchets pin the arrangement (**107 guardrail tests**, from 104).
  22 rather than 26 because CI is the authority: a contributor on another major
  is told to switch instead of discovering a phantom `dist/` diff.
- **A contributing guide for the console.** `console-ui/` was not mentioned
  anywhere in README or CONTRIBUTING, so a contributor touching the front end had
  no documented way to rebuild the bundle CI would then fail them on. Every
  command in the new section was run as written. It also records *why* tests are
  excluded from Tailwind's scan — the kind of line that otherwise gets tidied
  away by someone who does not know it changes the shipped stylesheet.

### Changed

- The console header's controls (recorded-run picker, mid-run permission mode,
  interrupt) are one right-aligned group, which retires the conditional
  `ml-auto` that was being juggled between them.

## [1.28.0] - 2026-07-30

The console v1.27.0 shipped did not work: `events.normalize` was written against
the CLI's stream-json wire format while the Python SDK yields typed dataclasses
with no `type` field, so every message normalized to nothing and the browser
received **zero events** while 62/62 tests passed. This release is the first in
which `/console` does what 1.27.0's entry claims, and the first in which its
central promise — that a human sees every decision — is actually enforced.

### Added

- **Every Bash command now reaches the browser, including read-only ones.**
  `can_use_tool` is not the first gate: Claude Code auto-allowed read-only Bash
  before the callback ran, so `echo hello` produced `tool_use` → `tool_result`
  with zero `prompt` events and nobody was asked. No SDK option or settings key
  disables that — the SDK's own shadowing warning says to use a `PreToolUse`
  hook, and that is the only layer which sees every call. The console registers
  one in-process (`engine._make_pre_tool_use`, wrapped into a `HookMatcher` by
  `serve.py` so `engine.py` stays free of `import claude_agent_sdk`) and returns
  `permissionDecision: "ask"` for Bash, routing the call back through
  `can_use_tool` — which already emits the `prompt` event the browser answers, so
  the whole approval path is reused rather than duplicated. Verified against a
  live run, not just units.
- **"N ran unasked" on every lane and for the main thread.** A `tool_gate` event
  now accompanies every tool call recording whether the browser was asked, so a
  transcript can no longer be mistaken for an approval record. Non-Bash tools
  allowed by a settings rule still run without an ask; they are now visible
  rather than silent.
- **"Allow always" keeps meaning something for Bash.** A hook `ask` outranks
  allow rules, so the persisted `localSettings` rule would have been overridden
  on the very next call. The run remembers exact `(Bash, command)` signatures and
  the hook falls through for them — exact match, never a pattern.
- **Mid-run permission-mode switch** in the console header, which the spec
  claimed and only the API could do. Optimistic, and reverted if the API refuses.
- **Attribution confidence.** `prompt` and `prompt_resolved` carry
  `agent_confidence`; the approval bar says "Possibly Adam needs approval" for
  the newest-open-lane fallback, and the board marks **no** card, keeping its
  promise that a marked card is really the blocked one.
- **The console UI is under test at last.** 22 mount tests drive a real `<App />`
  with `fetch` and `EventSource` faked at the transport boundary, so `lib/api`,
  the reducer, the submit gate and every component stay on the real path. 84
  frontend tests (from 37), 105 console python tests (from 85).
- **Four new guardrail ratchets** (104, from 100): the `PreToolUse` gate is
  registered, Bash is still forced through the browser, the API token is compared
  in constant time, and every manifest's declared version matches `VERSION` —
  the last of which is why `.cursor-plugin/marketplace.json` can no longer sit
  ten releases behind.

### Changed

- **A `git status` now parks a run.** Forcing read-only Bash through the browser
  is the price of the promise and is deliberate; `/console`'s notes say so
  plainly. Only Bash is forced — `Read`/`Grep`/`Glob` would park a routine run
  dozens of times for no safety gain.
- Tailwind no longer scans test files. Its scanner reads raw bytes, so
  `static instances` in a fake and a comment about content being "hidden" added
  `.static` and `.hidden` to the **shipped** stylesheet.
- The console ratchets ignore comment-only lines, so the code can explain itself
  without reddening the build. A trailing comment after real code still counts:
  a security ratchet must fail closed.
- CI no longer typechecks `console-ui` twice; `npm run build` already does it.
- The spec's SSE-resume promise is corrected: resume replays from the run's
  in-memory buffer, not the jsonl. Replay from disk is `GET /api/runs/{id}`, and
  the two paths stay separate so a dead run's stream cannot loop EventSource.

### Fixed

- **The console emitted no events at all** — SDK dataclasses translated into the
  wire format `normalize` reads (`_as_dict`, dispatching on class name so
  `engine.py` needs no SDK import).
- **A 36-second startup stall** before the tokenized URL appeared:
  `HTTPServer.server_bind` calls `socket.getfqdn` purely to populate a CGI field.
- **Approvals are a queue.** The UI modelled one pending prompt while the engine
  held a dict, so with two parallel subagents one was parked forever, unnameable.
- **One click resolves one decision.** The second click of a double-click landed
  on the next prompt's "Allow once" in the same screen position — a silent
  approval of something no human read.
- **An errored run ends.** A run that died without a `result` read as live
  forever, with the Launcher disabled and no way back short of reloading.
- **A failed interrupt still ends the run** rather than wedging the console.
- **A dead event stream says so.** A 404 for a run this process no longer owns
  (a console restart) was ignored entirely: the page just stopped updating.
- **A `connect()` failure reports itself** instead of leaving a run registered as
  `running` forever with nothing on its stream.
- The API token is compared with `secrets.compare_digest`; `==` exits at the
  first mismatching byte.
- A refused request drains its body. `protocol_version` is HTTP/1.1, so
  connections are reused and an unread body was parsed as the beginning of the
  next request on that connection.
- The raw SDK message is recorded once per message, not once per event line.
- Events route by `lane_id`, not agent slug: two subagents of the same kind
  running in parallel each received the other's events.
- The coordinator is the board's header, not a Working-column card —
  `catalog.py` gave it `stage: None` for that reason and `?? "Working"` undid it.
- `install_console` no longer copies `__pycache__` into installs.
- Zombie runs, dropped SSE connections, and approval attribution now reported
  from the prompt's own `tool_use_id` rather than guessed.

## [1.27.0] - 2026-07-30

### Added

- **The Guild web console — `/console [port]`.** A browser UI (React,
  `console-ui/`) that launches runs — a slash command, a named specialist, or a
  freeform task — streams every agent onto a live pipeline board, and surfaces
  approvals and checkpoint questions as real UI instead of terminal text.
  Backed by a stdlib `http.server` + Claude Agent SDK bridge
  (`scripts/console/`), served on loopback only, guarded by a per-start token
  (`X-Guild-Token`) and an Origin allowlist. The built bundle is committed
  under `scripts/console/dist/` so installing users need no Node toolchain.
  Claude Code only — it drives the Claude Agent SDK, which the other runtimes
  don't ship. This is the 13th slash command; the installer now recurses
  `scripts/console/` (a tree `install_dir` would otherwise skip).
- **Two new CI jobs.** `console-python` runs the stdlib `unittest` suite under
  `tests/console/` (no SDK required); `console-ui` typechecks, unit-tests, and
  rebuilds the React app, then fails if `scripts/console/dist/` drifts from
  source — the same staleness guard the Gemini/Codex mirrors already have.
- **Eight new guardrail ratchets** (100 tests, from 92): the console never
  offers `bypassPermissions` or `dontAsk` as a selectable permission mode, the
  server binds `127.0.0.1` only and never `0.0.0.0`, its API is
  token-guarded and rejects a non-local `Origin`, the built bundle stays
  committed, and `emit-agent-events.sh` (the board's observer, deliberately
  untouched by this work) is still wired three ways in `hooks/hooks.json`.

### Changed

- Command count is 13 everywhere it's claimed (four manifests + README); the
  Gemini command count stays 11 (13 minus `board.md` and the newly-skipped
  `console.md` — Gemini has no Agent SDK to drive it), so no Gemini-facing
  claim moved.

## [1.26.0] - 2026-07-29

Five published sources on agent design read end to end and audited against the
pack — [`docs/research/2026-07-29-agent-literature-audit.md`](docs/research/2026-07-29-agent-literature-audit.md).
Most of the canon turned out to be already here under pack-native names
(orchestrator-workers, least-privilege tools, model tiers by failure cost,
fail-closed guardrails, HITL gates, the fast path, per-agent token telemetry),
so the audit's value is the four places it *wasn't*. One lands here; three are
held.

### Added

- **Rubric judge for the eval harness — `EVAL_JUDGE=1`.** The answer key is
  `grep`, which is exact-match scoring of a nondeterministic output, and it has
  already failed in both directions: `check_log 'update'` passes on any
  occurrence of the word, while run 4 froze a live IDOR into a test the regexes
  accepted. Each case now carries a `case_rubric` stating what a correct run must
  *achieve* rather than what it must *say*, and `EVAL_JUDGE=1` scores the run
  against it.
  - **Advisory by construction.** It never touches the check count, the case
    verdict, or the exit code, so runs stay comparable to 1–4 and eval run 5 is
    unaffected. A guardrails test asserts `judge_case` assigns to none of
    `CHECK_PASS` / `CHECK_FAIL` / `verdict`.
  - **Independent, not anchored.** The judge never sees the regexes or their
    result; the harness compares the two afterwards and marks divergence with
    `!` in `summary.md`. A disagreement in either direction is the signal.
  - **Fail-open.** Missing `python3`, an unparsable reply, or a judge timeout
    prints one line, keeps the raw reply at `<case>.judge.raw.txt`, and moves on.
    The judge runs in a neutral empty workdir so it scores the evidence bundle
    instead of wandering into the fixture app.
  - Env: `EVAL_JUDGE_MODEL` pins the judge model, `EVAL_JUDGE_TIMEOUT` (300s)
    bounds it. Verdicts persist to `<case>.judge.json`.
- **Two static ratchets** (92 guardrail tests, from 90): every case in
  `ALL_CASES` has a `case_rubric` — so a case added later can't be silently
  unjudged — and the judge-never-alters-the-verdict assertion above.

### Changed

- `tests/eval/README.md` documents the judge, its rules, and the rubric
  requirement when extending with a new case.

### Deferred

- Three body-level findings — `NOT-CHECKED` as an escalation trigger
  (confidence, not just category, should stop a lane), a declared stage budget
  with an explicit completion condition, and resume state flushed before a
  blocking checkpoint — are staged in
  [`docs/plans/2026-07-29-literature-gap-tranche.md`](docs/plans/2026-07-29-literature-gap-tranche.md)
  with the exact edits and their risks. They change agent behaviour, and **eval
  run 5** is outstanding with a deliberately un-reseeded baseline so it isolates
  the 1.24.0 worktree and reachability levers. Landing them first would confound
  it; they ship as one release after run 5 reports.
- Also recorded: the patterns deliberately **not** adopted — group-chat debate,
  decentralized handoff (not implementable, Claude Code subagents cannot transfer
  control to each other), magentic task-ledger orchestration, and voting
  ensembles — each with the reason, so they don't get re-proposed.

## [1.25.0] - 2026-07-28

Closes the two items 1.24.0 recorded but deliberately left out of scope, both
from [eval run 4](docs/evals/2026-07-28-run-4.md).

### Fixed

- **The agents-board feed now carries real durations for async stages.**
  `SubagentStop`'s documented `duration` field never arrives in practice — every
  stop event across all five run-4 feeds had `ms: null`. `board.html` already
  fell back to the `start`→`stop` timestamp delta, so the *dashboard* was never
  wrong, but the feed itself was un-timed: run 4's per-stage numbers had to be
  subtracted by hand, and the eval harness copies the feed verbatim. The emitter
  now derives `ms` from the matching start event when `duration` is absent,
  pairing on `sid` + `agent` + latest start. `.duration` is still read first, so
  a payload that ever grows the field wins.
  - The dedupe key now normalises `ms` alongside `ts`. A derived duration is a
    function of the hook's own clock, so the concurrent twin computes a slightly
    different value and would otherwise have escaped suppression — the exact
    class of bug that took two releases to kill in 1.16.0/1.17.0. The pattern
    deliberately does not match `null` (a zero-width match would corrupt the key
    to `"ms":0null`).
  - An unpaired stop event keeps `ms: null` rather than guessing. Pairing is
    heuristic by necessity: `PreToolUse` carries no id for the agent being
    spawned, so two concurrent runs of the *same* agent type can't be
    distinguished. The timestamps remain the source of truth.
- **Four new tests (90 total)**, including the realistic case the old suite
  missed: it only ever fed a synthetic `duration`. New coverage — derivation
  when `duration` is absent, twin suppression with a derived `ms`, an unpaired
  stop staying null, and an exact-elapsed assertion (seeded 42s in the past,
  asserts the derived value rather than merely "not null").

### Changed

- **Nine stale `★ NEW` markers removed from the README tree.** They marked
  additions from 1.7.0 through 1.21.0 with no defined expiry, and an
  unmaintained "new" claim is worse than no claim — the CHANGELOG is what says
  what shipped when.

## [1.24.0] - 2026-07-28

Everything here traces to a measured failure in
[eval run 4](docs/evals/2026-07-28-run-4.md) — the first sequential run since
run 2, and the first quality regression in four runs (`tests` 2/4). Nothing
discretionary: no model-tier changes, no new agents, skills, or commands.

### Fixed

- **Builders can run their own verification gates again — `isolation: worktree`
  removed from all eight writers.** `git worktree add` checks out *tracked* files
  only, so a worktree never contains `vendor/`, `node_modules/`, or `.env`. Every
  gate the bodies promise — `pint --dirty`, `phpstan analyse`, `artisan test` —
  was unrunnable there. Run 4 caught `qa-engineer` writing an entire test suite
  it could not execute ("couldn't run — no `vendor/`"), leaving the main thread to
  install dependencies and redo the verification, while two other cases spent a
  whole stage on `composer install`. Under Sail it fails harder: the container
  mounts the main project directory, so a worktree-resident agent tests the wrong
  tree or collides on container names and ports. `isolation:` is static
  frontmatter and cannot be conditional, so the choice was binary — and
  self-verification is worth more than write isolation.
- **The NOT-CHECKED contract now reaches the human.** Nine of ten commands bound
  the calibration shape to *specialist → coordinator* returns, which are internal;
  headless runs print only the final assistant message, so the v1.19.0 contract
  was structurally invisible (`/team-hygiene` was the sole exception). The shared
  `Interface` block — still byte-identical across all nine — now also binds the
  run's **own final answer** to `VERIFIED` + `NOT-CHECKED`, and
  `delivery-coordinator` gains the matching step 10. Run 4 showed the honesty was
  already there in prose ("PHPStan not run — no `phpstan.neon` exists"); it just
  wasn't labelled where the human scans.
- **qa-engineer can no longer pin a security hole as expected behavior.** Dina
  found the fixture's unguarded `update` route, flagged it — then wrote a test
  asserting "non-owner update pinned as current behavior", turning a live IDOR
  into a passing spec that the eventual fix would appear to break. The
  authorization always-check fired only for endpoints that were *already*
  protected. It now covers the unprotected case: assert the **secure** outcome
  (403), mark it `->todo()` / `markTestIncomplete()` with the reason, name it in
  FLAGS. A matching entry joins the refuse-to-ship list.

### Changed

- **Writers stay in their lane by contract instead of by isolation.** All eight
  gain one byte-identical principle: the brief names the paths you own, and a fix
  worth making outside that scope belongs in FLAGS, never in your diff.
  `delivery-coordinator`'s three worktree-dependent paragraphs are rewritten for a
  shared tree — parallel lanes must own **disjoint paths**, and integration means
  verifying one tree rather than merging branches.
- **qa-engineer's scope rule gains a reachability test.** Run 4's `policy` case
  spent 634s writing allowed+denied pairs for all seven Policy methods, and its
  own report admits `delete`/`restore`/`forceDelete` "have no corresponding
  routes". An ability with no real call site now gets one line in `NEXT`, never a
  test pair — grep for the call site first.
- **Documentation corrected where it taught the defect.**
  `docs/authoring-agents.md`'s `isolation: worktree` section is inverted (it told
  authors to set it on any agent that edits code) and gains the empirical
  reasoning; `CONTRIBUTING.md`'s frontmatter table marks the field **never**;
  `README.md` replaces "Writers run in isolated worktrees" with why nobody does.
  Three stale model annotations in the README tree are fixed in passing
  (`technical-writer` Haiku → Sonnet, `tech-lead` and `performance-engineer`
  Sonnet → Opus 4.8 — drift from 1.22.0/1.23.0).

### Added

- **Two static ratchets** in `tests/guardrails.test.sh` (86 tests): no agent body
  may declare `isolation: worktree`, and the `Interface` block must stay
  byte-identical across all nine pipeline commands *and* contain the final-answer
  clause. Both regressions would otherwise return silently.
- **`docs/evals/2026-07-28-run-4.md`** — the run-4 findings doc, evidence base for
  this release. Also records two verified wins (the 1.17.0 atomic-lock dedupe held:
  0 duplicate lines across all five feeds; 1.20.0's `SubagentStop` emitter made
  run 3's invisible async lanes visible) and one doc-vs-reality correction:
  **real `SubagentStop` payloads carry no `duration` field** — every stop event
  has `ms: null`, so async stage durations must come from the start→stop timestamp
  delta.
- **`hygiene` ceiling in `tests/eval/baseline.json`** (200s, from run 4's 86s). The
  other four ceilings are deliberately left alone: this release makes no speed
  claim, and only a sequential **run 5** can confirm the two latency levers. The
  eval answer key is unchanged on purpose — both failing `tests` checks are now
  legitimately passable, which is the cleanest verification available.

## [1.23.0] - 2026-07-28

### Changed

- **technical-writer promoted `haiku` → `sonnet`.** Reverses the 1.5.0 demotion:
  docs quality (API reference accuracy, runbook clarity) benefits from Sonnet-tier
  writing, and Sofia runs infrequently enough that the cost delta is negligible.
  scrum-master stays the pack's only `haiku` agent (high-frequency, low-stakes
  ceremony work).

## [1.22.0] - 2026-07-27

### Changed

- **Model tiers re-pinned by role importance.** The two highest-failure-cost
  reasoning roles — `solution-architect` and `security-engineer` — move from the
  floating `opus` alias to the pinned `claude-opus-5`. The deep-review/diagnosis
  roles — `tech-lead` and `performance-engineer` — are promoted from `sonnet` to
  `claude-opus-4-8` (partially reversing the 1.5.0 tech-lead demotion, now that
  Opus-tier pricing is $5/$25 per MTok). Builders and coordination roles stay on
  `sonnet`/`haiku`; the delivery-coordinator deliberately stays `sonnet` because
  Opus cost would multiply across every pipeline stage. `docs/authoring-agents.md`
  documents the pinned-ID convention.

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
