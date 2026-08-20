#!/usr/bin/env bash
# The check kit + checks_* functions are dispatched dynamically ("checks_$name"),
# which shellcheck can't see — hence the file-wide suppression (SC2329 on >=0.10,
# SC2317 on the older shellcheck in ubuntu-latest CI).
# shellcheck disable=SC2317,SC2329
#
# Eval harness — proves the pack's agents actually find (or fix) the flaws
# planted in tests/fixture-app, and times every run.
#
# Each case:
#   1. copies the fixture app into a throwaway workdir
#   2. installs the pack into it via install.sh
#   3. runs one headless `claude -p "/<command> ..."` inside it
#   4. asserts against the answer key (agent output + files on disk)
#
# Usage:
#   ./tests/eval/run-evals.sh                    # run every case
#   ./tests/eval/run-evals.sh n-plus-one policy  # run selected cases
#   ./tests/eval/run-evals.sh --list             # list cases and exit
#   ./tests/eval/run-evals.sh feature            # opt-in case: the only one that
#                                               # must delegate (see OPT_IN_CASES)
#
# Env:
#   CLAUDE_BIN=claude   claude executable to use
#   EVAL_MODEL=         optional --model for the headless runs
#   EVAL_TIMEOUT=1200   per-case timeout in seconds
#   EVAL_PARALLEL=1     run cases concurrently (isolated workdirs make this safe;
#                       wall-clock drops to the slowest case, console prints per
#                       case as each finishes)
#   EVAL_JUDGE=1        also score each case against its rubric with an LLM judge
#                       (advisory — never changes the case verdict; one extra
#                       billed call per case)
#   EVAL_JUDGE_MODEL=   optional --model for the judge call
#   EVAL_JUDGE_TIMEOUT=300  per-judge timeout in seconds
#   KEEP_WORKDIR=1      keep throwaway workdirs for inspection
#   KEEP_TRANSCRIPT=1   keep each case's raw stream-json transcript. Megabytes per
#                       case, so off by default -- but <case>.cost.json counts tool
#                       calls by NAME only, and run 6 could not explain why
#                       n-plus-one spent 25 Bash calls without the commands themselves
#
# Headless runs use --dangerously-skip-permissions INSIDE the throwaway
# workdir only. Real agent runs are billed — this is a manual harness, not CI.
# Results land in tests/eval/results/<run-id>/ (gitignored).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FIXTURE="$ROOT/tests/fixture-app"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
EVAL_TIMEOUT="${EVAL_TIMEOUT:-1200}"
EVAL_JUDGE="${EVAL_JUDGE:-0}"
EVAL_JUDGE_TIMEOUT="${EVAL_JUDGE_TIMEOUT:-300}"
KEEP_WORKDIR="${KEEP_WORKDIR:-0}"
KEEP_TRANSCRIPT="${KEEP_TRANSCRIPT:-0}"

ALL_CASES=(n-plus-one policy action tests hygiene)

# Registered but NOT in the default sweep: runnable by name only
# (`./tests/eval/run-evals.sh feature`). `/make-feature` is parallel by
# construction, so it is the only case guaranteed to delegate — which is exactly
# what the coordinator's escalation and stage-budget rules need in order to be
# measured at all. It is also the most expensive case in the suite (`action`,
# the closest comparable, cost $5.16 in run 6), so adding it to every sweep
# would raise the standing cost of a run by roughly half for a signal that is
# only needed when coordinator behaviour changes. Opt in when it does.
# teach + teach-delivery: run 7's split hypothesis (docs/evals/2026-08-06-run-7-scope.md).
# Opt-in like feature: they measure coordinator/team-memory behaviour, which only
# needs re-measuring when that behaviour changes — the hash gate says when.
OPT_IN_CASES=(feature teach teach-delivery)

case_prompt() {
  case "$1" in
    n-plus-one) echo "/audit-n-plus-one posts.index" ;;
    policy)     echo "/add-policy Post" ;;
    action)     echo "/refactor-to-action PostController@store" ;;
    tests)      echo "/add-test PostController" ;;
    hygiene)    echo "/team-hygiene" ;;
    feature)    echo "/make-feature Tag --api" ;;
    teach)      echo "/teach New tables use ULID primary keys, never auto-increment integers — sortable and non-enumerable" ;;
    teach-delivery) echo "/make-feature Donation --api" ;;
  esac
}

case_desc() {
  case "$1" in
    n-plus-one) echo "finds the N+1 in posts.index (user + comments in Blade loop)" ;;
    policy)     echo "creates PostPolicy and guards the open update route" ;;
    action)     echo "extracts fat PostController@store into an Action" ;;
    tests)      echo "writes feature tests incl. update authorization" ;;
    hygiene)    echo "flags the planted duplicate/conflict/stale entries, applies nothing headless" ;;
    feature)    echo "scaffolds an API Tag feature across specialists — the only case that must delegate" ;;
    teach)      echo "records a taught rule in docs/team/conventions.md in the Rule/Why/Scope/Source contract" ;;
    teach-delivery) echo "delivers a feature that must OBEY two seeded taught rules where defaults differ, and harvest without being asked" ;;
  esac
}

