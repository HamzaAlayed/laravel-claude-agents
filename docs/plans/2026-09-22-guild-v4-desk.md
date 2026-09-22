# Guild 4.0 console desk — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `/console` opens on a delivery desk that can start a `make-feature` run and watch one pull request at a time.

**Architecture:** Extend `scripts/guild-kernel/` with `seen_checks`, `seen_comments`, and `watch_once` (one event per call). The console server lists `kernel.json` files under its cwd and keeps the watch set in memory. The React desk replaces the idle call sheet. The floor and spotlight stay.

**Tech Stack:** Python 3.10+ stdlib unittest, the existing console HTTP server, Vitest, Vite bundle. No billed eval.

**Spec:** [docs/plans/2026-09-22-guild-v4-desk-design.md](2026-09-22-guild-v4-desk-design.md)

---

## Global constraints

- Branch: `feat/v4-desk` from `main` @ 3.3.0. Worktree: `.claude/worktrees/v4-desk` (that directory is gitignored). Do **not** call `move_agent_to_root`.
- Do **not** bump `VERSION` until Task 12.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `$8.50` / `EVAL_TIMEOUT` (1200) / 14.5M.
- Do **not** run billed evals.
- Default `/make-feature` stays Supervisor. `--issue` stays opt-in.
- Watch is off until a POST enables one name. One `watch_once` call applies at most one reopen.
- The browser cannot choose `--root` or a `gh` command. Root is `os.getcwd()`.
- Do not add `gh pr create` or `gh pr merge`.
- Agents **18**. Commands **16**. Guardrails **9**.
- `load()` must `setdefault` `seen_checks` `[]` and `seen_comments` `[]` so 3.3 files still load.

---

### Task 1: Seen-event fields

**Files:** `tests/kernel/test_kernel.py`, `scripts/guild-kernel/kernel.py`

**Step 1: Failing test** on a new `DeskLoadTest`. Write a 3.3-shaped `kernel.json` (the same keys as `WorkplaceLoadTest`, no `seen_*`). `load` returns `seen_checks == []` and `seen_comments == []`.

**Step 2:** `python3 -m unittest tests.kernel.test_kernel.DeskLoadTest -v` fails.

**Step 3:** `Delivery.seen_checks` and `seen_comments` default to empty lists. `load()` `setdefault`s both before constructing `Delivery`.

**Step 4:** Full `python3 -m unittest tests.kernel.test_kernel` OK.

**Step 5: Commit** `feat(kernel): remember seen checks and comments`

---

### Task 2: `watch_once` reopens one failing check

**Files:** `tests/kernel/test_kernel.py`, `scripts/guild-kernel/kernel.py`

Plant a workplace delivery the way `WorkplaceIngestTest` does: issue 42, stage `a` / `database-developer` done, PR 17, repo `acme/app`, state open.

`watch_once(root, name, runner)`:

- No `pr.number`: return `{"action": "skip"}` and do not call `capture`.
- Command for checks is exactly `gh pr checks 17 --json name,bucket,link`.
- First failing check name not in `seen_checks` reopens the last done writer (here `a`) via the existing `_reopen` rules, then appends that name to `seen_checks` and saves.
- A green board returns `{"action": "noop"}` and does not save.
- While stage `a` is `running`, return `{"action": "wait"}` and do not call `capture`.
- After the stage is `done` again, a new failing check name stops the delivery (`reopens` already 1) and returns `{"action": "stopped"}`.

Tests: `test_watch_skips_without_pr`, `test_watch_reopens_one_failing_check`, `test_watch_green_does_not_save`, `test_watch_waits_while_stage_running`, `test_watch_second_failure_stops`.

TDD, then full kernel suite.

**Commit** `feat(kernel): watch_once reopens one failing check`

---

### Task 3: Review comments lose to a failing check

**Files:** same as Task 2.

When checks contain an unseen failure, do not call the review API. When every check is passing or already seen, run exactly `gh api repos/acme/app/pulls/17/comments --jq .[].id`. The first unseen id reopens and is appended to `seen_comments`. An id already stored does not reopen. Unsafe `repo` or a non-int PR number raises `PlanError` before `capture` (same rules as `ingest`).

Tests: `test_failing_check_skips_review_api`, `test_new_comment_reopens_when_checks_pass`, `test_seen_comment_does_not_reopen`.

**Commit** `feat(kernel): watch_once applies one new review comment`

---

### Task 4: List deliveries

