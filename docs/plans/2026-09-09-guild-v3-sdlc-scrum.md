# Guild 3.1 SDLC / Scrum kernel — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Light DoR on every `plan`, DoD on delivery `done`, and an optional sprint object (Goal, WIP, attached stories) in the same `guild.py` kernel so SDLC/Scrum cannot be outranked by prose.

**Architecture:** Extend `scripts/guild-kernel/`. Delivery stays `docs/delivery/<name>/kernel.json`. Sprint is `docs/sprints/<id>/sprint.json` with view `docs/sprints/<id>/sprint.md`. Solo `/make-feature` still works. One running sprint implicit-attaches. `/sprint` is the 15th command.

**Tech Stack:** Python 3.10+ stdlib unittest, bash PreToolUse hook, markdown Interface, Gemini/Codex rebuild. No billed eval.

**Spec:** [docs/plans/2026-09-09-guild-v3-sdlc-scrum-design.md](2026-09-09-guild-v3-sdlc-scrum-design.md)

---

## Global constraints

- Branch: `feat/v3.1-sdlc-scrum` (already created from `main` @ 3.0.0). Do **not** reuse `v221-adaptive-persist`. Do **not** call `move_agent_to_root`.
- Do **not** bump `VERSION` until Task 12.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `$8.50` / `EVAL_TIMEOUT` (1200) / 14.5M.
- Do **not** loosen `check_kernel_state`.
- Do **not** add a sprint plant to default `feature`.
- Do **not** run billed evals.
- Default `/make-feature` stays Supervisor. Adaptive stays opt-in.
- Interface stays **byte-identical** across the nine pipeline commands. `/sprint` is **not** a pipeline command and must **not** carry that blockquote (keep the "9" grep).
- Coordinator `grep -c` needles for **new** clauses stay **exactly 1**.
- Nine pipeline commands: `commands/make-feature.md`, `commands/add-test.md`, `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md`.
- Kernel is stdlib only. Fake the process runner in tests.
- After Interface + coordinator edits, rebuild Gemini and Codex in the same change.
- Existing kernel tests that already pass `done_when` and nonempty `success_criteria` must stay green.
- `Delivery.sprint` defaults to `""` so 3.0 `kernel.json` files still `load`.

### Exact new Interface (Task 9)

Replace the entire `> **Interface:**` blockquote (one line) with this blockquote (one line, still starting `> **Interface:**`):

```
> **Interface:** Call `python3 scripts/guild-kernel/guild.py` for this delivery — `plan` before any Agent, `next` to choose whom to Agent, `report` on `docs/delivery/<name>/stages/<agent>.md` after each return, `board` to print `✔ done / ▶ running / · queued / ✖ failed`. `plan` must pass a nonempty `--done-when` and every `--stage` must carry success criteria. If a sprint is running, attach it (`--sprint <id>` or the kernel attaches the single running sprint). Never invent a checkmark; never compose `docs/delivery/<name>/close.md` (the kernel renders that view). Never compose `docs/sprints/<id>/sprint.md` (the kernel renders that view). Writers Write the six fields `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines) as their last act; never write a writer's stage file for them. Read-only specialists — persist their stage file from the report you already file, then `report`. `VERIFIED:` lines are shell commands the kernel re-runs; prose is a reject. `NOT-CHECKED:` that names a stage success criterion is a reject. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, persist `docs/delivery/<name>/stages/peer-router.md` and `report` it; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.
```

New Interface needles (count **9**):

- `plan` must pass a nonempty `--done-when`
- `Never compose \`docs/sprints/<id>/sprint.md\``

### Exact coordinator Kernel paragraph (Task 9)

Keep the existing Kernel paragraph. Append (same paragraph or the next sentence, still count **1** for the new needle):

`plan` carries nonempty `done_when` and per-stage success criteria. If a sprint is running, attach it. Do not Write sprint.md; the kernel renders it.

Needle (count **1**): `Do not Write sprint.md; the kernel renders it`

---

### Task 1: Light DoR on `plan`

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py`

**Step 1: Write the failing tests** (new class `DorTest`)

```python
class DorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_rejects_empty_done_when(self):
        with self.assertRaises(kernel.PlanError):
            kernel.plan(
                root=self.root,
                name="tag",
                done_when="",
                stages=[
                    kernel.StageSpec("a", "database-developer", "writer", ["m"], []),
                ],
            )
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())

    def test_plan_rejects_stage_without_criteria(self):
        with self.assertRaises(kernel.PlanError):
            kernel.plan(
                root=self.root,
                name="tag",
                done_when="POST /api/tags creates a Tag",
                stages=[
                    kernel.StageSpec("a", "database-developer", "writer", [], []),
                ],
            )
        self.assertFalse((self.root / "docs/delivery/tag/kernel.json").is_file())
