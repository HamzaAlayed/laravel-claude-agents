#!/usr/bin/env bash
# Zero-dependency test harness for the guardrail hook scripts.
#
# Why not bats? These tests must run anywhere — a contributor's laptop and CI —
# with nothing to install. Pure bash + coreutils is the lowest common denominator.
#
#   ./tests/guardrails.test.sh          # run all tests
#
# Exit code is the number of failures (0 = all green).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$SCRIPT_DIR/scripts"

PASS=0
FAIL=0

# run_hook <script> <json-on-stdin> -> echoes exit code
run_hook() {
  local script="$1" json="$2"
  printf '%s' "$json" | bash "$SCRIPTS/$script" >/dev/null 2>&1
  echo $?
}

# run_hook_noparsers <script> <json> -> runs with a PATH that has neither jq nor
# python3, exercising the raw-payload fallback (the old fail-open hole).
run_hook_noparsers() {
  local script="$1" json="$2"
  local sandbox
  sandbox="$(mktemp -d)"
  # Symlink only the coreutils the scripts need — deliberately NOT jq/python3.
  local tool
  for tool in cat tr grep sed basename mktemp dirname; do
    local path
    path="$(command -v "$tool" 2>/dev/null || true)"
    if [ -n "$path" ]; then
      ln -s "$path" "$sandbox/$tool" 2>/dev/null || true
    fi
  done
  # Invoke bash by absolute path: a `PATH=… bash` prefix would resolve `bash`
  # itself against the stripped PATH and fail with 127.
  local bash_bin
  bash_bin="$(command -v bash)"
  printf '%s' "$json" | PATH="$sandbox" "$bash_bin" "$SCRIPTS/$script" >/dev/null 2>&1
  local code=$?
  rm -rf "$sandbox"
  echo "$code"
}

# expect <description> <expected-exit> <actual-exit>
expect() {
  local desc="$1" want="$2" got="$3"
  if [ "$got" = "$want" ]; then
    PASS=$((PASS + 1))
    printf '  ok   %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    printf '  FAIL %s (expected exit %s, got %s)\n' "$desc" "$want" "$got"
  fi
}

BLOCK=2
ALLOW=0

echo "block-prod-destructive-sql.sh"
expect "DROP TABLE on production target blocks" "$BLOCK" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":"mysql production -e \"DROP TABLE users\""}}')"
expect "TRUNCATE on prod_ target blocks" "$BLOCK" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":"psql -c \"TRUNCATE prod_orders\""}}')"
expect "DELETE FROM on live- target blocks" "$BLOCK" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":"mysql live-db -e \"DELETE FROM orders\""}}')"
expect "UPDATE with alias on production blocks" "$BLOCK" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":"mysql production_db -e \"UPDATE orders AS o SET o.x=1\""}}')"
expect "DROP TABLE on non-prod target allows" "$ALLOW" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":"mysql staging_local -e \"DROP TABLE scratch\""}}')"
expect "plain SELECT allows" "$ALLOW" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":"mysql production -e \"SELECT * FROM users\""}}')"
expect "php artisan migrate allows" "$ALLOW" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":"php artisan migrate"}}')"
expect "empty command allows" "$ALLOW" \
  "$(run_hook block-prod-destructive-sql.sh '{"tool_input":{"command":""}}')"
expect "FALLBACK (no jq/python3): DROP on prod still blocks" "$BLOCK" \
  "$(run_hook_noparsers block-prod-destructive-sql.sh '{"tool_input":{"command":"DROP TABLE production_users"}}')"
expect "FALLBACK (no jq/python3): harmless still allows" "$ALLOW" \
  "$(run_hook_noparsers block-prod-destructive-sql.sh '{"tool_input":{"command":"echo hello"}}')"

echo "block-prod-artisan.sh"
expect "migrate:fresh --env=production blocks" "$BLOCK" \
  "$(run_hook block-prod-artisan.sh '{"tool_input":{"command":"php artisan migrate:fresh --env=production"}}')"
expect "db:wipe --env=prod blocks" "$BLOCK" \
  "$(run_hook block-prod-artisan.sh '{"tool_input":{"command":"php artisan db:wipe --env=prod"}}')"
expect "artisan against .env.production blocks" "$BLOCK" \
  "$(run_hook block-prod-artisan.sh '{"tool_input":{"command":"php artisan migrate --env-file=.env.production"}}')"
expect "migrate:fresh on local soft-warns (allows)" "$ALLOW" \
  "$(run_hook block-prod-artisan.sh '{"tool_input":{"command":"php artisan migrate:fresh"}}')"
expect "plain migrate allows" "$ALLOW" \
  "$(run_hook block-prod-artisan.sh '{"tool_input":{"command":"php artisan migrate"}}')"
expect "cache:clear without prod context allows" "$ALLOW" \
  "$(run_hook block-prod-artisan.sh '{"tool_input":{"command":"php artisan cache:clear"}}')"
expect "FALLBACK (no jq/python3): migrate:fresh --env=production blocks" "$BLOCK" \
  "$(run_hook_noparsers block-prod-artisan.sh '{"tool_input":{"command":"php artisan migrate:fresh --env=production"}}')"

