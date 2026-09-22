# Guild 3.3 workplace loop — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** An opt-in GitHub issue becomes the delivery identity, the kernel records the pull request by re-running `gh`, and a failing check or a confirmed review comment reopens that stage once.

**Architecture:** Extend `scripts/guild-kernel/`. `issue`, `pr`, and `repo` live on the delivery; `reopens` lives on the stage. `runner.capture` returns `(code, stdout)` and is used only by `plan --issue`, `pr`, and `ingest`. `report` still uses `runner.run`. The console posts ingest against the process cwd. Local `/make-feature` without `--issue` is unchanged.

**Tech Stack:** Python 3.10+ stdlib unittest, markdown Interface, Gemini/Codex rebuild, console HTTP + a small React strip. No billed eval.

**Spec:** [docs/plans/2026-09-22-guild-v3-workplace-design.md](2026-09-22-guild-v3-workplace-design.md)

---

## Global constraints

- Branch: `feat/v3.3-workplace` from `main` @ 3.2.0. Do **not** call `move_agent_to_root`.
- Do **not** bump `VERSION` until Task 12.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `$8.50` / `EVAL_TIMEOUT` (1200) / 14.5M.
- Do **not** loosen `check_kernel_state`.
- Do **not** run billed evals.
- Default `/make-feature` stays Supervisor. Adaptive stays opt-in. `--issue` stays opt-in.
- Interface stays **byte-identical** across the nine pipeline commands.
- Coordinator needle `Do not merge.` stays count **1**.
- Nine pipeline commands: `commands/make-feature.md`, `commands/add-test.md`, `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md`.
- Kernel is stdlib only. Fake `capture` in tests. Do not call the network.
- `load()` must `setdefault` `issue` `{}`, `pr` `{}`, `repo` `""` on the delivery, and `reopens` `0` on every stage, before constructing dataclasses. 3.2 files must still load.
- `runner.run` stays `int`. Do not change existing `report` tests to return tuples.
- After Interface + coordinator edits, rebuild Gemini and Codex in the same change.
- Commands stay **16**. Guardrails stay **9**. Agents stay **18**.

### Exact `gh` commands

| Call | Command |
| --- | --- |
| Issue | `gh issue view 42 --json number,title,url` |
| Repo | `gh repo view --json nameWithOwner` |
| PR | `gh pr view 17 --json number,url,state` |
| Checks | `gh pr checks 17 --json name,bucket,link` |
| Review ids | `gh api repos/acme/app/pulls/17/comments --jq .[].id` |

Stdout fixtures:

```json
{"number":42,"title":"Add tags","url":"https://github.com/acme/app/issues/42"}
```

```json
{"nameWithOwner":"acme/app"}
```

```json
{"number":17,"url":"https://github.com/acme/app/pull/17","state":"OPEN"}
```

```json
[{"name":"pint","bucket":"fail","link":"https://github.com/acme/app/runs/1"}]
```

Review stdout is one id per line: `99\n`.

### Exact Interface insertion (Task 9)

After `` Never compose `docs/team/lessons.md` (the kernel renders that view). `` insert:

```
 When the command includes `--issue <n>`, `plan` passes `--issue <n>`. Call `pr --number <n>` once a pull request exists; the kernel re-fetches it. Call `ingest` only for a failing check or a review comment the kernel confirms. Never compose issue or pr fields. A workplace delivery stays running until the recorded PR state is open. Never merge.
```

Needles (count **9**):

- `` `plan` passes `--issue <n>` ``
- `Never merge.`

### Exact coordinator sentence (Task 9)

Append to the Kernel paragraph:

`When --issue is present, pass it to plan. Record the PR with pr. Ingest only a check or comment the kernel confirms. Do not merge.`

Needle (count **1**): `Do not merge.`

---