# Intent-level rubric per case, for the optional LLM judge (EVAL_JUDGE=1).
# The regex answer key asserts *wording and paths*; a rubric asserts *outcome* —
# so it can catch a correct fix the regex missed, and a regex pass that left the
# flaw live (run 4 froze a live IDOR into a test that the regexes accepted).
# Keep rubrics outcome-shaped. Never name the regexes: the judge scores the run
# independently, and the harness reports where the two verdicts disagree.
case_rubric() {
  case "$1" in
    n-plus-one) cat <<'EOF'
- Identifies the N+1 on the posts.index path: the Blade loop reads the post's
  user and its comments with no eager loading.
- Proposes eager-loading the user relation, and a count-only load (withCount)
  for the comments count rather than hydrating whole comment collections.
- Names the actual offending file(s) in the fixture.
- Generic advice about N+1 with no fixture-specific diagnosis does not count.
EOF
      ;;
    policy) cat <<'EOF'
- A Policy governing Post actions exists.
- PostController@update actually enforces it, so a user who does not own a post
  is refused. The previously unguarded update route is closed.
- Enforcement is real and wired (the policy is invoked on the update path), not
  a Policy class left unreferenced by any controller, route or middleware.
EOF
      ;;
    action) cat <<'EOF'
- The inline work in PostController@store (validation, slug generation, mail
  fan-out, stats bookkeeping, logging) moves into a single-responsibility
  Action class that the controller delegates to.
- The mail fan-out no longer sits in the controller.
- Behaviour is preserved — the refactor is not a partial move that drops one of
  the store() responsibilities silently.
- Tests cover the refactored path.
EOF
      ;;
    tests) cat <<'EOF'
- Adds feature tests over the previously untested posts.* routes, including the
  update route.
- Authorization is probed by asserting the SECURE outcome (a non-owner is
  refused, 403). A test that asserts the current INSECURE behaviour (non-owner
  succeeds, 200) and thereby locks the IDOR in as expected behaviour is a FAIL
  even though it passes — the flaw must be surfaced, not frozen.
- The run states what it did not check rather than implying full coverage.
EOF
      ;;
    feature) cat <<'EOF'
- A Tag feature is scaffolded across the layers the command promises: schema
  (migration), model, an HTTP entry point, a registered route, and at least one
  feature test.
- The work is DELEGATED to specialists rather than done inline by the
  coordinator — this case exists to exercise multi-stage delegation, so a
  correct-looking feature built entirely on the main thread does not count.
- The progress board states how many stages the delivery expects and the
  observable condition that ends it, so the human can see the plan before the
  agents spend tokens on it.
- The run's own final answer carries VERIFIED (commands actually run, with
  counts) and NOT-CHECKED (what nobody verified, or "none").
- A stage that cannot verify the substance of its own brief is re-briefed or
  surfaced, not advanced past silently.
EOF
      ;;
    hygiene) cat <<'EOF'
- Produces a proposal table that classifies the two UUID-rule entries as
  duplicates and the Pest-vs-PHPUnit pair as a conflict.
- Names the LegacyPayments fact whose Verify command fails as stale.
- Applies NO edits to docs/team/conventions.md — a headless run has no human
  approval, and the sweep proposes only.
EOF
      ;;
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
  esac
}

# hygiene case: plant a duplicate pair, a conflict pair, and a stale-Verify
# fact in docs/team/. Headless runs get no approval, so the answer key
# asserts the proposal table (and that the ledger is untouched), not edits.
seed_hygiene_fixture() { # seed_hygiene_fixture <workdir>
  mkdir -p "$1/docs/team"
  cat >"$1/docs/team/conventions.md" <<'EOF'
# Team conventions — taught rules

## Use UUIDs for public identifiers
- **Rule:** Every publicly exposed ID is a UUID, never an auto-increment integer.
- **Why:** Enumeration resistance.
- **Scope:** backend-developer, database-developer
- **Source:** user, 2026-05-02

## Public identifiers are UUIDs
- **Rule:** Expose UUIDs in URLs and API payloads instead of integer primary keys.
- **Why:** Prevents ID enumeration.
- **Scope:** backend-developer
- **Source:** user, 2026-06-14

## Prefer Pest for new tests
- **Rule:** All new test files use Pest syntax.
- **Why:** Team standard since the v2 migration.
- **Scope:** qa-engineer
- **Source:** user, 2026-04-20

## Write new tests in PHPUnit style
- **Rule:** New tests use PHPUnit classes, not Pest closures.
- **Why:** Consistency with the legacy suite.
- **Scope:** qa-engineer
- **Source:** user, 2026-03-01

## Payments go through LegacyPayments service
- **Rule:** All payment writes call app/Services/LegacyPayments.php.
- **Why:** Single audited money path.
- **Scope:** backend-developer (payments)
- **Source:** user, 2026-02-10
- **Verify:** test -f app/Services/LegacyPayments.php

## Money is integer minor units
- **Rule:** Store and compute money as integer cents.
- **Why:** Float drift is unacceptable in invoicing.
- **Scope:** all agents
- **Source:** user, 2026-01-15
EOF
}

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

# ---------------------------------------------------------------- check kit --

WORK=""
LOG=""
FULL_LOG=""
SUBAGENT_LOG=""
CHECK_PASS=0
CHECK_FAIL=0
CHECK_LINES=()

