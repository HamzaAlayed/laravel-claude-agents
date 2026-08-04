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

ALL_CASES=(n-plus-one policy action tests hygiene)

case_prompt() {
  case "$1" in
    n-plus-one) echo "/audit-n-plus-one posts.index" ;;
    policy)     echo "/add-policy Post" ;;
    action)     echo "/refactor-to-action PostController@store" ;;
    tests)      echo "/add-test PostController" ;;
    hygiene)    echo "/team-hygiene" ;;
  esac
}

case_desc() {
  case "$1" in
    n-plus-one) echo "finds the N+1 in posts.index (user + comments in Blade loop)" ;;
    policy)     echo "creates PostPolicy and guards the open update route" ;;
    action)     echo "extracts fat PostController@store into an Action" ;;
    tests)      echo "writes feature tests incl. update authorization" ;;
    hygiene)    echo "flags the planted duplicate/conflict/stale entries, applies nothing headless" ;;
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
    hygiene) cat <<'EOF'
- Produces a proposal table that classifies the two UUID-rule entries as
  duplicates and the Pest-vs-PHPUnit pair as a conflict.
- Names the LegacyPayments fact whose Verify command fails as stale.
- Applies NO edits to docs/team/conventions.md — a headless run has no human
  approval, and the sweep proposes only.
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

# ---------------------------------------------------------------- check kit --

WORK=""
LOG=""
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

check_file() { # check_file <glob-relative-to-workdir> <description>
  compgen -G "$WORK/$1" >/dev/null
  record $? "file:   $2"
}

check_file_under() { # check_file_under <dir> <name-glob> <description> — any depth
  [ -n "$(find "$WORK/$1" -type f -name "$2" 2>/dev/null | head -1)" ]
  record $? "file:   $3"
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
  check_log 'update' "covers the unguarded update route"
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

checks_hygiene() {
  check_log 'duplicate' "classifies the UUID twin entries as duplicate"
  check_log 'conflict' "classifies the Pest-vs-PHPUnit pair as conflict"
  check_log 'LegacyPayments' "names the stale-Verify payments fact"
  # Headless = no approval: the ledger must be untouched (proposal only).
  git -C "$WORK" diff --quiet -- docs/team/conventions.md
  record $? "diff:   applies nothing without approval"
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
  : >"$WORK/.claude/agents-board.jsonl"
  if ! bash "$ROOT/install.sh" "$WORK" >"$results/$name.install.log" 2>&1; then
    echo "   ERROR: install.sh failed — see $results/$name.install.log"
    return 1
  fi

  [ "$name" = "hygiene" ] && seed_hygiene_fixture "$WORK"

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

  # Per-agent input/output/cache tokens, tool-call counts, and the run's billed
  # cost. Models come from the transcript (message.model), so a re-tiered agent
  # is priced at what actually billed rather than what the pack declares.
  python3 "$ROOT/scripts/eval-cost.py" --transcript "$stream" \
    --rates "$ROOT/tests/eval/model-rates.json" >"$results/$name.cost.json" 2>/dev/null \
    || echo "   WARNING: could not summarise cost for $name"

  # Megabytes per case, and tests/eval/results/ is committed. The derived summary
  # is the artifact; the raw stream is scaffolding.
  rm -f "$stream"

  if [ "$dur" -ge "$EVAL_TIMEOUT" ]; then
    echo "   TIMED OUT after ${dur}s"
  elif [ "$rc" -ne 0 ]; then
    echo "   claude exited $rc after ${dur}s (checks still run — output may be partial)"
  fi

  "checks_$(echo "$name" | tr '-' '_')"

  # Evidence for the findings doc: what changed + per-agent event timing.
  git -C "$WORK" status --porcelain >"$results/$name.status.txt" 2>/dev/null
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