### Task 1: Workplace fields and close view

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`

**Step 1: Write the failing tests** (class `WorkplaceLoadTest`)

```python
class WorkplaceLoadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_v32_kernel_json_loads_empty_workplace_fields(self):
        folder = self.root / "docs" / "delivery" / "tag"
        folder.mkdir(parents=True)
        folder.joinpath("kernel.json").write_text(
            json.dumps(
                {
                    "name": "tag",
                    "done_when": "POST /api/tags creates a Tag",
                    "cap": 3,
                    "status": "running",
                    "spawns": 0,
                    "sprint": "",
                    "rules_printed": [],
                    "stages": [
                        {
                            "id": "a",
                            "agent": "database-developer",
                            "role": "writer",
                            "success_criteria": ["tags migration exists"],
                            "depends_on": [],
                            "status": "queued",
                            "did": [],
                            "verified": [],
                            "flags": [],
                            "pair": "",
                            "awaiting_pair": False,
                        }
                    ],
                }
            )
        )
        delivery = kernel.load(self.root, "tag")
        self.assertEqual(delivery.issue, {})
        self.assertEqual(delivery.pr, {})
        self.assertEqual(delivery.repo, "")
        self.assertEqual(delivery.stages[0].reopens, 0)

    def test_close_view_appends_issue_and_pr_none(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
        )
        close = (self.root / "docs/delivery/tag/close.md").read_text()
        self.assertIn("\nISSUE: none\n", close)
        self.assertTrue(close.endswith("PR: none\n"))
```

**Step 2: Run to verify fail**

```bash
python3 -m unittest tests.kernel.test_kernel.WorkplaceLoadTest -v
```

Expected: FAIL (`issue` unexpected keyword, or `ISSUE:` missing).

**Step 3: Minimal implementation**

- `StageSpec.reopens: int = 0`.
- `Delivery.issue: dict = field(default_factory=dict)`, `pr: dict = field(default_factory=dict)`, `repo: str = ""`.
- In `load()`, `setdefault` those four keys (`reopens` on each stage).
- `render_close` appends `ISSUE: {url or none}` and `PR: {url or none}` after `BOARD:`.

**Step 4: Run all kernel tests**

```bash
python3 -m unittest tests.kernel.test_kernel
```

Expected: OK.

**Step 5: Commit**

```bash
git commit -m "feat(kernel): workplace fields default empty"
```

---

### Task 2: `plan --issue` stores `gh` output

**Files:**
- Modify: `tests/kernel/test_kernel.py` (`FakeRunner`)
- Modify: `scripts/guild-kernel/kernel.py` (`plan`)

**Step 1: Extend `FakeRunner`**

```python
def __init__(self, codes, captured=None):
    self.codes = codes
    self.captured = captured or {}
    self.calls = []

def capture(self, cwd, cmd):
    self.calls.append((str(cwd), cmd))
    code, out = self.captured[cmd]
    return code, out
```

`run` stays as it is. Existing callers pass only `codes`.

**Step 2: Failing tests** (class `WorkplacePlanTest`)

```python
ISSUE_CMD = "gh issue view 42 --json number,title,url"
ISSUE_OUT = json.dumps(
    {"number": 42, "title": "Add tags", "url": "https://github.com/acme/app/issues/42"}
)

class WorkplacePlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, runner, issue=42):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
            issue=issue,
            runner=runner,
        )

    def test_plan_issue_stores_number_title_url(self):
        runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
        delivery = self._plan(runner)
        self.assertEqual(delivery.issue["number"], 42)
        self.assertEqual(delivery.issue["title"], "Add tags")
        self.assertEqual(delivery.issue["url"], "https://github.com/acme/app/issues/42")
        self.assertEqual(runner.calls, [(str(self.root), ISSUE_CMD)])

    def test_plan_issue_nonzero_gh_writes_no_file(self):
        runner = FakeRunner({}, {ISSUE_CMD: (1, "")})
        with self.assertRaises(kernel.PlanError):
            self._plan(runner)
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_without_issue_does_not_capture(self):
        runner = FakeRunner({})
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
            runner=runner,
        )
        self.assertEqual(runner.calls, [])
```

**Step 3: Run — expect FAIL** (`plan` has no `issue`).

**Step 4: Implement**

- `plan(..., issue=0, runner=None)`.
- When `issue` is 0, ignore `runner` and keep today's body.
- When `issue` is set: require `runner` with `capture`, else `PlanError`. Run the exact command. Non-zero exit or `int(payload["number"]) != int(issue)` raises `PlanError` before `save`. Store `{"number", "title", "url"}` only.
- The existing-file no-op stays first and does not call `capture`.

**Step 5: Units OK. Commit** `feat(kernel): plan stores a GitHub issue`

---

### Task 3: Resume does not refetch

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py` only if Task 2's no-op is not already first

