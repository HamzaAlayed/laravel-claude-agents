#!/usr/bin/env bash
# Bounce Writes/Edits of docs/delivery/*/close.md unless the payload is helper
# shape. Wire this via a PreToolUse hook on Write and Edit. Exit 2 to block.
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

deny() {
  echo "blocked: docs/delivery/*/close.md must be helper shape." >&2
  echo "copy skills/delivery-templates/close.md; close.md is not log.md." >&2
  exit 2
}

PATH_TARGET="$(extract_path)"

# No-parser / unparseable fallback: PATH_TARGET is the raw stdin. Fail closed
# when the payload looks like a delivery close.md — do not try to score labels.
if [ "$PATH_TARGET" = "$INPUT" ]; then
  if printf '%s' "$PATH_TARGET" | grep -qE 'docs/delivery' \
     && printf '%s' "$PATH_TARGET" | grep -qE 'close\.md'; then
    deny
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
