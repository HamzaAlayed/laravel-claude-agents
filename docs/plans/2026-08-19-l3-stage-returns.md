# L3 Stage-Return Files Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the existing Interface loop measurable by persisting each specialist's six-field return as `docs/delivery/<name>/stages/<agent>.md`, then asserting those files in the opt-in `feature` eval.

**Architecture:** Nested Claude Code turns are `tool_use` only (`$SUBAGENT_LOG` empty on run 10). Writers persist the return with Write. The coordinator Reads the file before `✔`. Read-only specialists cannot Write; the coordinator persists their stage file after filing their report (existing persist duty). Evals grep the files, never `$SUBAGENT_LOG`.

**Tech Stack:** Markdown agent/command bodies, bash guardrails + eval harness, Gemini/Codex rebuild scripts, one billed `claude -p` `feature` run.

**Spec:** [docs/plans/2026-08-19-l3-stage-returns-design.md](2026-08-19-l3-stage-returns-design.md)

---

## Global constraints

- No new command, agent, console scene, or daemon.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` `max_usd` (stays **$8.50**).
- Do **not** merge `feat/agent-cost-instrument`.
- Interface block stays **one** distinct line across the 9 pipeline commands.
- `checks_*` never grep `stream.jsonl`.
- Coordinator still does not patch a **writer's** app files or stage file.
- Release when billed proof lands: **1.45.0**. Do not bump VERSION until Task 7.
- Repo root: `/Users/developer/Projects/Personal/laravel-claude-agents`.

**Nine pipeline commands** (only these carry Interface):

`commands/{add-policy,audit-n-plus-one,add-test,optimize-query,make-feature,refactor-to-action,ship-checklist,review-pr,upgrade-laravel}.md`

Do not add Interface to `board.md`, `console.md`, `teach.md`, `team-hygiene.md`, `audit-agents.md`.

**Writers (13)** — have Write, not coordinator: `backend-developer`, `business-analyst`, `database-developer`, `devops-engineer`, `frontend-developer`, `mobile-developer`, `package-developer`, `product-owner`, `qa-engineer`, `scrum-master`, `solution-architect`, `technical-writer`, `ui-ux-designer`.

**Read-only (3)** — `disallowedTools: Write`: `tech-lead`, `security-engineer`, `performance-engineer`.

**Coordinator:** `delivery-coordinator` — Reads stage files; persists read-only ones; never writes a writer's.

---

### Task 1: Failing guardrails for the new contract

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1: Write the failing ratchets**

Insert immediately after the existing `Interface block requires verify-before-advancing` expect (around line 349):

```bash
expect "Interface block requires stage returns on disk" "9" \
  "$(grep -l 'Stage returns land on disk' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

Insert in the coordinator/static-ratchet section (after the verify-before-advancing block is fine; keep near other Interface expects):

```bash
expect "thirteen writer agents require a last-Write stage file" "13" \
  "$(grep -l 'as your last Write' "$SCRIPT_DIR"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "three read-only agents defer the stage file to the coordinator" "3" \
  "$(grep -l 'coordinator persists your stage file' "$SCRIPT_DIR"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "coordinator never writes a writer stage file" "1" \
  "$(grep -c 'never write a writer'\''s stage file' "$COORD")"
expect "coordinator Reads the stage file before a checkmark" "1" \
  "$(grep -c 'Read that file before' "$COORD")"
```

The coordinator greps use `$COORD`, already set earlier in the file. If the `never write a writer's stage file` apostrophe is painful in the test, grep the unique substring `never write a writer` instead — then use that same substring in the coordinator body.

After the existing `expect "the opt-in case asserts that work was delegated"` block (~line 650), add:

```bash
expect "the opt-in case asserts stage-return files" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_stage_return_files')"
expect "the opt-in case does not enable check_subagent_log" "0" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "^[[:space:]]*check_subagent_log ")"
```

After the existing `check_subagent_log does not read the raw transcript` expects, add:

```bash
expect "check_stage_return_files does not read the raw transcript" "0" \
  "$(sed -n '/^check_stage_return_files()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
```

**Step 2: Run the new expects and confirm they fail**

Run: `./tests/guardrails.test.sh 2>&1 | rg -n "FAIL|land on disk|last-Write|stage-return files|check_stage_return_files"`

