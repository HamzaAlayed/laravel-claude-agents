# Eval harness

`run-evals.sh` proves the pack's agents actually find — or fix — known flaws,
by running real headless `claude -p` sessions against a copy of
[`tests/fixture-app`](../fixture-app/) and asserting against the answer key
below. It also times every run, which feeds the speed findings in
`docs/evals/`.

**This is a manual harness, not CI** — every case is a real billed agent run
(minutes each). Run it before a release, or after changing agent bodies,
commands, or model tiers.

```bash
./tests/eval/run-evals.sh              # all cases, sequential
EVAL_PARALLEL=1 ./tests/eval/run-evals.sh   # all cases concurrently — wall-clock ≈ slowest case
./tests/eval/run-evals.sh n-plus-one   # one case
./tests/eval/run-evals.sh --list       # list cases
KEEP_WORKDIR=1 ./tests/eval/run-evals.sh policy   # keep workdir to inspect
```

Parallel mode is safe (every case gets its own throwaway workdir + git repo) but
burstier on API usage; console output prints per case as each finishes.
**Per-case durations from a parallel run are not comparable to sequential
runs** — four concurrent sessions contend for the same API limits and CPU
(run 3 saw n-plus-one go 96s → 619s). Use parallel for pass/fail smoke before
a release; use sequential when the findings doc needs timing numbers.

Results land in `tests/eval/results/<run-id>/` (gitignored): per-case output
log, check results, `git diff` of what the agents changed, and the
`agents-board.jsonl` event stream (per-agent timing).

## Answer key — planted flaws

The fixture is a small blog app. **The flaws are documented here, not in the
fixture**, so agents under evaluation can't read the answer key.

| # | Flaw | Where | Exercised by case |
| - | ---- | ----- | ----------------- |
| 1 | N+1: Blade loop reads `$post->user->name`, `$post->comments->count()`, and latest comment with no eager load | `PostController@index` + `resources/views/posts/index.blade.php` | `n-plus-one` |
| 2 | Missing authorization: any authenticated user can update any post — no Policy, no `authorize()` | `PostController@update` | `policy`, probed again by `tests` |
| 3 | Mass assignment: `Post::$guarded = []` + `$request->all()` into `create()`/`update()` | `Post` model + `PostController` | `policy` / `tests` (surfaced in review output) |
| 4 | Fat controller: `store()` does inline validation, slug generation, mail fan-out, stats bookkeeping, logging | `PostController@store` | `action` |
| 5 | No test coverage on any `posts.*` route (only a trivial `/` smoke test) | `tests/Feature/` | `tests` |
| 6 | Rotten team ledger: a duplicate pair (two UUID-rule entries), a conflict pair (Pest vs PHPUnit), and a stale fact whose `Verify` fails (`app/Services/LegacyPayments.php` doesn't exist) — seeded by the harness, not the fixture | `docs/team/conventions.md` (via `seed_hygiene_fixture`) | `hygiene` |

## Cases

| Case | Command under eval | Passes when |
| ---- | ------------------ | ----------- |
| `n-plus-one` | `/audit-n-plus-one posts.index` | report proposes eager loading + `withCount`, names the file and the `comments` relation |
| `policy` | `/add-policy Post` | `PostPolicy.php` exists, controller calls `authorize`/`can`, update route covered |
| `action` | `/refactor-to-action PostController@store` | an `app/Actions/*.php` exists, controller delegates to it, mail fan-out left the controller, tests touched |
| `tests` | `/add-test PostController` | test files added, update route covered, authorization failure (403) probed |
| `hygiene` | `/team-hygiene` | proposal table classifies the duplicate + conflict, names the stale `LegacyPayments` fact, and applies **nothing** (headless = no approval) |
| `feature` **(opt-in)** | `/make-feature Tag --api` | a tags migration, `Tag` model, registered route and a feature test exist; **the board feed shows ≥2 distinct agents**; the printed board carries a `done when:` completion condition; the coordinator's closing answer carries `VERIFIED`/`NOT-CHECKED`, and it persisted `docs/team/stack.md` + a `docs/delivery/*/log.md` entry (harvest) |

A failing check is **signal, not necessarily a harness bug** — it becomes a
line in the findings doc. Keep checks intent-level (did the flaw get found?)
rather than wording-level, so phrasing changes don't flake.

### The opt-in `feature` case

`feature` is registered but **excluded from the default sweep** — run it by name:

```sh
./tests/eval/run-evals.sh feature
```

It exists because nothing else in the suite proves delegation happened. `policy`
and `action` each ran *both* ways across runs 5 and 6 — one delegating across four
specialists, the other finishing alone on the main thread via the coordinator's
fast path — and the answer key could not tell the difference either time. That
makes the coordinator's own rules (stage budget, `NOT-CHECKED` escalation, resume
state at checkpoints) unmeasurable on a run that happens not to delegate.
`/make-feature` is parallel by construction, so this case always delegates.