record() { # record <exit-code> <description>
  if [ "$1" -eq 0 ]; then
    CHECK_PASS=$((CHECK_PASS + 1))
    CHECK_LINES+=("  PASS  $2")
  else
    CHECK_FAIL=$((CHECK_FAIL + 1))
    CHECK_LINES+=("  FAIL  $2")
  fi
}

check_log() { # check_log <regex> <description>
  grep -qiE "$1" "$LOG"
  record $? "output: $2"
}

check_log_anywhere() { # check_log_anywhere <regex> <description>
  # Like check_log, but greps $FULL_LOG -- every assistant turn concatenated,
  # not just $LOG's closing-summary-only text. For assertions on something the
  # Interface mandates EARLY (a board header, printed before any agent spends
  # tokens): run 7 (docs/evals/2026-08-06-run-7.md, finding 3) found check_log
  # scoring two false negatives here, because $LOG structurally cannot show a
  # turn earlier than the CLI's own closing `result` line.
  grep -qiE "$1" "$FULL_LOG"
  record $? "output: $2"
}

check_subagent_log() { # check_subagent_log <regex> <description>
  # Greps the derived subagent log -- assistant text from subagent turns only
  # (the complement of the main-thread full-text log). Per-stage specialist
  # returns (STATUS/DID/VERIFIED/NOT-CHECKED/FLAGS/NEXT) live on those turns
  # and are structurally invisible to full_text() (run 8). Must not read
  # the raw transcript: tests/guardrails.test.sh forbids checks_* from
  # grepping it, and this helper itself must not collapse to that.
  grep -qiE "$1" "$SUBAGENT_LOG"
  record $? "output: $2"
}

check_file() { # check_file <glob-relative-to-workdir> <description>
  compgen -G "$WORK/$1" >/dev/null
  record $? "file:   $2"
}

check_file_under() { # check_file_under <dir> <name-glob> <description> — any depth
  [ -n "$(find "$WORK/$1" -type f -name "$2" 2>/dev/null | head -1)" ]
  record $? "file:   $3"
}

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

check_in_files() { # check_in_files <regex> <relative-path> <description>
  grep -qriE "$1" "$WORK/$2" 2>/dev/null
  record $? "code:   $3"
}

check_not_in_files() { # check_not_in_files <regex> <relative-path> <description>
  if grep -qriE "$1" "$WORK/$2" 2>/dev/null; then
    record 1 "code:   $3"
  else
    record 0 "code:   $3"
  fi
}

check_update_guarded() { # check_update_guarded <description>
  # Planted flaw 2 is that PostController@update has no authorization. Asserting
  # that it is closed used to be `check_log 'update'` -- a grep for one word in the
  # final answer, which the 2026-07-29 literature audit named as an antipattern
  # citing this exact check. It then failed both ways for real: it passes on any
  # stray "update", and on 2026-08-05 it failed a run that closed the hole
  # correctly and simply never used the word (the rubric judge scored that run 5/5
  # and disagreed with the key).
  #
  # So assert the artifact instead, accepting either placement Laravel makes
  # idiomatic: the guard inline in the controller's update(), or in the
  # authorize() of the Form Request that update() type-hints.
  python3 - "$WORK" <<'PYGUARD' >/dev/null 2>&1
import pathlib, re, sys

work = pathlib.Path(sys.argv[1])
controller = work / "app/Http/Controllers/PostController.php"
if not controller.is_file():
    sys.exit(1)
src = controller.read_text(encoding="utf-8", errors="replace")

GUARD = re.compile(r"authorize\s*\(|Gate::|->can\s*\(|->cannot\s*\(")

# The update method: signature through the next method or end of class.
m = re.search(r"function\s+update\s*\((?P<sig>[^)]*)\)(?P<body>.*?)"
              r"(?=\n\s*(?:public|protected|private)\s+function|\n\}\s*$)",
              src, re.S)
if not m:
    sys.exit(1)

# (a) guard inline in the controller.
if GUARD.search(m.group("body")):
    sys.exit(0)

# (b) guard in the Form Request that update() type-hints.
for cls in re.findall(r"([A-Z]\w*Request)\s+\$", m.group("sig")):
    for candidate in work.glob(f"app/Http/Requests/{cls}.php"):
        text = candidate.read_text(encoding="utf-8", errors="replace")
        auth = re.search(r"function\s+authorize\s*\([^)]*\)(?P<body>.*?)"
                         r"(?=\n\s*(?:public|protected|private)\s+function|\n\}\s*$)",
                         text, re.S)
        if auth and GUARD.search(auth.group("body")):
            sys.exit(0)

sys.exit(1)
PYGUARD
  record $? "code:   $1"
}

check_delegated() { # check_delegated <min-distinct-agents> <description>
  # Reads the live board feed the emit-agent-events hook writes. The feed is
  # truncated at case start, so anything in it belongs to this run. No other case
  # asserts that delegation happened at all — `policy` and `action` each ran both
  # ways across runs 5 and 6 without the answer key noticing which.
  local feed="$WORK/.claude/agents-board.jsonl" count=0
  if [ -f "$feed" ] && command -v python3 >/dev/null 2>&1; then
    count="$(python3 - "$feed" <<'PYCOUNT' 2>/dev/null || echo 0
import json, sys
agents = set()
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue
    if isinstance(obj, dict) and obj.get("agent"):
        agents.add(obj["agent"])
print(len(agents))
PYCOUNT
)"
  fi
  [ "${count:-0}" -ge "$1" ]
  record $? "agents: $2 (saw ${count:-0} distinct)"
}

