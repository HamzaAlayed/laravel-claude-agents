#!/usr/bin/env bash
# Install the Laravel pack's Codex CLI 'Core' target into a project:
#   - AGENTS.md            -> <target>/AGENTS.md            (created only if missing)
#   - laravel-conventions  -> <target>/.agents/skills/      (Codex agent skill)
#   - guardrail hooks       -> <target>/.codex/hooks/ + hooks.json (PreToolUse)
#
# Usage:
#   ./codex/install-codex.sh                # install into the current directory
#   ./codex/install-codex.sh /path/to/proj  # install into the given project
#
# Codex copies the guardrail scripts' paths are resolved from the git root at
# runtime, so the project must be a git repo. On the next `codex` run you'll be
# asked to review and trust the hooks before they execute.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-.}"

if [ ! -d "$TARGET" ]; then
  echo "target directory does not exist: $TARGET" >&2
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"

echo "installing Codex Core target into: $TARGET"

# 1. AGENTS.md — never clobber an existing one (Codex concatenates the hierarchy).
if [ -f "$TARGET/AGENTS.md" ]; then
  echo "  AGENTS.md: already exists — left untouched (merge from $SRC/AGENTS.md if you want our conventions)"
else
  cp "$SRC/AGENTS.md" "$TARGET/AGENTS.md"
  echo "  AGENTS.md: created -> $TARGET/AGENTS.md"
fi

# 2. Skill — copy the laravel-conventions skill into the repo-local skills dir.
mkdir -p "$TARGET/.agents/skills"
rm -rf "$TARGET/.agents/skills/laravel-conventions"
cp -R "$SRC/.agents/skills/laravel-conventions" "$TARGET/.agents/skills/laravel-conventions"
echo "  skill: laravel-conventions -> $TARGET/.agents/skills/laravel-conventions"

# 3. Guardrail hook scripts.
mkdir -p "$TARGET/.codex/hooks"
cp "$SRC/.codex/hooks/"*.sh "$TARGET/.codex/hooks/"
chmod +x "$TARGET/.codex/hooks/"*.sh
echo "  hooks: 3 guardrail scripts -> $TARGET/.codex/hooks/"

# 4. hooks.json — back up an existing one rather than clobbering (it may carry
#    the user's own hooks; merging JSON is left to them).
if [ -f "$TARGET/.codex/hooks.json" ]; then
  bak="$TARGET/.codex/hooks.json.bak.$(date +%Y%m%d%H%M%S)"
  cp "$TARGET/.codex/hooks.json" "$bak"
  cp "$SRC/.codex/hooks.json" "$TARGET/.codex/hooks.json"
  echo "  hooks.json: existing backed up to $(basename "$bak"); ours written — merge if you had custom hooks"
else
  cp "$SRC/.codex/hooks.json" "$TARGET/.codex/hooks.json"
  echo "  hooks.json: created -> $TARGET/.codex/hooks.json"
fi

echo
echo "done."
echo "next steps:"
echo "  1) ensure '$TARGET' is a git repo (hook paths resolve from the git root)"
echo "  2) review $TARGET/AGENTS.md and fill in the project-specific TODOs"
echo "  3) run 'codex' — it will ask you to review and trust the guardrail hooks before they run"
echo "  4) the full 17-agent team is available on Claude Code / Gemini CLI (this is the Codex Core target)"
