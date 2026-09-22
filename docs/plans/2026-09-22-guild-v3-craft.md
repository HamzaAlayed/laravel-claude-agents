# Guild 3.2 craft layer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A repeated `FLAGS` line becomes a taught lesson the next `plan` prints, `/pair` holds one stage until a reviewer command exits 0, and opt-in `feature-replay` can prove a planted violation did not recur.

**Architecture:** Extend `scripts/guild-kernel/`. Lessons live in `docs/team/lessons.json`; `lessons.md` is a view. `plan` stores `rules_printed` and the CLI prints `RULES:`. `/pair` sets a reviewer on one stage; `next` returns that reviewer while the writer lane stays `▶`. Replay is an opt-in eval, not a ship gate.

**Tech Stack:** Python 3.10+ stdlib unittest, bash PreToolUse hook, markdown Interface, Gemini/Codex rebuild. No billed eval.

**Spec:** [docs/plans/2026-09-22-guild-v3-craft-design.md](2026-09-22-guild-v3-craft-design.md)

---

## Global constraints

- Branch: `feat/v3.2-craft` (from `main` @ 3.1.0). Do **not** call `move_agent_to_root`.
- Do **not** bump `VERSION` until Task 13.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `$8.50` / `EVAL_TIMEOUT` (1200) / 14.5M.
- Do **not** loosen `check_kernel_state`.
- Do **not** run billed evals.
- Default `/make-feature` stays Supervisor. Adaptive stays opt-in.
- `/pair` is **not** a pipeline command and must **not** carry the Interface blockquote (keep the "9" grep).
- Interface stays **byte-identical** across the nine pipeline commands.
- Coordinator `grep -c` needles for **new** clauses stay **exactly 1**.
- Nine pipeline commands: `commands/make-feature.md`, `commands/add-test.md`, `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md`.
- `kernel.plan` stores `rules_printed` and does **not** print. `guild.py plan` prints those lines to stdout. Library prints would flood unittest.
- `load()` must `setdefault` `flags` `[]`, `pair` `""`, `awaiting_pair` false on every stage, and `rules_printed` `[]` on the delivery, before constructing dataclasses. 3.1 files must still load.
- Registered reviewers are the 18 stems in `agents/*.md`: `backend-developer`, `business-analyst`, `database-developer`, `delivery-coordinator`, `devops-engineer`, `frontend-developer`, `mobile-developer`, `package-developer`, `peer-router`, `performance-engineer`, `product-owner`, `qa-engineer`, `scrum-master`, `security-engineer`, `solution-architect`, `tech-lead`, `technical-writer`, `ui-ux-designer`.

### Exact Interface insertion (Task 9)

After `Never compose \`docs/sprints/<id>/sprint.md\` (the kernel renders that view).` insert:

```
 `plan` prints `RULES:` for taught lessons; brief every `RULES:` line. Never compose `docs/team/lessons.md` (the kernel renders that view).
```

Needles (count **9**):

- `` `plan` prints `RULES:` ``
- `` Never compose `docs/team/lessons.md` ``

### Exact coordinator sentence (Task 9)

Append to the Kernel paragraph:

`Brief every RULES: line plan printed. Do not Write lessons.md; the kernel renders it.`

Needle (count **1**): `Do not Write lessons.md; the kernel renders it`

---

### Task 1: Store a first flag as `seen`

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`

**Step 1: Write the failing tests** (class `LessonTest`)

```python
class LessonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, name, agent, flags):
        kernel.plan(
            root=self.root,
            name=name,
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", agent, "writer", ["m"], [])],
        )
        path = self.root / f"docs/delivery/{name}/stages/{agent}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "STATUS: done\nDID: app/Models/Tag.php\n"
            "VERIFIED: php artisan test --filter=TagTest\n"
            f"NOT-CHECKED: none\nFLAGS: {flags}\nNEXT: none\n"
        )
        return kernel.report(
            self.root,
            name,
            path,
            runner=FakeRunner({"php artisan test --filter=TagTest": 0}),
        )

    def test_none_flag_writes_no_lesson(self):
        self._report("tag", "database-developer", "none")
        self.assertFalse((self.root / "docs/team/lessons.json").is_file())

    def test_first_flag_is_seen_and_plan_prints_no_rule(self):
        self._report("tag", "database-developer", "Do not call Model::all()")
        lessons = json.loads((self.root / "docs/team/lessons.json").read_text())
        self.assertEqual(lessons["lessons"][0]["status"], "seen")
        self.assertEqual(lessons["lessons"][0]["deliveries"], ["tag"])
        again = kernel.plan(
            root=self.root,
            name="other",
            done_when="POST /api/tags creates a Tag",
            stages=[kernel.StageSpec("a", "database-developer", "writer", ["m"], [])],
        )
        self.assertEqual(again.rules_printed, [])
