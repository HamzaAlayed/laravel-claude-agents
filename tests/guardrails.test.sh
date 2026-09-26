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

# hook_command_count <file> <event> <matcher> <script-suffix>
hook_command_count() {
  python3 -c 'import json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); print(sum(1 for entry in data.get("hooks", {}).get(sys.argv[2], []) if entry.get("matcher") == sys.argv[3] for hook in entry.get("hooks", []) if str(hook.get("command", "")).endswith(sys.argv[4])))' "$1" "$2" "$3" "$4"
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

echo "enforce-close-file.sh"
expect "close.md stub Write allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"path":"docs/delivery/tag/close.md","contents":"VERIFIED: x\nNOT-CHECKED: y\nSTATUS: running\nBOARD: z\n"}}')"
expect "close.md journal Write blocks" "$BLOCK" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"path":"docs/delivery/tag/close.md","contents":"# Close file\n\nVERIFIED (coordinator):\nx\nSTATUS: planning complete\n"}}')"
expect "non-close.md Write allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"path":"app/Models/Tag.php","contents":"class Tag {}\n"}}')"
expect "close.md stub Edit allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"file_path":"docs/delivery/tag/close.md","new_string":"VERIFIED: x\nNOT-CHECKED: none\nSTATUS: done\nBOARD: done\n"}}')"
expect "close.md journal Edit blocks" "$BLOCK" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"file_path":"docs/delivery/tag/close.md","new_string":"more journal\n"}}')"
expect "FALLBACK (no jq/python3): close.md path still blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-close-file.sh '{"tool_input":{"path":"docs/delivery/tag/close.md","contents":"# Close file\n\nVERIFIED (coordinator):\nx\nSTATUS: planning complete\n"}}')"
expect "close.md Bash cat-redirect blocks" "$BLOCK" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"command":"cat > docs/delivery/tag/close.md <<EOF\njournal\nEOF"}}')"
expect "close.md Bash read allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"command":"cat docs/delivery/tag/close.md"}}')"
expect "php artisan test allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"command":"php artisan test --compact"}}')"
expect "FALLBACK (no jq/python3): close.md Bash write still blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-close-file.sh '{"tool_input":{"command":"cat > docs/delivery/tag/close.md <<EOF\nx\nEOF"}}')"

echo "enforce-stage-return.sh"
expect "stage return stub Write allows" "$ALLOW" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"path":"docs/delivery/tag/stages/database-developer.md","contents":"STATUS: done\nDID: x\nVERIFIED: y\nNOT-CHECKED: z\nFLAGS: none\nNEXT: none\n"}}')"
expect "stage return journal Write blocks" "$BLOCK" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"path":"docs/delivery/tag/stages/database-developer.md","contents":"# Stage return\n\nI did some work\n"}}')"
expect "non-stage-return Write allows" "$ALLOW" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"path":"app/Models/Tag.php","contents":"class Tag {}\n"}}')"
expect "stage return stub Edit allows" "$ALLOW" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"file_path":"docs/delivery/tag/stages/database-developer.md","new_string":"STATUS: done\nDID: x\nVERIFIED: y\nNOT-CHECKED: none\nFLAGS: none\nNEXT: none\n"}}')"
expect "stage return journal Edit blocks" "$BLOCK" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"file_path":"docs/delivery/tag/stages/database-developer.md","new_string":"more journal\n"}}')"
expect "FALLBACK (no jq/python3): stage return path still blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-stage-return.sh '{"tool_input":{"path":"docs/delivery/tag/stages/database-developer.md","contents":"# Stage return\n\nI did some work\n"}}')"
expect "stage return Bash cat-redirect blocks" "$BLOCK" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"command":"cat > docs/delivery/tag/stages/database-developer.md <<EOF\njournal\nEOF"}}')"
expect "stage return Bash read allows" "$ALLOW" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"command":"cat docs/delivery/tag/stages/database-developer.md"}}')"
expect "stage return php artisan test allows" "$ALLOW" \
  "$(run_hook enforce-stage-return.sh '{"tool_input":{"command":"php artisan test --compact"}}')"
expect "FALLBACK (no jq/python3): stage return Bash write still blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-stage-return.sh '{"tool_input":{"command":"cat > docs/delivery/tag/stages/database-developer.md <<EOF\nx\nEOF"}}')"

echo "enforce-sprint-file.sh"
expect "sprint.md stub Write allows" "$ALLOW" \
  "$(run_hook enforce-sprint-file.sh '{"tool_input":{"path":"docs/sprints/3.1/sprint.md","contents":"GOAL: x\nWIP: 0/2\nBOARD: none\nSTATUS: running\n"}}')"
expect "sprint.md journal Write blocks" "$BLOCK" \
  "$(run_hook enforce-sprint-file.sh '{"tool_input":{"path":"docs/sprints/3.1/sprint.md","contents":"# Sprint\n\nI started the sprint\n"}}')"
expect "non-sprint.md Write allows" "$ALLOW" \
  "$(run_hook enforce-sprint-file.sh '{"tool_input":{"path":"docs/sprints/3.1/retro.md","contents":"# Retro\n"}}')"
expect "sprint.md Bash cat-redirect blocks" "$BLOCK" \
  "$(run_hook enforce-sprint-file.sh '{"tool_input":{"command":"cat > docs/sprints/3.1/sprint.md <<EOF\njournal\nEOF"}}')"
expect "sprint.md Bash read allows" "$ALLOW" \
  "$(run_hook enforce-sprint-file.sh '{"tool_input":{"command":"cat docs/sprints/3.1/sprint.md"}}')"

echo "enforce-lessons-file.sh"
expect "lessons.md none Write allows" "$ALLOW" \
  "$(run_hook enforce-lessons-file.sh '{"tool_input":{"path":"docs/team/lessons.md","contents":"LESSONS: none\n"}}')"
expect "lessons.md approved Write allows" "$ALLOW" \
  "$(run_hook enforce-lessons-file.sh '{"tool_input":{"path":"docs/team/lessons.md","contents":"LESSONS:\nID: abc\nRULE: x\nSCOPE: database-developer\nSTATUS: approved\nPROVENANCE: stage_flag (2 observations)\nAPPROVED-BY: user at 2026-09-22T00:00:00+00:00\n"}}')"
expect "lessons.md candidate Write allows without approval" "$ALLOW" \
  "$(run_hook enforce-lessons-file.sh '{"tool_input":{"path":"docs/team/lessons.md","contents":"LESSONS:\nID: abc\nRULE: x\nSCOPE: database-developer\nSTATUS: candidate\nPROVENANCE: stage_flag (2 observations)\n"}}')"
expect "lessons.md legacy taught status blocks" "$BLOCK" \
  "$(run_hook enforce-lessons-file.sh '{"tool_input":{"path":"docs/team/lessons.md","contents":"LESSONS:\nID: abc\nRULE: x\nSCOPE: database-developer\nSTATUS: taught\nPROVENANCE: stage_flag (2 observations)\n"}}')"
expect "lessons.md journal Write blocks" "$BLOCK" \
  "$(run_hook enforce-lessons-file.sh '{"tool_input":{"path":"docs/team/lessons.md","contents":"# Lessons\n\nI learned something\n"}}')"
expect "conventions.md Write allows" "$ALLOW" \
  "$(run_hook enforce-lessons-file.sh '{"tool_input":{"path":"docs/team/conventions.md","contents":"# Conventions\n"}}')"
expect "lessons.md Bash cat-redirect blocks" "$BLOCK" \
  "$(run_hook enforce-lessons-file.sh '{"tool_input":{"command":"cat > docs/team/lessons.md <<EOF\njournal\nEOF"}}')"

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
expect "peer-router sed -i blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"peer-router","tool_input":{"command":"sed -i s/a/b/ file.php"}}')"
expect "main thread (no agent_type) sed -i allows" "$ALLOW" \
  "$(run_hook enforce-reviewer-readonly.sh '{"tool_input":{"command":"sed -i s/a/b/ file.php"}}')"
expect "FALLBACK (no jq/python3): tech-lead sed -i blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-reviewer-readonly.sh '{"agent_type":"tech-lead","tool_input":{"command":"sed -i s/a/b/ app/file.php"}}')"
expect "FALLBACK (no jq/python3): builder payload allows" "$ALLOW" \
  "$(run_hook_noparsers enforce-reviewer-readonly.sh '{"agent_type":"backend-developer","tool_input":{"command":"sed -i s/a/b/ app/file.php"}}')"

echo "enforce-agent-paths.sh (registry-backed native write scope)"
run_path_policy() {
  local root="$1" json="$2"
  printf '%s' "$json" | CLAUDE_PROJECT_DIR="$root" "$SCRIPTS/enforce-agent-paths.sh" >/dev/null 2>&1
  echo $?
}
write_policy_state() {
  local root="$1" delivery="$2" delivery_status="$3" stage_status="$4"
  local agent="$5" owned="$6"
  mkdir -p "$root/docs/delivery/$delivery"
  printf '{"status":"%s","stages":[{"id":"a","agent":"%s","status":"%s","owned_paths":%s}]}' \
    "$delivery_status" "$agent" "$stage_status" "$owned" \
    > "$root/docs/delivery/$delivery/kernel.json"
}

POLICY_TMP="$(mktemp -d)"
POLICY_DIRECT="$POLICY_TMP/direct"
mkdir -p "$POLICY_DIRECT"
expect "main-thread native write stays outside subagent policy" "$ALLOW" \
  "$(run_path_policy "$POLICY_DIRECT" '{"tool_input":{"file_path":"app/Models/User.php"}}')"
expect "agent from another plugin is ignored" "$ALLOW" \
  "$(run_path_policy "$POLICY_DIRECT" '{"agent_type":"unrelated-agent","tool_input":{"file_path":"app/Models/User.php"}}')"
expect "direct builder fast path remains writable without an active delivery" "$ALLOW" \
  "$(run_path_policy "$POLICY_DIRECT" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models/User.php"}}')"
expect "direct builder cannot use native write outside the project" "$BLOCK" \
  "$(run_path_policy "$POLICY_DIRECT" '{"agent_type":"backend-developer","tool_input":{"file_path":"../escaped.php"}}')"
