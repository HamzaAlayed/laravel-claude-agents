---
description: Optimize a slow query or endpoint — capture, EXPLAIN, diagnose, produce a fix plan, hand to database/backend developer.
argument-hint: <route, query, or model method> [--adaptive]
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
---

# Optimize query — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

> **Interface:** Call `python3 scripts/guild-kernel/guild.py` for this delivery — `plan` before any Agent, `ready` to fetch the bounded dependency-ready wave, `claim --stage <id>` before each Agent, then dispatch every claimed lane concurrently, and `report` on `docs/delivery/<name>/stages/<agent>.md` after each return, `board` to print `✔ done / ▶ running / · queued / ✖ failed`. `plan` must pass a nonempty `--done-when` and every typed `--stage-json` must carry success criteria and `owned_paths`; use `--max-parallel` to set the WIP ceiling. If a sprint is running, attach it (`--sprint <id>` or the kernel attaches the single running sprint). Never invent a checkmark; never compose `docs/delivery/<name>/close.md` (the kernel renders that view). Never compose `docs/sprints/<id>/sprint.md` (the kernel renders that view). `plan` prints `RULES:` only for user-approved learned rules; brief every `RULES:` line. Never compose `docs/team/lessons.md` (the kernel renders that view). When the command includes `--issue <n>`, `plan` passes `--issue <n>`. Call `pr --number <n>` once a pull request exists; the kernel re-fetches it. Call `ingest` only for a failing check or a review comment the kernel confirms. Never compose issue or pr fields. A workplace delivery stays running until the recorded PR state is open. Never merge. Writers Write the six fields `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines) as their last act; never write a writer's stage file for them. Read-only specialists — persist their stage file from the report you already file, then `report`. `VERIFIED:` lines are JSON verification records (`{"runner":"artisan-test","args":["--filter=TagTest"]}`); the kernel accepts only registered runners and executes argv without a shell; prose and legacy command strings are rejected. `NOT-CHECKED:` that names a stage success criterion is a reject. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, persist `docs/delivery/<name>/stages/peer-router.md` and `report` it; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.

Diagnose why `{{args}}` (a route name/path, raw query, or `Model::method`) is slow and produce a fix plan with measured evidence. Measure first. You diagnose; builders apply.

## What you do

1. **Locate the subject.**
   - Route / path → `php artisan route:list | grep '{{args}}'` → controller → the queries it triggers.
   - `Model::method` → read the model + scope. Raw query → take it as given.
   - Identify the table(s), relations, and the call site.

2. **Capture the query + timing.** Before touching anything:
   - Wrap a reproduction with `DB::listen(fn ($q) => Log::info('sql', ['sql' => $q->sql, 'bindings' => $q->bindings, 'ms' => $q->time]))`. Record query count + total ms.
   - Or read Telescope's Queries tab / Pulse slow-queries for the live numbers.
   - Pull the actual SQL (`->toSql()` / Telescope) and run `EXPLAIN ANALYZE <sql>` (MySQL 8 / Postgres). Read: access type (`ALL` = full scan), rows examined vs returned, filesort, temporary table, key used.

3. **Diagnose.** Match against the usual suspects:
   - **Missing index** — `WHERE` / `JOIN` / `ORDER BY` column not indexed. `EXPLAIN` shows `type=ALL` / large rows-examined.
   - **N+1** — query count scales with row count. Relation accessed in a loop / Resource / Blade without eager load.
   - **`SELECT *`** — pulling fat / TEXT / BLOB columns the caller never reads.
   - **Unbounded result set** — no `LIMIT`, whole table into memory.
   - **Missing pagination** — list endpoint returning everything.
   - **Function-on-column** — `WHERE DATE(created_at) = ?`, `WHERE LOWER(email) = ?` — defeats the index. Rewrite to a range / generated column / store normalized.
   - **Leading-wildcard `LIKE '%x'`** — can't use a B-tree index; consider full-text / different access.
   - **Bad join order / cartesian** — duplicated rows from `whereHas` vs `whereRelation`, or a many-to-many fanout.

4. **Produce the fix plan:**

   ```
   # Query optimization — {{args}}

   ## Baseline
   - Query count: <n>   Total DB time: <ms>   p95 endpoint: <ms>
   - Worst query: <sql>
   - EXPLAIN: <access type, rows examined vs returned, key, filesort?>

   ## Diagnosis
   - Root cause: <pattern from above>

   ## Fix plan
   1. <change> — owner: <database-developer | backend-developer>
   2. ...

   ## Projected result + verification
   - Expected: <n→m queries / ms→ms>. Re-run DB::listen + EXPLAIN after to confirm.
   ```

5. **Route the fix.**
   - Index changes, schema, generated columns → **database-developer** (attach the EXPLAIN plan + target).
   - Eager-load, query-shape, `select()` narrowing, pagination, scope rewrites → **backend-developer**.
   - Caching as a fix (after the query is as good as it gets) → loop in **performance-engineer** for the invalidation strategy.

6. **Do not edit code.** Hand the plan to the owners above.