```

**Step 2: Run to verify fail**

```bash
python3 -m unittest tests.kernel.test_kernel.LessonTest -v
```

Expected: FAIL (`lessons.json` missing or `rules_printed` missing).

**Step 3: Minimal implementation**

- `StageSpec.flags: list = field(default_factory=list)`.
- `Delivery.rules_printed: list = field(default_factory=list)`.
- In `load()`, `setdefault` the new keys.
- `_norm_flag`: `" ".join(text.strip().lower().split())`. Ignore `""` and `"none"`.
- On a successful `report`, store real flag strings on the matched stage.
- `_record_lesson(root, delivery_name, agent, text)`: load or create `docs/team/lessons.json` `{"lessons": []}`. Match on `norm`. First sight appends `status=seen`, `scope=[agent]`, `deliveries=[name]`, `text` = original wording. Same delivery again does not promote.
- `plan` sets `rules_printed` to taught lesson texts whose `scope` intersects stage agents. Taught-only. Do not print from `plan()`.

**Step 4: Run all kernel tests**

```bash
python3 -m unittest tests.kernel.test_kernel
```

Expected: OK.

**Step 5: Commit**

```bash
git commit -m "feat(kernel): record a first flag as seen"
```

---

### Task 2: Second delivery teaches, view, CLI prints `RULES:`

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`
- Modify: `scripts/guild-kernel/guild.py`

**Step 1: Failing tests**

- After Task 1's first report, `_report("post", "backend-developer", "Do not call Model::all()")` promotes `status` to `taught`, `scope` contains both agents, `deliveries` is `["tag", "post"]`.
- `docs/team/lessons.md` contains lines starting `LESSONS:`, `RULE:`, `SCOPE:`, `STATUS:`.
- A third `plan` for `database-developer` has `rules_printed == ["Do not call Model::all()"]`.
- Same delivery reporting the same flag twice stays `seen` (call `_record_lesson` twice on `tag` only — cover with a direct second report on a fresh stage file after resetting, or report two stages in one delivery).
- CLI: `plan` stdout is `RULES: none` when nothing is taught, and `RULES: Do not call Model::all()` after the lesson is taught. No traceback.

**Step 2: FAIL** (`taught` missing or CLI prints nothing).

**Step 3:** Promote when the delivery name is not already in `deliveries` and the list would then have length ≥ 2. Union `scope`. `render_lessons` writes only `taught` rows; zero taught rows is the single line `LESSONS: none`. `guild.py plan` prints `RULES: none` or one `RULES: <text>` line per entry in `rules_printed`.

**Step 4:** Full kernel units OK.

**Step 5: Commit** `feat(kernel): teach a repeated flag`

---

### Task 3: `pair` rejects and no-ops

**Files:**
- Modify: `scripts/guild-kernel/kernel.py`
- Modify: `scripts/guild-kernel/guild.py`
- Modify: `tests/kernel/test_kernel.py`

**Step 1: Failing tests**

- `pair(root, "tag", "a", reviewer="tech-lead")` after `plan` sets `stage.pair == "tech-lead"`.
- Unknown reviewer `nope`, reviewer equal to the stage agent, unknown stage id, and a stage saved as `done` each raise `PlanError` and do not change `pair`.
- A second `pair` with `tech-lead` is a no-op. A second `pair` with `qa-engineer` raises `PlanError` and leaves `tech-lead`.
- CLI `pair --root --name tag --stage a --reviewer nope` exits nonzero with no traceback.

**Step 2: FAIL** (`pair` missing).

**Step 3:** `AGENTS` frozenset of the 18 stems. `pair()` loads the delivery, finds the stage, rejects unless status is `queued` or `running`, rejects unknown or self reviewer, rejects a conflicting reviewer, no-ops the same reviewer, saves.

**Step 4:** Units OK.

**Step 5: Commit** `feat(kernel): pair a stage with a reviewer`

---

### Task 4: Writer report waits; `next` returns the reviewer

**Files:**
- Modify: `scripts/guild-kernel/kernel.py` (`report`, `next_agent`, `board_line`)
- Modify: `tests/kernel/test_kernel.py`

**Step 1: Failing test**

