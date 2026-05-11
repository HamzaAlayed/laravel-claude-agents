#!/usr/bin/env bash
# Protects sensitive env files from accidental writes by agents.
# Wire this into agents that have Write/Edit access via a PreToolUse hook
# on Write and Edit. Returns exit 2 to block.
#
# Hook receives the tool invocation JSON on stdin.

set -euo pipefail

INPUT="$(cat)"

if ! command -v jq >/dev/null 2>&1; then
  echo "warn: protect-env-files.sh needs jq; allowing without check" >&2
  exit 0
fi

# Both Write and Edit pass the target via tool_input.path (Write) or tool_input.file_path (Edit-like).
PATH_TARGET="$(printf '%s' "$INPUT" | jq -r '.tool_input.path // .tool_input.file_path // empty')"
[ -z "$PATH_TARGET" ] && exit 0

# Filename-only check — covers `.env`, `.env.production`, `.env.prod`, `.env.live`, `.env.staging`
basename_target="$(basename "$PATH_TARGET")"

case "$basename_target" in
  .env|.env.production|.env.prod|.env.live|.env.staging|.env.local)
    echo "blocked: agents may not write to '$basename_target'." >&2
    echo "target: $PATH_TARGET" >&2
    echo "if you need to add a new env key, document it in .env.example and CLAUDE.md instead, and have a human update the live env file." >&2
    exit 2
    ;;
esac

# Also block writes to anything under a path that looks like an env-secrets directory
case "$PATH_TARGET" in
  */secrets/*|*/credentials/*|*/.ssh/*|*id_rsa*|*id_ed25519*)
    echo "blocked: refusing to write to a credential-looking path: $PATH_TARGET" >&2
    exit 2
    ;;
esac

exit 0
