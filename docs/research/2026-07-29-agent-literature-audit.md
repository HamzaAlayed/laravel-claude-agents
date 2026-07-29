# Agent-design literature audit — 2026-07-29

Five industry sources on building agents, read end to end and mapped against
what this pack actually does. The point is not a reading list: it is to find
where the pack has **independently converged** on published practice (leave it
alone, and stop re-deriving it), and where it has a **real gap** (fix it).

Verdicts are evidence-backed — every "satisfied" row names the file that
satisfies it, every gap names the line that proves the absence.

## Sources

| # | Source | Access |
| - | ------ | ------ |
| 1 | [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | read in full |
| 2 | [Azure Architecture Center — AI agent orchestration patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) | read in full (7133 words) |
| 3 | [ByteByteGo — Best practices for building AI agents](https://blog.bytebytego.com/p/best-practices-for-building-ai-agents) | read in full |
| 4 | [OpenAI — A practical guide to building agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/) | **partial** — see note |
| 5 | [Building my own AI agent orchestrator (level 8)](https://medium.com/@onomojo/building-my-own-ai-agent-orchestrator-a-journey-to-level-8-14cfb0c0a813) | read in full |

> **Source 4 access note.** The landing page returns HTTP 403 to non-browser
> clients, and the canonical PDF
> (`cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf`)
> ships every glyph as vector outlines — `FontFile: 0`, `ToUnicode: 0`, so it
> has no extractable text layer at all and only OCR would recover it. Its
> claims below are therefore sourced from search-result excerpts and a
> secondary summary, and are marked *(4, secondary)*. Treat them as weaker
> evidence than 1–3 and 5. Re-verify against the primary before promoting any
> of them to canon.

## Already satisfied — convergent design

The pack arrived at most of the published canon on its own. These rows are
closed: do not re-litigate them, and do not "add" a practice that is already
here under a different name.

| Prescription | Source | Pack mechanism |
| ------------ | ------ | -------------- |
| Orchestrator-workers: a central LLM decomposes and delegates, subtasks not predefined | 1, 2 (*manager pattern*, 4 secondary) | [`delivery-coordinator.md`](../../agents/delivery-coordinator.md) — routing map + `When invoked` |
| Start simple; add agentic machinery only when simpler fails | 1, 2, 3 | Fast path — single-specialist asks skip the pipeline entirely ([`delivery-coordinator.md:95`](../../agents/delivery-coordinator.md#L95)) |
| Show the agent's planning steps; prioritise transparency | 1 | Progress board, reprinted after every stage ([`:29-40`](../../agents/delivery-coordinator.md#L29-L40)) |
| Narrow, single-job agents beat one broad agent | 2, 3, 4 (secondary) | 17 role-scoped specialists, each with an explicit lane + `Handoffs` |
| Least privilege per agent | 2 | Per-role `tools:` grants; reviewers set `disallowedTools` ([`authoring-agents.md:75-81`](../authoring-agents.md#L75-L81)) |
| Match model tier to task complexity, not one model everywhere | 2 (cost), 5 | Pinned tiers by failure cost — `claude-opus-5` for architect/security, `sonnet` builders, `haiku` scrum-master |
| Poka-yoke the tools; make mistakes structurally hard | 1 | 5 fail-closed `PreToolUse` guardrails ([`hooks/hooks.json`](../../hooks/hooks.json)) — prod SQL, prod artisan, `.env`, reviewer writes, Sail |
| Curate context per call; compact between agents | 2, 3 | Minimum-context briefs, no file dumps, `≤12`-line stage returns ([`:18`](../../agents/delivery-coordinator.md#L18), [`:108`](../../agents/delivery-coordinator.md#L108)) |
| Validate agent output before passing it downstream | 2 | Coordinator re-runs success criteria itself; "a subagent's *done* is a claim, not a fact" ([`:109`](../../agents/delivery-coordinator.md#L109)) |
| Circuit-break a failing dependency instead of retrying forever | 2 | Re-brief once → fails twice → stop the lane, escalate ([`:110`](../../agents/delivery-coordinator.md#L110)) |
| Human-in-the-loop gates scoped to sensitive operations, not all output | 2, 3, 4 (secondary) | `Human checkpoint required:` line in all 17 bodies |
| Maker-checker / evaluator-optimizer loop with a read-only checker | 1, 2 | Review roles report findings, the owning builder fixes ([`read-only-by-design.md`](../read-only-by-design.md)) |
| Persist state externally; don't rely on in-context memory | 2, 3 | `docs/**` artifacts + delivery log + team KB (`conventions`/`stack`/`decisions`) |
| Cap concurrency; more WIP lengthens cycle time | 2, 3 | Parallel lanes capped 2–3, lanes assigned disjoint paths ([`:118`](../../agents/delivery-coordinator.md#L118)) |
| Instrument every agent operation and handoff | 2, 5 | [`emit-agent-events.sh`](../../scripts/emit-agent-events.sh) → `agents-board.jsonl` → [`board.html`](../../scripts/board.html) |
| Track token consumption per agent and per run | 2, 5 | Per-lane tokens + run total ([`board.html:165-185`](../../scripts/board.html#L165-L185)) |
| Version-control and review prompts like source code | 3 | Bodies in git + ratcheted sizes (`body_budget.json`) + inventory-claim CI check |
| Evaluate against known-answer cases before shipping | 1 ("run many example inputs"), 2 | [`tests/eval/`](../../tests/eval/) — planted-flaw fixture, 5 cases, timing baseline |
| High-quality instructions are the top success factor; convert SOPs into numbered steps with explicit branches | 4 (secondary) | Every body: `Principles` / `When invoked` (numbered) / `Anti-patterns (refuse to ship)` |

Notable inversion: source 4's own acknowledged weak spot is evaluation — no
guidance on benchmarking, reliability, or production-readiness. That is one of
this pack's strongest areas. The influence runs the other way.

## Gaps — confirmed against the tree

### 1. Escalation triggers on category only, never on confidence

**Prescribed.** Escalate "when actions are sensitive, confidence is low, or
customers request a person" (3). Source 4 *(secondary)* pairs high-risk actions
with **failure thresholds** as distinct HITL triggers.

**Actual.** Checkpoints enumerate *categories* — authn, authz, billing, PII,
money, tenant isolation
([`delivery-coordinator.md:136`](../../agents/delivery-coordinator.md#L136)).
`NOT-CHECKED` already makes a stage declare its own blind spots
([`:48`](../../agents/delivery-coordinator.md#L48)) — but nothing consumes it.
A stage returning thin `VERIFIED` and a `NOT-CHECKED` that swallows the core of
the ask advances exactly like a fully verified one. The calibration signal is
printed and dropped.

**Fix.** Make `NOT-CHECKED` load-bearing: when it covers the substance of the
brief, that is a stop, not a footnote. → staged tranche, item 1.

### 2. Eval scoring is exact-match regex

**Prescribed.** "Agent outputs are nondeterministic, so use scoring rubrics or
language-model-as-judge evaluations rather than exact-match assertions" (2).

**Actual.** Every check is `grep`
([`run-evals.sh:129-160`](../../tests/eval/run-evals.sh#L129-L160)). The
sharpest example is `check_log 'update'`
([`:174`](../../tests/eval/run-evals.sh#L174)) — it passes on *any* occurrence
of the word "update" anywhere in the transcript. This cuts both ways, and the
pack has already paid on both sides: run 4 froze a live IDOR into a *passing*
test (regex satisfied, intent violated), and 2 of 4 `tests` checks failed on
wording while the underlying work was arguably fine.

**Fix.** Add an opt-in rubric judge alongside the regexes — intent-level
scoring that can dissent from a regex verdict in either direction. → **landed
now**, `EVAL_JUDGE=1`.

### 3. No global stage budget and no explicit completion condition

**Prescribed.** "Implement hard limits: iteration caps, timeouts, explicit
completion conditions" (3); set iteration limits to guard tool-call loops (4,
secondary); a manager agent must "guard against infinite remediation loops" and
watch for stalls (2, magentic).

**Actual.** Two caps exist and both are local: parallel *lanes* ≤2–3
([`:118`](../../agents/delivery-coordinator.md#L118)) and per-stage retry ≤1
([`:110`](../../agents/delivery-coordinator.md#L110)). Nothing bounds the total
number of stages. Step 3 replans "next 1–3 steps" each cycle
([`:99`](../../agents/delivery-coordinator.md#L99)) with no termination
condition beyond the coordinator's own judgement, and no rule for what happens
when a delivery keeps growing stages without converging.

**Fix.** A declared stage budget at plan time, and re-confirmation with the
human when it is exceeded. → staged tranche, item 2.

### 4. Checkpoints don't persist resume state

**Prescribed.** "Mandatory gates make the orchestration synchronous at that
step, so persist state at these checkpoints to resume operation without a
replay of prior agent work" (2).

**Actual.** `grep -rin 'resume\|pause\|interrupt' agents/ commands/` returns
nothing. The delivery log is written per phase
([`:113`](../../agents/delivery-coordinator.md#L113)) but a blocking checkpoint
writes no state, so a session that stops at `⏸` and resumes tomorrow has to
reconstruct board position, open lanes, and the pending question from the
transcript — which a fresh session does not have.

**Fix.** Flush board + pending decision to the delivery log *before* blocking.
→ staged tranche, item 3.

## Deliberately rejected

Not every published pattern belongs here. Recording the refusals so they don't
get re-proposed:

- **Group-chat / multi-agent debate orchestration** (2). Azure itself caps it at
  ≤3 agents and flags conversation loops as the main failure mode. The pack's
  review → fix loop already covers validation, and a shared debate thread over
  a code diff burns tokens without changing the diff. The deterministic gates
  (`pint`, `phpstan`, the suite) are cheaper *and* exact.
- **Decentralized handoff** (2, and 4's second pattern). Not implementable:
  Claude Code subagents cannot transfer control to each other — only the main
  thread spawns. The `Handoffs` sections are advisory routing hints *for the
  coordinator*, not runtime transfers, and should not be reworded to imply
  otherwise.
- **Magentic / task-ledger orchestration** (2). Avoid when work is
  time-sensitive; the plan + progress board + delivery log is the light version
  of the same idea, without the manager's replan-until-viable loop.
- **Voting / ensemble on the same task** (1 *parallelization-voting*, 2
  *quorum*). Parallel `tech-lead` + `security-engineer` is **sectioning** —
  different lenses, not repeated votes. Paying 3× for a majority verdict on a
  diff is poor value when the compiler, Larastan, and the test suite already
  answer exactly and for free.
- **Framework adoption** (1 warns frameworks obscure prompts and invite
  complexity). The pack is markdown bodies + shell hooks precisely so the prompt
  is the artifact.

## Disposition

| Gap | Where it landed |
| --- | --------------- |
| 2 — rubric-judge scoring | **v1.26.0**, opt-in `EVAL_JUDGE=1` (no agent-behaviour change) |
| 1 — confidence escalation | [staged tranche](../plans/2026-07-29-literature-gap-tranche.md), item 1 |
| 3 — stage budget | staged tranche, item 2 |
| 4 — checkpoint resume state | staged tranche, item 3 |

Items 1, 3 and 4 edit agent bodies, which would change agent behaviour
mid-experiment: **eval run 5** is outstanding and was deliberately left with an
un-reseeded baseline so it isolates the 1.24.0 worktree and reachability levers.
They ship as a reviewed tranche after run 5 reports. Gap 2 touches only the
measuring instrument, is opt-in, and leaves the regex checks untouched — so
run 5 stays comparable to runs 1–4 either way.
