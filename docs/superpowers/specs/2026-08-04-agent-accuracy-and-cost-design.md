# Design — agent accuracy and cost, made measurable

**Date:** 2026-08-04
**Scope:** the eval harness, `agents/delivery-coordinator.md`, and `tests/eval/baseline.json`. No other agent *prose* changes — the one path that touches other agents is the effort spike below, and only as frontmatter, and only if the official docs confirm the field exists.
**Priority when the three goals conflict, chosen by the user:** accuracy first, then cost, then speed. **Cost savings must come from waste — redundant work, over-delegation, unnecessary depth — never from less checking.** The pack's whole pitch is planted-flaw detection; a cheaper pack that finds fewer flaws is a worse pack.

## Why this milestone is mostly instrumentation

The request was to make the agents more accurate, faster, and cheaper. Two of those three are already measured: correctness by the eval answer key, latency by per-case duration ceilings in `baseline.json`. **Cost is measured by nothing.** There is no ceiling, no baseline, and no per-run number a reviewer could regress against.

Worse, the one cost signal that exists is not trustworthy. Run 5's per-case feeds each report an identical 48,895 qa-engineer tokens — including in `action`, `hygiene`, and `n-plus-one`, three cases that [run 5's own finding 4](../../evals/2026-07-31-run-5.md) established delegated nothing at all. The number is fixture debris: the same two events (24,107 tokens / 2673 ms and 24,788 / 4848 ms) appear in all five feeds. `f12ad7c` truncates the feed per case so run 6 will be clean, but every cost figure from runs 1–5 is contaminated.

Subtracting that constant pair recovers what run 5 actually cost:

| case | agent | tokens | duration |
| --- | --- | ---: | ---: |
| `policy` | backend-developer | 41,495 | 103 s |
| `policy` | qa-engineer | 52,959 | 158 s |
| `policy` | security-engineer | 88,625 | 526 s |
| `tests` | qa-engineer | 138,035 | 531 s |

**Time and money point at different agents.** Run 5's finding 2 named security-engineer as the hog on wall-clock, and it is — 526 s, two thirds of `policy`'s subagent time. By tokens, qa-engineer is the hog: ~191k across two cases, roughly 60% of all subagent spend. Tuning on latency alone would have optimized the wrong agent. That is the case for the instrument in one line.

## Pricing, so the tiers are argued from facts

Verified against the current model catalog rather than recalled:

| tier | input $/1M | output $/1M | pack agents |
| --- | ---: | ---: | --- |
| Opus 5 / Opus 4.8 | $5 | $25 | security-engineer, solution-architect (Opus 5); tech-lead, performance-engineer (Opus 4.8) |
| Sonnet | $3 | $15 | the other 12 |
| Haiku 4.5 | $1 | $5 | scrum-master |

Two consequences shaped this design:

- **Opus is 1.67× Sonnet, not the 5× people assume.** Demoting the four Opus agents saves far less than intuition suggests, while spending exactly the accuracy the user ranked first. Not proposed.
- **Output costs 5× input on every tier.** Cost is driven by how much the agents *write* and how much tool output flows back into context — not by how long their bodies are. Combined with prompt caching (cached prefixes read at ~0.1×, and a 17-agent body set is the most cacheable thing in the pack), **body slimming is a weak lever with a real accuracy cost.** Also not proposed.

## The measurement layer

**Capture.** `tests/eval/run-evals.sh` runs headless `claude -p` with default output, so `<case>.log` holds only the final answer — 36 lines for run 5's `tests` case, with no record of what the 531 s or 138k tokens went on. Adding `--output-format stream-json --verbose` captures the full transcript, whose `usage` objects carry the **input/output split**. That split is what turns a token count into a defensible dollar figure; without it, any cost number is a blended-rate guess.

**Deliberately not a hook.** Per-tool telemetry could come from a PostToolUse hook with an empty matcher, but that spawns a bash process per tool call, and this repo has been bitten twice by concurrent-hook races (the 1.16.0 doubled-events fix and the 1.17.0 atomic-mkdir dedupe). A single harness flag adds no runtime surface and cannot race.