check_touched() { # check_touched <path-prefix> <description>
  git -C "$WORK" status --porcelain | grep -qE "^(\?\?|.M|A.) +\"?$1"
  record $? "diff:   $2"
}

# ------------------------------------------------------------- answer key ----

checks_n_plus_one() {
  check_log 'with\(|eager[- ]?load' "proposes eager loading"
  check_log 'withCount' "proposes withCount for the comments count"
  check_log 'PostController|index\.blade' "names the offending file"
  check_log 'comments' "identifies the comments relation"
}

checks_policy() {
  check_file "app/Policies/PostPolicy.php" "PostPolicy.php created"
  check_in_files 'authorize|Gate::|->can\(|can:' "app/Http/Controllers/PostController.php" "controller enforces the policy"
  check_update_guarded "the unguarded update route is closed"
}

checks_action() {
  check_file_under "app/Actions" "*.php" "Action class created"
  check_in_files 'Action' "app/Http/Controllers/PostController.php" "controller delegates to the Action"
  check_not_in_files 'Mail::to' "app/Http/Controllers/PostController.php" "mail fan-out moved out of the controller"
  check_touched "tests/" "tests added or updated"
}

checks_tests() {
  check_touched "tests/" "test files added or updated"
  check_in_files 'posts\.update|->put\(|->patch\(' "tests" "covers the update route"
  check_in_files 'assertForbidden|403' "tests" "probes the missing update authorization"
  check_log 'NOT-CHECKED' "return includes NOT-CHECKED calibration"
}

checks_feature() {
  check_file_under "database/migrations" "*tags*.php" "tags migration created"
  check_file_under "app/Models" "Tag.php" "Tag model created"
  check_in_files 'tag' "routes" "route registered for tags"
  check_touched "tests/" "feature test added"
  # The point of this case: the coordinator must delegate, not build it inline.
  check_delegated 2 "work was delegated to specialists"
  # Tranche item 2 — the board declares its budget and completion condition.
  check_log_anywhere 'done when:' "board declares a completion condition"
  # Orchestration-audit layer B (docs/superpowers/specs/2026-08-12-agent-orchestration-audit-design.md §3):
  # static file review can't prove the contract is followed at runtime, only declared on paper.
  # $FULL_LOG is main-thread turns only (scripts/eval-cost.py's full_text()) --
  # a per-stage specialist return is a subagent turn and structurally never
  # shows up here, so only the coordinator's own closing-answer contract
  # (Interface block's last sentence) can be asserted against this stream.
  check_log 'VERIFIED' "final answer carries VERIFIED"
  check_log 'NOT-CHECKED' "final answer carries NOT-CHECKED"
  # Opt-in shape for a future billed feature run that keeps <case>.subagent.log.
  # Do NOT uncomment without a transcript that has been inspected: this worktree
  # has no run-8/run-9 feature artifacts, and enabling these would fail the
  # case (or pass on the wrong evidence). Grep the derived subagent log via
  # check_subagent_log — never the raw transcript, never $FULL_LOG (run 8).
  # check_subagent_log 'STATUS:' "a specialist return carries STATUS"
  # check_subagent_log 'DID:' "a specialist return carries DID"
  # check_subagent_log 'VERIFIED:' "a specialist return carries VERIFIED"
  # check_subagent_log 'NOT-CHECKED:' "a specialist return carries NOT-CHECKED"
  # check_subagent_log 'FLAGS:' "a specialist return carries FLAGS"
  # check_subagent_log 'NEXT:' "a specialist return carries NEXT"
  # Per-stage returns are the stage files (this helper); $SUBAGENT_LOG stays an instrument (run 10).
  check_file "docs/team/stack.md" "harvest persisted the stack snapshot (routing-table artifact)"
  check_file_under "docs/delivery" "log.md" "harvest persisted the delivery log (routing-table artifact)"
  check_stage_return_files 
}

checks_hygiene() {
  # Free-prose greps hardened 2026-08-06 (docs/evals/2026-08-06-check-audit.md):
  # a run that says "identical"/"redundant" or "contradicts" is right and used
  # to fail the key — the same disease check_update_guarded fixed in v1.37.0.
  # Stems on purpose: duplicat~ covers duplicate/duplicated/duplication.
  check_log 'duplicat|identical|redundan|twin' "classifies the UUID twin entries as duplicate"
  check_log 'conflict|contradict|disagree|mutually exclusive' "classifies the Pest-vs-PHPUnit pair as conflict"
  check_log 'LegacyPayments' "names the stale-Verify payments fact"
  # Headless = no approval: the ledger must be untouched (proposal only).
  git -C "$WORK" diff --quiet -- docs/team/conventions.md
  record $? "diff:   applies nothing without approval"
}

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