Two reasons it stays out of the default sweep:

- **Cost.** `action`, the closest comparable shape, billed $5.16 of run 6's
  $12.50. Adding a second case of that size raises the standing price of every
  sweep by roughly half, for a signal that only changes when coordinator
  behaviour changes.
- **Comparability.** `ALL_CASES` is what the public scorecard's denominator is
  computed from, so leaving it at five keeps runs 1–6 comparable with what
  follows.

Its `check_delegated` assertion is the load-bearing one, and it is negative-
controlled: a stub that scaffolds a *correct* Tag feature entirely inline fails
that check, and also the two harvest checks (harvest is gated on ≥2 specialists,
so an inline run correctly skips both files). The other seven checks pass.

## Rubric judge — `EVAL_JUDGE=1`

The checks above are `grep`. That is cheap and stable, but it is exact-match
scoring of a nondeterministic output, and it fails in both directions:
`check_log 'update'` passes on *any* occurrence of the word, while run 4 froze a
live IDOR into a test the regexes happily accepted.

`EVAL_JUDGE=1` adds a second, outcome-level opinion per case — an LLM scored
against the case's `case_rubric`, which states what a correct run must *achieve*
rather than what it must *say*.

```bash
EVAL_JUDGE=1 ./tests/eval/run-evals.sh                    # all cases + rubric judge
EVAL_JUDGE=1 EVAL_JUDGE_MODEL=claude-opus-5 ./tests/eval/run-evals.sh tests
```

```
   FAIL — 1/4 checks, 0s
   judge: PASS 4/5 — DISAGREES with the regex verdict — unmet: …
```

Rules it plays by:

- **Advisory only.** It never touches the check count, the case verdict, or the
  exit code. Runs stay comparable to earlier ones, and a judge outage cannot
  fail a release.
- **Independent, not anchored.** The judge never sees the regexes or their
  result. The harness compares the two afterwards and marks divergence with
  `!` — a disagreement in *either* direction is the interesting row.
- **Fail-open.** No `python3`, no parsable JSON, or a judge timeout prints one
  line, keeps the raw reply at `<case>.judge.raw.txt`, and moves on.
- **Costs one extra billed call per case**, in a neutral empty workdir so the
  judge reads the evidence bundle rather than the fixture app.

Verdicts land in `<case>.judge.json`, and a `judge` column joins `summary.md`.
Env: `EVAL_JUDGE_MODEL` pins the judge model, `EVAL_JUDGE_TIMEOUT` (default
300s) bounds it.

## Extending

Add a planted flaw to the fixture (no hints in the fixture!), then register a
case: name in `ALL_CASES`, a `case_prompt`/`case_desc`/`case_rubric` entry, and
a `checks_<name>` function in `run-evals.sh`, and a row in both tables above.
A guardrails test asserts every case has a rubric, so the judge can't silently
skip a case you added.
