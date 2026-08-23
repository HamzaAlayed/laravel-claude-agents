#!/usr/bin/env bash
# Bounce Writes/Edits of docs/delivery/*/close.md unless the payload is helper
# shape, and deny Bash that writes that path. Wire this via a PreToolUse hook
# on Write, Edit, and Bash. Exit 2 to block.
#
# Hook receives the tool invocation JSON on stdin.

set -euo pipefail

INPUT="$(cat)"

# Both Write and Edit pass the target via tool_input.path (Write) or
# tool_input.file_path (Edit-like). Degrade jq -> python3 -> raw payload so a
# missing JSON parser can't silently disable the guard.
extract_path() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r '.tool_input.path // .tool_input.file_path // .tool_input.absolute_path // empty'
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c 'import sys,json
try:
    ti=json.load(sys.stdin).get("tool_input",{})
    print(ti.get("path") or ti.get("file_path") or ti.get("absolute_path") or "")
except Exception:
    sys.exit(3)' 2>/dev/null || printf '%s' "$INPUT"
  else
    printf '%s' "$INPUT"
  fi
}

# Write sends the new file via tool_input.contents; Edit sends the replacement
# via tool_input.new_string. Parse failure returns empty so a matching path
# fails closed instead of scanning raw JSON for labels.
extract_body() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r '.tool_input.contents // .tool_input.new_string // empty'
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c 'import sys,json
try:
    ti=json.load(sys.stdin).get("tool_input",{})
    print(ti.get("contents") or ti.get("new_string") or "")
except Exception:
    sys.exit(3)' 2>/dev/null || true
  else
    printf ''
  fi
}

extract_command() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r '.tool_input.command // empty'
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c 'import sys,json
try:
    ti=json.load(sys.stdin).get("tool_input",{})
    print(ti.get("command") or "")
except Exception:
    sys.exit(3)' 2>/dev/null || true
  else
    printf ''
  fi
}

deny() {
  echo "blocked: docs/delivery/*/close.md must be helper shape." >&2
  echo "copy skills/delivery-templates/close.md; close.md is not log.md." >&2
  exit 2
}

deny_bash() {
  echo "blocked: Bash must not write docs/delivery/*/close.md." >&2
  echo "use the Write tool; copy skills/delivery-templates/close.md." >&2
  exit 2
}

# True when flattened Bash writes docs/delivery/*/close.md via >, >>, tee, or
# a heredoc onto that path. Does not parse heredoc labels. Does not match
# skills/delivery-templates/close.md.
writes_delivery_close() {
  local cmd="$1"
  # Relative or absolute docs/delivery/<feature>/close.md — not the skill stub.
  local path='docs/delivery/[^ ;&|"'"'"']+/close\.md'

  if printf '%s' "$cmd" | grep -qE ">>?[ ]*[\"']?[^ ;&|\"']*$path"; then
    return 0
  fi
  if printf '%s' "$cmd" | grep -qE "(^|[;&| ])tee([ ]+-[a-zA-Z]+)*[ ]+[\"']?[^ ;&|\"']*$path"; then
    return 0
  fi
  if printf '%s' "$cmd" | grep -qE "${path}[\"']?[ ]*<<"; then
    return 0
  fi
  return 1
}

PATH_TARGET="$(extract_path)"

# No-parser / unparseable fallback: PATH_TARGET is the raw stdin. Fail closed
# when the payload looks like a delivery close.md — do not try to score labels.
# Stronger than write-operator-only: any docs/delivery + close.md still denies
# (Write|Edit journal and Bash writes).
if [ "$PATH_TARGET" = "$INPUT" ]; then
  if printf '%s' "$PATH_TARGET" | grep -qE 'docs/delivery' \
     && printf '%s' "$PATH_TARGET" | grep -qE 'close\.md'; then
    deny
  fi
  exit 0
fi

COMMAND="$(extract_command)"
if [ -n "$COMMAND" ]; then
  FLAT="$(printf '%s' "$COMMAND" | tr '\n\t' '  ')"
  if writes_delivery_close "$FLAT"; then
    deny_bash
  fi
  exit 0
fi

# Delivery artifact only — not skills/delivery-templates/close.md.
if ! printf '%s' "$PATH_TARGET" | grep -qE '(^|/)docs/delivery/.+/close\.md'; then
  exit 0
fi

BODY="$(extract_body)"

if printf '%s' "$BODY" | grep -qE '^VERIFIED:' \
   && printf '%s' "$BODY" | grep -qE '^NOT-CHECKED:' \
   && printf '%s' "$BODY" | grep -qE '^STATUS: (running|done|stopped)' \
   && printf '%s' "$BODY" | grep -qE '^BOARD:'; then
  exit 0
fi

deny
