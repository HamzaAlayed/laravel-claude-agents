# Guild 2.0 close.md shape hook Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deny `Write`/`Edit` of `docs/delivery/*/close.md` unless the payload is helper shape, then billed-pin. Do not ship 2.0.0 unless `check_delivery_close_file` PASSes.

**Architecture:** Runs 13–15 paraphrased `VERIFIED (` despite skeleton, ban, procedure, and stub files. This slice adds `scripts/enforce-close-file.sh` on the existing `Write|Edit` PreToolUse matcher (sixth production guardrail). Helper stays `^VERIFIED:`. Interface block unchanged.

**Tech Stack:** Bash hook + guardrail harness, inventory/hook-sync, Gemini/Codex rebuild, one billed `claude -p` `feature` run.

**Spec:** [docs/plans/2026-08-21-guild-v2-close-hook-design.md](2026-08-21-guild-v2-close-hook-design.md)

---

## Global constraints

- Stay on `feat/close-md-hook`. This is a 2.0 follow-up, not 2.1 / 2.2.
- Do **not** loosen `check_delivery_close_file` to accept `VERIFIED (`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` `max_usd` ($8.50), `EVAL_TIMEOUT` (1200), or the 14.5M token ceiling.
- Do **not** drop existing overwrite / next-Write / ban / stub-copy expects.
- Interface block stays byte-identical. Do not edit `commands/*.md`.
- Do **not** bump `VERSION` until Task 7’s billed close-file helper PASSes.
- Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/close-md-hook`.

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1: Write the failing expects**

Place a new section after the existing `protect-env-files.sh` expects. `BLOCK=2` `ALLOW=0` already defined. `run_hook` / `run_hook_noparsers` already exist.

Script name: `enforce-close-file.sh` (does not exist yet — expects FAIL until Task 2).

```bash
echo "enforce-close-file.sh (close.md helper shape)"
CLOSE_OK='{"tool_input":{"path":"docs/delivery/tag/close.md","contents":"VERIFIED: x\nNOT-CHECKED: y\nSTATUS: running\nBOARD: z\n"}}'
CLOSE_JOURNAL='{"tool_input":{"path":"docs/delivery/tag/close.md","contents":"# Close file\n\nVERIFIED (coordinator):\nx\nSTATUS: planning complete\n"}}'
CLOSE_OTHER='{"tool_input":{"path":"app/Models/Tag.php","contents":"class Tag {}\n"}}'
CLOSE_EDIT_OK='{"tool_input":{"file_path":"docs/delivery/tag/close.md","new_string":"VERIFIED: x\nNOT-CHECKED: none\nSTATUS: done\nBOARD: done\n"}}'
CLOSE_EDIT_BAD='{"tool_input":{"file_path":"docs/delivery/tag/close.md","new_string":"more journal\n"}}'
expect "close.md stub Write allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh "$CLOSE_OK")"
expect "close.md journal Write blocks" "$BLOCK" \
  "$(run_hook enforce-close-file.sh "$CLOSE_JOURNAL")"
expect "non-close.md Write allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh "$CLOSE_OTHER")"
expect "close.md stub Edit allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh "$CLOSE_EDIT_OK")"
expect "close.md journal Edit blocks" "$BLOCK" \
  "$(run_hook enforce-close-file.sh "$CLOSE_EDIT_BAD")"
expect "FALLBACK (no jq/python3): close.md path still blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-close-file.sh "$CLOSE_JOURNAL")"
```

`COORD` is already set later in the file. Add the coordinator needle next to the existing close-stub copy expects (after `copy skills/delivery-templates/stage-return.md`):

```bash
expect "coordinator names the close.md hook bounce" "1" \
  "$(grep -c 'close.md hook bounces a Write that is not helper shape' "$COORD")"
```

That needle is **0** today. Do not add hook-sync / inventory expects here — those scripts fail the whole check until wiring exists; Task 2/3 own them. Keep helper fixtures unchanged.

**Step 2: Run to confirm red**

```bash
./tests/guardrails.test.sh
```

Expected FAIL on the six hook expects plus the coordinator needle.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet close.md shape hook"
```

---

### Task 2: Hook script + Claude wiring

**Files:**
- Create: `scripts/enforce-close-file.sh` (executable)
- Modify: `hooks/hooks.json` (Write|Edit matcher, next to protect-env-files)
- Modify: `install.sh` (`desired` list)
- Modify: `README.md` (tree listing + Guardrail scripts table + example JSON if that example lists every Write|Edit hook)

**Step 1:** Write the hook. Match `protect-env-files.sh` structure (stdin JSON, jq → python3 → raw fallback, exit 2 to block). Differences:

- Path match: `docs/delivery/` … `/close.md` (allow `file_path` / `path` / `absolute_path`).
- Body: `tool_input.contents` or `tool_input.new_string`.
- Allow when body matches all four: `^VERIFIED:` `^NOT-CHECKED:` `^STATUS: (running|done|stopped)` `^BOARD:` (multiline grep -qE).
- Deny otherwise, stderr: copy `skills/delivery-templates/close.md`; close.md is not log.md.
- Non-matching path: exit 0 even if body is empty.
- Path matches and body empty/unparseable: exit 2 (fail closed).
- No-parser fallback: if the raw payload looks like `docs/delivery` + `close.md`, exit 2.

**Step 2:** Wire `hooks.json` and `install.sh`. Add a README table row. Tree listing under `scripts/` should name the file.

**Step 3:**

```bash
chmod +x scripts/enforce-close-file.sh
./tests/guardrails.test.sh
python3 scripts/check-hook-sync.py
```

Expected: hook fixtures PASS. Coordinator needle still FAIL until Task 4. `check-hook-sync` PASS. Inventory still claims 5 guardrails — FAIL until Task 3; that is OK for this commit if you have not updated manifests yet. Prefer updating inventory in Task 3.

**Step 4: Commit**

```bash
git add scripts/enforce-close-file.sh hooks/hooks.json install.sh README.md
git commit -m "feat: bounce close.md Writes that are not helper shape"
```

---

### Task 3: Inventory 5→6 + Gemini/Codex

**Files:**
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json` (guardrail count **five/5 → six/6**)
- Modify: `README.md` remaining “5 guardrail” / “five guardrail” claims that `check_inventory_sync.py` greps
- Modify: `gemini/hooks/hooks.json` (`write_file|replace` matcher, next to protect-env-files)
- Modify: `scripts/build-codex-extension.py` (copy `enforce-close-file.sh` into `.codex/hooks/`, wire `Write|Edit`; print line 4→5 hooks)
- Modify: any Codex README claim of **4** PreToolUse guardrails that inventory greps (`the 4 guardrail hooks as PreToolUse`)

If `check_inventory_sync.py` claim phrases use `NUM`, keep the phrase shape and only change the digit/word on disk.

**Step 1:** Update counts. Gemini wiring. Codex generator + regenerate:

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
```

Gemini hook json is source, not generated — edit it by hand. Codex `.codex/hooks/` is generated.

**Step 2:**

```bash
python3 scripts/check_inventory_sync.py
python3 scripts/check-hook-sync.py
./tests/guardrails.test.sh
```

Inventory may still fail on `coordinator_hash` until Task 7 if Task 4 has already landed; if Task 4 has not landed, hash is still the run-15 pin and inventory should be green except coordinator needle (guardrails). Do this task **before** Task 4 so inventory can go green on counts.

**Step 3: Commit**

```bash
git add .claude-plugin/ .cursor-plugin/ README.md gemini/hooks/hooks.json scripts/build-codex-extension.py gemini/ codex/
git commit -m "chore: sixth guardrail — inventory, Gemini, Codex"
```

(Only add generated trees that actually diff.)

---

### Task 4: Coordinator needle

**Files:**
- Modify: `agents/delivery-coordinator.md` (Close file Working-interface block)

**Step 1:** Keep overwrite / next-Write / ban / stub-copy (each count 1). Add **once**, exact bytes:

- `close.md hook bounces a Write that is not helper shape`

Put it in the Close file block. Do not duplicate other needles. Do not edit `commands/*.md`.

**Step 2:**

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

Expected: ALL GREEN guardrails. Inventory fails on `coordinator_hash` until Task 7 — do not pin. If body_budget trips, raise `agents.delivery-coordinator.lines` only as much as needed.

**Step 3: Commit**

```bash
git add agents/delivery-coordinator.md scripts/body_budget.json
git commit -m "feat: coordinator names the close.md hook bounce"
```

(Omit `body_budget.json` if unchanged.)

---

### Task 5: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`

**Step 1:** Do **not** retitle to `[2.0.0]`. Add a **Changed** (or **Added**) bullet: PreToolUse hook bounces `close.md` Writes that are not helper shape. Do not claim the billed gate passed.

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: Unreleased close.md shape hook"
```

---

### Task 6: Gemini / Codex mirrors (coordinator body)

**Files:** generated trees only, if Task 4 changed the coordinator.

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

```bash
git add gemini/ codex/
git commit -m "chore: rebuild Gemini and Codex mirrors for close.md hook"
```

If the rebuild produces no diff, do not empty-commit. If Task 3 already rebuilt after the hook file existed, this commit is coordinator-body only.

---

### Task 7: Billed `feature` pin

**Do not run until Tasks 1–6 are green locally** (`./tests/guardrails.test.sh`; inventory may still be hash-red until this pin).

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature
```

Receipt: `docs/evals/2026-08-21-run-16.md` (or next date). Record: close file PASS/FAIL, basename PASS/FAIL, whether the workdir `close.md` starts `VERIFIED:`, cost vs $8.50, timeout or not, tokens vs 14.5M. Pin `coordinator_hash`. `waivers: []`.

**If `check_delivery_close_file` PASSes** and the basename check PASSes: bump `VERSION` + the five manifests to **2.0.0**. Retitle changelog `[2.0.0]`. Move the Open row to Closed. Commit `release: 2.0.0 — Supervisor complete (close file on disk)`.

**If either file check FAILs:** pin the hash anyway, leave VERSION at 1.45.0, leave Unreleased. Commit `docs: eval run 16 — <what missed>`. Do not loosen the helper. Do not raise ceilings.

Do not tag until CI is green on the PR.

---

## Out of bounds

- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s / 14.5M tokens
- Accepting `VERIFIED (`
- Editing the nine-command Interface block
- Peer handoff, router agent, `graph.md`
- Replacing the hook with a louder prompt-only ban