expect "direct docs-only fast path may write an approved documentation root" "$ALLOW" \
  "$(run_path_policy "$POLICY_DIRECT" '{"agent_type":"business-analyst","tool_input":{"file_path":"docs/requirements/story.md"}}')"
expect "direct docs-only fast path may write the root README" "$ALLOW" \
  "$(run_path_policy "$POLICY_DIRECT" '{"agent_type":"technical-writer","tool_input":{"file_path":"README.md"}}')"
expect "direct docs-only profile cannot write application code" "$BLOCK" \
  "$(run_path_policy "$POLICY_DIRECT" '{"agent_type":"business-analyst","tool_input":{"file_path":"app/Models/User.php"}}')"
expect "deny profile cannot use native Write even without a delivery" "$BLOCK" \
  "$(run_path_policy "$POLICY_DIRECT" '{"agent_type":"tech-lead","tool_input":{"file_path":"docs/review.md"}}')"

POLICY_QUEUED="$POLICY_TMP/queued"
write_policy_state "$POLICY_QUEUED" tag running queued backend-developer '["app/Models"]'
expect "queued stage must be claimed before native mutation" "$BLOCK" \
  "$(run_path_policy "$POLICY_QUEUED" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models/Tag.php"}}')"

POLICY_RUNNING="$POLICY_TMP/running"
write_policy_state "$POLICY_RUNNING" tag running running backend-developer '["app/Models"]'
expect "claimed stage may write its exact owned path" "$ALLOW" \
  "$(run_path_policy "$POLICY_RUNNING" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models"}}')"
expect "claimed stage may write a nested owned file" "$ALLOW" \
  "$(run_path_policy "$POLICY_RUNNING" '{"agent_type":"laravel-team:backend-developer","tool_input":{"file_path":"app/Models/Tag.php"}}')"
expect "claimed stage cannot write a sibling path" "$BLOCK" \
  "$(run_path_policy "$POLICY_RUNNING" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Http/TagController.php"}}')"
expect "claimed stage cannot write outside the project" "$BLOCK" \
  "$(run_path_policy "$POLICY_RUNNING" '{"agent_type":"backend-developer","tool_input":{"file_path":"../escaped.php"}}')"
expect "claimed stage blocks a native write with no path" "$BLOCK" \
  "$(run_path_policy "$POLICY_RUNNING" '{"agent_type":"backend-developer","tool_input":{}}')"

POLICY_DOCS="$POLICY_TMP/docs"
write_policy_state "$POLICY_DOCS" plan running running technical-writer '["docs/releases"]'
expect "docs-only stage may write inside its claimed documentation path" "$ALLOW" \
  "$(run_path_policy "$POLICY_DOCS" '{"agent_type":"technical-writer","tool_input":{"file_path":"docs/releases/next.md"}}')"
expect "docs-only stage cannot escape its claimed documentation path" "$BLOCK" \
  "$(run_path_policy "$POLICY_DOCS" '{"agent_type":"technical-writer","tool_input":{"file_path":"README.md"}}')"

POLICY_AMBIGUOUS="$POLICY_TMP/ambiguous"
write_policy_state "$POLICY_AMBIGUOUS" one running running backend-developer '["app/Models"]'
write_policy_state "$POLICY_AMBIGUOUS" two running running backend-developer '["app/Http"]'
expect "two running stages for one agent fail closed as ambiguous" "$BLOCK" \
  "$(run_path_policy "$POLICY_AMBIGUOUS" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models/Tag.php"}}')"

POLICY_DONE="$POLICY_TMP/done"
write_policy_state "$POLICY_DONE" tag "done" "done" backend-developer '["app/Models"]'
expect "completed delivery does not disable a later direct fast path" "$ALLOW" \
  "$(run_path_policy "$POLICY_DONE" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Http/TagController.php"}}')"

POLICY_INTERRUPTED="$POLICY_TMP/interrupted"
write_policy_state "$POLICY_INTERRUPTED" tag interrupted interrupted backend-developer '["app/Models"]'
expect "interrupted delivery cannot fall through to the direct write fast path" "$BLOCK" \
  "$(run_path_policy "$POLICY_INTERRUPTED" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models/Tag.php"}}')"

POLICY_BAD="$POLICY_TMP/bad"
mkdir -p "$POLICY_BAD/docs/delivery/tag"
printf '{' > "$POLICY_BAD/docs/delivery/tag/kernel.json"
expect "malformed delivery state fails closed" "$BLOCK" \
  "$(run_path_policy "$POLICY_BAD" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models/Tag.php"}}')"

POLICY_LINK="$POLICY_TMP/link"
POLICY_OUTSIDE="$POLICY_TMP/outside"
mkdir -p "$POLICY_LINK/app/Models" "$POLICY_OUTSIDE"
ln -s "$POLICY_OUTSIDE" "$POLICY_LINK/app/Models/external"
write_policy_state "$POLICY_LINK" tag running running backend-developer '["app/Models"]'
expect "symlink escape beneath an owned path is blocked" "$BLOCK" \
  "$(run_path_policy "$POLICY_LINK" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models/external/Tag.php"}}')"

POLICY_STATE_LINK="$POLICY_TMP/state-link"
mkdir -p "$POLICY_STATE_LINK/docs" "$POLICY_TMP/external-state/tag"
printf '{"status":"running","stages":[]}' > "$POLICY_TMP/external-state/tag/kernel.json"
ln -s "$POLICY_TMP/external-state" "$POLICY_STATE_LINK/docs/delivery"
expect "delivery-state directory symlink outside the project fails closed" "$BLOCK" \
  "$(run_path_policy "$POLICY_STATE_LINK" '{"agent_type":"backend-developer","tool_input":{"file_path":"app/Models/Tag.php"}}')"
rm -rf "$POLICY_TMP"

echo "enforce-kernel-approvals.sh (durable user approval authority)"
run_approval_policy() {
  local root="$1" json="$2"
  printf '%s' "$json" | CLAUDE_PROJECT_DIR="$root" "$SCRIPTS/enforce-kernel-approvals.sh" >/dev/null 2>&1
  echo $?
}

APPROVAL_TMP="$(mktemp -d)"
mkdir -p "$APPROVAL_TMP/docs/delivery/tag"
printf '%s' '{"status":"running","stages":[{"id":"database","agent":"database-developer","status":"queued","approval_categories":["destructive migration"],"approvals":[]}]}' \
  > "$APPROVAL_TMP/docs/delivery/tag/kernel.json"
expect "main thread may record an explicit approval through the kernel CLI" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py approval grant --root . --name tag --stage database --category destructive-migration"}}')"
expect "subagent cannot grant its own stage approval" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py approval grant --root . --name tag --stage database --category destructive-migration"}}')"
expect "main thread may record an explicit criterion waiver through the kernel CLI" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py criterion waive --root . --name tag --stage database --criterion rollback-documented --reason accepted-by-user"}}')"
expect "subagent cannot waive its own success criterion" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py criterion waive --root . --name tag --stage database --criterion rollback-documented --reason self-approved"}}')"
expect "main thread may open a durable checkpoint through the kernel CLI" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py checkpoint open --root . --name tag --stage database --id migration-risk --question proceed --risk data-loss --option-json option --recommended approve"}}')"
expect "subagent cannot open its own checkpoint" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py checkpoint open --root . --name tag --stage database --id migration-risk --question proceed --risk data-loss --option-json option --recommended approve"}}')"
expect "main thread may resolve a durable checkpoint through the kernel CLI" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py checkpoint resolve --root . --name tag --id migration-risk --option approve"}}')"
expect "subagent cannot resolve its own checkpoint" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py checkpoint resolve --root . --name tag --id migration-risk --option approve"}}')"
expect "main thread may request an explicit stage retry through the kernel CLI" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py retry request --root . --name tag --stage database --source stage-return --reason missing-evidence --event-id turn:1"}}')"
expect "subagent cannot request its own stage retry" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py retry request --root . --name tag --stage database --source stage-return --reason self-retry --event-id turn:1"}}')"
expect "main thread may assign an unrouted feedback event" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py feedback assign --root . --name tag --event-id check:security:1 --stage database"}}')"
expect "subagent cannot assign its own feedback route" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py feedback assign --root . --name tag --event-id check:security:1 --stage database"}}')"
expect "main thread may record an interrupted stage through the kernel CLI" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py recovery interrupt --root . --name tag --stage database --source process-exit --reason disconnected --event-id process:1"}}')"
expect "subagent cannot mark its own stage interrupted" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py recovery interrupt --root . --name tag --stage database --source process-exit --reason disconnected --event-id process:1"}}')"
expect "main thread may resolve an interrupted stage through the kernel CLI" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py recovery resolve --root . --name tag --event-id process:1 --action continue"}}')"
expect "subagent cannot resolve its own interrupted stage" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"python3 scripts/guild-kernel/guild.py recovery resolve --root . --name tag --event-id process:1 --action continue"}}')"
APPROVAL_INTERRUPTED="$(mktemp -d)"
mkdir -p "$APPROVAL_INTERRUPTED/docs/delivery/tag"
printf '%s' '{"status":"interrupted","stages":[{"id":"database","agent":"database-developer","status":"interrupted","approval_categories":[],"approvals":[]}]}' \
  > "$APPROVAL_INTERRUPTED/docs/delivery/tag/kernel.json"
expect "interrupted delivery keeps subagent Bash blocked until recovery" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_INTERRUPTED" '{"agent_type":"database-developer","tool_name":"Bash","tool_input":{"command":"php artisan test"}}')"
rm -rf "$APPROVAL_INTERRUPTED"
expect "pending approval blocks subagent Bash before claim" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"laravel-team:database-developer","tool_name":"Bash","tool_input":{"command":"php artisan migrate"}}')"
expect "unrelated Guild agent is not blocked by another lane's approval" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"backend-developer","tool_name":"Bash","tool_input":{"command":"php artisan test"}}')"
expect "native Write cannot replace kernel approval state" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Write","tool_input":{"file_path":"docs/delivery/tag/kernel.json","contents":"{}"}}')"
expect "native Edit cannot replace absolute kernel approval state" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$APPROVAL_TMP/docs/delivery/tag/kernel.json\",\"new_string\":\"{}\"}}")"
expect "Bash redirect cannot replace kernel approval state" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"printf x > docs/delivery/tag/kernel.json"}}')"
expect "read-only cat of kernel state remains available" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Bash","tool_input":{"command":"cat docs/delivery/tag/kernel.json"}}')"
expect "ordinary application write stays outside kernel-state policy" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"tool_name":"Write","tool_input":{"file_path":"app/Models/Tag.php","contents":"<?php"}}')"
printf '%s' '{"status":"running","stages":[{"id":"database","agent":"database-developer","status":"running","approval_categories":["destructive migration"],"approvals":[{"category":"destructive migration","by":"user","at":"2026-09-25T00:00:00+00:00"}]}]}' \
  > "$APPROVAL_TMP/docs/delivery/tag/kernel.json"
