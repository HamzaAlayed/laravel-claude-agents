#!/usr/bin/env bash
# One-click installer for the Laravel-aware Claude Code agent team.
#
# Remote (recommended):
#   curl -fsSL https://raw.githubusercontent.com/HamzaAlayed/laravel-claude-agents/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- -g          # global install
#   curl -fsSL .../install.sh | bash -s -- /path/proj  # specific target
#
# Local:
#   ./install.sh                # installs into the current directory (.)
#   ./install.sh /path/to/proj  # installs into the given directory
#   ./install.sh -g             # installs globally to ~/.claude/
#   ./install.sh --interactive  # prompt before overwrites (default: zero-prompt)
#   ./install.sh --no-hooks     # skip auto-wiring .claude/settings.json hooks
#   ./install.sh --no-claudemd  # skip copying CLAUDE.md.template

set -euo pipefail

REPO_URL="${LARAVEL_CLAUDE_AGENTS_REPO:-https://github.com/HamzaAlayed/laravel-claude-agents.git}"
REPO_BRANCH="${LARAVEL_CLAUDE_AGENTS_BRANCH:-main}"

# Resolve script directory; tolerate piped invocation where BASH_SOURCE is empty.
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  SCRIPT_DIR=""
fi

# Bootstrap: if we don't have the source tree alongside us, clone the repo and re-exec.
# This is what makes `curl | bash` work — the piped script clones itself, then runs.
if [ -z "$SCRIPT_DIR" ] || [ ! -d "$SCRIPT_DIR/agents" ] || [ ! -d "$SCRIPT_DIR/commands" ]; then
  if ! command -v git >/dev/null 2>&1; then
    echo "error: git is required for remote install but was not found in PATH." >&2
    exit 1
  fi
  TMPDIR="$(mktemp -d -t laravel-claude-agents.XXXXXX)"
  trap 'rm -rf "$TMPDIR"' EXIT
  echo "→ fetching laravel-claude-agents ($REPO_BRANCH) ..."
  git clone --quiet --depth=1 --branch "$REPO_BRANCH" "$REPO_URL" "$TMPDIR/repo" >/dev/null
  # Don't `exec` — we'd lose the EXIT trap and leak the temp dir on every remote install.
  bash "$TMPDIR/repo/install.sh" "$@"
  exit $?
fi

GLOBAL=0
INTERACTIVE=0
SKIP_HOOKS=0
SKIP_CLAUDEMD=0
TARGET=""

print_usage() {
  cat <<EOF
One-click installer for the Laravel-aware Claude Code agent team.

Usage:
  $(basename "$0") [path]        install into [path] (default: current directory)
  $(basename "$0") -g            install globally into ~/.claude/
  $(basename "$0") --interactive prompt before overwriting files (default: zero-prompt)
  $(basename "$0") --no-confirm  (deprecated, kept for compat — same as default)
  $(basename "$0") --no-hooks    skip auto-wiring .claude/settings.json hooks
  $(basename "$0") --no-claudemd skip copying CLAUDE.md.template

Remote one-liner:
  curl -fsSL https://raw.githubusercontent.com/HamzaAlayed/laravel-claude-agents/main/install.sh | bash

Installs:
  agents/    -> <target>/.claude/agents/
  commands/  -> <target>/.claude/commands/
  scripts/   -> <target>/scripts/ (project installs only)
  CLAUDE.md  -> <target>/CLAUDE.md (from template, only if missing)
  hooks      -> merged into <target>/.claude/settings.json (idempotent)
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) print_usage; exit 0 ;;
    -g|--global) GLOBAL=1; shift ;;
    --interactive) INTERACTIVE=1; shift ;;
    --no-confirm) shift ;; # deprecated, now the default
    --no-hooks) SKIP_HOOKS=1; shift ;;
    --no-claudemd) SKIP_CLAUDEMD=1; shift ;;
    -*) echo "unknown option: $1" >&2; print_usage; exit 1 ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [ "$GLOBAL" -eq 1 ]; then
  DEST_ROOT="${HOME}/.claude"
  TARGET=""
else
  TARGET="${TARGET:-.}"
  if [ ! -d "$TARGET" ]; then
    echo "target directory does not exist: $TARGET" >&2
    exit 1
  fi
  TARGET="$(cd "$TARGET" && pwd)"
  DEST_ROOT="${TARGET}/.claude"
fi

# Laravel detection — warn only in interactive mode. Zero-prompt installs proceed.
if [ "$GLOBAL" -eq 0 ] && [ "$INTERACTIVE" -eq 1 ]; then
  if [ ! -f "${TARGET}/artisan" ] || [ ! -f "${TARGET}/composer.json" ]; then
    echo "warn: '$TARGET' does not look like a Laravel project (no artisan/composer.json)."
    read -r -p "      install anyway? [y/N] " ans
    case "$ans" in
      y|Y|yes|YES) ;;
      *) echo "aborted."; exit 0 ;;
    esac
  fi
fi