echo "protect-env-files.sh"
expect "write to .env blocks" "$BLOCK" \
  "$(run_hook protect-env-files.sh '{"tool_input":{"file_path":"/app/.env"}}')"
expect "write to .env.production blocks" "$BLOCK" \
  "$(run_hook protect-env-files.sh '{"tool_input":{"path":"/app/.env.production"}}')"
expect "write under secrets/ blocks" "$BLOCK" \
  "$(run_hook protect-env-files.sh '{"tool_input":{"file_path":"/app/secrets/key.pem"}}')"
expect "write to id_rsa blocks" "$BLOCK" \
  "$(run_hook protect-env-files.sh '{"tool_input":{"file_path":"/home/u/.ssh/id_rsa"}}')"
expect "write to .env.example allows" "$ALLOW" \
  "$(run_hook protect-env-files.sh '{"tool_input":{"file_path":"/app/.env.example"}}')"
expect "write to app/Models/User.php allows" "$ALLOW" \
  "$(run_hook protect-env-files.sh '{"tool_input":{"file_path":"/app/app/Models/User.php"}}')"
expect "FALLBACK (no jq/python3): .env.production still blocks" "$BLOCK" \
  "$(run_hook_noparsers protect-env-files.sh '{"tool_input":{"file_path":"/app/.env.production"}}')"

echo "codex-protect-env-files.sh (Codex apply_patch-aware)"
expect "apply_patch adding .env.production blocks" "$BLOCK" \
  "$(run_hook codex-protect-env-files.sh '{"tool_input":{"command":"*** Begin Patch\n*** Add File: .env.production\n+SECRET=x\n*** End Patch"}}')"
expect "apply_patch updating nested .env blocks" "$BLOCK" \
  "$(run_hook codex-protect-env-files.sh '{"tool_input":{"command":"*** Begin Patch\n*** Update File: app/.env\n+APP_KEY=y\n*** End Patch"}}')"
expect "apply_patch touching secrets/ blocks" "$BLOCK" \
  "$(run_hook codex-protect-env-files.sh '{"tool_input":{"command":"*** Begin Patch\n*** Add File: config/secrets/key.pem\n+x\n*** End Patch"}}')"
expect "Edit/Write path to .env.local blocks" "$BLOCK" \
  "$(run_hook codex-protect-env-files.sh '{"tool_input":{"file_path":"/app/.env.local"}}')"
expect "apply_patch editing README that MENTIONS .env in content allows" "$ALLOW" \
  "$(run_hook codex-protect-env-files.sh '{"tool_input":{"command":"*** Begin Patch\n*** Update File: README.md\n+Copy .env.example to .env.production and fill it in.\n*** End Patch"}}')"
expect "apply_patch adding .env.example allows" "$ALLOW" \
  "$(run_hook codex-protect-env-files.sh '{"tool_input":{"command":"*** Begin Patch\n*** Add File: .env.example\n+APP_NAME=Laravel\n*** End Patch"}}')"
expect "apply_patch adding app/Models/User.php allows" "$ALLOW" \
  "$(run_hook codex-protect-env-files.sh '{"tool_input":{"command":"*** Begin Patch\n*** Add File: app/Models/User.php\n+<?php\n*** End Patch"}}')"
expect "FALLBACK (no jq/python3): apply_patch .env.production blocks" "$BLOCK" \
  "$(run_hook_noparsers codex-protect-env-files.sh '{"tool_input":{"command":"*** Begin Patch\n*** Add File: .env.production\n+SECRET=x\n*** End Patch"}}')"

echo "enforce-reviewer-readonly.sh (reviewer Bash write-vector guard)"
expect "tech-lead sed -i blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"sed -i s/foo/bar/ app/Models/User.php"}}')"
expect "plugin-prefixed security-engineer git reset --hard blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"laravel-team:security-engineer","tool_input":{"command":"git reset --hard HEAD~1"}}')"
expect "performance-engineer redirect to file blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"performance-engineer","tool_input":{"command":"wrk -t4 -c50 -d30s http://localhost > results.txt"}}')"
expect "performance-engineer plain wrk allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"performance-engineer","tool_input":{"command":"wrk -t4 -c50 -d30s http://localhost:8000/api/orders"}}')"
expect "tech-lead pint --test allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"./vendor/bin/pint --test"}}')"
expect "tech-lead pint without --test blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"./vendor/bin/pint app/"}}')"
# shellcheck disable=SC2016 # literal \$user in the JSON fixture, not an expansion
expect "tech-lead php arrow syntax no false positive" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"php -r \"echo \\$user->name;\""}}')"
expect "tech-lead stderr redirect to /dev/null allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"./vendor/bin/phpstan analyse 2>/dev/null"}}')"
expect "tech-lead 2>&1 dup allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"php artisan route:list 2>&1"}}')"
expect "security-engineer composer audit allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"security-engineer","tool_input":{"command":"composer audit"}}')"
expect "security-engineer composer require blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"security-engineer","tool_input":{"command":"composer require spatie/laravel-permission"}}')"
expect "security-engineer rm -rf blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"security-engineer","tool_input":{"command":"rm -rf storage/logs"}}')"
expect "tech-lead git diff allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"git diff origin/main...HEAD"}}')"
expect "tech-lead artisan migrate:status allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"php artisan migrate:status"}}')"
expect "tech-lead artisan migrate blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"php artisan migrate"}}')"
expect "backend-developer sed -i allows (not a reviewer)" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"backend-developer","tool_input":{"command":"sed -i s/a/b/ app/Models/User.php"}}')"
expect "main thread (no agent_type) sed -i allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"tool_input":{"command":"sed -i s/a/b/ file.php"}}')"
expect "FALLBACK (no jq/python3): tech-lead sed -i blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"sed -i s/a/b/ app/file.php"}}')"
expect "FALLBACK (no jq/python3): builder payload allows" "$ALLOW" \
  "$(run_hook_noparsers enforce-reviewer-readonly.sh '{"agent_type":"backend-developer","tool_input":{"command":"sed -i s/a/b/ app/file.php"}}')"

