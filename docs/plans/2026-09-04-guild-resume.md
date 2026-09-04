# Guild 2.3.0 resume — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When `docs/delivery/<name>/close.md` is `STATUS: running`, a second `/make-feature` reprints the board from disk and does not Agent skippable `✔` stages.

**Architecture:** Prompt-layer stickiness. Before the first Agent, Read `close.md`. `done`/`stopped` → print four labels and stop. `running` → skip writers whose stage file is `STATUS: done` and a `DID:`/`VERIFIED:` path still exists; skip read-only stage files that are `STATUS: done`; Agent `▶` and `·`. Eval plants a completed `database-developer` stage plus Tag model/migration, then asserts `cost.json` has no `database-developer`.

**Tech Stack:** Agent markdown, byte-identical Interface, guardrail harness, opt-in eval case, Gemini/Codex rebuild, billed `claude -p` pin.

**Spec:** [docs/plans/2026-09-04-guild-resume-design.md](2026-09-04-guild-resume-design.md)

---

## Global constraints

- Branch: `feat/v2.3.0-resume`. Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/v230-resume`. Create it from `main` (after this plan is on `main`). Do **not** reuse `v221-adaptive-persist` or `v222-close-print`. After checkout, verify `VERSION` is `2.2.2` and `HEAD` is this branch. Do **not** call `move_agent_to_root`.
- Do **not** loosen `check_delivery_close_file`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `$8.50` / `EVAL_TIMEOUT` (1200) / 14.5M.
- Interface stays **byte-identical** across the nine pipeline commands.
- Coordinator `grep -c` needles stay **exactly 1**. Resume is one new paragraph. Do not mention `docs/delivery/<name>/close.md` in it (Close file already has that path; count must stay **1**). Do not repeat `copy skills/delivery-templates/close.md`.
- The Graph paragraph already contains `before the first Agent`. The Resume needle is the longer unique string `before the first Agent, if close.md exists`.
- `CLOSE_COORD` is the sed range `**Close file**` … `**Need-to-know briefs**` (Adaptive and Graph already sit inside it). Resume must not add a line matching `^VERIFIED:`, `^NOT-CHECKED:`, `^STATUS: running$`, or `^BOARD:`.
- Coordinator is 162 lines vs budget 179. Raise `scripts/body_budget.json` **only** if a cap exceeds; do not full `--reseed`. Commands are not in that file.
- Do **not** bump `VERSION` until Task 7 PASS.
- Billed evals **only** when the user says **run it**.
- Default `/make-feature` stays Supervisor.
- Do not add `/resume-feature`.
- Do not write `stream.jsonl` inside any `checks_*` or `check_agent_absent` body (comments count — the ratchet greps those functions). Say “raw transcript” if you must.

Nine pipeline commands:

`commands/make-feature.md`, `commands/add-test.md`, `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md`.

### Exact Interface insertion (Task 2)

Find this sentence (keep it):

`After that Write, print `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:` in the same turn.`

Immediately after it, still inside the same `> **Interface:**` blockquote, before `**Spawn cap in the board header**`, insert this sentence (no `**Resume.**` heading):

`Before the first Agent, if `docs/delivery/<name>/close.md` exists: `STATUS: done` or `stopped` → print those four labels and stop; `STATUS: running` → reprint the board from disk, skip a writer whose `stages/<agent>.md` is `STATUS: done` and a path named in `DID:` or `VERIFIED:` still exists, skip a read-only stage file that is `STATUS: done`, Agent `▶` and `·`; remaining spawn cap is `M` minus distinct `stages/*.md` already present.`

Do not change Adaptive or graph sentences. Close print stays.

Joined snippet after the edit (one Interface paragraph, excerpt):

`After that Write, print `VERIFIED:` / `NOT-CHECKED:` / `STATUS:` / `BOARD:` in the same turn. Before the first Agent, if `docs/delivery/<name>/close.md` exists: `STATUS: done` or `stopped` → print those four labels and stop; `STATUS: running` → reprint the board from disk, skip a writer whose `stages/<agent>.md` is `STATUS: done` and a path named in `DID:` or `VERIFIED:` still exists, skip a read-only stage file that is `STATUS: done`, Agent `▶` and `·`; remaining spawn cap is `M` minus distinct `stages/*.md` already present. **Spawn cap in the board header**`

Interface ratchet greps `reprint the board from disk` (no backticks between those words). Count **9**.

### Exact coordinator Resume paragraph (Task 2)

Insert after the Close file skeleton fence and the `` `STATUS` is exactly `running`…`VERIFIED (` `` line, **before** `**Adaptive**`. One paragraph:

`**Resume** — before the first Agent, if close.md exists: STATUS: done or stopped → print VERIFIED: / NOT-CHECKED: / STATUS: / BOARD: from that file and stop; STATUS: running → Read graph.md and stages/*.md, reprint the board, skip a writer whose stage file is STATUS: done and a path named in DID: or VERIFIED: still exists, skip a read-only stage file that is STATUS: done, Agent ▶ and · (overwrite the same stage path). If graph.md already has NODES:/EDGES:/PARALLEL:/ON-FAIL:, do not rewrite it. Remaining spawn cap is M minus distinct stages/*.md already present; remaining 0 → STATUS: stopped, print, stop.`

Coordinator needle (count **1**): `before the first Agent, if close.md exists`

Existing close needles stay count **1**: `overwrite close.md after every stage`, `after every Agent return, the next Write is close.md`, `copy skills/delivery-templates/close.md`, `Bash must not write close.md`, `after that Write, print VERIFIED:`, `docs/delivery/<name>/close.md`.

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1:** After `Interface block prints close labels after the Write`, add:

```bash
expect "Interface block resumes a running close.md" "9" \
  "$(grep -l 'reprint the board from disk' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

After `coordinator prints close labels after the Write`, add:

```bash
expect "coordinator resumes from close.md before the first Agent" "1" \
  "$(grep -c 'before the first Agent, if close.md exists' "$COORD")"
```

After `the Adaptive case does not enable check_subagent_log`, add:

```bash
expect "the resume case asserts skipped database-developer" "1" \
  "$(sed -n '/^checks_feature_resume()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_agent_absent database-developer')"
expect "the resume case does not enable check_subagent_log" "0" \
  "$(sed -n '/^checks_feature_resume()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "^[[:space:]]*check_subagent_log ")"
expect "the resume case is opt-in" "1" \
  "$(sed -n 's/^OPT_IN_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature-resume' || true)"
expect "the resume case stays out of the default sweep" "0" \
  "$(sed -n 's/^ALL_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature-resume' || true)"
expect "check_agent_absent does not read the raw transcript" "0" \
  "$(sed -n '/^check_agent_absent()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
```

Do not edit agents, commands, or `run-evals.sh` in this task.

**Step 2:**

```bash
./tests/guardrails.test.sh
```

Expected: four FAIL (Interface, coordinator, skip assert, opt-in membership — all got 0). Three PASS (no `check_subagent_log` on an empty function, not in `ALL_CASES`, helper has no `stream.jsonl`). Everything else still GREEN (currently 263). Net: **270 expects, 4 FAIL**.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet resume from running close.md"
```

---

### Task 2: Interface + coordinator copy

**Files:**
- Modify: the nine pipeline commands (Interface insertion only)
- Modify: `agents/delivery-coordinator.md` — new Resume paragraph only
- Modify: `scripts/body_budget.json` — only if a cap exceeds; raise **only** exceeded entries. Do not full `--reseed`.

**Step 1:** Apply the exact replacements in Global constraints.

```bash
grep -h '^> \*\*Interface:\*\*' commands/*.md | sort -u | wc -l
```

Expected: `1`.

```bash
COORD=agents/delivery-coordinator.md
grep -c 'overwrite close.md after every stage' "$COORD"
grep -c 'after every Agent return, the next Write is close.md' "$COORD"
grep -c 'copy skills/delivery-templates/close.md' "$COORD"
grep -c 'Bash must not write close.md' "$COORD"
grep -c 'after that Write, print VERIFIED:' "$COORD"
grep -c 'before the first Agent, if close.md exists' "$COORD"
grep -c 'docs/delivery/<name>/close.md' "$COORD"
```

First six print `1`. The close.md path count must stay **1** (Close file paragraph only).

**Step 2:**

```bash
./tests/guardrails.test.sh
```

Expected: Interface + coordinator expects PASS. Skip assert and opt-in membership still FAIL.

**Step 3: Commit**

```bash
git add commands/*.md agents/delivery-coordinator.md
git commit -m "feat: resume a running close.md on the same command"
```

Include `scripts/body_budget.json` only if it changed.

---

### Task 3: `feature-resume` harness + seed

**Files:**
- Modify: `tests/eval/run-evals.sh`
- Seed lives **inside** `seed_feature_resume_fixture()` (same style as `seed_hygiene_fixture`). Do **not** add Tag files to `tests/fixture-app/` (that would pollute `feature`).
- Modify: `tests/eval/baseline.json` — add `feature-resume` under `cases` with the same ceilings as `feature` (`max_seconds` 1900, `max_tokens` 14500000, `max_usd` 8.5). `basis`: “unmeasured; same Tag --api floor as feature until billed pin.” Also change `_opt_in` from “Four cases” to “Five cases” and mention `feature-resume`.
- Modify: `tests/eval/README.md` — add an opt-in row; mention `./tests/eval/run-evals.sh feature-resume`. Keep “the 5 eval cases” / `ALL_CASES` denominator unchanged.
- Modify: `docs/evals/2026-08-06-check-audit.md` — add one artifact row for `feature-resume` / `check_agent_absent`. `Tally: 51` → `Tally: 52` and artifact 38 → 39.

Planted `Tag.php` / tags migration make `checks_feature`'s model and migration file-exists checks PASS from the seed. That is **not** the skip gate. The skip gate is `check_agent_absent`. Routes and tests must still land from later stages.

**Step 1: Helper** (next to `check_delegated`, **before** the `# ------------------------------------------------------------- answer key ----` marker so the definition does not double-count):

```bash
check_agent_absent() { # check_agent_absent <agent> <description>
  local cost="${LOG%.log}.cost.json"
  python3 - "$cost" "$1" <<'PYABSENT' >/dev/null 2>&1
import json, sys
path, agent = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path, encoding="utf-8"))
except Exception:
    sys.exit(1)
attr = data.get("attributed") or {}
agents = attr.get("agents") or {}
launched = attr.get("launched_without_measured_turns") or []
sys.exit(0 if agent not in agents and agent not in launched else 1)
PYABSENT
  record $? "agents: $2"
}
```

Cost JSON is written at ` "$results/$name.cost.json" ` before `checks_*` runs. `$LOG` is `$results/$name.log`, so `${LOG%.log}.cost.json` is that file. Do not mention the raw transcript. Treat `launched_without_measured_turns` as present too — a spawn with no measured turns must still FAIL the skip.

**Step 2: Seed** after `seed_taught_fixture`:

```bash
seed_feature_resume_fixture() { # seed_feature_resume_fixture <workdir>
  local w="$1"
  mkdir -p "$w/docs/delivery/tag/stages" "$w/app/Models" "$w/database/migrations"
  cat >"$w/docs/delivery/tag/close.md" <<'EOF'
VERIFIED: `php artisan test --compact` → 1 passed (baseline ExampleTest)
NOT-CHECKED: Tag HTTP, feature tests, Pint on new files
STATUS: running
BOARD: 4 stages · cap: 6 spawns · done when: POST /api/tags creates a Tag · a ✔ database-developer · b ▶ backend-developer · c · qa-engineer · d · tech-lead
EOF
  cat >"$w/docs/delivery/tag/graph.md" <<'EOF'
NODES: database-developer, backend-developer, qa-engineer, tech-lead
EDGES: database-developer -> backend-developer, backend-developer -> qa-engineer, backend-developer -> tech-lead
PARALLEL: qa-engineer || tech-lead
ON-FAIL: stop
EOF
  cat >"$w/docs/delivery/tag/stages/database-developer.md" <<'EOF'
STATUS: done
DID: app/Models/Tag.php, database/migrations/2026_09_04_000000_create_tags_table.php
VERIFIED: files exist on disk
NOT-CHECKED: HTTP, feature tests
FLAGS: none
NEXT: backend-developer
EOF
  cat >"$w/app/Models/Tag.php" <<'EOF'
<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Tag extends Model
{
    protected $fillable = ['name', 'slug'];
}
EOF
  cat >"$w/database/migrations/2026_09_04_000000_create_tags_table.php" <<'EOF'
<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('tags', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->string('slug')->unique();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('tags');
    }
};
EOF
}
```

Wire next to the other seeds in `run_case` (after `install.sh`, before `git init`):

```bash
  [ "$name" = "feature-resume" ] && seed_feature_resume_fixture "$WORK"
```

**Step 3: Case registration**

- `OPT_IN_CASES=(feature teach teach-delivery feature-adaptive feature-resume)`
- `case_prompt`: `feature-resume) echo "/make-feature Tag --api" ;;`
- `case_desc`: `feature-resume) echo "resume Tag --api; skip completed database-developer" ;;`
- `case_rubric` (four-space indent so `every eval case has a judge rubric` matches `    feature-resume)`):

```bash
    feature-resume) cat <<'EOF'
- A Tag API feature is finished across the remaining layers: an HTTP entry
  point, a registered route, and at least one feature test. Schema and model
  already exist on disk from a prior running close.md.
- The completed database-developer stage is not launched again.
- The work that still runs is DELEGATED to specialists rather than done
  inline by the coordinator.
- The close file stays helper-shaped (verified / not-checked / status).
EOF
      ;;
```

```bash
checks_feature_resume() {
  checks_feature
  check_agent_absent database-developer "resume skipped the completed database-developer stage"
}
```

Do not uncomment `check_subagent_log`. Do not change `check_delivery_close_file`. A coordinator that prints-and-stops on `STATUS: running` (treating it as finished) fails routes/tests/`check_delegated` even if skip PASSes.

**Step 4: README + audit**

In `tests/eval/README.md` Cases table, after the `feature-adaptive` row:

```markdown
| `feature-resume` **(opt-in)** | `/make-feature Tag --api` | same Tag --api floor as `feature`, but the workdir already has a running `close.md` and a completed `database-developer` stage plus Tag model/migration; **attributed agents must not include `database-developer`**; routes and tests still land |
```

Under the opt-in heading, add `./tests/eval/run-evals.sh feature-resume`. Do not retitle the section as if this were the fifth default sweep case.

In `docs/evals/2026-08-06-check-audit.md`, after the last `feature-adaptive` row:

```markdown
| feature-resume | `check_agent_absent database-developer` | artifact | sound — `cost.json` attributed.agents plus launched_without_measured_turns must not name database-developer |
```

**Step 5:**

```bash
./tests/guardrails.test.sh
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
```

Expected: guardrails ALL GREEN (270). Body budget GREEN or one-cap raise. Inventory FAIL only `coordinator_hash`. VERSION `2.2.2`. Audit tally 52. `every eval case has a judge rubric` empty. `every opt-in case has a baseline entry` empty.

**Step 6: Commit**

```bash
git add tests/eval/run-evals.sh tests/eval/baseline.json tests/eval/README.md docs/evals/2026-08-06-check-audit.md
git commit -m "feat(eval): opt-in feature-resume plants a completed db stage"
```

---

### Task 4: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` — fill `[Unreleased]`. Do **not** retitle to `[2.3.0]`.
- Modify: `docs/README.md` — Open row only. Do not add a Closed 2.3.0 row until Task 7.

```markdown
## [Unreleased]

The same `/make-feature` again resumes a `STATUS: running` delivery from
`close.md` and stage files. Completed writer stages whose artifacts still
exist are not re-Agented. Default `/make-feature` stays Supervisor.

### Added

- **Resume.** Before the first Agent, Read `docs/delivery/<name>/close.md`.
  `running` reprints the board from disk and skips skippable `✔` stages.
```

Exact `docs/README.md` Open table (replace the current “No open Guild v2 slice” row):

```markdown
| Guild 2.3.0 resume | [design](plans/2026-09-04-guild-resume-design.md); [plan](plans/2026-09-04-guild-resume.md) — same `/make-feature` continues a running close.md. Gate is billed `feature-resume`. |
```

**Commit:**

```bash
git add CHANGELOG.md docs/README.md
git commit -m "docs: Unreleased 2.3.0 resume"
```

---

### Task 5: Gemini / Codex mirrors

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

Commit only if diff: `chore: rebuild Gemini and Codex mirrors for resume`. If no diff, do not empty-commit.

---

### Task 6: Local verification (no billed run)

```bash
./tests/guardrails.test.sh
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
```

Expected: guardrails GREEN. Body budget GREEN. Inventory FAIL only `coordinator_hash`. VERSION `2.2.2`. Do not commit unless a check forced a missed edit. Stop until the user says **run it**.

---

### Task 7: Billed `feature-resume` pin

**Do not run until Tasks 1–6 are green. Do not run until the user says `run it`.**

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature-resume
```

Receipt: `docs/evals/2026-09-04-run-24.md` (or next date). Record: close file, `$LOG`/`$FULL_LOG` `VERIFIED`/`NOT-CHECKED`, whether `cost.json` attributed agents (or `launched_without_measured_turns`) include `database-developer`, Tag HTTP/tests, harvest, cost vs $8.50, timeout, tokens vs 14.5M. Pin `coordinator_hash`. `waivers: []`.

**If close file PASS and skip PASS (no `database-developer` in attributed agents or `launched_without_measured_turns`) and `VERIFIED`/`NOT-CHECKED` PASS and Tag HTTP/tests PASS:** bump VERSION + five manifests to **2.3.0**. Retitle changelog `[2.3.0]`. Close the Open row. Commit `release: 2.3.0 — resume running close.md`.

**If they FAIL:** pin the hash, leave VERSION at 2.2.2, leave Unreleased. Commit `docs: eval run 24 — <what missed>`. Do not drop `check_agent_absent`. Do not raise ceilings.

Do not tag until CI is green on the PR.

---

## Out of bounds

- `/resume-feature`
- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s / 14.5M
- Loosening `check_delivery_close_file`
- Adding Tag files to `tests/fixture-app/`
- Adaptive as default `/make-feature`
- Two billed kill-then-continue runs
- Console UI
- Full `body_budget.json --reseed`
