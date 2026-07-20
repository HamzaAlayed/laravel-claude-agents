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
./tests/eval/run-evals.sh              # all cases
./tests/eval/run-evals.sh n-plus-one   # one case
./tests/eval/run-evals.sh --list       # list cases
KEEP_WORKDIR=1 ./tests/eval/run-evals.sh policy   # keep workdir to inspect
```

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

## Cases

| Case | Command under eval | Passes when |
| ---- | ------------------ | ----------- |
| `n-plus-one` | `/audit-n-plus-one posts.index` | report proposes eager loading + `withCount`, names the file and the `comments` relation |
| `policy` | `/add-policy Post` | `PostPolicy.php` exists, controller calls `authorize`/`can`, update route covered |
| `action` | `/refactor-to-action PostController@store` | an `app/Actions/*.php` exists, controller delegates to it, mail fan-out left the controller, tests touched |
| `tests` | `/add-test PostController` | test files added, update route covered, authorization failure (403) probed |

A failing check is **signal, not necessarily a harness bug** — it becomes a
line in the findings doc. Keep checks intent-level (did the flaw get found?)
rather than wording-level, so phrasing changes don't flake.

## Extending

Add a planted flaw to the fixture (no hints in the fixture!), then register a
case: name in `ALL_CASES`, a `case_prompt`/`case_desc` entry, and a
`checks_<name>` function in `run-evals.sh`, and a row in both tables above.