**Files:** `scripts/console/server.py`, `tests/console/test_server.py`

`GET /api/kernel/deliveries` behind `_guard`. Scan `os.getcwd()/docs/delivery`. Skip names that fail `KERNEL_NAME`. Skip unreadable JSON. Return `{"deliveries": [{name, status, done_when, issue_url, pr_url, pr_state, board}]}`. `board` is `kernel.board_line` of the loaded delivery. Ignore a `root` query param.

Test on a second server whose cwd is a temp dir (pass cwd into `make_server` as keyword-only `kernel_root=None`, default `os.getcwd()`). Plant two folders: a valid `tag/kernel.json` and a `../evil` or `bad name` directory that must not appear. Assert the valid row and that the evil name is absent.

Do not change the existing board or ingest routes.

**Commit** `feat(console): list kernel deliveries`

---

### Task 5: Watch toggle and one tick

**Files:** `scripts/console/server.py`, `tests/console/test_server.py`

`POST /api/kernel/watch` body `{name, enabled}`. Ignore `root`.

- `enabled: true` loads that delivery from `kernel_root`. Missing file or no `pr.number` → 400 and the name is not stored.
- `enabled: false` removes the name. 200.
- `GET /api/kernel/deliveries` includes `watching: true|false`.

Inject keyword-only `watch_once=None`. A test calls the server's `tick_watches()` (a method on the handler's closure, exposed on the server object). It invokes `watch_once(root, name)` only for enabled names. When `watch_once` returns `{"action": "stopped"}`, the name is removed. Do not `time.sleep(60)` in the test. The 60 second thread is started from `serve.py` only, and a unit test asserts the thread target is `tick_watches` without waiting for it.

**Commit** `feat(console): toggle watch for one delivery`

---

### Task 6: Desk scene

**Files:** `console-ui/src/lib/scene.ts`, `console-ui/src/lib/scene.test.ts` (create if missing), `console-ui/src/App.tsx`

`sceneOf` returns `"desk"` when no run is active and the run is not recorded. Recorded runs stay `"floor"`. A live run stays `"floor"` or `"spotlight"`.

Add `"desk"` to the `Scene` union. App renders a new `Desk` when the scene is `desk`. The launcher renders when local state `composing` is true, with a way back to the desk. Remove `<KernelStrip />` from the call sheet.

Update any scene test that expected `"call"` for an idle console.

**Commit** `feat(console): idle scene is the delivery desk`

---

### Task 7: Desk list, run, and watch

**Files:** `console-ui/src/components/Desk.tsx`, `console-ui/src/components/Desk.test.tsx`, `console-ui/src/lib/api.ts`, `console-ui/src/App.tsx`

`api.listDeliveries()`, `api.setWatch(name, enabled)`.

Desk shows one row per delivery: name, status, issue url, PR url, board line. Empty list says there are no deliveries and offers New run.

Run on a row calls `onLaunch` with `{kind: "command", target: "make-feature", text: "<name> --issue <n>", mode: "default"}` when `issue_number` is present, otherwise text is just the name. The list payload includes `issue_number` (number or null). The POST body has no `root`.

Watch calls `setWatch(name, true)`. The button is disabled when `pr_url` is empty.

Vitest mocks `fetch`. Assert the Run payload and that Watch is disabled without a PR.

**Commit** `feat(console): run and watch a delivery from the desk`

---

### Task 8: Rebuild the bundle

```bash
cd console-ui && npm test -- --run Desk scene KernelStrip
cd console-ui && npm run build
```

Commit a type-only test fix first if `tsc` fails. Commit dist only when it changes: `build(console-ui): rebuild the bundle for the delivery desk`.

---

### Task 9: Version 4.0.0

Gates first:

```bash
python3 -m unittest tests.kernel.test_kernel tests.console.test_server
tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

Stop if any fail. Then bump `VERSION` and every `VERSIONED` manifest to `4.0.0`. Changelog `[4.0.0] - 2026-09-22`: the console opens on a delivery desk; Run starts `/make-feature`; Watch reopens one stage from a failing check or a new review comment; the floor stays the live run; merge stays a person.

Rebuild Gemini. Inventory must be ok.

**Commit** `chore: release 4.0.0`

---

## Non-goals during execution

- Do not poll deliveries that were not toggled on.
- Do not open or merge a pull request.
- Do not delete the launcher, the floor, or the spotlight.
- Do not add a slash command.
- Do not run `tests/eval/run-evals.sh`.