expect "approved claimed stage may execute Bash" "$ALLOW" \
  "$(run_approval_policy "$APPROVAL_TMP" '{"agent_type":"database-developer","tool_name":"Bash","tool_input":{"command":"php artisan migrate"}}')"
expect "malformed hook JSON fails closed" "$BLOCK" \
  "$(run_approval_policy "$APPROVAL_TMP" '{')"
rm -rf "$APPROVAL_TMP"

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
expect "one canonical orchestration contract is committed" "1" \
  "$([ -s "$SCRIPT_DIR/config/orchestration-contract.md" ] && echo 1 || echo 0)"
expect "canonical orchestration markers wrap all 10 runtime carriers" "10 10" \
  "$(python3 - "$SCRIPT_DIR" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
paths = list((root / "commands").glob("*.md")) + [root / "agents/delivery-coordinator.md"]
start = sum("<!-- BEGIN GENERATED ORCHESTRATION CONTRACT -->" in p.read_text() for p in paths)
end = sum("<!-- END GENERATED ORCHESTRATION CONTRACT -->" in p.read_text() for p in paths)
print(start, end)
PY
)"
expect "canonical orchestration carriers are generated and current" "0" \
  "$(python3 "$SCRIPT_DIR/scripts/sync-orchestration-contract.py" --check >/dev/null 2>&1; echo $?)"
expect "CI checks the canonical orchestration source" "1" \
  "$(grep -c 'sync-orchestration-contract.py --check' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs canonical orchestration unit tests" "1" \
  "$(grep -c 'unittest discover -s tests/orchestration' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "one versioned adversarial attack matrix is committed" "1" \
  "$(python3 - "$SCRIPT_DIR/config/adversarial-harness.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(1 if payload.get("schemaVersion") == 1 and len(payload.get("cases", [])) == 18 else 0)
PY
)"
expect "CI has a separate adversarial engineering-loop gate" "1" \
  "$(grep -c '^    name: adversarial engineering loop$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs the versioned adversarial attack suite" "1" \
  "$(grep -c 'unittest discover -s tests/adversarial' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the adversarial gate" "1" \
  "$(grep -c '"adversarial engineering loop"' "$SCRIPT_DIR/config/release-harness.json")"
expect "one versioned observability contract is committed" "1" \
  "$(python3 - "$SCRIPT_DIR/config/observability-harness.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
required = {"events.jsonl", "observability.md", "kernel.json"}
print(1 if payload.get("schemaVersion") == 1 and required == set(payload.get("artifacts", [])) else 0)
PY
)"
expect "CI has a separate observability contract gate" "1" \
  "$(grep -c '^    name: observability contract$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs delivery observability contract tests" "1" \
  "$(grep -c 'unittest discover -s tests/observability' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the observability gate" "1" \
  "$(grep -c '"observability contract"' "$SCRIPT_DIR/config/release-harness.json")"
expect "one versioned outcome benchmark contract is committed" "1" \
  "$(python3 - "$SCRIPT_DIR/config/benchmark-harness.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
valid = payload.get("schemaVersion") == 1
valid = valid and payload.get("databaseMode") == "read-only"
valid = valid and payload.get("registeredRunner") == "outcome-benchmark"
valid = valid and payload.get("minimumRuns") >= 7
print(1 if valid else 0)
PY
)"
expect "CI has a separate outcome benchmark gate" "1" \
  "$(grep -c '^    name: outcome benchmark$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs outcome benchmark contract tests" "1" \
  "$(grep -c 'unittest discover -s tests/benchmark' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the outcome benchmark gate" "1" \
  "$(grep -c '"outcome benchmark"' "$SCRIPT_DIR/config/release-harness.json")"
expect "kernel registers the outcome benchmark runner" "1" \
  "$(grep -c '"outcome-benchmark": (' "$SCRIPT_DIR/scripts/guild-kernel/kernel.py")"
expect "benchmark contract excludes all six raw payload classes" "6" \
  "$(python3 - "$SCRIPT_DIR/config/benchmark-harness.json" <<'PY'
import json, sys
print(len(json.load(open(sys.argv[1]))["forbiddenPayloads"]))
PY
)"
expect "Interface requires outcome receipts for performance claims" "9" \
  "$(grep -l '^> \*\*Outcome benchmarks:\*\*' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "one versioned Laravel capture contract is committed" "1" \
  "$(python3 - "$SCRIPT_DIR/config/capture-harness.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
valid = payload.get("schemaVersion") == 1
valid = valid and payload.get("command") == "guild:benchmark-capture"
valid = valid and payload.get("databaseMode") == "read-only"
valid = valid and payload.get("minimumWarmupRuns") >= 2
valid = valid and payload.get("minimumMeasuredRuns") >= 7
print(1 if valid else 0)
PY
)"
expect "CI has a separate Laravel capture gate" "1" \
  "$(grep -c '^    name: laravel benchmark capture$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs Laravel capture adapter tests" "1" \
  "$(grep -c 'pest tests/capture-adapter' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the Laravel capture gate" "1" \
  "$(grep -c '"laravel benchmark capture"' "$SCRIPT_DIR/config/release-harness.json")"
expect "one versioned context packet contract is committed" "1" \
  "$(python3 - "$SCRIPT_DIR/config/context-harness.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
valid = payload.get("schemaVersion") == 1
valid = valid and payload.get("packetSchemaVersion") == 2
valid = valid and payload.get("staleSourcePolicy") == "fail"
valid = valid and payload.get("sourceTrust") == "untrusted-data-not-instructions"
valid = valid and payload.get("defaultMaxTokens") <= payload.get("maximumMaxTokens")
print(1 if valid else 0)
PY
)"
expect "CI has a separate context packet gate" "1" \
  "$(grep -c '^    name: context packet harness$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs context packet contract tests" "1" \
  "$(grep -c 'unittest discover -s tests/context' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the context packet gate" "1" \
  "$(grep -c '"context packet harness"' "$SCRIPT_DIR/config/release-harness.json")"
expect "Interface requires a verified context packet before dispatch" "9" \
  "$(grep -l '^> \*\*Context packets:\*\*' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "guild exposes the context command group" "1" \
  "$(grep -c 'context = sub.add_parser("context")' "$SCRIPT_DIR/scripts/guild-kernel/guild.py")"
expect "one versioned memory retrieval contract is committed" "1" \
  "$(python3 - "$SCRIPT_DIR/config/memory-harness.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
valid = payload.get("schemaVersion") == 1
valid = valid and payload.get("conflictPolicy") == "explicit-supersession"
valid = valid and payload.get("deletionPolicy") == "two-step-tombstone"
valid = valid and payload.get("staleEvidencePolicy") == "exclude"
print(1 if valid else 0)
PY
)"
expect "CI has a separate memory retrieval gate" "1" \
  "$(grep -c '^    name: memory retrieval harness$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs memory retrieval contract tests" "1" \
  "$(grep -c 'unittest discover -s tests/memory' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the memory retrieval gate" "1" \
  "$(grep -c '"memory retrieval harness"' "$SCRIPT_DIR/config/release-harness.json")"
expect "Interface retrieves approved durable memory before dispatch" "9" \
  "$(grep -l '^> \*\*Durable memory:\*\*' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "guild exposes the memory command group" "1" \
  "$(grep -c 'memory = sub.add_parser("memory")' "$SCRIPT_DIR/scripts/guild-kernel/guild.py")"
expect "Interface verifies delivery observability before closure" "9" \
  "$(grep -l 'again before the final answer, call' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "kernel exposes the observability command group" "1" \
  "$(grep -c 'observe = sub.add_parser("observe")' "$SCRIPT_DIR/scripts/guild-kernel/guild.py")"
expect "shared observability excludes raw payloads" "1" \
  "$(grep -c '"rawPayloads": false' "$SCRIPT_DIR/config/agent-harness.json")"
expect "one versioned enforcement map is committed" "19" \
  "$(python3 - "$SCRIPT_DIR/config/enforcement-map.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(len(payload.get("controls", [])) if payload.get("schemaVersion") == 1 else 0)
PY
)"
expect "CI has a separate enforcement-map gate" "1" \
  "$(grep -c '^    name: enforcement map$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs enforcement-map tests" "1" \
  "$(grep -c 'unittest discover -s tests/enforcement' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the enforcement-map gate" "1" \
  "$(grep -c '"enforcement map"' "$SCRIPT_DIR/config/release-harness.json")"
expect "README links the engineering-loop enforcement map" "1" \
  "$(grep -c 'engineering-loop enforcement map' "$SCRIPT_DIR/README.md")"
expect "Interface block binds the final answer to VERIFIED + NOT-CHECKED" "9" \
  "$(grep -l 'Your own final answer closes the same way' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# Tranche item 2 lived only in agents/delivery-coordinator.md, and eval run 6's
# `feature` case proved it therefore never fired: /make-feature is driven by the
# main thread, the coordinator is never spawned, and the board arrived as a closing
# summary with no up-front count and no completion condition. Same shape as the
# v1.24.0 finding, same fix — the contract belongs in the shared block, so a
# headless command run is bound by it too.
# shellcheck disable=SC2016 # literal guild.py backticks in the Interface needle
expect "Interface block calls the guild kernel" "9" \
  "$(grep -l 'Call `python3 scripts/guild-kernel/guild.py`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# Run 7 (docs/evals/2026-08-06-run-7.md) proved harvest never fires for
