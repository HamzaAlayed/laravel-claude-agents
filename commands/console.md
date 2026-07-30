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
  amber bar at the top of the board is the signal. Several agents can park at
  once; the bar counts them and you answer one at a time.
- **Every Bash command asks you** — including read-only ones like `echo hello`,
  which Claude Code would otherwise approve by itself before the console was
  consulted. A `PreToolUse` hook forces them back through the browser, because no
  setting can. Expect a `git status` to park the run just like an `rm` would.
- **"Allow always" means "stop asking me this run"** for Bash: the exact same
  command falls through from then on, while any other command still asks. It also
  persists a settings rule for future sessions, as before.
- **Other tools can still run without asking you** when a settings rule or the
  run's mode already allows them — a `Read` is not forced through the browser. The
  agent's card now says how many of its calls ran unasked, so the transcript is
  not mistaken for an approval record.
- The five guardrail hooks still apply. A hook deny outranks every permission
  mode, so the console cannot be used to route around them — including the
  auto-approved read-only calls above.
- `/board` is unchanged and still covers runs you start in the terminal.