echo "enforce-sail.sh (host-PHP redirect on Sail projects)"
# Fixture projects: one on Sail (binary + compose file), one with only the
# sail dependency (the Herd/Valet shape — skeleton ships laravel/sail), one bare.
SAILPROJ="$(mktemp -d)"
mkdir -p "$SAILPROJ/vendor/bin"
printf '#!/bin/sh\n' > "$SAILPROJ/vendor/bin/sail"
chmod +x "$SAILPROJ/vendor/bin/sail"
touch "$SAILPROJ/docker-compose.yml"
SAILDEP="$(mktemp -d)"
mkdir -p "$SAILDEP/vendor/bin"
printf '#!/bin/sh\n' > "$SAILDEP/vendor/bin/sail"
chmod +x "$SAILDEP/vendor/bin/sail"
BAREPROJ="$(mktemp -d)"

# sail_json <cwd> <command> -> hook stdin payload
sail_json() { printf '{"cwd":"%s","tool_input":{"command":"%s"}}' "$1" "$2"; }

expect "php artisan on sail project blocks" "$BLOCK" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "php artisan test")")"
expect "php8.3 artisan on sail project blocks" "$BLOCK" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "php8.3 artisan migrate")")"
expect "composer require on sail project blocks" "$BLOCK" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "composer require spatie/laravel-permission")")"
expect "./vendor/bin/pint on sail project blocks" "$BLOCK" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "./vendor/bin/pint --dirty")")"
expect "vendor/bin/phpstan on sail project blocks" "$BLOCK" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "vendor/bin/phpstan analyse")")"
expect "chained bare artisan blocks" "$BLOCK" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "git pull && php artisan migrate")")"
expect "./vendor/bin/sail artisan allows" "$ALLOW" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "./vendor/bin/sail artisan test --compact")")"
expect "bare sail alias allows" "$ALLOW" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "sail pest --filter=Checkout")")"
expect "docker compose exec allows" "$ALLOW" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "docker compose exec app php artisan about")")"
expect "non-php command on sail project allows" "$ALLOW" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "git status")")"
expect "php artisan on bare project allows" "$ALLOW" \
  "$(run_hook enforce-sail.sh "$(sail_json "$BAREPROJ" "php artisan test")")"
expect "sail dependency without compose file allows (Herd shape)" "$ALLOW" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILDEP" "php artisan test")")"
expect "LARAVEL_AGENTS_SAIL=0 opt-out allows" "$ALLOW" \
  "$(LARAVEL_AGENTS_SAIL=0 run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "php artisan test")")"
expect "empty command allows" "$ALLOW" \
  "$(run_hook enforce-sail.sh "$(sail_json "$SAILPROJ" "")")"
expect "FALLBACK (no jq/python3): php artisan on sail project blocks" "$BLOCK" \
  "$(CLAUDE_PROJECT_DIR="$SAILPROJ" run_hook_noparsers enforce-sail.sh '{"tool_input":{"command":"php artisan test"}}')"
expect "FALLBACK (no jq/python3): sail-prefixed still allows" "$ALLOW" \
  "$(CLAUDE_PROJECT_DIR="$SAILPROJ" run_hook_noparsers enforce-sail.sh '{"tool_input":{"command":"./vendor/bin/sail artisan test"}}')"

rm -rf "$SAILPROJ" "$SAILDEP" "$BAREPROJ"

echo "emit-agent-events.sh (agents-board observer)"
BOARDPROJ="$(mktemp -d)"
START_JSON='{"session_id":"abc12345-zzz","hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"laravel-team:backend-developer","description":"Build invoices API"}}'
END_JSON='{"session_id":"abc12345-zzz","hook_event_name":"PostToolUse","tool_name":"Agent","tool_input":{"subagent_type":"laravel-team:backend-developer","description":"Build invoices API"},"tool_response":{"status":"completed","totalDurationMs":42000,"totalTokens":1234}}'
FEED="$BOARDPROJ/.claude/agents-board.jsonl"

expect "subagent start exits 0" "$ALLOW" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$START_JSON")"
expect "subagent end exits 0" "$ALLOW" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$END_JSON")"
expect "feed carries both events" "2" "$(wc -l < "$FEED" | tr -d ' ')"
expect "start event recorded with plugin prefix stripped" "1" \
  "$(grep -c '"ev":"start"' "$FEED")$(grep -q '"agent":"backend-developer"' "$FEED" || echo MISSING)"