**Step 1: Failing test** on `WorkplacePlanTest`

```python
def test_second_plan_does_not_refetch_or_replace_issue(self):
    runner = FakeRunner({}, {ISSUE_CMD: (0, ISSUE_OUT)})
    self._plan(runner)
    other = "gh issue view 7 --json number,title,url"
    runner.captured[other] = (
        0,
        json.dumps({"number": 7, "title": "Other", "url": "https://example.test/7"}),
    )
    again = kernel.plan(
        root=self.root,
        name="tag",
        done_when="POST /api/tags creates a Tag",
        stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
        issue=7,
        runner=runner,
    )
    self.assertEqual(again.issue["number"], 42)
    self.assertEqual([call[1] for call in runner.calls], [ISSUE_CMD])
```

**Step 2: FAIL** if the no-op calls `capture` or overwrites `issue`.

**Step 3:** Keep the existing-file return before any `gh` call.

**Step 4: Units OK. Commit** `fix(kernel): resume plan does not refetch the issue`

---

### Task 4: Record the pull request

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`

**Step 1: Failing tests** (class `WorkplacePrTest`)

Helper plants an issue via `plan --issue` using Task 2's runner, then:

```python
REPO_CMD = "gh repo view --json nameWithOwner"
PR_CMD = "gh pr view 17 --json number,url,state"

def test_record_pr_stores_open_state_and_repo(self):
    # plan --issue 42 first
    runner.captured[REPO_CMD] = (0, json.dumps({"nameWithOwner": "acme/app"}))
    runner.captured[PR_CMD] = (
        0,
        json.dumps(
            {
                "number": 17,
                "url": "https://github.com/acme/app/pull/17",
                "state": "OPEN",
            }
        ),
    )
    delivery = kernel.record_pr(self.root, "tag", 17, runner)
    self.assertEqual(delivery.repo, "acme/app")
    self.assertEqual(delivery.pr["state"], "open")
    self.assertEqual(delivery.pr["url"], "https://github.com/acme/app/pull/17")
    close = (self.root / "docs/delivery/tag/close.md").read_text()
    self.assertIn("PR: https://github.com/acme/app/pull/17\n", close)

def test_record_pr_without_issue_raises(self):
    kernel.plan(
        root=self.root,
        name="tag",
        done_when="POST /api/tags creates a Tag",
        stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
    )
    runner = FakeRunner({}, {REPO_CMD: (0, "{}"), PR_CMD: (0, "{}")})
    with self.assertRaises(kernel.PlanError):
        kernel.record_pr(self.root, "tag", 17, runner)
    self.assertEqual(kernel.load(self.root, "tag").pr, {})

def test_failed_pr_view_leaves_pr_empty(self):
    # plan --issue 42 first
    runner.captured[REPO_CMD] = (0, json.dumps({"nameWithOwner": "acme/app"}))
    runner.captured[PR_CMD] = (1, "")
    with self.assertRaises(kernel.PlanError):
        kernel.record_pr(self.root, "tag", 17, runner)
    self.assertEqual(kernel.load(self.root, "tag").pr, {})
    self.assertEqual(kernel.load(self.root, "tag").repo, "")
```

**Step 2: FAIL** (`record_pr` missing).

**Step 3: Implement `record_pr(root, name, number, runner)`**

- No `issue` → `PlanError` before any `capture`.
- Capture repo, then PR. Non-zero on either → `PlanError` before `save`.
- Store `repo` and `pr` with `state` lowercased.
- `write_views` so `PR:` updates.
- Do not set `done` in this task.

**Step 4: Units OK. Commit** `feat(kernel): record a pull request from gh`

---

### Task 5: Open PR is the workplace definition of done

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py` (`report`, `record_pr`)

**Step 1: Failing tests**

Use the existing stage-file shape (`STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT`) and `FakeRunner({"php artisan test --filter=TagTest": 0})` the way `LessonTest._report` does.

