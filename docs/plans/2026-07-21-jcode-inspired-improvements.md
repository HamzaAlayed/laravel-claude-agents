# Plan: jcode-inspired improvements (1.19.0 → 1.21.0)

Source: review of [1jehuang/jcode](https://github.com/1jehuang/jcode) (2026-07-21).
Five features, grouped into three releases so each ships with its own verification.
Patterns adopted: evidence-typed completion contracts, ratchet CI budgets,
delegation-tree observability, memory consolidation cycles, published eval scorecard.
Pattern deliberately NOT adopted: jcode's autonomous-by-default tool execution —
our fail-closed guardrails are the pack's differentiator (see §5).

---

## Release 1.19.0 — Calibrated returns + ratchet budgets

### Feature 1: Evidence-typed completion contract (`NOT-CHECKED` + evidence-required `VERIFIED`)

**Why.** jcode's swarm deep-mode forces workers to return typed artifacts: findings with
`file:line` evidence, and an honest "what_i_did_not_check" list; a turn without the
contract gets re-queued. Our STATUS/DID/VERIFIED/FLAGS/NEXT return lacks the calibration
fields — a Ship verdict today reads as unbounded confidence.

**Changes.**

1. **Stage-return shape** (`agents/delivery-coordinator.md:45-49`) gains one line:
   ```
   STATUS: done | blocked | needs-decision
   DID: …
   VERIFIED: command → result (test/pint/phpstan counts) — evidence, not claims
   NOT-CHECKED: surfaces deliberately not examined (≤3 lines) — or "none"
   FLAGS: corrections, risks, checkpoint triggers — or "none"
   NEXT: handoff or "none"
   ```
   Cap NOT-CHECKED at 3 lines — it is a calibration signal, not a disclaimer dump.

2. **Reviewer bodies** — byte-identical sed-sweep line (same technique as the 1.11.0
   "Taught rules win" sweep) added to the report/verdict sections of:
   - `agents/qa-engineer.md` — Ship/Hold gates (~line 89): a Ship verdict without
     NOT-CHECKED is incomplete; "not run — no vendor/" moves from VERIFIED into it.
   - `agents/tech-lead.md` — review report format.
   - `agents/security-engineer.md` + `skills/laravel-security/SKILL.md` finding format:
     add "surfaces not threat-modeled" to the report skeleton.
   - `agents/performance-engineer.md` — measurements not taken (e.g. "did not load-test").
   Builders (backend/frontend/database/mobile/package) get the field via the shared
   stage-return shape only — no per-body wording, their "Report back distilled"
   principle already points at the coordinator's shape.

3. **Coordinator enforcement** (`agents/delivery-coordinator.md:107`): a return missing
   `VERIFIED` evidence or `NOT-CHECKED` is re-delegated **once**, naming the missing
   fields verbatim; a second incomplete return is surfaced to the human as a FLAG, never
   silently accepted. (jcode re-queues; we cap at one retry — token cost discipline.)

4. **Templates**: `skills/delivery-templates/SKILL.md` — update the stage-return /
   delivery-log templates to the six-line shape.

**Verification.** Eval run 4 (already scheduled, sequential): add two answer-key checks
to `tests/eval/run-evals.sh` — qa stage output contains `NOT-CHECKED:`, and no stage
return contains `VERIFIED:` with an empty value. Watch for return-length creep
(budget: the ≤10-line cap at coordinator line 107 becomes ≤12).

**Effort.** ~2h. Risk: wording bloat in 5 bodies — keep each addition to one line.

---

### Feature 2: Ratchet budgets in CI

**Why.** jcode commits JSON baselines (panic count, file size, swallowed errors) and
fails CI on any regression — debt is measured and frozen, not remembered. Our
equivalents: agent bodies creep every release, and inventory counts went stale in
1.10.0 (currently guarded only by a grep convention).

**Changes.**

1. **`scripts/check_body_budget.py` + `scripts/body_budget.json`** (committed baseline):
   - Per agent: max body lines, max `description:` characters.
   - Per skill: max SKILL.md lines.
   - Seed budgets = current actuals + 10% headroom (measure first, then freeze).
   - Over budget → exit 1 with `::error file=…` annotations (matches ci.yml style).
   - Under budget by >15% → exit 0 but print a tighten-the-baseline notice.
   - No deps beyond stdlib (frontmatter split by `---`, not YAML) — runs in the
     same job as the other python checks, no PyYAML needed.

2. **`scripts/check_inventory_sync.py`**: compute agent/command/skill/hook counts from
   disk; assert they match README claims, all 4 manifests, and the build-gemini
   description string. Encodes the known offsets structurally (gemini commands = 10
   because board.md is skipped; codex ships no commands) instead of prose in memory.

3. **CI wiring** (`.github/workflows/ci.yml`): one new job `budgets` running both
   scripts. Both also called from `scripts/validate-frontmatter.py`'s local path?
   No — keep them standalone; add to the release checklist in CONTRIBUTING/memory.

4. **Eval scorecard baseline** — `tests/eval/baseline.json`: per-case duration + token
   ceilings from sequential runs 1–3. `run-evals.sh` compares at end of a sequential
   run and prints PASS/REGRESSED per case (soft warn, never hard-fail — timings are
   machine-dependent and evals are manual/billed, so this never runs in CI).

**Verification.** CI green with seeded budgets; deliberately fatten one body locally →
job fails with the right annotation; guardrails suite untouched.

**Effort.** ~3h. Risk: budgets seeded too tight cause noise — the +10% headroom and
the measure-first step handle it.

---

## Release 1.20.0 — Delegation tree + SubagentStop (rides with eval run 4)

### Feature 3: Board delegation tree + async-agent visibility

**Why.** jcode encodes the spawn tree (`report_back_to_session_id`) so its UI shows
who spawned whom. Our board renders flat lanes, and async-launched subagents are
invisible (known gap from eval run 3: PostToolUse fires at launch with ms/tokens null,
no completion event).

**Changes.**

1. **Parent capture** (`scripts/emit-agent-events.sh`): add `parent` to the event
   object — the hook stdin's `agent_id`/`agent_type` identify the *calling* agent when
   an Agent call is made from inside a subagent (verified Claude Code fact, 1.13.0
   cycle; re-verify field names against current hooks docs before building). Top-level
   calls → `parent: null`. Must land in **both** the jq and python3 branches
   (`check-hook-sync.py` and guardrails test #77/#78 style twin-parity applies).

2. **`scripts/board.html`**: indent child lanes under their parent's lane (parent id →
   lane grouping); unknown parent → flat as today. GUILD initials and colors unchanged.

3. **SubagentStop emitter**: register a `SubagentStop` hook in `hooks.json` +
   `install.sh` (event, matcher, script) tuples, reusing emit-agent-events.sh with an
   `ev: "end"` mapping, so async-launched agents get a real completion event with
   duration. **Gate:** verify the SubagentStop hook event exists and its stdin schema
   at code.claude.com/docs/en/hooks.md first — pack convention: never ship against an
   unverified API. If absent, ship parent-capture only and keep SubagentStop on the
   ladder.

4. **Tests**: extend `tests/guardrails.test.sh` — parent field present/absent cases,
   SubagentStop event dedupe (the 1.17.0 mkdir-lock race fix must hold for the new
   event type), jq-removed fallback parity.

**Verification.** Eval run 4 doubles as the live test: the policy case's async agent
must appear with a completion event; feeds must stay duplicate-free (run-4 checklist
item already).

**Effort.** ~4h including doc verification. Risk: SubagentStop schema differs from
PostToolUse — the emitter's field mapping is the only touch point, keep it isolated.

---

## Release 1.21.0 — Ledger hygiene + public scorecard

### Feature 4: `/team-hygiene` — ledger consolidation cycle

**Why.** jcode's memory system runs periodic consolidation (dedup, staleness, conflict
resolution). Our `docs/team/` ledger gets only ad-hoc, coordinator-driven eviction at
delivery end (`agents/delivery-coordinator.md:111`). Entries rot between deliveries.

