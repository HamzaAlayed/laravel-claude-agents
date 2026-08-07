# Harvest Interface Fix (v1.41.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Exception: Task 2 is controller-executed** (billed, must never be dispatched to a subagent).

**Goal:** Make team-memory harvest (`docs/team/stack.md` + `docs/delivery/<name>/log.md`) actually fire on command-driven deliveries, by moving the requirement from `agents/delivery-coordinator.md` — a file `/make-feature` and its 8 sibling commands never load — into the shared `Interface` block those 9 commands already carry.

**Architecture:** One new sentence appended to the existing, byte-identical Interface paragraph in all 9 pipeline commands, guarded by a new ratchet mirroring the exact pattern the v1.36.0 stage-budget fix used for this same class of bug. A billed re-run of `teach-delivery` (the only case whose answer key tests harvest) is the acceptance test.

**Tech Stack:** Markdown command files (no code), bash (guardrails ratchet), the `claude` CLI headless for the billed re-run.

## Global Constraints

- **Harvest scope is `docs/team/stack.md` + `docs/delivery/<name>/log.md` ONLY.** Do not touch `docs/team/conventions.md`/`decisions.md` harvesting — no eval evidence exists on whether that needs the same fix; out of scope for this release.
- **All 9 pipeline commands carry the new clause, byte-identical, unconditionally.** The 9: `commands/{add-policy,audit-n-plus-one,add-test,optimize-query,make-feature,refactor-to-action,ship-checklist,review-pr,upgrade-laravel}.md`.
- **Harvest fires only once ≥2 specialists have reported** — a single-specialist ask has nothing to harvest, mirroring the coordinator's own existing fast-path exemption for the board and delivery log.
- **`agents/delivery-coordinator.md` is not touched by this release.** Its own harvest steps and the 1.40 "await lanes" edit both stay as-is.
- **No new commands, agents, or skills.**
- **Exactly one billed re-run: `teach-delivery`, ~$4-5, pre-approved** (this plan's own approval — no further human sign-off needed to run it) — drawn from the "Prove it" milestone's remaining ~$9.69 of its $30 ceiling. Do **not** re-run `feature`; its answer key doesn't test harvest.
- **This release is v1.41.0.** The milestone's originally-planned Adoption release slides to v1.42.0 — record this in the milestone spec's header in the same commit that ships the harvest clause.
- Repo root: `/Users/developer/Projects/Personal/laravel-claude-agents`.

---

### Task 1: The Interface-block harvest clause + its ratchet

**Files:**
- Modify: `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/add-test.md`, `commands/optimize-query.md`, `commands/make-feature.md`, `commands/refactor-to-action.md`, `commands/ship-checklist.md`, `commands/review-pr.md`, `commands/upgrade-laravel.md` (all 9, identical edit)
- Modify: `tests/guardrails.test.sh` (new ratchet)
- Modify: `docs/superpowers/specs/2026-08-06-prove-it-milestone-design.md` (version-header note)

**Interfaces:**
- Produces: the exact string `this delivery harvests too` present in all 9 command files — Task 2 greps for this string (indirectly, via the guardrail) to confirm the edit landed before spending money on the re-run.

- [ ] **Step 1: Write the failing guardrail test**

Open `tests/guardrails.test.sh` and find this existing block (search for `Interface block requires an up-front stage budget`):

```bash
expect "Interface block requires an up-front stage budget" "9" \
  "$(grep -l 'done when: <the observable' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

Immediately after it, add:

```bash
# Run 7 (docs/evals/2026-08-06-run-7.md) proved harvest never fires for
# command-driven deliveries: agents/delivery-coordinator.md promises it, but
# /make-feature and its 8 siblings never load that file. Same shape as the
# stage-budget finding two lines above, same fix — the contract belongs in
# the shared block, so a headless command run is bound by it too.
expect "Interface block requires harvest once specialists report" "9" \
  "$(grep -l 'this delivery harvests too' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

- [ ] **Step 2: Run the guardrail suite to verify the new test fails**

Run: `./tests/guardrails.test.sh 2>&1 | grep -A1 "harvest once specialists"`
Expected: `FAIL Interface block requires harvest once specialists report (expected exit 9, got 0)` — none of the 9 files carry the string yet.

- [ ] **Step 3: Add the harvest clause to all 9 command files**

Each of the 9 files contains this exact line today (verified byte-identical across all 9 before this change):

```
> **Interface:** Print a progress board after the plan and after every stage — `✔ done / ▶ running / · queued / ✖ failed` + owner + one-line result, so the user never wonders what's running or what's left. The board's header states the stage budget **before** any agent spends tokens — how many stages you expect and the observable condition that ends the run (`N stages · done when: <the observable thing>`); a board that arrives only as a closing summary told the human nothing they could still act on. Growing past that budget is a re-plan: reprint the header with the new count and why it grew. Demand each specialist return `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines; an empty VERIFIED is a claim, a missing NOT-CHECKED is uncalibrated — either → re-brief once naming the gap). Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). Stage returns are internal; this is the only calibration the human ever sees, so a run that ends without it is unfinished.
```

In **each of the 9 files**, replace this substring:

```
or "none"). Stage returns are internal;
```

with this substring (note: the `\`` backtick characters below are literal — this is Markdown, not a code block needing escaping when you write it into the file):

