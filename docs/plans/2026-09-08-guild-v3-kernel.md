# Guild 3.0 kernel + Laravel truth — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A pack-local Python kernel owns join, skip, cap, resume, and `VERIFIED` as a command that exited 0. The coordinator Supervises; it does not invent `✔`.

**Architecture:** Stdlib Python under `scripts/guild-kernel/`. State is `docs/delivery/<name>/kernel.json`. `close.md` and `graph.md` are kernel-rendered views. Nine pipeline commands share a thinner byte-identical Interface: call the kernel, Agent whom `next` names, `report` the stage file. Eval’s billed `feature` gate adds `check_kernel_state` and keeps Tag Pest/HTTP checks.

**Tech Stack:** Python 3.10+ (stdlib unittest), bash PreToolUse hook, markdown Interface, Gemini/Codex rebuild, billed `claude -p` pin.

**Spec:** [docs/plans/2026-09-08-guild-v3-kernel-design.md](2026-09-08-guild-v3-kernel-design.md)

---

## Global constraints

- Branch: `feat/v3-kernel`. Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/v3-kernel`. Already created from `main` @ `cdfabae` / **2.3.0**. Do **not** reuse `v221-adaptive-persist`. Do **not** call `move_agent_to_root`.
- Do **not** bump `VERSION` until Task 13 PASS.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `$8.50` / `EVAL_TIMEOUT` (1200) / 14.5M.
- Do **not** grep `stream.jsonl` inside any `checks_*` body (comments count).
- Billed evals **only** when the user says **run it**.
- Default `/make-feature` stays Supervisor. Adaptive stays opt-in.
- Interface stays **byte-identical** across the nine pipeline commands (new text, still one unique blockquote).
- Coordinator `grep -c` needles for **new** clauses stay **exactly 1**.
- Nine pipeline commands: `commands/make-feature.md`, `commands/add-test.md`, `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md`.
- Kernel is stdlib only. Fake the process runner in tests; never hit a real artisan in units.
- Do not implement 3.1 / 3.2 / 3.3 in this plan.
- After Interface + coordinator edits, rebuild Gemini and Codex in the same change.

### Exact new Interface (Task 7)

Replace the entire `> **Interface:**` blockquote (one line) with this blockquote (one line, still starting `> **Interface:**`):

```
> **Interface:** Call `python3 scripts/guild-kernel/guild.py` for this delivery — `plan` before any Agent, `next` to choose whom to Agent, `report` on `docs/delivery/<name>/stages/<agent>.md` after each return, `board` to print `✔ done / ▶ running / · queued / ✖ failed`. Never invent a checkmark; never compose `docs/delivery/<name>/close.md` (the kernel renders that view). Writers Write the six fields `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines) as their last act; never write a writer's stage file for them. Read-only specialists — persist their stage file from the report you already file, then `report`. `VERIFIED:` lines are shell commands the kernel re-runs; prose is a reject. `NOT-CHECKED:` that names a stage success criterion is a reject. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, persist `docs/delivery/<name>/stages/peer-router.md` and `report` it; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.
```

Ratchets that grepped v2 encyclopedia phrases (`reprint the board from disk`, `overwrite close.md after every stage`, `copy skills/delivery-templates/close.md`, `Do not Agent a skipped writer`, graph stub byte copy, …) must be **rewritten** in Task 8 to kernel-contract phrases. Do not leave failing v2 greps.

Interface needles (count **9**):

- `Call \`python3 scripts/guild-kernel/guild.py\``
- `Never invent a checkmark`
- `never compose \`docs/delivery/<name>/close.md\``
- `VERIFIED:` lines are shell commands the kernel re-runs
- harvest clause unchanged: `Once ≥2 specialists have reported, this delivery harvests too`
- `You do not build and you do not patch`

### Exact coordinator Kernel paragraph (Task 7)

Replace Close file / Resume / Graph / Spawn cap prompt-procedure with one **Kernel** section that says:

`**Kernel** — before any Agent, run \`python3 scripts/guild-kernel/guild.py plan --root . --name <name> ...\`. Agent only the type \`next\` prints. After each return, \`report\` the stage path. Print \`board\`. Do not Write close.md; the kernel renders it. Do not Agent a type \`next\` did not return.`

Needle (count **1**): `Do not Write close.md; the kernel renders it`

Keep: never writes a writer stage file; copy stage-return stub when persisting read-only; Adaptive paragraph can stay if it still matches the Interface Adaptive sentence (count **1** each existing adaptive needle, or drop coordinator duplicates that the Interface already carries — prefer drop coordinator copies of Adaptive/Graph that would exceed line budget). Raise `scripts/body_budget.json` delivery-coordinator **only** if a cap exceeds; do not full `--reseed`.

---

### Task 1: Failing kernel tests — plan and next

**Files:**
- Create: `tests/kernel/test_kernel.py`
- Create: `scripts/guild-kernel/__init__.py` (empty)
- Create: `scripts/guild-kernel/kernel.py` (minimal stubs that fail the tests)

