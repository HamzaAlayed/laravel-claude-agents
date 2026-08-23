# Guild 2.0 close.md procedure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** After every Agent return the coordinator’s next Write is `close.md` in helper shape (`^VERIFIED:`, `^NOT-CHECKED:`, `STATUS: running|done|stopped`) — then billed-pin. Do not ship 2.0.0 unless `check_delivery_close_file` PASSes.

**Architecture:** Run 13 paraphrased `VERIFIED (` and left close.md stale after qa/tech-lead returned. This slice is one Integrate procedure, one ban (`VERIFIED (` is a contract break), and a helper tighten to line-anchored labels. Interface block unchanged. No stub file.

**Tech Stack:** Markdown agent body, bash guardrails + eval harness, Gemini/Codex rebuild, one billed `claude -p` `feature` run.

**Spec:** [docs/plans/2026-08-20-guild-v2-close-procedure-design.md](2026-08-20-guild-v2-close-procedure-design.md)

---

## Global constraints

- Stay on `feat/close-md-procedure`. This is a 2.0 follow-up, not 2.1 / 2.2.
- Do **not** loosen `check_delivery_close_file` to accept `VERIFIED (`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` `max_usd` ($8.50) or `EVAL_TIMEOUT` (1200).
- Do **not** duplicate `overwrite close.md after every stage` (count stays **1**).
- Do **not** grep the word `fixes` in helper source as a pin.
- Interface block stays byte-identical. Do not edit `commands/*.md`.
- Do **not** bump `VERSION` until Task 6’s billed close-file helper PASSes.
- Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/close-md-procedure`.

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1: Write the failing expects**

`COORD` is already `$SCRIPT_DIR/agents/delivery-coordinator.md`. Place next to the existing close-file expects (~ the `overwrite close.md after every stage` block):

```bash
expect "coordinator Writes close.md after every Agent return" "1" \
  "$(grep -c 'after every Agent return, the next Write is close.md' "$COORD")"
expect "coordinator bans parentheticals on close labels" "1" \
  "$(grep -c 'VERIFIED (` is a contract break' "$COORD")"
```

Those two are **0** today.

After the existing `close file accepts STATUS running` fixture, add a line-anchor reject. Current helper matches `VERIFIED:` anywhere on the line, so this expect is **red** until Task 2 (`CHECK_FAIL` is 0 today, want 1):

```bash
CLOSE_INDENT_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_INDENT_DIR/docs/delivery/tag"
printf '%s\n' \
  '  VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: z' \
  >"$CLOSE_INDENT_DIR/docs/delivery/tag/close.md"
expect "close file rejects indented VERIFIED:" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_INDENT_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_INDENT_DIR"

CLOSE_PAREN_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_PAREN_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED (coordinator): x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: z' \
  >"$CLOSE_PAREN_DIR/docs/delivery/tag/close.md"
expect "close file rejects VERIFIED parenthetical" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_PAREN_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_PAREN_DIR"
```

The parenthetical fixture should already be green (unanchored `VERIFIED:` already misses). It pins run 13. The indented fixture is the new red.

**Step 2: Run to confirm red**

```bash
./tests/guardrails.test.sh
```

Expected FAIL on: `coordinator Writes close.md after every Agent return`, `coordinator bans parentheticals on close labels`, and `close file rejects indented VERIFIED:`.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet close.md procedure and line-anchored labels"
```

---

### Task 2: Helper line-anchor

**Files:**
- Modify: `tests/eval/run-evals.sh` (`check_delivery_close_file`)
- Modify: `tests/eval/README.md` (one sentence)

**Step 1:** Keep the STATUS vocab check. Change the three-label loop to line-start:

```bash
    for label in 'VERIFIED:' 'NOT-CHECKED:' 'STATUS:'; do
      if ! grep -qE "^${label}" "$f"; then
        record 1 "file:   close file missing $label ($(basename "$(dirname "$f")")/close.md)"
        return
      fi
    done
```

Do not remove the `^STATUS: (running|done|stopped)` check. Do not accept `VERIFIED (`.

**Step 2:** In `tests/eval/README.md`, next to the existing close-file sentence, add that `VERIFIED:` / `NOT-CHECKED:` must start the line (`VERIFIED (` fails).

**Step 3:**

```bash
./tests/guardrails.test.sh
```

Expected: indented + parenthetical rejects PASS. Coordinator procedure/ban expects still FAIL until Task 3.

**Step 4: Commit**

```bash
git add tests/eval/run-evals.sh tests/eval/README.md
git commit -m "feat(eval): close.md labels must start the line"
```

---

### Task 3: Coordinator procedure + ban

**Files:**
- Modify: `agents/delivery-coordinator.md` (Close file / Integrate)

**Step 1:** Keep `overwrite close.md after every stage` (count 1). Add these two sentences **once** each, exact bytes:

- `After every Agent return, the next Write is close.md.`
- `` `VERIFIED (` is a contract break. ``

Put them in the Close file Working-interface block. Also state that harvest and the next Task wait until that Write lands, and that nothing sits between the label word and the colon. Do not duplicate the overwrite sentence. Do not put `VERIFIED (` anywhere except the ban sentence.

**Step 2:**

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

Expected: ALL GREEN guardrails. Inventory may fail on `coordinator_hash` until Task 6 — do not pin. If body_budget trips on coordinator lines, raise `scripts/body_budget.json` `agents.delivery-coordinator.lines` only as much as needed.

**Step 3: Commit**

```bash
git add agents/delivery-coordinator.md scripts/body_budget.json
git commit -m "feat: close.md is the next Write after every Agent return"
```

(Omit `body_budget.json` if unchanged.)

---

### Task 4: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`

**Step 1:** Do **not** retitle to `[2.0.0]`. Add a **Changed** bullet: after every specialist returns, the coordinator’s next Write is `close.md`; labels start the line (`VERIFIED (` is a contract break). Do not claim the billed gate passed.

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: Unreleased close.md procedure after every Agent return"
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
git commit -m "chore: rebuild Gemini and Codex mirrors for close.md procedure"
```

If the rebuild produces no diff, do not empty-commit.

---

### Task 6: Billed `feature` pin

**Do not run until Tasks 1–5 are green locally** (`./tests/guardrails.test.sh`; inventory may still be hash-red until this pin).

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature
```

Receipt: `docs/evals/2026-08-20-run-14.md` (or next date). Record: close file PASS/FAIL (line-anchor + STATUS vocab), basename PASS/FAIL, cost vs $8.50, timeout or not. Pin `coordinator_hash`. `waivers: []`.

**If `check_delivery_close_file` PASSes** and the basename check PASSes: bump `VERSION` + the five manifests to **2.0.0**. Retitle changelog `[2.0.0]`. Move the Open row to Closed. Commit `release: 2.0.0 — Supervisor complete (close file on disk)`.

**If either file check FAILs:** pin the hash anyway, leave VERSION at 1.45.0, leave Unreleased. Commit `docs: eval run 14 — <what missed>`. Do not loosen the helper.

Do not tag until CI is green on the PR.

---

## Out of bounds

- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s
- Accepting `VERIFIED (`
- Canonical stub file / copy-from-templates Write
- Editing the nine-command Interface block
- Peer handoff, router agent, `graph.md`