Plan one writer stage, `pair` it with `tech-lead`, report the writer file with exit 0. Assert stage status is still `running`, `awaiting_pair` is true, `verified` has the writer's exit 0, and `next_agent` returns `tech-lead`. Board line for that lane contains `tech-lead` and `▶`.

**Step 2: FAIL** (status becomes `done` or `next` returns the writer).

**Step 3:** In the stage loop, if this report is the writer and `stage.pair` is set, store did/verified/flags, set `awaiting_pair` true, leave status `running`. In `next_agent`, before the queued/running return, if `stage.awaiting_pair` return `stage.pair`. Lane text includes `pair:<reviewer>` while waiting.

**Step 4:** Units OK. Existing one-stage reports with no pair still mark `done`.

**Step 5: Commit** `feat(kernel): hold a paired stage for the reviewer`

---

### Task 5: Reviewer report completes; the rejects

**Files:**
- Modify: `scripts/guild-kernel/kernel.py` (`report`)
- Modify: `tests/kernel/test_kernel.py`

**Step 1: Failing tests**

- Reviewer file `stages/tech-lead.md` with exit 0 marks the waiting stage `done`, clears `awaiting_pair`, and `verified` still contains the writer's command plus the reviewer's.
- Prose `VERIFIED` and exit 1 raise `ReportError`; status stays `running` and `awaiting_pair` stays true.
- A `tech-lead.md` report when `awaiting_pair` is false raises `ReportError`.
- A second writer report while `awaiting_pair` raises `ReportError` and does not clear the wait.

**Step 2: FAIL.**

**Step 3:** If the file stem equals `stage.pair` and `awaiting_pair`, append reviewer commands and finish the stage. If the stem is `stage.agent` while `awaiting_pair`, raise. If the stem matches no waiting pair and no stage agent, raise (do not let a loose reviewer file succeed).

**Step 4:** Units OK.

**Step 5: Commit** `feat(kernel): reviewer exit 0 finishes a paired stage`

---