**Step 1: Write the failing test**

```python
import pathlib
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "guild-kernel"))

import kernel  # noqa: E402


class PlanNextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_writes_kernel_json_and_cap_is_n_plus_2(self):
        d = kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["tags migration exists"], []),
                kernel.StageSpec("b", "backend-developer", "writer", ["Tag HTTP"], ["a"]),
            ],
        )
        self.assertEqual(d.cap, 4)
        self.assertEqual(d.status, "running")
        self.assertTrue((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_next_is_first_stage_with_deps_met(self):
        kernel.plan(
            root=self.root,
            name="tag",
            done_when="POST /api/tags creates a Tag",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["m"], []),
                kernel.StageSpec("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        )
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")

    def test_next_does_not_name_dependent_before_upstream_done(self):
        d = kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[
                kernel.StageSpec("a", "database-developer", "writer", ["m"], []),
                kernel.StageSpec("b", "backend-developer", "writer", ["h"], ["a"]),
            ],
        )
        d.stages[0].status = "running"
        kernel.save(self.root, d)
        self.assertEqual(kernel.next_agent(self.root, "tag"), "database-developer")
        self.assertNotEqual(kernel.next_agent(self.root, "tag"), "backend-developer")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests/kernel -t tests/kernel -v`

Expected: FAIL (`No module named kernel` or `plan` missing)

**Step 3: Minimal `kernel.py` so plan/next pass** — dataclass `StageSpec`, `Delivery`, `plan` writes JSON, `next_agent` returns first `queued` whose `depends_on` are all `done` or `skipped`, else `STOP`.

**Step 4: Re-run units — PASS**

**Step 5: Commit** `feat(kernel): plan and next own the board order`

---

