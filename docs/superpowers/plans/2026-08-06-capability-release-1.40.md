# Capability Release (v1.40.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Exception: Task 4 is controller-executed** (billed, long-running) and is never dispatched to an implementer.

**Goal:** Run eval run 7 — the teach delivery — proving (or breaking) teach → override → harvest end to end on the fixture app, and commit the team-memory example instance the README claims but cannot show.

**Architecture:** Release 2 of 3 in the [Prove-it milestone spec](../specs/2026-08-06-prove-it-milestone-design.md), scoped by [run-7-scope](../../evals/2026-08-06-run-7-scope.md). Two new opt-in eval cases split the hypothesis at the harness's natural seam (one `claude -p` call per case): `teach` proves `/teach` writes the ledger in its contracted shape (~$1); `teach-delivery` proves a delivery *obeys* a seeded ledger where defaults differ and that the coordinator *harvests* without being asked (~$5–8). The 1.39 parked hardening (audit-tally claim, waiver-field validation) lands before the billed run; fixes the run exposes land after it.

**Tech Stack:** bash + coreutils (harness, guardrails), Python 3 stdlib (check_inventory_sync, unit tests), the `claude` CLI headless for the billed run.

## Global Constraints

- **Budget is a hard ceiling: ~$30 total for the milestone's eval spend**, user-approved. Run 7's projection: sweep ~$12.50 + teach ~$1 + teach-delivery ~$5–8 + feature ~$7 + judge ≈ $27–29. **No re-run of any case without explicit human approval** — a re-run request goes to the human with the case name, the reason, and the price.
- **`ALL_CASES` stays five.** New cases join `OPT_IN_CASES` so the scorecard denominator and runs 1–6 stay comparable.
- **Nothing is committed into `tests/fixture-app`** (run 5's pollution lesson). Case seeding happens in the throwaway workdir via `seed_*` functions; example-artifact capture copies OUT of a kept workdir.
- **Answer-key discipline per the check audit** (`docs/evals/2026-08-06-check-audit.md`): new checks are artifact-based wherever an artifact exists; transcript greps only as fixture-noun or format-contract; every added check gets a row in the audit table and the tally moves with it, in the same commit.
- **`agents/` and `commands/` may be edited ONLY in Task 7** (the contingency task), and any edit to `agents/delivery-coordinator.md` or an Interface line trips the coordinator-hash CI gate — the resolution is a pin update backed by the run record or a dated waiver with a reason, never a silent hash bump.
- Repo root: `/Users/developer/Projects/Personal/laravel-claude-agents`. Case-name → function mangling is `checks_$(echo "$name" | tr '-' '_')` (run-evals.sh:593).
- This release does not touch `console-ui/`; `scripts/console/dist` must ship untouched.

---

### Task 1: Register the `teach` case — does `/teach` write the contract?

**Files:**
- Modify: `tests/eval/run-evals.sh` (OPT_IN_CASES, case_prompt, case_desc, case_rubric, new `checks_teach`)
- Modify: `docs/evals/2026-08-06-check-audit.md` (six new rows + tally)

**Interfaces:**
- Produces: case name `teach`; function `checks_teach()`; the audit tally moves 25 → 31. Task 3's tally claim and Task 4's run command use the name verbatim.

- [ ] **Step 1: Register the case in the four registries**

In `OPT_IN_CASES`, extend (comment explains why opt-in):

```bash
# teach + teach-delivery: run 7's split hypothesis (docs/evals/2026-08-06-run-7-scope.md).
# Opt-in like feature: they measure coordinator/team-memory behaviour, which only
# needs re-measuring when that behaviour changes — the hash gate says when.
OPT_IN_CASES=(feature teach teach-delivery)
```
(Task 2 registers `teach-delivery`'s other pieces; listing the name here now is harmless — the main loop validates via `case_prompt`, and Task 2 lands before any run.) **If you prefer strict isolation, add only `teach` here and let Task 2 append `teach-delivery`; either way the end state after Task 2 is the three-element array above.**

In `case_prompt()`, add before the closing `esac`:
```bash
    teach)      echo "/teach New tables use ULID primary keys, never auto-increment integers — sortable and non-enumerable" ;;
```

In `case_desc()`:
```bash
    teach)      echo "records a taught rule in docs/team/conventions.md in the Rule/Why/Scope/Source contract" ;;
```

In `case_rubric()`, add before the closing `esac`:
```bash
    teach) cat <<'EOF'
- docs/team/conventions.md exists after the run and contains one new entry
  capturing the user's rule (ULID primary keys, not auto-increment).
- The entry follows the ledger contract: Rule, Why, Scope, Source lines. The
  wording is the user's, tightened — not reinterpreted into something else.
- Scope names the agents the rule binds (database/backend), not "all agents"
  boilerplate.
- Nothing else is created or edited — /teach writes the ledger and only the
  ledger.
EOF
      ;;
```

- [ ] **Step 2: Add the answer key**

After `checks_hygiene()` in the answer-key section:

```bash
checks_teach() {
  # All artifact: /teach's deliverable IS the ledger file, so the transcript
  # proves nothing the file doesn't prove better.
  check_file "docs/team/conventions.md" "conventions ledger exists"
  check_in_files '\*\*Rule:\*\*' "docs/team/conventions.md" "entry carries a Rule line"
  check_in_files '\*\*Why:\*\*' "docs/team/conventions.md" "entry carries a Why line"
  check_in_files '\*\*Scope:\*\*' "docs/team/conventions.md" "entry carries a Scope line"
  check_in_files '\*\*Source:\*\* user' "docs/team/conventions.md" "entry attributed to the user"
  check_in_files 'ulid' "docs/team/conventions.md" "the taught rule's content landed"
}
```

- [ ] **Step 3: Dry-validate the checks without billing**

The check kit greps `$WORK`; point it at synthetic trees both ways:

```bash
bash -c '
source /dev/stdin <<"HARNESS"
WORK=""; LOG=/dev/null; CHECK_PASS=0; CHECK_FAIL=0; CHECK_LINES=()
record() { [ "$1" -eq 0 ] && CHECK_PASS=$((CHECK_PASS+1)) || CHECK_FAIL=$((CHECK_FAIL+1)); }
'"$(sed -n '/^check_file()/,/^check_touched()/p' tests/eval/run-evals.sh | head -40)"'
'"$(sed -n '/^checks_teach()/,/^}/p' tests/eval/run-evals.sh)"'
WORK=$(mktemp -d); mkdir -p "$WORK/docs/team"
printf "## New tables use ULID primary keys\n- **Rule:** ULID primary keys, never auto-increment.\n- **Why:** sortable, non-enumerable.\n- **Scope:** database-developer + backend-developer\n- **Source:** user, 2026-08-06\n" > "$WORK/docs/team/conventions.md"
checks_teach; echo "positive: $CHECK_PASS pass / $CHECK_FAIL fail (expect 6/0)"
CHECK_PASS=0; CHECK_FAIL=0; WORK=$(mktemp -d)
checks_teach; echo "negative: $CHECK_PASS pass / $CHECK_FAIL fail (expect 0/6)"
HARNESS'
```
Expected: `positive: 6 pass / 0 fail` and `negative: 0 pass / 6 fail`. If the sed extraction proves brittle, an equivalent standalone script that redefines the three `check_*` functions inline (they are 4 lines each — copy them verbatim from run-evals.sh) is acceptable; what matters is both fixtures exercising the real regexes, and both outputs captured in your report.

- [ ] **Step 4: Update the audit doc**

Add six rows to the table in `docs/evals/2026-08-06-check-audit.md` (after the hygiene rows), all `artifact`/`sound`:

```markdown
| teach | `check_file docs/team/conventions.md` | artifact | sound |
| teach | `check_in_files '\*\*Rule:\*\*'` (ledger) | artifact | sound — the ledger contract is on-disk |
| teach | `check_in_files '\*\*Why:\*\*'` (ledger) | artifact | sound |
| teach | `check_in_files '\*\*Scope:\*\*'` (ledger) | artifact | sound |
| teach | `check_in_files '\*\*Source:\*\* user'` (ledger) | artifact | sound |
| teach | `check_in_files 'ulid'` (ledger) | artifact | sound — the taught content, not a wording choice |
```

Update the tally line to: `Tally: 31 checks — 22 artifact, 5 fixture-noun, 2 format-contract, **2 hardened-prose (formerly free-prose; 0 free-prose remain)**.` (16+6=22 artifact; total 25+6=31.)

- [ ] **Step 5: Verify the sweep is unchanged and the case is reachable**

```bash
./tests/eval/run-evals.sh --list
bash -n tests/eval/run-evals.sh && echo "syntax ok"
./tests/guardrails.test.sh 2>&1 | tail -2
```
Expected: `--list` shows `teach` among opt-in cases and the default sweep still lists exactly five; syntax ok; guardrails 141 (nothing pinned the old tally — Task 3 adds that).

- [ ] **Step 6: Commit**

```bash
git add tests/eval/run-evals.sh docs/evals/2026-08-06-check-audit.md
git commit -m "feat(evals): the teach case — does /teach write the ledger contract?

Run 7's hypothesis part 1, split at the harness's one-prompt-per-case
seam. Six artifact checks assert the Rule/Why/Scope/Source shape on disk;
dry-validated against positive and negative synthetic trees without
billing. Opt-in: team-memory behaviour needs re-measuring only when it
changes, and the hash gate says when.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Register the `teach-delivery` case — obedience and harvest

**Files:**
- Modify: `tests/eval/run-evals.sh` (case_prompt, case_desc, case_rubric, `seed_taught_fixture`, seeding hook in run_case, `checks_teach_delivery`)
- Modify: `docs/evals/2026-08-06-check-audit.md` (eight new rows + tally)

**Interfaces:**
- Consumes: `OPT_IN_CASES` already lists `teach-delivery` (Task 1).
- Produces: `seed_taught_fixture()`, `checks_teach_delivery()`; audit tally 31 → 39 (29 artifact, 5 fixture-noun, 3 format-contract, 2 hardened-prose). Task 4 runs it; Task 6 captures its kept workdir.

- [ ] **Step 1: Registries**

`case_prompt()`:
```bash
    teach-delivery) echo "/make-feature Donation --api" ;;
```
`case_desc()`:
```bash
    teach-delivery) echo "delivers a feature that must OBEY two seeded taught rules where defaults differ, and harvest without being asked" ;;
