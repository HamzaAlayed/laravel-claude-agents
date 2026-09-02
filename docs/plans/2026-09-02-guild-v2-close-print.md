# Guild 2.2.2 close print — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** After every `close.md` Write, print `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:` in the same turn so a killed `/make-feature` still shows the scorecard in the transcript.

**Architecture:** Prompt-layer stickiness. Write `close.md` first (byte copy of the stub). Then print the four lines. Score billed `feature` `VERIFIED` / `NOT-CHECKED` on `$FULL_LOG` (`check_log_anywhere`) so an earlier printed close still counts when `$LOG` is a “waiting…” result. Do not loosen the close *file* helper.

**Tech Stack:** Agent markdown, byte-identical Interface, guardrail harness, Gemini/Codex rebuild, billed `claude -p` pin.

**Spec:** [docs/plans/2026-09-02-guild-v2-close-print-design.md](2026-09-02-guild-v2-close-print-design.md)

---

## Global constraints

- Branch: `feat/v2.2.2-close-print`. Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/v222-close-print`. Create it from `main` (after this plan is on `main`). Do **not** reuse `v221-adaptive-persist`. After checkout, verify `VERSION` is `2.2.1` and `HEAD` is this branch. Do **not** call `move_agent_to_root` (it can check out the wrong branch on a local-only name).
- Do **not** loosen `check_delivery_close_file`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `$8.50` / `EVAL_TIMEOUT` (1200) / 14.5M.
- Interface stays **byte-identical** across the nine pipeline commands.
- Coordinator `grep -c` needles stay **exactly 1**. Keep Close file as one paragraph. Do not mention `docs/delivery/<name>/close.md` on a new line (already count 1 via the packet/graph path discipline — the close path already lives in this paragraph).
- Do **not** bump `VERSION` until Task 7 PASS.
- Billed evals **only** when the user says **run it**.
- Default `/make-feature` stays Supervisor.

Nine pipeline commands:

`commands/make-feature.md`, `commands/add-test.md`, `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md`.

Exact Interface insertion after Task 2. Find this sentence (keep it):

`**Close file on disk** — after the plan and after every stage, overwrite `docs/delivery/<name>/close.md` with coordinator `VERIFIED` / `NOT-CHECKED` / `STATUS` / `BOARD`. A killed run is scored from that file.`

Immediately after it, still inside the same `> **Interface:**` blockquote, insert:

`After that Write, print `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:` in the same turn.`

Do not change Adaptive or graph sentences. “Your own final answer closes the same way” stays.

Exact coordinator **Close file** paragraph after Task 2 (keep it one paragraph; do not split the skeleton fence):

`**Close file** — persisted at `docs/delivery/<name>/close.md`; overwrite close.md after every stage (and after the plan, and after a re-brief returns — last Write before the next Task). Latest wins — a killed run is scored from this file, not mid-board prose. First Write of close.md is a byte copy of that file; copy skills/delivery-templates/close.md, then Edit only after the colons. Including a read-only persist, after every Agent return, the next Write is close.md. After that Write, print VERIFIED: / NOT-CHECKED: / STATUS: / BOARD: in the same turn. Harvest (`stack.md`, `log.md`) and the next Task wait until that Write lands. The close.md hook bounces a Write that is not helper shape. Bash must not write close.md.`

The fenced skeleton under that paragraph is unchanged.

Existing coordinator needles that must remain count **1**: `overwrite close.md after every stage`, `after every Agent return, the next Write is close.md`, `copy skills/delivery-templates/close.md`, `Bash must not write close.md`, `close.md hook bounces a Write that is not helper shape`.

New coordinator needle (count **1**): `after that Write, print VERIFIED:`

Interface uses backticks around the four labels (`print `VERIFIED:`). The Interface ratchet therefore greps `After that Write, print` — not `print VERIFIED:` (that substring is not present; a backtick sits between `print` and `VERIFIED:`). The coordinator paragraph has no backticks, so `after that Write, print VERIFIED:` is the coordinator needle.

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1:** After `Interface block requires graph stub byte copy`, add (no extra locals):

```bash
expect "Interface block prints close labels after the Write" "9" \
  "$(grep -l 'After that Write, print' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

After `coordinator forbids Bash writes of close.md`, add:

```bash
expect "coordinator prints close labels after the Write" "1" \
  "$(grep -c 'after that Write, print VERIFIED:' "$COORD")"
```

After `the opt-in case asserts the delivery graph file`, add:

```bash
expect "the opt-in case scores VERIFIED on FULL_LOG" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "check_log_anywhere 'VERIFIED'")"
expect "the opt-in case scores NOT-CHECKED on FULL_LOG" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "check_log_anywhere 'NOT-CHECKED'")"
```

Do not edit agents, commands, or `run-evals.sh` in this task.

**Step 2:**

```bash
./tests/guardrails.test.sh
```

Expected: those four FAIL. Everything else still GREEN (currently 259).

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet close print after close.md Write"
```

---

### Task 2: Interface + coordinator copy

**Files:**
- Modify: the nine pipeline commands (Interface Close-file insertion only)
- Modify: `agents/delivery-coordinator.md` — Close file paragraph only
- Modify: `scripts/body_budget.json` — only if a cap exceeds; raise **only** exceeded entries. Do not full `--reseed`.

**Step 1:** Apply the exact replacements in Global constraints. The Close-file sentence is already present as a unique substring (confirmed on `make-feature.md`). Insert the new sentence immediately after `A killed run is scored from that file.` and before `**Spawn cap in the board header**`. Confirm:

```bash
grep -h '^> \*\*Interface:\*\*' commands/*.md | sort -u | wc -l
```

Expected: `1`.

