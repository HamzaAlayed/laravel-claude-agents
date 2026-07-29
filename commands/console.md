---
description: Open the Guild web console — a browser UI that launches, streams, and steers agent runs in this project.
argument-hint: [port]
allowed-tools: Bash, Read, Glob
---

# Guild console

Serve the web console for this project. It launches runs (a slash command, a
named specialist, or a freeform task), streams every agent onto a pipeline
board, and surfaces approvals and checkpoint questions as real UI. Claude Code
only — it drives the Claude Agent SDK, which the other runtimes don't ship.

## What you do

1. **Locate the entry script.** `scripts/console/serve.py` in this repo or the
   installed pack; find the plugin copy via
   `~/.claude/plugins/**/laravel-team/scripts/console/serve.py` if needed.

2. **Start it in the background**, from the project root so the console serves
   the right working tree:
   `python3 <path>/scripts/console/serve.py --port ${1:-8378}`
   First run creates `.claude/console/venv` and installs `claude-agent-sdk`
   there — that takes a few seconds and only happens once. Port busy →
   it increments on its own.

3. **Report the tokenized URL it prints.** The token is minted per start and is
   required on every API call; a URL without it will not work.

4. **Don't babysit it.** The page streams over SSE. Your job ends once the URL
   is out. Tell the user to stop it with Ctrl-C in that shell.

## Notes for the user (include in your reply)

- Runs persist to `.claude/console/runs/*.jsonl`; add `.claude/console/` to
  `.gitignore` if `.claude/` is committed.
- A run **parks** until you answer an approval or a checkpoint question — the
  amber bar at the top of the board is the signal.
- The five guardrail hooks still apply. A hook deny outranks every permission
  mode, so the console cannot be used to route around them.
- `/board` is unchanged and still covers runs you start in the terminal.