confirm_overwrite() {
  local what="$1"
  local path="$2"
  [ "$INTERACTIVE" -eq 0 ] && return 0
  if [ -e "$path" ]; then
    read -r -p "warn: '$path' exists ($what). overwrite? (backup created) [y/N] " ans
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
      if cmp -s "$f" "$target"; then
        skipped=$((skipped + 1))
        continue
      fi
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

install_claudemd() {
  [ "$SKIP_CLAUDEMD" -eq 1 ] && return 0
  [ "$GLOBAL" -eq 1 ] && return 0
  local src="$SCRIPT_DIR/CLAUDE.md.template"
  local dest="$TARGET/CLAUDE.md"
  [ ! -f "$src" ] && { echo "  CLAUDE.md: template missing — skipped"; return 0; }
  if [ -f "$dest" ]; then
    echo "  CLAUDE.md: already exists — left untouched"
    return 0
  fi
  cp "$src" "$dest"
  echo "  CLAUDE.md: created from template -> $dest"
}

HOOKS_WIRED=0

wire_hooks() {
  [ "$SKIP_HOOKS" -eq 1 ] && return 0
  [ "$GLOBAL" -eq 1 ] && return 0
  if ! command -v python3 >/dev/null 2>&1; then
    echo "  hooks: python3 not found — skipping auto-wire (configure manually per README)"
    SKIP_HOOKS=1
    return 0
  fi

  local settings="$DEST_ROOT/settings.json"
  mkdir -p "$DEST_ROOT"

  if python3 - "$settings" <<'PY'
import json, os, sys

path = sys.argv[1]
data = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except json.JSONDecodeError:
        backup = path + ".bak." + __import__("time").strftime("%Y%m%d%H%M%S")
        os.replace(path, backup)
        print(f"  hooks: existing settings.json was invalid JSON — backed up to {backup}")
        data = {}

hooks = data.get("hooks")
if not isinstance(hooks, dict):
    hooks = {}
    data["hooks"] = hooks

pre = hooks.get("PreToolUse")
if not isinstance(pre, list):
    pre = []
    hooks["PreToolUse"] = pre

# Claude Code's actual hook shape is nested: each matcher entry contains a
# `hooks` array of {type, command} objects.
desired = [
    ("Bash",       "./scripts/block-prod-destructive-sql.sh"),
    ("Bash",       "./scripts/block-prod-artisan.sh"),
    ("Bash",       "./scripts/enforce-reviewer-readonly.sh"),
    ("Bash",       "./scripts/enforce-sail.sh"),
    ("Write|Edit", "./scripts/protect-env-files.sh"),
]

def has_command(entry, matcher, command):
    if not isinstance(entry, dict) or entry.get("matcher") != matcher:
        return False
    # Nested shape (the real Claude Code format)
    inner = entry.get("hooks")
    if isinstance(inner, list):
        for h in inner:
            if isinstance(h, dict) and h.get("command") == command:
                return True
    # Tolerate legacy flat shape from older installs
    if entry.get("command") == command:
        return True
    return False

added = 0
for matcher, command in desired:
    if any(has_command(e, matcher, command) for e in pre):
        continue
    pre.append({
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command}],
    })
    added += 1

# Idempotent rerun: only rewrite the file when we actually changed something.
if added > 0:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

print(f"  hooks: {added} added, {len(desired) - added} already present -> {path}")
PY
  then
    HOOKS_WIRED=1
  fi
}

echo "installing into: $DEST_ROOT"
mkdir -p "$DEST_ROOT/agents" "$DEST_ROOT/commands"

install_dir "$SCRIPT_DIR/agents"   "$DEST_ROOT/agents"   "agents"
install_dir "$SCRIPT_DIR/commands" "$DEST_ROOT/commands" "commands"

# scripts/ goes into <target>/scripts (not under .claude/) so projects can reuse
# them in CI and in hooks.
if [ "$GLOBAL" -eq 0 ]; then
  SCRIPTS_DEST="$TARGET/scripts"
  install_dir "$SCRIPT_DIR/scripts" "$SCRIPTS_DEST" "guardrail scripts"
  find "$SCRIPTS_DEST" -maxdepth 1 -name "*.sh" -type f -exec chmod +x {} \; 2>/dev/null || true

  install_claudemd
  wire_hooks
fi

echo
echo "done."
echo
echo "next steps:"
echo "  1) restart your Claude Code session — agents load at startup"
if [ "$GLOBAL" -eq 0 ]; then
  if [ "$SKIP_CLAUDEMD" -eq 0 ]; then
    echo "  2) review $TARGET/CLAUDE.md and fill in the project-specific TODOs"
  fi
  if [ "$HOOKS_WIRED" -eq 1 ]; then
    echo "  3) hooks are already wired in $DEST_ROOT/settings.json — verify with: cat $DEST_ROOT/settings.json"
  elif [ "$SKIP_HOOKS" -eq 1 ]; then
    echo "  3) hooks were NOT auto-wired — configure them manually per the README"
  fi
else
  echo "  2) agents and commands are now available globally in every project"
fi
echo
echo "drive multi-stage work with:"
echo "    claude --agent delivery-coordinator"
echo "for single-task work, just run 'claude' — agents auto-delegate based on your prompt."