Expected: those new expects FAIL (phrase missing). Existing 152 still pass. Do not "fix" by weakening the expect.

**Step 3: Leave uncommitted** (or commit locally). Do **not** push: CI runs `tests/guardrails.test.sh` and this step is red until Tasks 2–5 land. Prefer one commit at the end of Task 2 that includes these ratchets plus the Interface sentence.

---

### Task 2: Shared Interface sentence (9 commands)

**Files:**
- Modify: the 9 pipeline commands listed above
- Modify: `tests/eval/baseline.json` (dated waiver only)
- Modify: Gemini/Codex mirrors via rebuild

**Step 1: Insert the sentence**

In every Interface blockquote, after the Demand sentence (the one ending `re-brief once naming the gap).`) and before `Human decision needed`, insert exactly:

` **Stage returns land on disk** — brief each specialist with \`docs/delivery/<name>/stages/<agent>.md\`; writers Write the six fields there as their last act; Read that file before \`✔\`; never write a writer's stage file for them. Read-only specialists (\`disallowedTools: Write\`) — persist their stage file from the report you already file, same as their other artifacts.`

The result must remain **one physical line** starting with `> **Interface:**` (the whole paragraph is one line today; keep it that way). Do not wrap.

Apply the identical insertion to all 9 files. Do not touch non-pipeline commands.

**Step 2: Confirm byte-identity**

```bash
grep -h '^> \*\*Interface:\*\*' commands/*.md | sort -u | wc -l
```

Expected: `1`

```bash
grep -l 'Stage returns land on disk' commands/*.md | wc -l
```

Expected: `9`

**Step 3: Waiver so CI can see the Interface change before the billed run**

In `tests/eval/baseline.json`, under `coordinator_hash.waivers`, add one object:

```json
{
  "sha256": "<output of: python3 -c \"from pathlib import Path; import sys; sys.path.insert(0,'scripts'); import importlib.util; spec=importlib.util.spec_from_file_location('c','scripts/check_inventory_sync.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(m.coordinator_hash(m.ROOT))\">",
  "date": "2026-08-19",
  "reason": "Interface stage-return-on-disk sentence; billed feature re-pin is plan Task 7"
}
```

Easier: after the Interface edit,

```bash
python3 - <<'PY'
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("inv", "scripts/check_inventory_sync.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(m.coordinator_hash(m.ROOT))
PY
```

Paste that hex into the waiver `sha256`. Leave the existing pin + `as_of` untouched.

**Step 4: Rebuild mirrors**

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
```

Commit whatever those scripts dirty for the 9 commands / agent copies.

**Step 5: Local gate (hash waived)**

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

Expected: Interface-on-disk expect now **passes**. Writer/read-only/coordinator/eval expects still **fail** until later tasks. Inventory `ok` because of the waiver.

If you need a green guardrails file before Task 3, do not delete the failing expects — finish Task 3–6 in this session.

**Step 6: Commit** (include whatever gemini/codex actually changed)

```bash
git add commands/add-policy.md commands/audit-n-plus-one.md commands/add-test.md \
  commands/optimize-query.md commands/make-feature.md commands/refactor-to-action.md \
  commands/ship-checklist.md commands/review-pr.md commands/upgrade-laravel.md \
  tests/eval/baseline.json
# plus gemini/ and codex/ paths from git status
git commit -m "$(cat <<'EOF'
feat: demand stage-return files in the shared Interface block

EOF
)"
```

---

### Task 3: Writer agents + authoring guide + template

**Files:**
- Modify: the 13 writer files under `agents/`
- Modify: `docs/authoring-agents.md`
- Modify: `skills/delivery-templates/SKILL.md`

**Step 1: Append the writer clause**

At the **end** of each of the 13 writer bodies, append:

```markdown

## Stage return

**Stage return file.** The brief names `docs/delivery/<name>/stages/<your-agent>.md` → Write that file with `STATUS` / `DID` / `VERIFIED` / `NOT-CHECKED` / `FLAGS` / `NEXT` (≤12 lines) as your last Write, then stop. No path in the brief → skip. No diffs in the file.
```

Use the registered filename as `<your-agent>` only in prose if you must; keep the placeholder `<your-agent>` so all 13 stay greppable with `as your last Write`.

**Step 2: Authoring guide**

In `docs/authoring-agents.md`, add a short subsection under "Anatomy" or "Checklist": writers with Write persist that path as last Write; read-only agents cannot; coordinator persists those. Checklist bullet: **Has the stage-return clause** matching writer vs read-only.

**Step 3: Template**

In `skills/delivery-templates/SKILL.md`, after the Delivery log section, add:

```markdown
## Stage return — `docs/delivery/<feature>/stages/<agent>.md` (specialist writes; coordinator Reads)