```
or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. Stage returns are internal;
```

Apply this identical substitution to all 9 files listed above. Do not touch `commands/board.md`, `commands/console.md`, `commands/teach.md`, or `commands/team-hygiene.md` — they never carried the Interface block and must not gain it now.

- [ ] **Step 4: Verify all 9 files are still byte-identical to each other**

Run:
```bash
grep -h '^> \*\*Interface:\*\*' commands/*.md | sort -u | wc -l
```
Expected: `1` (one distinct line across whichever files match the grep — this is the same assertion `tests/guardrails.test.sh` makes; confirms no file got a typo'd variant).

- [ ] **Step 5: Run the guardrail suite to verify the new test passes**

Run: `./tests/guardrails.test.sh 2>&1 | tail -3`
Expected: `total: 142 passed, 0 failed` / `ALL GREEN` (141 existing + 1 new).

- [ ] **Step 6: Record the version renumber in the milestone spec**

Open `docs/superpowers/specs/2026-08-06-prove-it-milestone-design.md`. Find its header line:

```
# "Prove it" milestone — trust, capability, adoption (v1.39 → v1.41)
```

Replace it with:

```
# "Prove it" milestone — trust, capability, adoption (v1.39 → v1.42)

**Renumbered 2026-08-07:** what this doc calls "Release 1.41.0 — Adoption"
below actually ships as **v1.42.0**. v1.41.0 went to an unplanned fix run 7
exposed — moving team-memory harvest into the shared Interface block
(`docs/superpowers/specs/2026-08-07-harvest-interface-fix-design.md`) — not
described anywhere in this document, because it wasn't part of the original
milestone. Adoption's own content is unchanged; only its version number
moved.
```

- [ ] **Step 7: Run the full local gate sequence**

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py'
bash -n tests/eval/run-evals.sh
shellcheck scripts/*.sh tests/*.sh tests/eval/*.sh gemini/scripts/*.sh codex/install-codex.sh codex/.codex/hooks/*.sh
shellcheck --severity=error install.sh
```
Expected: guardrails 142/142, `check_inventory_sync` still `ok` (agent/command/skill counts unchanged — this task edits existing files, doesn't add or remove any), eval unit tests still 67/67, syntax OK, shellcheck clean on both invocations.

- [ ] **Step 8: Rebuild the gemini and codex mirrors**

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
git status --short
```
Expected: `gemini/commands/*.md` for the same 9 commands show the identical harvest-clause addition (the generator copies command bodies verbatim); `gemini/gemini-extension.json` and `codex/` show no diff (this task doesn't touch versions or agent bodies).

- [ ] **Step 9: Commit**

```bash
git add commands/add-policy.md commands/audit-n-plus-one.md commands/add-test.md \
  commands/optimize-query.md commands/make-feature.md commands/refactor-to-action.md \
  commands/ship-checklist.md commands/review-pr.md commands/upgrade-laravel.md \
  gemini/commands/add-policy.md gemini/commands/audit-n-plus-one.md gemini/commands/add-test.md \
  gemini/commands/optimize-query.md gemini/commands/make-feature.md gemini/commands/refactor-to-action.md \
  gemini/commands/ship-checklist.md gemini/commands/review-pr.md gemini/commands/upgrade-laravel.md \
  tests/guardrails.test.sh docs/superpowers/specs/2026-08-06-prove-it-milestone-design.md
git commit -m "feat: harvest moves into the shared Interface block (run 7 finding 2, the real fix)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(If Step 8's gemini rebuild produced no diff for the command files — e.g. if the generator only mirrors a subset of fields — adjust the `git add` list to whatever `git status --short` actually shows; do not add files with no changes.)

---

### Task 2: The billed re-run — controller-executed, never dispatched to a subagent

**Not an implementer dispatch.** Pre-approved by this plan's Global Constraints: one re-run of `teach-delivery`, ~$4-5, drawn from the milestone's remaining budget.

**Interfaces:**
- Consumes: Task 1's commit (the harvest clause must be live in `commands/make-feature.md` before this runs — verify with `grep -c 'this delivery harvests too' commands/make-feature.md` returns `1`).
- Produces: the acceptance verdict Task 3's CHANGELOG cites.

- [ ] **Step 1: Pre-flight, including the free dry-validation the design calls for**

```bash
grep -c 'this delivery harvests too' commands/make-feature.md
./tests/guardrails.test.sh 2>&1 | tail -3
```
Expected: `1`, and `142 passed, 0 failed`. If either fails, stop — Task 1 isn't actually done.

Then read `commands/make-feature.md`'s full Interface line back (not just grep for the substring) and confirm, as a competent reader would, that the new sentence is a clear, mechanically followable instruction: does it say WHAT file to write, WHEN (after ≥2 specialists report, before the final answer), and WHAT shape (the two artifact names + their content sources)? This is the last free check before spending money — a re-run against an unclear instruction wastes the budget on an ambiguous test, not a real one.

- [ ] **Step 2: Run the re-run**

```bash
EVAL_JUDGE=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh teach-delivery
```
Run in the foreground or background at your discretion; it takes roughly 15-20 minutes based on the case's prior runs (962s and 1204s).

- [ ] **Step 3: Acceptance — verify against the filesystem, not the check's word**

Find the kept workdir path from the run's own console output (`workdir kept: ...`), then:

```bash
find <workdir>/docs -maxdepth 4
cat <workdir>/docs/team/stack.md 2>/dev/null
find <workdir>/docs/delivery -maxdepth 3 2>/dev/null
```

Three outcomes, decide which applies before writing anything down:

- **Both files exist with real content** → the fix worked. Record the case's checks/judge/seconds/USD/tokens for Task 3.
- **Neither exists, and the run did not time out** → the fix did not work even now that the command loads the clause; this is a genuine, deeper finding (the main thread read the instruction and still didn't follow it) — do not spend further budget on another re-run without going back to the human with what was found, per the standing re-run-approval rule.
- **The run timed out before reaching the point where it would write these files** → inconclusive, same shape as run 7's second re-run; report to the human rather than guessing at a fix.

- [ ] **Step 4: Update the coordinator-hash pin**

This task's Task 1 changed all 9 commands' Interface lines, which `coordinator_hash()` includes in its input. Recompute and pin:

```bash
python3 -c "
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location('cis', 'scripts/check_inventory_sync.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(m.coordinator_hash(pathlib.Path('.')))
"
```

Open `tests/eval/baseline.json`, find the `coordinator_hash` object, and set `sha256` to the printed value, `as_of` to today's date, and `note` to a sentence stating plainly whether the re-run in Step 3 confirmed harvest now fires (write the real outcome — do not copy this sentence verbatim, since it must match what Step 3 actually found):

```json
"coordinator_hash": {
  "sha256": "<value from the command above>",
  "as_of": "<today's date>",
  "note": "<state Step 3's actual outcome here>",
  "waivers": []
}
```

- [ ] **Step 5: Seed teach-delivery's ceilings from this run if outcome was a clean pass**

Only if Step 3's outcome was "the fix worked": update `tests/eval/baseline.json`'s `cases.teach-delivery` block with `max_seconds`/`max_tokens`/`max_usd` from this run's measured values + ~30% headroom, and a `basis` string citing this run. If the outcome was NOT a clean pass, leave the existing ceilings (seeded from run 7) alone — this run didn't produce a valid "the fix works" measurement to seed from.

- [ ] **Step 6: Write the outcome into run 7's findings doc**

Open `docs/evals/2026-08-06-run-7.md`. After the existing "Addendum" section, add a new section:

```markdown
## Second addendum: the real fix (v1.41.0), re-run

[Write 3-5 sentences stating: what changed (harvest requirement moved to the
shared Interface block, docs/superpowers/specs/2026-08-07-harvest-interface-fix-design.md),
what the re-run found (Step 3's actual outcome, with the specific evidence —
file paths that now exist, or don't), the case's checks/judge/seconds/USD/tokens,
and the updated milestone total spend. Do not claim more than Step 3
established.]
```

- [ ] **Step 7: Verify and commit**

```bash
python3 -c "import json; json.load(open('tests/eval/baseline.json')); print('valid JSON')"
python3 scripts/check_inventory_sync.py
git add tests/eval/baseline.json docs/evals/2026-08-06-run-7.md
git commit -m "docs(evals): the harvest fix, re-run — <one-line outcome, from Step 3>

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
(The commit subject's outcome clause is the one intentionally run-dependent string in this plan — write it from Step 3's actual finding.)

---

### Task 3: Release 1.41.0

Same ritual as 1.39.0 and 1.40.0's release tasks.

- [ ] **Step 1:** Bump `1.40.0` → `1.41.0` in `VERSION` + the 5 manifests:

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
    new_text, n = re.subn(r"1\.40\.0", "1.41.0", text)
    p.write_text(new_text)
    print(f, "->", n, "replacement(s)")
PY
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
python3 scripts/check_inventory_sync.py
```
Expected: each file reports exactly 1 replacement, and `check_inventory_sync` prints `every manifest declares 1.41.0`.

- [ ] **Step 2:** CHANGELOG section above `## [1.40.0]`:

```markdown
## [1.41.0] - <date of release>

### Added

- **Harvest moves into the shared Interface block.** Run 7 (v1.40.0) found
  that `/make-feature` and its 8 sibling commands never load
  `agents/delivery-coordinator.md`, so the harvest steps promised there —
  persisting `docs/team/stack.md` and `docs/delivery/<name>/log.md` — never
  fired for any command-driven delivery. Same fix shape as v1.24.0
  (`NOT-CHECKED`) and v1.36.0 (the stage-budget header): the requirement now
  lives in the shared, byte-identical Interface block all 9 commands carry,
  firing once a delivery has delegated to ≥2 specialists. <1-2 sentences on
  the re-run's actual outcome, from docs/evals/2026-08-06-run-7.md's second
  addendum — state plainly whether harvest now fires.>

### Changed

- **The milestone's originally-planned Adoption release is renumbered
  v1.42.0.** This release took the v1.41.0 slot instead, since it addresses
  a real gap the milestone's own verification run exposed. Adoption's
  content (README quickstart, docs index, onboarding guide) is unchanged.
```
Fill the `<...>` clause from Task 2's actual finding before committing; every other line is fixed.

- [ ] **Step 3:** All local gates:

```bash
./tests/guardrails.test.sh
python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py'
python3 scripts/check_inventory_sync.py
bash -n tests/eval/run-evals.sh
shellcheck scripts/*.sh tests/*.sh tests/eval/*.sh gemini/scripts/*.sh codex/install-codex.sh codex/.codex/hooks/*.sh
shellcheck --severity=error install.sh
git diff --exit-code -- scripts/console/dist
```
Expected: guardrails 142/142, eval units 67/67 (unless Task 2 added a new test — verify against whatever Task 2 actually left), inventory sync `ok` at 1.41.0, syntax OK, shellcheck clean, dist untouched (this release does not touch `console-ui/`).

- [ ] **Step 4:** Commit, merge, tag, publish — same sequence as v1.40.0:

```bash
git add VERSION .claude-plugin/plugin.json .claude-plugin/marketplace.json \
  .cursor-plugin/plugin.json .cursor-plugin/marketplace.json gemini/gemini-extension.json \
  CHANGELOG.md
git status --short   # review for any generator-produced diffs (e.g. gemini/agents) before adding those too
git commit -m "release: 1.41.0 — <short outcome-based subtitle>

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git checkout main
git merge --ff-only <release-branch, if one was used>
git push origin main
gh run watch <run-id-for-this-push> --exit-status
git tag -a v1.41.0 -m "v1.41.0"
git push origin v1.41.0
sed -n '/^## \[1.41.0\]/,/^## \[1.40.0\]/p' CHANGELOG.md | sed '$d' > /tmp/release-1.41.0-body.md
gh release create v1.41.0 --title "v1.41.0 — <short outcome-based subtitle>" --notes-file /tmp/release-1.41.0-body.md
rm /tmp/release-1.41.0-body.md
```

- [ ] **Step 5:** Cleanup — delete the release branch and its SDD workspace if one was used (`.superpowers/sdd/2026-08-07-harvest-interface-fix/`), matching the 1.39.0/1.40.0 precedent.

- [ ] **Step 6:** Update the `laravel-agents-pack-state` memory file with this release's real outcome (not the plan's guess) and the `MEMORY.md` index line.
