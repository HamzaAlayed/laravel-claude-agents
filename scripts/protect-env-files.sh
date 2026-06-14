#!/usr/bin/env bash
# Protects sensitive env files from accidental writes by agents.
# Wire this into agents that have Write/Edit access via a PreToolUse hook
# on Write and Edit. Returns exit 2 to block.
#
# Hook receives the tool invocation JSON on stdin.

set -euo pipefail

INPUT="$(cat)"

# Both Write and Edit pass the target via tool_input.path (Write) or
# tool_input.file_path (Edit-like). Degrade jq -> python3 -> raw payload so a
# missing JSON parser can't silently disable the guard.
extract_path() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r '.tool_input.path // .tool_input.file_path // empty'
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c 'import sys,json
try:
    ti=json.load(sys.stdin).get("tool_input",{})
    print(ti.get("path") or ti.get("file_path") or "")
except Exception:
    sys.exit(3)' 2>/dev/null || printf '%s' "$INPUT"
  else
    printf '%s' "$INPUT"
  fi
}

PATH_TARGET="$(extract_path)"
[ -z "$PATH_TARGET" ] && exit 0

# Sensitive env-file check. A boundary-aware regex rather than a `basename` case
# so it works both on a cleanly-parsed path AND on the raw JSON payload (the
# no-parser fallback). `.env.example` is deliberately NOT matched — the optional
# suffix group only accepts the protected variants, and `.example` fails both the
# suffix alternatives and the trailing boundary class.
ENV_FILE='(^|/|")\.env(\.(production|prod|live|staging|local))?("|$|[^.A-Za-z0-9_])'

if printf '%s' "$PATH_TARGET" | grep -qE "$ENV_FILE"; then
  echo "blocked: agents may not write to a protected .env file." >&2
  echo "target: $PATH_TARGET" >&2
  echo "if you need to add a new env key, document it in .env.example and CLAUDE.md instead, and have a human update the live env file." >&2
  exit 2
fi

# Also block writes to anything under a path that looks like an env-secrets directory
case "$PATH_TARGET" in
  */secrets/*|*/credentials/*|*/.ssh/*|*id_rsa*|*id_ed25519*)
    echo "blocked: refusing to write to a credential-looking path: $PATH_TARGET" >&2
    exit 2
    ;;
esac

exit 0
