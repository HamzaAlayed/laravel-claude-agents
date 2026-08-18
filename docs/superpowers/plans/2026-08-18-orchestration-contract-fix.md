# Orchestration Contract Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 2026-08-12 orchestration audit's 3 Blocking + 5 Should-fix findings so command-driven runs actually refuse to build/patch and verify before advancing, then ship that plus `/audit-agents` as v1.42.0.

**Architecture:** Same move as v1.41.0 harvest: append a compact clause to the shared, byte-identical Interface paragraph in all 9 pipeline commands (TDD via two new guardrail ratchets), then patch the coordinator routing table and Working-interface note (TDD via five more ratchets). A billed `feature` run re-pins `coordinator_hash`. Version bump and changelog last.

**Tech Stack:** Markdown command/agent prompt files, Bash guardrails (`tests/guardrails.test.sh`), `scripts/check_inventory_sync.py`, `scripts/build-gemini-extension.py` / `scripts/build-codex-extension.py`, billed `./tests/eval/run-evals.sh feature`.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-08-18-orchestration-contract-fix-design.md` (approved 2026-08-18).
- **9 pipeline commands only** for the Interface edit: `commands/{add-policy,audit-n-plus-one,add-test,review-pr,refactor-to-action,make-feature,optimize-query,upgrade-laravel,ship-checklist}.md`. Do not add an Interface block to `audit-agents.md`.
- **Do not put the 8 Nits in the Interface paragraph.**
- **Do not silently bump `coordinator_hash`.** Inventory sync will fail after Tasks 2–3 until Task 6's billed run re-pins it. That red is expected.
- **Gemini/Codex are generated.** Edit `commands/*.md` and `agents/*.md`, then run the builders. Do not hand-edit `gemini/commands/*.toml`.
- **Baseline at plan-writing:** guardrails 143/143, eval units 67/67, inventory `ok` at 1.41.0, hash pin `3d7b873c5110…` as_of 2026-08-07.

---

## File Structure

- **Modify:** `tests/guardrails.test.sh` — two Interface ratchets (Task 1) + five coordinator ratchets (Task 3).
- **Modify:** the 9 pipeline command files listed above (Task 2).
- **Modify:** `agents/delivery-coordinator.md` (Task 3).
- **Modify:** `tests/eval/README.md` (Task 4).
- **Create:** `docs/evals/2026-08-18-run-9.md` (Task 6).
- **Modify:** `tests/eval/baseline.json` (Task 6, hash pin only).
- **Modify:** `VERSION` + five manifests + `CHANGELOG.md` + milestone spec header (Task 7).
- **Generated:** `python3 scripts/build-gemini-extension.py` and `python3 scripts/build-codex-extension.py` after Tasks 2 and 7.

---

### Task 1: Failing Interface ratchets

**Files:**
- Modify: `tests/guardrails.test.sh` (insert after the harvest Write+Edit expect, currently ending ~line 341)

**Step 1: Write the failing tests**

Insert immediately after the `expect "every command with the harvest clause also grants Write + Edit"` block:

```bash
# Orchestration-audit Blocking findings (docs/evals/2026-08-12-orchestration-audit.md):
# write-scope, never-patch, and verify-before-advancing lived only in
# agents/delivery-coordinator.md, which command-driven runs never load.
# Same shape as harvest (v1.41.0). The compact clause lives in the shared
# Interface block.
expect "Interface block refuses to build or patch specialist files" "9" \
  "$(grep -l 'You do not build and you do not patch' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block requires verify-before-advancing" "9" \
  "$(grep -l 'Verify before advancing' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

**Step 2: Run them and confirm they fail for the right reason**

```bash
./tests/guardrails.test.sh 2>&1 | grep -A2 -E 'refuses to build|verify-before-advancing|total:'
```

Expected: both new expects FAIL (got `0`, want `9`). Existing 143 still pass. Total 143 passed, 2 failed.

If they already pass, stop — the clause is already in the commands and this task has nothing to catch.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet the build/patch and verify-before-advancing Interface clauses"
```

---

### Task 2: Append the Interface clause to all 9 commands

**Files:**
- Modify: the 9 pipeline command files (one shared sentence).
- Generated: Gemini + Codex mirrors.

**Step 1: Apply the clause**

The needle below is currently present exactly once in each of the 9 files (verified 2026-08-18). Do not edit `commands/audit-agents.md`.

```bash
python3 - << 'PY'
from pathlib import Path
files = [
    "commands/add-policy.md",
    "commands/audit-n-plus-one.md",
    "commands/add-test.md",
    "commands/review-pr.md",
    "commands/refactor-to-action.md",
    "commands/make-feature.md",
    "commands/optimize-query.md",
    "commands/upgrade-laravel.md",
    "commands/ship-checklist.md",
]
old = "A single-specialist ask has nothing to harvest — skip both. Stage returns are internal"
new = (
    "A single-specialist ask has nothing to harvest — skip both. "
    "**You do not build and you do not patch** — Write/Edit only under `docs/**`; "
    "never edit a specialist's files to \"just fix it\" (re-brief or escalate). "
    "**Verify before advancing** — re-run that brief's success criteria yourself; "
    "a specialist's `STATUS: done` is a claim, not a `✔`. "
    "Stage returns are internal"
)
for f in files:
    p = Path(f)
    text = p.read_text()
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{f}: expected 1 occurrence of needle, found {n}")
    p.write_text(text.replace(old, new, 1))
    print("ok", f)
PY
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
```

Expected: 9 `ok` lines, both builders exit 0.

**Step 2: Confirm identity + ratchets green, hash red**

```bash
./tests/guardrails.test.sh 2>&1 | grep -E 'refuses to build|verify-before-advancing|byte-identical|total:'
python3 scripts/check_inventory_sync.py; echo "inventory exit: $?"
```

Expected:
- both new expects PASS (9)
- `Interface block is byte-identical across them` still PASS (1)
- total: 145 passed, 0 failed
- inventory FAIL with `delegation-steering surfaces changed` and a new hash prefix. Do not update the pin.

**Step 3: Commit**

```bash
git add commands/add-policy.md commands/audit-n-plus-one.md commands/add-test.md \
  commands/review-pr.md commands/refactor-to-action.md commands/make-feature.md \
  commands/optimize-query.md commands/upgrade-laravel.md commands/ship-checklist.md
git status --short   # add any gemini/ and codex/ diffs the builders produced
git add -u gemini/commands/ codex/ 2>/dev/null || true
git status --short
git commit -m "fix: command-driven runs refuse to build/patch and must verify before advancing"
```

If the builders rewrote files outside `gemini/commands/` or `codex/`, include those too — they are generated from the same source.

---

### Task 3: Coordinator Should-fix (note + routing table)

**Files:**
- Modify: `tests/guardrails.test.sh` (five expects after `COORD=` is assigned, currently ~line 347)
- Modify: `agents/delivery-coordinator.md`

`$COORD` is assigned *after* the Interface expects. Put these ratchets after that assignment, not with Task 1's expects.

**Step 1: Write the failing tests**

Immediately after `COORD="$SCRIPT_DIR/agents/delivery-coordinator.md"`:

```bash
# Orchestration-audit Should-fix (docs/evals/2026-08-12-orchestration-audit.md):
# Dimension 3 — Working interface is a deliberate Interface-contract superset.
# Dimension 4 — four specialist docs/ paths missing from the routing table.
expect "coordinator Working interface documents itself as an Interface-contract superset" "1" \
  "$(grep -c 'own superset of the shared Interface contract' "$COORD")"
expect "routing table names tech-lead tech-debt artifact" "1" \
  "$(grep -c 'docs/tech-debt.md' "$COORD")"
expect "routing table names product-owner backlog.md" "1" \
  "$(grep -c 'docs/backlog/backlog.md' "$COORD")"
expect "routing table names design system.md" "1" \
  "$(grep -c 'docs/design/system.md' "$COORD")"
expect "routing table names database-developer migration docs" "1" \
  "$(grep -c 'docs/db/<migration>.md' "$COORD")"
```

**Step 2: Run them and confirm they fail**

```bash
./tests/guardrails.test.sh 2>&1 | grep -E 'superset|tech-debt|backlog.md|system.md|migration docs|total:'
```

Expected: five FAIL (got `0`, want `1`). Interface ratchets from Task 2 still pass. Total 145 passed, 5 failed.

**Step 3: Apply the coordinator edits**

Under `## Working interface`, replace:

```
## Working interface

The human sees three shapes from you, and only these:
```

with:

```
## Working interface

This section is delivery-coordinator's own superset of the shared Interface contract the 9 pipeline commands carry. Omitting that blockquote here is deliberate: a command-driven run never loads this file, and this section binds the coordinator agent when it is spawned.

The human sees three shapes from you, and only these:
```

Do **not** include the substring `> **Interface:**` in that note — Dimension 3 of `/audit-agents` identifies Interface blocks by that marker.

In the routing table, replace these four lines (exact current text):

```
| Prioritization    | `product-owner`      | `docs/backlog/<story-id>.md`, roadmap entry             |
```

```
| Design            | `ui-ux-designer`     | `docs/design/<feature>/*`                               |
```

```
| Database impl     | `database-developer` | Migrations, models, factories, seeders                  |
```

```
| Code review       | `tech-lead`          | Review findings (no code edits)                         |
```

with:

```
| Prioritization    | `product-owner`      | `docs/backlog/<story-id>.md`, `docs/backlog/backlog.md`, roadmap entry |
```

```
| Design            | `ui-ux-designer`     | `docs/design/<feature>/*`, `docs/design/system.md`      |
```

```
| Database impl     | `database-developer` | Migrations, models, factories, seeders, `docs/db/<migration>.md` |
```

```
| Code review       | `tech-lead`          | Review findings (no code edits)                         |
| Tech debt         | `tech-lead`          | `docs/tech-debt.md`                                     |
```

**Step 4: Confirm ratchets green, hash still red**

```bash
./tests/guardrails.test.sh 2>&1 | tail -5
python3 scripts/check_inventory_sync.py; echo "inventory exit: $?"
```

Expected: total 150 passed, 0 failed. Inventory still FAIL on coordinator hash (both the Interface line and this file's bytes changed). Still do not update the pin.

**Step 5: Commit**

```bash
git add tests/guardrails.test.sh agents/delivery-coordinator.md
git commit -m "fix: document coordinator Interface-superset + close four routing-table gaps"
```

---

### Task 4: Correct the feature-case negative-control claim

**Files:**
- Modify: `tests/eval/README.md` lines 87–89

**Step 1: Replace the stale sentence**

Change:

```
Its `check_delegated` assertion is the load-bearing one, and it is negative-
controlled: a stub that scaffolds a *correct* Tag feature entirely inline passes
nine of ten checks and fails exactly that one.
```

to:

```
Its `check_delegated` assertion is the load-bearing one, and it is negative-
controlled: a stub that scaffolds a *correct* Tag feature entirely inline fails
that check, and also the two harvest checks (harvest is gated on ≥2 specialists,
so an inline run correctly skips both files). The other seven checks pass.
```

**Step 2: Confirm inventory still only fails on the hash** (this README sentence is not an inventory CLAIM)

```bash
python3 scripts/check_inventory_sync.py; echo "inventory exit: $?"
```

Expected: still the coordinator-hash error only.

**Step 3: Commit**

```bash
git add tests/eval/README.md
git commit -m "docs(evals): inline Tag stub fails delegated plus harvest, not one check of ten"
```

---

### Task 5: Prove `/audit-agents`

**Files:** none kept. A DRIFT-FOUND report written during this task is deleted before commit.

This is the spec's Task 4, which the audit work never evidenced.

**Step 1: Empty-diff short-circuit (free, no Agent calls)**

```bash
git diff --name-only HEAD...HEAD -- 'agents/*.md' 'commands/*.md' 'hooks/**'
```

Expected: empty output. That is the command's `$FILES` empty path. Print (do not spawn reviewers):

```
CLEAN — no agent-facing files changed vs HEAD
```

**Step 2: Full scan**

Follow `commands/audit-agents.md` with no `$BASE`: fan out the 5 dimension reviewers in parallel over `agents/*.md`, `commands/*.md`, `hooks/hooks.json`, `scripts/*.sh`, `docs/read-only-by-design.md`. Aggregate with that command's Blocking / Should-fix / Nit rules.

Expected verdict: **CLEAN**. Remaining items must be Nits only (the 8 from the 2026-08-12 report that this release explicitly parked). Any Blocking or Should-fix means Tasks 2–3 missed; stop and fix before Task 6.

If the command writes `docs/evals/$(date +%F)-audit-agents.md` despite a CLEAN verdict, delete it — CLEAN is print-only.

**Step 3: Confirm `commands/audit-agents.md` is not a Dimension-3 finding**

Its documented-exception note must suppress the missing-Interface-block flag. If it is reported, strengthen Dimension 3's exception clause in `commands/audit-agents.md` (and the copies in the 2026-08-12 plan/spec), then re-run Step 2.

**Step 4: No commit unless Step 3 required a prompt fix.**

---

### Task 6: Billed `feature` run and hash re-pin

**Files:**
- Create: `docs/evals/2026-08-18-run-9.md`
- Modify: `tests/eval/baseline.json` (`coordinator_hash` block only)

Already approved 2026-08-18. Last comparable run (run 8) was $3.44 / 726s.

**Step 1: Run**

```bash
./tests/eval/run-evals.sh feature
```

Expected: the `feature` answer key's 10 checks pass, including harvest (`docs/team/stack.md` + `docs/delivery/*/log.md`) and closing `VERIFIED` / `NOT-CHECKED`. If harvest fails, that is a regression of v1.41.0 — stop and escalate; do not loosen the checks.

Qualitatively read the transcript for the new Interface rules (main thread did not edit app code; a `✔` was preceded by verification the orchestrator itself ran). The harness cannot see per-stage specialist returns ([run 8](../../evals/2026-08-12-run-8.md)); do not re-add `check_stage_return_shape`.

**Step 2: Write the run record**

Create `docs/evals/2026-08-18-run-9.md` in the same shape as `docs/evals/2026-08-12-run-8.md`: trigger (this plan, Task 6), score, cost, duration, run id, what the new Interface clause looked like in the transcript, harvest evidence (paths exist with run-specific content), anything still open.

**Step 3: Re-pin the hash**

```bash
python3 - << 'PY'
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("cis", "scripts/check_inventory_sync.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(m.coordinator_hash(Path(".")))
PY
```

In `tests/eval/baseline.json`, replace the `coordinator_hash` object with:

```json
"coordinator_hash": {
  "sha256": "<hex from Step 3>",
  "as_of": "2026-08-18",
  "note": "Verified by the v1.42.0 billed feature run (2026-08-18, docs/evals/2026-08-18-run-9.md): Interface-block edit (build/patch refusal + verify-before-advancing) plus coordinator routing-table/Working-interface note. Harvest still fired (docs/team/stack.md + a docs/delivery/*/log.md), confirmed by reading the files. Score: <N/10 from Step 1>.",
  "waivers": []
}
```

Fill `<hex>` and `<N/10>` from the actual run. Do not leave the placeholder.

**Step 4: Confirm inventory green**

```bash
python3 scripts/check_inventory_sync.py
```

Expected: `ok: every manifest declares 1.41.0; inventory claims match disk — …` (version bump is Task 7). Exit 0.

**Step 5: Commit**

```bash
git add docs/evals/2026-08-18-run-9.md tests/eval/baseline.json
git commit -m "test(evals): re-pin coordinator_hash from the 1.42.0 feature run"
```

---

### Task 7: Release 1.42.0

Same ritual as 1.41.0.

**Step 1: Bump `1.41.0` → `1.42.0` in `VERSION` + the 5 manifests**

```bash
python3 - << 'PY'
import re, pathlib
root = pathlib.Path(".")
files = [
    "VERSION",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
    ".cursor-plugin/marketplace.json",
    "gemini/gemini-extension.json",
]
for f in files:
    p = root / f
    text = p.read_text()
    new_text, n = re.subn(r"1\.41\.0", "1.42.0", text)
    p.write_text(new_text)
    print(f, "->", n, "replacement(s)")
PY
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
python3 scripts/check_inventory_sync.py
```

Expected: each file reports at least 1 replacement (`marketplace.json` may report 2). Inventory prints `every manifest declares 1.42.0`.

**Step 2: CHANGELOG section above `## [1.41.0]`**

```markdown
## [1.42.0] - 2026-08-18

### Added

- **`/audit-agents`** — a free, repeatable static check of the pack's own
  orchestration contract (Interface placement, tool-grant coverage,
  stage-return consistency, artifact routing, read-only enforcement).
  Diff-scoped against a base branch, or a full scan. Verdict is CLEAN or
  DRIFT-FOUND. Report-only; it never edits files.

### Fixed

- **Command-driven runs now refuse to build or patch, and they verify
  before marking a stage done.** The 2026-08-12 orchestration audit found
  three rules that bound only `delivery-coordinator.md` — a file
  `/make-feature` and its 8 siblings never load. Same shape as the harvest
  miss in v1.41.0. The shared Interface block now says: Write/Edit only
  under `docs/**`; never edit a specialist's files to "just fix it";
  re-run the brief's success criteria yourself — a specialist's
  `STATUS: done` is a claim, not a `✔`. <1–2 sentences on run 9's actual
  outcome from docs/evals/2026-08-18-run-9.md.>

- **Coordinator routing table names the four specialist docs/ paths it
  was missing** (`docs/tech-debt.md`, `docs/db/<migration>.md`,
  `docs/design/system.md`, `docs/backlog/backlog.md`), and Working
  interface now states it is a deliberate superset of the shared
  Interface contract.

### Changed

- **The milestone's originally-planned Adoption release is renumbered
  v1.43.0.** v1.41.0 took the first slide (harvest); this release takes
  the second (audit contract repair). Adoption's content (README
  quickstart, docs index, onboarding guide) is unchanged.
```

Fill the run-9 sentence from Task 6 before committing.

**Step 3: Slide Adoption in the milestone spec header**

In `docs/superpowers/specs/2026-08-06-prove-it-milestone-design.md`, replace the title and the `**Renumbered 2026-08-07:**` paragraph with:

```markdown
# "Prove it" milestone — trust, capability, adoption (v1.39 → v1.43)

**Renumbered 2026-08-18:** what this doc calls "Release 1.41.0 — Adoption"
below actually ships as **v1.43.0**. v1.41.0 went to the harvest Interface
fix; v1.42.0 went to the orchestration-audit contract repair
(`docs/superpowers/specs/2026-08-18-orchestration-contract-fix-design.md`).
Adoption's own content is unchanged; only its version number moved (twice).
```

**Step 4: All local gates**

```bash
./tests/guardrails.test.sh
python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py'
python3 scripts/check_inventory_sync.py
bash -n tests/eval/run-evals.sh
shellcheck scripts/*.sh tests/*.sh tests/eval/*.sh gemini/scripts/*.sh codex/install-codex.sh codex/.codex/hooks/*.sh
shellcheck --severity=error install.sh
git diff --exit-code -- scripts/console/dist
```

Expected: guardrails 150/150, eval units 67/67, inventory `ok` at 1.42.0, syntax OK, shellcheck clean, dist untouched.

**Step 5: Commit**

```bash
git add VERSION .claude-plugin/plugin.json .claude-plugin/marketplace.json \
  .cursor-plugin/plugin.json .cursor-plugin/marketplace.json gemini/gemini-extension.json \
  CHANGELOG.md docs/superpowers/specs/2026-08-06-prove-it-milestone-design.md
git status --short   # add generator-produced diffs
git commit -m "release: 1.42.0 — command-driven runs bound by the audit's Blocking rules"
```

Do not push, merge, or tag in this task. Push/PR is a human choice after review.

---

## Self-Review Notes

- **Spec coverage:** Interface clause → Tasks 1–2. Should-fix → Task 3. README negative-control → Task 4. `/audit-agents` proof → Task 5. Billed hash re-pin → Task 6. Version/changelog/Adoption slide → Task 7. All spec sections have a task.
- **Placeholder scan:** run-9 cost/score and the changelog's run-9 sentence are filled from Task 6's actual output, same convention as the harvest plan. No TBD.
- **Hash gate:** Tasks 2–5 expect inventory red; only Task 6 turns it green. A pin update before the billed run is a spec violation.
