#!/usr/bin/env bash
# Codex CLI variant: block writes to protected .env / secret files.
# Wire as a PreToolUse hook matching `apply_patch|Edit|Write` (see .codex/hooks.json).
#
# Codex delivers file edits either as an apply_patch patch in `.tool_input.command`
# (with `*** Add/Update/Delete File: <path>` headers) or via a path field on
# Edit/Write. We extract the TARGET PATH(S) only — never scan patch *content*, which
# would false-positive on any file that merely mentions `.env`. exit 2 blocks; the
# reason goes to stderr (Codex's documented PreToolUse block contract).

set -euo pipefail

INPUT="$(cat)"

get_path() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r '.tool_input.path // .tool_input.file_path // .tool_input.absolute_path // empty'
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c 'import sys, json
try:
    ti = json.load(sys.stdin).get("tool_input", {})
    print(ti.get("path") or ti.get("file_path") or ti.get("absolute_path") or "")
except Exception:
    sys.exit(0)'
  else
    printf ''
  fi
}

PF="$(get_path)"
candidates="$PF"

# apply_patch target paths — pulled from the RAW payload so it works with or without
# a JSON parser (the `*** Add File: <path>` headers survive JSON-escaping as
# `... File: <path>\n`). Only header paths are considered — never patch *content*,
# which would false-positive on any file that merely mentions `.env`.
patch_paths="$(printf '%s' "$INPUT" | grep -oE '\*\*\* (Add|Update|Delete|Move) File: [^"\]+' | sed -E 's/^\*\*\* (Add|Update|Delete|Move) File: //' || true)"
[ -n "$patch_paths" ] && candidates="$candidates
$patch_paths"

# No-parser fallback for Edit/Write path fields (jq and python3 both absent):
# read the path straight out of the raw JSON.
if [ -z "$PF" ] && ! command -v jq >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  raw_paths="$(printf '%s' "$INPUT" | grep -oE '"(path|file_path|absolute_path)"[[:space:]]*:[[:space:]]*"[^"]+"' | sed -E 's/.*"([^"]+)"$/\1/' || true)"
  [ -n "$raw_paths" ] && candidates="$candidates
$raw_paths"
fi

blocked=""
while IFS= read -r p; do
  [ -z "$p" ] && continue
  p="$(printf '%s' "$p" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
  [ -z "$p" ] && continue
  case "$(basename "$p")" in
    .env|.env.production|.env.prod|.env.live|.env.staging|.env.local) blocked="$p" ;;
  esac
  case "$p" in
    */secrets/*|*/credentials/*|*/.ssh/*|*id_rsa*|*id_ed25519*) blocked="$p" ;;
  esac
  [ -n "$blocked" ] && break
done <<EOF
$candidates
EOF

if [ -n "$blocked" ]; then
  echo "blocked: refusing to write a protected env/secret file: $blocked" >&2
  echo "if you need a new env key, document it in .env.example and AGENTS.md; a human updates the live env file." >&2
  exit 2
fi

exit 0