# command-driven deliveries: agents/delivery-coordinator.md promises it, but
# /make-feature and its 8 siblings never load that file. Same shape as the
# kernel-call finding two lines above, same fix — the contract belongs in
# the shared block, so a headless command run is bound by it too.
expect "Interface block requires harvest once specialists report" "9" \
  "$(grep -l 'this delivery harvests too' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# Final review of the harvest fix caught this: the clause above requires the
# command's OWN main thread to write two files, but all 9 commands' frontmatter
# still declared only read/delegate tools. The billed re-run that validated the
# clause used --dangerously-skip-permissions, which bypasses tool permission
# checks entirely -- it proved the model complies, not that harvest is reachable
# under a real user's default permissions. Every command carrying the harvest
# clause must also declare Write and Edit.
expect "every command with the harvest clause also grants Write + Edit" "9" \
  "$(grep -l 'this delivery harvests too' "$SCRIPT_DIR"/commands/*.md 2>/dev/null \
     | xargs grep -l '^allowed-tools:.*\bWrite\b.*\bEdit\b' 2>/dev/null | wc -l | tr -d ' ')"
# Orchestration-audit Blocking findings (docs/evals/2026-08-12-orchestration-audit.md):
# write-scope, never-patch, and verify-before-advancing lived only in
# agents/delivery-coordinator.md, which command-driven runs never load.
# Same shape as harvest (v1.41.0). The compact clause lives in the shared
# Interface block.
expect "Interface block refuses to build or patch specialist files" "9" \
  "$(grep -l 'You do not build and you do not patch' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block binds VERIFIED to registered JSON runners" "9" \
  "$(grep -l 'lines are JSON verification records' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "kernel verification subprocesses never use a shell" "1" \
  "$(grep -c 'subprocess.run(list(argv), cwd=cwd, shell=False)' "$SCRIPT_DIR/scripts/guild-kernel/guild.py")"
expect "kernel rejects legacy free-form VERIFIED commands" "1" \
  "$(grep -c 'VERIFIED must be JSON' "$SCRIPT_DIR/scripts/guild-kernel/kernel.py")"
expect "Interface block persists read-only stage files" "9" \
  "$(grep -l 'persist their stage file from the report you already file' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal close.md path backticks in the Interface needle
expect "Interface block never composes close.md" "9" \
  "$(grep -l 'never compose `docs/delivery/<name>/close.md`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal --done-when backticks in the Interface needle
expect "Interface block requires nonempty --done-when" "9" \
  "$(grep -l 'nonempty `--done-when`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal sprint.md path backticks in the Interface needle
expect "Interface block never composes sprint.md" "9" \
  "$(grep -l 'Never compose `docs/sprints/<id>/sprint.md`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "/sprint does not carry the pipeline Interface" "0" \
  "$(grep -c '> \*\*Interface:\*\*' "$SCRIPT_DIR/commands/sprint.md")"
# shellcheck disable=SC2016 # literal RULES backticks in the Interface needle
expect "Interface block prints RULES" "9" \
  "$(grep -l 'plan` prints `RULES:' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal lessons.md path backticks in the Interface needle
expect "Interface block never composes lessons.md" "9" \
  "$(grep -l 'Never compose `docs/team/lessons.md`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `plan` + `--issue` backticks in the Interface needle
expect "Interface block plan passes --issue" "9" \
  "$(grep -l '`plan` passes `--issue <n>`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block never merges" "9" \
  "$(grep -l 'Never merge\.' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "/pair does not carry the pipeline Interface" "0" \
  "$(grep -c '> \*\*Interface:\*\*' "$SCRIPT_DIR/commands/pair.md")"
expect "Interface block never invents a checkmark" "9" \
  "$(grep -l 'Never invent a checkmark' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block never writes a writer stage file" "9" \
  "$(grep -l "never write a writer's stage file for them" "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block counts Adaptive hops against the spawn cap" "9" \
  "$(grep -l 'hops count against the spawn cap' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `--adaptive` backticks in the Interface needle
expect "Interface block requires adaptive opt-in" "9" \
  "$(grep -l 'Without `--adaptive`, ignore' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block requires adaptive fallback hop" "9" \
  "$(grep -l 'one fallback packet per run' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block rejects NOT-CHECKED that names unwaived success criteria" "9" \
  "$(grep -l 'that names an unwaived stage success criterion is a reject' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block requires writers to Write six fields" "9" \
  "$(grep -l 'Writers Write the six fields' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `plan` backticks in the Interface needle
expect "Interface block plans before any Agent" "9" \
  "$(grep -l '`plan` before any Agent' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal command backticks in the Interface needle
expect "Interface block fetches a bounded ready wave" "9" \
  "$(grep -l '`ready` to fetch the bounded dependency-ready wave' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal command backticks in the Interface needle
expect "Interface block claims every lane before Agent" "9" \
  "$(grep -l '`claim --stage <id>` before each Agent' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal field backticks in the Interface needle
expect "Interface block uses typed stages with path ownership" "9" \
  "$(grep -l 'typed `--stage-json`.*`owned_paths`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal field backticks in the Interface needle
expect "Interface block plans stable criterion ids" "9" \
  "$(grep -l 'one-to-one stable `criterion_ids`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal command backticks in the Interface needle
expect "Interface block inspects criterion coverage before report" "9" \
  "$(grep -l 'Before `report`, call `criterion list`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block leaves criterion waivers to the main thread" "9" \
  "$(grep -l 'only the main thread may call `criterion waive' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block binds each verification to a criterion" "9" \
  "$(grep -l 'JSON verification records (`{"criterion"' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal field backticks in the Interface needle
expect "Interface block declares profile approval categories" "9" \
  "$(grep -l '`approval_categories`.*profile category applies' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal command backticks in the Interface needle
expect "Interface block lists and grants approvals before ready" "9" \
  "$(grep -l 'call `approval list`.*main thread may call `approval grant`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `checkpoint list` in the Interface needle
expect "Interface block lists durable checkpoints on start and resume" "9" \
  "$(grep -l 'every start or resume, call `checkpoint list`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `checkpoint open` in the Interface needle
expect "Interface block persists a checkpoint before asking" "9" \
  "$(grep -l 'Before asking.*main thread calls `checkpoint open`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `checkpoint resolve` in the Interface needle
expect "Interface block resolves checkpoints only on the main thread" "9" \
  "$(grep -l 'only the main thread calls `checkpoint resolve`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block preserves exact pending prompts across resume" "9" \
  "$(grep -l 'present the pending record exactly as stored' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block never re-asks a resolved checkpoint" "9" \
  "$(grep -l 'resolved checkpoint is not asked again' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `ready` in the Interface needle
expect "Interface block continues independent lanes during a checkpoint" "9" \
  "$(grep -l 'continue dispatching independent `ready` lanes' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block defines the exact repeated-cycle threshold" "9" \
  "$(grep -l 'exact same 1–4-step cycle reaches three repetitions' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `loop list` and `board` in the Interface needle
expect "Interface block inspects loop evidence and stops dispatch" "9" \
  "$(grep -l 'call `loop list`, print `board`, and stop dispatch' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block forbids an unchanged loop retry" "9" \
  "$(grep -l 'Never retry the same sequence' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal retry commands in the Interface needle
expect "Interface block inspects retries and transitions on resume" "9" \
  "$(grep -l 'every start or resume, call `retry list` and `transition list`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block leaves retry requests to the main thread" "9" \
  "$(grep -l 'only the main thread calls `retry request' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `claim` in the Interface needle
expect "Interface block requires a fresh retry claim" "9" \
  "$(grep -l 'normal atomic `claim` starts it' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block makes duplicate retry events idempotent" "9" \
  "$(grep -l 'duplicate event ID is a no-op' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal status backticks in the Interface needle
expect "Interface block stops after retry exhaustion" "9" \
  "$(grep -l 'second distinct failure marks the stage `failed` and the delivery `stopped`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal field backticks in the Interface needle
expect "Interface block declares CI feedback ownership" "9" \
  "$(grep -l 'declares globally unique `feedback_checks`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal command backticks in the Interface needle
expect "Interface block inspects durable feedback" "9" \
  "$(grep -l 'call `feedback list`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal field backticks in the Interface needle
expect "Interface block routes reviews by longest owned path" "9" \
  "$(grep -l 'longest matching `owned_paths`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal option backticks in the Interface needle
expect "Interface block treats stage as an assertion" "9" \
  "$(grep -l '`--stage` is only an assertion' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal status backticks in the Interface needle
expect "Interface block blocks on unrouted feedback" "9" \
  "$(grep -l 'durable `route_required` and blocks dispatch' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block leaves feedback assignment to main" "9" \
  "$(grep -l 'Only the main thread may call `feedback assign' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block groups one feedback repair attempt" "9" \
  "$(grep -l 'All open items for one lane attach to one repair attempt' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block forbids last-writer routing" "9" \
  "$(grep -l 'Never route by last writer' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal recovery command in the Interface needle
expect "Interface block inspects recoveries before dispatch" "9" \
  "$(grep -l 'every start or resume, call `recovery list` before `ready`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block leaves interruption authority to the main thread" "9" \
  "$(grep -l 'only the main thread calls `recovery interrupt' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block freezes at last observed activity" "9" \
  "$(grep -l 'freezes the claim at its last observed activity' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal action names in the Interface needle
expect "Interface block resolves interruption with continue or stop" "9" \
  "$(grep -l '`recovery resolve --event-id <id> --action continue|stop`' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block never fabricates interruption telemetry" "9" \
  "$(grep -l 'Never reclaim by editing state, reusing the old report, or fabricating telemetry' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# shellcheck disable=SC2016 # literal `board` backticks in the Interface needle
expect "Interface block prints the kernel board" "9" \
  "$(grep -l '`board` to print' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block requires peer-router stage persist" "9" \
  "$(grep -l 'stages/peer-router.md' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block requires handoff colon line" "9" \
  "$(grep -l 'handoff:' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