```python
def test_workplace_stays_running_until_pr_is_open(self):
    # plan --issue 42, one stage, report a passing command
    delivery = kernel.load(self.root, "tag")
    self.assertEqual(delivery.stages[0].status, "done")
    self.assertEqual(delivery.status, "running")
    self.assertEqual(kernel.next_agent(self.root, "tag"), "STOP")

def test_record_pr_promotes_finished_workplace_delivery(self):
    # after the test above, record_pr OPEN
    delivery = kernel.record_pr(self.root, "tag", 17, runner)
    self.assertEqual(delivery.status, "done")

def test_delivery_without_issue_can_finish_with_empty_pr(self):
    # plan without issue, report passing command
    self.assertEqual(kernel.load(self.root, "tag").status, "done")
    self.assertEqual(kernel.load(self.root, "tag").pr, {})
```

**Step 2: FAIL** (workplace delivery becomes `done` with `pr == {}`).

**Step 3: Implement**

- Extract a helper `_dod_met(delivery)` that is true when every stage is `done` or `skipped` and every non-skipped stage has a verified entry with `exit == 0`.
- In `report`, when `_dod_met`: if `delivery.issue` and `delivery.pr.get("state") != "open"`, leave `status` as `running`. Else set `done`. Still `save`.
- In `record_pr`, after storing an `open` PR, if `_dod_met`, set `status` `done`.
- `closed` and `merged` do not promote.

**Step 4: Units OK. Commit** `feat(kernel): workplace done requires an open PR`

---

### Task 6: A failing check reopens once

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`

**Step 1: Failing tests** (class `WorkplaceIngestTest`)

Plant a workplace delivery with stage `a` `done`, `reopens` 0, `issue` set, `pr.number` 17, `repo` `acme/app`, `spawns` equal to `cap`.

```python
CHECKS = "gh pr checks 17 --json name,bucket,link"

def test_failing_check_reopens_once_and_allows_one_spawn(self):
    runner = FakeRunner({}, {CHECKS: (0, json.dumps([
        {"name": "pint", "bucket": "fail", "link": "https://github.com/acme/app/runs/1"}
    ]))})
    delivery = kernel.ingest(
        self.root, "tag", kind="check", stage_id="a", check="pint", runner=runner
    )
    self.assertEqual(delivery.stages[0].status, "running")
    self.assertEqual(delivery.stages[0].reopens, 1)
    self.assertEqual(delivery.status, "running")
    self.assertGreaterEqual(delivery.cap, delivery.spawns + 1)
    self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")

def test_green_check_does_not_write(self):
    before = (self.root / "docs/delivery/tag/kernel.json").read_text()
    runner = FakeRunner({}, {CHECKS: (0, json.dumps([
        {"name": "pint", "bucket": "pass", "link": "https://github.com/acme/app/runs/1"}
    ]))})
    kernel.ingest(self.root, "tag", kind="check", stage_id="a", check="pint", runner=runner)
    self.assertEqual((self.root / "docs/delivery/tag/kernel.json").read_text(), before)

def test_second_check_stops_the_delivery(self):
    # first ingest as above, then ingest again with the same failing payload
    delivery = kernel.ingest(...)
    self.assertEqual(delivery.status, "stopped")
    self.assertEqual(delivery.stages[0].reopens, 1)
    self.assertEqual(kernel.next_agent(self.root, "tag"), "STOP")
```

**Step 2: FAIL** (`ingest` missing).

**Step 3: Implement `ingest` and `_reopen`**

- Require `issue` and `pr.get("number")`, else `PlanError`.
- Unknown stage → `PlanError`.
- Check command is exactly `gh pr checks {number} --json name,bucket,link`.
- Non-zero `gh`, invalid JSON, or missing `name` → `PlanError` before save.
- `bucket != "fail"` → return the loaded delivery and do not `save`.
- `_reopen`: stage status must be `done` on the first call, else `PlanError`. If `reopens >= 1`, set delivery `stopped`, save, return. Else set stage `running`, `reopens = 1`, delivery `running`, `cap = max(cap, spawns + 1)`, save, `write_views`.

**Step 4: Units OK. Commit** `feat(kernel): a failing check reopens one stage`

---

### Task 7: Review comments and ingest rejects

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py` (`ingest`)

