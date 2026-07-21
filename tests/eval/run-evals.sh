#!/usr/bin/env bash
# The check kit + checks_* functions are dispatched dynamically ("checks_$name"),
# which shellcheck can't see — hence the file-wide SC2329 suppression.
# shellcheck disable=SC2329
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
KEEP_WORKDIR="${KEEP_WORKDIR:-0}"

ALL_CASES=(n-plus-one policy action tests)

case_prompt() {
  case "$1" in
    n-plus-one) echo "/audit-n-plus-one posts.index" ;;
    policy)     echo "/add-policy Post" ;;
    action)     echo "/refactor-to-action PostController@store" ;;
    tests)      echo "/add-test PostController" ;;
  esac
}

case_desc() {
  case "$1" in
    n-plus-one) echo "finds the N+1 in posts.index (user + comments in Blade loop)" ;;
    policy)     echo "creates PostPolicy and guards the open update route" ;;
    action)     echo "extracts fat PostController@store into an Action" ;;
    tests)      echo "writes feature tests incl. update authorization" ;;
  esac
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
  if ! bash "$ROOT/install.sh" "$WORK" >"$results/$name.install.log" 2>&1; then
    echo "   ERROR: install.sh failed — see $results/$name.install.log"
    return 1
  fi

  git -C "$WORK" init -q
  git -C "$WORK" -c user.email=eval@example.com -c user.name=eval add -A
  git -C "$WORK" -c user.email=eval@example.com -c user.name=eval commit -qm baseline

  local -a cmd=("$CLAUDE_BIN" -p "$prompt" --dangerously-skip-permissions)
  if [ -n "${EVAL_MODEL:-}" ]; then
    cmd+=(--model "$EVAL_MODEL")
  fi

  local start=$SECONDS rc=0
  (cd "$WORK" && run_with_timeout "$EVAL_TIMEOUT" "${cmd[@]}") >"$LOG" 2>&1 || rc=$?
  local dur=$((SECONDS - start))

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
  echo

  echo "| $name | $verdict | $CHECK_PASS/$((CHECK_PASS + CHECK_FAIL)) | ${dur}s |" >"$results/.$name.row"
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
echo "eval run $RUN_ID — ${#CASES[@]} case(s), timeout ${EVAL_TIMEOUT}s each, $MODE"
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
  echo "| case | verdict | checks | duration |"
  echo "| ---- | ------- | ------ | -------- |"
  for c in "${CASES[@]}"; do
    cat "$RESULTS/.$c.row" 2>/dev/null
    rm -f "$RESULTS/.$c.row"
  done
} >"$RESULTS/summary.md"

echo "done: $((${#CASES[@]} - FAILED))/${#CASES[@]} cases passed — summary: $RESULTS/summary.md"
exit "$FAILED"
