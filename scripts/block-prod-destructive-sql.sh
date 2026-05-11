#!/usr/bin/env bash
# Blocks destructive SQL operations targeting production-named databases.
# Wire this into the database-developer agent via a PreToolUse hook on Bash.
# See README.md for setup details.
#
# Hook receives the tool invocation JSON on stdin; exit 0 to allow, exit 2 to block.

set -euo pipefail

INPUT="$(cat)"

# `jq` may not be available in every environment — fail open with a warning if missing,
# rather than silently blocking nothing.
if ! command -v jq >/dev/null 2>&1; then
  echo "warn: block-prod-destructive-sql.sh needs jq to parse tool input; allowing without check" >&2
  exit 0
fi

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Destructive ops (case-insensitive)
DESTRUCTIVE='\b(DROP[[:space:]]+TABLE|DROP[[:space:]]+DATABASE|DROP[[:space:]]+SCHEMA|TRUNCATE|DELETE[[:space:]]+FROM|UPDATE[[:space:]]+[^[:space:]]+[[:space:]]+SET)\b'

# Production-looking targets — tune this regex to your hostname/DB naming conventions.
PROD_TARGET='(prod[-_]|production|live[-_]|-prd[-.]|-prd$)'

if echo "$COMMAND" | grep -iE "$DESTRUCTIVE" >/dev/null; then
  if echo "$COMMAND" | grep -iE "$PROD_TARGET" >/dev/null; then
    echo "blocked: destructive SQL targeting a production-named target detected." >&2
    echo "command: $COMMAND" >&2
    echo "if this is intentional, get explicit human approval and run from a privileged operator session." >&2
    exit 2
  fi
fi

exit 0
