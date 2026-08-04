# Literature-gap tranche — ready to apply (gate cleared 2026-07-31)

Three body-level fixes from the
[2026-07-29 agent-literature audit](../research/2026-07-29-agent-literature-audit.md).
All three edit agent bodies, which changes agent behaviour — so they were held
until eval run 5 reported. Run 5 was deliberately left with an un-reseeded
baseline so it isolated the 1.24.0 worktree and reachability levers; landing
these first would have confounded it.

The audit's fourth finding (rubric-judge eval scoring) already shipped in
v1.26.0 — it touches only the measuring instrument, so it was safe to land then.

**Gate: CLEARED.** [Eval run 5](../evals/2026-07-31-run-5.md) reported on
2026-07-31 — 5/5 cases, 19/19 checks, baseline reseeded (`policy` raised to
1100s deliberately, `action` lowered to 600s), and its finding 1 (per-case event
feeds polluted by committed fixture telemetry) fixed in `f12ad7c`. Run 5's own
run-6 checklist expects this tranche to land before run 6. Apply items 1–3 as
one release.

---

## Item 1 — Make `NOT-CHECKED` an escalation trigger, not a footnote

**Gap.** Escalation fires on *category* only (authn, authz, billing, PII, money,
tenant isolation). Published guidance pairs sensitive-action triggers with
**confidence** triggers: escalate when "actions are sensitive, confidence is
low, or customers request a person" (ByteByteGo), and OpenAI's guide treats
failure thresholds as a distinct HITL trigger from high-risk actions.

The pack already *collects* the signal — every stage return carries
`NOT-CHECKED` (v1.24.0 extended it to bind the run's own final answer). Nothing
consumes it. A stage whose `NOT-CHECKED` swallows the substance of its brief
advances exactly like a fully verified one.

**Change.** `agents/delivery-coordinator.md`, step 5 (integrate + persist).
After the existing verification sentence, add:

> A return whose `NOT-CHECKED` covers the substance of its own brief is not a
> completed stage — it is an unverified one wearing a `STATUS: done`. Treat it
> like a failed success criterion: re-brief once naming the unchecked surface,
> and if it comes back unchecked again, stop the lane and surface it as a
> checkpoint. Low confidence is a stop trigger in its own right, independent of
> the checkpoint categories.

**Also** extend the closing checkpoint line's preamble in
`agents/delivery-coordinator.md` so category and confidence read as peers, not
as one list:

> **Human checkpoint required:** … *(unchanged categories)* … — plus any stage
> that cannot verify the core of its own brief.

**Risk.** Over-triggering: a specialist that lists every adjacent surface in
`NOT-CHECKED` could stall a lane. Mitigated by the existing wording that
`NOT-CHECKED` is "calibration, not a disclaimer dump", and by scoping the
trigger to *the substance of its own brief* rather than any non-empty value.
Watch for it in the run after this lands: a rise in checkpoint prompts per
delivery is the tell.

## Item 2 — A declared stage budget with an explicit completion condition

**Gap.** Both caps in the pack are local: parallel lanes ≤2–3, per-stage retry
≤1. Nothing bounds total stages. Step 3 replans "next 1–3 steps" each cycle with
no termination condition beyond the coordinator's judgement.

Published guidance is unanimous here — "iteration caps, timeouts, explicit
completion conditions" (ByteByteGo), iteration limits to guard tool-call loops
(OpenAI), and a manager that must "guard against infinite remediation loops" and
watch for stalls (Azure, magentic). ByteByteGo's arithmetic is the argument: at
95% per-step reliability, twenty sequential steps succeed about a third of the
time.

**Change.** `agents/delivery-coordinator.md`, step 3 (plan + print the board).
Append:

> State the stage budget on the board — the number of stages you expect this
> delivery to take, and the condition that ends it (`done when: <the observable
> thing>`). The board is a plan the human approved, so growing past that budget
> is a re-plan, not a continuation: reprint the board with the new count and the
> reason it grew, and get agreement before spending the extra stages. Three
> re-plans on one delivery is a scoping failure — stop and hand the shape of the
> problem back to the human.

Board example in the same body gains the budget line:

```
▶ invoices — make-feature · 4 stages · done when: subscription upgrade covered by green feature tests
```

**Risk.** Low. It is a display + replan rule, not a hard abort; the coordinator
already reprints the board every stage.

## Item 3 — Persist resume state at a blocking checkpoint

**Gap.** `grep -rin 'resume\|pause\|interrupt' agents/ commands/` returns
nothing. Azure is explicit: mandatory gates make the orchestration synchronous,
"so persist state at these checkpoints to resume operation without a replay of
prior agent work". The delivery log is written per phase, but a `⏸` writes no
state — a session that stops at a checkpoint and resumes tomorrow rebuilds board
position, open lanes, and the pending question from a transcript the new session
does not have.

**Change.** `agents/delivery-coordinator.md`, step 7 (surface checkpoints).
Append:

> Before you block on a checkpoint, flush the resume state to
> `docs/delivery/<feature>/log.md`: the board as printed, which lanes are open
> and which paths they own, the exact question pending, and the options offered.
> A checkpoint can outlive the session — a resumed delivery that has to
> reconstruct its own position from a transcript it no longer has replays work
> the human already paid for.

**Risk.** Low, one extra small write per checkpoint. It also improves the
delivery log's value as an audit trail, which the Azure guidance asks for
separately.

---

## Applying this tranche

Standard release checklist (`docs/authoring-agents.md` + the release conventions):

1. Apply items 1–3 to `agents/delivery-coordinator.md`. **No other body
   changes** — none of the three touch the shared `Interface` block in the 9
   pipeline commands, so its byte-identical guardrail test stays green.
2. `python3 scripts/check_body_budget.py --reseed` (the coordinator body grows) —
   same commit.
3. Regenerate mirrors: `scripts/build-gemini-extension.py`,
   `scripts/build-codex-extension.py`. Never hand-edit mirrors.
4. `tests/guardrails.test.sh` + `scripts/validate-frontmatter.py`.
5. `scripts/check_inventory_sync.py` — counts do not change, so this should be a
   no-op; if it complains, a claim drifted independently.
6. VERSION + **all four hand-maintained manifests** (`.claude-plugin/{plugin,marketplace}.json`,
   `.cursor-plugin/{plugin,marketplace}.json`); gemini's comes from the rebuild in
   step 3, so bump VERSION *before* running it. Since v1.28.0
   `check_inventory_sync.py` walks all five manifests for `version` at any depth
   and fails if any differs from VERSION — that check is what caught
   `.cursor-plugin/marketplace.json` sitting ten releases behind. CHANGELOG in
   Keep-a-Changelog voice.
7. Then **eval run 6** to measure the tranche: watch checkpoint-prompt count per
   delivery (item 1's over-trigger risk) and total stages per case (item 2).