checks_teach_delivery() {
  # Obedience: both taught rules land where Laravel's default points the other
  # way. Artifact checks on the migration/model — a delivery that ignores the
  # ledger produces decimal('amount') and $table->id(), and fails here.
  check_file_under "database/migrations" "*donations*.php" "donations migration created"
  check_in_files 'cents' "database/migrations" "money lands as integer cents (taught rule 1)"
  # Any decimal/float/double column in the donations migration fails the money
  # rule — anchoring on the column NAME ('amount…) let decimal('price_cents')
  # slip by, and the migration this case scaffolds has no legitimate float
  # column. Scoped to the donations migration so unrelated fixture migrations
  # cannot trip it.
  if ls "$WORK"/database/migrations/*donations*.php >/dev/null 2>&1 \
     && ! grep -qiE '(decimal|float|double)\(' "$WORK"/database/migrations/*donations*.php 2>/dev/null; then
    record 0 "code:   no float/decimal column in the donations migration"
  else
    record 1 "code:   no float/decimal column in the donations migration"
  fi
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
  check_log_anywhere 'done when:' "board declares a completion condition"
}

# ---------------------------------------------------------------- plumbing ---

run_with_timeout() { # run_with_timeout <seconds> <cmd...>
  local secs="$1"
  shift
  "$@" &
  local pid=$!
  (
    # Deadline off the wall clock, not a sleep counter — counting sleeps
    # drifts under load (run 3: a case sailed 600s past its cap). TERM
    # first, KILL 30s later: claude finishes its in-flight turn on TERM.
    deadline=$((SECONDS + secs))
    while kill -0 "$pid" 2>/dev/null && [ "$SECONDS" -lt "$deadline" ]; do
      sleep 5
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null
      sleep 30
      kill -KILL "$pid" 2>/dev/null
    fi
  ) &
  local watchdog=$!
  wait "$pid"
  local rc=$?
  kill "$watchdog" 2>/dev/null
  wait "$watchdog" 2>/dev/null
  return "$rc"
}

JUDGE_CELL=""

# Rubric judge (EVAL_JUDGE=1). Advisory by design: it prints, persists, and
# reports disagreement with the regex verdict, but never touches CHECK_FAIL or
# the case verdict — runs 1-5 stay comparable, and a judge outage can't fail a
# release. Nondeterministic output needs a rubric, not exact-match assertions
# (Azure orchestration guidance); the regexes stay as the cheap stable floor.
judge_case() { # judge_case <name> <results-dir> <regex-verdict>
  local name="$1" results="$2" regex_verdict="$3"
  JUDGE_CELL=""

  if ! command -v python3 >/dev/null 2>&1; then
    echo "   judge: skipped (verdict parsing needs python3)"
    return 0
  fi

  # Neutral cwd — the judge must not load the pack installed in the case
  # workdir, or go reading the fixture app instead of the evidence it was given.
  local jdir
  jdir="$(mktemp -d -t "laravel-agents-judge-$name.XXXXXX")"

  local prompt
  prompt="$(
    printf 'Score one run of an automated coding agent against a rubric.\n'
    printf 'Judge ONLY from the evidence below. Do not credit work it does not show.\n\n'
    printf 'RUBRIC — what a correct run must achieve:\n%s\n\n' "$(case_rubric "$name")"
    printf 'EVIDENCE\n--- agent transcript (tail) ---\n%s\n' "$(tail -c 20000 "$LOG" 2>/dev/null)"
    printf '\n--- git status ---\n%s\n' "$(cat "$results/$name.status.txt" 2>/dev/null)"
    printf '\n--- git diff (head) ---\n%s\n' "$(head -c 20000 "$results/$name.diff.patch" 2>/dev/null)"
    printf '\nReply with ONE JSON object — no prose, no code fence:\n'
    printf '{"verdict":"pass"|"fail","score":1-5,"unmet":["rubric points not met"],'
    printf '"rationale":["at most 3 short bullets"]}\n'
    printf 'score: 5 = fully met, 3 = partly met, 1 = not met.\n'
    printf 'A run that satisfies the letter of the rubric while leaving the '
    printf 'underlying flaw live is a fail.\n'
  )"

  local -a jcmd=("$CLAUDE_BIN" -p "$prompt" --dangerously-skip-permissions)
  if [ -n "${EVAL_JUDGE_MODEL:-}" ]; then
    jcmd+=(--model "$EVAL_JUDGE_MODEL")
  fi

  local rawf="$results/$name.judge.raw.txt"
  (cd "$jdir" && run_with_timeout "$EVAL_JUDGE_TIMEOUT" "${jcmd[@]}") >"$rawf" 2>/dev/null
  rm -rf "$jdir"

  local parsed
  parsed="$(python3 - "$rawf" "$results/$name.judge.json" "$regex_verdict" <<'PY' || true
import json, re, sys

raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r"\{.*\}", raw, re.S)
if not m:
    sys.exit(0)
try:
    d = json.loads(m.group(0))
except ValueError:
    sys.exit(0)

verdict = str(d.get("verdict", "")).strip().lower()
if verdict not in ("pass", "fail"):
    sys.exit(0)

with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(d, fh, indent=2)

score = d.get("score")
unmet = [str(u) for u in (d.get("unmet") or [])][:3]
disagrees = verdict != sys.argv[3].strip().lower()

cell = f"{verdict.upper()} {score}/5" if score is not None else verdict.upper()
if disagrees:
    cell += " !"
parts = [cell.replace(" !", "")]
if disagrees:
    parts.append("DISAGREES with the regex verdict")
if unmet:
    parts.append("unmet: " + "; ".join(unmet))
print(cell + "|" + " — ".join(parts))
PY
  )"

  if [ -z "$parsed" ]; then
    echo "   judge: no parsable verdict (raw kept: $rawf)"
    return 0
  fi

  JUDGE_CELL="${parsed%%|*}"
  echo "   judge: ${parsed#*|}"
}

run_case() { # run_case <name> <results-dir>
  local name="$1" results="$2"
  local prompt
  prompt="$(case_prompt "$name")"

  WORK="$(mktemp -d -t "laravel-agents-eval-$name.XXXXXX")"
  LOG="$results/$name.log"
  FULL_LOG="$results/$name.full-text.log"
  SUBAGENT_LOG="$results/$name.subagent.log"
  CHECK_PASS=0
  CHECK_FAIL=0
  CHECK_LINES=()

  echo "== $name — $(case_desc "$name")"
  echo "   prompt:  $prompt"
  echo "   workdir: $WORK"

  cp -R "$FIXTURE/." "$WORK/"
  # Start every case's board feed empty. Run 5 was analysed with a feed that
  # opened with two qa-engineer stages of exactly 3000ms and 5000ms in EVERY
  # case -- committed telemetry from an unrelated 2026-07-30 session, copied in
  # with the fixture. Read naively it said `hygiene` ran qa-engineer. Truncating
  # here means the feed is this case's events and nothing else, whatever the
  # fixture happens to carry.
  mkdir -p "$WORK/.claude"
  : >"$WORK/.claude/agents-board.jsonl"
  if ! bash "$ROOT/install.sh" "$WORK" >"$results/$name.install.log" 2>&1; then
    echo "   ERROR: install.sh failed — see $results/$name.install.log"
    return 1
  fi

  [ "$name" = "hygiene" ] && seed_hygiene_fixture "$WORK"
  [ "$name" = "teach-delivery" ] && seed_taught_fixture "$WORK"

  git -C "$WORK" init -q
  git -C "$WORK" -c user.email=eval@example.com -c user.name=eval add -A
  git -C "$WORK" -c user.email=eval@example.com -c user.name=eval commit -qm baseline

  # stream-json (not plain text) so the transcript carries per-turn `usage` with
  # the input/output/cache split -- the only way to price a run rather than guess
  # at it. It does NOT go to $LOG: the answer key greps $LOG, and JSON there
  # would silently start matching tool inputs and thinking text. $LOG is rebuilt
  # below from the result field, which is exactly what plain `-p` prints.
  local -a cmd=("$CLAUDE_BIN" -p "$prompt" --dangerously-skip-permissions
                --output-format stream-json --verbose)
  if [ -n "${EVAL_MODEL:-}" ]; then
    cmd+=(--model "$EVAL_MODEL")
  fi

  local stream="$results/$name.stream.jsonl"
  local start=$SECONDS rc=0
  (cd "$WORK" && run_with_timeout "$EVAL_TIMEOUT" "${cmd[@]}") >"$stream" 2>&1 || rc=$?
  local dur=$((SECONDS - start))

  # Rebuild the human-readable log that the checks and the findings doc both
  # read. A timed-out run emits no result line, so eval-cost falls back to the
  # concatenated assistant text; if even that is empty it exits 2 and we keep the
  # raw stream as the only evidence rather than leaving an empty log unexplained.
  if ! python3 "$ROOT/scripts/eval-cost.py" --transcript "$stream" \
       --rates "$ROOT/tests/eval/model-rates.json" --text-only >"$LOG" 2>/dev/null; then
    echo "   WARNING: no final text in the transcript — keeping $name.stream-kept.jsonl"
    cp "$stream" "$results/$name.stream-kept.jsonl"
  fi

  # Every assistant turn, concatenated -- for checks (check_log_anywhere) that
  # assert on something said EARLY, which $LOG's closing-only text cannot show.
  # `>"$FULL_LOG"` already creates an empty file before eval-cost.py runs, even
  # on failure (no assistant text found) -- leave it empty rather than rm it,
  # so check_log_anywhere's later grep sees an empty file (a clean FAIL), not
  # a "No such file or directory" error.
  python3 "$ROOT/scripts/eval-cost.py" --transcript "$stream" \
    --rates "$ROOT/tests/eval/model-rates.json" --full-text >"$FULL_LOG" 2>/dev/null || true

  # Subagent assistant text only -- complement of $FULL_LOG. Empty file on
  # failure (no subagent turn produced text), same as $FULL_LOG, so a later
  # check_subagent_log grep is a clean FAIL rather than a missing-file error.
  python3 "$ROOT/scripts/eval-cost.py" --transcript "$stream" \
    --rates "$ROOT/tests/eval/model-rates.json" --subagent-text >"$SUBAGENT_LOG" 2>/dev/null || true

  # Per-agent input/output/cache tokens, tool-call counts, and the run's billed
  # cost. Models come from the transcript (message.model), so a re-tiered agent
  # is priced at what actually billed rather than what the pack declares.
  python3 "$ROOT/scripts/eval-cost.py" --transcript "$stream" \
    --rates "$ROOT/tests/eval/model-rates.json" >"$results/$name.cost.json" 2>/dev/null \
    || echo "   WARNING: could not summarise cost for $name"

  # Megabytes per case, and tests/eval/results/ is committed. The derived summary
  # is the artifact; the raw stream is scaffolding -- unless you are diagnosing
  # *why* an agent spent what it spent, which needs the tool inputs the summary
  # does not keep (run-6 finding: 25 Bash calls, no way to see the commands).
  if [ "$KEEP_TRANSCRIPT" = "1" ]; then
    echo "   kept transcript: $name.stream.jsonl ($(wc -c <"$stream" | tr -d ' ') bytes)"
  else
    rm -f "$stream"
  fi

  if [ "$dur" -ge "$EVAL_TIMEOUT" ]; then
    echo "   TIMED OUT after ${dur}s"
  elif [ "$rc" -ne 0 ]; then
    echo "   claude exited $rc after ${dur}s (checks still run — output may be partial)"
  fi

  "checks_$(echo "$name" | tr '-' '_')"

  # Evidence for the findings doc + the rubric judge: what changed, and the
  # per-agent event timing. Status is captured BEFORE the intent-to-add below, so
  # it still reports new files as `??` rather than `A `.
  git -C "$WORK" status --porcelain >"$results/$name.status.txt" 2>/dev/null
  # `git diff` does not show untracked files, so a case whose job is CREATING a
  # file produced a diff with that file's body missing entirely. Run 6's judge
  # caught it on `action`: the new Action class existed and passed its checks, but
  # its body was absent from the evidence, so behaviour preservation could only be
  # taken on trust. `add -N` records intent-to-add (contents unstaged) purely so
  # the diff includes new files; it runs after the checks and after status, so it
  # changes no verdict. Throwaway workdir, so staging state is irrelevant.
  git -C "$WORK" add -N . >/dev/null 2>&1 || true
  git -C "$WORK" diff >"$results/$name.diff.patch" 2>/dev/null
  if [ -f "$WORK/.claude/agents-board.jsonl" ]; then
    cp "$WORK/.claude/agents-board.jsonl" "$results/$name.agent-events.jsonl"
  fi

  printf '%s\n' "${CHECK_LINES[@]}"
  local verdict=PASS
  [ "$CHECK_FAIL" -gt 0 ] && verdict=FAIL
  echo "   $verdict — $CHECK_PASS/$((CHECK_PASS + CHECK_FAIL)) checks, ${dur}s"

  if [ -s "$results/$name.cost.json" ] && command -v python3 >/dev/null 2>&1; then
    python3 - "$results/$name.cost.json" <<'PY' || true
import json, sys
d = json.load(open(sys.argv[1]))
billed, attr = d["billed"], d["attributed"]
if billed["usd"] is not None:
    check = billed["rate_table_check"]
    stale = "" if check["agrees"] is not False else "  (RATE TABLE STALE — see model-rates.json)"
    print(f"   cost: ${billed['usd']:.2f} billed{stale}")
tok = attr["total"]
share = f", {attr['coverage_of_billed']:.0%} of billed" if attr["coverage_of_billed"] else ""
print(f"   attributed: {tok['tokens']:,} tokens "
      f"({tok['input_tokens']:,} in / {tok['output_tokens']:,} out / "
      f"{tok['cache_read_tokens'] + tok['cache_write_1h_tokens'] + tok['cache_write_5m_tokens']:,} cache)"
      f"{share}")
top = sorted(attr["agents"].items(), key=lambda kv: -kv[1]["tokens"])[:4]
for agent, a in top:
    calls = sum(a["tools"].values())
    print(f"         {agent:22} {a['tokens']:>9,} tok  ${a['usd']:.2f}  "
          f"{calls:>3} tool calls  {','.join(a['models']) or '-'}")
absent = attr.get("launched_without_measured_turns") or []
if absent:
    # Almost always background/async subagents: launched, but no turn of theirs
    # landed in the transcript. They sort last by token count, so say it outright
    # rather than leaving a zero at the bottom of the list to be noticed.
    print(f"         launched but unmeasured (async?): {', '.join(absent)}")
if d["unpriced_models"]:
    print(f"   WARNING: unpriced models: {', '.join(d['unpriced_models'])}")
PY
  fi

  JUDGE_CELL=""
  [ "$EVAL_JUDGE" = "1" ] && judge_case "$name" "$results" "$verdict"

  # Soft timing ratchet: sequential runs only (parallel contention inflates
  # durations 2-6x — see tests/eval/README.md). Warns, never fails: timings
  # are machine- and API-load-dependent. Ceilings live in baseline.json.
  if [ "$MODE" = "sequential" ] && [ -f "$ROOT/tests/eval/baseline.json" ] \
     && command -v python3 >/dev/null 2>&1; then
    python3 - "$name" "$dur" "$ROOT/tests/eval/baseline.json" "$results/$name.cost.json" <<'PY' || true
import json, sys
name, dur, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
cost_path = sys.argv[4] if len(sys.argv) > 4 else None
try:
    case = json.load(open(path)).get("cases", {}).get(name)
except Exception:
    sys.exit(0)
cap = (case or {}).get("max_seconds")
if cap is not None:
    state = "within" if dur <= cap else "REGRESSED vs"
    print(f"   baseline: {state} {cap}s ceiling ({dur}s)")
# Cost ratchets: dollars AND tokens. Each catches a regression the other misses
# -- a sonnet -> opus re-tier keeps tokens flat and triples the bill, while
# dollars drift with published prices and tokens do not. See baseline.json's
# _metrics. Token totals are >99% cache reads (run-6 finding), so read tokens as
# work volume and let dollars speak for cost.
summary = None
if cost_path:
    try:
        summary = json.load(open(cost_path))
    except Exception:
        summary = None
if summary is not None:
    usd_cap = (case or {}).get("max_usd")
    billed = (summary.get("billed") or {}).get("usd")
    if billed is None:
        pass
    elif usd_cap is None:
        print(f"   baseline: cost ceiling unseeded (${billed:.2f} billed this run)")
    else:
        state = "within" if billed <= usd_cap else "REGRESSED vs"
        print(f"   baseline: {state} ${usd_cap:.2f} cost ceiling (${billed:.2f} billed)")

    tok_cap = (case or {}).get("max_tokens")
    actual = summary["attributed"]["total"]["tokens"]
    if tok_cap is None:
        print(f"   baseline: token ceiling unseeded ({actual:,} tokens this run)")
    else:
        state = "within" if actual <= tok_cap else "REGRESSED vs"
        print(f"   baseline: {state} {tok_cap:,}-token ceiling ({actual:,} tokens)")
PY
  fi
  echo

  if [ "$EVAL_JUDGE" = "1" ]; then
    echo "| $name | $verdict | $CHECK_PASS/$((CHECK_PASS + CHECK_FAIL)) | ${dur}s | ${JUDGE_CELL:-—} |" >"$results/.$name.row"
  else
    echo "| $name | $verdict | $CHECK_PASS/$((CHECK_PASS + CHECK_FAIL)) | ${dur}s |" >"$results/.$name.row"
  fi
  printf '%s\n' "${CHECK_LINES[@]}" >"$results/$name.checks.txt"

  if [ "$KEEP_WORKDIR" != "1" ]; then
    rm -rf "$WORK"
  else
    echo "   workdir kept: $WORK"
  fi

  [ "$verdict" = PASS ]
}

# -------------------------------------------------------------------- main ---

if [ "${1:-}" = "--list" ]; then
  for c in "${ALL_CASES[@]}"; do
    printf '  %-12s %s\n' "$c" "$(case_desc "$c")"
  done
  printf '\n  opt-in (run by name, excluded from the default sweep):\n'
  for c in "${OPT_IN_CASES[@]}"; do
    printf '  %-12s %s\n' "$c" "$(case_desc "$c")"
  done
  exit 0
fi

if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  echo "error: '$CLAUDE_BIN' not found on PATH (set CLAUDE_BIN=...)" >&2
  exit 1
fi

CASES=("$@")
[ "${#CASES[@]}" -eq 0 ] && CASES=("${ALL_CASES[@]}")
for c in "${CASES[@]}"; do
  if [ -z "$(case_prompt "$c")" ]; then
    echo "error: unknown case '$c' (try --list)" >&2
    exit 1
  fi
done

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RESULTS="$ROOT/tests/eval/results/$RUN_ID"
mkdir -p "$RESULTS"

MODE=sequential
[ "${EVAL_PARALLEL:-0}" = "1" ] && [ "${#CASES[@]}" -gt 1 ] && MODE=parallel
JUDGE_NOTE=""
[ "$EVAL_JUDGE" = "1" ] && JUDGE_NOTE=", rubric judge on (advisory)"
echo "eval run $RUN_ID — ${#CASES[@]} case(s), timeout ${EVAL_TIMEOUT}s each, $MODE$JUDGE_NOTE"
echo "results: $RESULTS"
echo

FAILED=0
if [ "$MODE" = parallel ]; then
  # Each case runs in its own subshell (run_case's globals are per-process),
  # console buffered per case and printed in launch order as cases finish.
  PIDS=()
  for c in "${CASES[@]}"; do
    run_case "$c" "$RESULTS" >"$RESULTS/.$c.console" 2>&1 &
    PIDS+=($!)
  done
  i=0
  for c in "${CASES[@]}"; do
    wait "${PIDS[$i]}" || FAILED=$((FAILED + 1))
    cat "$RESULTS/.$c.console"
    rm -f "$RESULTS/.$c.console"
    i=$((i + 1))
  done
else
  for c in "${CASES[@]}"; do
    run_case "$c" "$RESULTS" || FAILED=$((FAILED + 1))
  done
fi

{
  echo "# Eval run $RUN_ID"
  echo
  if [ "$EVAL_JUDGE" = "1" ]; then
    echo "| case | verdict | checks | duration | judge |"
    echo "| ---- | ------- | ------ | -------- | ----- |"
  else
    echo "| case | verdict | checks | duration |"
    echo "| ---- | ------- | ------ | -------- |"
  fi
  for c in "${CASES[@]}"; do
    cat "$RESULTS/.$c.row" 2>/dev/null
    rm -f "$RESULTS/.$c.row"
  done
} >"$RESULTS/summary.md"

echo "done: $((${#CASES[@]} - FAILED))/${#CASES[@]} cases passed — summary: $RESULTS/summary.md"
exit "$FAILED"