### Task 6: Cap while a pair is waiting

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py` only if the existing cap path does not already stop the delivery

**Step 1: Failing test**

One stage, so cap is 3. Pair it. Set `spawns` to `cap - 1`, save, then the writer report. Delivery status is `stopped`, stage stays `running`, `next_agent` is `STOP`.

**Step 2: FAIL** if `next` still returns `tech-lead` after the cap.

**Step 3:** The existing `report` cap assignment must run after `awaiting_pair` is set. `next_agent` already returns `STOP` for `stopped`. Do not mark the lane `done`.

**Step 4:** Units OK.

**Step 5: Commit** `feat(kernel): cap stops a waiting pair`

---

### Task 7: Lessons-file hook (9th guardrail)

**Files:**
- Create: `scripts/enforce-lessons-file.sh` (clone `scripts/enforce-sprint-file.sh`; path `docs/team/lessons.md`; allow a body whose first line is `LESSONS:` and that is either `LESSONS: none` or also contains `^RULE:`, `^SCOPE:`, and `^STATUS:`)
- Modify: `hooks/hooks.json`, `install.sh` desired list (Bash + Write|Edit)
- Modify: `scripts/build-codex-extension.py`, `scripts/build-gemini-extension.py` (copy + wire like sprint)
- Modify: `README.md` guardrail table and counts that `check-hook-sync` and inventory read
- Test: `tests/guardrails.test.sh` — helper Write allows, journal Write blocks, Bash write blocks, retro-style other path allows

**Step 1:** RED expects.

**Step 2–4:** Implement and wire. Inventory counts will be wrong until Task 8. Prefer Tasks 7 and 8 in the same commit if `check_inventory_sync.py` is run in CI on this branch before Task 8.

**Step 5: Commit** `feat(hooks): bounce non-helper lessons.md`

Guardrails become **9**. Codex hook files become **8** after the builder runs.

---

### Task 8: `/pair` command + inventory

**Files:**
- Create: `commands/pair.md` — **no** `> **Interface:**` blockquote. Frontmatter `allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion`. Body: call `python3 scripts/guild-kernel/guild.py pair --root . --name <delivery> --stage <id> [--reviewer tech-lead]`. Do not spawn a reviewer `next` did not return. Do not compose `lessons.md`.
- Modify: four manifests, `README.md`, `scripts/build-gemini-extension.py` description: commands **16**, gemini_commands **14**, guardrails **9**, Codex hooks **8**.

**Step 1:** `python3 scripts/check_inventory_sync.py` FAILs on the new counts before the claim edits.

**Step 2:** Add the command and update the claim strings (`16 workflow commands`, `14` gemini commands, `9` guardrails, `8` Codex PreToolUse hooks).

**Step 3:** Inventory `ok` except `coordinator_hash` if the Interface is not edited yet. If Task 9 is the same day, pin the hash there. Do not waive.

**Step 4: Commit** `feat: add /pair and inventory 16/9`

---

### Task 9: Interface + coordinator + rebuild

**Files:**
- Modify: the nine pipeline commands (exact insertion above)
- Modify: `agents/delivery-coordinator.md`
- Run: `python3 scripts/build-gemini-extension.py` and `python3 scripts/build-codex-extension.py`

**Step 1:** Guardrail greps for the new needles FAIL until the nine files match.

**Step 2:** Insert the sentence. Append the coordinator sentence once.

**Step 3:** Rebuild Gemini and Codex.

**Step 4:** `python3 scripts/check_inventory_sync.py` FAILs `coordinator_hash`. Update `tests/eval/baseline.json` `sha256` to the printed hash, `as_of` `2026-09-22`, note: `Pinned after 3.2 craft Interface. Billed feature-replay is not a ship gate. Do not raise ceilings.` `waivers: []`.

**Step 5: Commit** `feat: Interface carries RULES and lessons view`

---

### Task 10: Guardrail ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

Add expects (count **9** unless noted):

- Interface prints `RULES:`
- Interface never composes `lessons.md`
- Coordinator needle count **1**
- `/pair` does **not** contain `> **Interface:**` (count **0**)

Keep the 3.1 DoR and sprint expects.

**Commit:** `test(guardrails): ratchet RULES and lessons view`

---

### Task 11: Opt-in `feature-replay` (do not run it)

**Files:**
- Modify: `tests/eval/run-evals.sh`
- Modify: `tests/eval/baseline.json`
- Modify: `tests/guardrails.test.sh`

**Step 1:** Add `feature-replay` to `OPT_IN_CASES` only. Not `ALL_CASES`.

**Step 2:** `case_prompt` / `case_desc`: `/make-feature Tag --api`, description `replay a taught Model::all ban`. Prompt text tells the team to list tags and that `docs/team/lessons.json` is already taught.

**Step 3:** `seed_feature_replay_fixture` writes `docs/team/lessons.json` with one taught lesson, text `Do not call Model::all()`, scope `["backend-developer"]`, deliveries `["prior"]`. Call it from `run_case` the way `feature-resume` calls its seed.

**Step 4:** `check_rules_printed` reads `docs/delivery/*/kernel.json` and passes only if some `rules_printed` entry contains `Do not call Model::all()`. `check_no_model_all` passes when no `*.php` file under the workdir contains `Model::all()`. Both read the workdir only. `checks_feature_replay` calls `checks_feature` plus those two. Do not uncomment `check_subagent_log`.

**Step 5:** Copy the `feature` baseline ceilings onto `feature-replay` (1900 / 14500000 / 8.5) with basis `unmeasured; same Tag --api floor as feature. Do not raise.`

**Step 6:** Guardrail expects: `feature-replay` is opt-in (count 1), absent from `ALL_CASES` (count 0), `checks_feature_replay` calls `check_rules_printed` and `check_no_model_all`, and does not call `check_subagent_log`.

**Step 7:** Do **not** run `./tests/eval/run-evals.sh feature-replay`.

**Commit:** `test(eval): register opt-in feature-replay`

---

### Task 12: Local verify (no billed)

```bash
python3 -m unittest discover -s tests/kernel -t tests/kernel -v
python3 -m unittest discover -s tests/console -t tests/console -v
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
python3 scripts/check_body_budget.py
python3 scripts/check-hook-sync.py
shellcheck scripts/enforce-lessons-file.sh
```

Expected: all GREEN. Commit only if a fix was needed.

---

### Task 13: VERSION 3.2.0

**Files:** `VERSION`, five manifests (`VERSIONED` in `scripts/check_inventory_sync.py`), `CHANGELOG.md` (`[Unreleased]` → `[3.2.0] - <today>`), `docs/README.md` (move the Open 3.2 row to Closed), `docs/onboarding.md` last-verified. Rebuild Gemini so `gemini/gemini-extension.json` picks up `VERSION`.

**Commit:** `release: 3.2.0 — craft layer`

Do **not** tag or push unless the user says to release.

---

## Out of scope

Workplace, console as control plane, auto-pair on every flag, kernel writes to `conventions.md`, billed `feature-replay` as a ship gate, uncommenting `check_subagent_log`, raising ceilings, a new default agent, Adaptive as default.