```

**Step 2: Run to verify fail**

```bash
python3 -m unittest tests.kernel.test_kernel.DorTest -v
```

Expected: FAIL (`PlanError` missing or `plan` writes the file).

**Step 3: Minimal implementation**

- Add `class PlanError(Exception):` next to `ReportError`.
- At the start of `plan()`, after the existing-file no-op: if not `done_when.strip()` or any stage has no nonempty `success_criteria` item, raise `PlanError`. Do not `save`.

**Step 4: Run all kernel tests**

```bash
python3 -m unittest tests.kernel.test_kernel
```

Expected: OK (existing plans already have criteria + done_when).

**Step 5: Commit**

```bash
git commit -m "feat(kernel): light DoR on plan"
```

---

### Task 2: DoD on delivery `done`

**Files:**
- Modify: `tests/kernel/test_kernel.py`
- Modify: `scripts/guild-kernel/kernel.py` (`report`)

**Step 1: Failing test**

When every stage is `done` but one has `verified == []`, `report` on the last stage must not set `delivery.status = "done"` — raise `ReportError` or leave `running`. Prefer: after marking the current stage, if all stages are done/skipped and any non-skipped stage has no `verified` entry with `exit == 0`, raise `ReportError` and do not save `status=done`.

Simplest reproducible case: two stages; first marked `done` with empty `verified` via `save`; second `report` succeeds commands — delivery must not become `done`.

**Step 2: Run — expect FAIL** (today `report` sets `done` whenever all statuses are done/skipped).

**Step 3: Gate the `delivery.status = "done"` assignment in `report`.

**Step 4: Full kernel units OK.

**Step 5: Commit** `feat(kernel): DoD requires verified exit 0`

---

### Task 3: Sprint start + view + no-op

**Files:**
- Modify: `scripts/guild-kernel/kernel.py`
- Modify: `tests/kernel/test_kernel.py`

**Step 1: Failing tests**

- `sprint_start(root, id="3.1", goal="SDLC/Scrum kernel", wip=2)` writes `docs/sprints/3.1/sprint.json` with `status=running`, `stories=[]`, and `docs/sprints/3.1/sprint.md` whose lines start with `GOAL:`, `WIP:`, `BOARD:`, `STATUS:`.
- Second `sprint_start` while running does not reset `stories` or `wip` (mutate stories, save, start again).

**Step 2: FAIL** (`sprint_start` missing).

**Step 3: Add `@dataclass Sprint` (`id`, `goal`, `wip`, `stories`, `status`). Paths under `docs/sprints/<id>/`. `write_sprint_view`. `sprint_start` no-op if any sprint.json has `status==running` (load that one, rewrite view, return it) — if the running id differs from the requested id, still no-op the **existing** running sprint (do not create a second).

**Step 4: Units OK.

**Step 5: Commit** `feat(kernel): sprint start and helper view`

---

### Task 4: Attach, WIP, implicit, two sprints

**Files:**
- Modify: `scripts/guild-kernel/kernel.py` (`plan`, `Delivery.sprint` field)
- Modify: `tests/kernel/test_kernel.py`

**Step 1: Failing tests**

- `plan(..., sprint="3.1")` after `sprint_start` sets `delivery.sprint == "3.1"` and appends the name to `stories`.
- WIP: `wip=1`, one running attached delivery, second `plan` raises `PlanError`.
- No running sprint: `plan` without sprint still succeeds (light DoR).
- One running sprint: `plan` **without** `sprint=` still attaches.
- Two `running` sprint.json files (write the second by hand) → `plan` raises.

`load()` must `setdefault("sprint", "")` before `Delivery(**data)`.

**Step 2: FAIL.

**Step 3: Implement `running_sprints(root)`, attach + WIP count = attached names whose `kernel.json` `status==running`. Missing/done/stopped `--sprint` id raises `PlanError`.

**Step 4: Units OK.

**Step 5: Commit** `feat(kernel): plan attaches to a running sprint`

---

### Task 5: Sprint close and `--force`

**Files:**
- Modify: `scripts/guild-kernel/kernel.py`
- Modify: `tests/kernel/test_kernel.py`

**Step 1:** `sprint_close` with a running story raises; `sprint_close(..., force=True)` sets sprint `stopped`; all stories `done`/`stopped` → sprint `done`.

**Step 2–4:** TDD. **Step 5:** Commit `feat(kernel): sprint close`

---

### Task 6: CLI

**Files:**
- Modify: `scripts/guild-kernel/guild.py`
- Modify: `tests/kernel/test_kernel.py` (CLI subprocess, same pattern as `test_cli_stage_carries_success_criteria`)

**Step 1:** CLI tests:

- `plan` without `--done-when` or with `--stage a,database-developer,writer` (no 5th field) exits nonzero.
- `sprint start --root --id 3.1 --goal "…" --wip 2` then `sprint board` prints GOAL/WIP.
- `plan --sprint 3.1 --done-when … --stage a,database-developer,writer,,migration exists` attaches.

**Step 2–4:** Wire `build_parser` subparser `sprint` with `start|board|status|close`. `plan --sprint` default `""`. Map `PlanError` to `SystemExit` with the message (not a traceback).

**Step 5:** Commit `feat(kernel): sprint CLI and plan --sprint`

---

### Task 7: Sprint-file hook (8th guardrail)

**Files:**
- Create: `scripts/enforce-sprint-file.sh` (clone `scripts/enforce-stage-return.sh`; path `docs/sprints/.+/sprint\.md`; labels `GOAL` `WIP` `BOARD` `STATUS`)
- Modify: `hooks/hooks.json` (Write|Edit + Bash, same as close-file)
- Modify: `install.sh` merge list if it names scripts
- Modify: `scripts/build-codex-extension.py` (copy + wire like stage-return; print string will say 7 Codex hooks)
- Modify: `scripts/check-hook-sync.py` or equivalent list
- Modify: `README.md` Codex/plugin guardrail counts
- Test: `tests/guardrails.test.sh` — copy the stage-return expects for sprint.md

**Step 1:** RED expects (stub Write allows, journal Write blocks, Bash write blocks).

**Step 2–4:** Implement + wire. Inventory will be red until Task 8 — that is OK if you bump README/manifests in Task 8 the same day; **prefer Task 7+8 together if inventory fails CI mid-branch**, else fix claims in Task 8 immediately after.

**Step 5:** Commit `feat(hooks): bounce non-helper sprint.md`

Guardrails: production **8**. Codex `*.sh` **7**. Plugin README "eight guardrail hooks". Gemini command count unchanged until `/sprint` exists.

---

### Task 8: `/sprint` command + inventory

**Files:**
- Create: `commands/sprint.md` — **no** pipeline Interface blockquote. Frontmatter `allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion`. Body: call `python3 scripts/guild-kernel/guild.py sprint …`; start/board/status/close; do not compose `sprint.md`; persist retro at `docs/sprints/<id>/retro.md` (unhooked). Delegate Petra/Hana as needed.
- Modify: four manifests + README + `scripts/build-gemini-extension.py` description string for command counts: commands **15**, gemini_commands **13** (sprint is not in `GEMINI_SKIP_COMMANDS`), guardrails **8**, README Codex hooks **7**.
- Modify: plugin descriptions "14 workflow commands" → "15", "7 production guardrail" → "8".

**Step 1:** `python3 scripts/check_inventory_sync.py` should FAIL on counts before edits.

**Step 2:** Add command + update claims.

**Step 3:** Inventory `ok`. Gemini rebuild not required until Task 9 if Interface unchanged; still update the **count string** in the builder.

**Step 4:** Commit `feat: add /sprint and inventory 15/8`

---

### Task 9: Thin Interface + coordinator + rebuild

**Files:**
- Modify: nine pipeline commands (exact Interface above)
- Modify: `agents/delivery-coordinator.md` Kernel paragraph
- Run: `python3 scripts/build-gemini-extension.py` and `python3 scripts/build-codex-extension.py`

**Step 1:** Guardrail Interface greps FAIL until the nine files match.

**Step 2:** Replace the blockquote; append coordinator needle.

**Step 3:** Rebuild Gemini/Codex.

**Step 4:** `python3 scripts/check_inventory_sync.py` — `coordinator_hash` will FAIL. Update `tests/eval/baseline.json` `sha256` + `as_of` 2026-09-09 + note: "Pinned after 3.1 SDLC Interface. Billed feature is not a ship gate. Do not raise ceilings." `waivers: []`.

**Step 5:** Commit `feat: Interface carries DoR and sprint attach`

---

### Task 10: Guardrail ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

Add expects (count **9** unless noted):

- Interface: nonempty `--done-when`
- Interface: never compose sprint.md
- Coordinator: `Do not Write sprint.md; the kernel renders it` count **1**
- `/sprint` does **not** contain `> **Interface:**` (count **0** on that file)

Keep existing kernel Interface expects.

**Commit:** `test(guardrails): ratchet DoR and sprint view`

---

### Task 11: Local verify (no billed)

```bash
python3 -m unittest discover -s tests/kernel -t tests/kernel -v
python3 -m unittest discover -s tests/console -t tests/console -v
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
python3 scripts/check_body_budget.py
```

Expected: all GREEN. Commit only if a fix was needed.

---

### Task 12: VERSION 3.1.0

**Files:** `VERSION`, five manifests, `CHANGELOG.md` (`[Unreleased]` → `[3.1.0] - 2026-09-09`), `docs/README.md` (move Open 3.1 row to Closed), `docs/onboarding.md` last-verified.

**Commit:** `release: 3.1.0 — SDLC / Scrum kernel`

Do **not** tag or push unless the user says to release.

---

## Out of scope

Compounding company, `/pair`, workplace, billed `feature-sprint`, RICE in JSON, Linear as source of truth, nested deliveries, second Python package.
