#!/usr/bin/env bash
# Blocks file-mutating Bash from the read-only reviewer subagents
# (tech-lead, security-engineer, performance-engineer).
#
# Their frontmatter already denies Edit/Write, but Bash remains a write vector
# (sed -i, redirects, git reset, pint without --test — see
# docs/read-only-by-design.md). This hook closes it deterministically: the
# PreToolUse stdin JSON carries `agent_type` when a subagent calls, so the
# guard applies only to the three reviewers and never touches builders or the
# main thread. Claude Code only — Gemini's hook input carries no agent
# identity, so this script is deliberately absent from the Gemini target.
#
# Hook receives the tool invocation JSON on stdin; exit 0 to allow, exit 2 to block.

set -euo pipefail

INPUT="$(cat)"

REVIEWERS='(tech-lead|security-engineer|performance-engineer)'

# Extract a field from the tool-input JSON. Degrades jq -> python3 -> empty
# (the raw-payload fallback is handled separately below).
extract() {
  local jq_path="$1" py_expr="$2"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r "$jq_path // empty"
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c "import sys,json
try:
    d=json.load(sys.stdin)
    print($py_expr or \"\")
except Exception:
    pass" 2>/dev/null || true
  fi
}

AGENT_TYPE="$(extract '.agent_type' 'd.get("agent_type","")')"
COMMAND="$(extract '.tool_input.command' 'd.get("tool_input",{}).get("command","")')"

# No parser available -> conservative raw-payload mode: if the payload names a
# reviewer agent_type, screen the whole payload rather than failing open.
if ! command -v jq >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  if printf '%s' "$INPUT" | grep -qE "\"agent_type\"[[:space:]]*:[[:space:]]*\"[^\"]*${REVIEWERS}\""; then
    AGENT_TYPE="reviewer"
    # Quotes stripped so word-boundary patterns match inside the JSON payload.
    COMMAND="$(printf '%s' "$INPUT" | tr '"' ' ')"
  fi
fi

# Not a reviewer subagent (main thread, builder, or field absent) -> allow.
printf '%s' "$AGENT_TYPE" | grep -qE "(^|:)${REVIEWERS}$|^reviewer$" || exit 0
[ -z "$COMMAND" ] && exit 0

FLAT="$(printf '%s' "$COMMAND" | tr '\n\t' '  ')"

block() {
  echo "blocked: read-only reviewer ($AGENT_TYPE) attempted a file-mutating command." >&2
  echo "reason:  $1" >&2
  echo "command: $COMMAND" >&2
  echo "reviewers report findings; the owning builder applies the fix (docs/read-only-by-design.md)." >&2
  exit 2
}

# --- In-place editors -------------------------------------------------------
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])(sed|perl)[ ]([^;&|]* )?-[a-zA-Z]*i|--in-place'; then
  block "in-place edit (sed -i / perl -i)"
fi

# --- tee (writes its argument) — /dev/* and /tmp/* targets tolerated --------
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])tee[ ]' &&
   ! printf '%s' "$FLAT" | grep -qE '(^|[;&| ])tee[ ]+(-a[ ]+)?(/dev/|/tmp/)'; then
  block "tee writes files"
fi

# --- Output redirects -------------------------------------------------------
# Strip tokens that look like '>' but are not file redirects, then strip safe
# redirect targets (fd dups, /dev/*, /tmp/*); anything left with '>' blocks.
SCRUBBED="$(printf '%s' "$FLAT" | sed -E \
  -e 's/->//g; s/=>//g; s/>=//g; s/<<[-~]?//g' \
  -e 's/[0-9]*>>?[ ]*(\&[0-9]+|\/dev\/(null|stderr|stdout|tty)|\/tmp\/[^ ;&|]*)//g')"
if printf '%s' "$SCRUBBED" | grep -q '>'; then
  block "output redirect to a file"
fi

# --- git subcommands that mutate the tree, index, or remote -----------------
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])git[ ]+(-[^ ]+[ ]+)*(checkout|restore|reset|clean|stash|commit|merge|rebase|cherry-pick|revert|am|apply|push|pull|rm|mv)([ ]|$)'; then
  block "mutating git subcommand"
fi

# --- pint without --test (formats in place) ---------------------------------
if printf '%s' "$FLAT" | grep -qE '(^|[;&|/ ])pint([ ]|$)' &&
   ! printf '%s' "$FLAT" | grep -qE '(^|[;&|/ ])pint[^;&|]*--test'; then
  block "pint without --test rewrites files"
fi

# --- artisan commands that mutate state --------------------------------------
# migrate:status stays allowed; bare migrate and destructive variants block.
if printf '%s' "$FLAT" | grep -qiE 'artisan[ ]+(migrate(:(fresh|reset|rollback|refresh))?([ ]|$)|db:(seed|wipe)|queue:(work|flush|forget|retry|clear)|cache:clear|config:(clear|cache)|optimize|schedule:(run|work)|tinker)'; then
  block "state-mutating artisan command"
fi

# --- filesystem + dependency mutators ----------------------------------------
# shellcheck disable=SC2016 # literal $TMPDIR is the pattern being matched, not an expansion
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])(rm|mv|cp|touch|chmod|chown|truncate|ln)[ ]' &&
   ! printf '%s' "$FLAT" | grep -qE '(^|[;&| ])(rm|mv|cp|touch)[ ]+(-[a-zA-Z]+[ ]+)*(/tmp/|"?\$TMPDIR)'; then
  block "filesystem mutation (rm/mv/cp/touch/chmod/chown/ln)"
fi
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])composer[ ]+(install|update|require|remove|dump-autoload)|(^|[;&| ])(npm|pnpm|yarn)[ ]+(install|ci|add|update|remove|up)([ ]|$)'; then
  block "dependency mutation (composer/npm) — report the missing dependency as a review gap instead"
fi

exit 0