expect "end event carries duration" "1" "$(grep -c '"ms":42000' "$FEED")"
expect "legacy Task tool name also recorded" "$ALLOW" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh '{"hook_event_name":"PreToolUse","tool_name":"Task","tool_input":{"subagent_type":"qa-engineer","description":"Run suite"}}')"
expect "non-subagent tool ignored (exit 0, no event)" "3" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls"}}' >/dev/null; wc -l < "$FEED" | tr -d ' ')"
DEDUP_JSON='{"session_id":"abc12345-zzz","hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"laravel-team:database-developer","description":"Dedup probe"}}'
expect "dual-registration twin suppressed (plugin + settings both fire)" "4" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$DEDUP_JSON" >/dev/null; CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$DEDUP_JSON" >/dev/null; wc -l < "$FEED" | tr -d ' ')"
CONC_JSON='{"session_id":"abc12345-zzz","hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"laravel-team:security-engineer","description":"Concurrent dedup probe"}}'
expect "CONCURRENT twins suppressed (real hooks fire simultaneously)" "5" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$CONC_JSON" >/dev/null & CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$CONC_JSON" >/dev/null & wait; wc -l < "$FEED" | tr -d ' ')"
NESTED_JSON='{"session_id":"abc12345-zzz","hook_event_name":"PreToolUse","tool_name":"Agent","agent_id":"par-agent-1","agent_type":"laravel-team:delivery-coordinator","tool_input":{"subagent_type":"laravel-team:qa-engineer","description":"Nested spawn probe"}}'
expect "nested spawn records parent (calling agent_type, prefix stripped)" "6" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$NESTED_JSON" >/dev/null; wc -l < "$FEED" | tr -d ' ')$(grep -q '"parent":"delivery-coordinator"' "$FEED" || echo MISSING)"
expect "top-level spawn records parent null" "1" \
  "$(head -n 1 "$FEED" | grep -c '"parent":null')"
STOP_JSON='{"session_id":"abc12345-zzz","hook_event_name":"SubagentStop","agent_id":"sub-agent-1","agent_type":"laravel-team:qa-engineer","duration":12.5,"tool_response":"done"}'
expect "SubagentStop recorded as end with ms from duration" "7" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$STOP_JSON" >/dev/null; wc -l < "$FEED" | tr -d ' ')$(grep -q '"status":"subagent_stop"' "$FEED" && grep -q '"ms":12500' "$FEED" || echo MISSING)"
expect "SubagentStop twin suppressed (dual registration)" "7" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$STOP_JSON" >/dev/null; wc -l < "$FEED" | tr -d ' ')"
# Reality check: real SubagentStop payloads carry NO duration (eval run 4 — ms
# was null on every stop event, all five feeds). ms must then be derived from
# the matching start event so the feed stays timed.
NODUR_START='{"session_id":"abc12345-zzz","hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"laravel-team:technical-writer","description":"Duration derivation probe"}}'
NODUR_STOP='{"session_id":"abc12345-zzz","hook_event_name":"SubagentStop","agent_id":"sub-agent-2","agent_type":"laravel-team:technical-writer","tool_response":"done"}'
expect "SubagentStop without duration derives ms from its start event" "0" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$NODUR_START" >/dev/null
     CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$NODUR_STOP" >/dev/null
     grep 'technical-writer' "$FEED" | grep -c '"ms":null,"tokens":null,"status":"subagent_stop"')"
expect "derived-ms twin still suppressed (ms normalised in the dedupe key)" "9" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh "$NODUR_STOP" >/dev/null; wc -l < "$FEED" | tr -d ' ')"
expect "unpaired SubagentStop leaves ms null rather than guessing" "1" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook emit-agent-events.sh '{"session_id":"abc12345-zzz","hook_event_name":"SubagentStop","agent_type":"laravel-team:product-owner","tool_response":"done"}' >/dev/null
     grep 'product-owner' "$FEED" | grep -c '"ms":null')"

# Exact-value proof, not just "non-null": seed a start event 42s in the past in
# a clean feed, fire the stop, read back the derived duration. Tolerates a 1s
# clock tick between seeding and the hook's own `now`.
ELAPSED_PROJ="$(mktemp -d)"
mkdir -p "$ELAPSED_PROJ/.claude"
printf '{"ts":%s,"sid":"deadbeef","ev":"start","agent":"backend-developer","task":"Elapsed probe","ms":null,"tokens":null,"status":null,"parent":null}\n' \
  "$(( $(date +%s) - 42 ))" > "$ELAPSED_PROJ/.claude/agents-board.jsonl"
DERIVED_MS="$(CLAUDE_PROJECT_DIR="$ELAPSED_PROJ" run_hook emit-agent-events.sh \
  '{"session_id":"deadbeef-xx","hook_event_name":"SubagentStop","agent_type":"laravel-team:backend-developer","tool_response":"done"}' >/dev/null
  tail -n 1 "$ELAPSED_PROJ/.claude/agents-board.jsonl" | sed 's/.*"ms"://; s/,.*//')"
case "$DERIVED_MS" in
  42000 | 43000) DERIVED_VERDICT="elapsed" ;;
  *) DERIVED_VERDICT="$DERIVED_MS" ;;