**Step 1: Failing tests**

```python
REVIEW = "gh api repos/acme/app/pulls/17/comments --jq .[].id"

def test_review_id_in_stdout_reopens(self):
    runner = FakeRunner({}, {REVIEW: (0, "99\n100\n")})
    delivery = kernel.ingest(
        self.root, "tag", kind="review", stage_id="a", comment="99", runner=runner
    )
    self.assertEqual(delivery.stages[0].status, "running")

def test_missing_review_id_rejects(self):
    runner = FakeRunner({}, {REVIEW: (0, "100\n")})
    with self.assertRaises(kernel.PlanError):
        kernel.ingest(
            self.root, "tag", kind="review", stage_id="a", comment="99", runner=runner
        )
    self.assertEqual(kernel.load(self.root, "tag").stages[0].status, "done")

def test_ingest_without_pr_rejects(self):
    # workplace issue planted, pr still {}
    runner = FakeRunner({})
    with self.assertRaises(kernel.PlanError):
        kernel.ingest(
            self.root, "tag", kind="check", stage_id="a", check="pint", runner=runner
        )
    self.assertEqual(runner.calls, [])
```

**Step 2: FAIL.**

**Step 3:** Review command uses `delivery.repo` and `delivery.pr["number"]`. Split stdout on lines and compare stripped strings. Absent id → `PlanError` before save. Unknown `kind` → `PlanError`.

**Step 4: Units OK. Commit** `feat(kernel): a confirmed review comment reopens one stage`

---

### Task 8: CLI

**Files:**
- Modify: `scripts/guild-kernel/guild.py`
- Modify: `tests/kernel/test_kernel.py` only if a CLI test is cheaper than a manual argv check. Prefer calling `guild.main` with `argv` and a monkeypatched `kernel.plan` / `kernel.record_pr` / `kernel.ingest`.

**Step 1: Failing test**

```python
def test_cli_passes_issue_pr_and_ingest(self):
    # monkeypatch the three kernel functions to record kwargs
    code = guild.main(["plan", "--root", str(root), "--name", "tag",
                       "--done-when", "POST /api/tags creates a Tag",
                       "--stage", "a,database-developer,writer,,m",
                       "--issue", "42"])
    self.assertEqual(code, 0)
    self.assertEqual(seen["issue"], 42)
```

Same shape for `pr --number 17` and `ingest --kind check --stage a --check pint` and `ingest --kind review --stage a --comment 99`.

**Step 2: FAIL** (unknown args).

**Step 3:** Add flags. `plan` passes `issue=int` and `runner=ProcessRunner()` when `--issue` is non-zero. `pr` and `ingest` always pass `ProcessRunner()`. `ProcessRunner.capture` uses `subprocess.run(..., capture_output=True, text=True)` and returns `(returncode, stdout)`. `run` stays unchanged.

**Step 4: Units OK. Commit** `feat(kernel): CLI for issue, pr, and ingest`

---

### Task 9: Interface, coordinator, rebuild

**Files:**
- Modify: the nine pipeline commands (exact insertion above)
- Modify: `agents/delivery-coordinator.md`
- Modify: `tests/guardrails.test.sh`
- Run: `python3 scripts/build-gemini-extension.py` and `python3 scripts/build-codex-extension.py`

**Step 1:** Add guardrail expects, count **9** unless noted:

- Interface contains `` `plan` passes `--issue <n>` ``
- Interface contains `Never merge.`
- Coordinator file contains `Do not merge.` once

Run `tests/guardrails.test.sh`. Expected: FAIL on those three expects.

**Step 2:** Insert the sentence on all nine commands. Append the coordinator sentence once.

**Step 3:** Rebuild Gemini and Codex. Do not hand-edit `gemini/commands/*.toml`.

**Step 4:** `python3 scripts/check_inventory_sync.py` FAILs `coordinator_hash`. Update `tests/eval/baseline.json` `sha256` to the printed hash, `as_of` `2026-09-22`, note: `Pinned after 3.3 workplace Interface. No billed pin. Do not raise ceilings.` `waivers: []`.

