#!/usr/bin/env bash
# Redirects host PHP tooling through Laravel Sail when the project runs on Sail.
#
# Agents default to bare `php artisan` / `composer` / `vendor/bin/*` — on a
# Sail project those hit the host PHP (wrong version, missing extensions, no
# DB) and the agent burns turns flailing. This hook blocks the bare form with
# the exact sail rewrite so the first failure self-corrects.
#
# Active only when BOTH markers sit at the project root: an executable
# `vendor/bin/sail` AND a compose file (`sail:install` publishes one). The
# sail dependency alone proves nothing — the default Laravel skeleton ships
# `laravel/sail` in require-dev even for Herd/Valet users.
#
# Opt out (Herd/Valet alongside a leftover compose file): LARAVEL_AGENTS_SAIL=0
#
# Hook receives the tool invocation JSON on stdin; exit 0 to allow, exit 2 to block.

set -euo pipefail

INPUT="$(cat)"

[ "${LARAVEL_AGENTS_SAIL:-}" = "0" ] && exit 0

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

COMMAND="$(extract '.tool_input.command' 'd.get("tool_input",{}).get("command","")')"
CWD="$(extract '.cwd' 'd.get("cwd","")')"

# No parser available -> screen the raw payload (quotes stripped so word
# boundaries match) rather than failing open; root detection falls back to
# CLAUDE_PROJECT_DIR / PWD below.
if ! command -v jq >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  COMMAND="$(printf '%s' "$INPUT" | tr '"' ' ')"
fi

[ -z "$COMMAND" ] && exit 0

# --- Does this project run on Sail? -----------------------------------------
ROOT=""
for candidate in "$CWD" "${CLAUDE_PROJECT_DIR:-}" "$PWD"; do
  if [ -n "$candidate" ] && [ -x "$candidate/vendor/bin/sail" ]; then
    ROOT="$candidate"
    break
  fi
done
[ -z "$ROOT" ] && exit 0

COMPOSE=""
for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
  if [ -f "$ROOT/$f" ]; then
    COMPOSE="$f"
    break
  fi
done
[ -z "$COMPOSE" ] && exit 0

FLAT="$(printf '%s' "$COMMAND" | tr '\n\t' '  ')"

# Already containerised -> allow. Matches `sail`, `./vendor/bin/sail`, and
# explicit docker / docker compose invocations.
if printf '%s' "$FLAT" | grep -qE '(^|[;&| /])sail([ ]|$)'; then
  exit 0
fi
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])docker(-compose)?([ ]|$)'; then
  exit 0
fi

block() {
  echo "blocked: this project runs on Laravel Sail ($COMPOSE + vendor/bin/sail) — host PHP is the wrong runtime." >&2
  echo "reason:  $1" >&2
  echo "rewrite: php artisan <cmd>         -> ./vendor/bin/sail artisan <cmd>" >&2
  echo "         composer <cmd>            -> ./vendor/bin/sail composer <cmd>" >&2
  echo "         vendor/bin/pint <args>    -> ./vendor/bin/sail pint <args>" >&2
  echo "         vendor/bin/pest <args>    -> ./vendor/bin/sail pest <args>" >&2
  echo "         vendor/bin/phpunit <args> -> ./vendor/bin/sail phpunit <args>" >&2
  echo "         vendor/bin/phpstan <args> -> ./vendor/bin/sail bin phpstan <args>" >&2
  echo "containers down? ./vendor/bin/sail up -d first." >&2
  echo "genuinely host-side? set LARAVEL_AGENTS_SAIL=0 to disable this guard." >&2
  echo "command: $COMMAND" >&2
  exit 2
}

# --- Bare artisan (php artisan, php8.3 artisan, php -d ... artisan) ----------
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])php[0-9.]*[ ]+(-[^ ]+[ ]+)*artisan([ ]|$)'; then
  block "bare 'php artisan' on the host"
fi

# --- Bare vendor/bin tools (with or without ./ or a php prefix) --------------
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])(php[0-9.]*[ ]+)?(\./)?vendor/bin/(pint|pest|phpunit|phpstan|paratest)([ ]|$)'; then
  block "bare vendor/bin binary on the host"
fi

# --- Bare composer ------------------------------------------------------------
if printf '%s' "$FLAT" | grep -qE '(^|[;&| ])composer[ ]+[a-z]'; then
  block "bare 'composer' on the host"
fi

exit 0
