---
description: Hold one delivery stage until a named reviewer reports a command that exited 0.
argument-hint: <delivery> <stage-id> [reviewer]
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
---

# Pair — `{{args}}`

Call `python3 scripts/guild-kernel/guild.py pair --root . --name <delivery> --stage <id> [--reviewer tech-lead]`. Do not compose `docs/team/lessons.md`; the kernel renders that view.

## What you do

1. **Mark the stage.** Run the pair CLI. An unknown reviewer, the writer pairing with themselves, a finished stage, or a different reviewer than the one already set is a reject. The same reviewer is a no-op.
2. **Wait for `next`.** After the writer reports, `next` returns the reviewer. Do not spawn a reviewer `next` did not return.
3. **Finish on exit 0.** The reviewer writes `docs/delivery/<name>/stages/<reviewer>.md`. The kernel appends their `VERIFIED` command. Exit 0 marks the lane done.

Solo `/make-feature` does not pair unless this command is used.
