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
to `Bash`. The pack mitigates this with the explicit "never modify files via Bash"
instruction in each reviewer body, plus the production guardrail hooks
(`block-prod-destructive-sql.sh`, `block-prod-artisan.sh`, `protect-env-files.sh`).

> **There is no per-subagent OS-level Bash sandbox in Claude Code today.** A blanket
> `permissions.deny` in `.claude/settings.json` is **project-wide** — it would also block
> the *builders* (`backend-`, `database-developer`) and `devops-engineer`, which
> legitimately run `git`, `migrate`, and file writes. So the pack does **not** ship a
> forced deny. The control is instruction + allowlist + guardrail hooks.

## Opt-in: a stricter project-wide policy

If your team is willing to constrain *every* agent in the project (including builders)
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