esac
expect "derived ms carries the real start->stop elapsed time (~42s)" "elapsed" "$DERIVED_VERDICT"
rm -rf "$ELAPSED_PROJ"
expect "viewer copied next to the feed" "yes" \
  "$([ -f "$BOARDPROJ/.claude/board.html" ] && echo yes || echo no)"
expect "FALLBACK (no jq/python3): exits 0, fails open" "$ALLOW" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook_noparsers emit-agent-events.sh "$START_JSON")"

rm -rf "$BOARDPROJ"

echo "static ratchets (eval run 4 regressions must not return)"
# Finding 1: `git worktree add` checks out tracked files only, so a worktree has
# no vendor/ — an isolated agent cannot run pint, phpstan, or the suite it just
# wrote, and under Sail it mounts the wrong tree. See docs/evals/2026-07-28-run-4.md.
expect "no agent body declares isolation: worktree" "0" \
  "$(grep -l '^isolation: worktree$' "$SCRIPT_DIR"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
# Finding 2: stage returns are internal — headless runs print only the final
# assistant message, so the shared block must bind that too, identically in all 9.
expect "all 9 pipeline commands carry the Interface block" "9" \
  "$(grep -l '^> \*\*Interface:\*\*' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block is byte-identical across them" "1" \
  "$(grep -h '^> \*\*Interface:\*\*' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | sort -u | wc -l | tr -d ' ')"
expect "Interface block binds the final answer to VERIFIED + NOT-CHECKED" "9" \
  "$(grep -l 'Your own final answer closes the same way' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# Tranche item 2 lived only in agents/delivery-coordinator.md, and eval run 6's
# `feature` case proved it therefore never fired: /make-feature is driven by the
# main thread, the coordinator is never spawned, and the board arrived as a closing
# summary with no up-front count and no completion condition. Same shape as the
# v1.24.0 finding, same fix — the contract belongs in the shared block, so a
# headless command run is bound by it too.
expect "Interface block requires an up-front stage budget" "9" \
  "$(grep -l 'done when: <the observable' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# Literature-gap tranche (docs/plans/2026-07-29-literature-gap-tranche.md), gate
# cleared by eval run 5. Escalation fired on category only; NOT-CHECKED was
# collected by every stage return and consumed by nothing. Nothing bounded a
# run's total stages (only lane cap and per-stage retry). A checkpoint wrote no
# resume state, so a delivery resumed tomorrow replayed work already paid for.
COORD="$SCRIPT_DIR/agents/delivery-coordinator.md"
expect "low confidence is its own stop trigger" "1" \
  "$(grep -c 'Low confidence is a stop trigger in its own right' "$COORD")"
expect "the board declares a stage budget" "1" \
  "$(grep -c 'State the stage budget on the board' "$COORD")"
expect "checkpoints flush resume state" "1" \
  "$(grep -c 'flush the resume state' "$COORD")"
# All three edit the coordinator ONLY. The 9 pipeline commands share a
# byte-identical Interface block; a tranche edit that leaked into it would
# diverge them and drift the delegation contract per command.
expect "the tranche touched no other agent body" "0" \
  "$(grep -l 'State the stage budget on the board' "$SCRIPT_DIR"/agents/*.md 2>/dev/null \
     | grep -cv 'delivery-coordinator.md' || true)"
# Per-agent reasoning effort (verified as a real subagent frontmatter field
# against code.claude.com/docs/en/sub-agents.md, 2026-08-04). It overrides the
# session effort level, so it is declared ONLY where the pack has an opinion:
# the two highest-failure-cost reviewers get depth, the two artifact-summarising
# roles give it up, and everything else stays absent so the human's own /effort
# still governs. An unrecognised frontmatter key is ignored rather than
# rejected, so a typo'd level would look tuned while changing nothing.
expect "the highest-failure-cost reviewers declare xhigh effort" "2" \
  "$(grep -l '^effort: xhigh$' "$SCRIPT_DIR"/agents/security-engineer.md \
     "$SCRIPT_DIR"/agents/solution-architect.md 2>/dev/null | wc -l | tr -d ' ')"
# FNR==1 resets the frontmatter-fence counter per file: awk keeps one `c` across
# the whole file list, so without the reset `c==1` only ever matches inside the
# FIRST file and every later agent goes unchecked. Caught by mutation-testing
# this very assertion — it passed a deliberately invalid level.
expect "every declared effort level is one Claude Code accepts" "" \
  "$(awk 'FNR==1{c=0} /^---$/{c++; next} c==1 && /^effort:/{print FILENAME": "$2}' \
       "$SCRIPT_DIR"/agents/*.md | grep -vE ': (low|medium|high|xhigh|max)$' || true)"
# Effort errors on Haiku 4.5, so declaring it on a haiku-pinned agent would break
# that agent rather than tune it. scrum-master is the pack's only haiku agent and
# is already at the cheapest tier — there is nothing to gain and a launch failure
# to lose.
expect "no haiku-pinned agent declares effort" "" \
  "$(for f in "$SCRIPT_DIR"/agents/*.md; do \
       awk '/^---$/{c++; next} c==1 && /^model: haiku$/{h=1} c==1 && /^effort:/{e=1} \
            END{if (h && e) print FILENAME}' "$f"; \
     done | tr -d ' ')"
