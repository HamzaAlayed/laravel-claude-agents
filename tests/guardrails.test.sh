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
expect "viewer copied next to the feed" "yes" \
  "$([ -f "$BOARDPROJ/.claude/board.html" ] && echo yes || echo no)"
expect "FALLBACK (no jq/python3): exits 0, fails open" "$ALLOW" \
  "$(CLAUDE_PROJECT_DIR="$BOARDPROJ" run_hook_noparsers emit-agent-events.sh "$START_JSON")"

rm -rf "$BOARDPROJ"

echo
echo "----------------------------------------"
printf 'total: %d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && echo "ALL GREEN" || echo "FAILURES PRESENT"
exit "$FAIL"
