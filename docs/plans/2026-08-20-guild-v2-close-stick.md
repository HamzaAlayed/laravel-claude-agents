# Guild 2.0 close-file stickiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the coordinator Write the `close.md` skeleton the eval already scores, and re-brief onto `stages/<agent>.md` — then billed-pin. Do not ship 2.0.0 unless `check_delivery_close_file` PASSes.

**Architecture:** Run 12 paraphrased a template that already had colons. This slice is a copy-paste skeleton (four labeled lines), one Task-prompt path line, a helper STATUS-vocab tighten (`running|done|stopped`), and static ratchets on the extracted Close file section. Interface block unchanged. No new surface.

**Tech Stack:** Markdown agent/skill bodies, bash guardrails + eval harness, Gemini/Codex rebuild, one billed `claude -p` `feature` run.

**Spec:** [docs/plans/2026-08-20-guild-v2-close-stick-design.md](2026-08-20-guild-v2-close-stick-design.md)

---

## Global constraints

- Stay on `feat/guild-v2`. This is a 2.0 follow-up, not 2.1 / 2.2.
- Do **not** loosen `check_delivery_close_file` to accept `VERIFIED (`.
- Do **not** allow `-fixes` basenames.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` `max_usd` ($8.50) or `EVAL_TIMEOUT` (1200).
- Do **not** duplicate `overwrite close.md after every stage` (count stays **1**). Extend that same sentence if you mention re-brief.
- Do **not** grep the word `fixes` in helper source as a pin.
- Interface block stays byte-identical across the nine pipeline commands. Do not edit it.
- Do **not** bump `VERSION` until Task 7’s billed close-file helper PASSes.
- `checks_*` never grep `stream.jsonl`.
- Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/guild-v2`.

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1: Write the failing expects**

Place next to the existing close-file / `-fixes` expects. Extract the Close file *section*, not the whole coordinator body — stage-return also starts lines with `VERIFIED:`.

After the `coordinator writes the close file after every stage` expect (~line 375):

```bash
CLOSE_COORD="$(sed -n '/^\*\*Close file\*\*/,/^\*\*Need-to-know briefs\*\*/p' "$COORD")"
expect "coordinator close skeleton prefixes VERIFIED:" "1" \
  "$(printf '%s\n' "$CLOSE_COORD" | grep -c '^VERIFIED:')"
expect "coordinator close skeleton prefixes NOT-CHECKED:" "1" \
  "$(printf '%s\n' "$CLOSE_COORD" | grep -c '^NOT-CHECKED:')"
expect "coordinator close skeleton STATUS is the in-flight default" "1" \
  "$(printf '%s\n' "$CLOSE_COORD" | grep -cE '^STATUS: running$')"
expect "coordinator close skeleton prefixes BOARD:" "1" \
  "$(printf '%s\n' "$CLOSE_COORD" | grep -c '^BOARD:')"
expect "coordinator re-brief names the exact stage path" "1" \
  "$(grep -c 'Stage file (overwrite, no other name):' "$COORD")"
```

`STATUS: running | done | stopped` is still the current line, so `^STATUS: running$` is **0**. The path needle is **0**. Those two are the red ones; the `VERIFIED:` / `NOT-CHECKED:` / `BOARD:` prefixes should already be 1.

After the `-fixes` fixture (~line 725), add helper fixtures. `check_delivery_close_file` currently accepts `STATUS: in-progress` if the three colons exist — this expect is red until Task 2:

```bash
TPL="$SCRIPT_DIR/skills/delivery-templates/SKILL.md"
CLOSE_TPL="$(sed -n '/^## Close file/,/^## Hygiene proposal/p' "$TPL")"
expect "delivery-templates close skeleton prefixes VERIFIED:" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -c '^VERIFIED:')"
expect "delivery-templates close skeleton prefixes NOT-CHECKED:" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -c '^NOT-CHECKED:')"
expect "delivery-templates close skeleton STATUS is the in-flight default" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -cE '^STATUS: running$')"
expect "delivery-templates close skeleton prefixes BOARD:" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -c '^BOARD:')"

CLOSE_REJECT_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_REJECT_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: in-progress' 'BOARD: z' \
  >"$CLOSE_REJECT_DIR/docs/delivery/tag/close.md"
expect "close file rejects STATUS in-progress" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_REJECT_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_REJECT_DIR"

CLOSE_PASS_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_PASS_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: z' \
  >"$CLOSE_PASS_DIR/docs/delivery/tag/close.md"
expect "close file accepts STATUS running" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_PASS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_PASS_DIR"
```

The `STATUS: running` pass fixture should already be green (colons only). The `in-progress` reject fixture is red.

**Step 2: Run to confirm red**

```bash
./tests/guardrails.test.sh
```

Expected: FAIL on `coordinator close skeleton STATUS is the in-flight default`, `coordinator re-brief names the exact stage path`, `delivery-templates close skeleton STATUS is the in-flight default`, and `close file rejects STATUS in-progress`.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet close.md skeleton and STATUS vocab"
```

---

### Task 2: Helper STATUS vocabulary

**Files:**
- Modify: `tests/eval/run-evals.sh` (`check_delivery_close_file`, ~351–369)
- Modify: `tests/eval/README.md` (one sentence)

**Step 1: Tighten the helper**

After the three-label loop, reject a STATUS that is not the allowed vocab. Do not remove the colon checks.

```bash
    if ! grep -qE '^STATUS: (running|done|stopped)(\b|$)' "$f"; then
      record 1 "file:   close file STATUS is not running|done|stopped ($(basename "$(dirname "$f")")/close.md)"
      return
    fi