# Literature-gap tranche (docs/plans/2026-07-29-literature-gap-tranche.md), gate
# cleared by eval run 5. Escalation fired on category only; NOT-CHECKED was
# collected by every stage return and consumed by nothing. Nothing bounded a
# run's total stages (only lane cap and per-stage retry). A checkpoint wrote no
# resume state, so a delivery resumed tomorrow replayed work already paid for.
COORD="$SCRIPT_DIR/agents/delivery-coordinator.md"
expect "thirteen writer agents require a last-Write stage file" "13" \
  "$(grep -l 'as your last Write' "$SCRIPT_DIR"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "four read-only agents defer the stage file to the coordinator" "4" \
  "$(grep -l 'coordinator persists your stage file' "$SCRIPT_DIR"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "peer-router does not require a writer-named packet" "0" \
  "$(grep -c 'writer has named' "$SCRIPT_DIR/agents/peer-router.md")"
expect "peer-router spawns when a packet exists" "2" \
  "$(grep -c 'a packet exists' "$SCRIPT_DIR/agents/peer-router.md")"
expect "coordinator never writes a writer stage file" "yes" \
  "$(grep -q 'never write a writer' "$COORD" && echo yes || echo no)"
expect "coordinator Reads the stage file before a checkmark" "1" \
  "$(grep -c 'Read that file before' "$COORD")"
expect "coordinator shares the generated orchestration lifecycle" "0" \
  "$(python3 "$SCRIPT_DIR/scripts/sync-orchestration-contract.py" --check >/dev/null 2>&1; echo $?)"
expect "coordinator copies the stage-return stub when persisting read-only" "1" \
  "$(grep -c 'copy skills/delivery-templates/stage-return.md' "$COORD")"
# shellcheck disable=SC2016 # literal `board` backticks in the coordinator Kernel needle
expect "coordinator prints the kernel board" "1" \
  "$(grep -c 'print `board`' "$COORD")"
expect "coordinator reports the stage path after each return" "1" \
  "$(grep -c 'report.*docs/delivery/<name>/stages/<agent>.md' "$COORD")"
expect "coordinator copies the Adaptive packet stub" "1" \
  "$(grep -c 'skills/delivery-templates/packet.md' "$COORD")"
expect "coordinator still names Need-to-know briefs" "1" \
  "$(grep -c 'Need-to-know briefs' "$COORD")"
expect "coordinator specialists never Agent a peer" "1" \
  "$(grep -c 'Specialists never Agent a peer' "$COORD")"
expect "coordinator names the packet path" "1" \
  "$(grep -c 'docs/delivery/<name>/packets/' "$COORD")"
expect "coordinator has peer-router validate" "1" \
  "$(grep -c 'validates the packet' "$COORD")"
expect "coordinator prints a handoff line" "1" \
  "$(grep -c 'print a handoff line' "$COORD")"
expect "coordinator counts hops against the spawn cap" "1" \
  "$(grep -c 'hops count against the spawn cap' "$COORD")"
expect "coordinator never spawns peer-router without --adaptive" "1" \
  "$(grep -c 'never spawn.*peer-router.*without.*--adaptive' "$COORD")"
expect "coordinator names one fallback packet per run" "1" \
  "$(grep -c 'one fallback packet per run' "$COORD")"
expect "coordinator fallback TO is next queued specialist else tech-lead" "1" \
  "$(grep -c 'next queued specialist else tech-lead' "$COORD")"
expect "coordinator still joins before dependents" "1" \
  "$(grep -c 'Join before dependents' "$COORD")"
expect "coordinator documents that the kernel owns the cap" "1" \
  "$(grep -c 'the kernel owns the cap' "$COORD")"
expect "coordinator still verifies before advancing" "1" \
  "$(grep -c 'Verify before advancing' "$COORD")"
expect "coordinator persists peer-router.md after router return" "1" \
  "$(grep -c 'stages/peer-router.md' "$COORD")"
expect "coordinator prints handoff colon line" "1" \
  "$(grep -c 'handoff:' "$COORD")"
expect "coordinator spawns peer-router when a packet exists" "1" \
  "$(grep -c 'when a packet exists' "$COORD")"
# The backticks are literal prompt text, not shell interpolation.
# shellcheck disable=SC2016
expect "coordinator never spawns a -fixes suffix" "1" \
  "$(grep -c 'never spawn a `-fixes` suffix' "$COORD")"
expect "coordinator never pastes another specialist diff into a brief" "1" \
  "$(grep -c 'never paste another specialist' "$COORD")"
expect "coordinator writers share one working tree" "1" \
  "$(grep -c 'Writers share one working tree' "$COORD")"
expect "coordinator closes its own answer with the contract" "1" \
  "$(grep -c 'Close your own answer with the contract' "$COORD")"
expect "coordinator fast-paths a single-specialist ask" "1" \
  "$(grep -c 'Fast path — check before anything else' "$COORD")"
expect "coordinator re-brief names the exact stage path" "1" \
  "$(grep -c 'Stage file (overwrite, no other name):' "$COORD")"
expect "coordinator spawn cap is documented once" "1" \
  "$(grep -c 'cap: M spawns' "$COORD")"
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
expect "low confidence is its own stop trigger" "1" \
  "$(grep -c 'Low confidence is a stop trigger in its own right' "$COORD")"
expect "the board declares a stage budget" "1" \
  "$(grep -c 'State both budgets:' "$COORD")"
# shellcheck disable=SC2016 # literal `checkpoints.md` in the coordinator needle
expect "checkpoints persist authoritative resume state" "1" \
  "$(grep -c '`checkpoints.md` preserves the exact question' "$COORD")"
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
expect "one strict evaluation harness contract is committed" "1" \
  "$(python3 - "$SCRIPT_DIR/config/evaluation-harness.json" <<'PY'
import json, pathlib, sys
d = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(int(d.get("schemaVersion") == 1 and d.get("receiptSchemaVersion") == 1
          and d.get("verdictPolicy", {}).get("rubricJudge") == "advisory-only"))
PY
)"
expect "evaluation registry covers all eleven live cases" "11" \
  "$(python3 - "$SCRIPT_DIR/config/evaluation-cases.json" <<'PY'
import json, pathlib, sys
d = json.loads(pathlib.Path(sys.argv[1]).read_text())
cases = d.get("cases", [])
print(len(cases) if d.get("schemaVersion") == 1
      and all(c.get("requiredOutcomes") and c.get("forbiddenOutcomes") for c in cases)
      else 0)
PY
)"
expect "live evals seal authoritative source-bound receipts" "1" \
  "$(grep -c 'evaluation-harness.py.*receipt' "$EVAL_SH")"
expect "CI has a separate evaluation harness gate" "1" \
  "$(grep -c '^    name: evaluation harness$' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI validates the evaluation contract" "1" \
  "$(grep -c 'evaluation-harness.py validate' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication requires the evaluation harness gate" "1" \
  "$(grep -c '"evaluation harness"' "$SCRIPT_DIR/config/release-harness.json")"
expect "README links the evaluation-engineering runbook" "1" \
  "$(grep -c 'evaluation engineering' "$SCRIPT_DIR/README.md")"
MISSING_RUBRIC=""
read -r -a EVAL_CASE_LIST <<<"$(sed -n 's/^ALL_CASES=(\(.*\))$/\1/p' "$EVAL_SH")"
# Opt-in cases count too: excluded from the default sweep is not excluded from
# needing a rubric, and an unjudged case is exactly what this ratchet exists for.
read -r -a EVAL_OPT_IN_LIST <<<"$(sed -n 's/^OPT_IN_CASES=(\(.*\))$/\1/p' "$EVAL_SH")"
EVAL_CASE_LIST+=("${EVAL_OPT_IN_LIST[@]}")
# Capture once and match in-process. `sed | grep -q` races under `pipefail`:
# grep -q closes the pipe on the first hit, sed SIGPIPEs, the pipeline is
# non-zero, and `||` records a false miss. CI hit that on the jq-removed
# invocation (Broken pipe, then `got  tests`) after the with-jq run passed.
RUBRIC_SRC="$(sed -n '/^case_rubric()/,/^}/p' "$EVAL_SH")"
for c in "${EVAL_CASE_LIST[@]}"; do
  case "$RUBRIC_SRC" in
    *"    ${c})"*) ;;
    *) MISSING_RUBRIC="$MISSING_RUBRIC $c" ;;
  esac
done
expect "every eval case has a judge rubric" "" "$MISSING_RUBRIC"
# Assignments only — `regex_verdict="$3"` (reading the verdict) must not trip it.
expect "the rubric judge never alters the case verdict" "0" \
  "$(sed -n '/^judge_case()/,/^}/p' "$EVAL_SH" \
     | grep -cE '(^|[^_[:alnum:]])(CHECK_PASS|CHECK_FAIL|verdict)=')"
# 2026-08-06 check audit: hygiene's two free-prose greps were the last instances
# of the check_log-'update' disease (an English word the model may synonymise —
# see docs/evals/2026-08-06-check-audit.md). The hardened vocabularies are
# additive-only; narrowing one back to a single word is how the disease returns.
expect "hygiene duplicate check accepts synonyms (2026-08-06 audit)" "1" \
  "$(grep -cF "check_log 'duplicat|identical|redundan|twin'" "$SCRIPT_DIR/tests/eval/run-evals.sh")"
expect "hygiene conflict check accepts synonyms (2026-08-06 audit)" "1" \
  "$(grep -cF "check_log 'conflict|contradict|disagree|mutually exclusive'" "$SCRIPT_DIR/tests/eval/run-evals.sh")"
# The gate exists AND main() consults it — unit tests call the functions
# directly, so deleting the wiring would disarm the trigger with everything
# still green. The stage budget lived exactly this failure until v1.36.0.
expect "coordinator hash gate is wired into check_inventory_sync main()" "1" \
  "$(grep -c 'if check_coordinator_hash(ROOT):' "$SCRIPT_DIR/scripts/check_inventory_sync.py")"
# shellcheck disable=SC2016 # literal field backticks in the agent needle
expect "agent FLAGS are hypotheses, not user intent" "17" \
  "$(grep -l 'Agent `FLAGS` are learned hypotheses only' "$SCRIPT_DIR"/agents/*.md | wc -l | tr -d ' ')"
expect "kernel plans only from approved learned rules" "1" \
  "$(grep -c 'lesson.get("status") != "approved"' "$SCRIPT_DIR/scripts/guild-kernel/kernel.py")"
expect "kernel exposes explicit lesson approval" "1" \
  "$(grep -c 'def approve_lesson' "$SCRIPT_DIR/scripts/guild-kernel/kernel.py")"
