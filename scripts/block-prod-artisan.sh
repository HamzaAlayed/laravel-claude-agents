#!/usr/bin/env bash
# Blocks destructive `php artisan` commands when the current shell context
# looks like it might be hitting a production environment.
# Wire this into agents that have Bash access via a PreToolUse hook on Bash.
#
# Hook receives the tool invocation JSON on stdin; exit 0 to allow, exit 2 to block.

set -euo pipefail

INPUT="$(cat)"

if ! command -v jq >/dev/null 2>&1; then
  echo "warn: block-prod-artisan.sh needs jq; allowing without check" >&2
  exit 0
fi

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"
[ -z "$COMMAND" ] && exit 0

# Destructive or production-affecting artisan commands.
# Tune for your environment — these are conservative defaults.
DANGEROUS_ARTISAN='(php[[:space:]]+artisan[[:space:]]+(migrate:fresh|migrate:reset|migrate:rollback|db:wipe|db:seed|tinker|cache:clear|config:clear|optimize:clear|telescope:prune|horizon:clear|queue:flush|queue:forget|queue:retry))'

# Detect prod-looking context — either the command itself names a prod env,
# or `--env=production` is passed.
PROD_CONTEXT='(--env[= ]+(production|prod|live)|APP_ENV[= ]+(production|prod|live))'

# Also block if .env.production is being sourced or copied over .env in the same command
ENV_PROD_OVERRIDE='(\.env\.production|\.env\.prod)'

if echo "$COMMAND" | grep -iE "$DANGEROUS_ARTISAN" >/dev/null; then
  if echo "$COMMAND" | grep -iE "$PROD_CONTEXT" >/dev/null; then
    echo "blocked: destructive artisan command targeting production." >&2
    echo "command: $COMMAND" >&2
    echo "run this only from a privileged operator session with explicit human approval." >&2
    exit 2
  fi
fi

if echo "$COMMAND" | grep -iE "$ENV_PROD_OVERRIDE" >/dev/null; then
  if echo "$COMMAND" | grep -iE 'php[[:space:]]+artisan' >/dev/null; then
    echo "blocked: running artisan against a production env file." >&2
    echo "command: $COMMAND" >&2
    exit 2
  fi
fi

# Always block `migrate:fresh` and `db:wipe` regardless of detected env —
# in 99% of cases these are accidents.
if echo "$COMMAND" | grep -iE 'php[[:space:]]+artisan[[:space:]]+(migrate:fresh|db:wipe)' >/dev/null; then
  echo "warn: 'migrate:fresh' / 'db:wipe' detected. confirm this is the local DB before proceeding." >&2
  # Soft warn (exit 0) rather than hard block — local dev needs these freely.
  # Promote to exit 2 if your team wants the stronger guarantee.
fi

exit 0
