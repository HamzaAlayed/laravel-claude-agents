---
description: Run a layered review of the current branch diff — correctness, security, test coverage, performance — and aggregate into one verdict.
argument-hint: [base-branch]
allowed-tools: Agent, Read, Bash, Grep, Glob
---

# Review PR — diff against `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

Layered review of the current branch against base `{{args}}` (default `main`). Fan out to specialists, aggregate, return one verdict. You orchestrate; the specialists judge.

## What you do

1. **Get the diff.**
   ```
   BASE="${ARGS:-main}"
   git fetch origin "$BASE" --quiet
   git diff "$BASE"...HEAD --stat
   git diff "$BASE"...HEAD
   ```
   - List changed files, grouped: HTTP, Eloquent/migrations, jobs/events, config, frontend, tests.
   - `git log --oneline "$BASE"..HEAD` for intent.

2. **Fan out** (run the reviews in parallel; each gets the diff + changed-file list):
   - **tech-lead** — correctness, architecture fit, convention adherence (skinny controllers, Actions, Form Requests, Resources, no `env()` outside config), naming, dead code, leaky abstractions.
   - **security-engineer** — authz (Policy/`authorize()` per state change), mass-assignment, injection, secrets in diff, PII handling, file uploads, new routes' middleware.
   - **qa-engineer** — does the diff have tests? Are happy path, failure modes, and authz (allowed + denied) covered? Any changed branch left untested?
   - **performance-engineer** — N+1 introduced, missing eager loads, `SELECT *`, unbounded queries, missing pagination, missing index for a new query shape, cache without invalidation, query-count regression.

3. **Aggregate** each specialist's findings into one report. De-dupe overlaps. Tag each finding with its owner agent + `path:line`.

   ```
   # PR review — <branch> vs {{args}}

   **Verdict:** APPROVE / APPROVE-WITH-NITS / REQUEST-CHANGES

   ## Blocking (must fix before merge)
   - [security] path:line — <issue> → <fix> (owner: backend-developer)
   - [correctness] ...

   ## Should-fix (fix this PR or file a tracked follow-up)
   - [perf] path:line — <issue> → <fix>
   - [tests] ...

   ## Nits (non-blocking)
   - [style] ...

   ## Test coverage of the diff
   <covered / uncovered branches>

   ## Notes for the author
   - ...
   ```

4. **Decide the verdict.**
   - **REQUEST-CHANGES** if any Blocking finding exists (any security Block, broken correctness, an untested new code path with risk, a clear N+1 in a list endpoint).
   - **APPROVE-WITH-NITS** if only Nits remain.
   - **APPROVE** if clean.

5. **Do not edit code.** Findings route to their owner agents (`backend-developer`, `database-developer`, `frontend-developer`) for the actual fixes.