# Finding 3 (2026-07-29 literature audit): regex answer keys are exact-match
# scoring of nondeterministic output. The rubric judge is the second opinion, so
# a case registered without a rubric would be silently unjudged.
EVAL_SH="$SCRIPT_DIR/tests/eval/run-evals.sh"
MISSING_RUBRIC=""
read -r -a EVAL_CASE_LIST <<<"$(sed -n 's/^ALL_CASES=(\(.*\))$/\1/p' "$EVAL_SH")"
# Opt-in cases count too: excluded from the default sweep is not excluded from
# needing a rubric, and an unjudged case is exactly what this ratchet exists for.
read -r -a EVAL_OPT_IN_LIST <<<"$(sed -n 's/^OPT_IN_CASES=(\(.*\))$/\1/p' "$EVAL_SH")"
EVAL_CASE_LIST+=("${EVAL_OPT_IN_LIST[@]}")
for c in "${EVAL_CASE_LIST[@]}"; do
  sed -n '/^case_rubric()/,/^}/p' "$EVAL_SH" | grep -qE "^ *$c\)" || MISSING_RUBRIC="$MISSING_RUBRIC $c"
done
expect "every eval case has a judge rubric" "" "$MISSING_RUBRIC"
# Assignments only — `regex_verdict="$3"` (reading the verdict) must not trip it.
expect "the rubric judge never alters the case verdict" "0" \
  "$(sed -n '/^judge_case()/,/^}/p' "$EVAL_SH" \
     | grep -cE '(^|[^_[:alnum:]])(CHECK_PASS|CHECK_FAIL|verdict)=')"

echo "console (static ratchets)"

# console_hits <token> <file-or-dir>... -> count of matching NON-COMMENT lines.
#
# These ratchets used to match raw bytes, which punished the code for explaining
# itself: a comment reading "never offer bypassPermissions" reddened the build,
# and the cheapest way to green it was to delete the explanation. Comment-ONLY
# lines are dropped (`//`, `*`, `/*`, `#`). A trailing comment after real code
# still counts: a security ratchet must fail closed, so over-strict beats
# under-strict. The `path:line:` prefix is removed by position rather than by
# regex, so a URL's `//` inside the matched text cannot hide a real hit.
console_hits() {
  local token="$1"
  shift
  { grep -rn "$token" "$@" 2>/dev/null || true; } \
    | awk '{ line = $0
             sub(/^[^:]*:[0-9]+:/, "", line)
             sub(/^[[:space:]]+/, "", line)
             if (line !~ /^(\/\/|\*|\/\*|#)/) print }' \
    | wc -l | tr -d ' '
}

# bypassPermissions is inherited by subagents and cannot be overridden per
# subagent — offering it in the UI would grant 17 agents unattended access.
# Checked against dist/ (the built, installed bundle) and console-ui/src (the
# source, repo-side only) so the assertion still has evidence post-install.
expect "console never offers bypassPermissions" "0" \
  "$(console_hits 'bypassPermissions' "$SCRIPT_DIR"/scripts/console/dist "$SCRIPT_DIR"/console-ui/src)"
# dontAsk denies AskUserQuestion, which is how checkpoint prompts arrive.
expect "console never selects dontAsk" "0" \
  "$(console_hits 'dontAsk' "$SCRIPT_DIR"/scripts/console/dist "$SCRIPT_DIR"/console-ui/src)"
expect "console server binds loopback only" "1" \
  "$(grep -q 'make_server("127\.0\.0\.1"' "$SCRIPT_DIR"/scripts/console/serve.py && echo 1 || echo 0)"
expect "console never binds a public interface" "0" \
  "$(console_hits '0\.0\.0\.0' "$SCRIPT_DIR"/scripts/console/serve.py "$SCRIPT_DIR"/scripts/console/server.py)"
expect "console API is token-guarded" "1" \
  "$(grep -q 'X-Guild-Token' "$SCRIPT_DIR"/scripts/console/server.py && echo 1 || echo 0)"
expect "console rejects non-local Origin" "1" \
  "$(grep -q 'LOCAL_ORIGIN' "$SCRIPT_DIR"/scripts/console/server.py && echo 1 || echo 0)"
# `==` on the token exits at the first mismatching byte, which leaks how much of
# it a caller guessed. Reverting to `==` breaks no behavioural test -- both forms
# reject a wrong token -- so this is the only thing that would notice.
expect "console compares the token in constant time" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR"/scripts/console/server.py \
     | grep -cE 'secrets\.compare_digest\(')"
# SandboxSettings.autoAllowBashIfSandboxed defaults to True, which auto-decides
# sandboxed Bash calls INSIDE the CLI: can_use_tool never fires, no `prompt`
# event is emitted, and the spec's "every non-preapproved call reaches the
# browser" stops being true. Comments are stripped first so the explanation
# above cannot satisfy the ratchet on its own.
expect "console disables the SDK's sandboxed-bash auto-approval" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR"/scripts/console/serve.py \
     | grep -cE 'sandbox=\{"autoAllowBashIfSandboxed": False\}')"
# The other half: read-only Bash (READ_ONLY_AUTO_ALLOW_REASON) is auto-allowed
# before can_use_tool runs and NO setting disables it. A PreToolUse hook is the
# only layer that sees every call, so dropping this registration silently
# reopens the hole. Comments stripped first, as above.
expect "console registers the PreToolUse gate" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR"/scripts/console/serve.py \
     | grep -cE 'hooks=\{"PreToolUse": \[HookMatcher\(')"
expect "console still forces Bash through the browser" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR"/scripts/console/engine.py \
     | grep -cE '^ASK_ALWAYS_TOOLS = \("Bash",\)')"
# The harness copies the fixture into every eval workdir, so anything left in
# tests/fixture-app/.claude leaks into EVERY case's feed. Run 5 was analysed with
# two qa-engineer stages that never happened, in all five cases, from a local
# console smoke test that had run inside the fixture. That directory is gitignored
# so it cannot be committed — which is exactly why there is no assertion about its
# contents here: on a fresh clone it does not exist at all. The truncate below is
# the load-bearing guard, because it holds whatever the working copy contains.
expect "the eval harness starts each feed empty" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE ': >".*/\.claude/agents-board\.jsonl"')"
# Cost was unmeasured: the harness timed runs and scored them and never priced
# them. stream-json carries per-turn usage with the input/output/cache split,
# which is the only way to price a run rather than guess at it.
#
# The load-bearing risk is $LOG. Every checks_* function greps it for answer-key
# patterns, so if stream-json landed there directly the answer key would start
# matching tool inputs and thinking text, and run 6 would stop being comparable
# to run 5. The transcript goes to its own file; $LOG is rebuilt from the result
# field, which is exactly what plain `claude -p` prints.
expect "the eval harness requests stream-json" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE '\-\-output-format stream-json')"
# The transcript's redirect target must be the dedicated stream file, never $LOG.
# shellcheck disable=SC2016 # literal \$vars in the grep pattern, not expansions
expect "the transcript goes to its own file, not the log" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'run_with_timeout "\$EVAL_TIMEOUT" "\$\{cmd\[@\]\}"\) >"\$stream"')"
# shellcheck disable=SC2016 # literal \$vars in the grep pattern, not expansions
expect "the stream file is named .stream.jsonl" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'local stream=.*\$name\.stream\.jsonl')"
# $LOG must be produced by --text-only (the result field, i.e. what plain -p
# prints) and by nothing else, or the answer key changes meaning.
# shellcheck disable=SC2016 # literal \$vars in the grep pattern, not expansions
expect "the log is rebuilt from the transcript's result field" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE '\-\-text-only >"\$LOG"')"
# shellcheck disable=SC2016 # literal \$vars in the grep pattern, not expansions
expect "the eval harness writes a per-case cost summary" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE '>"\$results/\$name\.cost\.json"')"
# Megabytes per case, and tests/eval/results/ is committed. The derived summary
# is the artifact; the raw stream is scaffolding.
# shellcheck disable=SC2016 # literal \$vars in the grep pattern, not expansions
expect "the eval harness discards the raw transcript" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE '^ *rm -f "\$stream"')"
# Cost had no ceiling at all, so a cost regression was invisible while a latency
# one failed loudly. Token ceilings ride alongside the duration ones and start
# null -- every token figure from runs 1-5 is contaminated (run-5 finding 1), so
# there is nothing honest to seed with until run 6.
expect "every eval case has a token-ceiling key" "" \
  "$(python3 - "$SCRIPT_DIR/tests/eval/baseline.json" "$SCRIPT_DIR/tests/eval/run-evals.sh" <<'PY'
