# Trust Release (v1.39.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the eval instrument — audit all 25 answer-key checks for prose-grep fragility, fix the two genuinely fragile ones, declare `max_usd` the cost metric of record, make the `feature`-case trigger deterministic via a coordinator content hash, and scope eval run 7 — with zero agent-body changes.

**Architecture:** Release 1 of 3 in the [Prove-it milestone spec](../specs/2026-08-06-prove-it-milestone-design.md). Everything here touches the measuring instrument or docs, never `agents/` or the behavioural half of `commands/` — that is what keeps run 7 comparable to runs 1–6. The hash rule lives in `scripts/check_inventory_sync.py` (already a CI gate, already Python, already the "claims match disk" checker); the vocabulary ratchets live in `tests/guardrails.test.sh` (zero-dependency bash, the pack's ratchet home).

**Tech Stack:** bash + coreutils (guardrails), Python 3 stdlib only (`hashlib`, `json`, `pathlib`, `unittest`), no new dependencies anywhere.

## Global Constraints

- **No agent-body changes.** Nothing under `agents/` is edited in this release. Nothing in `commands/` is edited either (the hash rule *reads* them).
- **Answer-key intent is frozen.** A check's meaning may not change; only its evidence source or vocabulary coverage may. Every check edit is documented in the audit doc in the same commit.
- **Guardrails stay zero-dependency** — pure bash + coreutils, no jq/python3 inside `tests/guardrails.test.sh` assertions (the file's own header states this contract).
- **Python is stdlib-only**, matching every other script in `scripts/`.
- **House voice in comments:** every non-obvious block explains *why*, in the terse style of the surrounding file.
- Repo root is `/Users/developer/Projects/Personal/laravel-claude-agents`; all paths below are relative to it. Run commands from the root unless stated.
- After completing the plan, the release ritual (Task 6) must ship `scripts/console/dist` untouched — this release does not touch `console-ui/`, so a dist diff means something went wrong.

---

### Task 1: The check-fragility audit document

The audit's deliverable is a classification table. It is written first because Task 2's edits cite it, and because the honest finding is that **most checks are already sound** — recording *why* stops a future contributor from "fixing" greps that are correct.

**Files:**
- Create: `docs/evals/2026-08-06-check-audit.md`

**Interfaces:**
- Produces: the classification vocabulary used by Task 2's commit message and the run-7 stub (Task 5): *artifact*, *fixture-noun*, *format-contract*, *free-prose*.

- [ ] **Step 1: Write the audit document**

The classification below is verbatim from `tests/eval/run-evals.sh` lines 339–385 (verified 2026-08-06). Write exactly this file:

````markdown
# Answer-key check audit — 2026-08-06

Every check the eval harness dispatches, classified by evidence source. Trigger:
v1.37.0 replaced `check_log 'update'` — a grep for one English word in
nondeterministic prose — after the rubric judge correctly failed the key on a
run that closed the planted IDOR without using the word. The
[project-state review](../requirements/2026-08-05-project-state-review.md)
(gap 5) asked whether the other checks carry the same disease. This audit
answers that, check by check, so the classification is never re-derived.

## Classification vocabulary

- **artifact** — inspects files/code/diff the run produced on disk. The gold
  standard: immune to wording.
- **fixture-noun** — greps the transcript for a proper noun or API name from
  the fixture (`PostController`, `withCount`, `LegacyPayments`). Sound: any
  correct report *must* contain these — they are the answer, not a wording
  choice.
- **format-contract** — greps for a string the Interface block mandates
  verbatim (`NOT-CHECKED`, `done when:`). Sound: the contract *is* the string.
- **free-prose** — greps for an ordinary English word the model may synonymise.
  This is the `check_log 'update'` disease. Two instances found; both fixed
  in this release.

## The table

| Case | Check | Kind | Verdict |
| ---- | ----- | ---- | ------- |
| n-plus-one | `check_log 'with\(\|eager[- ]?load'` | fixture-noun (API) | sound — alternation covers both idioms |
| n-plus-one | `check_log 'withCount'` | fixture-noun (API) | sound |
| n-plus-one | `check_log 'PostController\|index\.blade'` | fixture-noun | sound |
| n-plus-one | `check_log 'comments'` | fixture-noun (relation name) | sound |
| policy | `check_file PostPolicy.php` | artifact | sound |
| policy | `check_in_files 'authorize\|Gate::\|->can\(\|can:'` (controller) | artifact | sound |
| policy | `check_update_guarded` | artifact | sound — the v1.37.0 conversion, keep as reference implementation |
| action | `check_file_under app/Actions *.php` | artifact | sound |
| action | `check_in_files 'Action'` (controller) | artifact | sound — a controller that delegates must reference the class; acceptable breadth |
| action | `check_not_in_files 'Mail::to'` (controller) | artifact | sound |
| action | `check_touched tests/` | artifact | sound |
| tests | `check_touched tests/` | artifact | sound |
| tests | `check_in_files 'posts\.update\|->put\(\|->patch\('` | artifact | sound |
| tests | `check_in_files 'assertForbidden\|403'` | artifact | sound |
| tests | `check_log 'NOT-CHECKED'` | format-contract | sound — the Interface block mandates the literal string |
| feature | `check_file_under database/migrations *tags*.php` | artifact | sound |
| feature | `check_file_under app/Models Tag.php` | artifact | sound |
| feature | `check_in_files 'tag' routes` | artifact | sound |
| feature | `check_touched tests/` | artifact | sound |
| feature | `check_delegated 2` | artifact (board feed) | sound — negative-controlled at introduction (v1.34.0) |
| feature | `check_log 'done when:'` | format-contract | sound — Interface-mandated header string |
| hygiene | `check_log 'duplicate'` | **free-prose** | **FRAGILE — fixed this release.** A run classifying the UUID twins as "identical"/"redundant" fails the key while being right. Now `'duplicat\|identical\|redundan\|twin'` (stems cover duplicate/duplicated/duplication, redundant/redundancy). |
| hygiene | `check_log 'conflict'` | **free-prose** | **FRAGILE — fixed this release.** "Contradicts" fails the key. Now `'conflict\|contradict\|disagree\|mutually exclusive'`. |
| hygiene | `check_log 'LegacyPayments'` | fixture-noun | sound |
| hygiene | inline `git diff --quiet -- docs/team/conventions.md` | artifact | sound — headless run must propose, not apply |

Tally: 25 checks — 16 artifact, 5 fixture-noun, 2 format-contract, **2 free-prose
(previously; 0 after this release)**. The rubric judge (`EVAL_JUDGE=1`) stays on
as the independent dissenter for the transcript-based checks; it has been right
both times it disagreed with the key.

## Rules this audit sets

1. **New checks prefer artifact evidence.** A transcript grep is acceptable
   only as fixture-noun or format-contract — never for an ordinary English
   word. Guardrail ratchets pin the two hardened vocabularies.
2. **A conversion documents itself here, in the same commit.** Old form, new
   form, and why the intent is unchanged.
3. **The synonym lists are additive-only** without a documented reason — a
   narrowed vocabulary is how the disease returns.
````

- [ ] **Step 2: Verify the table against the source**

Run: `grep -n "check_log\|check_file\|check_in_files\|check_not_in_files\|check_touched\|check_delegated\|check_update_guarded\|git -C" tests/eval/run-evals.sh | sed -n '/checks_n_plus_one/,$p'` — cross-check every row's regex is verbatim. Expected: every check in `checks_*` functions appears in the table; no extras. (The count is 25 including hygiene's inline diff check.)

- [ ] **Step 3: Commit**

```bash
git add docs/evals/2026-08-06-check-audit.md
git commit -m "docs(evals): audit all 25 answer-key checks for prose-grep fragility

16 artifact, 5 fixture-noun, 2 format-contract, 2 free-prose. The two
free-prose greps (hygiene's 'duplicate' and 'conflict') are the same
disease check_update_guarded fixed in v1.37.0 — an English word the model
may synonymise. They are hardened in the next commit; the table records
why the other 22 greps are sound so nobody 'fixes' them.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Harden the two fragile hygiene checks, ratcheted

TDD via the guardrails file: the ratchets are written first and must FAIL against the current regexes, proving they test the right thing.

**Files:**
- Modify: `tests/guardrails.test.sh` (append two `expect` lines in the static-ratchets section, after the Interface-block ratchets)
- Modify: `tests/eval/run-evals.sh:378-379` (the two `check_log` lines in `checks_hygiene`)

**Interfaces:**
- Consumes: classification + exact hardened vocabularies from Task 1's audit doc.
- Produces: the exact strings `check_log 'duplicat|identical|redundan|twin'` and `check_log 'conflict|contradict|disagree|mutually exclusive'` in `run-evals.sh` — pinned verbatim by the ratchets.

- [ ] **Step 1: Add the failing ratchets**

In `tests/guardrails.test.sh`, locate the static-ratchets section (search for `static ratchets`) and append after the last Interface-block `expect`:

```bash
# 2026-08-06 check audit: hygiene's two free-prose greps were the last instances
# of the check_log-'update' disease (an English word the model may synonymise —
# see docs/evals/2026-08-06-check-audit.md). The hardened vocabularies are
# additive-only; narrowing one back to a single word is how the disease returns.
expect "hygiene duplicate check accepts synonyms (2026-08-06 audit)" "1" \
  "$(grep -cF "check_log 'duplicat|identical|redundan|twin'" "$SCRIPT_DIR/tests/eval/run-evals.sh")"
expect "hygiene conflict check accepts synonyms (2026-08-06 audit)" "1" \
  "$(grep -cF "check_log 'conflict|contradict|disagree|mutually exclusive'" "$SCRIPT_DIR/tests/eval/run-evals.sh")"
```

- [ ] **Step 2: Run guardrails to verify the new ratchets fail**

Run: `./tests/guardrails.test.sh 2>&1 | tail -6`
Expected: exactly 2 failures (the two new expects, actual `0` vs expected `1`); total shows `2 failed`. If anything else fails, stop — the tree was dirty before you started.

- [ ] **Step 3: Harden the two regexes**

In `tests/eval/run-evals.sh`, `checks_hygiene()`, replace:

```bash
  check_log 'duplicate' "classifies the UUID twin entries as duplicate"
  check_log 'conflict' "classifies the Pest-vs-PHPUnit pair as conflict"
```

with:

```bash
  # Free-prose greps hardened 2026-08-06 (docs/evals/2026-08-06-check-audit.md):
  # a run that says "identical"/"redundant" or "contradicts" is right and used
  # to fail the key — the same disease check_update_guarded fixed in v1.37.0.
  # Stems on purpose: duplicat~ covers duplicate/duplicated/duplication.
  check_log 'duplicat|identical|redundan|twin' "classifies the UUID twin entries as duplicate"
  check_log 'conflict|contradict|disagree|mutually exclusive' "classifies the Pest-vs-PHPUnit pair as conflict"
```

- [ ] **Step 4: Run guardrails to verify all green**

Run: `./tests/guardrails.test.sh 2>&1 | tail -3`
Expected: `total: 140 passed, 0 failed` (138 existing + 2 new), `ALL GREEN`.

- [ ] **Step 5: Sanity-check the hardened greps behave**

```bash
LOGTMP=$(mktemp)
echo "these two entries are identical twins; the Pest fact contradicts the PHPUnit one" > "$LOGTMP"
grep -qiE 'duplicat|identical|redundan|twin' "$LOGTMP" && echo "dup: PASS (synonym accepted)"
grep -qiE 'conflict|contradict|disagree|mutually exclusive' "$LOGTMP" && echo "conf: PASS (synonym accepted)"
echo "nothing relevant here" > "$LOGTMP"
grep -qiE 'duplicat|identical|redundan|twin' "$LOGTMP" || echo "dup: correctly rejects silence"
rm "$LOGTMP"
```
Expected: all three lines print — synonyms accepted, silence still fails.

- [ ] **Step 6: Commit**

```bash
git add tests/guardrails.test.sh tests/eval/run-evals.sh
git commit -m "fix(evals): hygiene's duplicate/conflict checks accept the model's synonyms

The last two free-prose greps in the answer key (per the 2026-08-06
audit). A run classifying the UUID twins as 'identical' or the Pest/PHPUnit
pair as 'contradicts' was right and failed the key. Vocabularies are
additive-only and ratchet-pinned so they cannot quietly narrow back.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Declare the cost metric of record

Doc-only, but it settles a rule every future release consults, so it is its own reviewable unit.

**Files:**
- Modify: `tests/eval/baseline.json` (the `_metrics` top-level string)
- Modify: `README.md` (the eval paragraph)

**Interfaces:**
- Consumes: run-6 findings already recorded in baseline's `_metrics`/`_tokens_caveat`/`_bimodal_cases` strings.
- Produces: the phrase **"metric of record"** in both files — Task 6's changelog cites it.

- [ ] **Step 1: Extend `_metrics` in baseline.json**

The current `_metrics` string explains the three ceilings. Append the tie-break rule to it. Using python3 (JSON-safe, no hand-editing):

```bash
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("tests/eval/baseline.json")
b = json.loads(p.read_text(encoding="utf-8"))
b["_metrics"] = b["_metrics"].rstrip() + (
    " TIE-BREAK (2026-08-06): max_usd is the cost metric of record. When the"
    " ceilings disagree, dollars win — token totals are >99% cache reads (they"
    " measure conversation shape, not spend) and wall clock measures the"
    " experience, not the bill (run 6: security-engineer was 53% of policy's"
    " wall clock and a sixth of its bill). Seconds and tokens remain as"
    " ceilings because each catches regressions dollars miss; they just do not"
    " outvote it. Bimodal exception unchanged: check _bimodal_cases before"
    " calling any policy/action number a regression.")
p.write_text(json.dumps(b, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
PY
```

**Formatting caveat:** before running, check the file's current indent style (`head -3 tests/eval/baseline.json`). If it is not 2-space-indented JSON, match whatever it is — a whole-file reformat buries the real diff. If `json.dumps(indent=2)` would reformat, instead edit the `_metrics` string with `Edit` on the exact old/new strings.

- [ ] **Step 2: Add the rule to the README's eval section**

Locate the paragraph beginning `Each run's misses become levers, ship in the next release` (README.md, eval section). Append this sentence to that paragraph:

```
Three ceilings guard each case — seconds, tokens, dollars — and when they disagree, **`max_usd` is the metric of record**: token totals are >99% cache reads and wall clock measures experience rather than spend, so dollars are the only ceiling that tracks what a regression actually costs (`tests/eval/baseline.json` `_metrics` has the full tie-break rule and the bimodal exception).
```

- [ ] **Step 3: Verify claims still sync**

Run: `python3 scripts/check_inventory_sync.py && python3 -c "import json; json.load(open('tests/eval/baseline.json')); print('valid json')"`
Expected: `ok: every manifest declares 1.38.1; …` and `valid json`.

- [ ] **Step 4: Commit**

```bash
git add tests/eval/baseline.json README.md
git commit -m "docs(evals): max_usd is the cost metric of record

Three ceilings each catch regressions the others miss, but no doc said
which wins when they disagree — every release re-argued it. Dollars win:
tokens are >99% cache reads, seconds measure the experience (run 6:
security-engineer was 53% of policy's wall clock, a sixth of its bill).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: The coordinator content hash — a deterministic feature-case trigger

The review's gap: "run the feature case when coordinator behaviour changes" has no named judge and will silently never fire. The fix: pin a sha256 of the delegation-steering surfaces; CI fails when they drift unmeasured. TDD — unit tests first, against a fake tree.

**Files:**
- Create: `tests/eval/test_coordinator_hash.py`
- Modify: `scripts/check_inventory_sync.py` (two new functions + one call in `main()`)
- Modify: `tests/eval/baseline.json` (new top-level `coordinator_hash` block, seeded in Step 6)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `coordinator_hash(root: pathlib.Path) -> str` — hex sha256 over: the raw bytes of `agents/delivery-coordinator.md`, then each distinct line starting `> **Interface:**` from `commands/*.md` (sorted, UTF-8), all joined with `b"\n"`.
  - `check_coordinator_hash(root: pathlib.Path) -> int` — 0 = pinned or waived, 1 = drift (with `::error` message).
  - baseline.json key shape (Task 6's changelog and the 1.40 plan rely on it):
    ```json
    "coordinator_hash": {
      "sha256": "<hex>",
      "as_of": "2026-08-06",
      "note": "...",
      "waivers": [{"date": "YYYY-MM-DD", "sha256": "<hex>", "reason": "..."}]
    }
    ```

- [ ] **Step 1: Write the failing tests**

Create `tests/eval/test_coordinator_hash.py`:

```python
"""Unit tests for the coordinator content hash in scripts/check_inventory_sync.py.

The hash pins the surfaces that steer delegation — the coordinator body and the
commands' shared Interface block — to the last billed run of the `feature` eval
case. CI cannot run billed evals; it CAN refuse to let those surfaces ship
changed without a human recording either a re-run or a dated waiver.
"""

import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "check_inventory_sync", ROOT / "scripts" / "check_inventory_sync.py")
inv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv)


def make_tree(base: pathlib.Path, body="coordinator v1",
              interface="> **Interface:** the shared block") -> pathlib.Path:
    (base / "agents").mkdir(parents=True)
    (base / "commands").mkdir()
    (base / "tests" / "eval").mkdir(parents=True)
    (base / "agents" / "delivery-coordinator.md").write_text(body, encoding="utf-8")
    for name in ("a.md", "b.md"):
        (base / "commands" / name).write_text(
            f"# cmd\n\n{interface}\n\nbody\n", encoding="utf-8")
    return base


def pin(base: pathlib.Path, sha: str, waivers=()) -> None:
    (base / "tests" / "eval" / "baseline.json").write_text(json.dumps({
        "coordinator_hash": {"sha256": sha, "as_of": "2026-08-06",
                             "note": "test", "waivers": list(waivers)},
    }), encoding="utf-8")


class TestCoordinatorHash(unittest.TestCase):
    def test_stable_across_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            self.assertEqual(inv.coordinator_hash(root), inv.coordinator_hash(root))

    def test_changes_when_coordinator_body_changes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            h1 = inv.coordinator_hash(make_tree(pathlib.Path(a), body="v1"))
            h2 = inv.coordinator_hash(make_tree(pathlib.Path(b), body="v2"))
            self.assertNotEqual(h1, h2)

    def test_changes_when_interface_line_changes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            h1 = inv.coordinator_hash(make_tree(
                pathlib.Path(a), interface="> **Interface:** one"))
            h2 = inv.coordinator_hash(make_tree(
                pathlib.Path(b), interface="> **Interface:** two"))
            self.assertNotEqual(h1, h2)

    def test_ignores_command_edits_outside_the_interface_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            before = inv.coordinator_hash(root)
            cmd = root / "commands" / "a.md"
            cmd.write_text(cmd.read_text(encoding="utf-8")
                           + "\nan unrelated prose edit\n", encoding="utf-8")
            self.assertEqual(before, inv.coordinator_hash(root))

    def test_check_passes_on_pinned_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            pin(root, inv.coordinator_hash(root))
            self.assertEqual(inv.check_coordinator_hash(root), 0)

    def test_check_fails_on_unpinned_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            pin(root, "0" * 64)
            self.assertEqual(inv.check_coordinator_hash(root), 1)

    def test_waiver_accepts_the_drift_it_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            current = inv.coordinator_hash(root)
            pin(root, "0" * 64, waivers=[
                {"date": "2026-08-06", "sha256": current, "reason": "test waiver"}])
            self.assertEqual(inv.check_coordinator_hash(root), 0)

    def test_check_fails_when_pin_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(pathlib.Path(tmp))
            (root / "tests" / "eval" / "baseline.json").write_text("{}", encoding="utf-8")
            self.assertEqual(inv.check_coordinator_hash(root), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail correctly**

Run: `python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_coordinator*.py' -v 2>&1 | tail -5`
Expected: every test ERRORS with `AttributeError: module 'check_inventory_sync' has no attribute 'coordinator_hash'` — the module imports fine (it has a `main()` guard), the functions don't exist yet. Any other failure mode: stop and investigate.

- [ ] **Step 3: Implement the two functions**

In `scripts/check_inventory_sync.py`: add `import hashlib` to the imports (keep alphabetical), then add above `main()`:

```python
def coordinator_hash(root: Path) -> str:
    """sha256 over the surfaces that steer delegation: the coordinator body,
    plus each distinct `> **Interface:**` line from commands/*.md (sorted).

    Whole-command hashing would fire on prose edits that change no behaviour;
    the Interface line is the only part of a command the eval `feature` case's
    checks depend on, and a guardrails ratchet already pins it byte-identical
    across all nine commands.
    """
    parts = [(root / "agents" / "delivery-coordinator.md").read_bytes()]
    lines = set()
    for path in sorted((root / "commands").glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("> **Interface:**"):
                lines.add(line)
    parts.extend(line.encode("utf-8") for line in sorted(lines))
    return hashlib.sha256(b"\n".join(parts)).hexdigest()


def check_coordinator_hash(root: Path) -> int:
    """The `feature` eval case's trigger, made deterministic.

    'Run it when coordinator behaviour changes' had no named judge and would
    silently never fire (2026-08-05 review, gap: feature-case trigger). CI
    cannot run billed evals; it can refuse to let delegation-steering surfaces
    ship changed unless a human records a re-run (update sha256/as_of) or a
    dated waiver in tests/eval/baseline.json.
    """
    baseline = json.loads(
        (root / "tests" / "eval" / "baseline.json").read_text(encoding="utf-8"))
    pinned = baseline.get("coordinator_hash")
    if not pinned:
        print("::error file=tests/eval/baseline.json::coordinator_hash pin is "
              "missing — seed it from scripts/check_inventory_sync.py "
              "coordinator_hash() and record as_of + note")
        return 1
    current = coordinator_hash(root)
    accepted = {pinned.get("sha256")}
    accepted.update(w.get("sha256") for w in pinned.get("waivers", []))
    if current in accepted:
        return 0
    print(f"::error file=agents/delivery-coordinator.md::delegation-steering "
          f"surfaces changed since the feature case last ran (hash "
          f"{current[:12]}… is neither pinned nor waived) — run "
          f"./tests/eval/run-evals.sh feature and update coordinator_hash in "
          f"tests/eval/baseline.json, or add a dated waiver with a reason")
    return 1
```

Then wire into `main()` — after the existing `fail = check_versions(version)` line, add:

```python
    if check_coordinator_hash(ROOT):
        fail = 1
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_coordinator*.py' -v 2>&1 | tail -4`
Expected: `Ran 8 tests … OK`.

- [ ] **Step 5: Verify the checker fails on the real tree (pin not yet seeded)**

Run: `python3 scripts/check_inventory_sync.py; echo "exit: $?"`
Expected: the `::error …coordinator_hash pin is missing…` message and `exit: 1`. This is the negative control for the wiring — the rule demonstrably fires before we seed it.

- [ ] **Step 6: Seed the pin**

```bash
python3 - <<'PY'
import importlib.util, json, pathlib
root = pathlib.Path(".").resolve()
spec = importlib.util.spec_from_file_location(
    "inv", root / "scripts" / "check_inventory_sync.py")
inv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv)
p = root / "tests" / "eval" / "baseline.json"
b = json.loads(p.read_text(encoding="utf-8"))
b["coordinator_hash"] = {
    "sha256": inv.coordinator_hash(root),
    "as_of": "2026-08-06",
    "note": ("Seeded at current content, NOT verified by a billed run: the "
             "2026-08-04 feature run predates the v1.36.0 Interface "
             "stage-budget edit, so no billed run has measured exactly this "
             "content. The 1.40 re-run replaces this note with its record."),
    "waivers": [],
}
p.write_text(json.dumps(b, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("seeded", b["coordinator_hash"]["sha256"][:12])
PY
```

(Same formatting caveat as Task 3 Step 1 — match the file's existing indent.)

- [ ] **Step 7: Verify the full gate goes green, then prove drift detection once**

```bash
python3 scripts/check_inventory_sync.py && echo GREEN
printf '\n' >> agents/delivery-coordinator.md
python3 scripts/check_inventory_sync.py; echo "drift exit: $?"
git checkout -- agents/delivery-coordinator.md
python3 scripts/check_inventory_sync.py && echo "GREEN again"
```
Expected: `GREEN` → the `::error …neither pinned nor waived…` message with `drift exit: 1` → `GREEN again`. (The append/restore is the live negative control; `git checkout --` restores the exact bytes.)

- [ ] **Step 8: Run every suite the change could touch**

Run: `python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py' 2>&1 | tail -3 && ./tests/guardrails.test.sh 2>&1 | tail -2`
Expected: eval units `OK` (existing cost-parser tests plus the 8 new), guardrails `140 passed, 0 failed`.

- [ ] **Step 9: Commit**

```bash
git add scripts/check_inventory_sync.py tests/eval/test_coordinator_hash.py tests/eval/baseline.json
git commit -m "feat(evals): pin delegation-steering surfaces to the last billed feature run

'Run the feature case when coordinator behaviour changes' had no named
judge and would silently never fire. Now a sha256 over the coordinator
body + the commands' shared Interface line is pinned in baseline.json;
check_inventory_sync fails CI on drift until a human records a re-run or
a dated waiver. Seeded at current content with an honest note: the
2026-08-04 run predates v1.36.0's Interface edit, so the 1.40 re-run is
what first verifies this exact content.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Scope eval run 7

**Files:**
- Create: `docs/evals/2026-08-06-run-7-scope.md`

**Interfaces:**
- Consumes: the audit vocabulary (Task 1), the metric of record (Task 3), the hash pin's note (Task 4).
- Produces: the hypothesis the 1.40 plan implements; referenced by the milestone spec.

- [ ] **Step 1: Write the scope document**

````markdown
# Eval run 7 — scope

Written before the run, unlike every predecessor: the
[2026-08-05 review](../requirements/2026-08-05-project-state-review.md) (gap 1)
found "run 7" existed only as a misleading checklist heading — run 6's own
closure wearing a forward-looking name. This document is what a run 7 is FOR.

## Hypothesis

**Teach → override → harvest works end to end on a real delivery.** Concretely,
on a throwaway copy of `tests/fixture-app`:

1. Rules taught via `/teach` land in `docs/team/conventions.md` in the
   Rule / Why / Scope / Source shape.
2. A delivery whose natural implementation crosses those rules produces code
   that **visibly obeys them where the default would differ** — the rules are
   chosen so the override is observable (e.g. integer-cents money, ULID keys).
3. The delivery-coordinator's end-of-delivery harvest **appends** to the team
   ledger without being asked — `docs/team/` grows; it does not merely survive.

This is the pack's flagship claim with zero example instances (review, gap 4).
Run 7 either produces the missing artifact or finds the feature broken on the
fixture before a user finds it broken in their repo. Both outcomes are wins.

## Composition

The standard five-case sweep (unchanged denominator, scorecard comparable to
runs 1–6) **plus** the new teach case, **plus** the `feature` case if the
coordinator hash pin (`tests/eval/baseline.json → coordinator_hash`) has
drifted by then — which 1.40's harvest fixes make likely. Expected spend:
sweep ~$12.50 + teach ~$5–8 + feature ~$7 if triggered.

## Measured by

The instrument this release hardened: 0 free-prose checks remain
(`docs/evals/2026-08-06-check-audit.md`), `max_usd` is the metric of record,
and the teach case's checks are artifact-based from day one — taught rule
reflected in produced code, ledger grown, delivery log present. Ceilings for
the new case are seeded from its first accepted run, never guessed.

## Deliberately not re-tested

Run 6's closed findings: the `->todo()` contradiction (v1.35.0), the stage
budget's placement (v1.36.0), the policy key's word-grep (v1.37.0), and the
n-plus-one "slowdown" (diagnosed as empirical verification, accepted). A run 7
finding that re-opens one of these must cite which regression, not re-argue
the original.
````

- [ ] **Step 2: Commit**

```bash
git add docs/evals/2026-08-06-run-7-scope.md
git commit -m "docs(evals): run 7 finally names a question

Hypothesis: teach → override → harvest works end to end on the fixture
app. Composition, spend, instrument, and what is deliberately not
re-tested — written BEFORE the run, unlike every predecessor.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Release 1.39.0

The repo's release ritual, spelled out because the executor may not carry session memory. **Precondition:** Tasks 1–5 committed, working tree clean.

**Files:**
- Modify: `VERSION`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json`, `gemini/gemini-extension.json`, `CHANGELOG.md`

- [ ] **Step 1: Bump the version surface**

```bash
printf '1.39.0\n' > VERSION
for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json \
         .cursor-plugin/plugin.json .cursor-plugin/marketplace.json \
         gemini/gemini-extension.json; do
  python3 - "$f" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
new, n = re.subn(r'("version"\s*:\s*)"1\.38\.1"', r'\g<1>"1.39.0"', t)
assert n == 1, (sys.argv[1], n)
p.write_text(new, encoding="utf-8")
PY
done
python3 scripts/build-gemini-extension.py >/dev/null
python3 scripts/check_inventory_sync.py
```
Expected: `ok: every manifest declares 1.39.0; …`.

- [ ] **Step 2: Write the changelog section**

Insert above the `## [1.38.1]` heading in `CHANGELOG.md`:

```markdown
## [1.39.0] - 2026-08-06

### Added

- **A deterministic trigger for the opt-in `feature` eval case.** "Run it when
  coordinator behaviour changes" had no named judge and would silently never
  fire. A sha256 over the delegation-steering surfaces — the coordinator body
  plus the nine commands' shared Interface line — is now pinned in
  `tests/eval/baseline.json`; `check_inventory_sync` fails CI on drift until a
  human records a re-run or a dated waiver. Seeded honestly: the pin notes that
  no billed run has measured exactly the current content, and the next billed
  run retires the note.
- **`docs/evals/2026-08-06-check-audit.md`** — all 25 answer-key checks
  classified by evidence source (16 artifact, 5 fixture-noun, 2
  format-contract, 2 free-prose). The sound greps are documented as sound so
  nobody "fixes" them; the classification rules bind future checks.
- **`docs/evals/2026-08-06-run-7-scope.md`** — run 7 named a question before
  being run: does teach → override → harvest work end to end on the fixture
  app? Scope, composition, spend, and what is deliberately not re-tested.

### Fixed

- **The answer key's last two free-prose greps.** `hygiene`'s
  `check_log 'duplicate'` and `check_log 'conflict'` failed runs that
  classified the planted items correctly in different words ("identical",
  "contradicts") — the same disease `check_update_guarded` fixed in v1.37.0.
  Both now accept the model's synonyms; the vocabularies are additive-only and
  ratchet-pinned.

### Changed

- **`max_usd` is the cost metric of record.** When the three ceilings disagree,
  dollars win: token totals are >99% cache reads and wall clock measures the
  experience, not the bill. Documented in `baseline.json`'s `_metrics` and the
  README's eval section; the bimodal `policy`/`action` exception is unchanged.
```

- [ ] **Step 3: Run every release gate locally**

```bash
./tests/guardrails.test.sh 2>&1 | tail -2
python3 -m unittest discover -s tests/console -t tests/console 2>&1 | tail -2
python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py' 2>&1 | tail -2
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
python3 scripts/check-hook-sync.py
shellcheck --severity=error install.sh && echo "shellcheck ok"
python3 scripts/build-gemini-extension.py >/dev/null && git diff --exit-code -- gemini/ && echo "gemini ok"
python3 scripts/build-codex-extension.py >/dev/null && git diff --exit-code -- codex/ && echo "codex ok"
git diff --exit-code -- scripts/console/dist && echo "dist untouched ok"
```
Expected: guardrails `140 passed`, both unittest suites `OK`, every gate `ok`. `dist untouched ok` **must** print — this release has no console changes.

- [ ] **Step 4: Commit, tag, push**

```bash
git add -A VERSION CHANGELOG.md .claude-plugin .cursor-plugin gemini
git commit -m "release: 1.39.0 — the instrument stops taking the model's word for it

The trust release of the prove-it milestone: all 25 answer-key checks
audited (the last two free-prose greps hardened), max_usd declared the
cost metric of record, the feature-case trigger made deterministic via a
pinned coordinator hash, and run 7 scoped before being run.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git tag v1.39.0
git push origin main
git push origin v1.39.0
```

- [ ] **Step 5: Watch CI, then publish the release**

```bash
RUN_ID=$(gh run list --branch main --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status --interval 20
```
Expected: conclusion `success` on all ten jobs. **Only then:**

```bash
python3 - <<'PY' > /tmp/notes-1.39.0.md
import re, pathlib
text = pathlib.Path("CHANGELOG.md").read_text(encoding="utf-8")
m = re.search(r"^## \[1\.39\.0\][^\n]*\n(.*?)(?=^## \[1\.38\.1\])", text, re.S | re.M)
print(m.group(1).strip())
PY
gh release create v1.39.0 \
  --title "v1.39.0 — The instrument stops taking the model's word for it" \
  --notes-file /tmp/notes-1.39.0.md
```

If CI fails: fix forward on main before the `gh release create` — the tag may be re-pointed only if nothing has been published yet.

---

## Self-review record (2026-08-06)

- **Spec coverage:** 1.39's four spec deliverables → Tasks 1–2 (audit + conversions), Task 3 (metric-of-record), Task 4 (hash trigger + seeding note), Task 5 (run-7 stub). Verification bullets → negative controls in Task 2 Step 5, Task 4 Steps 5 & 7; "hash rule has a test proving it fires on a coordinator edit and stays quiet otherwise" → Task 4 tests 2–4 + Step 7. Release mechanics → Task 6.
- **Placeholder scan:** none — every step carries exact content or exact commands.
- **Type consistency:** `coordinator_hash(root: Path) -> str` and `check_coordinator_hash(root: Path) -> int` used identically in Task 4's tests, implementation, and seeding script; baseline key shape identical in tests' `pin()`, the implementation's reads, and the seeding script.
- **Spec deviation, recorded:** the spec says checks convert prose→artifact; the audit found only 2 of 25 checks fragile and both are in a report-only case with no artifact to inspect, so the honest fix is synonym-hardening + ratchets, not conversion. The audit doc documents this reasoning — it satisfies the spec's intent (no check can fail a right answer over wording) by the means the evidence supports.
