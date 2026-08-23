# Guild 2.0 close.md stub copy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Coordinator first-Writes `close.md` by copying `skills/delivery-templates/close.md` (and the six-line stage-return stub when persisting read-only), then fills after the colons — then billed-pin. Do not ship 2.0.0 unless `check_delivery_close_file` PASSes.

**Architecture:** Runs 13 and 14 paraphrased `VERIFIED (` despite a skeleton, a ban, and a next-Write procedure. This slice adds two committed stub files and copy-then-fill needles. Helper stays `^VERIFIED:`. Interface block unchanged.

**Tech Stack:** Markdown agent body + skill stubs, bash guardrails + eval harness, Gemini/Codex rebuild, one billed `claude -p` `feature` run.

**Spec:** [docs/plans/2026-08-21-guild-v2-close-stub-design.md](2026-08-21-guild-v2-close-stub-design.md)

---

## Global constraints

- Stay on `feat/close-md-stub`. This is a 2.0 follow-up, not 2.1 / 2.2.
- Do **not** loosen `check_delivery_close_file` to accept `VERIFIED (`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` `max_usd` ($8.50) or `EVAL_TIMEOUT` (1200).
- Do **not** duplicate `overwrite close.md after every stage` (count stays **1**).
- Do **not** drop the existing next-Write / `VERIFIED (` ban / four-line fence expects.
- Do **not** grep the word `fixes` in helper source as a pin.
- Interface block stays byte-identical. Do not edit `commands/*.md`.
- Do **not** bump `VERSION` until Task 6’s billed close-file helper PASSes.
- Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/close-md-stub`.

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1: Write the failing expects**

`COORD` is already `$SCRIPT_DIR/agents/delivery-coordinator.md`. Place next to the existing close-file expects (after the parenthetical-ban expect):

```bash
expect "coordinator copies the close stub" "1" \
  "$(grep -c 'copy skills/delivery-templates/close.md' "$COORD")"
expect "coordinator copies the stage-return stub when persisting read-only" "1" \
  "$(grep -c 'copy skills/delivery-templates/stage-return.md' "$COORD")"
```

Those two are **0** today.

After the existing `delivery-templates close skeleton prefixes BOARD:` block, add stub-file expects. `CLOSE_STUB` / `STAGE_STUB` do not exist yet — the expects FAIL until Task 2:

```bash
CLOSE_STUB="$SCRIPT_DIR/skills/delivery-templates/close.md"
STAGE_STUB="$SCRIPT_DIR/skills/delivery-templates/stage-return.md"
expect "close stub file prefixes VERIFIED:" "1" \
  "$(sed -n '1p' "$CLOSE_STUB" 2>/dev/null | grep -c '^VERIFIED:')"
expect "close stub file prefixes NOT-CHECKED:" "1" \
  "$(sed -n '2p' "$CLOSE_STUB" 2>/dev/null | grep -c '^NOT-CHECKED:')"
expect "close stub file STATUS is the in-flight default" "1" \
  "$(sed -n '3p' "$CLOSE_STUB" 2>/dev/null | grep -cE '^STATUS: running$')"
expect "close stub file prefixes BOARD:" "1" \
  "$(sed -n '4p' "$CLOSE_STUB" 2>/dev/null | grep -c '^BOARD:')"
expect "stage-return stub file prefixes STATUS:" "1" \
  "$(sed -n '1p' "$STAGE_STUB" 2>/dev/null | grep -c '^STATUS:')"
expect "stage-return stub file prefixes DID:" "1" \
  "$(sed -n '2p' "$STAGE_STUB" 2>/dev/null | grep -c '^DID:')"
expect "stage-return stub file prefixes VERIFIED:" "1" \
  "$(sed -n '3p' "$STAGE_STUB" 2>/dev/null | grep -c '^VERIFIED:')"
expect "stage-return stub file prefixes NOT-CHECKED:" "1" \
  "$(sed -n '4p' "$STAGE_STUB" 2>/dev/null | grep -c '^NOT-CHECKED:')"
expect "stage-return stub file prefixes FLAGS:" "1" \
  "$(sed -n '5p' "$STAGE_STUB" 2>/dev/null | grep -c '^FLAGS:')"
expect "stage-return stub file prefixes NEXT:" "1" \
  "$(sed -n '6p' "$STAGE_STUB" 2>/dev/null | grep -c '^NEXT:')"
```

Keep the existing `TPL` / `CLOSE_TPL` SKILL.md skeleton expects. Helper fixtures stay as they are (already reject `VERIFIED (` and indent).

**Step 2: Run to confirm red**

```bash
./tests/guardrails.test.sh
```

Expected FAIL on: `coordinator copies the close stub`, `coordinator copies the stage-return stub when persisting read-only`, and the eight stub-file prefix expects.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet close.md stub copy-then-fill"
```

---

### Task 2: Stub files + skill pointer

**Files:**
- Create: `skills/delivery-templates/close.md`
- Create: `skills/delivery-templates/stage-return.md`
- Modify: `skills/delivery-templates/SKILL.md` (Close file + Stage return sections)

**Step 1:** Write the two stubs. No extra prose, no trailing blank line after the last label (or one trailing newline only — POSIX text file). Placeholders after the colon match the existing fences:

`skills/delivery-templates/close.md`:

```
VERIFIED: <commands you ran → counts>
NOT-CHECKED: <what nobody verified, or none>
STATUS: running
BOARD: <progress board as last printed>
```

`skills/delivery-templates/stage-return.md`:

```
STATUS: done | blocked | needs-decision
DID: files / artifacts touched, one line each
VERIFIED: command → result (counts, `file:line`) — not claims
NOT-CHECKED: surfaces not examined, ≤3 lines — or none
FLAGS: corrections, risks, checkpoints — or none
NEXT: handoff or none
```

**Step 2:** In `SKILL.md`, Close file section: keep the four-line fence (existing `CLOSE_TPL` expects). Add one sentence that the coordinator copies `close.md` in this skill directory and fills after the colons. Stage return section: same for `stage-return.md`. Do not remove the fences.

If `python3 scripts/check_body_budget.py` trips on `skills.delivery-templates.lines`, raise `scripts/body_budget.json` only as much as needed.

**Step 3:**

```bash
./tests/guardrails.test.sh
python3 scripts/check_body_budget.py
```

Expected: stub-file expects PASS. Coordinator copy needles still FAIL until Task 3.

**Step 4: Commit**

```bash
git add skills/delivery-templates/close.md skills/delivery-templates/stage-return.md skills/delivery-templates/SKILL.md scripts/body_budget.json
git commit -m "feat: canonical close.md and stage-return stubs"
```

(Omit `body_budget.json` if unchanged.)

---

### Task 3: Coordinator copy-then-fill

**Files:**
- Modify: `agents/delivery-coordinator.md` (Close file / read-only persist)

**Step 1:** Keep `overwrite close.md after every stage` (count 1), the next-Write sentence, and `` `VERIFIED (` is a contract break. `` Add these two needles **once** each, exact bytes:

- `copy skills/delivery-templates/close.md`
- `copy skills/delivery-templates/stage-return.md`

Put the close-stub needle in the Close file Working-interface block: first Write of close.md is a byte copy of that file; then Edit only after the colons.

Put the stage-return stub needle on the read-only persist sentence (tech-lead / security-engineer / performance-engineer): when persisting their stage file, copy the stub then fill after the colons. Do not write a writer's stage file.

Keep the four-line close fence and six-line stage-return fence. Do not duplicate the overwrite sentence.

**Step 2:**

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

Expected: ALL GREEN guardrails. Inventory may fail on `coordinator_hash` until Task 6 — do not pin. If body_budget trips on coordinator lines, raise `scripts/body_budget.json` `agents.delivery-coordinator.lines` only as much as needed.

**Step 3: Commit**

```bash
git add agents/delivery-coordinator.md scripts/body_budget.json
git commit -m "feat: copy close.md stub then fill after the colons"
```

(Omit `body_budget.json` if unchanged.)

---

### Task 4: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`

**Step 1:** Do **not** retitle to `[2.0.0]`. Add a **Changed** bullet: first Write of `close.md` copies `skills/delivery-templates/close.md`; read-only persist copies `stage-return.md`; fill after the colons. Do not claim the billed gate passed.

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: Unreleased close.md stub copy-then-fill"
```

---

### Task 5: Gemini / Codex mirrors

**Files:** generated trees only.

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

```bash
git add gemini/ codex/
git commit -m "chore: rebuild Gemini and Codex mirrors for close.md stub"
```

If the rebuild produces no diff, do not empty-commit.

---

### Task 6: Billed `feature` pin

**Do not run until Tasks 1–5 are green locally** (`./tests/guardrails.test.sh`; inventory may still be hash-red until this pin).

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature
```

Receipt: `docs/evals/2026-08-21-run-15.md` (or next date). Record: close file PASS/FAIL (`^VERIFIED:` + STATUS vocab), basename PASS/FAIL, tech-lead.md `^VERIFIED:` if present, cost vs $8.50, timeout or not. Pin `coordinator_hash`. `waivers: []`.

**If `check_delivery_close_file` PASSes** and the basename check PASSes: bump `VERSION` + the five manifests to **2.0.0**. Retitle changelog `[2.0.0]`. Move the Open row to Closed. Commit `release: 2.0.0 — Supervisor complete (close file on disk)`.

**If either file check FAILs:** pin the hash anyway, leave VERSION at 1.45.0, leave Unreleased. Commit `docs: eval run 15 — <what missed>`. Do not loosen the helper.

Do not tag until CI is green on the PR.

---

## Out of bounds

- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s
- Accepting `VERIFIED (`
- Editing the nine-command Interface block
- Peer handoff, router agent, `graph.md`
- Replacing the stub files with a louder prompt-only ban
