---
description: Open the live agents dashboard — an HTML board showing every subagent working, streamed from the emit-agent-events hook.
argument-hint: [port]
allowed-tools: Bash, Read, Glob
---

# Agents board

Serve and open the live dashboard. The `emit-agent-events` hook appends every subagent start / finish to `.claude/agents-board.jsonl`; `board.html` renders it — running agents pulse with a live timer, finished ones show duration and tokens. Claude Code only (the hook doesn't exist on other runtimes).

## What you do

1. **Locate the viewer.** `.claude/board.html` missing → copy it from `scripts/board.html` (install.sh layout) or the plugin's `scripts/` directory (find it via `~/.claude/plugins/**/laravel-team/scripts/board.html` if needed). Feed file missing is fine — the board shows its empty state until the first subagent runs.

2. **Serve `.claude/` over localhost.** Port: first arg, default `8377`; busy → increment until free.
   - `python3 -m http.server <port> --directory .claude` in the background
   - no python3 → `php -S localhost:<port> -t .claude` (through Sail is wrong here — the board is host-side tooling, and the guard hook lets `php -S` through since it's not artisan/composer)

3. **Open it.** `open http://localhost:<port>/board.html` (macOS) / `xdg-open …` (Linux). Report the URL and how to stop the server (`kill <pid>`).

4. **Don't babysit it.** The page polls the feed itself every 1.5s. Your job ends once it's open.

## Notes for the user (include in your reply)

- The feed is per-project local state. Add `.claude/agents-board.jsonl` and `.claude/board.html` to `.gitignore` if `.claude/` is committed.
- The board fills up whenever any workflow command or the `delivery-coordinator` spawns specialists — no per-run setup.