```
`case_rubric()`:
```bash
    teach-delivery) cat <<'EOF'
- The Donation feature obeys both taught rules where the default would differ:
  money lands as integer cents (no float/decimal amount column), and the new
  table uses ULID primary keys (not auto-increment).
- The taught rules were CONSULTED, not coincidental: briefs or returns
  reference the ledger, or the produced code matches the rules exactly where
  Laravel's own defaults point the other way.
- The coordinator harvested without being asked: docs/team/stack.md persisted
  (the stack snapshot), and the delivery log exists under docs/delivery/.
- The feature is real: migration, model, HTTP entry point, and at least one
  feature test.
- A correct-looking feature that ignores the ledger (float money or
  auto-increment ids) is a FAIL even if it works.
EOF
      ;;
```

- [ ] **Step 2: The seed function**

After `seed_hygiene_fixture()`:

```bash
# teach-delivery case: a CLEAN two-rule ledger in /teach's exact entry shape —
# no planted conflicts (that is hygiene's job). Both rules are chosen so the
# Laravel default visibly differs: money defaults to decimal, ids to
# auto-increment. Obedience is therefore observable in the migration itself.
seed_taught_fixture() { # seed_taught_fixture <workdir>
  mkdir -p "$1/docs/team"
  cat >"$1/docs/team/conventions.md" <<'EOF'
# Team conventions — taught rules

Rules the user taught the agent team. Every agent reads this file before
starting work; entries here override agent defaults. Maintain via /teach
(or edit by hand — the shape below is the contract).

## Money is integer cents
- **Rule:** Store and compute money as integer cents (`*_cents` integer columns) — never float or decimal columns.
- **Why:** Float drift is unacceptable in billing; integer math is exact.
- **Scope:** database-developer + backend-developer (migrations, models, calculations)
- **Source:** user, 2026-08-06

## New tables use ULID primary keys
- **Rule:** New tables use ULID primary keys (`$table->ulid('id')->primary()` + `HasUlids` on the model), never auto-increment integers.
- **Why:** Sortable, non-enumerable identifiers.
- **Scope:** database-developer + backend-developer
- **Source:** user, 2026-08-06
EOF
}
```

In `run_case()`, extend the seeding hook (currently `[ "$name" = "hygiene" ] && seed_hygiene_fixture "$WORK"`):
```bash
  [ "$name" = "hygiene" ] && seed_hygiene_fixture "$WORK"
  [ "$name" = "teach-delivery" ] && seed_taught_fixture "$WORK"