Do not touch Adaptive or Graph paragraphs. Do not repeat `copy skills/delivery-templates/close.md` (already count 1).

Verify coordinator needles:

```bash
COORD=agents/delivery-coordinator.md
grep -c 'overwrite close.md after every stage' "$COORD"
grep -c 'after every Agent return, the next Write is close.md' "$COORD"
grep -c 'copy skills/delivery-templates/close.md' "$COORD"
grep -c 'Bash must not write close.md' "$COORD"
grep -c 'after that Write, print VERIFIED:' "$COORD"
```

All must print `1`.

**Step 2:**

```bash
./tests/guardrails.test.sh
```

Expected: the two Interface/coordinator expects PASS. The two `checks_feature` expects still FAIL until Task 3.

**Step 3: Commit**

```bash
git add commands/*.md agents/delivery-coordinator.md
git commit -m "feat: print close labels after every close.md Write"
```

Include `scripts/body_budget.json` only if it changed.

---

### Task 3: Score VERIFIED / NOT-CHECKED on `$FULL_LOG`

**Files:**
- Modify: `tests/eval/run-evals.sh` — inside `checks_feature` only, replace:

```bash
  check_log 'VERIFIED' "final answer carries VERIFIED"
  check_log 'NOT-CHECKED' "final answer carries NOT-CHECKED"
```

with:

```bash
  check_log_anywhere 'VERIFIED' "final answer carries VERIFIED"
  check_log_anywhere 'NOT-CHECKED' "final answer carries NOT-CHECKED"
```

Also update the comment immediately above those two calls. Today it says only the closing-answer contract can be asserted against `$FULL_LOG`. After this slice, earlier coordinator turns that printed the four labels also count. Replace that comment with:

```bash
  # $FULL_LOG is main-thread turns only (scripts/eval-cost.py's full_text()).
  # After 2.2.2 the coordinator prints VERIFIED / NOT-CHECKED after every
  # close.md Write, so an earlier turn still scores when $LOG is a
  # "waiting…" kill. Do not grep stream.jsonl. Do not uncomment
  # check_subagent_log.
```

Do not change other `check_log` callers (hygiene, action, etc.). Do not grep `stream.jsonl`. Do not uncomment `check_subagent_log`. Do not change `check_delivery_close_file`. `checks_feature_adaptive` calls `checks_feature` — it inherits this automatically. Do **not** add a second pair of greps there.

**Step 1:** After the edit:

```bash
./tests/guardrails.test.sh
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
```

Expected: guardrails ALL GREEN (263 if 259+4). Body budget GREEN or one-cap raise. Inventory FAIL only on `coordinator_hash`. VERSION still `2.2.1`.

**Step 2: Commit**

```bash
git add tests/eval/run-evals.sh
git commit -m "feat(eval): score feature VERIFIED/NOT-CHECKED on FULL_LOG"
```

---

### Task 4: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` — fill `[Unreleased]`. Do **not** retitle to `[2.2.2]`. Do not claim billed PASS.
- Modify: `docs/README.md` — replace the Open table body. Do **not** add a Closed 2.2.2 row until Task 7.

```markdown
## [Unreleased]

After every `close.md` Write, the coordinator prints `VERIFIED:` /
`NOT-CHECKED:` / `STATUS:` / `BOARD:` in the same turn. A killed run
still shows the scorecard in the transcript. Default `/make-feature`
stays Supervisor.

### Changed

- **Close print.** After overwriting `docs/delivery/<name>/close.md`,
  print the four helper labels in the same turn, not only in the
  final answer.
```

Exact `docs/README.md` Open table (replace the current “No open Guild v2 slice” row):

```markdown
| Guild v2 — 2.2.2 close print | [design](plans/2026-09-02-guild-v2-close-print-design.md); [plan](plans/2026-09-02-guild-v2-close-print.md) — print close labels after every `close.md` Write. Gate is billed `feature`. |
```

**Step 2: Commit**

```bash
git add CHANGELOG.md docs/README.md
git commit -m "docs: Unreleased 2.2.2 close print"
```

---

### Task 5: Gemini / Codex mirrors

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

Commit only if diff: `chore: rebuild Gemini and Codex mirrors for close print`. If no diff, do not empty-commit.

---

### Task 6: Local verification (no billed run)

```bash
./tests/guardrails.test.sh
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
```

Expected: guardrails GREEN. Body budget GREEN. Inventory FAIL only `coordinator_hash`. VERSION `2.2.1`. Do not commit unless a check forced a missed edit. Stop until the user says **run it**.

---

### Task 7: Billed `feature` pin

**Do not run until Tasks 1–6 are green. Do not run until the user says `run it`.**

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature
```

Receipt: `docs/evals/2026-09-02-run-23.md` (or next date). Record: close file, `$LOG` vs `$FULL_LOG` `VERIFIED` / `NOT-CHECKED`, graph, harvest, cost vs $8.50, timeout, tokens vs 14.5M. Pin `coordinator_hash`. `waivers: []`.

**If close file PASS and `VERIFIED` / `NOT-CHECKED` PASS on `$LOG` or `$FULL_LOG`:** bump VERSION + five manifests to **2.2.2**. Retitle changelog `[2.2.2]`. Close the Open row. Commit `release: 2.2.2 — close print`.

**If they FAIL:** pin the hash, leave VERSION at 2.2.1, leave Unreleased. Commit `docs: eval run 23 — <what missed>`. Do not loosen the file helper. Do not raise ceilings.

Do not tag until CI is green on the PR.

---

## Out of bounds

- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s / 14.5M
- Loosening `check_delivery_close_file`
- Print without Write
- Adaptive as default `/make-feature`
- A new eval case
- Console UI
- Full `body_budget.json --reseed`