expect "kernel exposes bounded ready waves" "1" \
  "$(grep -c 'def ready_stages' "$SCRIPT_DIR/scripts/guild-kernel/kernel.py")"
expect "kernel exposes atomic lane claims" "1" \
  "$(grep -c 'def claim_stage' "$SCRIPT_DIR/scripts/guild-kernel/kernel.py")"
expect "runtime hook hashes tool inputs for loop detection" "1" \
  "$(grep -c 'signature=kernel.tool_call_signature(tool_name, tool_input)' "$SCRIPT_DIR/scripts/enforce-kernel-budgets.py")"
expect "kernel stops exact repeated tool cycles" "1" \
  "$(grep -c 'def _mark_loop_detected' "$SCRIPT_DIR/scripts/guild-kernel/kernel.py")"

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
expect "console raw SDK persistence is opt-in" "1" \
  "$(grep -c 'persist_raw=False' "$SCRIPT_DIR/scripts/console/engine.py")"
expect "console loads hard runtime budgets from the shared harness" "1" \
  "$(grep -c '^DEFAULT_BUDGET, HARD_BUDGET_CEILINGS = _load_budget_policy()' "$SCRIPT_DIR/scripts/console/engine.py")"
expect "shared harness includes default and hard assistant-turn budgets" "2" \
  "$(grep -c '"max_turns":' "$SCRIPT_DIR/config/agent-harness.json")"
expect "console interrupts on budget breach" "1" \
  "$(grep -c 'async def _budget_interrupt' "$SCRIPT_DIR/scripts/console/engine.py")"
expect "console trace retention is bounded" "1" \
  "$(grep -c '^DEFAULT_RETENTION_DAYS = 14' "$SCRIPT_DIR/scripts/console/engine.py")"
expect "console exposes durable resume" "1" \
  "$(grep -c 'manager.resume(run_id)' "$SCRIPT_DIR/scripts/console/server.py")"
# shellcheck disable=SC2016 # literal recovery commands in the resume prompt
expect "console resume inspects kernel recovery before dispatch" "1" \
  "$(grep -c '`guild recovery list` before `ready`' "$SCRIPT_DIR/scripts/console/engine.py")"
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
expect "the eval harness hard-gates committed ceilings" "1" \
  "$(grep -c 'scripts/check-eval-budget.py' "$SCRIPT_DIR/tests/eval/run-evals.sh")"
expect "CI continuously replays recorded traces" "1" \
  "$(grep -c 'scripts/replay-console-traces.py' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI runs the release harness units" "1" \
  "$(grep -c 'unittest discover -s tests/release' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "CI validates the synchronized release artifacts" "1" \
  "$(grep -c 'scripts/release.py validate' "$SCRIPT_DIR/.github/workflows/ci.yml")"
expect "release publication is manual only" "1" \
  "$(grep -c '^  workflow_dispatch:' "$SCRIPT_DIR/.github/workflows/release.yml")"
expect "release workflow has no automatic push trigger" "0" \
  "$(grep -c '^  push:' "$SCRIPT_DIR/.github/workflows/release.yml" || true)"
# shellcheck disable=SC2016 # literal GitHub expression in the workflow
expect "release workflow freezes checkout at the requested commit" "1" \
  "$(grep -c 'ref: \${{ github.sha }}' "$SCRIPT_DIR/.github/workflows/release.yml")"
expect "release workflow writes a durable receipt artifact" "2" \
  "$(grep -c 'release-receipt.json' "$SCRIPT_DIR/.github/workflows/release.yml")"
expect "release workflow invokes the fail-closed publisher once" "1" \
  "$(grep -c 'scripts/release.py publish' "$SCRIPT_DIR/.github/workflows/release.yml")"
expect "release publisher exposes no force flag" "0" \
  "$(grep -c -- '\-\-force' "$SCRIPT_DIR/scripts/release.py" || true)"
expect "release harness requires annotated non-force publication" "annotated False" \
  "$(python3 - "$SCRIPT_DIR/config/release-harness.json" <<'PY'
import json, sys
policy = json.load(open(sys.argv[1]))["publication"]
print(policy["tagType"], policy["force"])
PY
)"
expect "release harness gates the release automation job itself" "1" \
  "$(python3 - "$SCRIPT_DIR/config/release-harness.json" <<'PY'
import json, sys
jobs = json.load(open(sys.argv[1]))["requiredCiJobs"]
print(jobs.count("release automation"))
PY
)"
expect "scheduled live evals require an explicit repository opt-in" "1" \
  "$(grep -c "vars.ENABLE_SCHEDULED_LIVE_EVALS == 'true'" "$SCRIPT_DIR/.github/workflows/live-evals.yml")"
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
  "$(grep -c 'max_tokens' "$SCRIPT_DIR/scripts/check-eval-budget.py")"
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
  "$(grep -c 'max_usd' "$SCRIPT_DIR/scripts/check-eval-budget.py")"
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
expect "the opt-in case asserts stage-return files" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_stage_return_files')"
expect "the opt-in case asserts the delivery close file" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_delivery_close_file')"
expect "the opt-in case asserts the delivery graph file" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_delivery_graph_file')"
expect "the opt-in case asserts kernel state" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_kernel_state')"
expect "the opt-in case scores VERIFIED on FULL_LOG" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "check_log_anywhere 'VERIFIED'")"
expect "the opt-in case scores NOT-CHECKED on FULL_LOG" "1" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "check_log_anywhere 'NOT-CHECKED'")"
expect "the opt-in case does not enable check_subagent_log" "0" \
  "$(sed -n '/^checks_feature()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "^[[:space:]]*check_subagent_log ")"
expect "the opt-in case stays out of the default sweep" "0" \
  "$(sed -n 's/^ALL_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature' || true)"
# Checks must read the human-readable log, never the transcript.
expect "no checks function reads the raw transcript" "0" \
  "$(sed -n '/^checks_/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
# The subagent-log helper is the legal way to observe per-stage specialist
# returns (run 8). It must grep the derived $SUBAGENT_LOG, not collapse to
# reading stream.jsonl the way a checks_* workaround would.
expect "check_subagent_log does not read the raw transcript" "0" \
  "$(sed -n '/^check_subagent_log()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "check_stage_return_files does not read the raw transcript" "0" \
  "$(sed -n '/^check_stage_return_files()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "check_delivery_close_file does not read the raw transcript" "0" \
  "$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "check_kernel_state does not read the raw transcript" "0" \
  "$(sed -n '/^check_kernel_state()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "check_delivery_graph_file does not read the raw transcript" "0" \
  "$(sed -n '/^check_delivery_graph_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "check_adaptive_handoff does not read the raw transcript" "0" \
  "$(sed -n '/^check_adaptive_handoff()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "check_adaptive_peer_router does not read the raw transcript" "0" \
  "$(sed -n '/^check_adaptive_peer_router()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
expect "the Adaptive case asserts a handoff on board or close" "1" \
  "$(sed -n '/^checks_feature_adaptive()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_adaptive_handoff')"
expect "the Adaptive case asserts a peer-router stage file" "1" \
  "$(sed -n '/^checks_feature_adaptive()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_adaptive_peer_router')"
expect "the Adaptive case does not enable check_subagent_log" "0" \
  "$(sed -n '/^checks_feature_adaptive()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "^[[:space:]]*check_subagent_log ")"
expect "the resume case asserts skipped database-developer" "1" \
  "$(sed -n '/^checks_feature_resume()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_agent_absent database-developer')"
expect "the resume case does not enable check_subagent_log" "0" \
  "$(sed -n '/^checks_feature_resume()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "^[[:space:]]*check_subagent_log ")"
expect "the resume case is opt-in" "1" \
  "$(sed -n 's/^OPT_IN_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature-resume' || true)"
expect "the resume case stays out of the default sweep" "0" \
  "$(sed -n 's/^ALL_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature-resume' || true)"
expect "the replay case is opt-in" "1" \
  "$(sed -n 's/^OPT_IN_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature-replay' || true)"
expect "the replay case stays out of the default sweep" "0" \
  "$(sed -n 's/^ALL_CASES=(\(.*\))$/\1/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | tr ' ' '\n' | grep -cx 'feature-replay' || true)"
expect "the replay case asserts rules_printed" "1" \
  "$(sed -n '/^checks_feature_replay()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_rules_printed')"
expect "the replay case asserts the Model::all ban" "1" \
  "$(sed -n '/^checks_feature_replay()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'check_no_model_all')"
expect "the replay case does not enable check_subagent_log" "0" \
  "$(sed -n '/^checks_feature_replay()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE "^[[:space:]]*check_subagent_log ")"
expect "check_agent_absent does not read the raw transcript" "0" \
  "$(sed -n '/^check_agent_absent()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
ABSENT_DIR="$(mktemp -d)"
printf '%s\n' '{"attributed":{"agents":{"laravel-team:database-developer":{"tokens":1}},"launched_without_measured_turns":[]}}' \
  >"$ABSENT_DIR/x.cost.json"
expect "check_agent_absent treats a plugin-prefixed agent key as present" "1" \
  "$(LOG="$ABSENT_DIR/x.log" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_agent_absent()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_agent_absent database-developer "x"
    echo "$CHECK_FAIL"
  ')"
rm -rf "$ABSENT_DIR"
# A -fixes suffix is not a registered agent type — the helper must reject it on disk.
STAGE_REJECT_DIR="$(mktemp -d)"
mkdir -p "$STAGE_REJECT_DIR/docs/delivery/tag/stages"
printf '%s\n' \
  'STATUS: ok' 'DID: x' 'VERIFIED: y' 'NOT-CHECKED: z' 'FLAGS: none' 'NEXT: done' \
  >"$STAGE_REJECT_DIR/docs/delivery/tag/stages/backend-developer-fixes.md"
expect "stage return files reject unregistered basenames" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$STAGE_REJECT_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_stage_return_files()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_stage_return_files
    echo "$CHECK_FAIL"
  ')"
rm -rf "$STAGE_REJECT_DIR"
TPL="$SCRIPT_DIR/skills/delivery-templates/SKILL.md"
CLOSE_TPL="$(sed -n '/^## Close file/,/^## Hygiene proposal/p' "$TPL")"
expect "delivery-templates close skeleton prefixes VERIFIED:" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -c '^VERIFIED:')"
expect "delivery-templates close skeleton prefixes NOT-CHECKED:" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -c '^NOT-CHECKED:')"
expect "delivery-templates close skeleton STATUS is the in-flight default" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -cE '^STATUS: running$')"
expect "delivery-templates close skeleton prefixes BOARD:" "1" \
  "$(printf '%s\n' "$CLOSE_TPL" | grep -c '^BOARD:')"
