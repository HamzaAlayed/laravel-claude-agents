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

echo
echo "----------------------------------------"
printf 'total: %d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && echo "ALL GREEN" || echo "FAILURES PRESENT"
exit "$FAIL"
