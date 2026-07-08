#!/usr/bin/env bash
# Observer, not a guard: streams subagent lifecycle events to
# .claude/agents-board.jsonl so the /board HTML dashboard can render the team
# working live. Wired as PreToolUse + PostToolUse on the subagent tool
# (matcher "Agent|Task" — Task is the pre-2.1.63 alias of Agent).
#
# Deterministic by design: hooks fire on every spawn/finish regardless of what
# the orchestrating model remembers to narrate. Fails open everywhere — a
# dashboard must never block delivery. Claude Code only (Gemini's hook input
# carries no subagent identity).

set -u  # deliberately no -e / no pipefail: never fail the tool call

INPUT="$(cat)" || exit 0

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
DIR="$ROOT/.claude"
OUT="$DIR/agents-board.jsonl"

# Build one compact event line from the hook stdin. jq -> python3 -> give up
# (fail open: no parser, no dashboard, no harm).
EVENT=""
if command -v jq >/dev/null 2>&1; then
  EVENT="$(printf '%s' "$INPUT" | jq -c '
    select(((.tool_name // "Agent") | test("^(Agent|Task)$")))
    | {ts: (now | floor),
       sid: ((.session_id // "local")[0:8]),
       ev: (if .hook_event_name == "PostToolUse" then "end" else "start" end),
       agent: ((.tool_input.subagent_type // "unknown") | sub("^.*:"; "")),
       task: ((.tool_input.description // "")[0:120]),
       ms: (.tool_response.totalDurationMs // null),
       tokens: (.tool_response.totalTokens // null),
       status: (.tool_response.status // null)}' 2>/dev/null)"
elif command -v python3 >/dev/null 2>&1; then
  EVENT="$(printf '%s' "$INPUT" | python3 -c '
import sys, json, time
try:
    d = json.load(sys.stdin)
    if d.get("tool_name", "Agent") not in ("Agent", "Task"):
        sys.exit(0)
    ti = d.get("tool_input", {}) or {}
    tr = d.get("tool_response", {}) or {}
    print(json.dumps({
        "ts": int(time.time()),
        "sid": (d.get("session_id") or "local")[:8],
        "ev": "end" if d.get("hook_event_name") == "PostToolUse" else "start",
        "agent": (ti.get("subagent_type") or "unknown").split(":")[-1],
        "task": (ti.get("description") or "")[:120],
        "ms": tr.get("totalDurationMs"),
        "tokens": tr.get("totalTokens"),
        "status": tr.get("status"),
    }, separators=(",", ":")))
except Exception:
    pass' 2>/dev/null)"
fi
[ -z "$EVENT" ] && exit 0

mkdir -p "$DIR" 2>/dev/null || exit 0

# First event: drop the viewer next to the feed so /board has something to
# serve. Plugin installs resolve via CLAUDE_PLUGIN_ROOT; install.sh layouts
# find it next to this script.
if [ ! -f "$DIR/board.html" ]; then
  for src in "${CLAUDE_PLUGIN_ROOT:-}/scripts/board.html" "$(dirname "$0")/board.html"; do
    if [ -f "$src" ]; then
      cp "$src" "$DIR/board.html" 2>/dev/null && break
    fi
  done
fi

printf '%s\n' "$EVENT" >> "$OUT" 2>/dev/null

# Keep the feed bounded: past ~4000 events, keep the newest 2000.
LINES="$(wc -l < "$OUT" 2>/dev/null || echo 0)"
if [ "${LINES:-0}" -gt 4000 ]; then
  TMP="$(mktemp 2>/dev/null)" && tail -n 2000 "$OUT" > "$TMP" 2>/dev/null && mv "$TMP" "$OUT" 2>/dev/null
fi

exit 0
