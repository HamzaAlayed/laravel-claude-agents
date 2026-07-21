#!/usr/bin/env bash
# Observer, not a guard: streams subagent lifecycle events to
# .claude/agents-board.jsonl so the /board HTML dashboard can render the team
# working live. Wired as PreToolUse + PostToolUse on the subagent tool
# (matcher "Agent|Task" — Task is the pre-2.1.63 alias of Agent) and as
# SubagentStop, which fires on completion of sync AND async subagents — the
# only completion signal an async-launched agent ever gets (PostToolUse fires
# at launch with status "async_launched" and null ms/tokens).
#
# Events carry `parent`: hook stdin's top-level agent_type identifies the
# CALLING agent when the spawn happens inside a subagent (absent from the
# main thread) — the board indents child lanes under their spawner.
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
    if .hook_event_name == "SubagentStop" then
      {ts: (now | floor),
       sid: ((.session_id // "local")[0:8]),
       ev: "end",
       agent: ((.agent_type // "unknown") | sub("^.*:"; "")),
       task: "",
       ms: (if .duration != null then (.duration * 1000 | floor) else null end),
       tokens: null,
       status: "subagent_stop",
       parent: null}
    else
      select(((.tool_name // "Agent") | test("^(Agent|Task)$")))
      | {ts: (now | floor),
         sid: ((.session_id // "local")[0:8]),
         ev: (if .hook_event_name == "PostToolUse" then "end" else "start" end),
         agent: ((.tool_input.subagent_type // "unknown") | sub("^.*:"; "")),
         task: ((.tool_input.description // "")[0:120]),
         ms: (.tool_response.totalDurationMs // null),
         tokens: (.tool_response.totalTokens // null),
         status: (.tool_response.status // null),
         parent: (if .agent_type != null then (.agent_type | sub("^.*:"; "")) else null end)}
    end' 2>/dev/null)"
elif command -v python3 >/dev/null 2>&1; then
  EVENT="$(printf '%s' "$INPUT" | python3 -c '
import sys, json, time
try:
    d = json.load(sys.stdin)
    if d.get("hook_event_name") == "SubagentStop":
        dur = d.get("duration")
        print(json.dumps({
            "ts": int(time.time()),
            "sid": (d.get("session_id") or "local")[:8],
            "ev": "end",
            "agent": (d.get("agent_type") or "unknown").split(":")[-1],
            "task": "",
            "ms": int(dur * 1000) if isinstance(dur, (int, float)) else None,
            "tokens": None,
            "status": "subagent_stop",
            "parent": None,
        }, separators=(",", ":")))
        sys.exit(0)
    if d.get("tool_name", "Agent") not in ("Agent", "Task"):
        sys.exit(0)
    ti = d.get("tool_input", {}) or {}
    tr = d.get("tool_response", {}) or {}
    at = d.get("agent_type")
    print(json.dumps({
        "ts": int(time.time()),
        "sid": (d.get("session_id") or "local")[:8],
        "ev": "end" if d.get("hook_event_name") == "PostToolUse" else "start",
        "agent": (ti.get("subagent_type") or "unknown").split(":")[-1],
        "task": (ti.get("description") or "")[:120],
        "ms": tr.get("totalDurationMs"),
        "tokens": tr.get("totalTokens"),
        "status": tr.get("status"),
        "parent": at.split(":")[-1] if at else None,
    }, separators=(",", ":")))
except Exception:
    pass' 2>/dev/null)"
fi
[ -z "$EVENT" ] && exit 0

mkdir -p "$DIR" 2>/dev/null || exit 0

# Dedupe: installed BOTH as a plugin (command ${CLAUDE_PLUGIN_ROOT}/scripts/…)
# and via install.sh (command ./scripts/…), Claude Code registers two distinct
# command strings for the same event, so this script runs twice per spawn.
# Suppress the twin: identical to the last line modulo ts, within 2 seconds.
#
# The twin invocations run CONCURRENTLY — without a lock both read the feed
# before either appends and the compare never fires (eval run 3 evidence).
# mkdir is the atomic primitive; a stale lock (killed hook) is stolen after
# ~2s of spinning so the dashboard never blocks delivery.
LOCKDIR="$OUT.lock"
tries=0
until mkdir "$LOCKDIR" 2>/dev/null; do
  tries=$((tries + 1))
  [ "$tries" -gt 40 ] && break
  sleep 0.05
done
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

LAST="$(tail -n 1 "$OUT" 2>/dev/null || true)"
if [ -n "$LAST" ]; then
  LAST_KEY="$(printf '%s' "$LAST" | sed 's/"ts":[0-9]*/"ts":0/')"
  NEW_KEY="$(printf '%s' "$EVENT" | sed 's/"ts":[0-9]*/"ts":0/')"
  if [ "$LAST_KEY" = "$NEW_KEY" ]; then
    LAST_TS="${LAST#*\"ts\":}"; LAST_TS="${LAST_TS%%,*}"
    NEW_TS="${EVENT#*\"ts\":}"; NEW_TS="${NEW_TS%%,*}"
    case "$LAST_TS$NEW_TS" in
      *[!0-9]*) : ;; # unparsable ts — append rather than drop
      *) [ $((NEW_TS - LAST_TS)) -le 2 ] && exit 0 ;;
    esac
  fi
fi

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