**Changes.**

1. **New command `commands/team-hygiene.md`** (12th command), owner: **scrum-master**
   (Haiku — cheap, already has Edit + sprint-boundary duties). Procedure:
   - Scan `docs/team/conventions.md`, `stack.md`, `decisions.md`.
   - Detect: duplicates (same rule, different wording), conflicts (two entries
     disagree — the coordinator's update-in-place rule failed), stale facts (run each
     entry's **Verify** command; failures are eviction candidates), dead scopes
     (Scope path no longer exists in repo).
   - Output a proposal table (keep / merge-into / evict + reason); **human approves
     before any edit** — same poisoning defense as the 1.16.0 KB design. Never
     silently delete (existing rule, now enforced by the command shape).
2. **Coordinator step 8** (`delivery-coordinator.md:111`): delivery-end eviction
   becomes "run the `/team-hygiene` procedure" instead of bespoke wording.
3. **Template**: hygiene-report shape added to `skills/delivery-templates/SKILL.md`.
4. **Mirrors**: command ships to gemini (11 commands there, breaking the "gemini = 10"
   constant — `check_inventory_sync.py` from 1.19.0 makes this a one-line budget
   change, proving the ratchet's worth); codex unchanged (no commands).

**Verification.** Fixture test: seed a throwaway `docs/team/` with a planted duplicate,
a conflict, and a stale Verify → run `/team-hygiene` headless → assert the proposal
table catches all three (add as eval case 5 or a cheap standalone script test).

**Effort.** ~3h.

### Feature 5: README — eval scorecard + fail-closed positioning

**Why.** jcode's README leads with benchmark tables; ours buries its rarest asset —
three clean runs against a planted-flaw app — in docs/evals/. And the security review
showed our guardrail posture (5 fail-closed hooks) is genuinely ahead of a 10k-star
competitor: say so.

**Changes.**

1. README section "Proven against a planted-flaw app": table of eval cases × runs
   (4/4 cases, 14/14 checks, three runs), link to `docs/evals/` findings and the
   answer-key README. Numbers sourced from `tests/eval/baseline.json` (Feature 2) so
   the README can't drift from the measured truth — add a `check_inventory_sync.py`
   assertion tying them.
2. README "Design choices" gains one paragraph: guardrails fail closed (contrast:
   agent harnesses that ship autonomous shell with fail-open hooks), citing
   `docs/read-only-by-design.md`.

**Effort.** ~1h.

---

## Cross-cutting (every release)

- Version bump touches VERSION + all 4 manifests **before** running the build scripts
  (1.18.0 lesson); regenerate gemini/codex, never hand-edit mirrors.
- shellcheck: new/changed shell must pass both SC2317 and SC2329 conventions (1.18.0
  lesson); run the full strict command locally before pushing.
- Guardrails suite + validate-frontmatter on every change; CHANGELOG in
  Keep-a-Changelog voice; tag + GitHub release page (v1.18.0 restarted the practice).

## Sequencing rationale

1.19.0 first because Feature 1 changes what eval run 4 should assert and Feature 2's
budgets want seeding before more body edits land. 1.20.0 is coupled to run 4's live
dedupe test. 1.21.0 last because `/team-hygiene`'s inventory change leans on the
1.19.0 sync checker, and the README scorecard wants run 4's numbers included.

## Open questions (resolve before the relevant release)

1. SubagentStop hook: exists? stdin schema? (gate for 1.20.0 §3.3)
2. Exact parent-id field name on nested Agent-call hook stdin (1.20.0 §3.1).
3. Budget seed numbers — measure current actuals at 1.19.0 start, not now.
4. Does NOT-CHECKED belong in the ≤10-line cap or does the cap move to 12? Decide
   during the sweep; eval run 4 arbitrates if returns bloat.