```

**Step 2: Document**

In `tests/eval/README.md`, next to the existing `VERIFIED:`/`NOT-CHECKED:`/`STATUS:` sentence, add that `STATUS` must be `running`, `done`, or `stopped` (`in-progress` fails).

**Step 3: Run the in-progress / running fixtures**

```bash
./tests/guardrails.test.sh
```

Expected: `close file rejects STATUS in-progress` PASS. `close file accepts STATUS running` still PASS. Skeleton / path expects still FAIL until Tasks 3–4.

**Step 4: Commit**

```bash
git add tests/eval/run-evals.sh tests/eval/README.md
git commit -m "feat(eval): close.md STATUS must be running, done, or stopped"
```

---

### Task 3: Coordinator skeleton + re-brief path

**Files:**
- Modify: `agents/delivery-coordinator.md` (Working interface Close file + Re-brief)

**Step 1: Replace the Close file fenced example**

Keep the prose sentence that contains `overwrite close.md after every stage` — extend it, do not copy it. Target paragraph:

```
**Close file** — persisted at `docs/delivery/<name>/close.md`; overwrite close.md after every stage (and after the plan, and after a re-brief returns — last Write before the next Task). Latest wins — a killed run is scored from this file, not mid-board prose. Write these four lines as the start of close.md; do not rename labels.

VERIFIED: <commands you ran → counts>
NOT-CHECKED: <what nobody verified, or none>
STATUS: running
BOARD: <progress board as last printed>
```

`STATUS: running` must be the whole line (in-flight default). Enum lives in the next sentence: `STATUS` is exactly `running`, `done`, or `stopped` — never `in-progress`. Stage-return STATUS stays `done | blocked | needs-decision`.

The fenced block may wrap those four lines; they must still start at column 0 so `^STATUS: running$` matches. Do not put `VERIFIED (` anywhere.

**Step 2: Re-brief path line**

Keep `never spawn a `-fixes` suffix` (count 1). Add, in the Re-brief bullet or the Need-to-know briefs bullet, this exact phrase once:

```
Stage file (overwrite, no other name): docs/delivery/<name>/stages/<agent>.md
```

State that this line goes in the Task prompt, and that the coordinator still never writes a writer’s stage file.

**Step 3: Confirm coordinator expects**

```bash
./tests/guardrails.test.sh
```

Expected: coordinator skeleton + path expects PASS. Delivery-templates STATUS line still FAIL until Task 4.

**Step 4: Commit**

```bash
git add agents/delivery-coordinator.md
git commit -m "feat: close.md skeleton is four labeled lines; re-brief names the path"
```

---

### Task 4: delivery-templates aligned

**Files:**
- Modify: `skills/delivery-templates/SKILL.md` (Close file section)
- Modify: `scripts/body_budget.json` only if `skills.delivery-templates.lines` trips

**Step 1:** Same four first tokens as the coordinator skeleton (`VERIFIED:` / `NOT-CHECKED:` / `STATUS: running` / `BOARD:`). Same “never `in-progress`” sentence. Do not change the stage-return STATUS vocab in the section above.

**Step 2:**

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

Expected: ALL GREEN. If ratchet-budgets fails, raise `skills.delivery-templates.lines` the same way v1.45.0 did (109→126) — only as much as the new lines need.

**Step 3: Commit**

```bash
git add skills/delivery-templates/SKILL.md scripts/body_budget.json
git commit -m "feat: delivery-templates close skeleton matches the helper"
```

---

### Task 5: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`

**Step 1:** Do **not** retitle to `[2.0.0]`. Add a **Changed** bullet (user consequence): the close file is a four-line labeled skeleton; `STATUS` is `running|done|stopped`; a re-brief names the exact `stages/<agent>.md` path. Do not claim the billed gate passed.

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: Unreleased close.md skeleton and STATUS vocab"
```

---

### Task 6: Gemini / Codex mirrors

**Files:** generated trees only.

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

Commit whatever those scripts change (`gemini/`, `codex/`). CI jobs `gemini extension` and `codex target` must stay green.

```bash
git add gemini/ codex/
git commit -m "chore: rebuild Gemini and Codex mirrors for close.md skeleton"
```

---

### Task 7: Billed `feature` pin

**Do not run until Tasks 1–6 are green locally** (`./tests/guardrails.test.sh`, `python3 scripts/check_inventory_sync.py`).

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature
```

Receipt: `docs/evals/2026-08-20-run-13.md` (or next date). Record: close file PASS/FAIL, basename PASS/FAIL, `STATUS` vocab, cost vs $8.50, timeout or not, attributed USD, keep-workdir path. Pin `coordinator_hash` in `tests/eval/baseline.json`. `waivers: []` unless a new spec says otherwise.

**If `check_delivery_close_file` PASSes** and the basename check PASSes: bump `VERSION` + the five manifests `check_inventory_sync.py` lists to **2.0.0**. Retitle changelog `[2.0.0]`. Move the Open row to Closed. Last verified against v2.0.0. Commit `release: 2.0.0 — Supervisor complete (close file on disk)`.

**If either file check FAILs:** pin the hash anyway, leave VERSION at 1.45.0, leave Unreleased, do not claim 2.0.0. Commit `docs: eval run 13 — <what missed>`. Do not loosen the helper to green the run.

Do not tag until CI is green on the PR (same as 1.45.0).

---

## Out of bounds

- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s
- Accepting `VERIFIED (` or `-fixes`
- Unifying stage-return STATUS with close STATUS
- Peer handoff, router agent, `graph.md`
- New command, agent, console scene, or daemon
