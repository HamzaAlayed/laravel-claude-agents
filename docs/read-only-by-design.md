# Read-only reviewers: how "can't touch the code" is actually enforced

Three agents are review-only by design — they produce findings, other agents apply
changes: **`tech-lead`**, **`security-engineer`**, **`performance-engineer`**. This
keeps reviews trustworthy and prevents a reviewer from quietly "fixing" what it just
flagged. This page documents exactly how that guarantee is enforced, where it stops,
and how a team can make it airtight.

## The layered controls (what ships in the pack)

1. **Tool allowlist.** Each reviewer's `tools:` lists only read tools
   (`Read, Bash, Grep, Glob`, plus `WebFetch, WebSearch` for `security-engineer`).
   An allowlist excludes everything unlisted — `Edit` and `Write` are not available.
2. **`disallowedTools: Edit, Write`.** This is **load-bearing**, not redundant:
   `memory: project` auto-grants `Read, Write, Edit`, and this line cancels the
   `Write`/`Edit` half of that grant while leaving memory *readable*. Removing it would
   silently make the reviewer writable. Leave it.
3. **Persistence via the orchestrator.** Reviewers **return** their reports; the
   `delivery-coordinator` (which has `Write`) persists them to `docs/security/…`,
   `docs/breakdowns/…`, etc. No reviewer writes its own artifact.
4. **Explicit instruction.** Each reviewer's body states it is read-only and must not
   modify files — including via Bash.

## Where the guarantee stops: bare `Bash`

A reviewer keeps `Bash` (it needs `composer audit`, `php artisan route:list`,
`./vendor/bin/phpstan`, `git diff`, `wrk`, `EXPLAIN`, …). **`Bash` is a write vector**
the tool allowlist cannot scope:

- `sed -i …`, `perl -i`, `tee`, `>` / `>>` redirects
- `git checkout` / `git reset` / `git stash`
- `php artisan migrate` and other state-changing artisan commands

Tool-level config (`tools:` / `disallowedTools:`) gates *tools*, not the *arguments*
to `Bash`.

**Since 1.8.0 this gap is closed deterministically.** The `PreToolUse` hook input
carries `agent_type` when a subagent calls, so the shipped
`enforce-reviewer-readonly.sh` guard blocks write-shaped Bash (`sed -i` / `perl -i`,
output redirects, `tee`, mutating `git` / `artisan` / `composer` / `npm`, `pint`
without `--test`, `rm` / `mv` / `cp` / `chmod`) **only when the caller is
`tech-lead`, `security-engineer`, or `performance-engineer`** — builders,
`devops-engineer`, and the main thread are untouched. Safe forms stay allowed:
`2>&1`, redirects to `/dev/null` / `/tmp`, `migrate:status`, `pint --test`, PHP
`->` arrows. The reviewer-body instructions remain as the first layer;
the hook is the enforcement behind them.

> Scope note: the guard is **Claude Code only** — Gemini CLI's hook input carries no
> agent identity, so there the control remains instruction + allowlist. Codex Core
> ships no subagents, so the question doesn't arise.

## Opt-in: a stricter project-wide policy

The reviewer guard above covers the three read-only roles. If your team additionally
wants to constrain *every* agent in the project (including builders)
and prefers belt-and-suspenders, add deny rules to your project's
`.claude/settings.json`. Tune to your workflow — these examples are deliberately
conservative and **will** block legitimate builder commands, so adopt only with that
understanding:

```json
{
  "permissions": {
    "deny": [
      "Bash(sed -i*)",
      "Bash(perl -i*)",
      "Bash(git checkout*)",
      "Bash(git reset --hard*)",
      "Bash(php artisan migrate:fresh*)",
      "Bash(php artisan db:wipe*)"
    ]
  }
}
```

Deny rules in **top-level** `.claude/settings.json` are also the only control that holds
under an inherited `bypassPermissions` mode — agent frontmatter does not.

## If you want truly sandboxed reviewers

Run reviews in a throwaway worktree or container (read-mounted source), or in CI where
the checkout is ephemeral and discarded. That is the only way to make "a reviewer
cannot mutate my working tree" a hard guarantee rather than a strong convention.