**Derive, then discard.** Raw transcripts run to megabytes per case and `tests/eval/results/` is committed. The harness writes a `<case>.cost.json` summary — per-agent input and output tokens, per-tool call counts, and dollars computed from each agent's pinned model rate — then deletes the raw transcript. A rate table lives beside the harness with its source and date, so a stale price is visible rather than silently wrong.

**Ratchet.** `baseline.json` gains per-case token ceilings beside its existing duration ceilings, reseeded from run 6 (the first trustworthy numbers). Cost regressions then fail the same way latency ones already do. Run 5 set the precedent for honest ceilings: it raised `policy` to 1100 s deliberately and recorded why, on the grounds that a ceiling which always reads REGRESSED stops carrying information.

## The agent changes

Only the three held items from `docs/plans/2026-07-29-literature-gap-tranche.md`, whose gate cleared when run 5 reported. All three edit `agents/delivery-coordinator.md` alone, so the byte-identical `Interface` block shared across the nine pipeline commands stays untouched and its guardrail test stays green.

1. **`NOT-CHECKED` becomes an escalation trigger.** Escalation currently fires on category only; the calibrated-returns contract collects `NOT-CHECKED` and nothing consumes it. This is the accuracy item.
2. **A declared stage budget with an explicit completion condition.** Today there is only a lane cap and a per-stage retry cap — nothing bounds a run as a whole. This is the cost item.
3. **Resume state at blocking checkpoints.** Checkpoints persist nothing, so an interrupted run restarts.

**Two candidate changes were dropped after inspection, and the reasoning is recorded so nobody re-proposes them:**

- **A qa-engineer scope rule.** It already has two. The 1.16.0 rule scopes it to the brief's scenarios; the 1.24.0 rule makes it grep for a call site before testing an unreachable branch. Both are in the body today, and it still spent 138k tokens on one invocation. A third rule would be guessing at a driver nobody has measured — precisely what run 5 meant by "do not tune it blind". **qa-engineer's cost is this milestone's headline measurement target, not an edit.**
- **Deleting self-verification scaffolding.** Current Claude models verify their own work and prompts telling them to verify cause over-verification, so this looked promising. Grepping all 17 bodies returns one match: technical-writer's docs-drift check, which is a freshness policy for documentation pages, not model self-verification. Nothing to remove.

## The effort spike

Timeboxed, gated, and shipped only on evidence. Check the official Claude Code subagent documentation for whether agent frontmatter accepts an effort or thinking-depth setting. Current frontmatter across all 17 agents uses exactly six keys — `color`, `description`, `memory`, `model`, `name`, `tools` — and `effort` appears nowhere in the pack or its authoring docs.

If supported, it is the largest cost lever available, because it scales thinking depth *and* tool-call volume, and the pack's 17 agents differ enormously in failure cost — scrum-master summarizing standups has no business running at the depth security-engineer needs for an auth review. If the docs do not confirm it, it ships as a **recorded non-option** in the pack's verified-facts memory, the same way `isolation: worktree` and the `can_use_tool` hook requirement were recorded. Nothing speculative lands in a body.

## Verification

**Eval run 6 is a human-run, billed step and is not part of the implementation plan.** The harness makes real headless `claude -p` calls against the fixture app; CI only shellchecks it. The plan's deliverable is a harness that *would* produce a clean cost baseline, verified against recorded fixtures — the run itself, its findings doc, and the baseline reseed happen afterwards, when the human chooses to spend on it.

When it runs, it is sequential and measures three things in one pass:

- **The tranche's behavioral effect.** Watch `policy` and `tests` — the only two cases that delegate — for checkpoint over-triggering, item 1's known risk. The other three cases fast-path and exercise no lanes.
- **The first trustworthy cost baseline.** Per-agent input/output tokens and dollars per case, feeding the reseeded ceilings.
- **`EVAL_JUDGE=1`, finally.** The rubric judge shipped in v1.26.0 and has never run against a real eval.

Run 5's run-6 checklist carries two further items this design does not change: its finding 1 must stay fixed (it is, in `f12ad7c`), and the README's worktree claim needs no correction.

## What this milestone does not do

- **No model-tier changes.** Argued above from real pricing against the user's accuracy-first ruling.
- **No body slimming.** Weak lever once caching is accounted for, real accuracy cost.
- **No qa-engineer edit.** Measured first, tuned in a later milestone.
- **No answer-key changes.** Run 6 must stay comparable to run 5.