import json, re, sys
base = json.load(open(sys.argv[1]))
cases = re.search(r"^ALL_CASES=\((.*)\)$", open(sys.argv[2]).read(), re.M).group(1).split()
print(" ".join(c for c in cases if "max_tokens" not in base["cases"].get(c, {})))
PY
)"
expect "the harness compares tokens against the ceiling" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" | grep -cE 'max_tokens')"
# Dollars ratchet too, because tokens alone cannot see a model-mix regression: a
# sonnet -> opus re-tier keeps token counts flat and triples the bill. Run 6 also
# measured token totals at >99% cache reads, so tokens track context volume far
# more than spend -- dollars are the ceiling that speaks for cost.
expect "every eval case has a cost-ceiling key" "" \
  "$(python3 - "$SCRIPT_DIR/tests/eval/baseline.json" "$SCRIPT_DIR/tests/eval/run-evals.sh" <<'PY'
import json, re, sys
base = json.load(open(sys.argv[1]))
cases = re.search(r"^ALL_CASES=\((.*)\)$", open(sys.argv[2]).read(), re.M).group(1).split()
print(" ".join(c for c in cases if "max_usd" not in base["cases"].get(c, {})))
PY
)"
expect "the harness compares billed dollars against the ceiling" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" | grep -cE 'max_usd')"
# Seeded, not null: run 6 was accepted (5/5, 19/19), so leaving a ceiling
# unseeded now would waste the only clean measurement the suite has.
# `git diff` omits untracked files, so a case whose job is CREATING a class handed
# the rubric judge an artifact with that class's body missing (run-6 finding 2).
# intent-to-add fixes the artifact; it must stay AFTER the checks and after
# status.txt so it changes no verdict and no other evidence.
expect "the diff artifact records intent-to-add so new files appear" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" | grep -cE 'add -N \.')"
# Order matters and is asserted directly by line number: status.txt must be
# written BEFORE the intent-to-add (so it still reports new files as `??`), and
# the diff AFTER it (so the diff includes them).
expect "status is captured, then intent-to-add, then the diff" "ok" \
  "$(awk '
      /status --porcelain >"\$results\/\$name\.status\.txt"/ { st = NR }
      /add -N \./                                              { add = NR }
      /^ *git -C "\$WORK" diff >"\$results/                    { df = NR }
      END { print (st && add && df && st < add && add < df) ? "ok" : "BAD st=" st " add=" add " diff=" df }
    ' "$SCRIPT_DIR/tests/eval/run-evals.sh")"