### Task 2: Command-backed VERIFIED

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`

**Step 1: Failing tests**

```python
class FakeRunner:
    def __init__(self, codes):
        self.codes = codes
        self.calls = []

    def run(self, cwd, cmd):
        self.calls.append((str(cwd), cmd))
        return self.codes[cmd]


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan_one(self):
        return kernel.plan(
            root=self.root,
            name="tag",
            done_when="x",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["tags migration exists"], [])],
        )

    def test_prose_verified_is_rejected(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: the model looks right\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        with self.assertRaises(kernel.ReportError):
            kernel.report(self.root, "tag", p, runner=FakeRunner({}))

    def test_command_exit_nonzero_is_rejected(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner({"php artisan test --filter=TagTest": 1})
        with self.assertRaises(kernel.ReportError):
            kernel.report(self.root, "tag", p, runner=runner)

    def test_command_exit_zero_marks_done(self):
        self._plan_one()
        p = self.root / "docs/delivery/tag/stages/database-developer.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\nVERIFIED: php artisan test --filter=TagTest\n"
            "NOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"
        )
        runner = FakeRunner({"php artisan test --filter=TagTest": 0})
        d = kernel.report(self.root, "tag", p, runner=runner)
        self.assertEqual(d.stages[0].status, "done")
        self.assertEqual(runner.calls[0][1], "php artisan test --filter=TagTest")
```

**Step 2:** Run — FAIL

**Step 3:** `report` parses six labels; each `VERIFIED:` line after the colon is a command (strip a trailing ` → …` if present). Empty / non-command (no space-separated token that is not only words like `the model looks right` — **rule:** a command must contain a path separator, `artisan`, `vendor/bin`, `php`, `pint`, `phpstan`, `pest`, or `./`) → `ReportError`. Re-run via `runner.run(root, cmd)`. Exit 0 → `done` and increment `spawns` once per first `report` of that agent.

**Step 4:** PASS

**Step 5: Commit** `feat(kernel): VERIFIED is a command exit code`

---

### Task 3: NOT-CHECKED, skip, cap

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`

**Tests (fail first):**

1. `NOT-CHECKED:` containing the string `tags migration exists` (a success criterion) → `ReportError`; status not `done`.
2. Writer `done` with `DID:` path still on disk → `next_agent` skips that type (return the next eligible).
3. Writer `done` but `DID:` path missing → do not skip; `next_agent` returns that writer.
4. `spawns == cap` and `done_when` unmet → `status` is `stopped`; `next_agent` is `STOP`.
5. `plan` on existing `running` kernel.json is a no-op (does not reset `spawns`).

**Implement. Commit** `feat(kernel): skip, cap, and load-bearing NOT-CHECKED`

---

### Task 4: close.md and graph.md views + CLI

**Files:**
- Create: `scripts/guild-kernel/guild.py`
- Modify: `scripts/guild-kernel/kernel.py`
- Modify: `tests/kernel/test_kernel.py`

`report` and `plan` write `docs/delivery/<name>/close.md` helper shape (`VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:`) and `graph.md` helper shape (`NODES:` / `EDGES:` / `PARALLEL:` / `ON-FAIL:`). Test the four close labels and registered `NODES:`.

`guild.py` argparse: `plan|next|report|board|status` with `--root` `--name`. `next` prints the agent type or `STOP` on stdout.

```bash
python3 scripts/guild-kernel/guild.py next --root "$TMP" --name tag
```

**Commit** `feat(kernel): render close.md and a CLI`

---

### Task 5: Stage-return hook

**Files:**
- Create: `scripts/enforce-stage-return.sh` (clone `enforce-close-file.sh`; path `docs/delivery/.+/stages/.+\.md`; require `^STATUS:`, `^DID:`, `^VERIFIED:`, `^NOT-CHECKED:`, `^FLAGS:`, `^NEXT:`; deny Bash writes of that path)
- Modify: `hooks/hooks.json` — add the script on Write|Edit and Bash matchers next to close-file
- Modify: `tests/guardrails.test.sh` — copy close-file cases for stage returns
- Modify: Codex hook generator / `install.sh` / README guardrail list **in the same change** so inventory stays GREEN (7 production guardrails)

**Commit** `feat(hooks): bounce non-helper stage returns`

---

### Task 6: Kernel units in CI

**Files:**
- Modify: `.github/workflows/ci.yml` — job `kernel-python` mirroring `console-python`:

```yaml
  kernel-python:
    name: guild kernel units
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Run guild-kernel unit tests (stdlib unittest)
        run: python3 -m unittest discover -s tests/kernel -t tests/kernel -v
```

**Commit** `ci: run guild-kernel units`

---

### Task 7: Thin Interface + coordinator

**Files:**
- Modify: all nine `commands/*.md` listed above — replace Interface blockquote with the Exact new Interface
- Modify: `agents/delivery-coordinator.md` — Kernel paragraph; drop Close-file compose / Resume encyclopedia that the kernel now owns
- Modify: `scripts/body_budget.json` only if coordinator lines exceed cap

**Verify:** `python3 scripts/check_body_budget.py` PASS

**Commit** `feat: thin Interface calls the kernel`

---

### Task 8: Rewrite guardrail Interface ratchets

**Files:**
- Modify: `tests/guardrails.test.sh` — every `expect` that greps a removed v2 phrase must grep the new Interface/coordinator needles (count **9** / **1**). Keep harvest, don’t-build, read-only persist, Adaptive opt-in, packet needles that still exist in the new Interface. Delete expects whose phrases are gone.

**Run:** `./tests/guardrails.test.sh` — ALL GREEN

**Commit** `test(guardrails): ratchet the kernel Interface`

---

### Task 9: `check_kernel_state` + Gemini/Codex rebuild

**Files:**
- Modify: `tests/eval/run-evals.sh` — helper reads `docs/delivery/tag/kernel.json` (or any `docs/delivery/*/kernel.json`). PASS when file exists, `status` is `running|done|stopped`, and every `stages[].status == done` has a `verified` command with `exit` 0. Never open the raw transcript. Add `check_kernel_state` to `checks_feature` (so adaptive/resume inherit it).
- Modify: inventory/eval-check tally if the audit sentence needs a +1 (update `docs/evals/2026-08-06-check-audit.md` tally **only** if that file is still the bound claim — prefer adding a line to `scripts/check_inventory_sync.py` CLAIMS if required)
- Run: `python3 scripts/build-gemini-extension.py` and the Codex generator (same commands the resume slice used)
- Run: `python3 scripts/check_inventory_sync.py`

**Commit** `feat(eval): score kernel.json; rebuild Gemini and Codex`

---

### Task 10: Unreleased docs

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]` — user-facing: kernel owns the board; `VERIFIED` is a command exit 0; re-install for 3.0. Do **not** retitle to `[3.0.0]`.
- `docs/README.md` Open row already cites the design; leave it until the pin.

**Commit** `docs: Unreleased 3.0 kernel`

---

### Task 11: Local verify

Run (no billed):

```bash
python3 -m unittest discover -s tests/kernel -t tests/kernel -v
python3 -m unittest discover -s tests/console -t tests/console -v
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
python3 scripts/check_body_budget.py
```

Expected: all PASS / GREEN. Fix anything red before asking for **run it**.

**Commit** only if a fix was needed.

---

### Task 12: Inventory claims for seven guardrails

If Task 5 added a hook, README + four manifests + gemini/codex copy must say **seven** guardrails (was six). Same commit as Task 5 if you notice during Task 5; otherwise this task.

---

### Task 13: Billed `feature` pin

**Do not start until the user says `run it`.**

```bash
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature
```

- Same ceilings. `waivers: []`. Pin `coordinator_hash`.
- Receipt `docs/evals/2026-09-08-run-27.md` (or next free run id).
- PASS → bump `VERSION` and the five manifests to **3.0.0**, retitle CHANGELOG `[3.0.0]`, close the Open row.
- FAIL → pin hash, stay **2.3.0** / Unreleased. Do not loosen `check_kernel_state`.

---