CLOSE_STUB="$SCRIPT_DIR/skills/delivery-templates/close.md"
STAGE_STUB="$SCRIPT_DIR/skills/delivery-templates/stage-return.md"
expect "close stub file prefixes VERIFIED:" "1" \
  "$(sed -n '1p' "$CLOSE_STUB" 2>/dev/null | grep -c '^VERIFIED:')"
expect "close stub file prefixes NOT-CHECKED:" "1" \
  "$(sed -n '2p' "$CLOSE_STUB" 2>/dev/null | grep -c '^NOT-CHECKED:')"
expect "close stub file STATUS is the in-flight default" "1" \
  "$(sed -n '3p' "$CLOSE_STUB" 2>/dev/null | grep -cE '^STATUS: running$')"
expect "close stub file prefixes BOARD:" "1" \
  "$(sed -n '4p' "$CLOSE_STUB" 2>/dev/null | grep -c '^BOARD:')"
PACKET="$SCRIPT_DIR/skills/delivery-templates/packet.md"
expect "packet stub prefixes FROM:" "1" \
  "$(grep -c '^FROM:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes TO:" "1" \
  "$(grep -c '^TO:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes SUMMARY:" "1" \
  "$(grep -c '^SUMMARY:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes PATHS:" "1" \
  "$(grep -c '^PATHS:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes STAGE:" "1" \
  "$(grep -c 'STAGE:' "$PACKET" 2>/dev/null || echo 0)"
GRAPH="$SCRIPT_DIR/skills/delivery-templates/graph.md"
expect "graph stub prefixes NODES:" "1" \
  "$(grep -c '^NODES:' "$GRAPH" 2>/dev/null || echo 0)"
expect "graph stub prefixes EDGES:" "1" \
  "$(grep -c '^EDGES:' "$GRAPH" 2>/dev/null || echo 0)"
expect "graph stub prefixes PARALLEL:" "1" \
  "$(grep -c '^PARALLEL:' "$GRAPH" 2>/dev/null || echo 0)"
expect "graph stub prefixes ON-FAIL:" "1" \
  "$(grep -c '^ON-FAIL:' "$GRAPH" 2>/dev/null || echo 0)"
expect "stage-return stub file prefixes STATUS:" "1" \
  "$(sed -n '1p' "$STAGE_STUB" 2>/dev/null | grep -c '^STATUS:')"
expect "stage-return stub file prefixes DID:" "1" \
  "$(sed -n '2p' "$STAGE_STUB" 2>/dev/null | grep -c '^DID:')"
expect "stage-return stub file prefixes VERIFIED:" "1" \
  "$(sed -n '3p' "$STAGE_STUB" 2>/dev/null | grep -c '^VERIFIED:')"
expect "stage-return stub file prefixes NOT-CHECKED:" "1" \
  "$(sed -n '4p' "$STAGE_STUB" 2>/dev/null | grep -c '^NOT-CHECKED:')"
expect "stage-return stub file prefixes FLAGS:" "1" \
  "$(sed -n '5p' "$STAGE_STUB" 2>/dev/null | grep -c '^FLAGS:')"
expect "stage-return stub file prefixes NEXT:" "1" \
  "$(sed -n '6p' "$STAGE_STUB" 2>/dev/null | grep -c '^NEXT:')"

CLOSE_REJECT_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_REJECT_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: in-progress' 'BOARD: z' \
  >"$CLOSE_REJECT_DIR/docs/delivery/tag/close.md"
expect "close file rejects STATUS in-progress" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_REJECT_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_REJECT_DIR"

CLOSE_PASS_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_PASS_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: z' \
  >"$CLOSE_PASS_DIR/docs/delivery/tag/close.md"
expect "close file accepts STATUS running" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_PASS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_PASS_DIR"

CLOSE_INDENT_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_INDENT_DIR/docs/delivery/tag"
printf '%s\n' \
  '  VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: z' \
  >"$CLOSE_INDENT_DIR/docs/delivery/tag/close.md"
expect "close file rejects indented VERIFIED:" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_INDENT_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_INDENT_DIR"

CLOSE_PAREN_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_PAREN_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED (coordinator): x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: z' \
  >"$CLOSE_PAREN_DIR/docs/delivery/tag/close.md"
expect "close file rejects VERIFIED parenthetical" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_PAREN_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_PAREN_DIR"

CLOSE_DONE_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_DONE_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: done' 'BOARD: z' \
  >"$CLOSE_DONE_DIR/docs/delivery/tag/close.md"
expect "close file accepts STATUS done" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_DONE_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_DONE_DIR"

CLOSE_STOPPED_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_STOPPED_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: stopped' 'BOARD: z' \
  >"$CLOSE_STOPPED_DIR/docs/delivery/tag/close.md"
expect "close file accepts STATUS stopped" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_STOPPED_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_STOPPED_DIR"

CLOSE_BUDGET_DIR="$(mktemp -d)"
mkdir -p "$CLOSE_BUDGET_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: budget_exceeded' 'BOARD: z' \
  >"$CLOSE_BUDGET_DIR/docs/delivery/tag/close.md"
expect "close file accepts STATUS budget_exceeded" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$CLOSE_BUDGET_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_close_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_close_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$CLOSE_BUDGET_DIR"

KERNEL_MISS_DIR="$(mktemp -d)"
mkdir -p "$KERNEL_MISS_DIR/docs/delivery/tag"
expect "kernel state missing file fails" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$KERNEL_MISS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_kernel_state()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_kernel_state
    echo "$CHECK_FAIL"
  ')"
rm -rf "$KERNEL_MISS_DIR"

KERNEL_PASS_DIR="$(mktemp -d)"
mkdir -p "$KERNEL_PASS_DIR/docs/delivery/tag"
python3 -c 'import json, pathlib, sys; pathlib.Path(sys.argv[1]).write_text(json.dumps({
  "status": "running",
  "stages": [
    {"id": "a", "status": "done", "verified": [{"cmd": "php artisan test", "exit": 0}]},
    {"id": "b", "status": "queued", "verified": []}
  ]
}) + "\n")' "$KERNEL_PASS_DIR/docs/delivery/tag/kernel.json"
expect "kernel state accepts running with verified exit 0" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$KERNEL_PASS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_kernel_state()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_kernel_state
    echo "$CHECK_FAIL"
  ')"
rm -rf "$KERNEL_PASS_DIR"

KERNEL_UNVERIFIED_DIR="$(mktemp -d)"
mkdir -p "$KERNEL_UNVERIFIED_DIR/docs/delivery/tag"
python3 -c 'import json, pathlib, sys; pathlib.Path(sys.argv[1]).write_text(json.dumps({
  "status": "done",
  "stages": [{"id": "a", "status": "done", "verified": []}]
}) + "\n")' "$KERNEL_UNVERIFIED_DIR/docs/delivery/tag/kernel.json"
expect "kernel state rejects done stage without verified exit 0" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$KERNEL_UNVERIFIED_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_kernel_state()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_kernel_state
    echo "$CHECK_FAIL"
  ')"
rm -rf "$KERNEL_UNVERIFIED_DIR"

KERNEL_STATUS_DIR="$(mktemp -d)"
mkdir -p "$KERNEL_STATUS_DIR/docs/delivery/tag"
python3 -c 'import json, pathlib, sys; pathlib.Path(sys.argv[1]).write_text(json.dumps({
  "status": "in-progress",
  "stages": []
}) + "\n")' "$KERNEL_STATUS_DIR/docs/delivery/tag/kernel.json"
expect "kernel state rejects status in-progress" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$KERNEL_STATUS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_kernel_state()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_kernel_state
    echo "$CHECK_FAIL"
  ')"
rm -rf "$KERNEL_STATUS_DIR"

GRAPH_PASS_DIR="$(mktemp -d)"
mkdir -p "$GRAPH_PASS_DIR/docs/delivery/tag"
printf '%s\n' \
  'NODES: backend-developer' \
  'EDGES: none' \
  'PARALLEL: none' \
  'ON-FAIL: stop' \
  >"$GRAPH_PASS_DIR/docs/delivery/tag/graph.md"
expect "graph file accepts registered NODES and four labels" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$GRAPH_PASS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_graph_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_graph_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$GRAPH_PASS_DIR"

GRAPH_MISS_DIR="$(mktemp -d)"
mkdir -p "$GRAPH_MISS_DIR/docs/delivery/tag"
expect "graph file FAILs when graph.md is missing" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$GRAPH_MISS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_graph_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_graph_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$GRAPH_MISS_DIR"

GRAPH_UNREG_DIR="$(mktemp -d)"
mkdir -p "$GRAPH_UNREG_DIR/docs/delivery/tag"
printf '%s\n' \
  'NODES: not-an-agent' \
  'EDGES: none' \
  'PARALLEL: none' \
  'ON-FAIL: stop' \
  >"$GRAPH_UNREG_DIR/docs/delivery/tag/graph.md"
expect "graph file rejects unregistered NODES token" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$GRAPH_UNREG_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_graph_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_graph_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$GRAPH_UNREG_DIR"

GRAPH_TO_MISS_DIR="$(mktemp -d)"
mkdir -p "$GRAPH_TO_MISS_DIR/docs/delivery/tag/packets"
printf '%s\n' \
  'NODES: backend-developer' \
  'EDGES: none' \
  'PARALLEL: none' \
  'ON-FAIL: stop' \
  >"$GRAPH_TO_MISS_DIR/docs/delivery/tag/graph.md"
printf '%s\n' \
  'FROM: backend-developer' \
  'TO: qa-engineer' \
  'SUMMARY: x' \
  'PATHS: y' \
  >"$GRAPH_TO_MISS_DIR/docs/delivery/tag/packets/backend-developer-to-qa-engineer.md"
