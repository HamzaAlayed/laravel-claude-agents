#!/usr/bin/env bash
# Blocks destructive SQL operations targeting production-named databases.
# Wire this into the database-developer agent via a PreToolUse hook on Bash.
# See README.md for setup details.
#
# Hook receives the tool invocation JSON on stdin; exit 0 to allow, exit 2 to block.

set -euo pipefail

INPUT="$(cat)"

# Extract the Bash command from the tool-input JSON.
# Order of preference: jq -> python3 -> raw payload. We deliberately degrade to
# scanning the raw stdin rather than failing open: a security guard that allows
# everything when its JSON parser is missing is worse than one that occasionally
# over-matches. The dangerous keywords survive JSON encoding verbatim.
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
    # No JSON parser available — scan the raw payload so we still fail closed.
    printf '%s' "$INPUT"
  fi
}

COMMAND="$(extract_command)"
[ -z "$COMMAND" ] && exit 0

# Flatten newlines so multiline statements can't slip a destructive verb past a
# line-oriented regex.
COMMAND_FLAT="$(printf '%s' "$COMMAND" | tr '\n\t' '  ')"

# Destructive ops (case-insensitive). UPDATE/DELETE allow table aliases
# (`UPDATE orders AS o SET ...`) by matching up to the next SET/WHERE/clause end.
DESTRUCTIVE='\b(DROP[[:space:]]+(TABLE|DATABASE|SCHEMA|INDEX)|TRUNCATE|DELETE[[:space:]]+FROM|UPDATE[[:space:]]+[^;]+[[:space:]]+SET)\b'

# Production-looking targets — tune this regex to your hostname/DB naming conventions.
PROD_TARGET='(prod[-_]|production|live[-_]|-prd[-.]|-prd$)'

if echo "$COMMAND_FLAT" | grep -iqE "$DESTRUCTIVE"; then
  if echo "$COMMAND_FLAT" | grep -iqE "$PROD_TARGET"; then
    echo "blocked: destructive SQL targeting a production-named target detected." >&2
    echo "command: $COMMAND" >&2
    echo "if this is intentional, get explicit human approval and run from a privileged operator session." >&2
    exit 2
  fi
fi

exit 0
