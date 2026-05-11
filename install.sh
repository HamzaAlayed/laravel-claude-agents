#!/usr/bin/env bash
# Installs the Laravel-aware Claude Code agent team into a project.
# Usage:
#   ./install.sh                # installs into the current directory (.)
#   ./install.sh /path/to/proj  # installs into the given directory
#   ./install.sh -g             # installs globally to ~/.claude/
#   ./install.sh --no-confirm   # skip confirmation prompts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL=0
NO_CONFIRM=0
TARGET=""

print_usage() {
  cat <<EOF
Installs the Laravel-aware Claude Code agent team into a project.

Usage:
  $(basename "$0") [path]      install into [path] (default: current directory)
  $(basename "$0") -g          install globally into ~/.claude/
  $(basename "$0") --no-confirm  do not prompt for confirmation

Installs:
  agents/    -> <target>/.claude/agents/
  commands/  -> <target>/.claude/commands/
  scripts/   -> <target>/scripts/ (only if missing or with confirmation)

Optional next steps after install:
  - Copy CLAUDE.md.template to <target>/CLAUDE.md and fill it in
  - Wire scripts/* into the agents that need them via PreToolUse hooks
EOF
}

# Parse args
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) print_usage; exit 0 ;;
    -g|--global) GLOBAL=1; shift ;;
    --no-confirm) NO_CONFIRM=1; shift ;;
    -*) echo "unknown option: $1" >&2; print_usage; exit 1 ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [ "$GLOBAL" -eq 1 ]; then
  DEST_ROOT="${HOME}/.claude"
else
  TARGET="${TARGET:-.}"
  if [ ! -d "$TARGET" ]; then
    echo "target directory does not exist: $TARGET" >&2
    exit 1
  fi
  DEST_ROOT="${TARGET}/.claude"
fi

# Laravel detection (skip if global or --no-confirm)
if [ "$GLOBAL" -eq 0 ] && [ "$NO_CONFIRM" -eq 0 ]; then
  if [ ! -f "${TARGET}/artisan" ] || [ ! -f "${TARGET}/composer.json" ]; then
    echo "warn: '$TARGET' does not look like a Laravel project (no artisan/composer.json)."
    echo "      these agents are tuned for Laravel; install anyway?"
    read -r -p "      [y/N] " ans
    case "$ans" in
      y|Y|yes|YES) ;;
      *) echo "aborted."; exit 0 ;;
    esac
  fi
fi

confirm_overwrite() {
  local what="$1"
  local path="$2"
  [ "$NO_CONFIRM" -eq 1 ] && return 0
  if [ -e "$path" ]; then
    echo "warn: '$path' already exists ($what)."
    read -r -p "      overwrite? existing files will be backed up to .bak [y/N] " ans
    case "$ans" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
  fi
  return 0
}

install_dir() {
  local src="$1"
  local dest="$2"
  local what="$3"

  if [ ! -d "$src" ]; then
    echo "warn: source missing: $src — skipping $what"
    return
  fi

  mkdir -p "$dest"

  local copied=0 skipped=0 backed_up=0
  shopt -s nullglob
  for f in "$src"/*; do
    [ -d "$f" ] && continue
    local target="$dest/$(basename "$f")"
    if [ -e "$target" ]; then
      if ! confirm_overwrite "$what file" "$target"; then
        skipped=$((skipped + 1))
        continue
      fi
      cp -p "$target" "${target}.bak.$(date +%Y%m%d%H%M%S)"
      backed_up=$((backed_up + 1))
    fi
    cp "$f" "$target"
    copied=$((copied + 1))
  done
  shopt -u nullglob

  echo "  $what: $copied copied, $skipped skipped, $backed_up backed up -> $dest"
}

echo "installing into: $DEST_ROOT"
mkdir -p "$DEST_ROOT/agents" "$DEST_ROOT/commands"

install_dir "$SCRIPT_DIR/agents"   "$DEST_ROOT/agents"   "agents"
install_dir "$SCRIPT_DIR/commands" "$DEST_ROOT/commands" "commands"

# scripts/ goes into <target>/scripts (not under .claude/) so projects can reuse
# them in CI and in hooks. Only install if --no-confirm or the dir is missing/empty.
if [ "$GLOBAL" -eq 0 ]; then
  SCRIPTS_DEST="$TARGET/scripts"
  if [ -d "$SCRIPTS_DEST" ] && [ "$(find "$SCRIPTS_DEST" -maxdepth 1 -type f 2>/dev/null | wc -l)" -gt 0 ] && [ "$NO_CONFIRM" -eq 0 ]; then
    echo "info: '$SCRIPTS_DEST' already contains files — install guardrail scripts there?"
    read -r -p "      [y/N] " ans
    case "$ans" in y|Y|yes|YES)
      install_dir "$SCRIPT_DIR/scripts" "$SCRIPTS_DEST" "guardrail scripts" ;;
    *) echo "  guardrail scripts: skipped" ;;
    esac
  else
    install_dir "$SCRIPT_DIR/scripts" "$SCRIPTS_DEST" "guardrail scripts"
  fi

  # Make scripts executable
  find "$SCRIPTS_DEST" -maxdepth 1 -name "*.sh" -type f -exec chmod +x {} \; 2>/dev/null || true
fi

echo
echo "done."
echo
echo "next steps:"
echo "  1) restart your Claude Code session — agents load at startup"
if [ "$GLOBAL" -eq 0 ]; then
  echo "  2) copy CLAUDE.md.template to '$TARGET/CLAUDE.md' and fill it in"
  echo "  3) wire scripts/*.sh into PreToolUse hooks on the agents that need them (see README)"
else
  echo "  2) agents and commands are now available globally in every project"
fi
echo
echo "drive multi-stage work with:"
echo "    claude --agent delivery-coordinator"
echo "for single-task work, just run 'claude' — agents auto-delegate based on your prompt."
