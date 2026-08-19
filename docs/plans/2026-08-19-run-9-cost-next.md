# Run 9 cost — next billed experiment (after 1.43.0)

**Not a fix.** Investigation: `docs/evals/2026-08-19-run-9-cost.md`. Do not raise `max_usd` / `max_tokens`. Do not edit agents, commands, or the fixture. Do not merge `feat/agent-cost-instrument`. Do not re-add `check_stage_return_shape`.

## Experiment

After v1.43.0 Adoption ships, run one billed `feature` case with `EVAL_TIMEOUT` set to at least `cases.feature.max_seconds` (1900) so a coordinator close can exist on the clock. Leave `max_usd` at $8.50. Keep `KEEP_WORKDIR=1` and `KEEP_TRANSCRIPT=1` so `feature.cost.json`, `$LOG`, `$FULL_LOG`, and the harvest files are not lost again.

```sh
EVAL_TIMEOUT=1900 KEEP_WORKDIR=1 KEEP_TRANSCRIPT=1 ./tests/eval/run-evals.sh feature
```

Estimated spend: **$8–10**. Same order as run 9 if the 419/500 loop recurs; closer to the $6.55 seed if the orchestrator takes the seed/run-7 path (api routes + auth checkpoint, no re-brief loop).

## What to read, in order

1. Harness line: `TIMED OUT` or not, duration vs 1200 and vs 1900.
2. `feature.cost.json`: `billed.usd`, `attributed.total` token classes (cache_read vs the rest), `coverage_of_billed`, per-agent tools (`Edit` / `SendMessage` / `Agent` counts on main).
3. `$FULL_LOG`: does the *orchestrator* close with its own `VERIFIED` / `NOT-CHECKED`, or does `$LOG` only pass because a specialist was concatenated (run 9 / run 7 timeout path)?
4. Harvest files on disk, read directly — same bar as run 9.

## What would falsify the write-up's hypothesis

| Outcome | Reads as |
| --- | --- |
| Finishes with no 419/500 re-brief loop (`SendMessage` not used for HTTP-kernel retries) and bills **≤ $8.50** | Finding 1 holds. Ceiling stays. The $9.00 was the loop + 1200s kill, not "1.42's new happy path." |
| Finishes with no 419/500 loop and bills **> $8.50** | Verify-before-advancing *alone* is the new shape. Then — and only then — a `max_usd` reseed is an argument, written into `baseline.json`'s `usd_basis`, not an absorption of run 9. |
| Still loops 419/500 after 1900s, or still has no orchestrator close at 1900s | The missing close is not the 1200s kill; the loop is not timeout-shaped. Stop and re-open Phase 1 before touching ceilings. |

A guest-500 disappearing because someone added `route('login')` to the fixture is **not** this experiment. That change is out of bounds here; it would also fail to explain CSRF 419.

## Out of bounds

- Raising `EVAL_TIMEOUT`'s default for every case (this experiment is per-invocation).
- Raising `max_usd` / `max_tokens` before the outcome table above is filled.
- Model-tier changes, body slimming, qa-engineer tuning (Prove-it non-goals).
- Implementing a subagent-inclusive log (run 8's filed gap; own plan).