One file per registered agent type. Latest return wins (overwrite). History lives in `log.md`.

```
STATUS: done | blocked | needs-decision
DID: files / artifacts touched, one line each
VERIFIED: command → result (counts, `file:line`) — not claims
NOT-CHECKED: surfaces not examined, ≤3 lines — or none
FLAGS: corrections, risks, checkpoints — or none
NEXT: handoff or none
```

≤12 lines. Coordinator Reads this file before `✔`. Direct invoke with no path: do not create `docs/delivery/unknown/`.
```

(Nested fences: in the skill file use a markdown code block as other templates do — indented triple-backtick matching the Stack snapshot style.)

**Step 4: Confirm ratchets**

```bash
grep -l 'as your last Write' agents/*.md | wc -l
```

Expected: `13`

**Step 5: Commit**

```bash
git add agents/*.md docs/authoring-agents.md skills/delivery-templates/SKILL.md
git commit -m "$(cat <<'EOF'
feat: writers persist six-field stage returns as their last Write

EOF
)"
```

Do not add the 3 read-only agents or the coordinator in this commit.

---

### Task 4: Read-only agents + coordinator

**Files:**
- Modify: `agents/tech-lead.md`, `agents/security-engineer.md`, `agents/performance-engineer.md`
- Modify: `agents/delivery-coordinator.md`

**Step 1: Read-only clause**

Append to each of the 3:

```markdown

## Stage return

**Stage return.** You cannot Write. End your report with `STATUS` / `DID` / `VERIFIED` / `NOT-CHECKED` / `FLAGS` / `NEXT` (≤12 lines). The coordinator persists your stage file at `docs/delivery/<name>/stages/<your-agent>.md`. No path in the brief → skip.
```

Phrase `coordinator persists your stage file` must appear (guardrail).

**Step 2: Coordinator Working interface**

In `agents/delivery-coordinator.md`, under **Stage return**, after the six-field example fence, add:

```markdown
Each specialist lands that shape at `docs/delivery/<name>/stages/<agent>.md`. Read that file before `✔`. Never write a writer's stage file for them. Read-only specialists (`tech-lead`, `security-engineer`, `performance-engineer`) — persist their stage file from the report you already file, same as their other artifacts.
```

In **When invoked** step 4, after "Demand the stage-return shape …", add: name the exact path `docs/delivery/<name>/stages/<agent>.md` in every brief.

In step 5, after "Read each subagent's product.", add: Read `docs/delivery/<name>/stages/<agent>.md` before printing `✔`. Missing file / empty `VERIFIED` / missing `NOT-CHECKED` → re-brief once naming the gap (writer writes; you still never write a writer's stage file). Read-only: persist that path yourself after you persist their report.

**Step 3: Confirm**

```bash
grep -l 'coordinator persists your stage file' agents/*.md | wc -l
# 3
grep -c 'Read that file before' agents/delivery-coordinator.md
# ≥1
grep -c "never write a writer" agents/delivery-coordinator.md
# ≥1
```

**Step 4: Rebuild Gemini/Codex** (agent bodies changed)

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
```

**Step 5: Commit**

---

### Task 5: Eval helper + answer key + audit tally

**Files:**
- Modify: `tests/eval/run-evals.sh`
- Modify: `docs/evals/2026-08-06-check-audit.md`
- Modify: `tests/eval/README.md`
- Modify: `docs/README.md` (Open row points at the spec)

**Step 1: Helper** (next to `check_file_under`)

```bash
check_stage_return_files() { # ≥2 docs/delivery/*/stages/*.md, each with six labels
  local n=0
  local f label
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    n=$((n + 1))
    for label in 'STATUS:' 'DID:' 'VERIFIED:' 'NOT-CHECKED:' 'FLAGS:' 'NEXT:'; do
      if ! grep -q "$label" "$f"; then
        record 1 "file:   stage return missing $label ($(basename "$f"))"
        return
      fi
    done
  done < <(find "$WORK/docs/delivery" -type f -path '*/stages/*.md' 2>/dev/null)
  if [ "$n" -ge 2 ]; then
    record 0 "file:   ≥2 stage-return files with six labels"
  else
    record 1 "file:   ≥2 stage-return files with six labels (found $n)"
  fi
}
```

Do not mention `stream.jsonl` inside this function.

**Step 2: Call it from `checks_feature`**

After `check_file_under "docs/delivery" "log.md" ...`, add:

```bash
  check_stage_return_files
```

Leave the commented `check_subagent_log` lines **commented**. Add a one-line note: per-stage returns are the stage files (this helper); `$SUBAGENT_LOG` stays an instrument (run 10).

**Step 3: Audit table**

Add one row:

`| feature | \`check_stage_return_files\` | artifact | sound — six-field returns on disk; run 10 nested turns had no text |`

Change `Tally: 43 checks — 31 artifact` to **44 checks — 32 artifact**. Other buckets unchanged. `scripts/check_inventory_sync.py` binds this tally — if you get the arithmetic wrong, inventory fails.

**Step 4: `tests/eval/README.md`**

Where it tells people to use `check_subagent_log` for per-stage fields, say: those fields live on `docs/delivery/*/stages/*.md`; `check_stage_return_files` asserts them. `check_subagent_log` stays commented on the run-10 shape.

**Step 5: `docs/README.md` Open row**

Keep the item open until Task 7. Notes: spec [2026-08-19-l3-stage-returns-design.md](plans/2026-08-19-l3-stage-returns-design.md); do not uncomment `check_subagent_log`.

**Step 6: Guardrails should be ALL GREEN**

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py'
bash -n tests/eval/run-evals.sh
```

Expected: guardrails **156 passed, 0 failed** (152 + 4 Interface/agent expects from Task 1 that now pass; the two eval expects in Task 1 also pass — count the new expects you actually added and match that total). Inventory `ok` (tally 44). Eval unit tests unchanged (they do not execute `checks_feature`).

If the pass count is not 156, do not invent expects to hit a number — report the actual `total:` line.

**Step 7: Commit**

---

### Task 6: Docs changelog placeholder (no VERSION bump)

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`

Add a subsection: specialists persist six-field returns under `docs/delivery/<name>/stages/`; coordinator Reads before `✔`; `feature` eval asserts the files; `$SUBAGENT_LOG` still not an answer-key surface.

**Commit** that changelog line.

---

### Task 7: Billed `feature` run — controller-executed, never a subagent

**Not an implementer dispatch.** One opt-in run:

```bash
KEEP_TRANSCRIPT=1 ./tests/eval/run-evals.sh feature
```

Budget: `max_usd` **$8.50**. Stop if the harness kills on money.

**Pass when:**
- Answer key includes `check_stage_return_files` PASS (≥2 files, six labels each)
- Existing harvest + `VERIFIED` / `NOT-CHECKED` still PASS
- Inspect `docs/delivery/*/stages/` in the workdir (or `KEEP_WORKDIR=1`) — writers wrote their own files; if `tech-lead.md` exists it was coordinator-persisted
- `$SUBAGENT_LOG` may still be empty — that is **not** a fail

**Then:**
1. Write `docs/evals/2026-08-19-run-11.md` (or next unused run-N date) — score, cost, whether stage files existed, `$SUBAGENT_LOG` empty or not.
2. Replace `coordinator_hash` pin with the current hash; `as_of` today; `waivers: []`; note pointing at that eval record.
3. Bump `VERSION` and the five manifests to **1.45.0** (same files `check_inventory_sync.py` `VERSIONED` lists). Changelog: retitle Unreleased → `[1.45.0]`.
4. Rebuild Gemini/Codex so extension JSON versions match.
5. Move the Open corpus row to Closed, citing run-11 + this spec.
6. `python3 scripts/check_inventory_sync.py` → `ok`.

If the run **fails** `check_stage_return_files` because writers never wrote the files: do not uncomment `check_subagent_log`; do not raise `max_usd`; file the eval record as FAIL with the workdir listing and stop for a spec amendment.

---

## Out of scope (do not do)

- Console UI
- New eval case
- `check_stage_return_shape` on `$FULL_LOG`
- L4 watchers
