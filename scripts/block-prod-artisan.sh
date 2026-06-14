#!/usr/bin/env bash
# Blocks destructive `php artisan` commands when the current shell context
# looks like it might be hitting a production environment.
# Wire this into agents that have Bash access via a PreToolUse hook on Bash.
#
# Hook receives the tool invocation JSON on stdin; exit 0 to allow, exit 2 to block.

set -euo pipefail

INPUT="$(cat)"

# Extract the Bash command from tool-input JSON. Degrades jq -> python3 -> raw
# payload rather than failing open when no JSON parser is present.
extract_command() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r '.tool_input.command // empty'
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c 'import sys,json
try:
    print(json.load(sys.stdin).get("tool_input",{}).get("command","") or "")
except Exception:
    sys.exit(3)' 2>/dev/null || printf '%s' "$INPUT"
  else
    printf '%s' "$INPUT"
  fi
}

COMMAND="$(extract_command)"
[ -z "$COMMAND" ] && exit 0

COMMAND_FLAT="$(printf '%s' "$COMMAND" | tr '\n\t' '  ')"

# Destructive or production-affecting artisan commands.
# Tune for your environment — these are conservative defaults.
DANGEROUS_ARTISAN='(php[[:space:]]+artisan[[:space:]]+(migrate:fresh|migrate:reset|migrate:rollback|db:wipe|db:seed|tinker|cache:clear|config:clear|optimize:clear|telescope:prune|horizon:clear|queue:flush|queue:forget|queue:retry))'

# Detect prod-looking context — either the command itself names a prod env,
# or `--env=production` is passed.
PROD_CONTEXT='(--env[= ]+(production|prod|live)|APP_ENV[= ]+(production|prod|live))'

# Also block if .env.production is being sourced or copied over .env in the same command
ENV_PROD_OVERRIDE='(\.env\.production|\.env\.prod)'

if echo "$COMMAND_FLAT" | grep -iqE "$DANGEROUS_ARTISAN"; then
  if echo "$COMMAND_FLAT" | grep -iqE "$PROD_CONTEXT"; then
    echo "blocked: destructive artisan command targeting production." >&2
    echo "command: $COMMAND" >&2
    echo "run this only from a privileged operator session with explicit human approval." >&2
    exit 2
  fi
fi

if echo "$COMMAND_FLAT" | grep -iqE "$ENV_PROD_OVERRIDE"; then
  if echo "$COMMAND_FLAT" | grep -iqE 'php[[:space:]]+artisan'; then
    echo "blocked: running artisan against a production env file." >&2
    echo "command: $COMMAND" >&2
    exit 2
  fi
fi

# Always warn on `migrate:fresh` / `db:wipe` regardless of detected env —
# in 99% of cases these are accidents.
if echo "$COMMAND_FLAT" | grep -iqE 'php[[:space:]]+artisan[[:space:]]+(migrate:fresh|db:wipe)'; then
  echo "warn: 'migrate:fresh' / 'db:wipe' detected. confirm this is the local DB before proceeding." >&2
  # Soft warn (exit 0) rather than hard block — local dev needs these freely.
  # Promote to exit 2 if your team wants the stronger guarantee.
fi

exit 0