# <case>.cost.json counts tool calls by name only. Run 6 could not explain
# n-plus-one's 25 Bash calls without the commands themselves, so the raw
# transcript has to be preservable on demand.
# shellcheck disable=SC2016 # literal $KEEP_TRANSCRIPT in the grep pattern
expect "the raw transcript can be preserved for diagnosis" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" | grep -cE '\$KEEP_TRANSCRIPT" = "1"')"
expect "KEEP_TRANSCRIPT defaults to off" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'KEEP_TRANSCRIPT="\$\{KEEP_TRANSCRIPT:-0\}"')"
expect "no default-sweep ceiling is left unseeded after run 6" "" \
  "$(python3 - "$SCRIPT_DIR/tests/eval/baseline.json" "$SCRIPT_DIR/tests/eval/run-evals.sh" <<'PY'
import json, re, sys
base = json.load(open(sys.argv[1]))["cases"]
src = open(sys.argv[2]).read()
sweep = re.search(r"^ALL_CASES=\((.*)\)$", src, re.M).group(1).split()
print(" ".join(
    f"{name}.{key}" for name in sweep
    for key in ("max_seconds", "max_tokens", "max_usd")
    if base.get(name, {}).get(key) is None
))
PY
)"
# Opt-in cases still need their baseline entry present, so a first run has
# somewhere to report against and somewhere to seed.
expect "every opt-in case has a baseline entry" "" \
  "$(python3 - "$SCRIPT_DIR/tests/eval/baseline.json" "$SCRIPT_DIR/tests/eval/run-evals.sh" <<'PY'
import json, re, sys
base = json.load(open(sys.argv[1]))["cases"]
src = open(sys.argv[2]).read()
m = re.search(r"^OPT_IN_CASES=\((.*)\)$", src, re.M)
opt = m.group(1).split() if m else []
print(" ".join(c for c in opt if c not in base))
PY
)"
# The opt-in case exists to prove delegation happened. No other case asserts it,
# and `policy`/`action` each ran both ways across runs 5 and 6 without the answer
# key noticing which — so if this assertion goes, the case loses its whole point.
# The 2026-07-29 literature audit named exact-match grep scoring as an antipattern
# and cited `check_log 'update'` by name. It then failed both ways for real: it
# passes on any stray "update", and on 2026-08-05 it failed a run that closed the
# hole correctly via a Form Request and never used the word — the rubric judge
# scored that run 5/5 and disagreed with the key. The assertion is now
# artifact-level, and must not regress to wording.
expect "the policy case asserts the guard, not a word in the prose" "1" \
  "$(sed -n '/^checks_policy()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_update_guarded')"
expect "the policy case no longer greps the log for 'update'" "0" \
  "$(sed -n '/^checks_policy()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "check_log 'update'" || true)"
# A guard that authorizes everything is not a guard: the checker must reject a Form
# Request whose authorize() just returns true.
expect "the guard checker inspects the authorize body, not just its presence" "1" \
  "$(sed -n '/^check_update_guarded()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'GUARD\.search\(auth\.group')"
expect "the opt-in case asserts that work was delegated" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_delegated')"
expect "the opt-in case stays out of the default sweep" "0" \
  "$(sed -n 's/^ALL_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature' || true)"
# Checks must read the human-readable log, never the transcript.
expect "no checks function reads the raw transcript" "0" \
  "$(sed -n '/^checks_/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "console bundle is committed" "1" \
  "$([ -f "$SCRIPT_DIR/scripts/console/dist/index.html" ] && echo 1 || echo 0)"
# The committed bundle needs ONE blessed toolchain. A hardcoded node-version in
# CI drifting from .nvmrc is invisible until someone's clean checkout fails the
# dist/ staleness gate for reasons that have nothing to do with their change.
expect "one blessed node version, declared in .nvmrc" "1" \
  "$([ -s "$SCRIPT_DIR/.nvmrc" ] && echo 1 || echo 0)"
expect "CI reads the node version from .nvmrc" "1" \
  "$(grep -c 'node-version-file: .nvmrc' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI pins no node version by hand" "0" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/.github/workflows/ci.yml" | grep -cE 'node-version:' || true)"
# The board and its observer are deliberately untouched by the console work.
expect "emit-agent-events.sh still wired three ways" "3" \
  "$(grep -c 'emit-agent-events.sh' "$SCRIPT_DIR/hooks/hooks.json" | tr -d ' ')"

echo
echo "----------------------------------------"
printf 'total: %d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && echo "ALL GREEN" || echo "FAILURES PRESENT"
exit "$FAIL"
