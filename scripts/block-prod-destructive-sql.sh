#!/bin/bash
# Blocks destructive SQL operations targeting production-named databases.
# Wire this into the database-developer agent via a PreToolUse hook on Bash.
# See README.md for setup details.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Detect destructive operations (case-insensitive)
DESTRUCTIVE='\b(DROP\s+TABLE|DROP\s+DATABASE|DROP\s+SCHEMA|TRUNCATE|DELETE\s+FROM)\b'

# Detect production-looking targets — tune this regex to your naming
PROD_TARGET='(prod[-_]|production|live[-_])'

if echo "$COMMAND" | grep -iE "$DESTRUCTIVE" > /dev/null; then
  if echo "$COMMAND" | grep -iE "$PROD_TARGET" > /dev/null; then
    echo "Blocked: destructive SQL targeting production. Get explicit human approval and run from a privileged operator session." >&2
    exit 2
  fi
fi

exit 0