**Step 5: Commit** `feat: Interface carries the workplace loop`

---

### Task 10: Console board and ingest

**Files:**
- Modify: `scripts/console/server.py` (`make_server` gains keyword-only `kernel_cli=None`)
- Modify: `tests/console/test_server.py`
- Modify: `console-ui/src/lib/api.ts`
- Create: `console-ui/src/components/KernelStrip.tsx`
- Create: `console-ui/src/components/KernelStrip.test.tsx`
- Modify: `console-ui/src/App.tsx` to render the strip

**Step 1: Failing server test** on a second `make_server` bound to port 0 (do not reuse the class-level server; it has no `kernel_cli`).

```python
def test_ingest_uses_server_root_and_rejects_a_bad_kind(self):
    calls = []

    def kernel_cli(argv):
        calls.append(argv)
        return 0, "ok"

    httpd = server.make_server(
        "127.0.0.1", 0, TOKEN, FakeManager(), REPO, dist, kernel_cli=kernel_cli
    )
    # POST /api/kernel/ingest {"name":"tag","kind":"nope","stage":"a"} → 400, calls empty
    # POST {"name":"tag","kind":"check","stage":"a","check":"pint","root":"/tmp/evil"} → 200
    # argv contains "--root" equal to the server cwd, never "/tmp/evil"
    # argv contains "ingest", "--name", "tag", "--kind", "check", "--stage", "a", "--check", "pint"
```

Also `GET /api/kernel/board?name=tag` returns the stdout of `kernel_cli(["board", ...])`. Missing token stays 401.

**Step 2: FAIL** (404).

**Step 3: Implement**

- Name matches `^[A-Za-z0-9][A-Za-z0-9_-]*$`. Kind is `check` or `review`. Stage matches the same name pattern. `check` kind requires `check`. `review` kind requires `comment`.
- Root is `os.getcwd()`, never the body.
- Default `kernel_cli` subprocesses `python3 scripts/guild-kernel/guild.py` with that argv and returns `(code, stdout+stderr)`.
- Non-zero → 400 `{"error": <text>}`. Zero → 200 `{"ok": true, "text": <stdout>}`.
- `KernelStrip` has a delivery name field, a Show button, the returned board text, a stage field, a check name, a comment id, and two buttons. Check posts `{name, kind:"check", stage, check}`. Review posts `{name, kind:"review", stage, comment}`.
- Vitest: click check and assert `fetch` was called with that JSON. Follow `ShowHeader.test.tsx`.

**Step 4:** `python3 -m unittest tests.console.test_server` and `cd console-ui && npm test -- --run KernelStrip`.

**Step 5: Commit** `feat(console): post a kernel ingest`

---

### Task 11: Rebuild the console bundle

**Files:** `scripts/console/dist/**` (generated)

```bash
cd console-ui && npm run build
git diff --exit-code -- scripts/console/dist
```

Expected after the build: the diff is empty because the new bundle is staged. If the build changes `dist`, commit it.

```bash
git commit -m "build(console-ui): rebuild the bundle for kernel ingest"
```

If `dist` does not change, do not empty-commit.

---

### Task 12: Version 3.3.0

Do this only after Tasks 1–11 are green:

```bash
python3 -m unittest tests.kernel.test_kernel tests.console.test_server
tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

**Files:** `VERSION`, the five manifests listed as `VERSIONED` in `scripts/check_inventory_sync.py`, `CHANGELOG.md` (`[Unreleased]` → `[3.3.0] - 2026-09-22`), `docs/README.md`, `docs/onboarding.md` last-verified line. Rebuild Gemini so `gemini/gemini-extension.json` picks up `VERSION`.

Changelog note, one paragraph: opt-in `--issue`, recorded PR, one reopen from a failing check or a confirmed review, console strip posts ingest, merge stays human.

**Commit** `chore: release 3.3.0`

---

## Non-goals during execution

- Do not parse issue bodies into stages.
- Do not add `gh pr create` or `gh pr merge`.
- Do not poll GitHub.
- Do not add a tenth guardrail.
- Do not enable Agent Teams or worktrees.
- Do not run `tests/eval/run-evals.sh`.