expect "graph file rejects packet TO missing from NODES" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$GRAPH_TO_MISS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_graph_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_graph_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$GRAPH_TO_MISS_DIR"

GRAPH_TO_PASS_DIR="$(mktemp -d)"
mkdir -p "$GRAPH_TO_PASS_DIR/docs/delivery/tag/packets"
printf '%s\n' \
  'NODES: backend-developer, qa-engineer' \
  'EDGES: none' \
  'PARALLEL: none' \
  'ON-FAIL: stop' \
  >"$GRAPH_TO_PASS_DIR/docs/delivery/tag/graph.md"
printf '%s\n' \
  'FROM: backend-developer' \
  'TO: qa-engineer' \
  'SUMMARY: x' \
  'PATHS: y' \
  >"$GRAPH_TO_PASS_DIR/docs/delivery/tag/packets/backend-developer-to-qa-engineer.md"
expect "graph file accepts packet TO that is a NODES token" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$GRAPH_TO_PASS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_delivery_graph_file()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_delivery_graph_file
    echo "$CHECK_FAIL"
  ')"
rm -rf "$GRAPH_TO_PASS_DIR"

HANDOFF_CLOSE_DIR="$(mktemp -d)"
HANDOFF_CLOSE_LOG="$(mktemp)"
mkdir -p "$HANDOFF_CLOSE_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: handoff to qa-engineer' \
  >"$HANDOFF_CLOSE_DIR/docs/delivery/tag/close.md"
: >"$HANDOFF_CLOSE_LOG"
expect "adaptive handoff PASSes from close.md when FULL_LOG is silent" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$HANDOFF_CLOSE_DIR" FULL_LOG="$HANDOFF_CLOSE_LOG" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_adaptive_handoff()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_adaptive_handoff
    echo "$CHECK_FAIL"
  ')"
rm -rf "$HANDOFF_CLOSE_DIR" "$HANDOFF_CLOSE_LOG"

HANDOFF_LOG_DIR="$(mktemp -d)"
HANDOFF_FULL_LOG="$(mktemp)"
mkdir -p "$HANDOFF_LOG_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: no transfer noted' \
  >"$HANDOFF_LOG_DIR/docs/delivery/tag/close.md"
printf 'handoff to qa-engineer\n' >"$HANDOFF_FULL_LOG"
expect "adaptive handoff PASSes from FULL_LOG when close.md is silent" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$HANDOFF_LOG_DIR" FULL_LOG="$HANDOFF_FULL_LOG" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_adaptive_handoff()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_adaptive_handoff
    echo "$CHECK_FAIL"
  ')"
rm -rf "$HANDOFF_LOG_DIR" "$HANDOFF_FULL_LOG"

HANDOFF_MISS_DIR="$(mktemp -d)"
HANDOFF_MISS_LOG="$(mktemp)"
mkdir -p "$HANDOFF_MISS_DIR/docs/delivery/tag"
printf '%s\n' \
  'VERIFIED: x' 'NOT-CHECKED: y' 'STATUS: running' 'BOARD: no transfer noted' \
  >"$HANDOFF_MISS_DIR/docs/delivery/tag/close.md"
: >"$HANDOFF_MISS_LOG"
expect "adaptive handoff FAILs when board and close omit handoff" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$HANDOFF_MISS_DIR" FULL_LOG="$HANDOFF_MISS_LOG" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_adaptive_handoff()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_adaptive_handoff
    echo "$CHECK_FAIL"
  ')"
rm -rf "$HANDOFF_MISS_DIR" "$HANDOFF_MISS_LOG"

PEER_MISS_DIR="$(mktemp -d)"
mkdir -p "$PEER_MISS_DIR/docs/delivery/tag/stages"
expect "adaptive peer-router FAILs when the stage file is missing" "1" \
  "$(ROOT="$SCRIPT_DIR" WORK="$PEER_MISS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_adaptive_peer_router()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_adaptive_peer_router
    echo "$CHECK_FAIL"
  ')"
rm -rf "$PEER_MISS_DIR"

PEER_PASS_DIR="$(mktemp -d)"
mkdir -p "$PEER_PASS_DIR/docs/delivery/tag/stages"
printf '%s\n' \
  'STATUS: ok' 'DID: x' 'VERIFIED: y' 'NOT-CHECKED: z' 'FLAGS: none' 'NEXT: done' \
  >"$PEER_PASS_DIR/docs/delivery/tag/stages/peer-router.md"
expect "adaptive peer-router PASSes with six labels" "0" \
  "$(ROOT="$SCRIPT_DIR" WORK="$PEER_PASS_DIR" bash -c '
    CHECK_PASS=0 CHECK_FAIL=0
    record() { if [ "$1" -ne 0 ]; then CHECK_FAIL=$((CHECK_FAIL + 1)); fi; }
    '"$(sed -n '/^check_adaptive_peer_router()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh")"'
    check_adaptive_peer_router
    echo "$CHECK_FAIL"
  ')"
rm -rf "$PEER_PASS_DIR"
# shellcheck disable=SC2016 # literal $SUBAGENT_LOG in the grep pattern
expect "check_subagent_log greps the derived subagent log" "1" \
  "$(sed -n '/^check_subagent_log()/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE '\$SUBAGENT_LOG' || true)"
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
expect "runtime budget plugin hook meters every subagent tool" "1" \
  "$(hook_command_count "$SCRIPT_DIR/hooks/hooks.json" PreToolUse "" /scripts/enforce-kernel-budgets.sh)"
expect "runtime budget plugin hook records Agent completion" "1" \
  "$(hook_command_count "$SCRIPT_DIR/hooks/hooks.json" PostToolUse 'Agent|Task' /scripts/enforce-kernel-budgets.sh)"

# install_dir copies files only, so scripts/guild-kernel/ needs a dedicated
# installer — same shape as install_console. Eval workdirs go through
# install.sh; without this, Interface calls to guild.py 404.
echo
echo "install.sh"
INSTALL_DEST="$(mktemp -d)"
bash "$SCRIPT_DIR/install.sh" --no-claudemd "$INSTALL_DEST" >/dev/null
expect "install dest contains scripts/guild-kernel/guild.py" "1" \
  "$([ -f "$INSTALL_DEST/scripts/guild-kernel/guild.py" ] && echo 1 || echo 0)"
expect "install dest contains scripts/outcome-benchmark.py" "1" \
  "$([ -f "$INSTALL_DEST/scripts/outcome-benchmark.py" ] && echo 1 || echo 0)"
expect "install dest contains the outcome benchmark contract" "1" \
  "$([ -f "$INSTALL_DEST/config/benchmark-harness.json" ] && echo 1 || echo 0)"
expect "install dest contains the context packet runtime" "1" \
  "$([ -f "$INSTALL_DEST/scripts/guild-kernel/context_packets.py" ] && echo 1 || echo 0)"
expect "install dest contains the context packet contract" "1" \
  "$([ -f "$INSTALL_DEST/config/context-harness.json" ] && echo 1 || echo 0)"
expect "install dest contains the memory retrieval runtime" "1" \
  "$([ -f "$INSTALL_DEST/scripts/guild-kernel/memory_store.py" ] && echo 1 || echo 0)"
expect "install dest contains the memory retrieval contract" "1" \
  "$([ -f "$INSTALL_DEST/config/memory-harness.json" ] && echo 1 || echo 0)"
expect "install dest contains the evaluation runtime" "1" \
  "$([ -f "$INSTALL_DEST/scripts/evaluation-harness.py" ] && echo 1 || echo 0)"
expect "install dest contains the evaluation contract" "1" \
  "$([ -f "$INSTALL_DEST/config/evaluation-harness.json" ] && echo 1 || echo 0)"
expect "install dest contains the evaluation case registry" "1" \
  "$([ -f "$INSTALL_DEST/config/evaluation-cases.json" ] && echo 1 || echo 0)"
expect "install dest contains the shared agent harness" "1" \
  "$([ -f "$INSTALL_DEST/config/agent-harness.json" ] && echo 1 || echo 0)"
expect "install dest contains the native-write policy hook" "1" \
  "$([ -x "$INSTALL_DEST/scripts/enforce-agent-paths.sh" ] && echo 1 || echo 0)"
expect "install dest contains the registry-backed policy engine" "1" \
  "$([ -f "$INSTALL_DEST/scripts/enforce-agent-paths.py" ] && echo 1 || echo 0)"
expect "install dest contains the approval policy hook" "1" \
  "$([ -x "$INSTALL_DEST/scripts/enforce-kernel-approvals.sh" ] && echo 1 || echo 0)"
expect "install dest contains the approval policy engine" "1" \
  "$([ -f "$INSTALL_DEST/scripts/enforce-kernel-approvals.py" ] && echo 1 || echo 0)"
expect "installer wires the approval hook into project settings" "1" \
  "$(grep -c 'enforce-kernel-approvals.sh' "$INSTALL_DEST/.claude/settings.json")"
expect "install dest contains the runtime-budget policy hook" "1" \
  "$([ -x "$INSTALL_DEST/scripts/enforce-kernel-budgets.sh" ] && echo 1 || echo 0)"
expect "install dest contains the runtime-budget policy engine" "1" \
  "$([ -f "$INSTALL_DEST/scripts/enforce-kernel-budgets.py" ] && echo 1 || echo 0)"
expect "installer wires runtime budgets at pre-tool and completion boundaries" "2" \
  "$(grep -c 'enforce-kernel-budgets.sh' "$INSTALL_DEST/.claude/settings.json")"
expect "installed runtime budget hook meters every subagent tool" "1" \
  "$(hook_command_count "$INSTALL_DEST/.claude/settings.json" PreToolUse "" ./scripts/enforce-kernel-budgets.sh)"
expect "installed runtime budget hook records Agent completion" "1" \
  "$(hook_command_count "$INSTALL_DEST/.claude/settings.json" PostToolUse 'Agent|Task' ./scripts/enforce-kernel-budgets.sh)"
rm -rf "$INSTALL_DEST"

echo
echo "----------------------------------------"
printf 'total: %d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && echo "ALL GREEN" || echo "FAILURES PRESENT"
exit "$FAIL"