```

- [ ] **Step 3: Pre-flight the fixture for regex collisions**

```bash
grep -riE 'cents|ulid|donation' tests/fixture-app/database/migrations tests/fixture-app/app 2>/dev/null; echo "exit: $?"
```
Expected: `exit: 1` (no hits). If anything matches, STOP and report — the checks below would false-positive and need tightening to the donations migration specifically.

- [ ] **Step 4: The answer key**

```bash
checks_teach_delivery() {
  # Obedience: both taught rules land where Laravel's default points the other
  # way. Artifact checks on the migration/model — a delivery that ignores the
  # ledger produces decimal('amount') and $table->id(), and fails here.
  check_file_under "database/migrations" "*donations*.php" "donations migration created"
  check_in_files 'cents' "database/migrations" "money lands as integer cents (taught rule 1)"
  check_not_in_files "(decimal|float|double)\('amount" "database/migrations" "no float/decimal money column"
  # ULID accepted in either idiomatic placement: HasUlids on the model, or
  # ulid('id') in the migration. One check, inline OR (hygiene precedent).
  if grep -qriE 'HasUlids' "$WORK/app/Models" 2>/dev/null \
     || grep -qriE "ulid\(" "$WORK/database/migrations" 2>/dev/null; then
    record 0 "code:   ULID primary keys (taught rule 2)"
  else
    record 1 "code:   ULID primary keys (taught rule 2)"
  fi
  # Harvest: the promises the coordinator makes unprompted — stack snapshot
  # (step 4) and the delivery log (step 9). THIS is hypothesis part 3; a FAIL
  # here is run 7 doing its job, not a broken key.
  check_file "docs/team/stack.md" "harvest persisted the stack snapshot"
  check_file_under "docs/delivery" "log.md" "delivery log written"
  check_touched "tests/" "feature test added"
  check_log 'done when:' "board declares a completion condition"
}
```

- [ ] **Step 5: Dry-validate positive and negative**

Same technique as Task 1 Step 3 (source the kit + this function, synthetic `$WORK`): positive tree = migration file `2026_08_06_000000_create_donations_table.php` containing `$table->ulid('id')->primary();` and `$table->integer('amount_cents');`, plus `docs/team/stack.md`, `docs/delivery/donation/log.md`, and LOG file containing `done when:`; `check_touched` needs a git repo — `git init` the synthetic tree, commit, then add a file under `tests/`. Negative tree = migration with `$table->id();` and `$table->decimal('amount', 8, 2);`, no docs. Expected: positive 8/0, negative 1/7 (the `check_not_in_files` on a tree with a decimal amount column FAILS — which is 0 pass for it... careful: negative tree HAS `decimal('amount'`, so that check records FAIL; the migration glob check PASSES because a donations migration exists). State the exact expected split in your report and reason each line.

- [ ] **Step 6: Audit doc**

Eight rows after the teach rows:

```markdown
| teach-delivery | `check_file_under database/migrations *donations*.php` | artifact | sound |
| teach-delivery | `check_in_files 'cents'` (migrations) | artifact | sound — taught rule 1, observable in schema |
| teach-delivery | `check_not_in_files "(decimal\|float\|double)\('amount"` (migrations) | artifact | sound — the default the rule overrides |
| teach-delivery | inline `HasUlids` (models) OR `ulid\(` (migrations) | artifact | sound — either idiomatic placement |
| teach-delivery | `check_file docs/team/stack.md` | artifact | sound — the unprompted-harvest promise; a FAIL is a run-7 finding |
| teach-delivery | `check_file_under docs/delivery log.md` | artifact | sound |
| teach-delivery | `check_touched tests/` | artifact | sound |
| teach-delivery | `check_log 'done when:'` | format-contract | sound — Interface-mandated header string |
```

Tally: `Tally: 39 checks — 29 artifact, 5 fixture-noun, 3 format-contract, **2 hardened-prose (formerly free-prose; 0 free-prose remain)**.`

- [ ] **Step 7: Verify and commit**

```bash
./tests/eval/run-evals.sh --list && bash -n tests/eval/run-evals.sh && ./tests/guardrails.test.sh 2>&1 | tail -2
git add tests/eval/run-evals.sh docs/evals/2026-08-06-check-audit.md
git commit -m "feat(evals): the teach-delivery case — obedience and harvest, observed in schema

Run 7's hypothesis parts 2 and 3. A clean two-rule ledger is seeded in
/teach's exact shape (workdir only — nothing enters the fixture), both
rules chosen so Laravel's default visibly differs: decimal money vs
integer cents, auto-increment vs ULID. Obedience is asserted in the
migration; harvest by the stack snapshot and delivery log the coordinator
promises unprompted. A harvest FAIL here is run 7 doing its job.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: The 1.39 parked hardening — tally claim + waiver validation

**Files:**
- Modify: `scripts/check_inventory_sync.py` (actuals() gains `eval_checks`; CLAIMS gains the audit-tally row; `check_coordinator_hash` validates waiver fields)
- Modify: `tests/eval/test_coordinator_hash.py` (two new tests)
- Test: `python3 -m unittest discover -s tests/eval -t tests/eval`

**Interfaces:**
- Consumes: audit tally now reads 39 (Task 2).
- Produces: `eval_checks` count in the inventory line; malformed waivers fail CI. Task 8's gates expect `eval_cases=8` unchanged? No — `eval_cases` counts registered cases: verify what `actuals()` counts and expect it to move 6 → 8 (five default + feature + teach + teach-delivery) if it counts registrations; read the function first and report what it actually counts before asserting.

- [ ] **Step 1: Read `actuals()` and the CLAIMS shape in `scripts/check_inventory_sync.py`**

Report in your notes: what `eval_cases` counts today (its source of truth), and the exact CLAIMS tuple shape. If `eval_cases` counts `case_prompt` entries, Tasks 1–2 already moved it 6 → 8 and README/inventory claims may now MISMATCH — if `python3 scripts/check_inventory_sync.py` fails on entry, fixing the claim string (README inventory sentence) is in-scope for this task; record what you changed.

- [ ] **Step 2: Failing tests first**

Append to `tests/eval/test_coordinator_hash.py`:

```python
    def test_waiver_missing_date_or_reason_is_rejected(self):
        # The error message promises "a dated waiver with a reason" — make the
        # promise structural: a waiver without both fields must not be counted.
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            current = inv.coordinator_hash(root)
            pin(root, "0" * 64, waivers=[{"sha256": current}])  # no date, no reason
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(inv.check_coordinator_hash(root), 1)
            self.assertIn("::error", buf.getvalue())

    def test_fully_formed_waiver_still_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            current = inv.coordinator_hash(root)
            pin(root, "0" * 64, waivers=[
                {"date": "2026-08-06", "sha256": current, "reason": "test"}])
            self.assertEqual(inv.check_coordinator_hash(root), 0)
```

Run: `python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_coordinator*.py' -v 2>&1 | tail -4`
Expected: the first new test FAILS (current code accepts a bare-sha waiver); the second PASSES (already true). That asymmetry is the red phase.

- [ ] **Step 3: Implement waiver validation**

In `check_coordinator_hash`, replace the accepted-set construction:

```python
    accepted = {pinned.get("sha256")}
    accepted.update(w.get("sha256") for w in pinned.get("waivers", []))
```
with:
```python
    accepted = {pinned.get("sha256")}
    for waiver in pinned.get("waivers", []):
        # The message below promises "a dated waiver with a reason"; enforce it,
        # or the audit trail the waiver shape exists for is honor-system.
        if waiver.get("date") and waiver.get("reason"):
            accepted.add(waiver.get("sha256"))
```

- [ ] **Step 4: Implement the tally claim**

In `actuals()`, add a count named `eval_answer_checks`: parse `tests/eval/run-evals.sh`, count lines matching `^\s+check_[a-z_]+ ` plus lines matching `^\s+record \$\?` that occur AFTER the line `# ------------------------------------------------------------- answer key ----` (the answer-key section marker — verify the marker text verbatim first and adjust if it differs; the count must land on exactly 39). Add the CLAIMS row binding it to the audit doc:

```python
    ("docs/evals/2026-08-06-check-audit.md", "audit tally",
     r"Tally: (\d+) checks", "eval_answer_checks"),
```
(Match the existing CLAIMS tuple shape you recorded in Step 1 — if it differs from this sketch, follow the file.)

- [ ] **Step 5: Green + prove the tally claim can fail**

```bash
python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py' 2>&1 | tail -3
python3 scripts/check_inventory_sync.py
python3 - <<'PY'  # can-fail proof: doc says 39, disk says 40 → must error
import pathlib, re, subprocess
p = pathlib.Path("docs/evals/2026-08-06-check-audit.md")
orig = p.read_text(encoding="utf-8")
p.write_text(orig.replace("Tally: 39 checks", "Tally: 40 checks"), encoding="utf-8")
r = subprocess.run(["python3", "scripts/check_inventory_sync.py"], capture_output=True, text=True)
print("tampered exit:", r.returncode, "| mentions tally:", "audit tally" in (r.stdout + r.stderr))
p.write_text(orig, encoding="utf-8")
PY
python3 scripts/check_inventory_sync.py && echo "restored green"
```
Expected: units OK; sync ok; `tampered exit: 1 | mentions tally: True`; restored green.

- [ ] **Step 6: Commit**

```bash
git add scripts/check_inventory_sync.py tests/eval/test_coordinator_hash.py README.md
git commit -m "feat(evals): the audit tally is a CLAIMS row, and waivers must be dated with a reason

The two parked 1.39 hardenings. The tally was a hand-maintained count in
the one repo whose inventory checker exists because hand-maintained
counts drift; it is now counted from run-evals.sh and bound to the audit
doc's own sentence. A waiver without date and reason no longer counts —
the gate's error message promised both, and promises the code doesn't
keep are how escape hatches rust open.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
(Drop README.md from the add list if Step 1 found no claim-string change was needed.)

---

### Task 4: RUN 7 — **controller-executed, billed**

**Not an implementer dispatch.** The controller runs this from the main session: two background invocations, sequential cases (run-3 finding: parallel inflates per-case durations 2–6×), `EVAL_JUDGE=1` throughout, `KEEP_WORKDIR=1` so Task 6 can capture the teach-delivery workdir.

- [ ] **Step 1: The default five-case sweep (~$12.50, ~45–75 min)**

```bash
EVAL_JUDGE=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh
```
Run in background; the console output names the results directory. Abort criterion: any case erroring at `install.sh` (not at checks) → stop everything, nothing else billed, investigate.

- [ ] **Step 2: The three opt-in cases (~$13–16, ~50–70 min)**

```bash
EVAL_JUDGE=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh teach teach-delivery feature
```

- [ ] **Step 3: Acceptance**

Collect per case: checks scorecard, judge verdict + any judge-vs-key disagreement, `<case>.cost.json` (billed USD), duration, and for `teach-delivery` the kept workdir path. Total spend stated against the ≤$30 ceiling. **Any FAILED check is a finding, not an automatic re-run** — findings go to Task 5's doc; re-runs go to the human with a price.

---

### Task 5: Findings doc, baselines, and the pin's retirement

**Files:**
- Create: `docs/evals/2026-08-06-run-7.md`
- Modify: `tests/eval/baseline.json` (teach + teach-delivery ceilings seeded from measurement; `coordinator_hash` note retired; `_opt_in` updated)

**Interfaces:**
- Consumes: Task 4's results (scorecards, costs, durations, judge outputs).
- Produces: the run record Task 8's changelog cites; the retired pin note.

- [ ] **Step 1: Write the findings doc** in the run-1..6 house shape: header (date, composition, total spend vs budget), per-case table (checks, judge, seconds, USD, tokens), findings numbered with evidence, judge-vs-key disagreements called out, and a closing checklist of follow-ups. The hypothesis verdict leads: teach → override → harvest, each part PASS/FAIL with the artifact that proves it. Cross-reference `docs/evals/2026-08-06-run-7-scope.md` — every promise in the scope doc gets an outcome line.

- [ ] **Step 2: Seed the two new cases' ceilings** from measured + ~30% headroom (the `feature` precedent), with `basis`/`usd_basis`/`tokens_basis` strings naming this run. Reseed any default-sweep case only per the standing `_policy` (soft ceilings; update after each accepted sequential run) and note every reseed in the findings doc.

- [ ] **Step 3: Retire the pin's seeding note.** The `feature` case just ran billed. Recompute the hash (`python3` one-liner via importlib, as in 1.39), confirm it equals the pinned value (no coordinator edits have happened yet), and update `coordinator_hash`: `as_of` = today, `note` = "Verified by eval run 7 (2026-08-06, docs/evals/2026-08-06-run-7.md): the feature case ran billed at exactly this content." Also update `_opt_in` to name all three opt-in cases and the hash gate as the trigger.

- [ ] **Step 4: Verify and commit**

```bash
python3 scripts/check_inventory_sync.py && python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py' 2>&1 | tail -3
git add docs/evals/2026-08-06-run-7.md tests/eval/baseline.json
git commit -m "docs(evals): run 7 — <one-line verdict: fill from the actual result>

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
(The commit subject's verdict clause is the one intentionally run-dependent string in this plan — write it from the findings doc's hypothesis verdict, e.g. "teach and obedience hold, harvest is half-broken" or "all three hypothesis parts hold".)

---

### Task 6: The example instance — `docs/examples/team-memory/`

**Files:**
- Create: `docs/examples/team-memory/README.md`, plus captured artifacts (see Step 1)
- Modify: `README.md` (link where the team-memory feature is described)

**Interfaces:**
- Consumes: teach-delivery's kept workdir (Task 4) and the run record (Task 5).

- [ ] **Step 1: Capture from the kept workdir** (path from Task 4's report): copy `docs/team/conventions.md` (as seeded — the input), `docs/team/stack.md` and `docs/delivery/**/log.md` (the harvest — the output), and the case's final-answer log (`<results>/teach-delivery.log`) as `final-answer.md`. If harvest artifacts don't exist because the run FAILED that check, capture what does exist and say so in the README — a partial example honestly labeled beats none.

- [ ] **Step 2: Write `docs/examples/team-memory/README.md`**

```markdown
# Team memory, captured live

A real instance of the teach → override → harvest loop, captured from eval
run 7 (2026-08-06, pack v1.39.0 → released as v1.40.0; record:
../../evals/2026-08-06-run-7.md). Nothing here is hand-written except this
page — every other file is copied verbatim out of the run's throwaway
workdir.

- `conventions.md` — the ledger as seeded (two rules in /teach's contract
  shape: integer-cents money, ULID keys). This is the INPUT.
- `stack.md`, `delivery-log.md` — what the coordinator persisted without
  being asked at delivery end. This is the HARVEST.
- `final-answer.md` — the run's closing message, with its VERIFIED and
  NOT-CHECKED calibration.

What to look at: the donations migration the run produced used
`ulid('id')` and an integer cents column where Laravel's defaults are
auto-increment and decimal — the taught rules overrode the defaults. That
is the pack's team-memory claim, demonstrated rather than described.
```
(Adjust the "What to look at" paragraph to match the actual run outcome — never claim an override the artifacts don't show.)

- [ ] **Step 3: Link from the README** — find the paragraph describing `docs/team/` / `/teach` (grep `conventions.md` in README.md) and append: `A captured live instance — seeded ledger, obeyed rules, unprompted harvest — lives in [docs/examples/team-memory/](docs/examples/team-memory/).`

- [ ] **Step 4: Commit**

```bash
git add docs/examples README.md
git commit -m "docs: the team-memory example instance — the claim, demonstrated

The README described teach → override → harvest with no example instance
anywhere (2026-08-05 review, gap 4). This is one, captured verbatim from
eval run 7's kept workdir and labeled with exactly what it shows.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Contingency — fixes the run exposes (CONDITIONAL)

**Skip entirely if run 7 passes all checks.** Otherwise, per failing area:

- Triage in the findings doc first: is the failure the pack's behaviour (fix the body), the case's key (fix the check — and the audit doc in the same commit), or the fixture (fix the seed)?
- Body fixes may touch `agents/` / `commands/` — this is the one task allowed to. **An edit to `agents/delivery-coordinator.md` or any Interface line trips the hash gate**: the commit must either update the pin citing a re-run the human approved and paid for, or add a dated waiver whose reason names the pending re-run.
- **Any re-run is a human decision** (Global Constraints): present case, reason, price. The remaining budget after run 7 will be ~$1–3 — assume a re-run needs explicit approval to exceed the ceiling.
- Each fix follows TDD where testable and gets its own commit with the finding number in the message.

---

### Task 8: Release 1.40.0

Same ritual as 1.39 (Task 6 of that plan), with these values:

- [ ] **Step 1:** Bump `1.39.0` → `1.40.0` in VERSION + the five manifests (same python re.subn loop, pattern `"1\.39\.0"`), rebuild gemini, `check_inventory_sync` must print 1.40.0.
- [ ] **Step 2:** CHANGELOG section above `## [1.39.0]`:

```markdown
## [1.40.0] - <date of release>

### Added

- **Eval run 7 — the teach delivery.** <2-4 sentences from the findings doc:
  the hypothesis verdict, the spend, and the one number that matters.>
  Record: `docs/evals/2026-08-06-run-7.md`.
- **Two opt-in eval cases split the team-memory hypothesis** at the harness's
  one-prompt-per-case seam: `teach` (six artifact checks on the ledger
  contract `/teach` writes) and `teach-delivery` (a seeded two-rule ledger the
  delivery must obey where Laravel's defaults differ — integer-cents money,
  ULID keys — plus the unprompted harvest: stack snapshot and delivery log).
  The audit tally moves 25 → 39, and is now a CLAIMS row counted from
  `run-evals.sh` rather than a hand-maintained number.
- **`docs/examples/team-memory/`** — the example instance the README claimed
  without evidence (2026-08-05 review, gap 4): the seeded ledger, the code
  that obeyed it, and the harvest, captured verbatim from run 7's workdir.

### Changed

- **Waivers on the coordinator-hash gate must carry a date and a reason** —
  the error message always promised both; now a bare-sha waiver doesn't
  count. The pin's seeding note is retired: the `feature` case re-ran billed
  in run 7 at exactly the pinned content.
```
Fill the `<...>` clauses from the actual run before committing; every other line is fixed.
- [ ] **Step 3:** All local gates (the 1.39 list, guardrails still 141, eval units now 56, CI's full shellcheck line, dist untouched).
- [ ] **Step 4:** Release commit `release: 1.40.0 — <subtitle from the run's verdict>`, then controller merges/pushes/tags/publishes after review, as in 1.39.

---

## Self-review record (2026-08-06)

- **Spec coverage:** 1.40's spec deliverables → Tasks 1–2 (the case, split in two with the split argued), Task 4 (the billed run, composition per the scope doc: sweep + teach cases + feature unconditionally), Task 5 (ceilings from measurement; the pin retirement the 1.39 seeding note promised), Task 6 (the example instance + README link), Task 7 (fixes the run exposes). The 1.39 parked hardenings → Task 3. Release mechanics → Task 8.
- **Known run-dependence, stated rather than hidden:** Task 5's commit subject, Task 6's "what to look at" paragraph, and Task 8's changelog clauses depend on the run's outcome; each names exactly which string is variable and what governs it (the findings doc). Everything else is fixed text.
- **Placeholder scan:** the `<...>` clauses above are the only intentional ones; each has a source named. No TBDs elsewhere.
- **Type consistency:** case names `teach` / `teach-delivery` (mangled to `checks_teach` / `checks_teach_delivery` per run-evals.sh:593); `seed_taught_fixture` matches the `seed_hygiene_fixture` calling convention; the audit tally moves 25 → 31 → 39 across Tasks 1–2 and Task 3 binds 39 via CLAIMS; waiver-validation tests reuse `make_tree`/`pin` helpers exactly as defined in the 1.39 test file.
- **Budget honesty:** projected $27–29 against the ~$30 ceiling leaves no slack for re-runs; Task 7 therefore routes every re-run to the human. This is the spec's own appetite, not a new constraint.
