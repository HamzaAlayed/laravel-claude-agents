#!/bin/bash
# Installs the agent team into a project as .claude/agents/
# Run from the directory containing this script.

set -e

TARGET="${1:-.}"

if [ ! -d "$TARGET" ]; then
  echo "Target directory does not exist: $TARGET"
  exit 1
fi

mkdir -p "$TARGET/.claude/agents"
cp agents/*.md "$TARGET/.claude/agents/"

echo "Installed 15 agents into $TARGET/.claude/agents/"
echo "Restart your Claude Code session to pick them up (file-based agents load at startup)."
echo
echo "Optional next steps:"
echo "  - Copy CLAUDE.md.template to $TARGET/CLAUDE.md and fill it in"
echo "  - Copy scripts/ to $TARGET/scripts/ if you want the DB guardrail"
